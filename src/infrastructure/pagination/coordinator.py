from domain.pagination_models import PaginationConfig, PaginationResult


class PaginationCoordinator:
    def __init__(self, fetcher, engine, playwright_engine):
        self.fetcher = fetcher
        self.engine = engine
        self.playwright_engine = playwright_engine
        self.last_result: PaginationResult | None = None

    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        config: PaginationConfig,
    ) -> list[tuple[str, str]]:
        if self.fetcher.use_playwright:
            self.last_result = await self.playwright_engine.run(
                start_url=start_url,
                pagination_xpath=pagination_xpath,
                config=config,
            )
        else:
            self.last_result = await self.engine.run(
                start_html=start_html,
                start_url=start_url,
                pagination_xpath=pagination_xpath,
                pagination_type=pagination_type,
                config=config,
            )
        return self.last_result.pages
