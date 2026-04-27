import inspect

from application.dto.start_page_analysis import StartPageAnalysis
from domain.analysis_entities import PageType
from domain.errors import InvalidStartPageError


START_PAGE_ANALYZED = "start_page_analyzed"


class CrawlWebsite:
    def __init__(self, page_source, start_page_analyzer, listing_crawler, detail_crawler, reporter):
        self.page_source = page_source
        self.start_page_analyzer = start_page_analyzer
        self.listing_crawler = listing_crawler
        self.detail_crawler = detail_crawler
        self.reporter = reporter

    async def execute(self, request):
        page = await self.page_source.fetch(request.start_url)
        analysis = await self._analyze_start_page(page)
        self._validate_start_page_analysis(analysis)
        self._publish_start_page_analyzed(analysis)
        if analysis.page_type == PageType.LIST:
            return await self._route_listing(request, page, analysis)
        return await self._route_detail(request, page, analysis)

    async def _analyze_start_page(self, page):
        analyze = self.start_page_analyzer.analyze
        if isinstance(page, str):
            if self._supports_label_argument(analyze):
                result = analyze(page, label="start page")
            else:
                result = analyze(page)
        else:
            result = analyze(page)
        analysis = await self._resolve(result)
        return self._normalize_analysis(analysis)

    def _normalize_analysis(self, analysis):
        if isinstance(analysis, StartPageAnalysis):
            return analysis

        crawl_plan = getattr(analysis, "crawl_plan", None) or getattr(analysis, "crawl_config", None)
        if crawl_plan is None:
            raise TypeError("Start page analysis must provide crawl_plan or crawl_config")

        page_type = getattr(analysis, "page_type", None) or crawl_plan.page_type
        link_candidates = getattr(analysis, "link_candidates", None)
        if link_candidates is None:
            link_candidates = getattr(analysis, "link_xpath_candidates", [])

        return StartPageAnalysis(
            page_type=page_type,
            crawl_plan=crawl_plan,
            link_candidates=list(link_candidates),
        )

    @staticmethod
    def _validate_start_page_analysis(analysis):
        if analysis.page_type == PageType.LIST and not analysis.link_candidates:
            raise InvalidStartPageError.missing_link_candidates()
        if analysis.page_type == PageType.DETAIL and not analysis.crawl_plan.fields:
            raise InvalidStartPageError.missing_detail_fields()

    async def _route_listing(self, request, page, analysis):
        if hasattr(self.listing_crawler, "crawl"):
            return await self._resolve(self.listing_crawler.crawl(request, analysis))
        return await self._resolve(
            self.listing_crawler.run(
                run_config=request,
                start_url=request.start_url,
                raw_html=self._raw_html(page),
                list_config=analysis.crawl_plan,
                link_candidates=analysis.link_candidates,
            )
        )

    async def _route_detail(self, request, page, analysis):
        if hasattr(self.detail_crawler, "crawl"):
            return await self._resolve(self.detail_crawler.crawl(request, analysis))
        return await self._resolve(
            self.detail_crawler.run(
                run_config=request,
                start_url=request.start_url,
                raw_html=self._raw_html(page),
                detail_config=analysis.crawl_plan,
            )
        )

    def _publish_start_page_analyzed(self, analysis):
        self.reporter.publish(
            {
                "type": START_PAGE_ANALYZED,
                "page_type": analysis.page_type.value,
            }
        )

    @staticmethod
    def _raw_html(page):
        return getattr(page, "html", page)

    @staticmethod
    def _supports_label_argument(callable_obj):
        try:
            signature = inspect.signature(callable_obj)
        except (TypeError, ValueError):
            return False

        for parameter in signature.parameters.values():
            if parameter.kind == inspect.Parameter.VAR_KEYWORD:
                return True
            if parameter.name == "label" and parameter.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                return True
        return False

    @staticmethod
    async def _resolve(value):
        if inspect.isawaitable(value):
            return await value
        return value
