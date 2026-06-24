from __future__ import annotations

from datetime import date, datetime, timezone
from collections.abc import Iterable
from typing import Any

from paper_reading.models import Paper


def _norm(value: str) -> str:
    return value.casefold()


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    cleaned = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _keyword_matches(text: str, keywords: list[str]) -> list[str]:
    lowered = _norm(text)
    return [keyword for keyword in keywords if keyword and _norm(keyword) in lowered]


def _normalize_keyword_groups(raw_keywords: Any) -> list[list[str]]:
    if not raw_keywords:
        return []
    if isinstance(raw_keywords, str):
        keyword = raw_keywords.strip()
        return [[keyword]] if keyword else []
    if not isinstance(raw_keywords, Iterable):
        keyword = str(raw_keywords).strip()
        return [[keyword]] if keyword else []

    items = list(raw_keywords)
    has_nested_group = any(isinstance(item, Iterable) and not isinstance(item, str) for item in items)
    if not has_nested_group:
        flat_group = [str(item).strip() for item in items if str(item).strip()]
        return [flat_group] if flat_group else []

    groups: list[list[str]] = []
    for item in items:
        if isinstance(item, str):
            group = [item.strip()] if item.strip() else []
        elif isinstance(item, Iterable):
            group = [str(keyword).strip() for keyword in item if str(keyword).strip()]
        else:
            keyword = str(item).strip()
            group = [keyword] if keyword else []
        if group:
            groups.append(group)
    return groups


def _flatten_keyword_groups(groups: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for keyword in group:
            key = _norm(keyword)
            if key not in seen:
                seen.add(key)
                flattened.append(keyword)
    return flattened


def _grouped_keyword_matches(text: str, groups: list[list[str]]) -> tuple[bool, list[str]]:
    if not groups:
        return True, []
    all_matches: list[str] = []
    seen: set[str] = set()
    for group in groups:
        group_matches = _keyword_matches(text, group)
        if not group_matches:
            return False, []
        for keyword in group_matches:
            key = _norm(keyword)
            if key not in seen:
                seen.add(key)
                all_matches.append(keyword)
    return True, all_matches


def _recency_score(paper: Paper) -> float:
    paper_date = _parse_date(paper.published) or _parse_date(paper.updated)
    if not paper_date:
        return 0.0
    days_old = max((datetime.now(timezone.utc).date() - paper_date).days, 0)
    if days_old <= 1:
        return 8.0
    if days_old <= 3:
        return 5.0
    if days_old <= 7:
        return 3.0
    return 1.0


def _score_paper(paper: Paper, matches: list[str], config: dict[str, Any]) -> float:
    source_priority = config.get("ranking", {}).get("source_priority", {})
    title_matches = _keyword_matches(paper.title, matches)
    abstract_matches = _keyword_matches(paper.abstract, matches)
    return (
        float(source_priority.get(paper.source, 0))
        + len(matches) * 2.0
        + len(title_matches) * 4.0
        + len(abstract_matches) * 1.5
        + _recency_score(paper)
    )


def dedupe_papers(papers: list[Paper]) -> list[Paper]:
    seen: set[str] = set()
    unique: list[Paper] = []
    for paper in papers:
        key = paper.stable_key()
        if key in seen:
            continue
        seen.add(key)
        unique.append(paper)
    return unique


def rank_and_filter(papers: list[Paper], config: dict[str, Any]) -> tuple[list[Paper], dict[str, int]]:
    filters_cfg = config.get("filters", {})
    keyword_groups = _normalize_keyword_groups(filters_cfg.get("keywords"))
    keywords = _flatten_keyword_groups(keyword_groups)
    excludes = [str(item).strip() for item in filters_cfg.get("exclude_keywords") or [] if str(item).strip()]
    require_keywords = bool(filters_cfg.get("require_keywords", True))

    stats = {
        "fetched": len(papers),
        "deduped": 0,
        "excluded": 0,
        "keyword_filtered": 0,
        "ranked": 0,
    }
    filtered: list[Paper] = []
    for paper in dedupe_papers(papers):
        text = paper.match_text()
        exclude_matches = _keyword_matches(text, excludes)
        if exclude_matches:
            stats["excluded"] += 1
            continue
        grouped_match, grouped_matches = _grouped_keyword_matches(text, keyword_groups)
        matches = grouped_matches if require_keywords else _keyword_matches(text, keywords)
        if require_keywords and keyword_groups and not grouped_match:
            stats["keyword_filtered"] += 1
            continue
        paper.keyword_matches = matches
        paper.score = _score_paper(paper, matches or keywords, config)
        filtered.append(paper)

    stats["deduped"] = len(filtered)
    stats["ranked"] = len(filtered)
    filtered.sort(key=lambda item: (item.score, item.published, item.updated), reverse=True)
    return filtered, stats
