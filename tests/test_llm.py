import unittest

from paper_reading.llm import _fallback_analysis
from paper_reading.models import Paper


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


if __name__ == "__main__":
    unittest.main()
