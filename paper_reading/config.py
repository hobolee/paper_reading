from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONFIG: dict[str, Any] = {
    "daily": {
        "max_papers": 20,
        "lookback_days": 7,
        "timezone": "Asia/Shanghai",
        "dedupe_history": True,
    },
    "report": {
        "title": "Paper Reading",
        "language": "zh",
        "output_dir": "docs",
        "history_dir": "reports",
        "data_dir": "data",
    },
    "filters": {
        "require_keywords": True,
        "keyword_optional_sources": [],
        "keywords": [],
        "exclude_keywords": [],
    },
    "selection": {
        "source_minimums": {},
    },
    "feedback": {
        "enabled": True,
        "github_issues_enabled": True,
        "github_repo": "",
        "issue_label": "paper-feedback",
        "local_file": "data/feedback.json",
        "rating_weights": {
            "star": 22,
            "like": 14,
            "read": -4,
            "dislike": -28,
        },
    },
    "ranking": {
        "source_priority": {"nature": 20, "science": 20, "arxiv": 10},
    },
    "sources": {
        "arxiv": {
            "enabled": True,
            "categories": ["cs.AI", "cs.CL", "cs.LG", "stat.ML"],
            "fetch_limit": 80,
        },
        "journals": {
            "enabled": True,
            "fetch_limit_per_journal": 40,
            "fetch_page_size": 50,
            "article_only": True,
            "exclude_title_patterns": [],
            "items": [],
        },
    },
    "llm": {
        "enabled": True,
        "api_key_env": ["OPENAI_API_KEY", "LLM_API_KEY"],
        "base_url_env": ["OPENAI_BASE_URL", "LLM_BASE_URL"],
        "model_env": ["OPENAI_MODEL", "LLM_MODEL"],
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "temperature": 0.2,
        "timeout_seconds": 90,
        "max_input_chars_per_paper": 1800,
    },
    "email": {
        "enabled": True,
        "provider": "gmail-smtp",
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True,
        "username_env": ["GMAIL_USERNAME", "SMTP_USERNAME"],
        "password_env": ["GMAIL_APP_PASSWORD", "SMTP_PASSWORD"],
        "from_env": ["MAIL_FROM", "GMAIL_USERNAME"],
        "to_env": ["MAIL_TO"],
        "subject_prefix": "[Paper Reading]",
        "timeout_seconds": 60,
    },
    "http": {
        "user_agent": "paper-reading-bot/0.1",
        "mailto": "",
        "timeout_seconds": 30,
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required. Run: pip install -r requirements.txt") from exc

    with config_path.open("r", encoding="utf-8") as file_obj:
        loaded = yaml.safe_load(file_obj) or {}
    if not isinstance(loaded, dict):
        raise ValueError("Config root must be a mapping.")
    return deep_merge(DEFAULT_CONFIG, loaded)
