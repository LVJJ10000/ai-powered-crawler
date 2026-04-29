"""
Page Fetcher - handles HTTP requests (httpx) and browser rendering (Playwright).
"""

import asyncio
import logging

import httpx

import config
from infrastructure.fetching.playwright_sessions import PlaywrightPaginationSession

logger = logging.getLogger(__name__)


class PageFetcher:
    def __init__(self, use_playwright: bool = False):
        self.use_playwright = use_playwright
        self._browser = None
        self._playwright = None
        self._client = httpx.AsyncClient(
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": config.USER_AGENT},
            follow_redirects=True,
        )

    async def fetch(self, url: str) -> str:
        """Fetch a single page, return raw HTML."""
        if self.use_playwright:
            return await self._fetch_playwright(url)
        return await self._fetch_httpx(url)

    async def _ensure_browser(self):
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=False)

    async def _fetch_httpx(self, url: str) -> str:
        """Fetch using httpx."""
        response = await self._client.get(url)
        response.raise_for_status()
        html = response.text

        from lxml import html as lhtml

        try:
            tree = lhtml.fromstring(html)
            text = tree.text_content().strip()
            if len(text) < 500:
                logger.warning(
                    f"Page {url} has very little text ({len(text)} chars). "
                    "Consider using --use-playwright for JS-rendered pages."
                )
        except Exception:
            pass

        return html

    async def _fetch_playwright(self, url: str) -> str:
        """Fetch using Playwright."""
        await self._ensure_browser()

        page = await self._browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=config.REQUEST_TIMEOUT * 1000)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
                await asyncio.sleep(2)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            except Exception:
                pass
            return await page.content()
        finally:
            await page.close()

    async def open_pagination_session(self, url: str) -> PlaywrightPaginationSession:
        if not self.use_playwright:
            raise RuntimeError("Pagination sessions require Playwright")

        await self._ensure_browser()
        page = await self._browser.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=config.REQUEST_TIMEOUT * 1000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        return PlaywrightPaginationSession(page)

    async def fetch_many(self, urls: list[str]) -> list[tuple[str, str]]:
        """Fetch multiple pages sequentially."""
        results = []
        for url in urls:
            try:
                html = await self.fetch(url)
                results.append((url, html))
            except Exception as exc:
                logger.warning(f"Failed to fetch {url}: {exc}")
            await asyncio.sleep(config.REQUEST_DELAY)
        return results

    async def close(self):
        """Clean up resources."""
        await self._client.aclose()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
