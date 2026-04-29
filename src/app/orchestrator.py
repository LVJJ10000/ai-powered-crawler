from application.use_cases.crawl_website import CrawlWebsite


class CrawlOrchestrator:
    def __init__(self, crawl_website: CrawlWebsite):
        self.crawl_website = crawl_website

    async def run(self, run_config):
        return await self.crawl_website.execute(run_config)
