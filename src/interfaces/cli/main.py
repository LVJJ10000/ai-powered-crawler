import argparse
import asyncio
import sys
from collections.abc import Sequence

import config
from domain.crawl_entities import CrawlRequest
from domain.errors import MissingApiKeyError, MissingDetailFieldsError, MissingLinkCandidatesError
from interfaces.bootstrap.container import build_client_kwargs as build_shared_client_kwargs
from interfaces.bootstrap.container import build_container


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


def build_run_config(argv: Sequence[str] | None = None) -> CrawlRequest:
    args = parse_args(argv)
    return CrawlRequest(
        start_url=args.url,
        output_path=args.output,
        max_pages=args.max_pages,
        max_list_pages=args.max_list_pages,
        use_playwright=args.use_playwright,
        depth=args.depth,
    )


def build_client_kwargs() -> dict[str, str]:
    return build_shared_client_kwargs()


async def run(argv: Sequence[str] | None = None) -> None:
    request = build_run_config(argv)
    container = build_container()

    try:
        result = await container.crawl_website.execute(request)
    except MissingLinkCandidatesError:
        print("\nNo list-link XPath candidates found. Exiting.")
        sys.exit(1)
    except MissingDetailFieldsError:
        print("\nNo detail fields found. Exiting.")
        sys.exit(1)
    except MissingApiKeyError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    export_plan = getattr(result, "export_plan", None)
    if export_plan is None:
        return

    records = getattr(result, "records", [])
    container.output_writer.write(
        data=records,
        crawl_config=export_plan,
        source_url=request.start_url,
        output_path=request.output_path,
        detail_urls=getattr(result, "detail_urls", None) or None,
    )
    print(f"\nDone!  {len(records)} detail records  ->  {request.output_path}")


def main() -> None:
    asyncio.run(run())
