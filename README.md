# Paper Reading

一个每天自动收集最新论文、按关键词筛选，并生成中文 HTML 阅读报告的轻量系统。第一版支持：

- arXiv 最新论文
- Nature 主刊
- Science 主刊
- OpenAI-compatible LLM 总结
- GitHub Actions 每日更新
- GitHub Pages HTML 报告

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 先用内置样例生成页面，不需要网络和 API key
python -m paper_reading run --sample --no-llm --include-seen
```

生成结果在 `docs/index.html`，历史报告在 `docs/reports/`。

## 配置关键词

编辑 [config.yaml](config.yaml)，重点看这些字段：

```yaml
daily:
  max_papers: 20

filters:
  require_keywords: true
  keywords:
    - [large language model, agent, multimodal]
    - [earth, climate]
  exclude_keywords: []
```

关键词支持两种写法：

- 一维列表：所有词是 OR 关系，命中任意一个就保留。
- 二维列表：每个子列表内部是 OR 关系，子列表之间是 AND 关系。上面的例子表示论文必须同时命中“LLM/agent/multimodal 之一”和“earth/climate 之一”。

如果你想先看所有论文，把 `require_keywords` 改为 `false`，或者把 `keywords` 设为空列表。

## 配置 LLM

系统使用 OpenAI-compatible Chat Completions API。推荐在 GitHub Secrets 或本地环境变量中设置：

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4.1-mini"
```

也可以使用 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。如果没有 API key，系统会生成一个基于题录和摘要的保守版报告。

## 本地真实运行

```bash
python -m paper_reading run
```

真实运行会访问 arXiv API 和 Crossref API。Nature 与 Science 主刊通过 ISSN 从 Crossref 获取元数据，不抓全文。

## GitHub Pages

1. 把项目推到 GitHub。
2. 在仓库 `Settings -> Secrets and variables -> Actions` 添加：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`
3. 在 `Settings -> Pages` 里把 Source 设为 `GitHub Actions`。
4. 工作流 [.github/workflows/daily.yml](.github/workflows/daily.yml) 会每天运行，也可以手动触发。

## 目录结构

```text
paper_reading/
  config.py
  filters.py
  llm.py
  main.py
  models.py
  report.py
  sources/
    arxiv.py
    crossref.py
docs/
  index.html
data/
  seen_papers.json
  daily/
```

## 后续可扩展

- 增加更多期刊：在 `sources.journals.items` 中添加 ISSN。
- 增加邮件、飞书或 Slack 推送：在报告生成后加通知步骤。
- 增加更强可视化：可以基于 `data/daily/*.json` 做趋势图、主题变化、关键词热力图。
- 增加全文/PDF 摘要：后续可以为 open access 论文接入 PDF 下载和分段总结。
