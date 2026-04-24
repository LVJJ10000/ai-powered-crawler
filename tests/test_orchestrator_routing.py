import unittest
from unittest.mock import patch

from app.orchestrator import CrawlOrchestrator
from domain.models import RunConfig, XPathCandidate
from models.schemas import CrawlConfig, FieldXPath, PageType, ExtractType


class _FakeFetcher:
    def __init__(self, html: str):
        self._html = html

    async def fetch(self, url: str) -> str:
        return self._html


class _FakeAnalysisResult:
    def __init__(self, crawl_config: CrawlConfig, link_candidates=None):
        self.crawl_config = crawl_config
        self.link_xpath_candidates = link_candidates or []


class _FakeAnalyzerService:
    def __init__(self, start_result, detail_result=None):
        self._start_result = start_result
        self._detail_result = detail_result or start_result
        self.calls = 0
        self.client = object()

    def analyze(self, raw_html: str, label: str = "page"):
        self.calls += 1
        if self.calls == 1:
            return self._start_result
        return self._detail_result


class _FakeListPipeline:
    def __init__(self):
        self.called = False

    async def run(self, **kwargs):
        self.called = True
        return [], kwargs["list_config"]


class _FakeDetailPipeline:
    def __init__(self):
        self.called = False

    async def run(self, **kwargs):
        self.called = True
        return [], kwargs["detail_config"]


class TestOrchestratorRouting(unittest.IsolatedAsyncioTestCase):
    async def test_routes_to_list_pipeline(self):
        list_config = CrawlConfig(page_type=PageType.LIST, fields=[], pagination_xpath=None)
        start_result = _FakeAnalysisResult(
            crawl_config=list_config,
            link_candidates=[XPathCandidate(xpath="//main//a/@href", confidence=0.8)],
        )
        analyzer = _FakeAnalyzerService(start_result)
        list_pipeline = _FakeListPipeline()
        detail_pipeline = _FakeDetailPipeline()
        fetcher = _FakeFetcher("<html></html>")

        orchestrator = CrawlOrchestrator(fetcher, analyzer, list_pipeline, detail_pipeline)
        run_config = RunConfig(
            start_url="https://example.com/list",
            output_path="tmp.json",
            max_pages=5,
            max_list_pages=2,
            use_playwright=False,
        )

        with patch("app.orchestrator.export_json") as export_mock:
            await orchestrator.run(run_config)
            export_mock.assert_called_once()

        self.assertTrue(list_pipeline.called)
        self.assertFalse(detail_pipeline.called)

    async def test_routes_to_detail_pipeline(self):
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
        start_result = _FakeAnalysisResult(crawl_config=detail_config, link_candidates=[])
        analyzer = _FakeAnalyzerService(start_result)
        list_pipeline = _FakeListPipeline()
        detail_pipeline = _FakeDetailPipeline()
        fetcher = _FakeFetcher("<html></html>")

        orchestrator = CrawlOrchestrator(fetcher, analyzer, list_pipeline, detail_pipeline)
        run_config = RunConfig(
            start_url="https://example.com/detail/1",
            output_path="tmp.json",
            max_pages=5,
            max_list_pages=2,
            use_playwright=False,
        )

        with patch("app.orchestrator.export_json") as export_mock:
            await orchestrator.run(run_config)
            export_mock.assert_called_once()

        self.assertFalse(list_pipeline.called)
        self.assertTrue(detail_pipeline.called)


if __name__ == "__main__":
    unittest.main()

