import sys

from models.schemas import PageType
from storage.exporter import export_json


class CrawlOrchestrator:
    def __init__(self, fetcher, analyzer_service, list_pipeline, detail_pipeline):
        self.fetcher = fetcher
        self.analyzer_service = analyzer_service
        self.list_pipeline = list_pipeline
        self.detail_pipeline = detail_pipeline

    async def run(self, run_config):
        print(f"\n{'=' * 60}")
        print("AI-Powered-Crawler")
        print(f"Start URL: {run_config.start_url}")
        print(f"{'=' * 60}\n")

        print("[Step 1] Fetching & analyzing start page...")
        raw_html = await self.fetcher.fetch(run_config.start_url)
        print(f"  Fetched {len(raw_html)} chars")

        start_analysis = self.analyzer_service.analyze(raw_html, label="start page")
        start_config = start_analysis.crawl_config

        if start_config.page_type == PageType.LIST and not start_analysis.link_xpath_candidates:
            print("\nNo list-link XPath candidates found. Exiting.")
            sys.exit(1)
        if start_config.page_type == PageType.DETAIL and not start_config.fields:
            print("\nNo detail fields found. Exiting.")
            sys.exit(1)

        print(f"\n  => Start page is: {start_config.page_type.value.upper()}")

        detail_results = []
        detail_config = None
        if start_config.page_type == PageType.LIST:
            detail_results, detail_config = await self.list_pipeline.run(
                run_config=run_config,
                start_url=run_config.start_url,
                raw_html=raw_html,
                list_config=start_config,
                link_candidates=start_analysis.link_xpath_candidates,
            )
        else:
            detail_results, detail_config = await self.detail_pipeline.run(
                run_config=run_config,
                start_url=run_config.start_url,
                raw_html=raw_html,
                detail_config=start_config,
            )

        if detail_config is None:
            detail_config = start_config

        print(f"\n{'=' * 60}")
        export_json(
            data=detail_results,
            crawl_config=detail_config,
            source_url=run_config.start_url,
            output_path=run_config.output_path,
        )
        print(f"\nDone!  {len(detail_results)} detail records  ->  {run_config.output_path}")
        print(f"{'=' * 60}")
