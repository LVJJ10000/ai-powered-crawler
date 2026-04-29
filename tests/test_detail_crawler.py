import unittest

from application.use_cases.crawl_details import DetailCrawler
from domain.models import DetailLayerResult, RunConfig
from models.schemas import CrawlConfig, ExtractType, FieldXPath, PageData, PageType


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


class _FakeExtractionCoordinator:
    def extract_batch(self, batch, crawl_plan, client=None, label=""):
        records = [PageData(url=url, data={"title": url.rsplit("/", 1)[-1]}) for url, _ in batch]
        return records, crawl_plan

    def discover_child_urls(self, record, crawl_plan, page_html, page_url, remaining_pages):
        if page_url.endswith("/detail/1"):
            return ["https://example.com/detail/2"]
        return []


class _FakeAnalyzerService:
    def __init__(self, crawl_config):
        self.client = object()
        self._crawl_config = crawl_config

    def analyze(self, raw_html, label="page"):
        return type("Analysis", (), {"crawl_config": self._crawl_config})()


class _MultiRowExtractionCoordinator:
    def __init__(self):
        self.discovery_calls = []

    def extract_batch(self, batch, crawl_plan, client=None, label=""):
        records = []
        for url, _ in batch:
            if url.endswith("/detail/1"):
                records.append(PageData(url=url, data={"title": "first-a"}))
                records.append(PageData(url=url, data={"title": "first-b"}))
            else:
                records.append(PageData(url=url, data={"title": "second"}))
        return records, crawl_plan

    def discover_child_urls(self, record, crawl_plan, page_html, page_url, remaining_pages):
        self.discovery_calls.append((record.data["title"], page_url, page_html))
        return [f"{page_url}/child/{record.data['title']}"]


class TestDetailCrawler(unittest.IsolatedAsyncioTestCase):
    async def test_process_depth_layer_discovers_sub_details_by_record_url_not_batch_position(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        extraction_coordinator = _MultiRowExtractionCoordinator()
        crawler = DetailCrawler(
            fetcher=_FakeFetcher(),
            extraction_coordinator=extraction_coordinator,
            analyzer_service=_FakeAnalyzerService(detail_config),
        )

        result = await crawler.process_depth_layer(
            urls=[
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            remaining_pages=2,
            crawl_plan_cache={"example.com": detail_config},
            prefetched_pages={},
        )

        self.assertEqual(
            [
                ("first-a", "https://example.com/detail/1", "<html>https://example.com/detail/1</html>"),
                ("first-b", "https://example.com/detail/1", "<html>https://example.com/detail/1</html>"),
                ("second", "https://example.com/detail/2", "<html>https://example.com/detail/2</html>"),
            ],
            extraction_coordinator.discovery_calls,
        )
        self.assertEqual(
            [
                "https://example.com/detail/1/child/first-a",
                "https://example.com/detail/1/child/first-b",
                "https://example.com/detail/2/child/second",
            ],
            result.next_detail_urls,
        )

    async def test_process_depth_layer_reuses_template_fetch_for_uncached_domain(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        fetcher = _FakeFetcher()
        crawler = DetailCrawler(
            fetcher=fetcher,
            extraction_coordinator=_FakeExtractionCoordinator(),
            analyzer_service=_FakeAnalyzerService(detail_config),
        )

        await crawler.process_depth_layer(
            urls=[
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            remaining_pages=2,
            crawl_plan_cache={},
            prefetched_pages={},
        )

        self.assertEqual(["https://example.com/detail/1"], fetcher.fetch_calls)
        self.assertEqual([["https://example.com/detail/2"]], fetcher.fetch_many_calls)

    async def test_process_depth_layer_uses_prefetched_pages_and_discovers_next_urls(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        crawler = DetailCrawler(
            fetcher=_FakeFetcher(),
            extraction_coordinator=_FakeExtractionCoordinator(),
            analyzer_service=_FakeAnalyzerService(detail_config),
        )

        result = await crawler.process_depth_layer(
            urls=["https://example.com/detail/1"],
            remaining_pages=1,
            crawl_plan_cache={"example.com": detail_config},
            prefetched_pages={"https://example.com/detail/1": "<html>prefetched</html>"},
        )

        self.assertIsInstance(result, DetailLayerResult)
        self.assertEqual(1, len(result.records))
        self.assertEqual(["https://example.com/detail/2"], result.next_detail_urls)

    async def test_process_depth_layer_trims_urls_to_remaining_pages(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        fetcher = _FakeFetcher()
        crawler = DetailCrawler(
            fetcher=fetcher,
            extraction_coordinator=_FakeExtractionCoordinator(),
            analyzer_service=_FakeAnalyzerService(detail_config),
        )

        await crawler.process_depth_layer(
            urls=[
                "https://example.com/detail/1",
                "https://example.com/detail/2",
            ],
            remaining_pages=1,
            crawl_plan_cache={"example.com": detail_config},
            prefetched_pages={},
        )

        self.assertEqual([["https://example.com/detail/1"]], fetcher.fetch_many_calls)

    async def test_run_extracts_start_page_and_follow_up_pages(self):
        detail_config = CrawlConfig(
            page_type=PageType.DETAIL,
            fields=[
                FieldXPath(
                    name="title",
                    description="title",
                    xpath="//h1",
                    confidence=0.9,
                    extract=ExtractType.TEXT,
                )
            ],
            pagination_xpath=None,
        )
        fetcher = _FakeFetcher()
        crawler = DetailCrawler(
            fetcher=fetcher,
            extraction_coordinator=_FakeExtractionCoordinator(),
            analyzer_service=_FakeAnalyzerService(detail_config),
        )

        records, export_config = await crawler.run(
            run_config=RunConfig(start_url="https://example.com/detail/1", max_pages=2),
            start_url="https://example.com/detail/1",
            raw_html="<html>start</html>",
            detail_config=detail_config,
        )

        self.assertEqual(["https://example.com/detail/2"], [record.url for record in records[1:]])
        self.assertIs(export_config, detail_config)
        self.assertEqual([["https://example.com/detail/2"]], fetcher.fetch_many_calls)
