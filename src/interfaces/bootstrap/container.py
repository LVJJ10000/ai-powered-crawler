from dataclasses import dataclass

from openai import OpenAI

import config
from app.factory import ServiceFactory
from application.dto.crawl_outcomes import CrawlOutcome
from application.use_cases.crawl_website import CrawlWebsite
from crawler.fetcher import PageFetcher
from infrastructure.reporting.console_reporter import ConsoleRunReporter
from infrastructure.storage.json_output_writer import JsonOutputWriter


@dataclass
class Container:
    crawl_website: object
    output_writer: object


class _CachingPageSource:
    def __init__(self, fetcher):
        self._fetcher = fetcher
        self._pages: dict[str, str] = {}

    async def fetch(self, url: str) -> str:
        if url not in self._pages:
            self._pages[url] = await self._fetcher.fetch(url)
        return self._pages[url]

    def get_cached(self, url: str) -> str | None:
        return self._pages.get(url)

    def __getattr__(self, name):
        return getattr(self._fetcher, name)


class _ListingCrawlerAdapter:
    def __init__(self, page_source, pipeline):
        self._page_source = page_source
        self._pipeline = pipeline

    async def crawl(self, request, analysis):
        raw_html = self._page_source.get_cached(request.start_url)
        if raw_html is None:
            raw_html = await self._page_source.fetch(request.start_url)

        records, export_plan = await self._pipeline.run(
            run_config=request,
            start_url=request.start_url,
            raw_html=raw_html,
            list_config=analysis.crawl_plan,
            link_candidates=analysis.link_candidates,
        )
        return CrawlOutcome(
            records=records,
            export_plan=export_plan or analysis.crawl_plan,
        )


class _DetailCrawlerAdapter:
    def __init__(self, page_source, pipeline):
        self._page_source = page_source
        self._pipeline = pipeline

    async def crawl(self, request, analysis):
        raw_html = self._page_source.get_cached(request.start_url)
        if raw_html is None:
            raw_html = await self._page_source.fetch(request.start_url)

        records, export_plan = await self._pipeline.run(
            run_config=request,
            start_url=request.start_url,
            raw_html=raw_html,
            detail_config=analysis.crawl_plan,
        )
        return CrawlOutcome(
            records=records,
            export_plan=export_plan or analysis.crawl_plan,
        )


class _BootstrappedCrawlWebsite:
    def __init__(self, reporter):
        self._reporter = reporter

    async def execute(self, request):
        client = OpenAI(**_build_client_kwargs())
        async with PageFetcher(use_playwright=request.use_playwright) as fetcher:
            page_source = _CachingPageSource(fetcher)
            analyzer_service, list_pipeline, detail_pipeline = ServiceFactory.build(
                client=client,
                fetcher=page_source,
            )
            crawl_website = CrawlWebsite(
                page_source=page_source,
                start_page_analyzer=analyzer_service,
                listing_crawler=_ListingCrawlerAdapter(page_source, list_pipeline),
                detail_crawler=_DetailCrawlerAdapter(page_source, detail_pipeline),
                reporter=self._reporter,
            )
            return await crawl_website.execute(request)


def _build_client_kwargs() -> dict[str, str]:
    if not config.API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    kwargs = {"api_key": config.API_KEY}
    if config.BASE_URL:
        kwargs["base_url"] = config.BASE_URL
    return kwargs


def build_container() -> Container:
    reporter = ConsoleRunReporter()
    output_writer = JsonOutputWriter()
    return Container(
        crawl_website=_BootstrappedCrawlWebsite(reporter),
        output_writer=output_writer,
    )
