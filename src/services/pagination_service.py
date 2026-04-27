import asyncio

import config
from domain.pagination_models import PaginationResult
from infrastructure.pagination.coordinator import PaginationCoordinator
from infrastructure.pagination.progress_detector import ProgressDetector
from services.pagination_engine import PaginationEngine
from services.playwright_pagination_engine import PlaywrightPaginationEngine


class PaginationService:
    def __init__(self, fetcher, engine=None, playwright_engine=None):
        engine = engine or PaginationEngine(fetcher=fetcher, progress_detector=ProgressDetector())
        playwright_engine = playwright_engine or PlaywrightPaginationEngine(
            session_factory=fetcher.open_pagination_session,
            progress_detector=ProgressDetector(),
        )
        self._coordinator = PaginationCoordinator(
            fetcher=fetcher,
            engine=engine,
            playwright_engine=playwright_engine,
        )
        self.fetcher = self._coordinator.fetcher
        self.engine = self._coordinator.engine
        self.playwright_engine = self._coordinator.playwright_engine

    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        max_list_pages: int,
    ) -> list[tuple[str, str]]:
        pages = await self._coordinator.follow(
            start_html=start_html,
            start_url=start_url,
            pagination_xpath=pagination_xpath,
            pagination_type=pagination_type,
            max_list_pages=max_list_pages,
        )
        for page_url, _ in self.last_result.pages[1:]:
            print(f"    Paginated: {page_url}")
            await asyncio.sleep(config.REQUEST_DELAY)
        print(f"    Pagination stop reason: {self.last_result.stop_reason.value}")
        return pages

    @property
    def last_result(self) -> PaginationResult | None:
        return self._coordinator.last_result
