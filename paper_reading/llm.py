from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.request import Request, urlopen

from paper_reading.models import Paper


def _env_first(names: list[str]) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 20].rstrip() + " ...[truncated]"


def _fallback_analysis(papers: list[Paper], warning: str = "") -> dict[str, Any]:
    source_names = sorted({paper.journal or paper.source for paper in papers})
    daily_summary = "今天没有检索到符合条件的新论文。"
    if papers:
        daily_summary = (
            f"今天筛选出 {len(papers)} 篇论文，来源包括"
            f"{'、'.join(source_names)}。以下总结仅基于题录、摘要和关键词命中，建议阅读原文确认关键结论。"
        )
    paper_notes = {}
    for paper in papers:
        matched = "、".join(paper.keyword_matches) if paper.keyword_matches else "未命中显式关键词"
        paper_notes[paper.id] = {
            "summary": f"这篇论文来自 {paper.journal or paper.source}，关键词匹配：{matched}。",
            "contribution": "需要结合论文摘要和正文进一步判断核心贡献。",
            "why_read": "如果它与你当前关注的关键词或来源优先级一致，可以优先打开原文浏览摘要、图表和实验设置。",
            "limitations": "当前报告没有读取全文；题录元数据可能不足以判断方法细节和结论强度。",
        }
    return {
        "daily_summary": daily_summary,
        "themes": [],
        "papers": paper_notes,
        "llm_used": False,
        "warnings": [warning] if warning else [],
    }


def _paper_payload(papers: list[Paper], max_chars: int) -> list[dict[str, Any]]:
    payload = []
    for paper in papers:
        payload.append(
            {
                "id": paper.id,
                "source": paper.source,
                "journal": paper.journal,
                "title": paper.title,
                "authors": paper.authors[:12],
                "published": paper.published,
                "abstract": _truncate(paper.abstract, max_chars),
                "url": paper.url,
                "doi": paper.doi,
                "categories": paper.categories,
                "keyword_matches": paper.keyword_matches,
            }
        )
    return payload


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_analysis(result: dict[str, Any], papers: list[Paper]) -> dict[str, Any]:
    normalized = {
        "daily_summary": str(result.get("daily_summary") or ""),
        "themes": result.get("themes") if isinstance(result.get("themes"), list) else [],
        "papers": result.get("papers") if isinstance(result.get("papers"), dict) else {},
        "llm_used": True,
        "warnings": [],
    }
    fallback = _fallback_analysis(papers)
    if not normalized["daily_summary"]:
        normalized["daily_summary"] = fallback["daily_summary"]
    for paper in papers:
        note = normalized["papers"].get(paper.id)
        if not isinstance(note, dict):
            normalized["papers"][paper.id] = fallback["papers"].get(paper.id, {})
            continue
        for key in ("summary", "contribution", "why_read", "limitations"):
            note[key] = str(note.get(key) or fallback["papers"][paper.id][key])
    return normalized


def analyze_papers(papers: list[Paper], config: dict[str, Any]) -> dict[str, Any]:
    llm_cfg = config.get("llm", {})
    if not llm_cfg.get("enabled", True):
        return _fallback_analysis(papers, "LLM disabled by configuration.")

    api_key = _env_first(llm_cfg.get("api_key_env") or ["OPENAI_API_KEY", "LLM_API_KEY"])
    if not api_key:
        return _fallback_analysis(papers, "No LLM API key found; generated a metadata-only report.")

    base_url = _env_first(llm_cfg.get("base_url_env") or []) or llm_cfg.get("base_url")
    model = _env_first(llm_cfg.get("model_env") or []) or llm_cfg.get("model")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    max_chars = int(llm_cfg.get("max_input_chars_per_paper") or 1800)
    prompt_payload = {
        "papers": _paper_payload(papers, max_chars),
        "instructions": {
            "language": "zh-CN",
            "style": "面向科研人员的每日阅读简报",
            "avoid": "不要声称读过全文；不要编造实验结果；只根据提供的题录和摘要判断。",
        },
        "required_json_schema": {
            "daily_summary": "string",
            "themes": ["string"],
            "papers": {
                "<paper id>": {
                    "summary": "一到两句中文总结",
                    "contribution": "核心贡献或可能贡献",
                    "why_read": "为什么值得读",
                    "limitations": "基于现有元数据需要警惕什么",
                }
            },
        },
    }
    messages = [
        {
            "role": "system",
            "content": "你是严谨的科研阅读助手。输出必须是合法 JSON，不要输出 Markdown。",
        },
        {
            "role": "user",
            "content": json.dumps(prompt_payload, ensure_ascii=False),
        },
    ]
    body = {
        "model": model,
        "messages": messages,
        "temperature": float(llm_cfg.get("temperature", 0.2)),
    }
    request = Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=int(llm_cfg.get("timeout_seconds") or 90)) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        result = _extract_json(content)
        return _normalize_analysis(result, papers)
    except Exception as exc:  # noqa: BLE001 - report generation should survive LLM failures.
        return _fallback_analysis(papers, f"LLM call failed: {exc}")
