import logging
from dataclasses import dataclass, field

from preprocessing.cleaner import clean_html
from preprocessing.annotator import annotate_html, resolve_aid, get_sibling_elements
from preprocessing.classifier import classify_element
from ai.analyzer import analyze_page_v2
from ai.xpath_gen import generate_xpath
from models.schemas import (
    CrawlConfig,
    DetailFieldAnalysisResult,
    ExtractType,
    FieldInfo,
    FieldXPath,
    ListFieldAnalysisResult,
)
from domain.models import XPathCandidate

logger = logging.getLogger(__name__)


@dataclass
class AnalysisBuildResult:
    crawl_config: CrawlConfig
    link_xpath_candidates: list[XPathCandidate] = field(default_factory=list)


class PageAnalysisService:
    def __init__(self, client):
        self.client = client

    def analyze(self, raw_html: str, label: str = "page") -> AnalysisBuildResult:
        cleaned = clean_html(raw_html)
        annotated, tree = annotate_html(cleaned)

        print(f"  AI analyzing {label} structure...")
        page_result, analysis = analyze_page_v2(annotated, self.client)
        print(f"  Detected page type: {page_result.page_type.value} (confidence: {page_result.confidence:.2f})")

        if isinstance(analysis, ListFieldAnalysisResult):
            pagination = analysis.pagination
            link_candidates = [
                XPathCandidate(xpath=c.xpath, confidence=c.confidence, reason=c.reason or "")
                for c in analysis.detail_link_xpath_candidates
                if c.xpath
            ]
            pagination_xpath = self._build_pagination_xpath(tree, pagination.next_aid if pagination else None)
            crawl_config = CrawlConfig(
                page_type=analysis.page_type,
                container_xpath=None,
                fields=[],
                pagination_xpath=pagination_xpath,
                pagination_type=pagination.type if pagination else None,
            )
            print(f"  Link XPath candidates: {len(link_candidates)}")
            for idx, candidate in enumerate(link_candidates, 1):
                print(f"    [{idx}] {candidate.xpath} (confidence: {candidate.confidence:.2f})")
            return AnalysisBuildResult(crawl_config=crawl_config, link_xpath_candidates=link_candidates)

        detail_analysis: DetailFieldAnalysisResult = analysis
        fields = self._build_detail_field_xpaths(detail_analysis.fields, tree)
        crawl_config = CrawlConfig(
            page_type=detail_analysis.page_type,
            container_xpath=None,
            fields=fields,
            pagination_xpath=None,
            pagination_type=None,
        )
        print(f"  Found {len(fields)} fields: {', '.join(f.name for f in fields)}")
        return AnalysisBuildResult(crawl_config=crawl_config, link_xpath_candidates=[])

    def _build_pagination_xpath(self, tree, next_aid: str | None) -> str | None:
        if not next_aid:
            return None
        pag_el = resolve_aid(tree, next_aid)
        if pag_el is None:
            return None
        pag_fi = FieldInfo(
            name="pagination_next",
            aid=next_aid,
            extract=ExtractType.ATTRIBUTE,
            attribute_name="href",
            description="Next page link",
        )
        classified_pag = classify_element(pag_el, [], tree)
        pag_result = generate_xpath(pag_el, classified_pag, pag_fi, tree, client=self.client)
        print(f"    Pagination: {pag_result.xpath}")
        return pag_result.xpath

    def _build_detail_field_xpaths(self, fields_info: list[FieldInfo], tree) -> list[FieldXPath]:
        fields: list[FieldXPath] = []
        for fi in fields_info:
            element = resolve_aid(tree, fi.aid)
            if element is None:
                logger.warning(f"Could not resolve aid {fi.aid} for field {fi.name}")
                continue

            siblings = get_sibling_elements(element, None)
            classified = classify_element(element, siblings, tree)
            xpath_result = generate_xpath(
                element,
                classified,
                fi,
                tree,
                container_element=None,
                container_xpath=None,
                client=self.client,
            )
            fields.append(
                FieldXPath(
                    name=fi.name,
                    description=fi.description,
                    xpath=xpath_result.xpath,
                    fallback_xpath=xpath_result.fallback_xpath,
                    confidence=xpath_result.confidence,
                    extract=fi.extract,
                    attribute_name=fi.attribute_name,
                )
            )
            print(f"    {fi.name}: {xpath_result.xpath} (confidence: {xpath_result.confidence:.2f})")
        return fields
