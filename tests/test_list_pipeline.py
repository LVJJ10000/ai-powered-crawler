import unittest

from domain.models import ListDiscoveryResult, RunConfig, XPathCandidate
from models.schemas import CrawlConfig, PageType
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


class TestListPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_discover_detail_urls_returns_urls_without_extracting_records(self):
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
