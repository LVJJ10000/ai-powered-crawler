from urllib.parse import urlparse

from ai.healer import FieldHealthTracker
from lxml import html as lhtml

from crawler.url_utils import normalize_url
from domain.analysis_entities import ExtractType
from infrastructure.html.extractor import HealingExtractionBatchProcessor


class ExtractionCoordinator:
    def __init__(self, batch_extractor=None, health_tracker_factory=None):
        self.batch_extractor = batch_extractor or HealingExtractionBatchProcessor()
        self.health_tracker_factory = health_tracker_factory or FieldHealthTracker
        self._health_trackers: dict[object, object] = {}
        self._tracked_fields: dict[object, tuple[str, ...]] = {}

    def extract_batch(
        self,
        batch,
        crawl_plan,
        session_key=None,
        client=None,
        label: str = "",
    ):
        health_tracker = self._ensure_health_tracker(crawl_plan, session_key=session_key)
        return self.batch_extractor.extract_batch(
            batch=batch,
            crawl_plan=crawl_plan,
            health_tracker=health_tracker,
            client=client,
            label=label,
        )

    def discover_child_urls(
        self,
        record,
        crawl_plan,
        page_html: str,
        page_url: str,
        remaining_pages: int,
    ) -> list[str]:
        if crawl_plan is None:
            return []

        page_data = getattr(record, "data", record) or {}
        source_url = page_url or getattr(record, "url", "")
        urls: list[str] = []
        seen: set[str] = set()

        for field in crawl_plan.fields:
            if field.extract == ExtractType.ATTRIBUTE and field.attribute_name == "href":
                normalized = normalize_url(page_data.get(field.name), source_url)
                if normalized and normalized not in seen and normalized != source_url:
                    seen.add(normalized)
                    urls.append(normalized)

        if not page_html:
            return urls[:remaining_pages]

        parsed = urlparse(source_url)
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            return urls[:remaining_pages]

        prefix = "/".join(path_parts[:-1])
        try:
            tree = lhtml.fromstring(page_html)
            tree.make_links_absolute(source_url)
            for anchor in tree.xpath("//a[@href]"):
                normalized = normalize_url(anchor.get("href", "").strip(), source_url)
                if not normalized:
                    continue

                href_parts = urlparse(normalized)
                sibling_parts = href_parts.path.strip("/").split("/")
                if href_parts.netloc != parsed.netloc or len(sibling_parts) < 2:
                    continue
                if "/".join(sibling_parts[:-1]) != prefix or normalized == source_url:
                    continue
                if normalized in seen:
                    continue

                seen.add(normalized)
                urls.append(normalized)
        except Exception:
            pass

        return urls[:remaining_pages]

    def _ensure_health_tracker(self, crawl_plan, session_key=None):
        if crawl_plan is None:
            return None

        tracker_key = session_key if session_key is not None else id(crawl_plan)
        field_names = tuple(field.name for field in crawl_plan.fields)
        if (
            tracker_key not in self._health_trackers
            or self._tracked_fields.get(tracker_key) != field_names
        ):
            self._health_trackers[tracker_key] = self.health_tracker_factory(crawl_plan.fields)
            self._tracked_fields[tracker_key] = field_names
        return self._health_trackers[tracker_key]
