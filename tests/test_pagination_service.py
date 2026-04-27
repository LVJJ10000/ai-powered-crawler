import unittest

from domain.pagination_models import PaginationResult, StopReason
from infrastructure.pagination.coordinator import PaginationCoordinator
from services.pagination_service import PaginationService


class _FakeFetcher:
    def __init__(self, use_playwright):
        self.use_playwright = use_playwright


class _FakeEngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def run(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class TestPaginationService(unittest.IsolatedAsyncioTestCase):
    async def test_compatibility_service_uses_infrastructure_coordinator(self):
        result = PaginationResult(
            pages=[("https://example.com/list", "<html>1</html>")],
            stop_reason=StopReason.TARGET_REACHED,
            traces=[],
        )
        url_engine = _FakeEngine(result)
        playwright_engine = _FakeEngine(result)
        service = PaginationService(
            fetcher=_FakeFetcher(use_playwright=True),
            engine=url_engine,
            playwright_engine=playwright_engine,
        )

        self.assertIsInstance(service._coordinator, PaginationCoordinator)

    async def test_compatibility_service_routes_to_correct_engine(self):
        result = PaginationResult(
            pages=[("https://example.com/list", "<html>1</html>")],
            stop_reason=StopReason.TARGET_REACHED,
            traces=[],
        )
        url_engine = _FakeEngine(result)
        playwright_engine = _FakeEngine(result)
        service = PaginationService(
            fetcher=_FakeFetcher(use_playwright=True),
            engine=url_engine,
            playwright_engine=playwright_engine,
        )

        await service.follow(
            start_html="<html>1</html>",
            start_url="https://example.com/list",
            pagination_xpath="//a[@rel='next']",
            pagination_type=None,
            max_list_pages=1,
        )

        self.assertEqual(0, len(url_engine.calls))
        self.assertEqual(1, len(playwright_engine.calls))

    async def test_follow_uses_playwright_engine_when_fetcher_uses_playwright(self):
        result = PaginationResult(
            pages=[
                ("https://example.com/list", "<html>1</html>"),
                ("https://example.com/list", "<html>2</html>"),
            ],
            stop_reason=StopReason.TARGET_REACHED,
            traces=[],
        )
        url_engine = _FakeEngine(result)
        playwright_engine = _FakeEngine(result)
        service = PaginationService(
            fetcher=_FakeFetcher(use_playwright=True),
            engine=url_engine,
            playwright_engine=playwright_engine,
        )

        pages = await service.follow(
            start_html="<html>ignored</html>",
            start_url="https://example.com/list",
            pagination_xpath="//a[@rel='next']",
            pagination_type=None,
            max_list_pages=2,
        )

        self.assertEqual(0, len(url_engine.calls))
        self.assertEqual(1, len(playwright_engine.calls))
        self.assertEqual(2, len(pages))

    async def test_follow_uses_url_engine_when_playwright_is_disabled(self):
        result = PaginationResult(
            pages=[
                ("https://example.com/list?page=1", "<html>1</html>"),
                ("https://example.com/list?page=2", "<html>2</html>"),
            ],
            stop_reason=StopReason.TARGET_REACHED,
            traces=[],
        )
        url_engine = _FakeEngine(result)
        playwright_engine = _FakeEngine(result)
        service = PaginationService(
            fetcher=_FakeFetcher(use_playwright=False),
            engine=url_engine,
            playwright_engine=playwright_engine,
        )

        await service.follow(
            start_html="<html>page one</html>",
            start_url="https://example.com/list?page=1",
            pagination_xpath="//a[@rel='next']/@href",
            pagination_type=None,
            max_list_pages=2,
        )

        self.assertEqual(1, len(url_engine.calls))
        self.assertEqual(0, len(playwright_engine.calls))


if __name__ == "__main__":
    unittest.main()
