import unittest

from crawler.fetcher import PageFetcher
from crawler.playwright_session import PlaywrightPaginationSession as CompatibilityPlaywrightPaginationSession
from infrastructure.fetching.page_sources import PageFetcher as InfrastructurePageFetcher
from infrastructure.fetching.playwright_sessions import PlaywrightPaginationSession


class _FakeLocator:
    def __init__(self, visible=True, enabled=True):
        self._visible = visible
        self._enabled = enabled
        self.clicked = False

    async def count(self):
        return 1

    @property
    def first(self):
        return self

    async def is_visible(self):
        return self._visible

    async def is_enabled(self):
        return self._enabled

    async def click(self, timeout=None):
        self.clicked = True


class _FakePage:
    def __init__(self):
        self.url = "https://example.com/list"
        self.goto_calls = []
        self.load_state_calls = []
        self.timeout_calls = []
        self.evaluate_calls = []
        self.locator_calls = []
        self.closed = False
        self.locator_stub = _FakeLocator()

    async def goto(self, url, wait_until, timeout):
        self.goto_calls.append((url, wait_until, timeout))
        self.url = url

    async def wait_for_load_state(self, state, timeout):
        self.load_state_calls.append((state, timeout))

    async def wait_for_timeout(self, timeout_ms):
        self.timeout_calls.append(timeout_ms)

    async def content(self):
        return "<html><body>page one</body></html>"

    def locator(self, selector):
        self.locator_calls.append(selector)
        return self.locator_stub

    async def evaluate(self, script, arg=None):
        self.evaluate_calls.append((script, arg))
        if script == "window.innerHeight":
            return 900
        return None

    async def close(self):
        self.closed = True


class _FakeBrowser:
    def __init__(self, page):
        self.page = page

    async def new_page(self):
        return self.page


class TestPlaywrightPaginationSession(unittest.IsolatedAsyncioTestCase):
    async def test_compatibility_imports_expose_infrastructure_fetching_types(self):
        self.assertIs(PageFetcher, InfrastructurePageFetcher)
        self.assertIs(CompatibilityPlaywrightPaginationSession, PlaywrightPaginationSession)

    async def test_click_if_possible_uses_xpath_locator_and_waits_for_settle(self):
        page = _FakePage()
        session = PlaywrightPaginationSession(page)

        clicked = await session.click_if_possible("//a[@rel='next']")

        self.assertTrue(clicked)
        self.assertEqual(["xpath=//a[@rel='next']"], page.locator_calls)
        self.assertTrue(page.locator_stub.clicked)
        self.assertTrue(page.timeout_calls)

    async def test_open_pagination_session_returns_wrapped_page(self):
        fetcher = PageFetcher(use_playwright=True)
        page = _FakePage()
        fetcher._browser = _FakeBrowser(page)

        session = await fetcher.open_pagination_session("https://example.com/list")

        self.assertIsInstance(session, PlaywrightPaginationSession)
        self.assertEqual("https://example.com/list", page.goto_calls[0][0])
        await fetcher._client.aclose()


if __name__ == "__main__":
    unittest.main()
