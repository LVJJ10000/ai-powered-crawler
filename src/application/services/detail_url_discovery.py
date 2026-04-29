from urllib.parse import urlparse

from domain.models import SelectedLinksResult, XPathCandidateEvaluation


class DetailUrlDiscovery:
    def __init__(self, link_extractor, pattern_learner):
        self.link_extractor = link_extractor
        self.pattern_learner = pattern_learner

    def select(self, candidates, list_pages, max_pages):
        evaluations: list[XPathCandidateEvaluation] = []
        for candidate in candidates:
            raw_urls: list[str] = []
            total_matches = 0
            for page_url, page_html in list_pages:
                urls = self.link_extractor.extract_links(page_html, page_url, candidate.xpath)
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

    @staticmethod
    def _is_basic_valid(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False
        path = parsed.path.lower()
        if any(
            path.endswith(ext)
            for ext in (".pdf", ".zip", ".rar", ".7z", ".doc", ".docx", ".xls", ".xlsx")
        ):
            return False
        return True
