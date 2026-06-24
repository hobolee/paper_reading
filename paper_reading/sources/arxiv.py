from __future__ import annotations

import re
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


def fetch_arxiv(config: dict[str, Any]) -> list[Paper]:
    source_cfg = config.get("sources", {}).get("arxiv", {})
    if not source_cfg.get("enabled", True):
        return []

    categories = source_cfg.get("categories") or []
    fetch_limit = int(source_cfg.get("fetch_limit") or 80)
    timeout = int(config.get("http", {}).get("timeout_seconds") or 30)
    headers = {"User-Agent": user_agent(config)}
    params = {
        "search_query": _query_for_categories(categories),
        "start": 0,
        "max_results": fetch_limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    xml_text = fetch_text(API_URL, params=params, headers=headers, timeout=timeout)
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
