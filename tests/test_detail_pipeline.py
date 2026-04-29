import unittest

from domain.models import DetailLayerResult, RunConfig
from models.schemas import CrawlConfig, PageData, PageType
from pipelines.detail_pipeline import DetailPipeline


class _FakeDetailCrawler:
    def __init__(self):
        self.run_calls = []
        self.process_calls = []

    async def run(self, run_config, start_url, raw_html, detail_config):
        self.run_calls.append(
            {
                "run_config": run_config,
                "start_url": start_url,
                "raw_html": raw_html,
                "detail_config": detail_config,
            }
        )
        return [PageData(url=start_url, data={"title": "start"})], detail_config

    async def process_depth_layer(self, urls, remaining_pages, crawl_plan_cache=None, prefetched_pages=None):
        self.process_calls.append(
            {
                "urls": urls,
                "remaining_pages": remaining_pages,
                "crawl_plan_cache": crawl_plan_cache,
                "prefetched_pages": prefetched_pages,
            }
        )
        return DetailLayerResult(records=[PageData(url=urls[0], data={"title": "start"})])


class _FakeFetcher:
    def __init__(self):
        self.fetch_many_calls = []

    async def fetch_many(self, urls):
        self.fetch_many_calls.append(list(urls))
        return [(url, f"<html>{url}</html>") for url in urls]


class _FakeLegacyExtractionService:
    def __init__(self):
        self.extract_calls = []
        self.collect_calls = []

    def extract_pages(self, batch, crawl_plan, client=None, label=""):
        self.extract_calls.append(
            {
                "batch": batch,
                "crawl_plan": crawl_plan,
                "client": client,
                "label": label,
            }
        )
        records = [PageData(url=url, data={"title": url.rsplit("/", 1)[-1]}) for url, _html in batch]
        return records, crawl_plan

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
        if page_url.endswith("/1"):
            return ["https://example.com/detail/2"]
        return []


class _FakeAnalyzerService:
    def __init__(self):
        self.client = object()


class TestDetailPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_run_delegates_to_detail_crawler(self):
        detail_crawler = _FakeDetailCrawler()
        detail_config = CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None)
        pipeline = DetailPipeline(detail_crawler=detail_crawler)

        records, export_config = await pipeline.run(
            run_config=RunConfig(start_url="https://example.com/detail/1", max_pages=2),
            start_url="https://example.com/detail/1",
            raw_html="<html>start</html>",
            detail_config=detail_config,
        )
        self.assertEqual(1, len(records))
        self.assertIs(export_config, detail_config)
        self.assertEqual(
            [
                {
                    "run_config": RunConfig(start_url="https://example.com/detail/1", max_pages=2),
                    "start_url": "https://example.com/detail/1",
                    "raw_html": "<html>start</html>",
                    "detail_config": detail_config,
                }
            ],
            detail_crawler.run_calls,
        )

    async def test_process_depth_layer_delegates_to_detail_crawler(self):
        detail_crawler = _FakeDetailCrawler()
        detail_config = CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None)
        pipeline = DetailPipeline(detail_crawler=detail_crawler)

        result = await pipeline.process_depth_layer(
            urls=["https://example.com/detail/1"],
            remaining_pages=1,
            config_cache={"example.com": detail_config},
            prefetched_pages={"https://example.com/detail/1": "<html>prefetched</html>"},
        )

        self.assertIsInstance(result, DetailLayerResult)
        self.assertEqual(
            [
                {
                    "urls": ["https://example.com/detail/1"],
                    "remaining_pages": 1,
                    "crawl_plan_cache": {"example.com": detail_config},
                    "prefetched_pages": {"https://example.com/detail/1": "<html>prefetched</html>"},
                }
            ],
            detail_crawler.process_calls,
        )

    async def test_legacy_constructor_path_preserves_runtime_compatibility(self):
        fetcher = _FakeFetcher()
        extraction_service = _FakeLegacyExtractionService()
        analyzer_service = _FakeAnalyzerService()
        detail_config = CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None)
        pipeline = DetailPipeline(
            fetcher=fetcher,
            extraction_service=extraction_service,
            analyzer_service=analyzer_service,
        )

        records, export_config = await pipeline.run(
            run_config=RunConfig(start_url="https://example.com/detail/1", max_pages=2),
            start_url="https://example.com/detail/1",
            raw_html="<html>start</html>",
            detail_config=detail_config,
        )

        self.assertEqual(
            ["https://example.com/detail/1", "https://example.com/detail/2"],
            [record.url for record in records],
        )
        self.assertIs(export_config, detail_config)
        self.assertEqual([["https://example.com/detail/2"]], fetcher.fetch_many_calls)
        self.assertEqual(2, len(extraction_service.extract_calls))
        self.assertEqual(1, len(extraction_service.collect_calls))

    async def test_legacy_constructor_process_depth_layer_preserves_runtime_compatibility(self):
        fetcher = _FakeFetcher()
        extraction_service = _FakeLegacyExtractionService()
        analyzer_service = _FakeAnalyzerService()
        detail_config = CrawlConfig(page_type=PageType.DETAIL, fields=[], pagination_xpath=None)
        pipeline = DetailPipeline(
            fetcher=fetcher,
            extraction_service=extraction_service,
            analyzer_service=analyzer_service,
        )

        result = await pipeline.process_depth_layer(
            urls=["https://example.com/detail/1"],
            remaining_pages=1,
            config_cache={"example.com": detail_config},
            prefetched_pages={"https://example.com/detail/1": "<html>prefetched</html>"},
        )

        self.assertIsInstance(result, DetailLayerResult)
        self.assertEqual(["https://example.com/detail/1"], [record.url for record in result.records])
        self.assertEqual(["https://example.com/detail/2"], result.next_detail_urls)
        self.assertEqual([], fetcher.fetch_many_calls)
        self.assertEqual(1, len(extraction_service.extract_calls))
        self.assertEqual(1, len(extraction_service.collect_calls))
