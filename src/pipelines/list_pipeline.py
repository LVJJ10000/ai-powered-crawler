from application.dto.start_page_analysis import StartPageAnalysis
from application.services.detail_url_discovery import DetailUrlDiscovery
from application.use_cases.crawl_details import DetailCrawler
from application.use_cases.crawl_listing import ListingCrawler
from application.services.extraction_coordinator import ExtractionCoordinator
from domain.models import ListDiscoveryResult, RunConfig, XPathCandidate
from models.schemas import CrawlConfig, PageData
from pipelines.base_pipeline import BasePipeline


class ListPipeline(BasePipeline):
    def __init__(
        self,
        fetcher=None,
        analyzer_service=None,
        extraction_service=None,
        pagination_service=None,
        link_xpath_service=None,
        listing_crawler=None,
    ):
        if listing_crawler is None:
            if pagination_service is None:
                raise TypeError(
                    "ListPipeline requires listing_crawler or pagination_service"
                )
            detail_url_discovery = self._build_detail_url_discovery(link_xpath_service)
            detail_crawler = self._build_detail_crawler(fetcher, extraction_service, analyzer_service)
            listing_crawler = ListingCrawler(
                paginator=pagination_service,
                detail_url_discovery=detail_url_discovery,
                detail_crawler=detail_crawler,
            )

        self.listing_crawler = listing_crawler
        self.fetcher = fetcher
        self.analyzer_service = analyzer_service
        self.extraction_service = extraction_service
        self.pagination_service = pagination_service
        self.link_xpath_service = link_xpath_service

    async def discover_detail_urls(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        list_config: CrawlConfig,
        link_candidates: list[XPathCandidate],
    ) -> ListDiscoveryResult:
        analysis = StartPageAnalysis(
            page_type=list_config.page_type,
            crawl_plan=list_config,
            link_candidates=list(link_candidates),
        )
        return await self.listing_crawler.discover_detail_urls(
            request=run_config,
            raw_html=raw_html,
            analysis=analysis,
        )

    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        list_config: CrawlConfig,
        link_candidates: list[XPathCandidate],
    ) -> tuple[list[PageData], CrawlConfig | None]:
        analysis = StartPageAnalysis(
            page_type=list_config.page_type,
            crawl_plan=list_config,
            link_candidates=list(link_candidates),
        )
        return await self.listing_crawler.run(
            request=run_config,
            raw_html=raw_html,
            analysis=analysis,
        )

    @staticmethod
    def _build_detail_url_discovery(link_xpath_service):
        if link_xpath_service is None:
            raise TypeError(
                "ListPipeline legacy constructor path requires link_xpath_service"
            )
        if hasattr(link_xpath_service, "select"):
            return link_xpath_service
        if not hasattr(link_xpath_service, "extract_links"):
            return _LegacyDetailUrlDiscoveryAdapter(link_xpath_service)

        pattern_learner = getattr(link_xpath_service, "pattern_learner", None)
        return DetailUrlDiscovery(
            link_extractor=link_xpath_service,
            pattern_learner=pattern_learner,
        )

    @staticmethod
    def _build_detail_crawler(fetcher, extraction_service, analyzer_service):
        if fetcher is None or analyzer_service is None:
            return None

        coordinator = ListPipeline._build_extraction_coordinator(extraction_service)
        return DetailCrawler(
            fetcher=fetcher,
            extraction_coordinator=coordinator,
            analyzer_service=analyzer_service,
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
        return self.extraction_service.extract_pages(
            batch,
            crawl_plan,
            client,
            label=label,
            session_key=session_key,
        )

    def discover_child_urls(self, record, crawl_plan, page_html: str, page_url: str, remaining_pages: int):
        page_data = getattr(record, "data", record)
        return self.extraction_service.collect_sub_detail_urls(
            page_data,
            crawl_plan,
            page_html,
            page_url,
            remaining_pages,
        )


class _LegacyDetailUrlDiscoveryAdapter:
    def __init__(self, link_xpath_service):
        self.link_xpath_service = link_xpath_service

    def select(self, candidates, list_pages, max_pages):
        return self.link_xpath_service.evaluate_candidates(
            candidates=candidates,
            list_pages=list_pages,
            max_pages=max_pages,
        )
