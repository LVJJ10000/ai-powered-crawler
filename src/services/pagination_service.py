import asyncio
import logging

import config
from domain.pagination_models import PaginationConfig, PaginationResult
from services.pagination_engine import PaginationEngine
from services.progress_detector import ProgressDetector

logger = logging.getLogger(__name__)


class PaginationService:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.engine = PaginationEngine(fetcher=fetcher, progress_detector=ProgressDetector())
        self.last_result: PaginationResult | None = None

    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        max_list_pages: int,
    ) -> list[tuple[str, str]]:
        conf = PaginationConfig(
            max_rounds=max(0, max_list_pages - 1),
            max_no_progress_rounds=2,
            max_target_pages=max_list_pages,
        )
        self.last_result = await self.engine.run(
            start_html=start_html,
            start_url=start_url,
            pagination_xpath=pagination_xpath,
            pagination_type=pagination_type,
            config=conf,
        )

        for page_url, _ in self.last_result.pages[1:]:
            print(f"    Paginated: {page_url}")
            await asyncio.sleep(config.REQUEST_DELAY)
        print(f"    Pagination stop reason: {self.last_result.stop_reason.value}")
        return self.last_result.pages
