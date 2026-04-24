import argparse
import asyncio
import sys
from collections.abc import Sequence

from openai import OpenAI

import config
from app.factory import ServiceFactory
from app.orchestrator import CrawlOrchestrator
from crawler.fetcher import PageFetcher
from domain.models import RunConfig


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def parse_args(argv: Sequence[str] | None = None):
    parser = argparse.ArgumentParser(description="AI-Powered-Crawler adaptive crawler")
    parser.add_argument("url", help="Starting URL to crawl")
    parser.add_argument("--output", "-o", default="output.json", help="Output JSON file path")
    parser.add_argument("--max-pages", type=int, default=config.MAX_PAGES, help="Max detail pages to crawl")
    parser.add_argument("--max-list-pages", type=int, default=10, help="Max list pages to paginate")
    parser.add_argument("--depth", type=_positive_int, default=2, help="Traversal depth from the start page")
    parser.add_argument("--use-playwright", action="store_true", help="Force Playwright for fetching")
    return parser.parse_args(argv)


def build_run_config(argv: Sequence[str] | None = None) -> RunConfig:
    args = parse_args(argv)
    return RunConfig(
        start_url=args.url,
        output_path=args.output,
        max_pages=args.max_pages,
        max_list_pages=args.max_list_pages,
        use_playwright=args.use_playwright,
        depth=args.depth,
    )


def build_client_kwargs() -> dict[str, str]:
    if not config.API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    kwargs = {"api_key": config.API_KEY}
    if config.BASE_URL:
        kwargs["base_url"] = config.BASE_URL
    return kwargs


async def run(argv: Sequence[str] | None = None) -> None:
    run_config = build_run_config(argv)

    try:
        client_kwargs = build_client_kwargs()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    client = OpenAI(**client_kwargs)

    async with PageFetcher(use_playwright=run_config.use_playwright) as fetcher:
        analyzer_service, list_pipeline, detail_pipeline = ServiceFactory.build(
            client=client,
            fetcher=fetcher,
        )
        orchestrator = CrawlOrchestrator(
            fetcher=fetcher,
            analyzer_service=analyzer_service,
            list_pipeline=list_pipeline,
            detail_pipeline=detail_pipeline,
        )
        await orchestrator.run(run_config)


def main() -> None:
    asyncio.run(run())
