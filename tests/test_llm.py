import json
import os
import unittest
from unittest.mock import patch

from paper_reading.llm import LLMAuthError, _fallback_analysis, _post_chat_completion, analyze_papers
from paper_reading.models import Paper


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return b'{"choices":[{"message":{"content":"{}"}}]}'


class LlmFallbackTests(unittest.TestCase):
    def test_fallback_uses_title_and_abstract(self):
        paper = Paper(
            id="p1",
            source="science",
            journal="Science",
            title="A new climate model",
            abstract="We introduce a useful model for regional climate prediction. It improves forecasts.",
            keyword_matches=["climate"],
        )
        analysis = _fallback_analysis([paper], "test")
        note = analysis["papers"]["p1"]
        self.assertIn("A new climate model", note["summary"])
        self.assertIn("摘要要点", note["summary"])
        self.assertIn("regional climate prediction", note["details"])
        self.assertTrue(analysis["research_ideas"])

    def test_chat_completion_retries_after_timeout(self):
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(timeout)
            if len(calls) == 1:
                raise TimeoutError("timed out")
            return FakeResponse()

        with patch("paper_reading.llm.urlopen", fake_urlopen), patch("paper_reading.llm.time.sleep"):
            data = _post_chat_completion("https://example.com", "key", {}, 180, 2, 0)

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls, [180, 180])
        self.assertIn("choices", data)

    def test_analyze_papers_uses_one_call_per_paper_then_summary(self):
        papers = [
            Paper(
                id="p1",
                source="arxiv",
                title="Agentic climate model",
                abstract="An agent workflow improves climate model diagnostics.",
            ),
            Paper(
                id="p2",
                source="science",
                journal="Science",
                title="Remote sensing foundation model",
                abstract="A foundation model extracts signals from earth observation data.",
            ),
        ]
        calls = []

        def fake_post_chat_completion(endpoint, api_key, body, timeout, retry_attempts, retry_backoff):
            del endpoint, api_key, timeout, retry_attempts, retry_backoff
            payload = json.loads(body["messages"][1]["content"])
            calls.append(payload)
            if "paper" in payload:
                paper = payload["paper"]
                content = {
                    "summary": f"单篇总结：{paper['title']}",
                    "contribution": "围绕具体任务给出方法或证据。",
                    "details": f"详细解释：{paper['title']} 的方法、证据线索和需要核对的信息。",
                    "why_read": "与当前关键词和来源优先级相关。",
                    "limitations": "需要核对全文实验设置。",
                }
            else:
                content = {
                    "daily_summary": "今天的十篇候选围绕气候和 foundation model 展开。",
                    "themes": ["气候智能体", "遥感基础模型"],
                    "research_ideas": [
                        {
                            "idea": "复现一个遥感 foundation model 对照实验",
                            "why": "可以检验单篇笔记中的方法是否可迁移。",
                            "first_step": "整理公开数据集和非 foundation baseline。",
                            "risk": "元数据不足以判断数据是否开放。",
                        }
                    ],
                }
            return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}

        config = {
            "llm": {
                "enabled": True,
                "base_url": "https://example.com/v1",
                "model": "test-model",
                "timeout_seconds": 600,
                "retry_attempts": 1,
                "max_consecutive_failures": 2,
            }
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key"}), patch(
            "paper_reading.llm._post_chat_completion", fake_post_chat_completion
        ):
            analysis = analyze_papers(papers, config)

        self.assertEqual(len(calls), 3)
        self.assertIn("paper", calls[0])
        self.assertIn("paper", calls[1])
        self.assertIn("paper_analyses", calls[2])
        self.assertEqual(analysis["daily_summary"], "今天的十篇候选围绕气候和 foundation model 展开。")
        self.assertIn("单篇总结：Agentic climate model", analysis["papers"]["p1"]["summary"])
        self.assertIn("详细解释：Agentic climate model", analysis["papers"]["p1"]["details"])
        self.assertTrue(analysis["llm_used"])

    def test_analyze_papers_skips_remaining_after_consecutive_failures(self):
        papers = [
            Paper(id="p1", source="arxiv", title="Paper one", abstract="A"),
            Paper(id="p2", source="arxiv", title="Paper two", abstract="B"),
            Paper(id="p3", source="arxiv", title="Paper three", abstract="C"),
        ]
        calls = []

        def always_timeout(endpoint, api_key, body, timeout, retry_attempts, retry_backoff):
            del endpoint, api_key, body, timeout, retry_attempts, retry_backoff
            calls.append(1)
            raise TimeoutError("timed out")

        config = {
            "llm": {
                "enabled": True,
                "base_url": "https://example.com/v1",
                "model": "test-model",
                "timeout_seconds": 600,
                "retry_attempts": 1,
                "max_consecutive_failures": 2,
            }
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "key"}), patch(
            "paper_reading.llm._post_chat_completion", always_timeout
        ):
            analysis = analyze_papers(papers, config)

        self.assertEqual(len(calls), 2)
        self.assertFalse(analysis["llm_used"])
        self.assertIn("p3", analysis["papers"])
        self.assertTrue(any("Skipped LLM analysis" in item for item in analysis["warnings"]))

    def test_analyze_papers_stops_immediately_on_auth_error(self):
        papers = [
            Paper(id="p1", source="nature", title="Paper one", abstract="A"),
            Paper(id="p2", source="science", title="Paper two", abstract="B"),
            Paper(id="p3", source="arxiv", title="Paper three", abstract="C"),
        ]
        calls = []

        def unauthorized(endpoint, api_key, body, timeout, retry_attempts, retry_backoff):
            del endpoint, api_key, body, timeout, retry_attempts, retry_backoff
            calls.append(1)
            raise LLMAuthError("LLM authentication failed: HTTP 401 Unauthorized.")

        config = {
            "llm": {
                "enabled": True,
                "base_url": "https://example.com/v1",
                "model": "test-model",
                "timeout_seconds": 600,
                "retry_attempts": 1,
                "max_consecutive_failures": 2,
            }
        }
        with patch.dict(os.environ, {"OPENAI_API_KEY": "bad-key"}), patch(
            "paper_reading.llm._post_chat_completion", unauthorized
        ):
            analysis = analyze_papers(papers, config)

        self.assertEqual(len(calls), 1)
        self.assertFalse(analysis["llm_used"])
        self.assertIn("p3", analysis["papers"])
        self.assertTrue(any("authentication failed" in item for item in analysis["warnings"]))


if __name__ == "__main__":
    unittest.main()
