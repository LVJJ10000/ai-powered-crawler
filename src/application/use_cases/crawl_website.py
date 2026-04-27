from domain.analysis_entities import PageType


class CrawlWebsite:
    def __init__(self, page_source, start_page_analyzer, listing_crawler, detail_crawler, reporter):
        self.page_source = page_source
        self.start_page_analyzer = start_page_analyzer
        self.listing_crawler = listing_crawler
        self.detail_crawler = detail_crawler
        self.reporter = reporter

    async def execute(self, request):
        snapshot = await self.page_source.fetch(request.start_url)
        analysis = await self.start_page_analyzer.analyze(snapshot)
        self.reporter.publish({"type": "start_page_analyzed", "page_type": analysis.page_type.value})
        if analysis.page_type == PageType.LIST:
            return await self.listing_crawler.crawl(request, analysis)
        return await self.detail_crawler.crawl(request, analysis)
