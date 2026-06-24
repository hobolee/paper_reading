from __future__ import annotations

import html
import re
from datetime import date, timedelta
from typing import Any

from paper_reading.http import fetch_json, user_agent
from paper_reading.models import Paper


API_URL = "https://api.crossref.org/journals/{issn}/works"


def _short_error(exc: Exception, limit: int = 260) -> str:
    text = re.sub(r"\s+", " ", str(exc)).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _first(values: Any) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    if isinstance(values, str):
        return values
    return ""


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    without_tags = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(without_tags)).strip()


def _date_from_parts(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    parts = value.get("date-parts") or []
    if not parts or not parts[0]:
        return ""
    year = int(parts[0][0])
    month = int(parts[0][1]) if len(parts[0]) > 1 else 1
    day = int(parts[0][2]) if len(parts[0]) > 2 else 1
    return f"{year:04d}-{month:02d}-{day:02d}"


def _published_date(item: dict[str, Any]) -> str:
    for key in ("published-online", "published-print", "published", "issued", "created"):
        parsed = _date_from_parts(item.get(key))
        if parsed:
            return parsed
    return ""


def _authors(item: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for author in item.get("author") or []:
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = " ".join(part for part in [given, family] if part).strip()
        if name:
            names.append(name)
    return names


def _patterns(config: dict[str, Any], key: str) -> list[str]:
    values = config.get(key) or []
    if isinstance(values, str):
        return [values]
    return [str(value) for value in values if str(value)]


def _matches_any(value: str, patterns: list[str]) -> bool:
    if not value or not patterns:
        return False
    for pattern in patterns:
        if re.search(pattern, value, flags=re.IGNORECASE):
            return True
    return False


def _reference_count(item: dict[str, Any]) -> int:
    for key in ("reference-count", "references-count"):
        value = item.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    references = item.get("reference")
    return len(references) if isinstance(references, list) else 0


def _merged_journal_cfg(journals_cfg: dict[str, Any], journal_cfg: dict[str, Any]) -> dict[str, Any]:
    merged = {
        "article_only": journals_cfg.get("article_only", True),
        "exclude_title_patterns": _patterns(journals_cfg, "exclude_title_patterns"),
        "exclude_doi_patterns": _patterns(journals_cfg, "exclude_doi_patterns"),
        "exclude_url_patterns": _patterns(journals_cfg, "exclude_url_patterns"),
    }
    merged.update(journal_cfg)
    for key in (
        "include_title_patterns",
        "include_doi_patterns",
        "include_url_patterns",
        "exclude_title_patterns",
        "exclude_doi_patterns",
        "exclude_url_patterns",
    ):
        inherited = _patterns(merged, key)
        local = _patterns(journal_cfg, key)
        if key.startswith("exclude_"):
            inherited = _patterns(journals_cfg, key) + local
        merged[key] = inherited
    return merged


def _resource_url(item: dict[str, Any]) -> str:
    resource = item.get("resource")
    if isinstance(resource, dict):
        primary = resource.get("primary")
        if isinstance(primary, dict) and primary.get("URL"):
            return str(primary["URL"])
    return str(item.get("URL") or "")


def _passes_article_filter(item: dict[str, Any], journal_cfg: dict[str, Any]) -> bool:
    if not journal_cfg.get("article_only", True):
        return True

    title = _clean_text(_first(item.get("title")))
    doi = str(item.get("DOI") or "").strip()
    url = _resource_url(item)
    abstract = _clean_text(item.get("abstract"))

    if _matches_any(title, _patterns(journal_cfg, "exclude_title_patterns")):
        return False
    if _matches_any(doi, _patterns(journal_cfg, "exclude_doi_patterns")):
        return False
    if _matches_any(url, _patterns(journal_cfg, "exclude_url_patterns")):
        return False

    include_title_patterns = _patterns(journal_cfg, "include_title_patterns")
    include_doi_patterns = _patterns(journal_cfg, "include_doi_patterns")
    include_url_patterns = _patterns(journal_cfg, "include_url_patterns")
    if include_title_patterns and not _matches_any(title, include_title_patterns):
        return False
    if include_doi_patterns and not _matches_any(doi, include_doi_patterns):
        return False
    if include_url_patterns and not _matches_any(url, include_url_patterns):
        return False

    if journal_cfg.get("require_abstract") and not abstract:
        return False
    min_references = int(journal_cfg.get("min_references") or 0)
    if min_references and _reference_count(item) < min_references:
        return False
    return True


def _paper_from_item(item: dict[str, Any], journal_cfg: dict[str, Any]) -> Paper | None:
    title = _clean_text(_first(item.get("title")))
    doi = str(item.get("DOI") or "").strip()
    url = str(item.get("URL") or "").strip()
    if not title or not (doi or url):
        return None
    journal_name = _clean_text(_first(item.get("container-title"))) or journal_cfg.get("name", "")
    published = _published_date(item)
    abstract = _clean_text(item.get("abstract"))
    paper_id = f"doi:{doi.lower()}" if doi else f"{journal_cfg.get('id')}:{url}"
    return Paper(
        id=paper_id,
        source=str(journal_cfg.get("id") or journal_name).lower(),
        title=title,
        authors=_authors(item),
        published=published,
        updated=_date_from_parts(item.get("indexed")),
        abstract=abstract,
        url=url or (f"https://doi.org/{doi}" if doi else ""),
        doi=doi,
        journal=journal_name,
        categories=[str(item.get("type") or "journal-article")],
        raw={
            "publisher": item.get("publisher"),
            "volume": item.get("volume"),
            "issue": item.get("issue"),
            "page": item.get("page"),
            "reference_count": _reference_count(item),
            "resource_url": _resource_url(item),
        },
    )


def _page_size(journals_cfg: dict[str, Any]) -> int:
    try:
        value = int(journals_cfg.get("fetch_page_size") or 50)
    except (TypeError, ValueError):
        value = 50
    return min(max(value, 1), 100)


def fetch_journals(config: dict[str, Any]) -> tuple[list[Paper], list[str]]:
    sources_cfg = config.get("sources", {})
    journals_cfg = sources_cfg.get("journals", {})
    if not journals_cfg.get("enabled", True):
        return [], []

    lookback_days = int(config.get("daily", {}).get("lookback_days") or 7)
    from_date = (date.today() - timedelta(days=lookback_days)).isoformat()
    scan_limit = int(journals_cfg.get("fetch_limit_per_journal") or 40)
    rows = _page_size(journals_cfg)
    timeout = int(config.get("http", {}).get("timeout_seconds") or 30)
    headers = {"User-Agent": user_agent(config)}
    papers: list[Paper] = []
    warnings: list[str] = []

    for journal_cfg in journals_cfg.get("items") or []:
        if not journal_cfg.get("enabled", True):
            continue
        issns = journal_cfg.get("issns") or []
        if not issns:
            continue
        merged_cfg = _merged_journal_cfg(journals_cfg, journal_cfg)
        journal_name = str(journal_cfg.get("name") or journal_cfg.get("id") or issns[0])
        for offset in range(0, scan_limit, rows):
            batch_rows = min(rows, scan_limit - offset)
            params = {
                "rows": batch_rows,
                "offset": offset,
                "sort": "published",
                "order": "desc",
                "filter": f"type:journal-article,from-pub-date:{from_date}",
            }
            try:
                data = fetch_json(
                    API_URL.format(issn=issns[0]),
                    params=params,
                    headers=headers,
                    timeout=timeout,
                )
            except Exception as exc:  # noqa: BLE001 - keep other journal pages alive.
                warnings.append(
                    f"{journal_name} Crossref page failed at offset {offset}: {_short_error(exc)}"
                )
                continue
            items = data.get("message", {}).get("items", [])
            if not items:
                break
            for item in items:
                if not _passes_article_filter(item, merged_cfg):
                    continue
                paper = _paper_from_item(item, merged_cfg)
                if paper:
                    papers.append(paper)
    return papers, warnings
