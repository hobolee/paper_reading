# Paper Reading

一个每天自动收集最新论文、按关键词筛选，并生成中文 HTML 阅读报告的轻量系统。第一版支持：

- arXiv 最新论文
- Nature 主刊
- Science 主刊
- OpenAI-compatible LLM 总结
- GitHub Actions 每日更新
- GitHub Pages HTML 报告
- Gmail 邮件报告
- GitHub Issue 反馈排序
- 每日可做研究点生成

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
  max_papers: 10

filters:
  require_keywords: true
  keyword_optional_sources:
    - nature
    - science
  keywords:
    - [large language model, agent, multimodal]
    - [earth, climate]
  exclude_keywords: []

selection:
  source_minimums:
    nature: 3
    science: 3
    arxiv: 2
```

关键词支持两种写法：

- 一维列表：所有词是 OR 关系，命中任意一个就保留。
- 二维列表：每个子列表内部是 OR 关系，子列表之间是 AND 关系。上面的例子表示论文必须同时命中“LLM/agent/multimodal 之一”和“earth/climate 之一”。

如果你想先看所有论文，把 `require_keywords` 改为 `false`，或者把 `keywords` 设为空列表。

`keyword_optional_sources` 会让指定来源即使没有命中关键词也能进入候选池；`source_minimums` 会尽量为指定来源保留名额。默认配置会优先保证 Nature 和 Science 主刊有一定占比，同时每天尽量保留 arXiv 候选。当前关键词第二组也覆盖 AI for Science、科学推理、符号推理、形式化推理、符号回归和 test-time/inference-time scaling 等方向。

## 个人反馈

每篇论文标题旁边有 `⭐`、`👍`、`👎` 三个反馈按钮。按钮会打开一个预填好的 GitHub Issue；提交后，下一次 GitHub Actions 会读取这些 issue，并把反馈用于排序：

- `⭐` 和 `👍` 会提高相似关键词、相同来源、同一论文的权重。
- `👎` 会降低相似关键词和相同来源的权重。

每篇论文还有一个 `详情` 展开区，展示 LLM 的单篇分析和原始摘要；外层只保留“一句话”和“贡献”，方便快速扫描。

默认使用仓库 issue，不需要额外服务。配置在 `feedback` 段：

```yaml
feedback:
  enabled: true
  github_repo: hobolee/paper_reading
  issue_label: paper-feedback
```

也可以手动维护 `data/feedback.json`，适合快速给关键词或来源加权。

## 可做研究点

报告会在主题线索后生成“可做研究点”，每个点包含：

- idea：可以尝试的研究问题
- why：为什么值得做
- first_step：最小下一步实验或阅读动作
- risk：主要不确定性

如果 LLM 调用失败，系统也会基于题名、摘要和关键词生成保守版 research ideas，不再只输出模板空话。

## 配置 LLM

系统使用 OpenAI-compatible Chat Completions API。推荐在 GitHub Secrets 或本地环境变量中设置：

```bash
export OPENAI_API_KEY="..."
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_MODEL="gpt-4.1-mini"
```

也可以使用 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。如果没有 API key，系统会生成一个基于题录和摘要的保守版报告。

LLM 分析默认按论文逐篇调用：每篇论文先生成独立阅读笔记，最后再用这些短笔记做每日总览、主题线索和可做研究点。这样不会把所有论文和摘要一次性塞给模型，单篇失败也不会拖垮整份报告。

如果报告底部出现 `LLM call failed: timed out`，通常表示模型或代理在超时时间内没有返回完整结果。可以调大这些参数：

```yaml
llm:
  timeout_seconds: 600
  retry_attempts: 1
  retry_backoff_seconds: 8
  max_consecutive_failures: 2
  max_input_chars_per_paper: 1200
```

如果报告底部出现 `HTTP 401 Unauthorized` 或 `HTTP 403 Forbidden`，这是 LLM 服务拒绝了当前凭据。重点检查 GitHub Secrets 里的 `OPENAI_API_KEY`、`OPENAI_BASE_URL` 和 `OPENAI_MODEL` 是否匹配同一个服务商。

## 本地真实运行

```bash
python -m paper_reading run
```

真实运行会访问 arXiv API 和 Crossref API。Nature 与 Science 主刊通过 ISSN 从 Crossref 获取元数据，不抓全文。

Nature 与 Science 默认只保留研究 Article。系统会过滤 News、Comment、Editorial、Correction、Research Highlight 等内容；Nature 主要保留 `10.1038/s41586-...` DOI，Science 会要求 `10.1126/science...` DOI、摘要和最低引用条目数。需要调整时看 `sources.journals` 下的 `article_only`、`include_doi_patterns`、`exclude_title_patterns`、`require_abstract` 和 `min_references`。

Crossref 查询会按 `fetch_page_size` 小批量分页抓取，扫描到 `fetch_limit_per_journal` 为止。这样单页失败不会拖垮整个 Nature/Science 源，页面底部会显示简短 warning。

arXiv 查询也会按 `fetch_page_size` 分页抓取，默认每页 50 条；遇到 `503`、`504` 或网络抖动会重试。连续多页失败时会停止 arXiv 源，但 Nature/Science 和报告生成仍会继续。

## GitHub Pages

1. 把项目推到 GitHub。
2. 在仓库 `Settings -> Secrets and variables -> Actions` 添加：
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `OPENAI_MODEL`
   - `GMAIL_USERNAME`
   - `GMAIL_APP_PASSWORD`
   - `MAIL_TO`
3. 在 `Settings -> Pages` 里把 Source 设为 `GitHub Actions`。
4. 工作流 [.github/workflows/daily.yml](.github/workflows/daily.yml) 会每天运行，也可以手动触发。

## Gmail 邮件

GitHub Actions 会在 GitHub Pages 部署后尝试发送邮件。如果没有配置 Gmail Secrets，会自动跳过，不影响报告生成。

需要添加这些 Secrets：

```text
GMAIL_USERNAME=你的 Gmail 地址
GMAIL_APP_PASSWORD=Gmail App Password
MAIL_TO=收件邮箱，多个邮箱用逗号分隔
MAIL_FROM=可选，默认使用 GMAIL_USERNAME
```

Gmail SMTP 使用 `smtp.gmail.com:587` 和 TLS。`GMAIL_APP_PASSWORD` 不是 Gmail 登录密码；通常需要先开启两步验证，再在 Google Account 中创建 App Password。

本地测试邮件：

```bash
export GMAIL_USERNAME="yourname@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export MAIL_TO="yourname@gmail.com"
python -m paper_reading send-email --report docs/index.html
```

## 目录结构

```text
paper_reading/
  config.py
  filters.py
  emailer.py
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
