from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from paper_reading.config import load_config
from paper_reading.emailer import send_report_email
from paper_reading.filters import rank_and_filter
from paper_reading.llm import analyze_papers
from paper_reading.models import Paper
from paper_reading.report import write_report
from paper_reading.sources.arxiv import fetch_arxiv
from paper_reading.sources.crossref import fetch_journals
from paper_reading.storage import load_seen, save_daily_json, save_seen


def _sample_papers() -> list[Paper]:
    return [
        Paper(
            id="sample:llm-biology",
            source="nature",
            journal="Nature",
            title="Multimodal foundation models reveal new signals in earth observation maps",
            authors=["Ada Chen", "Min Li", "Sara Patel"],
            published=date.today().isoformat(),
            abstract=(
                "A multimodal foundation model is trained on earth observation profiles to identify "
                "shared representations across climate states and experimental conditions."
            ),
            url="https://www.nature.com/",
            categories=["journal-article"],
        ),
        Paper(
            id="sample:science-climate",
            source="science",
            journal="Science",
            title="Machine learning improves near-term climate risk forecasts",
            authors=["Rui Zhang", "Elena Garcia"],
            published=date.today().isoformat(),
            abstract=(
                "The study combines physical simulations and machine learning to improve regional "
                "climate risk forecasts under sparse observations."
            ),
            url="https://www.science.org/journal/science",
            categories=["journal-article"],
        ),
        Paper(
            id="arxiv:2606.00001",
            source="arxiv",
            journal="arXiv",
            title="Large language model agents for literature triage",
            authors=["Jamie Smith", "Lin Wang"],
            published=date.today().isoformat(),
            abstract=(
                "We introduce an agentic workflow for literature triage that ranks papers by user "
                "intent, summarizes evidence, and preserves citation links."
            ),
            url="https://arxiv.org/abs/2606.00001",
            pdf_url="https://arxiv.org/pdf/2606.00001",
            categories=["cs.CL", "cs.AI"],
        ),
    ]


def _fetch_all(config: dict[str, Any]) -> tuple[list[Paper], list[str]]:
    papers: list[Paper] = []
    warnings: list[str] = []
    for label, fetcher in (("arXiv", fetch_arxiv), ("journals", fetch_journals)):
        try:
            result = fetcher(config)
            if isinstance(result, tuple):
                source_papers, source_warnings = result
                papers.extend(source_papers)
                warnings.extend(str(warning) for warning in source_warnings)
            else:
                papers.extend(result)
        except Exception as exc:  # noqa: BLE001 - one broken source should not kill the report.
            warnings.append(f"{label} fetch failed: {exc}")
    return papers, warnings


def _configured_today(config: dict[str, Any]) -> str:
    timezone_name = str(config.get("daily", {}).get("timezone") or "UTC")
    try:
        from datetime import datetime

        return datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    except Exception:
        return date.today().isoformat()


def _source_minimums(config: dict[str, Any]) -> dict[str, int]:
    raw = config.get("selection", {}).get("source_minimums") or {}
    minimums: dict[str, int] = {}
    if not isinstance(raw, dict):
        return minimums
    for source, count in raw.items():
        try:
            parsed = int(count)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            minimums[str(source).lower()] = parsed
    return minimums


def select_papers(candidates: list[Paper], max_papers: int, config: dict[str, Any]) -> list[Paper]:
    minimums = _source_minimums(config)
    selected: list[Paper] = []
    selected_keys: set[str] = set()

    for source, minimum in minimums.items():
        picked = 0
        for paper in candidates:
            if picked >= minimum or len(selected) >= max_papers:
                break
            if paper.source != source or paper.stable_key() in selected_keys:
                continue
            selected.append(paper)
            selected_keys.add(paper.stable_key())
            picked += 1

    for paper in candidates:
        if len(selected) >= max_papers:
            break
        if paper.stable_key() in selected_keys:
            continue
        selected.append(paper)
        selected_keys.add(paper.stable_key())

    selected.sort(key=lambda item: (item.score, item.published, item.updated), reverse=True)
    return selected


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    if args.no_llm:
        config["llm"]["enabled"] = False

    run_date = args.date or _configured_today(config)
    fetched, source_warnings = (_sample_papers(), []) if args.sample else _fetch_all(config)
    ranked, stats = rank_and_filter(fetched, config)
    stats["source_warnings"] = len(source_warnings)

    max_papers = int(config.get("daily", {}).get("max_papers") or 20)
    dedupe_history = bool(config.get("daily", {}).get("dedupe_history", True))
    seen = load_seen(config) if dedupe_history else set()
    if args.include_seen:
        candidates = ranked
    else:
        candidates = [paper for paper in ranked if paper.stable_key() not in seen]
    stats["seen_filtered"] = len(ranked) - len(candidates)
    selected = select_papers(candidates, max_papers, config)
    stats["selected_by_source"] = dict(Counter(paper.source for paper in selected))

    analysis = analyze_papers(selected, config)
    if source_warnings:
        analysis.setdefault("warnings", [])
        analysis["warnings"].extend(source_warnings)

    paths = write_report(config, run_date, selected, analysis, stats)
    save_daily_json(config, run_date, selected, analysis, stats)

    if dedupe_history:
        for paper in selected:
            seen.add(paper.stable_key())
        save_seen(config, seen)

    print(f"Fetched: {stats['fetched']}")
    print(f"Ranked: {stats['ranked']}")
    print(f"Selected: {len(selected)}")
    print(f"Latest report: {paths['latest']}")
    print(f"Historical report: {paths['report']}")
    if analysis.get("warnings"):
        print("Warnings:")
        for warning in analysis["warnings"]:
            print(f"- {warning}")
    return 0


def send_email(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    send_report_email(config, args.report, args.date or _configured_today(config))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate daily paper reading report.")
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="Fetch, summarize, and render a report.")
    run_parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    run_parser.add_argument("--date", default="", help="Report date, YYYY-MM-DD.")
    run_parser.add_argument("--sample", action="store_true", help="Use built-in sample papers.")
    run_parser.add_argument("--include-seen", action="store_true", help="Do not filter historical papers.")
    run_parser.add_argument("--no-llm", action="store_true", help="Skip LLM calls.")
    email_parser = subparsers.add_parser("send-email", help="Send the generated HTML report by email.")
    email_parser.add_argument("--config", default="config.yaml", help="Path to config YAML.")
    email_parser.add_argument("--report", default="docs/index.html", help="Path to report HTML.")
    email_parser.add_argument("--date", default="", help="Report date for the email subject.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command in (None, "run"):
        if args.command is None:
            args = parser.parse_args(["run", *(argv or [])])
        return run(args)
    if args.command == "send-email":
        return send_email(args)
    parser.print_help()
    return 1
