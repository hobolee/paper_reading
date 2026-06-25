from __future__ import annotations

import html
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from paper_reading.feedback import feedback_issue_url
from paper_reading.models import Paper


CSS = """
:root {
  color-scheme: light;
  --bg: #f7f7f4;
  --ink: #202124;
  --muted: #626a70;
  --line: #dad7cf;
  --panel: #ffffff;
  --accent: #256f8f;
  --accent-2: #7a4f9a;
  --good: #2f7d50;
  --warn: #9a6a1d;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
}

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

.shell {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
}

.topbar {
  border-bottom: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.76);
}

.topbar-inner {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
}

.brand {
  font-weight: 760;
  letter-spacing: 0;
}

.nav {
  display: flex;
  gap: 14px;
  color: var(--muted);
  font-size: 14px;
}

.hero {
  padding: 38px 0 24px;
  border-bottom: 1px solid var(--line);
}

.eyebrow {
  color: var(--muted);
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: .08em;
}

h1 {
  margin: 8px 0 10px;
  max-width: 840px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1.05;
  letter-spacing: 0;
}

.summary {
  max-width: 880px;
  color: #34383c;
  font-size: 18px;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 24px 0 0;
}

.metric {
  padding: 14px 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.62);
  border-radius: 8px;
}

.metric strong {
  display: block;
  font-size: 24px;
  line-height: 1.1;
}

.metric span {
  color: var(--muted);
  font-size: 13px;
}

.section {
  padding: 28px 0;
  border-bottom: 1px solid var(--line);
}

.section h2 {
  margin: 0 0 14px;
  font-size: 22px;
  letter-spacing: 0;
}

.viz-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
}

.bar-row {
  display: grid;
  grid-template-columns: 92px 1fr 34px;
  gap: 10px;
  align-items: center;
  margin: 10px 0;
}

.bar-label,
.bar-count {
  color: var(--muted);
  font-size: 13px;
}

.bar-track {
  height: 10px;
  background: #e6e2d9;
  border-radius: 999px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-2));
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 5px 10px;
  background: rgba(255, 255, 255, 0.68);
  color: #35393d;
  font-size: 13px;
}

.paper-list {
  display: grid;
  gap: 14px;
}

.paper-card {
  border: 1px solid var(--line);
  background: var(--panel);
  border-radius: 8px;
  padding: 18px;
}

.paper-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--muted);
  font-size: 13px;
}

.source-pill {
  color: white;
  background: var(--accent);
  border-radius: 999px;
  padding: 2px 8px;
}

.paper-card h3 {
  margin: 10px 0 8px;
  font-size: 20px;
  line-height: 1.25;
  letter-spacing: 0;
}

.paper-title-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: start;
}

.feedback-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: flex-end;
}

.feedback-action {
  min-width: 38px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 4px 8px;
  background: #ffffff;
  color: #34383c;
  font-size: 13px;
  text-align: center;
}

.feedback-action:hover {
  text-decoration: none;
  border-color: var(--accent);
}

.authors {
  color: var(--muted);
  font-size: 14px;
  margin-bottom: 12px;
}

.note-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.note {
  border-left: 3px solid var(--accent);
  padding-left: 10px;
}

.note strong {
  display: block;
  margin-bottom: 2px;
  font-size: 13px;
  color: #1f4e63;
}

.note p {
  margin: 0;
  color: #34383c;
}

.abstract {
  margin-top: 12px;
  color: #3b4044;
}

.paper-detail {
  margin-top: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fbfbf8;
}

.paper-detail summary {
  cursor: pointer;
  list-style: none;
  padding: 9px 12px;
  color: #1f4e63;
  font-size: 14px;
  font-weight: 700;
}

.paper-detail summary::-webkit-details-marker {
  display: none;
}

.paper-detail summary::after {
  content: "展开";
  float: right;
  color: var(--muted);
  font-size: 12px;
  font-weight: 500;
}

.paper-detail[open] summary::after {
  content: "收起";
}

.detail-body {
  border-top: 1px solid var(--line);
  padding: 12px;
  color: #34383c;
}

.detail-body p {
  margin: 0 0 10px;
}

.detail-body p:last-child {
  margin-bottom: 0;
}

.detail-body strong {
  color: #1f4e63;
}

.idea-list {
  display: grid;
  gap: 12px;
}

.idea-item {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.68);
  padding: 14px 16px;
}

.idea-item strong {
  display: block;
  margin-bottom: 4px;
  color: #1f4e63;
}

.idea-item p {
  margin: 6px 0 0;
  color: #34383c;
}

.idea-item span {
  color: var(--muted);
  font-size: 13px;
}

.footer {
  padding: 24px 0 36px;
  color: var(--muted);
  font-size: 13px;
}

.empty {
  padding: 24px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
}

@media (max-width: 760px) {
  .topbar-inner,
  .viz-grid,
  .note-grid,
  .paper-title-row {
    grid-template-columns: 1fr;
  }

  .feedback-actions {
    justify-content: flex-start;
  }

  .topbar-inner {
    align-items: flex-start;
    padding: 12px 0;
    flex-direction: column;
  }

  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  h1 {
    font-size: 36px;
  }
}
"""


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _short_authors(authors: list[str]) -> str:
    if not authors:
        return "作者信息暂无"
    if len(authors) <= 4:
        return "、".join(authors)
    return "、".join(authors[:4]) + f" 等 {len(authors)} 人"


def _source_counts(papers: list[Paper]) -> Counter[str]:
    return Counter(paper.journal or paper.source for paper in papers)


def _counter_from_mapping(value: Any) -> Counter[str]:
    if not isinstance(value, dict):
        return Counter()
    counter: Counter[str] = Counter()
    for key, count in value.items():
        try:
            counter[str(key)] = int(count)
        except (TypeError, ValueError):
            continue
    return counter


def _keyword_counts(papers: list[Paper]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for paper in papers:
        counter.update(paper.keyword_matches)
    return counter


def _render_bars(counter: Counter[str]) -> str:
    if not counter:
        return '<p class="empty">暂无来源分布。</p>'
    max_count = max(counter.values()) or 1
    rows = []
    for label, count in counter.most_common():
        width = max(4, round(count / max_count * 100))
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{_esc(label)}</div>
              <div class="bar-track"><div class="bar-fill" style="width: {width}%"></div></div>
              <div class="bar-count">{count}</div>
            </div>
            """
        )
    return "\n".join(rows)


def _render_chips(counter: Counter[str]) -> str:
    if not counter:
        return '<p class="empty">没有关键词命中；可以在配置中调整关键词或关闭强制关键词过滤。</p>'
    chips = [
        f'<span class="chip">{_esc(keyword)} <strong>{count}</strong></span>'
        for keyword, count in counter.most_common(24)
    ]
    return '<div class="chips">' + "\n".join(chips) + "</div>"


def _render_themes(themes: list[Any]) -> str:
    if not themes:
        return ""
    chips = [f'<span class="chip">{_esc(theme)}</span>' for theme in themes[:12]]
    return '<div class="chips">' + "\n".join(chips) + "</div>"


def _render_research_ideas(ideas: list[Any]) -> str:
    if not ideas:
        return '<p class="empty">暂无可做研究点。</p>'
    rows = []
    for idea in ideas[:6]:
        if isinstance(idea, dict):
            title = idea.get("idea") or idea.get("title") or ""
            why = idea.get("why") or ""
            first_step = idea.get("first_step") or ""
            risk = idea.get("risk") or ""
        else:
            title = str(idea)
            why = ""
            first_step = ""
            risk = ""
        rows.append(
            f"""
            <div class="idea-item">
              <strong>{_esc(title)}</strong>
              {f'<p>{_esc(why)}</p>' if why else ''}
              {f'<p><span>第一步：</span>{_esc(first_step)}</p>' if first_step else ''}
              {f'<p><span>风险：</span>{_esc(risk)}</p>' if risk else ''}
            </div>
            """
        )
    return '<div class="idea-list">' + "\n".join(rows) + "</div>"


def _paper_note(analysis: dict[str, Any], paper: Paper) -> dict[str, str]:
    notes = analysis.get("papers") if isinstance(analysis.get("papers"), dict) else {}
    note = notes.get(paper.id) if isinstance(notes.get(paper.id), dict) else {}
    return {
        "summary": str(note.get("summary") or ""),
        "contribution": str(note.get("contribution") or ""),
        "details": str(note.get("details") or ""),
        "why_read": str(note.get("why_read") or ""),
        "limitations": str(note.get("limitations") or ""),
    }


def _render_feedback_actions(config: dict[str, Any], paper: Paper) -> str:
    actions = [
        ("star", "⭐", "收藏/稍后读"),
        ("like", "👍", "有用"),
        ("dislike", "👎", "无关"),
        ("read", "已读", "已读：降低同一论文再次出现优先级"),
    ]
    links = []
    for rating, label, title in actions:
        url = feedback_issue_url(config, paper, rating)
        if not url:
            continue
        links.append(
            f'<a class="feedback-action" href="{_esc(url)}" target="_blank" rel="noopener" title="{_esc(title)}">{_esc(label)}</a>'
        )
    return '<div class="feedback-actions">' + "\n".join(links) + "</div>" if links else ""


def _render_paper(paper: Paper, analysis: dict[str, Any], index: int, config: dict[str, Any]) -> str:
    note = _paper_note(analysis, paper)
    link = paper.url or paper.pdf_url
    doi_part = f' · DOI: <a href="https://doi.org/{_esc(paper.doi)}">{_esc(paper.doi)}</a>' if paper.doi else ""
    pdf_part = f' · <a href="{_esc(paper.pdf_url)}">PDF</a>' if paper.pdf_url else ""
    keywords = Counter({keyword: 1 for keyword in paper.keyword_matches})
    details = note["details"] or note["summary"] or note["contribution"]
    detail_abstract = (
        f'<p class="abstract"><strong>摘要：</strong>{_esc(paper.abstract)}</p>' if paper.abstract else ""
    )
    detail_panel = f"""
      <details class="paper-detail">
        <summary>详情</summary>
        <div class="detail-body">
          <p>{_esc(details)}</p>
          {detail_abstract}
        </div>
      </details>
    """
    return f"""
    <article class="paper-card">
      <div class="paper-meta">
        <span class="source-pill">{_esc(paper.journal or paper.source)}</span>
        <span>{_esc(paper.published or paper.updated or "日期暂无")}</span>
        <span>Score {_esc(f"{paper.score:.1f}")}</span>
      </div>
      <div class="paper-title-row">
        <h3>{index}. <a href="{_esc(link)}">{_esc(paper.title)}</a></h3>
        {_render_feedback_actions(config, paper)}
      </div>
      <div class="authors">{_esc(_short_authors(paper.authors))}{doi_part}{pdf_part}</div>
      {_render_chips(keywords) if paper.keyword_matches else ""}
      <div class="note-grid">
        <div class="note"><strong>一句话</strong><p>{_esc(note["summary"])}</p></div>
        <div class="note"><strong>贡献</strong><p>{_esc(note["contribution"])}</p></div>
      </div>
      {detail_panel}
    </article>
    """


def _empty_paper_message(stats: dict[str, Any]) -> str:
    fetched = int(stats.get("fetched") or 0)
    ranked = int(stats.get("ranked") or 0)
    keyword_filtered = int(stats.get("keyword_filtered") or 0)
    seen_filtered = int(stats.get("seen_filtered") or 0)
    source_warnings = int(stats.get("source_warnings") or 0)
    if ranked and seen_filtered >= ranked:
        return (
            f"今天抓取到 {fetched} 篇论文，其中 {ranked} 篇通过筛选，"
            "但都已经出现在历史记录中。可以等待明天的新论文，或手动运行时加 --include-seen 重新生成。"
        )
    if fetched and keyword_filtered:
        return (
            f"今天抓取到 {fetched} 篇论文，但当前关键词规则过滤掉了 "
            f"{keyword_filtered} 篇。可以扩展关键词、增加 arXiv 分类，或临时关闭强制关键词过滤。"
        )
    if fetched and seen_filtered:
        return (
            f"今天抓取到 {fetched} 篇论文，但它们都已经出现在历史记录中。"
            "如果想重新生成报告，可以运行时加 --include-seen。"
        )
    if source_warnings:
        return "今天没有可用论文，且部分数据源抓取失败。请查看页面底部或 Actions 日志里的 warning。"
    return "今天没有符合条件的新论文。可以放宽关键词、关闭历史去重，或延长 lookback_days。"


def _render_report_index(output_dir: Path, history_dir: Path) -> None:
    reports = sorted(history_dir.glob("*.html"), reverse=True)
    items = "\n".join(
        f'<li><a href="{_esc(path.name)}">{_esc(path.stem)}</a></li>' for path in reports
    )
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>历史报告</title>
  <link rel="stylesheet" href="../assets/styles.css">
</head>
<body>
  <header class="topbar"><div class="shell topbar-inner"><div class="brand">Paper Reading</div><nav class="nav"><a href="../index.html">最新报告</a></nav></div></header>
  <main class="shell section">
    <h1>历史报告</h1>
    <ul>{items or "<li>暂无历史报告</li>"}</ul>
  </main>
</body>
</html>
"""
    (history_dir / "index.html").write_text(content, encoding="utf-8")


def write_report(
    config: dict[str, Any],
    run_date: str,
    papers: list[Paper],
    analysis: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Path]:
    report_cfg = config.get("report", {})
    output_dir = Path(report_cfg.get("output_dir") or "docs")
    history_dir = output_dir / (report_cfg.get("history_dir") or "reports")
    assets_dir = output_dir / "assets"
    output_dir.mkdir(parents=True, exist_ok=True)
    history_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "styles.css").write_text(CSS.strip() + "\n", encoding="utf-8")

    warnings = analysis.get("warnings") if isinstance(analysis.get("warnings"), list) else []
    warning_text = " ".join(str(item) for item in warnings)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    source_counter = _source_counts(papers)
    fetched_source_counter = _counter_from_mapping(stats.get("fetched_by_source"))
    keyword_counter = _keyword_counts(papers)
    paper_cards = "\n".join(
        _render_paper(paper, analysis, idx + 1, config) for idx, paper in enumerate(papers)
    )
    if not paper_cards:
        paper_cards = f'<div class="empty">{_esc(_empty_paper_message(stats))}</div>'

    title = report_cfg.get("title") or "Paper Reading"
    content = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_esc(title)} · {run_date}</title>
  <link rel="stylesheet" href="assets/styles.css">
</head>
<body>
  <header class="topbar">
    <div class="shell topbar-inner">
      <div class="brand">{_esc(title)}</div>
      <nav class="nav">
        <a href="index.html">最新报告</a>
        <a href="reports/index.html">历史报告</a>
      </nav>
    </div>
  </header>
  <main>
    <section class="hero">
      <div class="shell">
        <div class="eyebrow">{_esc(run_date)} · 中文论文简报</div>
        <h1>今日论文阅读报告</h1>
        <p class="summary">{_esc(analysis.get("daily_summary") or "暂无摘要。")}</p>
        <div class="metrics">
          <div class="metric"><strong>{stats.get("fetched", 0)}</strong><span>抓取论文</span></div>
          <div class="metric"><strong>{stats.get("ranked", 0)}</strong><span>过滤后候选</span></div>
          <div class="metric"><strong>{len(papers)}</strong><span>进入报告</span></div>
          <div class="metric"><strong>{len(source_counter)}</strong><span>来源数量</span></div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="shell viz-grid">
        <div>
          <h2>入选来源</h2>
          {_render_bars(source_counter)}
        </div>
        <div>
          <h2>关键词命中</h2>
          {_render_chips(keyword_counter)}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <h2>抓取来源</h2>
        {_render_bars(fetched_source_counter)}
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <h2>主题线索</h2>
        {_render_themes(analysis.get("themes") if isinstance(analysis.get("themes"), list) else []) or '<p class="empty">暂无主题聚类。</p>'}
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <h2>可做研究点</h2>
        {_render_research_ideas(analysis.get("research_ideas") if isinstance(analysis.get("research_ideas"), list) else [])}
      </div>
    </section>

    <section class="section">
      <div class="shell">
        <h2>论文列表</h2>
        <div class="paper-list">{paper_cards}</div>
      </div>
    </section>
  </main>
  <footer class="footer">
    <div class="shell">
      生成时间：{_esc(generated_at)}。{_esc(warning_text)}
    </div>
  </footer>
</body>
</html>
"""
    report_path = history_dir / f"{run_date}.html"
    latest_path = output_dir / "index.html"
    history_content = content.replace('href="assets/styles.css"', 'href="../assets/styles.css"')
    history_content = history_content.replace('href="index.html">最新报告', 'href="../index.html">最新报告')
    history_content = history_content.replace('href="reports/index.html">历史报告', 'href="index.html">历史报告')
    report_path.write_text(history_content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")
    _render_report_index(output_dir, history_dir)
    return {"latest": latest_path, "report": report_path}
