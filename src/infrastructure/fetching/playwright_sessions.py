import config


class PlaywrightPaginationSession:
    def __init__(self, page):
        self._page = page

    async def capture_snapshot(self) -> tuple[str, str]:
        return self._page.url, await self._page.content()

    async def click_if_possible(self, xpath: str) -> bool:
        if not xpath:
            return False

        locator = self._page.locator(f"xpath={xpath}")
        if await locator.count() == 0:
            return False

        target = locator.first
        if not await target.is_visible():
            return False
        if not await target.is_enabled():
            return False

        try:
            await target.click(timeout=config.REQUEST_TIMEOUT * 1000)
        except Exception:
            return False

        await self._wait_for_settle()
        return True

    async def scroll_viewport(self) -> None:
        viewport_height = await self._page.evaluate("window.innerHeight")
        await self._page.evaluate("(height) => window.scrollBy(0, height)", viewport_height)
        await self._wait_for_settle()

    async def close(self) -> None:
        await self._page.close()

    async def _wait_for_settle(self) -> None:
        try:
            await self._page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        await self._page.wait_for_timeout(750)
