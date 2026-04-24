import unittest

from domain.pagination_models import PaginationConfig, PaginationMode, StopReason
from services.pagination_engine import PaginationEngine
from services.progress_detector import ProgressDetector


class _FakeFetcher:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages

    async def fetch(self, url: str) -> str:
        if url not in self.pages:
            raise RuntimeError(f"missing url: {url}")
        return self.pages[url]


class TestPaginationEngine(unittest.IsolatedAsyncioTestCase):
    async def test_link_strategy_advances_pages(self):
        url1 = "https://example.com/list?page=1"
        url2 = "https://example.com/list?page=2"
        html1 = "<html><body><a class='next' href='?page=2'>下一页</a><a href='/a1'>a</a></body></html>"
        html2 = "<html><body><a href='/a2'>b</a></body></html>"
        fetcher = _FakeFetcher({url2: html2})
        engine = PaginationEngine(fetcher=fetcher, progress_detector=ProgressDetector())

        result = await engine.run(
            start_html=html1,
            start_url=url1,
            pagination_xpath="//a[contains(@class,'next')]/@href",
            pagination_type=None,
            config=PaginationConfig(max_rounds=2, max_no_progress_rounds=2, max_target_pages=3),
        )

        self.assertEqual(2, len(result.pages))
        self.assertEqual(url2, result.pages[1][0])

    async def test_stops_when_no_strategy_advances(self):
        url1 = "https://example.com/list?page=1"
        html1 = "<html><body><a href='/a1'>a</a></body></html>"
        fetcher = _FakeFetcher({})
        engine = PaginationEngine(fetcher=fetcher, progress_detector=ProgressDetector())

        result = await engine.run(
            start_html=html1,
            start_url=url1,
            pagination_xpath="//a[contains(@class,'next')]/@href",
            pagination_type=None,
            config=PaginationConfig(
                max_rounds=3,
                max_no_progress_rounds=1,
                max_target_pages=3,
                strategy_order=[PaginationMode.LINK, PaginationMode.CLICK],
            ),
        )

        self.assertEqual(1, len(result.pages))
        self.assertEqual(StopReason.NO_PROGRESS_LIMIT, result.stop_reason)
        self.assertTrue(result.traces)


if __name__ == "__main__":
    unittest.main()
