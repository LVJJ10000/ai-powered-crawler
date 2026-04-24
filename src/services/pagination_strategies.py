import re
from abc import ABC, abstractmethod
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from lxml import html as lhtml

from crawler.url_utils import normalize_url
from domain.pagination_models import PaginationMode, StrategyResult


class PaginationContext:
    def __init__(self, pagination_xpath: str | None, pagination_type):
        self.pagination_xpath = pagination_xpath
        self.pagination_type = pagination_type


class BasePaginationStrategy(ABC):
    mode: PaginationMode

    @abstractmethod
    def find_next_url(
        self,
        page_url: str,
        page_html: str,
        context: PaginationContext,
        visited: set[str],
    ) -> StrategyResult:
        raise NotImplementedError

    @staticmethod
    def _first_unvisited(urls: list[str], visited: set[str]) -> str | None:
        for url in urls:
            if url and url not in visited:
                return url
        return None


class LinkNextStrategy(BasePaginationStrategy):
    mode = PaginationMode.LINK

    def find_next_url(self, page_url, page_html, context, visited) -> StrategyResult:
        tree = lhtml.fromstring(page_html)
        tree.make_links_absolute(page_url)
        candidates: list[str] = []

        if context.pagination_xpath:
            try:
                if context.pagination_xpath.endswith("/@href"):
                    values = tree.xpath(context.pagination_xpath)
                    candidates.extend(
                        [normalize_url(v if isinstance(v, str) else str(v), page_url) for v in values]
                    )
                else:
                    base = context.pagination_xpath.split("/text()")[0]
                    elements = tree.xpath(base)
                    for element in elements:
                        href = element.get("href") if hasattr(element, "get") else None
                        candidates.append(normalize_url(href, page_url))
            except Exception:
                pass

        if not candidates:
            values = tree.xpath("//a[contains(@class,'next') or contains(normalize-space(text()),'下一页')]/@href")
            candidates.extend([normalize_url(v, page_url) for v in values])

        clean_candidates = [c for c in candidates if c]
        next_url = self._first_unvisited(clean_candidates, visited)
        return StrategyResult(
            strategy=self.mode,
            advanced=bool(next_url),
            next_url=next_url,
            reason="next link resolved" if next_url else "no unvisited link candidate",
            candidate_count=len(clean_candidates),
        )


class ClickNextStrategy(BasePaginationStrategy):
    mode = PaginationMode.CLICK

    def find_next_url(self, page_url, page_html, context, visited) -> StrategyResult:
        tree = lhtml.fromstring(page_html)
        tree.make_links_absolute(page_url)
        xpaths = [
            "//a[contains(normalize-space(text()),'下一页')]/@href",
            "//a[contains(@class,'next')]/@href",
            "//button[contains(normalize-space(text()),'下一页')]/@data-url",
            "//button[contains(@class,'next')]/@data-url",
        ]
        candidates: list[str] = []
        for xpath in xpaths:
            try:
                values = tree.xpath(xpath)
            except Exception:
                values = []
            for value in values:
                candidates.append(normalize_url(str(value), page_url))
        clean_candidates = [c for c in candidates if c]
        next_url = self._first_unvisited(clean_candidates, visited)
        return StrategyResult(
            strategy=self.mode,
            advanced=bool(next_url),
            next_url=next_url,
            reason="click-style next resolved" if next_url else "no clickable next target",
            candidate_count=len(clean_candidates),
        )


class LoadMoreStrategy(BasePaginationStrategy):
    mode = PaginationMode.LOAD_MORE

    def find_next_url(self, page_url, page_html, context, visited) -> StrategyResult:
        tree = lhtml.fromstring(page_html)
        tree.make_links_absolute(page_url)
        xpaths = [
            "//a[contains(normalize-space(text()),'加载更多')]/@href",
            "//button[contains(normalize-space(text()),'加载更多')]/@data-url",
            "//a[contains(@class,'load_more')]/@href",
            "//button[contains(@class,'load_more')]/@data-url",
        ]
        candidates: list[str] = []
        for xpath in xpaths:
            try:
                values = tree.xpath(xpath)
            except Exception:
                values = []
            for value in values:
                candidates.append(normalize_url(str(value), page_url))
        clean_candidates = [c for c in candidates if c]
        next_url = self._first_unvisited(clean_candidates, visited)
        return StrategyResult(
            strategy=self.mode,
            advanced=bool(next_url),
            next_url=next_url,
            reason="load-more url resolved" if next_url else "no load-more target",
            candidate_count=len(clean_candidates),
        )


class InfiniteScrollStrategy(BasePaginationStrategy):
    mode = PaginationMode.INFINITE_SCROLL

    def find_next_url(self, page_url, page_html, context, visited) -> StrategyResult:
        parsed = urlparse(page_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        keys = ["page", "page_num", "pn", "offset", "start"]

        candidate_urls: list[str] = []
        for key in keys:
            if key in query and re.fullmatch(r"\d+", query[key] or ""):
                current = int(query[key])
                query_copy = dict(query)
                query_copy[key] = str(current + 1)
                new_query = urlencode(query_copy, doseq=True)
                candidate_urls.append(urlunparse(parsed._replace(query=new_query)))

        if not candidate_urls:
            candidate_urls.append(page_url + ("&" if parsed.query else "?") + "page=2")

        normalized = [normalize_url(url, page_url) for url in candidate_urls]
        clean_candidates = [c for c in normalized if c]
        next_url = self._first_unvisited(clean_candidates, visited)
        return StrategyResult(
            strategy=self.mode,
            advanced=bool(next_url),
            next_url=next_url,
            reason="scroll heuristic url generated" if next_url else "no infinite-scroll heuristic target",
            candidate_count=len(clean_candidates),
        )

