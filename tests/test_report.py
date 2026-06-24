import unittest

from paper_reading.report import _empty_paper_message


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


if __name__ == "__main__":
    unittest.main()
