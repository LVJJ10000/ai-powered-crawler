import unittest

from application.dto.start_page_analysis import StartPageAnalysis
from application.use_cases.crawl_website import CrawlWebsite
from domain.analysis_entities import PageType
from domain.crawl_entities import CrawlRequest, LinkCandidate
from domain.extraction_entities import CrawlPlan


class _FakePageSource:
    async def fetch(self, url):
        return type("Snapshot", (), {"url": url, "html": "<html></html>"})()


class _FakeAnalyzer:
    def __init__(self, analysis):
        self.analysis = analysis

    async def analyze(self, snapshot):
        return self.analysis


class _FakeListingCrawler:
    def __init__(self):
        self.called = False

    async def crawl(self, request, analysis):
        self.called = True
        return type("Result", (), {"records": [], "export_plan": analysis.crawl_plan, "detail_urls": []})()


class _FakeDetailCrawler(_FakeListingCrawler):
    pass


class _FakeReporter:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class TestCrawlWebsite(unittest.IsolatedAsyncioTestCase):
    async def test_execute_routes_list_analysis_to_listing_crawler(self):
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
            link_candidates=[LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
        )
        listing = _FakeListingCrawler()
        detail = _FakeDetailCrawler()
        use_case = CrawlWebsite(
            page_source=_FakePageSource(),
            start_page_analyzer=_FakeAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=_FakeReporter(),
        )

        await use_case.execute(
            CrawlRequest(
                start_url="https://example.com/list",
                output_path="out.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertTrue(listing.called)
        self.assertFalse(detail.called)


if __name__ == "__main__":
    unittest.main()
