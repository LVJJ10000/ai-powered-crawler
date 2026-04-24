"""
Prompt A: Page Analysis and Field Detection.

The AI receives annotated HTML (with data-aid on every element) and
identifies all data fields worth extracting. It returns data-aid
values, NOT XPaths.
"""

import json
import logging
from openai import OpenAI
from models.schemas import (
    AnalysisResult,
    DetailFieldAnalysisResult,
    DetailLinkXPathCandidate,
    ExtractType,
    FieldInfo,
    ListFieldAnalysisResult,
    PageType,
    PageTypeDetectionResult,
    PaginationInfo,
    PaginationType,
)
import config

logger = logging.getLogger(__name__)

PROMPT_A_TEMPLATE = '''You are a web data analyst. The HTML below has a unique data-aid
attribute on every element.

Identify all meaningful data fields a user would want to extract
from this page.

Rules:
- Focus on main content area. Ignore navigation, footer, sidebar, ads, cookie banners.
- Determine if this is a "list" page (repeating items like search results,
  product listings, article feeds) or a "detail" page (single item with full info).
- For list pages: identify the repeating container element first (the element
  that wraps one complete item). Provide its data-aid.
- For each data field, return the data-aid of ONE example element containing it.
  Pick an element from the first item if it's a list page.
- Common fields to look for: title, price, description, image, link/URL, date,
  author, rating, category, ID, status, location, phone, email.
- Only include fields with actual data content, not decorative elements.
- For "attribute" extraction: specify which attribute (href, src, alt, datetime, etc.)
- If pagination exists, identify the "next page" link element.

Return valid JSON only, no markdown fences, no other text:
{{
  "page_type": "list",
  "container_aid": "eXX",
  "fields": [
    {{
      "name": "descriptive_field_name",
      "aid": "eXX",
      "extract": "text",
      "attribute_name": null,
      "description": "What this field contains"
    }},
    {{
      "name": "product_image",
      "aid": "eYY",
      "extract": "attribute",
      "attribute_name": "src",
      "description": "Product image URL"
    }}
  ],
  "pagination": {{
    "next_aid": "eZZ",
    "type": "link"
  }}
}}

For detail pages, set container_aid to null.
For pages without pagination, set pagination to null.

HTML:
{annotated_html}'''

PROMPT_PAGE_TYPE_TEMPLATE = '''You are a web page classifier.
The HTML below has data-aid on every element.

Classify page type:
- "list": repeating item cards/rows (feeds, search/product/news listings)
- "detail": one main record/article/product/profile page

Return valid JSON only:
{{
  "page_type": "list",
  "confidence": 0.0,
  "reason": "short reason"
}}

HTML:
{annotated_html}'''

PROMPT_LIST_FIELDS_TEMPLATE = '''You are a web data analyst for list pages.
The HTML below has data-aid on every element.

Goal: identify fields needed to discover detail pages.

Rules:
- Assume this is a LIST page.
- Return a repeating item container as container_aid when possible.
- Output XPath selectors that target detail-page links in the list content area.
- Avoid navigation/menu/footer/sidebar links.
- NEVER use @data-aid in XPath selectors. data-aid is synthetic and not present on real pages.
- Provide one best XPath and 1-3 fallback candidates.
- If pagination exists, include next_aid and type.

Return valid JSON only:
{{
  "page_type": "list",
  "container_aid": "e10",
  "primary_detail_link_xpath": "//div[@class='news']//a/@href",
  "detail_link_xpath_candidates": [
    {{
      "xpath": "//div[@class='news']//a/@href",
      "confidence": 0.9,
      "reason": "main article cards"
    }}
  ],
  "pagination": null
}}

HTML:
{annotated_html}'''

PROMPT_DETAIL_FIELDS_TEMPLATE = '''You are a web data analyst for detail pages.
The HTML below has data-aid on every element.

Goal: detect business data fields from this DETAIL page.

Rules:
- Assume this is a DETAIL page.
- Ignore navigation/menu/footer/sidebar/ads/recommendation lists.
- For each field, return one representative data-aid.
- Use extract="attribute" with attribute_name when needed.

Return valid JSON only:
{{
  "page_type": "detail",
  "fields": [
    {{
      "name": "title",
      "aid": "e10",
      "extract": "text",
      "attribute_name": null,
      "description": "Primary title"
    }}
  ]
}}

HTML:
{annotated_html}'''


PAGINATION_TYPE_ALIASES = {
    "button": PaginationType.LOAD_MORE,
    "loadmore": PaginationType.LOAD_MORE,
    "next_button": PaginationType.LOAD_MORE,
    "next-link": PaginationType.LINK,
    "next_link": PaginationType.LINK,
}


def detect_page_type(annotated_html: str, client: OpenAI) -> PageTypeDetectionResult:
    """Detect whether page is list/detail."""
    prompt = PROMPT_PAGE_TYPE_TEMPLATE.format(annotated_html=annotated_html)
    data = _chat_json(prompt, client, "PageType")
    return PageTypeDetectionResult(
        page_type=PageType(data["page_type"]),
        confidence=float(data.get("confidence", 0.0)),
        reason=data.get("reason"),
    )


def analyze_list_fields(annotated_html: str, client: OpenAI) -> ListFieldAnalysisResult:
    """Analyze list pages for detail URL discovery + optional secondary fields."""
    prompt = PROMPT_LIST_FIELDS_TEMPLATE.format(annotated_html=annotated_html)
    data = _chat_json(prompt, client, "ListFields")

    container_aid = data.get("container_aid")
    if container_aid and f'data-aid="{container_aid}"' not in annotated_html:
        logger.warning(f"List container aid {container_aid} not found in HTML")
        container_aid = None

    candidates: list[DetailLinkXPathCandidate] = []

    primary_xpath = str(data.get("primary_detail_link_xpath") or "").strip()
    if primary_xpath and _is_valid_link_xpath(primary_xpath):
        candidates.append(
            DetailLinkXPathCandidate(
                xpath=primary_xpath,
                confidence=float(data.get("primary_confidence", 0.8)),
                reason=data.get("primary_reason", "primary detail-link xpath"),
            )
        )

    for item in data.get("detail_link_xpath_candidates", []):
        xpath = str(item.get("xpath") or "").strip()
        if not xpath or not _is_valid_link_xpath(xpath):
            continue
        candidates.append(
            DetailLinkXPathCandidate(
                xpath=xpath,
                confidence=float(item.get("confidence", 0.5)),
                reason=item.get("reason"),
            )
        )

    # Dedupe by xpath while preserving order
    deduped: list[DetailLinkXPathCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.xpath in seen:
            continue
        seen.add(candidate.xpath)
        deduped.append(candidate)

    primary = deduped[0].xpath if deduped else None
    pagination = _parse_pagination(data.get("pagination"))

    return ListFieldAnalysisResult(
        page_type=PageType(data.get("page_type", "list")),
        container_aid=container_aid,
        primary_detail_link_xpath=primary,
        detail_link_xpath_candidates=deduped,
        pagination=pagination,
    )


def analyze_detail_fields(annotated_html: str, client: OpenAI) -> DetailFieldAnalysisResult:
    """Analyze detail page and detect business fields."""
    prompt = PROMPT_DETAIL_FIELDS_TEMPLATE.format(annotated_html=annotated_html)
    data = _chat_json(prompt, client, "DetailFields")
    fields = _parse_fields(data.get("fields", []), annotated_html)
    return DetailFieldAnalysisResult(
        page_type=PageType(data.get("page_type", "detail")),
        fields=fields,
    )


def analyze_page_v2(
    annotated_html: str,
    client: OpenAI,
    min_confidence: float = 0.65,
) -> tuple[PageTypeDetectionResult, ListFieldAnalysisResult | DetailFieldAnalysisResult]:
    """Run page-type job first, then route to list/detail field job."""
    page_detect = detect_page_type(annotated_html, client)
    if page_detect.confidence < min_confidence:
        retry = detect_page_type(annotated_html, client)
        if retry.confidence > page_detect.confidence:
            page_detect = retry

    if page_detect.confidence < min_confidence:
        logger.warning("Low page-type confidence (%.2f), fallback to legacy analyze_page", page_detect.confidence)
        legacy = analyze_page(annotated_html, client)
        return _legacy_to_v2(legacy)

    if page_detect.page_type == PageType.LIST:
        return page_detect, analyze_list_fields(annotated_html, client)
    return page_detect, analyze_detail_fields(annotated_html, client)


def analyze_page(annotated_html: str, client: OpenAI) -> AnalysisResult:
    """Analyze page HTML and detect fields using AI."""
    prompt = _build_prompt_a(annotated_html)

    data = _chat_json(prompt, client, "Prompt A")

    # Parse fields
    fields = _parse_fields(data.get("fields", []), annotated_html)

    # Parse pagination
    pagination = _parse_pagination(data.get("pagination"))

    # Validate container_aid
    container_aid = data.get("container_aid")
    if container_aid and f'data-aid="{container_aid}"' not in annotated_html:
        logger.warning(f"Container aid {container_aid} not found in HTML")
        container_aid = None

    result = AnalysisResult(
        page_type=PageType(data["page_type"]),
        container_aid=container_aid,
        fields=fields,
        pagination=pagination
    )

    logger.info(f"Prompt A result: {result.page_type}, {len(result.fields)} fields")
    return result


def _build_prompt_a(annotated_html: str) -> str:
    """Construct full prompt from template + HTML."""
    return PROMPT_A_TEMPLATE.format(annotated_html=annotated_html)


def _chat_json(prompt: str, client: OpenAI, label: str) -> dict:
    response = client.chat.completions.create(
        model=config.MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    content = (response.choices[0].message.content or "").strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
    logger.info(f"{label} raw response: {content[:500]}")
    return json.loads(content)


def _parse_fields(field_data: list[dict], annotated_html: str) -> list[FieldInfo]:
    fields = []
    for f in field_data:
        try:
            aid = f["aid"]
            if f'data-aid="{aid}"' not in annotated_html:
                logger.warning(f"Field {f.get('name', 'unknown')} references non-existent aid {aid}, skipping")
                continue
            fields.append(
                FieldInfo(
                    name=f["name"],
                    aid=aid,
                    extract=ExtractType(f["extract"]),
                    attribute_name=f.get("attribute_name"),
                    description=f["description"],
                )
            )
        except Exception as e:
            logger.warning(f"Invalid field payload {f}: {e}")
    return fields


def _parse_pagination(pag_data: dict | None) -> PaginationInfo | None:
    if pag_data and pag_data.get("next_aid"):
        return PaginationInfo(
            next_aid=pag_data.get("next_aid"),
            type=_parse_pagination_type(pag_data.get("type")),
        )
    return None


def _legacy_to_v2(
    legacy: AnalysisResult,
) -> tuple[PageTypeDetectionResult, ListFieldAnalysisResult | DetailFieldAnalysisResult]:
    page_result = PageTypeDetectionResult(
        page_type=legacy.page_type,
        confidence=0.0,
        reason="fallback_legacy_prompt_a",
    )
    if legacy.page_type == PageType.LIST:
        detail_link_candidates = [
            DetailLinkXPathCandidate(
                xpath="//a/@href",
                confidence=0.5,
                reason=f"description:{f.description}",
            )
            for f in legacy.fields
            if f.extract == ExtractType.ATTRIBUTE and (f.attribute_name or "").lower() == "href"
        ]
        list_result = ListFieldAnalysisResult(
            page_type=legacy.page_type,
            container_aid=legacy.container_aid,
            primary_detail_link_xpath=detail_link_candidates[0].xpath if detail_link_candidates else None,
            detail_link_xpath_candidates=detail_link_candidates,
            pagination=legacy.pagination,
        )
        return page_result, list_result

    detail_result = DetailFieldAnalysisResult(
        page_type=legacy.page_type,
        fields=legacy.fields,
    )
    return page_result, detail_result


def _parse_pagination_type(raw_type: str | None) -> PaginationType | None:
    """Parse pagination type from model output with tolerant alias handling."""
    if not raw_type:
        return None

    normalized = str(raw_type).strip().lower()
    if normalized in PAGINATION_TYPE_ALIASES:
        return PAGINATION_TYPE_ALIASES[normalized]

    try:
        return PaginationType(normalized)
    except ValueError:
        logger.warning(f"Unknown pagination type from Prompt A: {raw_type!r}, ignoring")
        return None


def _is_valid_link_xpath(xpath: str) -> bool:
    """Basic safety filter for AI-provided detail-link XPaths."""
    lowered = xpath.lower()
    if "data-aid" in lowered:
        return False
    return True
