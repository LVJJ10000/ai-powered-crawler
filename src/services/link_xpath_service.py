from urllib.parse import urlparse

from lxml import html as lhtml

from crawler.url_utils import normalize_url
from domain.models import SelectedLinksResult, XPathCandidate, XPathCandidateEvaluation
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
        candidates: list[XPathCandidate],
        list_pages: list[tuple[str, str]],
        max_pages: int,
    ) -> SelectedLinksResult:
        evaluations: list[XPathCandidateEvaluation] = []
        for candidate in candidates:
            raw_urls: list[str] = []
            total_matches = 0
            for page_url, page_html in list_pages:
                urls = self.extract_links(page_html, page_url, candidate.xpath)
                raw_urls.extend(urls)
                total_matches += len(urls)

            deduped_urls = list(dict.fromkeys(raw_urls))
            filtered_urls = [url for url in deduped_urls if self._is_basic_valid(url)]
            valid_ratio = len(filtered_urls) / max(1, total_matches)

            model = self.pattern_learner.learn(filtered_urls)
            pattern_coverage, top_support = self.pattern_learner.evaluate(filtered_urls, model)
            score = (
                valid_ratio * 0.30
                + pattern_coverage * 0.40
                + top_support * 0.15
                + min(1.0, len(filtered_urls) / max(1, max_pages)) * 0.15
            )

            evaluations.append(
                XPathCandidateEvaluation(
                    candidate=candidate,
                    urls=filtered_urls,
                    basic_valid_ratio=valid_ratio,
                    pattern_coverage=pattern_coverage,
                    top_pattern_support=top_support,
                    score=score,
                )
            )

        if not evaluations:
            return SelectedLinksResult(selected_urls=[], selected_xpaths=[], evaluations=[])

        evaluations.sort(key=lambda item: item.score, reverse=True)
        best = evaluations[0]
        selected_urls = list(best.urls)
        selected_xpaths = [best.candidate.xpath]

        if len(evaluations) > 1 and evaluations[0].score - evaluations[1].score <= 0.1:
            selected_urls = list(dict.fromkeys(best.urls + evaluations[1].urls))
            selected_xpaths.append(evaluations[1].candidate.xpath)

        return SelectedLinksResult(
            selected_urls=selected_urls[:max_pages],
            selected_xpaths=selected_xpaths,
            evaluations=evaluations,
        )

    def _is_basic_valid(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in (".pdf", ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx")):
            return False
        return True

