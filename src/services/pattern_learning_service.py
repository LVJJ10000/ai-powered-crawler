import math
import re
from collections import Counter
from urllib.parse import urlparse

from domain.models import PatternModel


class PatternLearningService:
    NAV_KEYWORDS = ("about", "contact", "privacy", "terms", "category", "tag", "help", "login", "signup")
    STRONG_DETAIL_HINTS = ("article", "detail", "post")

    def learn(self, urls: list[str]) -> PatternModel:
        segment_matrix: list[list[str]] = []
        for url in urls:
            parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
            segment_matrix.append(parts)

        max_len = max((len(parts) for parts in segment_matrix), default=0)
        schema: list[str] = []
        for idx in range(max_len):
            column = [parts[idx] for parts in segment_matrix if len(parts) > idx]
            schema.append(self._infer_segment(column))

        pattern_counts: dict[str, int] = {}
        for url in urls:
            pattern = self.build_pattern(url, schema)
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        return PatternModel(segment_schema=schema, pattern_counts=pattern_counts, total_urls=len(urls))

    def evaluate(self, urls: list[str], model: PatternModel) -> tuple[float, float]:
        if not urls:
            return 0.0, 0.0

        valid_count = 0
        top_support = 0
        for pattern, count in model.pattern_counts.items():
            if self._is_effective_pattern(pattern, count):
                valid_count += count
            top_support = max(top_support, count)

        coverage = valid_count / len(urls)
        top_ratio = top_support / len(urls)
        return coverage, top_ratio

    def build_pattern(self, url: str, schema: list[str]) -> str:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        normalized_parts: list[str] = []
        for idx, segment in enumerate(parts):
            slot = schema[idx] if idx < len(schema) else "{var}"
            if slot.startswith("{"):
                normalized_parts.append(self._normalize_segment(segment))
            else:
                normalized_parts.append(segment.lower())
        return f"{parsed.netloc.lower()}/" + "/".join(normalized_parts)

    def _infer_segment(self, segments: list[str]) -> str:
        if not segments:
            return "{var}"
        unique_ratio = len(set(segments)) / len(segments)
        entropy = self._entropy(segments)
        numeric_ratio = sum(1 for s in segments if s.isdigit()) / len(segments)
        date_ratio = sum(1 for s in segments if self._is_date_like(s)) / len(segments)
        token_ratio = sum(1 for s in segments if self._is_token_like(s)) / len(segments)

        if numeric_ratio >= 0.6:
            return "{id}"
        if date_ratio >= 0.5:
            return "{date}"
        if token_ratio >= 0.5:
            return "{token}"
        if unique_ratio > 0.6 or entropy > 1.2:
            return "{var}"
        return Counter(segments).most_common(1)[0][0].lower()

    def _normalize_segment(self, segment: str) -> str:
        if segment.isdigit():
            return "{id}"
        if self._is_date_like(segment):
            return "{date}"
        if self._is_token_like(segment):
            return "{token}"
        if len(segment) > 30:
            return "{var}"
        return segment.lower()

    def _is_effective_pattern(self, pattern: str, count: int) -> bool:
        p = pattern.lower()
        if any(keyword in p for keyword in self.NAV_KEYWORDS):
            return False
        if count >= 3:
            return True
        if count >= 2 and (any(h in p for h in self.STRONG_DETAIL_HINTS) or "/p/" in p or "{id}" in p):
            return True
        return False

    @staticmethod
    def _entropy(values: list[str]) -> float:
        counts = Counter(values)
        total = len(values)
        return -sum((count / total) * math.log2(count / total) for count in counts.values() if count > 0)

    @staticmethod
    def _is_date_like(segment: str) -> bool:
        return bool(
            re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", segment)
            or re.fullmatch(r"\d{8}", segment)
            or re.fullmatch(r"\d{4}", segment)
        )

    @staticmethod
    def _is_token_like(segment: str) -> bool:
        return bool(
            re.fullmatch(r"[0-9a-f]{8,}", segment.lower())
            or re.fullmatch(r"[0-9a-f-]{18,}", segment.lower())
            or re.fullmatch(r"[a-zA-Z0-9_-]{20,}", segment)
        )

