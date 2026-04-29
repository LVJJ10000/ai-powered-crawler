from application.services.detail_url_discovery import DetailUrlDiscovery
from lxml import html as lhtml

from crawler.url_utils import normalize_url
from services.pattern_learning_service import PatternLearningService


class LinkXPathService:
    def __init__(self, pattern_learner: PatternLearningService):
        self.pattern_learner = pattern_learner

    def extract_links(self, page_html: str, page_url: str, xpath: str) -> list[str]:
        tree = lhtml.fromstring(page_html)
        tree.make_links_absolute(page_url)
        results = tree.xpath(xpath)
        urls: list[str] = []

        for item in results:
            if isinstance(item, str):
                normalized = normalize_url(item, page_url)
                if normalized:
                    urls.append(normalized)
                continue
            href = item.get("href") if hasattr(item, "get") else None
            normalized = normalize_url(href, page_url)
            if normalized:
                urls.append(normalized)
        return urls

    def evaluate_candidates(
        self,
        candidates,
        list_pages: list[tuple[str, str]],
        max_pages: int,
    ):
        return DetailUrlDiscovery(
            link_extractor=self,
            pattern_learner=self.pattern_learner,
        ).select(
            candidates=candidates,
            list_pages=list_pages,
            max_pages=max_pages,
        )
