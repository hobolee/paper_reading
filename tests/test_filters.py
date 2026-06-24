import unittest

from paper_reading.filters import rank_and_filter
from paper_reading.models import Paper


class FilterTests(unittest.TestCase):
    def test_rank_and_filter_requires_keywords(self):
        config = {
            "filters": {
                "require_keywords": True,
                "keywords": ["machine learning"],
                "exclude_keywords": [],
            },
            "ranking": {"source_priority": {"nature": 20, "arxiv": 10}},
        }
        papers = [
            Paper(
                id="1",
                source="nature",
                title="Machine learning for biology",
                abstract="",
                journal="Nature",
            ),
            Paper(
                id="2",
                source="arxiv",
                title="Unrelated title",
                abstract="",
                journal="arXiv",
            ),
        ]
        ranked, stats = rank_and_filter(papers, config)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].id, "1")
        self.assertEqual(stats["keyword_filtered"], 1)

    def test_rank_and_filter_dedupes_doi(self):
        config = {
            "filters": {"require_keywords": False, "keywords": [], "exclude_keywords": []},
            "ranking": {"source_priority": {}},
        }
        papers = [
            Paper(id="doi:10.1/test", source="science", title="A", doi="10.1/test"),
            Paper(id="other", source="science", title="A copy", doi="10.1/test"),
        ]
        ranked, _ = rank_and_filter(papers, config)
        self.assertEqual(len(ranked), 1)

    def test_rank_and_filter_keyword_groups_are_and_between_groups(self):
        config = {
            "filters": {
                "require_keywords": True,
                "keywords": [["agent", "multimodal"], ["earth", "climate"]],
                "exclude_keywords": [],
            },
            "ranking": {"source_priority": {}},
        }
        papers = [
            Paper(
                id="match",
                source="arxiv",
                title="Multimodal agent for climate modeling",
                abstract="",
            ),
            Paper(
                id="missing-second-group",
                source="arxiv",
                title="Multimodal agent benchmark",
                abstract="",
            ),
            Paper(
                id="missing-first-group",
                source="arxiv",
                title="Climate modeling benchmark",
                abstract="",
            ),
        ]
        ranked, stats = rank_and_filter(papers, config)
        self.assertEqual([paper.id for paper in ranked], ["match"])
        self.assertEqual(ranked[0].keyword_matches, ["agent", "multimodal", "climate"])
        self.assertEqual(stats["keyword_filtered"], 2)


if __name__ == "__main__":
    unittest.main()
