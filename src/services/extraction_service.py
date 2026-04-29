from application.services.extraction_coordinator import ExtractionCoordinator
from models.schemas import CrawlConfig, PageData


class ExtractionService:
    def __init__(self, coordinator: ExtractionCoordinator | None = None):
        self.coordinator = coordinator or ExtractionCoordinator()

    def extract_batch(
        self,
        batch: list[tuple[str, str]],
        crawl_plan: CrawlConfig,
        client=None,
        label: str = "",
        session_key=None,
    ) -> tuple[list[PageData], CrawlConfig]:
        return self.coordinator.extract_batch(
            batch=batch,
            crawl_plan=crawl_plan,
            session_key=session_key,
            client=client,
            label=label,
        )

    def discover_child_urls(
        self,
        record: PageData,
        crawl_plan: CrawlConfig,
        page_html: str,
        page_url: str,
        remaining_pages: int,
    ) -> list[str]:
        return self.coordinator.discover_child_urls(
            record=record,
            crawl_plan=crawl_plan,
            page_html=page_html,
            page_url=page_url,
            remaining_pages=remaining_pages,
        )

    def extract_pages(
        self,
        batch: list[tuple[str, str]],
        crawl_config: CrawlConfig,
        client=None,
        label: str = "",
        session_key=None,
    ) -> tuple[list[PageData], CrawlConfig]:
        return self.extract_batch(
            batch=batch,
            crawl_plan=crawl_config,
            session_key=session_key,
            client=client,
            label=label,
        )

    def collect_sub_detail_urls(
        self,
        page_data: dict,
        detail_config: CrawlConfig,
        page_html: str,
        page_url: str,
        max_pages: int,
    ) -> list[str]:
        record = page_data if hasattr(page_data, "data") else PageData(url=page_url, data=page_data)
        return self.discover_child_urls(
            record=record,
            crawl_plan=detail_config,
            page_html=page_html,
            page_url=page_url,
            remaining_pages=max_pages,
        )
