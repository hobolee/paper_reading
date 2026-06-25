import unittest

from paper_reading.feedback import Feedback, feedback_issue_url, feedback_score
from paper_reading.models import Paper


class FeedbackTests(unittest.TestCase):
    def test_feedback_score_uses_rating_and_keywords(self):
        feedback = Feedback(
            ratings={"doi:10.1/good": "star"},
            liked_keywords={"climate": 2},
            disliked_sources={"arxiv": 1},
        )
        config = {
            "feedback": {
                "rating_weights": {
                    "star": 22,
                    "like": 14,
                    "dislike": -28,
                }
            }
        }
        paper = Paper(
            id="doi:10.1/good",
            source="nature",
            title="Climate article",
            doi="10.1/good",
            keyword_matches=["climate"],
        )
        self.assertGreater(feedback_score(paper, feedback, config), 22)

    def test_feedback_issue_url_contains_structured_body(self):
        config = {"feedback": {"github_repo": "hobolee/paper_reading", "issue_label": "paper-feedback"}}
        paper = Paper(
            id="arxiv:1",
            source="arxiv",
            title="A useful paper",
            keyword_matches=["climate", "llm"],
        )
        url = feedback_issue_url(config, paper, "like")
        self.assertIn("github.com/hobolee/paper_reading/issues/new", url)
        self.assertIn("paper_id", url)
        self.assertIn("rating", url)


if __name__ == "__main__":
    unittest.main()
