import unittest
from tempfile import TemporaryDirectory

from paper_reading.models import Paper
from paper_reading.report import _empty_paper_message
from paper_reading.report import write_report


class ReportMessageTests(unittest.TestCase):
    def test_empty_message_prioritizes_seen_filtered_candidates(self):
        message = _empty_paper_message(
            {
                "fetched": 300,
                "ranked": 7,
                "keyword_filtered": 293,
                "seen_filtered": 7,
            }
        )
        self.assertIn("通过筛选", message)
        self.assertIn("历史记录", message)

    def test_report_renders_feedback_actions_and_research_ideas(self):
        paper = Paper(
            id="doi:10.1/demo",
            source="science",
            journal="Science",
            title="Climate model agents improve regional forecasts",
            abstract="The study tests agent workflows for regional climate forecasting.",
            doi="10.1/demo",
            keyword_matches=["climate", "agent"],
            url="https://example.com/paper",
        )
        analysis = {
            "daily_summary": "今天有一篇值得读的论文。",
            "themes": ["climate agent"],
            "research_ideas": [
                {
                    "idea": "复现区域预测实验",
                    "why": "可以验证 agent workflow 是否真的提高短期预测。",
                    "first_step": "找到公开数据集并建立一个非 agent 基线。",
                    "risk": "摘要不足以判断原文数据是否开放。",
                }
            ],
            "papers": {
                paper.id: {
                    "summary": "论文围绕区域气候预测展开。",
                    "contribution": "可能贡献是把 agent workflow 用于预测流程。",
                    "details": "这篇论文的详细解释会说明 agent workflow 如何连接区域气候预测、数据约束和实验验证。",
                    "why_read": "与 climate 和 agent 关键词相关。",
                    "limitations": "需要核对全文实验设置。",
                }
            },
        }
        stats = {"fetched": 1, "ranked": 1, "fetched_by_source": {"science": 1}}
        with TemporaryDirectory() as tmpdir:
            config = {
                "report": {"output_dir": f"{tmpdir}/docs", "history_dir": "reports"},
                "feedback": {"github_repo": "hobolee/paper_reading"},
            }
            paths = write_report(config, "2026-06-24", [paper], analysis, stats)
            html = paths["latest"].read_text(encoding="utf-8")
        self.assertIn("可做研究点", html)
        self.assertIn("复现区域预测实验", html)
        self.assertIn("github.com/hobolee/paper_reading/issues/new", html)
        self.assertIn("稍后读", html)
        self.assertIn("详情", html)
        self.assertIn("这篇论文的详细解释", html)
        self.assertIn("摘要：", html)
        self.assertNotIn("为什么读", html)
        self.assertNotIn("注意点", html)


if __name__ == "__main__":
    unittest.main()
