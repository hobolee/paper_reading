from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from typing import Any

from paper_reading.http import fetch_text, user_agent
from paper_reading.models import Paper


API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _entry_id(value: str) -> str:
    if "/abs/" in value:
        return "arxiv:" + value.rsplit("/abs/", 1)[-1]
    return "arxiv:" + value.rsplit("/", 1)[-1]


def _query_for_categories(categories: list[str]) -> str:
    if not categories:
        return "all:*"
    return " OR ".join(f"cat:{category}" for category in categories)


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _positive_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _is_transient_error(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in ("HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "Network error"))


def _short_error(exc: Exception, limit: int = 220) -> str:
    cleaned = re.sub(r"\s+", " ", str(exc)).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def _parse_feed(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers: list[Paper] = []

    for entry in root.findall("atom:entry", ATOM_NS):
        entry_url = _clean_text(entry.findtext("atom:id", default="", namespaces=ATOM_NS))
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        abstract = _clean_text(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
        published = _clean_text(entry.findtext("atom:published", default="", namespaces=ATOM_NS))
        updated = _clean_text(entry.findtext("atom:updated", default="", namespaces=ATOM_NS))
        authors = [
            _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        authors = [author for author in authors if author]
        categories = [
            category.attrib.get("term", "")
            for category in entry.findall("atom:category", ATOM_NS)
            if category.attrib.get("term")
        ]
        pdf_url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                pdf_url = link.attrib.get("href", "")
                break
        if not title or not entry_url:
            continue
        papers.append(
            Paper(
                id=_entry_id(entry_url),
                source="arxiv",
                title=title,
                authors=authors,
                published=published,
                updated=updated,
                abstract=abstract,
                url=entry_url,
                pdf_url=pdf_url,
                journal="arXiv",
                categories=categories,
            )
        )
    return papers


def fetch_arxiv(config: dict[str, Any]) -> tuple[list[Paper], list[str]]:
    source_cfg = config.get("sources", {}).get("arxiv", {})
    if not source_cfg.get("enabled", True):
        return [], []

    categories = source_cfg.get("categories") or []
    fetch_limit = _positive_int(source_cfg.get("fetch_limit"), 80)
    page_size = min(_positive_int(source_cfg.get("fetch_page_size"), 50), fetch_limit)
    retry_attempts = _positive_int(source_cfg.get("retry_attempts"), 2)
    retry_backoff_seconds = _positive_float(source_cfg.get("retry_backoff_seconds"), 5.0)
    page_pause_seconds = _positive_float(source_cfg.get("page_pause_seconds"), 3.0)
    max_consecutive_failures = _positive_int(source_cfg.get("max_consecutive_failures"), 2)
    timeout = _positive_int(config.get("http", {}).get("timeout_seconds"), 30)
    headers = {"User-Agent": user_agent(config)}
    query = _query_for_categories(categories)
    papers: list[Paper] = []
    warnings: list[str] = []
    consecutive_failures = 0

    for start in range(0, fetch_limit, page_size):
        remaining = fetch_limit - start
        max_results = min(page_size, remaining)
        params = {
            "search_query": query,
            "start": start,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        last_exc: Exception | None = None
        page_papers: list[Paper] = []
        for attempt in range(1, retry_attempts + 1):
            try:
                xml_text = fetch_text(API_URL, params=params, headers=headers, timeout=timeout)
                page_papers = _parse_feed(xml_text)
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 - one page should not kill the source.
                last_exc = exc
                if attempt >= retry_attempts or not _is_transient_error(exc):
                    break
                time.sleep(retry_backoff_seconds * attempt)

        if last_exc:
            consecutive_failures += 1
            warnings.append(
                f"arXiv page failed at start={start}, max_results={max_results}: {_short_error(last_exc)}"
            )
            if consecutive_failures >= max_consecutive_failures:
                warnings.append(
                    f"arXiv fetch stopped after {consecutive_failures} consecutive page failure(s)."
                )
                break
            continue

        consecutive_failures = 0
        if not page_papers:
            break
        papers.extend(page_papers)
        if len(papers) >= fetch_limit:
            papers = papers[:fetch_limit]
            break
        if page_pause_seconds > 0:
            time.sleep(page_pause_seconds)

    return papers, warnings
