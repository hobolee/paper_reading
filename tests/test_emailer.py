import unittest

from paper_reading.emailer import _absolutize_links, _recipients


class EmailerTests(unittest.TestCase):
    def test_recipients_accept_comma_and_semicolon(self):
        self.assertEqual(
            _recipients("a@example.com, b@example.com;c@example.com"),
            ["a@example.com", "b@example.com", "c@example.com"],
        )

    def test_absolutize_links_keeps_external_links(self):
        html = '<a href="reports/index.html">Reports</a><a href="https://example.com">External</a>'
        updated = _absolutize_links(html, "https://hobolee.github.io/paper_reading/")
        self.assertIn('href="https://hobolee.github.io/paper_reading/reports/index.html"', updated)
        self.assertIn('href="https://example.com"', updated)


if __name__ == "__main__":
    unittest.main()
