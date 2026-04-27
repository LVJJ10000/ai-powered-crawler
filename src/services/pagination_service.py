from domain.pagination_models import PaginationResult
from infrastructure.pagination.coordinator import PaginationCoordinator


class PaginationService:
    def __init__(self, fetcher, engine=None, playwright_engine=None):
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
        return await self._coordinator.follow(
            start_html=start_html,
            start_url=start_url,
            pagination_xpath=pagination_xpath,
            pagination_type=pagination_type,
            max_list_pages=max_list_pages,
        )

    @property
    def last_result(self) -> PaginationResult | None:
        return self._coordinator.last_result
