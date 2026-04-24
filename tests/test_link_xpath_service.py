import unittest

from domain.models import XPathCandidate
from services.link_xpath_service import LinkXPathService
from services.pattern_learning_service import PatternLearningService


class TestLinkXPathService(unittest.TestCase):
    def test_extract_links_supports_href_xpath(self):
        service = LinkXPathService(pattern_learner=PatternLearningService())
        html = """
        <html><body>
            <a href="/article/100">first article title</a>
            <a href="/article/101">second article title</a>
        </body></html>
        """
        urls = service.extract_links(html, "https://news.example.com/list", "//a/@href")
        self.assertEqual(2, len(urls))
        self.assertIn("https://news.example.com/article/100", urls)

    def test_evaluate_candidates_selects_best_xpath(self):
        service = LinkXPathService(pattern_learner=PatternLearningService())
        html = """
        <html><body>
            <nav>
              <a href="/about">about</a>
              <a href="/contact">contact</a>
            </nav>
            <main>
              <a href="/article/100">title one is meaningful</a>
              <a href="/article/101">title two is meaningful</a>
              <a href="/article/102">title three is meaningful</a>
            </main>
        </body></html>
        """
        candidates = [
            XPathCandidate(xpath="//nav//a/@href", confidence=0.7),
            XPathCandidate(xpath="//main//a/@href", confidence=0.8),
        ]

        result = service.evaluate_candidates(
            candidates=candidates,
            list_pages=[("https://news.example.com/world/", html)],
            max_pages=10,
        )

        self.assertTrue(result.selected_urls)
        self.assertIn("//main//a/@href", result.selected_xpaths)
        self.assertNotIn("https://news.example.com/about", result.selected_urls)


if __name__ == "__main__":
    unittest.main()

