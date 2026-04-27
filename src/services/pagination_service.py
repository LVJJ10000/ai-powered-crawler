import asyncio

import config
from domain.pagination_models import PaginationConfig, PaginationResult
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

    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        max_list_pages: int,
    ) -> list[tuple[str, str]]:
        pagination_config = PaginationConfig(
            max_rounds=max(0, max_list_pages - 1),
            max_no_progress_rounds=2,
            max_target_pages=max_list_pages,
        )
        pages = await self._coordinator.follow(
            start_html=start_html,
            start_url=start_url,
            pagination_xpath=pagination_xpath,
            pagination_type=pagination_type,
            config=pagination_config,
        )
        for page_url, _ in self.last_result.pages[1:]:
            print(f"    Paginated: {page_url}")
            await asyncio.sleep(config.REQUEST_DELAY)
        print(f"    Pagination stop reason: {self.last_result.stop_reason.value}")
        return pages

    @property
    def fetcher(self):
        return self._coordinator.fetcher

    @fetcher.setter
    def fetcher(self, value):
        self._coordinator.fetcher = value
        if hasattr(self._coordinator.engine, "fetcher"):
            try:
                self._coordinator.engine.fetcher = value
            except AttributeError:
                pass
        if hasattr(self._coordinator.playwright_engine, "session_factory"):
            try:
                self._coordinator.playwright_engine.session_factory = value.open_pagination_session
            except AttributeError:
                pass

    @property
    def engine(self):
        return self._coordinator.engine

    @engine.setter
    def engine(self, value):
        if hasattr(value, "fetcher"):
            try:
                value.fetcher = self.fetcher
            except AttributeError:
                pass
        self._coordinator.engine = value

    @property
    def playwright_engine(self):
        return self._coordinator.playwright_engine

    @playwright_engine.setter
    def playwright_engine(self, value):
        if hasattr(value, "session_factory"):
            try:
                value.session_factory = self.fetcher.open_pagination_session
            except AttributeError:
                pass
        self._coordinator.playwright_engine = value

    @property
    def last_result(self) -> PaginationResult | None:
        return self._coordinator.last_result
