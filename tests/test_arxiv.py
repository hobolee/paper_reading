import unittest
from unittest.mock import patch

from paper_reading.sources.arxiv import fetch_arxiv


def _feed(entry_id: str, title: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>https://arxiv.org/abs/{entry_id}</id>
    <title>{title}</title>
    <summary>A useful abstract about LLMs and earth observation.</summary>
    <published>2026-06-25T00:00:00Z</published>
    <updated>2026-06-25T00:00:00Z</updated>
    <author><name>Ada Chen</name></author>
    <category term="cs.AI" />
    <link href="https://arxiv.org/pdf/{entry_id}" title="pdf" type="application/pdf" />
  </entry>
</feed>
"""


class ArxivFetchTests(unittest.TestCase):
    def test_fetch_arxiv_keeps_previous_pages_when_later_page_fails(self):
        config = {
            "http": {"timeout_seconds": 30, "user_agent": "test"},
            "sources": {
                "arxiv": {
                    "enabled": True,
                    "categories": ["cs.AI"],
                    "fetch_limit": 2,
                    "fetch_page_size": 1,
                    "retry_attempts": 1,
                    "page_pause_seconds": 0,
                    "max_consecutive_failures": 2,
                }
            },
        }

        def fake_fetch_text(*args, **kwargs):
            if kwargs["params"]["start"] == 0:
                return _feed("2606.00001", "First paper")
            raise RuntimeError("HTTP 503 for https://export.arxiv.org/api/query: service unavailable")

        with patch("paper_reading.sources.arxiv.fetch_text", side_effect=fake_fetch_text):
            papers, warnings = fetch_arxiv(config)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].id, "arxiv:2606.00001")
        self.assertEqual(len(warnings), 1)
        self.assertIn("start=1", warnings[0])
        self.assertIn("HTTP 503", warnings[0])

    def test_fetch_arxiv_retries_transient_errors(self):
        config = {
            "http": {"timeout_seconds": 30, "user_agent": "test"},
            "sources": {
                "arxiv": {
                    "enabled": True,
                    "categories": ["cs.AI"],
                    "fetch_limit": 1,
                    "fetch_page_size": 1,
                    "retry_attempts": 2,
                    "retry_backoff_seconds": 0,
                    "page_pause_seconds": 0,
                }
            },
        }
        calls = []

        def fake_fetch_text(*args, **kwargs):
            del args, kwargs
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("HTTP 503 for https://export.arxiv.org/api/query: service unavailable")
            return _feed("2606.00002", "Recovered paper")

        with patch("paper_reading.sources.arxiv.fetch_text", side_effect=fake_fetch_text):
            papers, warnings = fetch_arxiv(config)

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(papers), 1)
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
