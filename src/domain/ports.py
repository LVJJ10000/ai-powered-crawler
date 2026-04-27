from typing import Protocol

from domain.analysis_entities import PaginationType
from domain.crawl_entities import CrawlRequest, LinkCandidate, LinkSelection
from domain.extraction_entities import CrawlPlan, ExtractionRecord
from domain.models import PatternModel


class IPageAnalyzer(Protocol):
    def analyze(self, raw_html: str, label: str):
        ...


class ILinkExtractor(Protocol):
    def extract_links(self, page_html: str, page_url: str, xpath: str) -> list[str]:
        ...


class IPatternLearner(Protocol):
    def learn(self, urls: list[str]) -> PatternModel:
        ...

    def evaluate(self, urls: list[str], model: PatternModel) -> tuple[float, float]:
        ...


class ILinkSelectionStrategy(Protocol):
    def select(
        self,
        candidates: list[LinkCandidate],
        list_pages: list[tuple[str, str]],
        max_pages: int,
    ) -> LinkSelection:
        ...


class IExtractionService(Protocol):
    def extract_pages(
        self,
        batch: list[tuple[str, str]],
        crawl_config: CrawlPlan,
        client,
        label: str = "",
    ) -> tuple[list[ExtractionRecord], CrawlPlan]:
        ...


class IPaginationService(Protocol):
    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type: PaginationType | None,
        max_list_pages: int,
    ) -> list[tuple[str, str]]:
        ...


class IListPipeline(Protocol):
    async def run(
        self,
        run_config: CrawlRequest,
        start_url: str,
        raw_html: str,
        list_config: CrawlPlan,
        link_candidates: list[LinkCandidate],
    ):
        ...


class IPlaywrightPaginationSession(Protocol):
    async def capture_snapshot(self) -> tuple[str, str]:
        ...

    async def click_if_possible(self, xpath: str) -> bool:
        ...

    async def scroll_viewport(self) -> None:
        ...

    async def close(self) -> None:
        ...


class IDetailPipeline(Protocol):
    async def run(
        self,
        run_config: CrawlRequest,
        start_url: str,
        raw_html: str,
        detail_config: CrawlPlan,
    ):
        ...
