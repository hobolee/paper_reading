import unittest
from unittest.mock import patch

from paper_reading.sources.crossref import _passes_article_filter, fetch_journals


class CrossrefArticleFilterTests(unittest.TestCase):
    def test_nature_research_article_doi_passes(self):
        item = {
            "DOI": "10.1038/s41586-026-10799-8",
            "title": ["A research article"],
            "resource": {"primary": {"URL": "https://www.nature.com/articles/s41586-026-10799-8"}},
        }
        config = {
            "article_only": True,
            "include_doi_patterns": [r"^10\.1038/s41586-"],
            "exclude_title_patterns": [r"^News"],
        }
        self.assertTrue(_passes_article_filter(item, config))

    def test_nature_news_doi_is_filtered(self):
        item = {
            "DOI": "10.1038/d41586-026-01958-y",
            "title": ["Why science needs the humanities more than ever"],
            "resource": {"primary": {"URL": "https://www.nature.com/articles/d41586-026-01958-y"}},
        }
        config = {
            "article_only": True,
            "include_doi_patterns": [r"^10\.1038/s41586-"],
        }
        self.assertFalse(_passes_article_filter(item, config))

    def test_nature_retraction_note_is_filtered_even_with_article_doi(self):
        item = {
            "DOI": "10.1038/s41586-026-10799-8",
            "title": ["Retraction Note: Sub-second periodicity in a fast radio burst"],
            "resource": {"primary": {"URL": "https://www.nature.com/articles/s41586-026-10799-8"}},
        }
        config = {
            "article_only": True,
            "include_doi_patterns": [r"^10\.1038/s41586-"],
            "exclude_title_patterns": [r"^Retraction Note:"],
        }
        self.assertFalse(_passes_article_filter(item, config))

    def test_science_requires_abstract_and_min_references(self):
        config = {
            "article_only": True,
            "include_doi_patterns": [r"^10\.1126/science\.[a-z0-9]+$"],
            "require_abstract": True,
            "min_references": 5,
        }
        article = {
            "DOI": "10.1126/science.aea0869",
            "title": ["Scalable fabrication of COF membranes"],
            "abstract": "<jats:p>Research abstract.</jats:p>",
            "reference-count": 42,
        }
        short_item = {
            "DOI": "10.1126/science.ady1234",
            "title": ["An editorial item"],
            "reference-count": 1,
        }
        self.assertTrue(_passes_article_filter(article, config))
        self.assertFalse(_passes_article_filter(short_item, config))

    def test_fetch_journals_keeps_going_when_a_page_fails(self):
        config = {
            "daily": {"lookback_days": 30},
            "http": {"timeout_seconds": 30, "user_agent": "test"},
            "sources": {
                "journals": {
                    "enabled": True,
                    "fetch_limit_per_journal": 2,
                    "fetch_page_size": 1,
                    "article_only": False,
                    "items": [
                        {
                            "id": "nature",
                            "name": "Nature",
                            "issns": ["1476-4687"],
                        }
                    ],
                }
            },
        }
        first_page = {
            "message": {
                "items": [
                    {
                        "DOI": "10.1038/s41586-test",
                        "title": ["Research title"],
                        "URL": "https://doi.org/10.1038/s41586-test",
                        "container-title": ["Nature"],
                    }
                ]
            }
        }

        def fake_fetch_json(*args, **kwargs):
            if kwargs["params"]["offset"] == 0:
                return first_page
            raise RuntimeError("Crossref exploded with a very long internal error")

        with patch("paper_reading.sources.crossref.fetch_json", side_effect=fake_fetch_json):
            papers, warnings = fetch_journals(config)

        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].source, "nature")
        self.assertEqual(len(warnings), 1)
        self.assertIn("offset 1", warnings[0])


if __name__ == "__main__":
    unittest.main()
