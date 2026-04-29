from application.services.extraction_coordinator import ExtractionCoordinator
from application.use_cases.crawl_details import DetailCrawler
from domain.models import DetailLayerResult, RunConfig
from models.schemas import CrawlConfig, PageData
from pipelines.base_pipeline import BasePipeline


class DetailPipeline(BasePipeline):
    def __init__(
        self,
        fetcher=None,
        extraction_service=None,
        analyzer_service=None,
        detail_crawler=None,
    ):
        if detail_crawler is None:
            if fetcher is None or analyzer_service is None:
                raise TypeError(
                    "DetailPipeline requires detail_crawler or fetcher and analyzer_service"
                )
            coordinator = self._build_extraction_coordinator(extraction_service)
            detail_crawler = DetailCrawler(
                fetcher=fetcher,
                extraction_coordinator=coordinator,
                analyzer_service=analyzer_service,
            )

        self.detail_crawler = detail_crawler
        self.fetcher = fetcher or getattr(detail_crawler, "fetcher", None)
        self.extraction_service = extraction_service
        self.analyzer_service = analyzer_service or getattr(detail_crawler, "analyzer_service", None)

    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        detail_config: CrawlConfig,
    ) -> tuple[list[PageData], CrawlConfig]:
        return await self.detail_crawler.run(
            run_config=run_config,
            start_url=start_url,
            raw_html=raw_html,
            detail_config=detail_config,
        )

    async def process_depth_layer(
        self,
        urls: list[str],
        remaining_pages: int,
        config_cache: dict[str, CrawlConfig] | None = None,
        prefetched_pages: dict[str, str] | None = None,
    ) -> DetailLayerResult:
        return await self.detail_crawler.process_depth_layer(
            urls=urls,
            remaining_pages=remaining_pages,
            crawl_plan_cache=config_cache,
            prefetched_pages=prefetched_pages,
        )

    @staticmethod
    def _build_extraction_coordinator(extraction_service):
        if extraction_service is None:
            return ExtractionCoordinator()
        if hasattr(extraction_service, "coordinator"):
            return extraction_service.coordinator
        return _LegacyExtractionServiceAdapter(extraction_service)


class _LegacyExtractionServiceAdapter:
    def __init__(self, extraction_service):
        self.extraction_service = extraction_service

    def extract_batch(self, batch, crawl_plan, session_key=None, client=None, label=""):
        return self.extraction_service.extract_pages(batch, crawl_plan, client, label=label)

    def discover_child_urls(self, record, crawl_plan, page_html: str, page_url: str, remaining_pages: int):
        page_data = getattr(record, "data", record)
        return self.extraction_service.collect_sub_detail_urls(
            page_data,
            crawl_plan,
            page_html,
            page_url,
            remaining_pages,
        )
