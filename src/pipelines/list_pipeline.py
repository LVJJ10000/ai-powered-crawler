import logging
from collections import OrderedDict

from domain.models import ListDiscoveryResult, RunConfig, XPathCandidate
from models.schemas import CrawlConfig, PageData, PageType
from pipelines.base_pipeline import BasePipeline
from crawler.url_utils import get_domain

logger = logging.getLogger(__name__)


class ListPipeline(BasePipeline):
    def __init__(
        self,
        fetcher,
        analyzer_service,
        extraction_service,
        pagination_service,
        link_xpath_service,
    ):
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
        print(f"\n[Step 2] Paginating list pages (max {run_config.max_list_pages})...")
        list_pages = await self.pagination_service.follow(
            raw_html,
            start_url,
            list_config.pagination_xpath,
            list_config.pagination_type,
            run_config.max_list_pages,
        )
        print(f"  Total list pages: {len(list_pages)}")

        print(f"\n[Step 3] Discovering detail URLs via AI XPath...")
        selection = self.link_xpath_service.evaluate_candidates(
            candidates=link_candidates,
            list_pages=list_pages,
            max_pages=run_config.max_pages,
        )

        if not selection.selected_urls:
            print("  No detail URLs found. Nothing to crawl.")
            return ListDiscoveryResult(detail_urls=[], selected_xpaths=[])

        print(f"  Selected {len(selection.selected_urls)} URLs using: {', '.join(selection.selected_xpaths)}")
        return ListDiscoveryResult(
            detail_urls=selection.selected_urls,
            selected_xpaths=selection.selected_xpaths,
        )

    async def run(
        self,
        run_config: RunConfig,
        start_url: str,
        raw_html: str,
        list_config: CrawlConfig,
        link_candidates: list[XPathCandidate],
    ) -> tuple[list[PageData], CrawlConfig | None]:
        print(f"\n[Step 2] Paginating list pages (max {run_config.max_list_pages})...")
        list_pages = await self.pagination_service.follow(
            raw_html,
            start_url,
            list_config.pagination_xpath,
            list_config.pagination_type,
            run_config.max_list_pages,
        )
        print(f"  Total list pages: {len(list_pages)}")

        print(f"\n[Step 3] Discovering detail URLs via AI XPath...")
        selection = self.link_xpath_service.evaluate_candidates(
            candidates=link_candidates,
            list_pages=list_pages,
            max_pages=run_config.max_pages,
        )
        for eval_result in selection.evaluations:
            print(
                f"    XPath score={eval_result.score:.3f} "
                f"coverage={eval_result.pattern_coverage:.2f} "
                f"urls={len(eval_result.urls)} -> {eval_result.candidate.xpath}"
            )

        detail_urls = selection.selected_urls
        if not detail_urls:
            print("  No detail URLs found. Nothing to crawl.")
            return [], None
        print(f"  Selected {len(detail_urls)} URLs using: {', '.join(selection.selected_xpaths)}")

        domain_buckets = self._bucket_urls_by_domain(detail_urls)
        print(f"  Domains discovered: {', '.join(domain_buckets.keys())}")

        print(f"\n[Step 4/5] Analyzing + crawling detail pages by domain...")
        all_results: list[PageData] = []
        export_config: CrawlConfig | None = None
        best_result_count = -1

        total_domains = len(domain_buckets)
        for idx, (domain, domain_urls) in enumerate(domain_buckets.items(), 1):
            print(f"  [{idx}/{total_domains}] Domain: {domain} ({len(domain_urls)} URLs)")
            print(f"    Template: {domain_urls[0]}")
            try:
                template_html = await self.fetcher.fetch(domain_urls[0])
                analysis = self.analyzer_service.analyze(template_html, label=f"detail page ({domain})")
                detail_config = analysis.crawl_config
                if detail_config.page_type != PageType.DETAIL:
                    print(f"    Skipped {domain}: detected as {detail_config.page_type.value}, not detail template")
                    continue
                if not detail_config.fields:
                    print(f"    Skipped {domain}: no fields detected")
                    continue

                detail_batch = await self.fetcher.fetch_many(domain_urls)
                domain_results, domain_config = self.extraction_service.extract_pages(
                    detail_batch, detail_config, self.analyzer_service.client, label=f"detail:{domain}"
                )
                all_results.extend(domain_results)
                print(f"    Extracted {len(domain_results)} records from {domain}")

                if len(domain_results) > best_result_count:
                    best_result_count = len(domain_results)
                    export_config = domain_config
            except Exception as exc:
                logger.error(f"Domain crawl failed for {domain}: {exc}")
                print(f"    ERROR on {domain}: {exc}")

        print(f"  Extracted {len(all_results)} detail records")
        return all_results, export_config

    @staticmethod
    def _bucket_urls_by_domain(urls: list[str]) -> OrderedDict[str, list[str]]:
        buckets: OrderedDict[str, list[str]] = OrderedDict()
        for url in urls:
            domain = get_domain(url) or "unknown"
            buckets.setdefault(domain, []).append(url)
        return buckets
