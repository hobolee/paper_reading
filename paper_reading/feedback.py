from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from paper_reading.models import Paper


RATINGS = {"star", "like", "dislike"}


@dataclass
class Feedback:
    ratings: dict[str, str] = field(default_factory=dict)
    liked_keywords: Counter[str] = field(default_factory=Counter)
    disliked_keywords: Counter[str] = field(default_factory=Counter)
    liked_sources: Counter[str] = field(default_factory=Counter)
    disliked_sources: Counter[str] = field(default_factory=Counter)
    issue_count: int = 0
    warnings: list[str] = field(default_factory=list)


def _norm(value: str) -> str:
    return value.strip().casefold()


def _split_keywords(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,;，；]", value or "") if item.strip()]


def _load_local_feedback(path: Path) -> Feedback:
    feedback = Feedback()
    if not path.exists():
        return feedback
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return feedback
    ratings = data.get("ratings")
    if isinstance(ratings, dict):
        for paper_id, rating in ratings.items():
            rating_key = _norm(str(rating))
            if rating_key in RATINGS:
                feedback.ratings[str(paper_id)] = rating_key
    for key, target in (
        ("liked_keywords", feedback.liked_keywords),
        ("disliked_keywords", feedback.disliked_keywords),
        ("liked_sources", feedback.liked_sources),
        ("disliked_sources", feedback.disliked_sources),
    ):
        values = data.get(key)
        if isinstance(values, list):
            target.update(_norm(str(value)) for value in values if str(value).strip())
        elif isinstance(values, dict):
            for value, count in values.items():
                try:
                    target[_norm(str(value))] += int(count)
                except (TypeError, ValueError):
                    continue
    return feedback


def _parse_issue_body(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = _norm(key)
        if key in {"paper_id", "rating", "source", "keywords", "title"}:
            fields[key] = value.strip()
    return fields


def _apply_issue_feedback(feedback: Feedback, fields: dict[str, str]) -> None:
    rating = _norm(fields.get("rating", ""))
    paper_id = fields.get("paper_id", "")
    if rating not in RATINGS or not paper_id:
        return
    feedback.ratings[paper_id] = rating
    source = _norm(fields.get("source", ""))
    keywords = [_norm(keyword) for keyword in _split_keywords(fields.get("keywords", ""))]
    if rating in {"star", "like"}:
        feedback.liked_keywords.update(keyword for keyword in keywords if keyword)
        if source:
            feedback.liked_sources[source] += 1
    elif rating == "dislike":
        feedback.disliked_keywords.update(keyword for keyword in keywords if keyword)
        if source:
            feedback.disliked_sources[source] += 1


def _fetch_github_issue_feedback(config: dict[str, Any]) -> Feedback:
    feedback = Feedback()
    feedback_cfg = config.get("feedback", {})
    repo = (
        os.getenv("GITHUB_REPOSITORY")
        or str(feedback_cfg.get("github_repo") or "").strip()
    )
    token = os.getenv("GITHUB_TOKEN", "")
    if not repo:
        return feedback
    url = "https://api.github.com/repos/{repo}/issues?{query}".format(
        repo=repo,
        query=urlencode({"state": "all", "per_page": 100}),
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "paper-reading-feedback",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            issues = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - feedback should never block reports.
        feedback.warnings.append(f"GitHub feedback fetch failed: {exc}")
        return feedback
    if not isinstance(issues, list):
        return feedback
    for issue in issues:
        if not isinstance(issue, dict) or "pull_request" in issue:
            continue
        fields = _parse_issue_body(str(issue.get("body") or ""))
        before = len(feedback.ratings)
        _apply_issue_feedback(feedback, fields)
        if len(feedback.ratings) != before:
            feedback.issue_count += 1
    return feedback


def _merge_feedback(items: list[Feedback]) -> Feedback:
    merged = Feedback()
    for item in items:
        merged.ratings.update(item.ratings)
        merged.liked_keywords.update(item.liked_keywords)
        merged.disliked_keywords.update(item.disliked_keywords)
        merged.liked_sources.update(item.liked_sources)
        merged.disliked_sources.update(item.disliked_sources)
        merged.issue_count += item.issue_count
        merged.warnings.extend(item.warnings)
    return merged


def load_feedback(config: dict[str, Any]) -> Feedback:
    feedback_cfg = config.get("feedback", {})
    if not feedback_cfg.get("enabled", True):
        return Feedback()
    local = _load_local_feedback(Path(feedback_cfg.get("local_file") or "data/feedback.json"))
    sources = [local]
    if feedback_cfg.get("github_issues_enabled", True):
        sources.append(_fetch_github_issue_feedback(config))
    return _merge_feedback(sources)


def feedback_score(paper: Paper, feedback: Feedback, config: dict[str, Any]) -> float:
    if not feedback:
        return 0.0
    weights = config.get("feedback", {}).get("rating_weights") or {}
    score = 0.0
    rating = feedback.ratings.get(paper.stable_key()) or feedback.ratings.get(paper.id)
    if rating:
        score += float(weights.get(rating, 0))
    source = _norm(paper.source)
    score += min(feedback.liked_sources.get(source, 0) * 2.0, 10.0)
    score -= min(feedback.disliked_sources.get(source, 0) * 3.0, 12.0)
    for keyword in paper.keyword_matches:
        key = _norm(keyword)
        score += min(feedback.liked_keywords.get(key, 0) * 2.0, 8.0)
        score -= min(feedback.disliked_keywords.get(key, 0) * 2.5, 10.0)
    return score


def feedback_issue_url(config: dict[str, Any], paper: Paper, rating: str) -> str:
    feedback_cfg = config.get("feedback", {})
    repo = (
        os.getenv("GITHUB_REPOSITORY")
        or str(feedback_cfg.get("github_repo") or "").strip()
    )
    if not repo:
        return ""
    label = str(feedback_cfg.get("issue_label") or "paper-feedback")
    keywords = ", ".join(paper.keyword_matches)
    body = "\n".join(
        [
            f"paper_id: {paper.stable_key()}",
            f"rating: {rating}",
            f"source: {paper.source}",
            f"title: {paper.title}",
            f"keywords: {keywords}",
            "",
            "notes:",
        ]
    )
    title = f"[paper-feedback] {rating}: {paper.title[:80]}"
    return "https://github.com/{repo}/issues/new?{query}".format(
        repo=repo,
        query=urlencode({"title": title, "labels": label, "body": body}),
    )
