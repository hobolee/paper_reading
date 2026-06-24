import unittest

from paper_reading.main import select_papers
from paper_reading.models import Paper


class SelectionTests(unittest.TestCase):
    def test_select_papers_respects_source_minimums(self):
        config = {
            "selection": {
                "source_minimums": {
                    "nature": 1,
                    "science": 1,
                }
            }
        }
        candidates = [
            Paper(id="arxiv-1", source="arxiv", title="A", score=50),
            Paper(id="arxiv-2", source="arxiv", title="B", score=49),
            Paper(id="nature-1", source="nature", title="C", score=10),
            Paper(id="science-1", source="science", title="D", score=9),
        ]
        selected = select_papers(candidates, 3, config)
        self.assertEqual({paper.source for paper in selected}, {"arxiv", "nature", "science"})


if __name__ == "__main__":
    unittest.main()
