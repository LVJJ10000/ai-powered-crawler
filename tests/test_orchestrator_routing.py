import unittest

from app.orchestrator import CrawlOrchestrator
from application.dto.start_page_analysis import StartPageAnalysis
from application.use_cases.crawl_website import CrawlWebsite
from domain.analysis_entities import ExtractType, PageType
from domain.crawl_entities import CrawlRequest, LinkCandidate
from domain.errors import InvalidStartPageError
from domain.extraction_entities import CrawlPlan, FieldDefinition


class _FakePageSource:
    def __init__(self, html):
        self.html = html

    async def fetch(self, url):
        return self.html


class _FakeAnalyzer:
    def __init__(self, analysis):
        self.analysis = analysis

    def analyze(self, raw_html, label="page"):
        return self.analysis


class _FakeCrawler:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def crawl(self, request, analysis):
        self.calls.append((request, analysis))
        return self.result


class _FakeReporter:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class TestOrchestratorRouting(unittest.IsolatedAsyncioTestCase):
    async def test_routes_list_analysis_to_listing_crawler(self):
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
            link_candidates=[LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
        )
        listing = _FakeCrawler("list-result")
        detail = _FakeCrawler("detail-result")
        reporter = _FakeReporter()
        crawl_website = CrawlWebsite(
            page_source=_FakePageSource("<html></html>"),
            start_page_analyzer=_FakeAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )
        orchestrator = CrawlOrchestrator(crawl_website)

        result = await orchestrator.run(
            CrawlRequest(
                start_url="https://example.com/list",
                output_path="tmp.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertEqual("list-result", result)
        self.assertEqual(1, len(listing.calls))
        self.assertEqual([], detail.calls)
        self.assertEqual([{"type": "start_page_analyzed", "page_type": "list"}], reporter.events)

    async def test_routes_detail_analysis_to_detail_crawler(self):
        analysis = StartPageAnalysis(
            page_type=PageType.DETAIL,
            crawl_plan=CrawlPlan(
                page_type=PageType.DETAIL,
                fields=[
                    FieldDefinition(
                        name="title",
                        description="title",
                        xpath="//h1",
                        confidence=0.9,
                        extract=ExtractType.TEXT,
                    )
                ],
            ),
        )
        listing = _FakeCrawler("list-result")
        detail = _FakeCrawler("detail-result")
        reporter = _FakeReporter()
        crawl_website = CrawlWebsite(
            page_source=_FakePageSource("<html></html>"),
            start_page_analyzer=_FakeAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )
        orchestrator = CrawlOrchestrator(crawl_website)

        result = await orchestrator.run(
            CrawlRequest(
                start_url="https://example.com/detail/1",
                output_path="tmp.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertEqual("detail-result", result)
        self.assertEqual([], listing.calls)
        self.assertEqual(1, len(detail.calls))
        self.assertEqual([{"type": "start_page_analyzed", "page_type": "detail"}], reporter.events)

    async def test_rejects_list_start_page_without_link_candidates_before_routing(self):
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
        )
        listing = _FakeCrawler("list-result")
        detail = _FakeCrawler("detail-result")
        reporter = _FakeReporter()
        crawl_website = CrawlWebsite(
            page_source=_FakePageSource("<html></html>"),
            start_page_analyzer=_FakeAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )
        orchestrator = CrawlOrchestrator(crawl_website)

        with self.assertRaises(InvalidStartPageError) as context:
            await orchestrator.run(
                CrawlRequest(
                    start_url="https://example.com/list",
                    output_path="tmp.json",
                    max_pages=5,
                    max_list_pages=2,
                )
            )

        self.assertEqual("missing_link_candidates", context.exception.reason)
        self.assertEqual([], listing.calls)
        self.assertEqual([], detail.calls)
        self.assertEqual([], reporter.events)

    async def test_rejects_detail_start_page_without_fields_before_routing(self):
        analysis = StartPageAnalysis(
            page_type=PageType.DETAIL,
            crawl_plan=CrawlPlan(page_type=PageType.DETAIL, fields=[]),
        )
        listing = _FakeCrawler("list-result")
        detail = _FakeCrawler("detail-result")
        reporter = _FakeReporter()
        crawl_website = CrawlWebsite(
            page_source=_FakePageSource("<html></html>"),
            start_page_analyzer=_FakeAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )
        orchestrator = CrawlOrchestrator(crawl_website)

        with self.assertRaises(InvalidStartPageError) as context:
            await orchestrator.run(
                CrawlRequest(
                    start_url="https://example.com/detail/1",
                    output_path="tmp.json",
                    max_pages=5,
                    max_list_pages=2,
                )
            )

        self.assertEqual("missing_detail_fields", context.exception.reason)
        self.assertEqual([], listing.calls)
        self.assertEqual([], detail.calls)
        self.assertEqual([], reporter.events)


if __name__ == "__main__":
    unittest.main()
