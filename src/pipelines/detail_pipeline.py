from domain.models import RunConfig
from models.schemas import CrawlConfig, PageData
from pipelines.base_pipeline import BasePipeline


class DetailPipeline(BasePipeline):
    def __init__(self, fetcher, extraction_service, analyzer_service):
        self.fetcher = fetcher
        self.extraction_service = extraction_service
        self.analyzer_service = analyzer_service

    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        detail_config: CrawlConfig,
    ) -> tuple[list[PageData], CrawlConfig]:
        print(f"\n[Step 2] Extracting data from start detail page...")
        results, detail_config = self.extraction_service.extract_pages(
            [(start_url, raw_html)], detail_config, self.analyzer_service.client, label="detail"
        )

        print(f"\n[Step 3] Discovering sub-detail page URLs...")
        first_data = results[0].data if results else {}
        sub_urls = self.extraction_service.collect_sub_detail_urls(
            first_data, detail_config, raw_html, start_url, run_config.max_pages
        )
        print(f"  Found {len(sub_urls)} sub-detail URLs")

        if sub_urls:
            print(f"\n[Step 4] Crawling {len(sub_urls)} sub-detail pages...")
            sub_batch = await self.fetcher.fetch_many(sub_urls)
            sub_results, detail_config = self.extraction_service.extract_pages(
                sub_batch, detail_config, self.analyzer_service.client, label="detail"
            )
            results.extend(sub_results)
            print(f"  Extracted {len(sub_results)} additional detail records")
        else:
            print("\n[Step 4] No sub-detail pages to crawl.")

        return results, detail_config

