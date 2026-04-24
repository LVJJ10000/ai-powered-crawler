from collections import OrderedDict

from crawler.url_utils import get_domain
from domain.models import DetailLayerResult, RunConfig
from models.schemas import CrawlConfig, PageData, PageType
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

    async def process_depth_layer(
        self,
        urls: list[str],
        remaining_pages: int,
        config_cache: dict[str, CrawlConfig] | None = None,
        prefetched_pages: dict[str, str] | None = None,
    ) -> DetailLayerResult:
        if remaining_pages <= 0 or not urls:
            return DetailLayerResult(config_cache=dict(config_cache or {}))

        budgeted_urls = urls[:remaining_pages]
        config_cache = dict(config_cache or {})
        prefetched_pages = dict(prefetched_pages or {})
        all_records = []
        next_urls = []
        export_config = None

        for domain, domain_urls in self._bucket_urls_by_domain(budgeted_urls).items():
            detail_config = config_cache.get(domain)
            if detail_config is None:
                template_url = domain_urls[0]
                template_html = prefetched_pages.get(template_url) or await self.fetcher.fetch(template_url)
                analysis = self.analyzer_service.analyze(template_html, label=f"detail page ({domain})")
                detail_config = analysis.crawl_config
                if detail_config.page_type != PageType.DETAIL or not detail_config.fields:
                    continue
                config_cache[domain] = detail_config

            missing_urls = [url for url in domain_urls if url not in prefetched_pages]
            fetched_batch = await self.fetcher.fetch_many(missing_urls)
            batch_map = {url: html for url, html in fetched_batch}
            for url, html in prefetched_pages.items():
                if url in domain_urls:
                    batch_map[url] = html

            batch = [(url, batch_map[url]) for url in domain_urls if url in batch_map]
            records, detail_config = self.extraction_service.extract_pages(
                batch,
                detail_config,
                self.analyzer_service.client,
                label=f"detail:{domain}",
            )
            all_records.extend(records)
            export_config = detail_config if export_config is None else export_config

            for record, (url, page_html) in zip(records, batch, strict=False):
                next_urls.extend(
                    self.extraction_service.collect_sub_detail_urls(
                        record.data,
                        detail_config,
                        page_html,
                        url,
                        remaining_pages,
                    )
                )

        return DetailLayerResult(
            records=all_records,
            next_detail_urls=list(dict.fromkeys(next_urls)),
            export_config=export_config,
            config_cache=config_cache,
        )

    @staticmethod
    def _bucket_urls_by_domain(urls: list[str]) -> OrderedDict[str, list[str]]:
        buckets: OrderedDict[str, list[str]] = OrderedDict()
        for url in urls:
            buckets.setdefault(get_domain(url) or "unknown", []).append(url)
        return buckets
