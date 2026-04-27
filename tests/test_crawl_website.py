import unittest

from application.dto.start_page_analysis import StartPageAnalysis
from application.use_cases.crawl_website import CrawlWebsite
from domain.analysis_entities import PageType
from domain.crawl_entities import CrawlRequest, LinkCandidate
from domain.extraction_entities import CrawlPlan


class _FuturePageSource:
    async def fetch(self, url):
        return type("Snapshot", (), {"url": url, "html": "<html></html>"})()


class _LegacyPageSource:
    async def fetch(self, url):
        return "<html>legacy</html>"


class _FutureAnalyzer:
    def __init__(self, analysis):
        self.analysis = analysis

    async def analyze(self, snapshot):
        return self.analysis


class _LegacyAnalyzer:
    def __init__(self, analysis):
        self.analysis = analysis
        self.calls = []

    def analyze(self, raw_html, label="page"):
        self.calls.append((raw_html, label))
        return self.analysis


class _LegacyAnalyzerWithoutLabel:
    def __init__(self, analysis):
        self.analysis = analysis
        self.calls = []

    def analyze(self, raw_html):
        self.calls.append(raw_html)
        return self.analysis


class _LegacyAnalyzerThatRaisesTypeError:
    def __init__(self):
        self.calls = []

    def analyze(self, raw_html, label="page"):
        self.calls.append((raw_html, label))
        raise TypeError("analyzer broke")


class _FutureListingCrawler:
    def __init__(self):
        self.called = False
        self.calls = []
        self.result = type("Result", (), {"records": [], "export_plan": None, "detail_urls": ["future-list"]})()

    async def crawl(self, request, analysis):
        self.called = True
        self.calls.append((request, analysis))
        self.result.export_plan = analysis.crawl_plan
        return self.result


class _FutureDetailCrawler(_FutureListingCrawler):
    def __init__(self):
        super().__init__()
        self.result = type("Result", (), {"records": [], "export_plan": None, "detail_urls": ["future-detail"]})()


class _LegacyListRunner:
    def __init__(self):
        self.calls = []
        self.result = (["list-record"], None)

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class _LegacyDetailRunner:
    def __init__(self):
        self.calls = []
        self.result = (["detail-record"], None)

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class _FakeReporter:
    def __init__(self):
        self.events = []

    def publish(self, event):
        self.events.append(event)


class TestCrawlWebsite(unittest.IsolatedAsyncioTestCase):
    def test_start_page_analysis_rejects_mismatched_page_types(self):
        with self.assertRaisesRegex(ValueError, "page_type"):
            StartPageAnalysis(
                page_type=PageType.LIST,
                crawl_plan=CrawlPlan(page_type=PageType.DETAIL, fields=[]),
            )

    async def test_execute_routes_list_analysis_to_listing_crawler(self):
        analysis = StartPageAnalysis(
            page_type=PageType.LIST,
            crawl_plan=CrawlPlan(page_type=PageType.LIST, fields=[]),
            link_candidates=[LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
        )
        listing = _FutureListingCrawler()
        detail = _FutureDetailCrawler()
        reporter = _FakeReporter()
        use_case = CrawlWebsite(
            page_source=_FuturePageSource(),
            start_page_analyzer=_FutureAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )

        result = await use_case.execute(
            CrawlRequest(
                start_url="https://example.com/list",
                output_path="out.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertTrue(listing.called)
        self.assertFalse(detail.called)
        self.assertIs(result, listing.result)
        self.assertEqual(1, len(reporter.events))
        self.assertEqual(
            {"type": "start_page_analyzed", "page_type": "list"},
            reporter.events[0],
        )

    async def test_execute_routes_detail_analysis_to_detail_crawler(self):
        analysis = StartPageAnalysis(
            page_type=PageType.DETAIL,
            crawl_plan=CrawlPlan(page_type=PageType.DETAIL, fields=[]),
        )
        listing = _FutureListingCrawler()
        detail = _FutureDetailCrawler()
        reporter = _FakeReporter()
        use_case = CrawlWebsite(
            page_source=_FuturePageSource(),
            start_page_analyzer=_FutureAnalyzer(analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )

        result = await use_case.execute(
            CrawlRequest(
                start_url="https://example.com/detail/1",
                output_path="out.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertFalse(listing.called)
        self.assertTrue(detail.called)
        self.assertIs(result, detail.result)
        self.assertEqual(
            [{"type": "start_page_analyzed", "page_type": "detail"}],
            reporter.events,
        )

    async def test_execute_bridges_legacy_list_runtime_shapes(self):
        legacy_analysis = type(
            "LegacyAnalysis",
            (),
            {
                "crawl_config": CrawlPlan(page_type=PageType.LIST, fields=[]),
                "link_xpath_candidates": [LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
            },
        )()
        listing = _LegacyListRunner()
        detail = _LegacyDetailRunner()
        reporter = _FakeReporter()
        request = CrawlRequest(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=5,
            max_list_pages=2,
        )
        use_case = CrawlWebsite(
            page_source=_LegacyPageSource(),
            start_page_analyzer=_LegacyAnalyzer(legacy_analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )

        result = await use_case.execute(request)

        self.assertEqual(listing.result, result)
        self.assertEqual(1, len(listing.calls))
        self.assertEqual([], detail.calls)
        self.assertEqual("<html>legacy</html>", listing.calls[0]["raw_html"])
        self.assertEqual(request.start_url, listing.calls[0]["start_url"])
        self.assertIs(legacy_analysis.crawl_config, listing.calls[0]["list_config"])
        self.assertEqual(
            legacy_analysis.link_xpath_candidates,
            listing.calls[0]["link_candidates"],
        )
        self.assertEqual([("<html>legacy</html>", "start page")], use_case.start_page_analyzer.calls)
        self.assertEqual(
            [{"type": "start_page_analyzed", "page_type": "list"}],
            reporter.events,
        )

    async def test_execute_bridges_legacy_list_runtime_without_label_argument(self):
        legacy_analysis = type(
            "LegacyAnalysis",
            (),
            {
                "crawl_config": CrawlPlan(page_type=PageType.LIST, fields=[]),
                "link_xpath_candidates": [LinkCandidate(xpath="//main//a/@href", confidence=0.8)],
            },
        )()
        analyzer = _LegacyAnalyzerWithoutLabel(legacy_analysis)
        listing = _LegacyListRunner()
        use_case = CrawlWebsite(
            page_source=_LegacyPageSource(),
            start_page_analyzer=analyzer,
            listing_crawler=listing,
            detail_crawler=_LegacyDetailRunner(),
            reporter=_FakeReporter(),
        )

        result = await use_case.execute(
            CrawlRequest(
                start_url="https://example.com/list",
                output_path="out.json",
                max_pages=5,
                max_list_pages=2,
            )
        )

        self.assertEqual(listing.result, result)
        self.assertEqual(["<html>legacy</html>"], analyzer.calls)

    async def test_execute_bridges_legacy_detail_runtime_shapes(self):
        legacy_analysis = type(
            "LegacyAnalysis",
            (),
            {
                "crawl_config": CrawlPlan(page_type=PageType.DETAIL, fields=[]),
                "link_xpath_candidates": [],
            },
        )()
        listing = _LegacyListRunner()
        detail = _LegacyDetailRunner()
        reporter = _FakeReporter()
        request = CrawlRequest(
            start_url="https://example.com/detail/1",
            output_path="out.json",
            max_pages=5,
            max_list_pages=2,
        )
        use_case = CrawlWebsite(
            page_source=_LegacyPageSource(),
            start_page_analyzer=_LegacyAnalyzer(legacy_analysis),
            listing_crawler=listing,
            detail_crawler=detail,
            reporter=reporter,
        )

        result = await use_case.execute(request)

        self.assertEqual(detail.result, result)
        self.assertEqual(1, len(detail.calls))
        self.assertEqual([], listing.calls)
        self.assertEqual("<html>legacy</html>", detail.calls[0]["raw_html"])
        self.assertEqual(request.start_url, detail.calls[0]["start_url"])
        self.assertIs(legacy_analysis.crawl_config, detail.calls[0]["detail_config"])
        self.assertEqual(
            [{"type": "start_page_analyzed", "page_type": "detail"}],
            reporter.events,
        )

    async def test_execute_surfaces_real_analyzer_type_error_without_retrying(self):
        analyzer = _LegacyAnalyzerThatRaisesTypeError()
        use_case = CrawlWebsite(
            page_source=_LegacyPageSource(),
            start_page_analyzer=analyzer,
            listing_crawler=_LegacyListRunner(),
            detail_crawler=_LegacyDetailRunner(),
            reporter=_FakeReporter(),
        )

        with self.assertRaisesRegex(TypeError, "analyzer broke"):
            await use_case.execute(
                CrawlRequest(
                    start_url="https://example.com/list",
                    output_path="out.json",
                    max_pages=5,
                    max_list_pages=2,
                )
            )

        self.assertEqual([("<html>legacy</html>", "start page")], analyzer.calls)


if __name__ == "__main__":
    unittest.main()
