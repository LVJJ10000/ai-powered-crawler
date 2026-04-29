import unittest

from domain.pagination_models import PaginationConfig, StopReason
from infrastructure.pagination.progress_detector import ProgressDetector
from services.playwright_pagination_engine import PlaywrightPaginationEngine


class _FakeSession:
    def __init__(self, snapshots, click_advances=False, scroll_advances=True):
        self.snapshots = list(snapshots)
        self.index = 0
        self.click_advances = click_advances
        self.scroll_advances = scroll_advances
        self.actions = []
        self.closed = False

    async def capture_snapshot(self):
        return self.snapshots[self.index]

    async def click_if_possible(self, xpath):
        self.actions.append(("click", xpath))
        if not self.click_advances:
            return False
        self.index = min(self.index + 1, len(self.snapshots) - 1)
        return True

    async def scroll_viewport(self):
        self.actions.append(("scroll", None))
        if self.scroll_advances:
            self.index = min(self.index + 1, len(self.snapshots) - 1)

    async def close(self):
        self.closed = True


def _session_factory(session):
    async def factory(start_url):
        return session

    return factory


class TestPlaywrightPaginationEngine(unittest.IsolatedAsyncioTestCase):
    async def test_clicks_ai_selector_before_scroll(self):
        session = _FakeSession(
            snapshots=[
                ("https://example.com/list", "<html><a href='/1'>same</a></html>"),
                ("https://example.com/list?page=2", "<html><a href='/2'>same</a></html>"),
            ],
            click_advances=True,
        )
        engine = PlaywrightPaginationEngine(
            session_factory=_session_factory(session),
            progress_detector=ProgressDetector(),
        )

        result = await engine.run(
            start_url="https://example.com/list",
            pagination_xpath="//a[@rel='next']",
            config=PaginationConfig(max_rounds=1, max_target_pages=2),
        )

        self.assertEqual([("click", "//a[@rel='next']")], session.actions)
        self.assertEqual(2, len(result.pages))
        self.assertEqual("https://example.com/list?page=2", result.pages[1][0])

    async def test_falls_back_to_scroll_and_preserves_same_url_snapshot(self):
        session = _FakeSession(
            snapshots=[
                ("https://example.com/list", "<html><a href='/detail/1'>Read more</a></html>"),
                (
                    "https://example.com/list",
                    "<html><a href='/detail/1'>Read more</a><a href='/detail/2'>Read more</a></html>",
                ),
            ],
            click_advances=False,
            scroll_advances=True,
        )
        engine = PlaywrightPaginationEngine(
            session_factory=_session_factory(session),
            progress_detector=ProgressDetector(),
        )

        result = await engine.run(
            start_url="https://example.com/list",
            pagination_xpath="//button[@data-next]",
            config=PaginationConfig(max_rounds=1, max_target_pages=2),
        )

        self.assertEqual(
            [("click", "//button[@data-next]"), ("scroll", None)],
            session.actions,
        )
        self.assertEqual(2, len(result.pages))
        self.assertEqual("https://example.com/list", result.pages[1][0])

    async def test_stops_after_no_progress_limit(self):
        session = _FakeSession(
            snapshots=[
                ("https://example.com/list", "<html><a href='/detail/1'>Read more</a></html>"),
            ],
            click_advances=False,
            scroll_advances=False,
        )
        engine = PlaywrightPaginationEngine(
            session_factory=_session_factory(session),
            progress_detector=ProgressDetector(),
        )

        result = await engine.run(
            start_url="https://example.com/list",
            pagination_xpath=None,
            config=PaginationConfig(max_rounds=2, max_no_progress_rounds=1, max_target_pages=3),
        )

        self.assertEqual(StopReason.NO_PROGRESS_LIMIT, result.stop_reason)
        self.assertTrue(session.closed)


if __name__ == "__main__":
    unittest.main()
