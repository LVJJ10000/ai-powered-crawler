import unittest

from domain.models import ListDiscoveryResult, RunConfig, XPathCandidate
from models.schemas import CrawlConfig, ExtractType, FieldXPath, PageData, PageType
from pipelines.list_pipeline import ListPipeline


class _FakePaginationService:
    async def follow(self, raw_html, start_url, pagination_xpath, pagination_type, max_list_pages):
        return [
            ("https://example.com/list", "<html>page one</html>"),
            ("https://example.com/list?page=2", "<html>page two</html>"),
        ]


class _FakeLinkXPathService:
    def evaluate_candidates(self, candidates, list_pages, max_pages):
        return type(
            "Result",
            (),
            {
                "selected_urls": [
                    "https://example.com/detail/1",
                    "https://example.com/detail/2",
                ],
                "selected_xpaths": ["//main//a/@href"],
                "evaluations": [],
            },
        )()


class _FakeFetcher:
    def __init__(self):
        self.fetch_calls = []
        self.fetch_many_calls = []

    async def fetch(self, url):
        self.fetch_calls.append(url)
        return "<html>template</html>"

    async def fetch_many(self, urls):
        self.fetch_many_calls.append(list(urls))
        return [(url, f"<html>{url}</html>") for url in urls]


class _FakeLegacyAnalyzerService:
    def __init__(self, detail_config):
        self.client = object()
        self.detail_config = detail_config

    def analyze(self, raw_html, label="page"):
        return type("Analysis", (), {"crawl_config": self.detail_config})()


class _FakeLegacyExtractionService:
    def __init__(self):
        self.extract_calls = []
        self.collect_calls = []

    def extract_pages(self, batch, crawl_plan, client=None, label="", session_key=None):
        self.extract_calls.append(
            {
                "batch": batch,
                "crawl_plan": crawl_plan,
                "client": client,
                "label": label,
                "session_key": session_key,
            }
        )
        return [PageData(url=url, data={"title": url.rsplit("/", 1)[-1]}) for url, _ in batch], crawl_plan

    def collect_sub_detail_urls(self, page_data, detail_config, page_html, page_url, max_pages):
        self.collect_calls.append(
            {
                "page_data": page_data,
                "detail_config": detail_config,
                "page_html": page_html,
                "page_url": page_url,
                "max_pages": max_pages,
            }
        )
        return []


class _FakeListingCrawler:
    def __init__(self):
        self.discover_calls = []
        self.run_calls = []

    async def discover_detail_urls(self, request, raw_html, analysis):
        self.discover_calls.append(
            {
                "request": request,
                "raw_html": raw_html,
                "analysis": analysis,
            }
        )
        return ListDiscoveryResult(
            detail_urls=["https://example.com/detail/1"],
            selected_xpaths=["//main//a/@href"],
        )

    async def run(self, request, raw_html, analysis):
        self.run_calls.append(
            {
                "request": request,
                "raw_html": raw_html,
                "analysis": analysis,
            }
        )
        return [], analysis.crawl_plan


class TestListPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_discover_detail_urls_delegates_to_listing_crawler(self):
        listing_crawler = _FakeListingCrawler()
        pipeline = ListPipeline(listing_crawler=listing_crawler)
        run_config = RunConfig(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=10,
            max_list_pages=2,
            use_playwright=False,
            depth=2,
        )
        list_config = CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None)
        link_candidates = [XPathCandidate(xpath="//main//a/@href", confidence=0.8)]

        result = await pipeline.discover_detail_urls(
            run_config=run_config,
            start_url=run_config.start_url,
            raw_html="<html>start</html>",
            list_config=list_config,
            link_candidates=link_candidates,
        )

        self.assertIsInstance(result, ListDiscoveryResult)
        self.assertEqual(["https://example.com/detail/1"], result.detail_urls)
        self.assertEqual(["//main//a/@href"], result.selected_xpaths)
        self.assertEqual(1, len(listing_crawler.discover_calls))
        self.assertIs(run_config, listing_crawler.discover_calls[0]["request"])
        self.assertEqual("<html>start</html>", listing_crawler.discover_calls[0]["raw_html"])
        self.assertEqual(list_config, listing_crawler.discover_calls[0]["analysis"].crawl_plan)
        self.assertEqual(link_candidates, listing_crawler.discover_calls[0]["analysis"].link_candidates)

    async def test_legacy_constructor_discover_detail_urls_returns_urls_without_extracting_records(self):
        pipeline = ListPipeline(
            fetcher=None,
            analyzer_service=None,
            extraction_service=None,
            pagination_service=_FakePaginationService(),
            link_xpath_service=_FakeLinkXPathService(),
        )
        run_config = RunConfig(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=10,
            max_list_pages=2,
            use_playwright=False,
            depth=2,
        )
        list_config = CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None)

        result = await pipeline.discover_detail_urls(
            run_config=run_config,
            start_url=run_config.start_url,
            raw_html="<html>start</html>",
            list_config=list_config,
            link_candidates=[XPathCandidate(xpath="//main//a/@href", confidence=0.8)],
        )

        self.assertIsInstance(result, ListDiscoveryResult)
        self.assertEqual(
            [
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            result.detail_urls,
        )
        self.assertEqual(["//main//a/@href"], result.selected_xpaths)

    async def test_run_delegates_to_listing_crawler(self):
        listing_crawler = _FakeListingCrawler()
        pipeline = ListPipeline(listing_crawler=listing_crawler)
        run_config = RunConfig(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=10,
            max_list_pages=2,
            use_playwright=False,
            depth=2,
        )
        list_config = CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None)
        link_candidates = [XPathCandidate(xpath="//main//a/@href", confidence=0.8)]

        records, export_plan = await pipeline.run(
            run_config=run_config,
            start_url=run_config.start_url,
            raw_html="<html>start</html>",
            list_config=list_config,
            link_candidates=link_candidates,
        )

        self.assertEqual([], records)
        self.assertIs(export_plan, list_config)
        self.assertEqual(1, len(listing_crawler.run_calls))

    async def test_legacy_constructor_run_preserves_runtime_compatibility(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="Title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        pipeline = ListPipeline(
            fetcher=_FakeFetcher(),
            analyzer_service=_FakeLegacyAnalyzerService(detail_config),
            extraction_service=_FakeLegacyExtractionService(),
            pagination_service=_FakePaginationService(),
            link_xpath_service=_FakeLinkXPathService(),
        )
        run_config = RunConfig(
            start_url="https://example.com/list",
            output_path="out.json",
            max_pages=2,
            max_list_pages=2,
            use_playwright=False,
            depth=2,
        )
        list_config = CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None)

        records, export_plan = await pipeline.run(
            run_config=run_config,
            start_url=run_config.start_url,
            raw_html="<html>start</html>",
            list_config=list_config,
            link_candidates=[XPathCandidate(xpath="//main//a/@href", confidence=0.8)],
        )

        self.assertEqual(
            [
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            [record.url for record in records],
        )
        self.assertIs(export_plan, detail_config)
