from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from urllib.error import HTTPError
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


def _first_sentence(value: str, limit: int = 260) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    if not cleaned:
        return ""
    match = re.search(r"(.+?[.!?。！？])\s", cleaned)
    sentence = match.group(1) if match else cleaned
    return _truncate(sentence, limit)


def _metadata_note(paper: Paper) -> dict[str, str]:
    matched = "、".join(paper.keyword_matches) if paper.keyword_matches else "未命中显式关键词"
    source = paper.journal or paper.source
    title = paper.title
    abstract_hint = _first_sentence(paper.abstract, 300)
    if abstract_hint:
        summary = f"{title}。摘要要点：{abstract_hint}"
        contribution = (
            f"摘要中最具体的线索是：{abstract_hint} "
            "阅读时应重点核对它把什么问题变得更可测、可解释或可复现，以及相对已有工作的增量在哪里。"
        )
        limitations = "这是基于题录和摘要的初步判断；需要打开原文核对实验设计、对照基线、统计显著性和适用边界。"
    else:
        summary = f"{title}。当前元数据没有提供摘要，报告只能基于题名、来源和关键词做粗筛。"
        contribution = (
            "题名显示它可能是一篇研究 Article，但 Crossref 未提供摘要；"
            "建议直接打开原文查看 abstract、图 1 和结论部分，再判断是否值得深读。"
        )
        limitations = "缺少摘要会显著降低自动总结质量；这类论文不应只凭本报告判断贡献大小。"
    return {
        "summary": summary,
        "contribution": contribution,
        "why_read": (
            f"来源为 {source}，关键词匹配：{matched}。"
            "如果它与当前主题、主刊优先级或你近期反馈偏好一致，值得先快速浏览摘要和关键图表。"
        ),
        "limitations": limitations,
    }


def _fallback_research_ideas(papers: list[Paper]) -> list[dict[str, str]]:
    ideas = []
    for paper in papers[:5]:
        topic = paper.title
        keywords = "、".join(paper.keyword_matches) if paper.keyword_matches else paper.source
        ideas.append(
            {
                "idea": f"围绕“{topic}”做一个小型 follow-up：验证其中的方法或发现能否迁移到你的目标任务。",
                "why": f"它与 {keywords} 相关，适合转化为可检查的研究假设，而不只是阅读材料。",
                "first_step": "先读摘要、方法和主要图表，记录一个可复现实验或可替换数据集。",
                "risk": "目前只基于题录/摘要生成，真实可行性取决于原文数据、代码和实验细节。",
            }
        )
    return ideas


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
        paper_notes[paper.id] = _metadata_note(paper)
    return {
        "daily_summary": daily_summary,
        "themes": [],
        "research_ideas": _fallback_research_ideas(papers),
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
    return parsed if parsed > 0 else default


def _post_chat_completion(
    endpoint: str,
    api_key: str,
    body: dict[str, Any],
    timeout_seconds: int,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    last_exc: Exception | None = None
    for attempt in range(1, retry_attempts + 1):
        request = Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError:
            raise
        except Exception as exc:  # noqa: BLE001 - transient network/model delays are retried.
            last_exc = exc
            if attempt >= retry_attempts:
                break
            time.sleep(retry_backoff_seconds * attempt)
    raise RuntimeError(
        f"{last_exc} after {retry_attempts} attempt(s), timeout={timeout_seconds}s"
    ) from last_exc


def _chat_json(
    endpoint: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    timeout_seconds: int,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    data = _post_chat_completion(
        endpoint,
        api_key,
        body,
        timeout_seconds,
        retry_attempts,
        retry_backoff_seconds,
    )
    content = data["choices"][0]["message"]["content"]
    return _extract_json(content)


def _normalize_paper_note(result: dict[str, Any], paper: Paper) -> dict[str, str]:
    note = result.get("paper") if isinstance(result.get("paper"), dict) else result
    if not isinstance(note, dict):
        note = {}
    fallback = _metadata_note(paper)
    normalized: dict[str, str] = {}
    for key in ("summary", "contribution", "why_read", "limitations"):
        normalized[key] = str(note.get(key) or fallback[key])
    return normalized


def _analyze_single_paper(
    paper: Paper,
    endpoint: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_seconds: int,
    retry_attempts: int,
    retry_backoff_seconds: float,
    max_chars: int,
) -> dict[str, str]:
    prompt_payload = {
        "paper": _paper_payload([paper], max_chars)[0],
        "instructions": {
            "language": "zh-CN",
            "style": "面向科研人员的单篇论文阅读笔记",
            "paper_notes": (
                "只根据提供的题名、来源、摘要、关键词和元数据分析。"
                "summary、contribution、why_read、limitations 都必须尽量落到具体对象、方法、数据、现象或任务上。"
                "不要输出泛泛模板句；如果摘要为空，要明确说明信息不足。"
            ),
            "avoid": "不要声称读过全文；不要编造实验结果；不要输出 Markdown。",
        },
        "required_json_schema": {
            "summary": "一到两句中文总结，必须包含论文具体对象或任务",
            "contribution": "核心贡献或可能贡献",
            "why_read": "为什么值得读，结合用户关键词、来源或研究机会",
            "limitations": "基于现有元数据需要警惕什么",
        },
    }
    messages = [
        {
            "role": "system",
            "content": "你是严谨的科研阅读助手。输出必须是合法 JSON，不要输出 Markdown。",
        },
        {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
    ]
    result = _chat_json(
        endpoint,
        api_key,
        model,
        messages,
        temperature,
        timeout_seconds,
        retry_attempts,
        retry_backoff_seconds,
    )
    return _normalize_paper_note(result, paper)


def _analysis_from_notes(
    papers: list[Paper],
    paper_notes: dict[str, dict[str, str]],
    llm_used: bool,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    fallback = _fallback_analysis(papers)
    return {
        "daily_summary": fallback["daily_summary"],
        "themes": fallback["themes"],
        "research_ideas": fallback["research_ideas"],
        "papers": paper_notes,
        "llm_used": llm_used,
        "warnings": list(warnings or []),
    }


def _summary_input(papers: list[Paper], paper_notes: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for paper in papers:
        note = paper_notes.get(paper.id, _metadata_note(paper))
        rows.append(
            {
                "id": paper.id,
                "source": paper.source,
                "journal": paper.journal,
                "title": paper.title,
                "published": paper.published,
                "keyword_matches": paper.keyword_matches,
                "score": round(paper.score, 2),
                "summary": _truncate(note.get("summary", ""), 420),
                "contribution": _truncate(note.get("contribution", ""), 420),
                "why_read": _truncate(note.get("why_read", ""), 360),
                "limitations": _truncate(note.get("limitations", ""), 320),
            }
        )
    return rows


def _summarize_daily(
    papers: list[Paper],
    paper_notes: dict[str, dict[str, str]],
    endpoint: str,
    api_key: str,
    model: str,
    temperature: float,
    timeout_seconds: int,
    retry_attempts: int,
    retry_backoff_seconds: float,
) -> dict[str, Any]:
    prompt_payload = {
        "paper_analyses": _summary_input(papers, paper_notes),
        "instructions": {
            "language": "zh-CN",
            "style": "面向科研人员的每日论文阅读总览",
            "daily_summary": "综合今天这些单篇笔记，写一个高密度中文总述，指出主要方向和阅读优先级。",
            "themes": "提炼 3-6 个主题线索，避免空泛标签。",
            "research_ideas": (
                "生成 3-6 个可做研究点，每个点要落到最小下一步实验、复现、数据检查、对照分析或综述整理。"
            ),
            "avoid": "不要声称读过全文；不要编造单篇笔记中没有的信息；不要输出 Markdown。",
        },
        "required_json_schema": {
            "daily_summary": "string",
            "themes": ["string"],
            "research_ideas": [
                {
                    "idea": "可做研究点",
                    "why": "为什么这个点值得做",
                    "first_step": "最小下一步实验或阅读动作",
                    "risk": "主要风险或不确定性",
                }
            ],
        },
    }
    messages = [
        {
            "role": "system",
            "content": "你是严谨的科研阅读助手。输出必须是合法 JSON，不要输出 Markdown。",
        },
        {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
    ]
    result = _chat_json(
        endpoint,
        api_key,
        model,
        messages,
        temperature,
        timeout_seconds,
        retry_attempts,
        retry_backoff_seconds,
    )
    analysis = _analysis_from_notes(papers, paper_notes, llm_used=True)
    if result.get("daily_summary"):
        analysis["daily_summary"] = str(result["daily_summary"])
    if isinstance(result.get("themes"), list):
        analysis["themes"] = result["themes"]
    if isinstance(result.get("research_ideas"), list):
        analysis["research_ideas"] = result["research_ideas"]
    return analysis


def _normalize_analysis(result: dict[str, Any], papers: list[Paper]) -> dict[str, Any]:
    normalized = {
        "daily_summary": str(result.get("daily_summary") or ""),
        "themes": result.get("themes") if isinstance(result.get("themes"), list) else [],
        "papers": result.get("papers") if isinstance(result.get("papers"), dict) else {},
        "research_ideas": result.get("research_ideas")
        if isinstance(result.get("research_ideas"), list)
        else [],
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
    if not normalized["research_ideas"]:
        normalized["research_ideas"] = fallback["research_ideas"]
    return normalized


def analyze_papers(papers: list[Paper], config: dict[str, Any]) -> dict[str, Any]:
    if not papers:
        return _fallback_analysis(papers, "No papers were selected after filtering; skipped LLM analysis.")

    llm_cfg = config.get("llm", {})
    if not llm_cfg.get("enabled", True):
        return _fallback_analysis(papers, "LLM disabled by configuration.")

    api_key = _env_first(llm_cfg.get("api_key_env") or ["OPENAI_API_KEY", "LLM_API_KEY"])
    if not api_key:
        return _fallback_analysis(papers, "No LLM API key found; generated a metadata-only report.")

    base_url = _env_first(llm_cfg.get("base_url_env") or []) or llm_cfg.get("base_url")
    model = _env_first(llm_cfg.get("model_env") or []) or llm_cfg.get("model")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    max_chars = _positive_int(llm_cfg.get("max_input_chars_per_paper"), 1200)
    temperature = float(llm_cfg.get("temperature", 0.2))
    timeout_seconds = _positive_int(llm_cfg.get("timeout_seconds"), 180)
    retry_attempts = _positive_int(llm_cfg.get("retry_attempts"), 1)
    retry_backoff_seconds = _positive_float(llm_cfg.get("retry_backoff_seconds"), 8.0)
    max_consecutive_failures = _positive_int(llm_cfg.get("max_consecutive_failures"), 2)

    paper_notes: dict[str, dict[str, str]] = {}
    warnings: list[str] = []
    llm_successes = 0
    consecutive_failures = 0
    skipped_after_failures = 0

    for paper in papers:
        if consecutive_failures >= max_consecutive_failures:
            paper_notes[paper.id] = _metadata_note(paper)
            skipped_after_failures += 1
            continue
        try:
            paper_notes[paper.id] = _analyze_single_paper(
                paper,
                endpoint,
                api_key,
                model,
                temperature,
                timeout_seconds,
                retry_attempts,
                retry_backoff_seconds,
                max_chars,
            )
            llm_successes += 1
            consecutive_failures = 0
        except Exception as exc:  # noqa: BLE001 - one paper should not kill the report.
            paper_notes[paper.id] = _metadata_note(paper)
            consecutive_failures += 1
            warnings.append(f"LLM paper analysis failed for {paper.id}: {exc}")

    if skipped_after_failures:
        warnings.append(
            "Skipped LLM analysis for "
            f"{skipped_after_failures} paper(s) after {max_consecutive_failures} consecutive failure(s)."
        )

    if not llm_successes:
        analysis = _analysis_from_notes(papers, paper_notes, llm_used=False, warnings=warnings)
        if not warnings:
            analysis["warnings"].append("LLM produced no successful paper analyses.")
        return analysis

    try:
        analysis = _summarize_daily(
            papers,
            paper_notes,
            endpoint,
            api_key,
            model,
            temperature,
            timeout_seconds,
            retry_attempts,
            retry_backoff_seconds,
        )
        analysis["warnings"] = warnings
        return analysis
    except Exception as exc:  # noqa: BLE001 - report generation should survive LLM failures.
        warnings.append(f"LLM daily summary failed: {exc}")
        return _analysis_from_notes(papers, paper_notes, llm_used=True, warnings=warnings)
