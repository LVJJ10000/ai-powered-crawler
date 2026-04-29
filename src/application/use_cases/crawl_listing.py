import inspect

from application.dto.start_page_analysis import StartPageAnalysis
from domain.models import ListDiscoveryResult


class ListingCrawler:
    def __init__(self, paginator, detail_url_discovery, detail_crawler):
        self.paginator = paginator
        self.detail_url_discovery = detail_url_discovery
        self.detail_crawler = detail_crawler

    async def discover_detail_urls(self, request, raw_html, analysis: StartPageAnalysis) -> ListDiscoveryResult:
        print(f"\n[Step 2] Paginating list pages (max {request.max_list_pages})...")
        list_pages = await self.paginator.follow(
            raw_html,
            request.start_url,
            analysis.crawl_plan.pagination_xpath,
            analysis.crawl_plan.pagination_type,
            request.max_list_pages,
        )
        print(f"  Total list pages: {len(list_pages)}")

        print("\n[Step 3] Discovering detail URLs via AI XPath...")
        selection = self.detail_url_discovery.select(
            candidates=analysis.link_candidates,
            list_pages=list_pages,
            max_pages=request.max_pages,
        )

        if not selection.selected_urls:
            print("  No detail URLs found. Nothing to crawl.")
            return ListDiscoveryResult(detail_urls=[], selected_xpaths=[])

        print(
            f"  Selected {len(selection.selected_urls)} URLs using: "
            f"{', '.join(selection.selected_xpaths)}"
        )
        return ListDiscoveryResult(
            detail_urls=selection.selected_urls,
            selected_xpaths=selection.selected_xpaths,
        )

    async def run(self, request, raw_html, analysis: StartPageAnalysis):
        discovery = await self.discover_detail_urls(request, raw_html, analysis)
        if not discovery.detail_urls:
            return [], None
        if self.detail_crawler is None:
            raise TypeError("ListingCrawler.run requires a detail_crawler")

        result = await self._crawl_details(request, analysis, discovery.detail_urls)
        records = list(getattr(result, "records", []))
        export_plan = (
            getattr(result, "export_config", None)
            or getattr(result, "export_plan", None)
            or analysis.crawl_plan
        )
        return records, export_plan

    async def _crawl_details(self, request, analysis, detail_urls):
        if hasattr(self.detail_crawler, "process_depth_layer"):
            return await self._resolve(
                self.detail_crawler.process_depth_layer(
                    urls=detail_urls,
                    remaining_pages=request.max_pages,
                    crawl_plan_cache=None,
                    prefetched_pages=None,
                )
            )

        return await self._resolve(
            self.detail_crawler.crawl(request, analysis, detail_urls=detail_urls)
        )

    @staticmethod
    async def _resolve(value):
        if inspect.isawaitable(value):
            return await value
        return value
