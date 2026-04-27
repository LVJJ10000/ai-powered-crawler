import unittest

from app.orchestrator import CrawlOrchestrator
from domain.crawl_entities import CrawlRequest


class _FakeCrawlWebsite:
    def __init__(self, result):
        self.result = result
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        return self.result


class TestOrchestratorRouting(unittest.IsolatedAsyncioTestCase):
    async def test_run_delegates_to_crawl_website(self):
        result = object()
        crawl_website = _FakeCrawlWebsite(result)
        request = CrawlRequest(
            start_url="https://example.com/list",
            output_path="tmp.json",
            max_pages=5,
            max_list_pages=2,
            use_playwright=False,
        )

        orchestrator = CrawlOrchestrator(crawl_website)

        actual = await orchestrator.run(request)

        self.assertIs(result, actual)
        self.assertEqual([request], crawl_website.requests)


if __name__ == "__main__":
    unittest.main()
