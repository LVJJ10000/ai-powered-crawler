import inspect
from collections import OrderedDict

from crawler.url_utils import get_domain
from domain.analysis_entities import PageType
from domain.models import DetailLayerResult


class DetailCrawler:
    def __init__(self, fetcher, extraction_coordinator, analyzer_service):
        self.fetcher = fetcher
        self.extraction_coordinator = extraction_coordinator
        self.analyzer_service = analyzer_service

    async def run(
        self,
        run_config,
        start_url: str,
        raw_html: str,
        detail_config,
    ):
        session_key = get_domain(start_url) or start_url
        print("\n[Step 2] Extracting data from start detail page...")
        results, detail_config = self._extract_batch(
            batch=[(start_url, raw_html)],
            crawl_plan=detail_config,
            session_key=session_key,
            label="detail",
        )

        print("\n[Step 3] Discovering sub-detail page URLs...")
        sub_urls = []
        remaining_pages = max(run_config.max_pages - 1, 0)
        if results:
            sub_urls = self.extraction_coordinator.discover_child_urls(
                record=results[0],
                crawl_plan=detail_config,
                page_html=raw_html,
                page_url=start_url,
                remaining_pages=remaining_pages,
            )
        print(f"  Found {len(sub_urls)} sub-detail URLs")

        if sub_urls and remaining_pages > 0:
            print(f"\n[Step 4] Crawling {len(sub_urls)} sub-detail pages...")
            sub_batch = await self.fetcher.fetch_many(sub_urls[:remaining_pages])
            sub_results, detail_config = self._extract_batch(
                batch=sub_batch,
                crawl_plan=detail_config,
                session_key=session_key,
                label="detail",
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
        crawl_plan_cache: dict[str, object] | None = None,
        prefetched_pages: dict[str, str] | None = None,
    ) -> DetailLayerResult:
        crawl_plan_cache = dict(crawl_plan_cache or {})
        if remaining_pages <= 0 or not urls:
            return DetailLayerResult(config_cache=crawl_plan_cache)

        budgeted_urls = urls[:remaining_pages]
        prefetched_pages = dict(prefetched_pages or {})
        all_records = []
        next_urls = []
        export_config = None

        for domain, domain_urls in self._bucket_urls_by_domain(budgeted_urls).items():
            domain_prefetched_pages = {
                url: html for url, html in prefetched_pages.items() if url in domain_urls
            }
            detail_config = crawl_plan_cache.get(domain)
            if detail_config is None:
                template_url = domain_urls[0]
                template_html = domain_prefetched_pages.get(template_url)
                if template_html is None:
                    template_html = await self.fetcher.fetch(template_url)
                    domain_prefetched_pages[template_url] = template_html

                analysis = await self._analyze_detail_template(template_html, domain)
                detail_config = self._normalize_crawl_plan(analysis)
                if detail_config.page_type != PageType.DETAIL or not detail_config.fields:
                    continue
                crawl_plan_cache[domain] = detail_config

            missing_urls = [url for url in domain_urls if url not in domain_prefetched_pages]
            fetched_batch = await self.fetcher.fetch_many(missing_urls) if missing_urls else []
            batch_map = {url: html for url, html in fetched_batch}
            batch_map.update(domain_prefetched_pages)

            batch = [(url, batch_map[url]) for url in domain_urls if url in batch_map]
            records, detail_config = self._extract_batch(
                batch=batch,
                crawl_plan=detail_config,
                session_key=domain,
                label=f"detail:{domain}",
            )
            all_records.extend(records)
            if export_config is None:
                export_config = detail_config

            for record in records:
                page_url = getattr(record, "url", "")
                page_html = batch_map.get(page_url)
                if not page_html:
                    continue
                next_urls.extend(
                    self.extraction_coordinator.discover_child_urls(
                        record=record,
                        crawl_plan=detail_config,
                        page_html=page_html,
                        page_url=page_url,
                        remaining_pages=remaining_pages,
                    )
                )

        return DetailLayerResult(
            records=all_records,
            next_detail_urls=list(dict.fromkeys(next_urls)),
            export_config=export_config,
            config_cache=crawl_plan_cache,
        )

    async def _analyze_detail_template(self, raw_html: str, domain: str):
        analyzer = getattr(self.analyzer_service, "analyze_detail_template", None)
        if analyzer is None:
            analyzer = self.analyzer_service.analyze
        result = analyzer(raw_html, label=f"detail page ({domain})")
        return await self._resolve(result)

    @staticmethod
    def _normalize_crawl_plan(analysis):
        crawl_plan = getattr(analysis, "crawl_plan", None) or getattr(analysis, "crawl_config", None)
        return crawl_plan or analysis

    def _analysis_client(self):
        return getattr(self.analyzer_service, "client", None)

    def _extract_batch(self, batch, crawl_plan, session_key, label: str):
        kwargs = {
            "batch": batch,
            "crawl_plan": crawl_plan,
            "client": self._analysis_client(),
            "label": label,
        }

        try:
            parameters = inspect.signature(self.extraction_coordinator.extract_batch).parameters
        except (TypeError, ValueError):
            parameters = {}

        if "session_key" in parameters:
            kwargs["session_key"] = session_key

        return self.extraction_coordinator.extract_batch(**kwargs)

    @staticmethod
    async def _resolve(value):
        if inspect.isawaitable(value):
            return await value
        return value

    @staticmethod
    def _bucket_urls_by_domain(urls: list[str]) -> OrderedDict[str, list[str]]:
        buckets: OrderedDict[str, list[str]] = OrderedDict()
        for url in urls:
            buckets.setdefault(get_domain(url) or "unknown", []).append(url)
        return buckets
