from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def user_agent(config: dict[str, Any]) -> str:
    http_cfg = config.get("http", {})
    agent = http_cfg.get("user_agent") or "paper-reading-bot/0.1"
    mailto = http_cfg.get("mailto") or ""
    if mailto and "mailto:" not in agent:
        return f"{agent} (mailto:{mailto})"
    return agent


def fetch_text(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> str:
    if params:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}{urlencode(params, doseq=True)}"
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    text = fetch_text(url, params=params, headers=headers, timeout=timeout)
    return json.loads(text)
