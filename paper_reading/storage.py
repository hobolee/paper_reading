from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper_reading.models import Paper


def data_dir(config: dict[str, Any]) -> Path:
    return Path(config.get("report", {}).get("data_dir") or "data")


def seen_path(config: dict[str, Any]) -> Path:
    return data_dir(config) / "seen_papers.json"


def load_seen(config: dict[str, Any]) -> set[str]:
    path = seen_path(config)
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as file_obj:
        data = json.load(file_obj)
    if isinstance(data, list):
        return {str(item) for item in data}
    return set()


def save_seen(config: dict[str, Any], seen: set[str]) -> None:
    path = seen_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as file_obj:
        json.dump(sorted(seen), file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")
    tmp_path.replace(path)


def save_daily_json(
    config: dict[str, Any],
    run_date: str,
    papers: list[Paper],
    analysis: dict[str, Any],
    stats: dict[str, Any],
) -> Path:
    path = data_dir(config) / "daily" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": run_date,
        "stats": stats,
        "analysis": analysis,
        "papers": [paper.to_dict() for paper in papers],
    }
    with path.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, ensure_ascii=False, indent=2)
        file_obj.write("\n")
    return path
