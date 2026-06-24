import unittest
from unittest.mock import patch

from paper_reading.llm import _fallback_analysis, _post_chat_completion
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


if __name__ == "__main__":
    unittest.main()
