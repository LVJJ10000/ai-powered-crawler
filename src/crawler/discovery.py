"""
Sub-page Discovery - finds all pages sharing the same template.
"""

import asyncio
import logging
from urllib.parse import urlparse
from lxml import html, etree
from crawler.fetcher import PageFetcher
from crawler.url_utils import normalize_url, is_same_domain
import config

logger = logging.getLogger(__name__)


async def discover_pages(
    start_url: str,
    fetcher: PageFetcher,
    max_pages: int = None,
    max_depth: int = None
) -> list[str]:
    """Run both strategies, merge and deduplicate results."""
    if max_pages is None:
        max_pages = config.MAX_PAGES
    if max_depth is None:
        max_depth = config.MAX_DEPTH

    urls_a = await try_sitemap(start_url, fetcher)
    urls_b = await crawl_links(start_url, fetcher, max_depth, max_pages)

    all_urls = list(dict.fromkeys(urls_a + urls_b))  # deduplicate preserving order

    # Filter by URL pattern similarity
    pattern = detect_url_pattern(all_urls)
    if pattern:
        all_urls = filter_by_pattern(all_urls, pattern)

    # Ensure start_url is included
    if start_url not in all_urls:
        all_urls.insert(0, start_url)

    return all_urls[:max_pages]


async def try_sitemap(start_url: str, fetcher: PageFetcher) -> list[str]:
    """Try to find pages from sitemap.xml."""
    parsed = urlparse(start_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    sitemap_url = f"{base}/sitemap.xml"

    try:
        sitemap_xml = await fetcher.fetch(sitemap_url)
        urls = _parse_sitemap(sitemap_xml, base)

        # Filter to same domain/path
        start_path = parsed.path.rstrip("/")
        if start_path:
            urls = [u for u in urls if urlparse(u).path.startswith(start_path)]

        logger.info(f"Sitemap found {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.debug(f"No sitemap found: {e}")
        return []


def _parse_sitemap(xml_str: str, base_url: str) -> list[str]:
    """Parse sitemap XML for URLs."""
    urls = []
    try:
        # Remove namespace for easier parsing
        xml_str = xml_str.replace(' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', '')
        tree = etree.fromstring(xml_str.encode())

        # Check for sitemap index
        for sitemap in tree.findall('.//sitemap'):
            loc = sitemap.find('loc')
            if loc is not None and loc.text:
                # Would need to fetch child sitemaps too
                pass

        # Get regular URLs
        for url_el in tree.findall('.//url'):
            loc = url_el.find('loc')
            if loc is not None and loc.text:
                normalized = normalize_url(loc.text.strip(), base_url=base_url)
                if normalized:
                    urls.append(normalized)

    except Exception as e:
        logger.debug(f"Sitemap parse error: {e}")

    return urls


async def crawl_links(
    start_url: str,
    fetcher: PageFetcher,
    max_depth: int = 3,
    max_pages: int = 200
) -> list[str]:
    """BFS link crawler."""
    parsed = urlparse(start_url)
    base_domain = parsed.netloc.lower()
    base_path = parsed.path.rstrip("/")

    queue = [(start_url, 0)]
    visited = set()
    discovered = []

    while queue and len(visited) < max_pages:
        url, depth = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)
        discovered.append(url)

        if depth >= max_depth:
            continue

        try:
            page_html = await fetcher.fetch(url)
            tree = html.fromstring(page_html)
            tree.make_links_absolute(url)

            for link_el in tree.xpath("//a[@href]"):
                href = link_el.get("href", "").strip()
                normalized = normalize_url(href, base_url=url)
                if not normalized:
                    continue

                # Same domain required
                if not is_same_domain(normalized, base_domain):
                    continue

                if normalized not in visited and len(visited) + len(queue) < max_pages * 2:
                    queue.append((normalized, depth + 1))

        except Exception as e:
            logger.debug(f"Error crawling {url}: {e}")

    return discovered


def detect_url_pattern(urls: list[str]) -> str | None:
    """Analyze URLs to find common pattern."""
    if len(urls) < 3:
        return None

    paths = [urlparse(u).path for u in urls]
    segments_list = [p.strip("/").split("/") for p in paths if p.strip("/")]

    if not segments_list:
        return None

    # Find most common first segment
    first_segments = {}
    for segs in segments_list:
        if segs:
            key = segs[0]
            first_segments[key] = first_segments.get(key, 0) + 1

    if not first_segments:
        return None

    most_common = max(first_segments, key=first_segments.get)
    if first_segments[most_common] >= len(urls) * 0.3:
        return f"/{most_common}/*"

    return None


def filter_by_pattern(urls: list[str], pattern: str) -> list[str]:
    """Keep only URLs matching the detected pattern."""
    if not pattern or not pattern.endswith("/*"):
        return urls

    prefix = pattern[:-1]  # Remove *
    filtered = []
    for url in urls:
        path = urlparse(url).path
        if path.startswith(prefix) or path == prefix.rstrip("/"):
            filtered.append(url)

    # If filtering removed too many, return original
    if len(filtered) < len(urls) * 0.3:
        return urls

    return filtered
