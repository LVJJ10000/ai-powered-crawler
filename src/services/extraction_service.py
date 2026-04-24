import logging
from urllib.parse import urlparse

from lxml import html as lhtml

import ai.healer as healer_module
from ai.healer import FieldHealthTracker
from crawler.extractor import extract_with_healing
from crawler.url_utils import normalize_url
from models.schemas import CrawlConfig, ExtractType, PageData
from preprocessing.annotator import annotate_html
from preprocessing.cleaner import clean_html

logger = logging.getLogger(__name__)


class ExtractionService:
    def extract_pages(
        self,
        batch: list[tuple[str, str]],
        crawl_config: CrawlConfig,
        client,
        label: str = "",
    ) -> tuple[list[PageData], CrawlConfig]:
        tracker = FieldHealthTracker(crawl_config.fields)
        results: list[PageData] = []

        for i, (url, page_html) in enumerate(batch, 1):
            try:
                cleaned = clean_html(page_html)
                annotated, tree = annotate_html(cleaned)
                data, crawl_config = extract_with_healing(
                    html_str=page_html,
                    url=url,
                    crawl_config=crawl_config,
                    health_tracker=tracker,
                    healer_module=healer_module,
                    annotated_html=annotated,
                    tree=tree,
                    client=client,
                )
                if isinstance(data, list):
                    for row in data:
                        results.append(PageData(url=url, data=row))
                else:
                    results.append(PageData(url=url, data=data))

                tag = f" ({label})" if label else ""
                if isinstance(data, list):
                    print(f"    [{i}/{len(batch)}]{tag} {url}  ->  {len(data)} items")
                else:
                    nn = sum(1 for v in data.values() if v)
                    print(f"    [{i}/{len(batch)}]{tag} {url}  ->  {nn}/{len(data)} fields")
            except Exception as exc:
                logger.error(f"Error processing {url}: {exc}")
                print(f"    [{i}/{len(batch)}] {url}  ->  ERROR: {exc}")

        return results, crawl_config

    def collect_sub_detail_urls(
        self,
        page_data: dict,
        detail_config: CrawlConfig,
        page_html: str,
        page_url: str,
        max_pages: int,
    ) -> list[str]:
        urls: list[str] = []
        seen: set[str] = set()

        for field in detail_config.fields:
            if field.extract == ExtractType.ATTRIBUTE and field.attribute_name == "href":
                normalized = normalize_url(page_data.get(field.name), page_url)
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    urls.append(normalized)

        parsed = urlparse(page_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            prefix = "/".join(path_parts[:-1])
            try:
                tree = lhtml.fromstring(page_html)
                tree.make_links_absolute(page_url)
                for a in tree.xpath("//a[@href]"):
                    normalized = normalize_url(a.get("href", "").strip(), page_url)
                    if not normalized:
                        continue
                    hp = urlparse(normalized)
                    hp_parts = hp.path.strip("/").split("/")
                    if hp.netloc == parsed.netloc and len(hp_parts) >= 2 and "/".join(hp_parts[:-1]) == prefix:
                        if normalized not in seen and normalized != page_url:
                            seen.add(normalized)
                            urls.append(normalized)
            except Exception:
                pass

        return urls[:max_pages]

