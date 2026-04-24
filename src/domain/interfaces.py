from typing import Protocol

from domain.models import PatternModel, RunConfig, SelectedLinksResult, XPathCandidate
from models.schemas import CrawlConfig, PageData


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
        candidates: list[XPathCandidate],
        list_pages: list[tuple[str, str]],
        max_pages: int,
    ) -> SelectedLinksResult:
        ...


class IExtractionService(Protocol):
    def extract_pages(
        self,
        batch: list[tuple[str, str]],
        crawl_config: CrawlConfig,
        client,
        label: str = "",
    ) -> tuple[list[PageData], CrawlConfig]:
        ...


class IPaginationService(Protocol):
    async def follow(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        max_list_pages: int,
    ) -> list[tuple[str, str]]:
        ...


class IListPipeline(Protocol):
    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        list_config: CrawlConfig,
        link_candidates: list[XPathCandidate],
    ):
        ...


class IDetailPipeline(Protocol):
    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        detail_config: CrawlConfig,
    ):
        ...
