import unittest

from paper_reading.sources.crossref import _passes_article_filter


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


if __name__ == "__main__":
    unittest.main()
