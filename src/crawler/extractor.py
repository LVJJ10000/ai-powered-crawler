"""
XPath Data Extractor - applies XPath configs to extract data from pages.
"""

import logging
import re
from lxml import html, etree
from models.schemas import CrawlConfig, FieldXPath, ExtractType, PageType
from ai.healer import FieldHealthTracker

logger = logging.getLogger(__name__)


def extract_data(html_str: str, config: CrawlConfig) -> list[dict] | dict:
    """Core extraction (no healing logic)."""
    tree = html.fromstring(html_str)

    if config.page_type == PageType.LIST:
        if not config.container_xpath:
            logger.warning("List page but no container XPath")
            return []

        containers = tree.xpath(config.container_xpath)
        if not containers:
            logger.warning(f"Container XPath matched 0 elements: {config.container_xpath}")
            return []

        results = []
        for container in containers:
            row = {}
            for field in config.fields:
                value = _extract_field(container, field)
                row[field.name] = value
            results.append(row)
        return results

    else:  # detail page
        result = {}
        for field in config.fields:
            value = _extract_field(tree, field)
            result[field.name] = value
        return result


def _extract_field(context, field: FieldXPath) -> str | None:
    """Extract a single field from context element."""
    try:
        results = context.xpath(field.xpath)
        value = _extract_value(results, field)
        if value:
            return _maybe_expand_text_from_parent(context, field.xpath, field, value)
        # If /text() returned empty, try getting full text_content from the element
        if field.extract == ExtractType.TEXT and field.xpath.endswith("/text()"):
            element_xpath = field.xpath[:-len("/text()")]
            elements = context.xpath(element_xpath)
            if elements and hasattr(elements[0], 'text_content'):
                text = _normalize_text(elements[0].text_content())
                if text:
                    return text
            if _is_long_text_field(field):
                broader_text = _extract_broader_container_text(context, element_xpath)
                if broader_text:
                    return broader_text
    except Exception as e:
        logger.debug(f"XPath failed for {field.name}: {field.xpath} - {e}")

    # Try fallback
    if field.fallback_xpath:
        try:
            results = context.xpath(field.fallback_xpath)
            value = _extract_value(results, field)
            if value:
                return _maybe_expand_text_from_parent(context, field.fallback_xpath, field, value)
            if field.extract == ExtractType.TEXT and field.fallback_xpath.endswith("/text()"):
                element_xpath = field.fallback_xpath[:-len("/text()")]
                elements = context.xpath(element_xpath)
                if elements and hasattr(elements[0], 'text_content'):
                    text = _normalize_text(elements[0].text_content())
                    if text:
                        return text
                if _is_long_text_field(field):
                    broader_text = _extract_broader_container_text(context, element_xpath)
                    if broader_text:
                        return broader_text
        except Exception as e:
            logger.debug(f"Fallback XPath failed for {field.name}: {field.fallback_xpath} - {e}")

    return None


def _extract_value(xpath_result, field: FieldXPath) -> str | None:
    """Process raw XPath result."""
    if not xpath_result:
        return None

    if isinstance(xpath_result, list):
        if field.extract == ExtractType.TEXT and _is_long_text_field(field) and len(xpath_result) > 1:
            merged = _merge_text_nodes(xpath_result)
            if merged:
                return merged
        result = xpath_result[0]
    else:
        result = xpath_result

    if hasattr(result, 'text_content'):
        # It's an lxml element
        text = _normalize_text(result.text_content())
        return text if text else None
    elif isinstance(result, str):
        # From /text() or /@attr
        text = _normalize_text(result)
        return text if text else None
    else:
        text = _normalize_text(str(result))
        return text if text else None


def _is_long_text_field(field: FieldXPath) -> bool:
    """Heuristic: fields likely representing article/body content."""
    text = f"{field.name} {field.description}".lower()
    keywords = ("content", "article", "body", "正文", "内容")
    return any(keyword in text for keyword in keywords)


def _normalize_text(text: str) -> str:
    """Collapse excessive whitespace while preserving readable sentences."""
    return re.sub(r"\s+", " ", text).strip()


def _merge_text_nodes(nodes) -> str | None:
    """Merge multiple XPath text-node matches into one coherent value."""
    parts: list[str] = []
    for node in nodes:
        if hasattr(node, 'text_content'):
            text = _normalize_text(node.text_content())
        else:
            text = _normalize_text(str(node))

        if not text:
            continue
        if parts and text == parts[-1]:
            continue
        parts.append(text)

    if not parts:
        return None

    return "\n".join(parts)


def _maybe_expand_text_from_parent(context, xpath: str, field: FieldXPath, current_value: str) -> str:
    """For long-text fields extracted via /text(), prefer richer parent text when clearly better."""
    if not current_value:
        return current_value
    if field.extract != ExtractType.TEXT or not _is_long_text_field(field):
        return current_value
    if not xpath.endswith("/text()"):
        return current_value

    element_xpath = xpath[:-len("/text()")]
    try:
        elements = context.xpath(element_xpath)
    except Exception:
        return current_value

    if not elements or not hasattr(elements[0], 'text_content'):
        broader_text = _extract_broader_container_text(context, element_xpath)
        return broader_text if broader_text else current_value

    full_text = _normalize_text(elements[0].text_content())
    if not full_text:
        broader_text = _extract_broader_container_text(context, element_xpath)
        return broader_text if broader_text else current_value

    # If extracted text is boilerplate/noise, prefer richer parent text when available.
    if _is_low_quality_content(current_value) and len(full_text) > len(current_value):
        return full_text

    # Prefer parent/container text if it's significantly richer.
    if len(full_text) >= max(120, len(current_value) * 2):
        return full_text
    broader_text = _extract_broader_container_text(context, element_xpath)
    if broader_text and len(broader_text) >= max(120, len(current_value) * 2):
        return broader_text
    return current_value


def _is_low_quality_content(text: str) -> bool:
    """Detect obvious non-article boilerplate content snippets."""
    t = text.strip().lower()
    if not t:
        return True
    patterns = (
        "未经许可",
        "请勿转载",
        "版权所有",
        "copyright",
        "all rights reserved",
    )
    return any(p in t for p in patterns)


def _extract_broader_container_text(context, element_xpath: str) -> str | None:
    """Try broader parent paths for long text when the leaf selector is too narrow."""
    path = element_xpath
    for _ in range(3):
        if "/" not in path:
            break
        path = path.rsplit("/", 1)[0]
        if not path:
            break
        try:
            elements = context.xpath(path)
        except Exception:
            continue
        if not elements or not hasattr(elements[0], "text_content"):
            continue
        text = _normalize_text(elements[0].text_content())
        if text and len(text) >= 80:
            return text
    return None


def extract_with_healing(
    html_str: str,
    url: str,
    crawl_config: CrawlConfig,
    health_tracker: FieldHealthTracker,
    healer_module,
    annotated_html: str | None,
    tree,
    client
) -> tuple[list[dict] | dict, CrawlConfig]:
    """Extraction with health tracking and self-healing."""
    # 1. Extract data
    data = extract_data(html_str, crawl_config)

    # 2. Record health
    if isinstance(data, list):
        # For list pages, record from first item
        if data:
            for field in crawl_config.fields:
                value = data[0].get(field.name)
                health_tracker.record(field.name, value)
        else:
            for field in crawl_config.fields:
                health_tracker.record(field.name, None)
    else:
        for field in crawl_config.fields:
            value = data.get(field.name)
            health_tracker.record(field.name, value)

    # 3. Check cascade failure
    if health_tracker.check_cascade():
        logger.warning("Cascade failure detected on page: %s", url)
        if annotated_html and client:
            try:
                new_config = _full_reanalyze(html_str, client)
                if new_config:
                    # Only replace the global config if the page type matches
                    # (different page types shouldn't overwrite the original config)
                    if new_config.page_type == crawl_config.page_type and new_config.fields:
                        data = extract_data(html_str, new_config)
                        return data, new_config
                    else:
                        # Different page type - extract with new config but keep old config
                        logger.info("Page %s has different type (%s), skipping config update",
                                    url, new_config.page_type.value)
                        data = extract_data(html_str, new_config)
                        return data, crawl_config
            except Exception as e:
                logger.error(f"Full re-analysis failed: {e}")

    # 4. Heal individual fields
    if annotated_html and client:
        config_changed = False
        for i, field in enumerate(crawl_config.fields):
            if health_tracker.needs_healing(field.name):
                if not health_tracker.can_heal(field.name):
                    logger.warning(f"Field {field.name} permanently broken (max heal attempts)")
                    continue

                logger.info(f"Healing field: {field.name}")
                container_element = None
                if crawl_config.container_xpath and tree is not None:
                    try:
                        containers = tree.xpath(crawl_config.container_xpath)
                        if containers:
                            container_element = containers[0]
                    except Exception:
                        pass

                from preprocessing.classifier import classify_element
                new_field = healer_module.perform_healing(
                    field=field,
                    health_tracker=health_tracker,
                    tree=tree,
                    annotated_html=annotated_html,
                    container_element=container_element,
                    container_xpath=crawl_config.container_xpath or "",
                    client=client,
                    classified_element_fn=classify_element
                )

                if new_field:
                    crawl_config.fields[i] = new_field
                    config_changed = True
                    logger.info(f"Healed field {field.name}: {new_field.xpath}")

        if config_changed:
            data = extract_data(html_str, crawl_config)

    return data, crawl_config


def _full_reanalyze(html_str: str, client) -> CrawlConfig | None:
    """Re-run the full analysis pipeline."""
    from preprocessing.cleaner import clean_html
    from preprocessing.annotator import annotate_html, resolve_aid, get_sibling_elements
    from preprocessing.classifier import classify_element
    from ai.analyzer import analyze_page_v2
    from ai.xpath_gen import generate_xpath, generate_container_xpath

    cleaned = clean_html(html_str)
    annotated, tree = annotate_html(cleaned)
    _, analysis = analyze_page_v2(annotated, client)

    if hasattr(analysis, "fields"):
        analysis_fields = analysis.fields
        analysis_container_aid = None
        analysis_page_type = analysis.page_type
    else:
        analysis_fields = []
        analysis_container_aid = getattr(analysis, "container_aid", None)
        analysis_page_type = analysis.page_type

    container_xpath = None
    container_element = None

    if analysis_container_aid:
        container_element = resolve_aid(tree, analysis_container_aid)
        if container_element is not None:
            siblings = get_sibling_elements(container_element, container_element)
            classified_container = classify_element(container_element, siblings, tree)
            container_xpath = generate_container_xpath(container_element, classified_container, tree, client)

    fields = []
    for fi in analysis_fields:
        element = resolve_aid(tree, fi.aid)
        if element is None:
            continue
        siblings = get_sibling_elements(element, container_element) if container_element is not None else []
        classified = classify_element(element, siblings, tree)
        xpath_result = generate_xpath(element, classified, fi, tree, container_element, container_xpath, client)

        from models.schemas import FieldXPath
        fields.append(FieldXPath(
            name=fi.name,
            description=fi.description,
            xpath=xpath_result.xpath,
            fallback_xpath=xpath_result.fallback_xpath,
            confidence=xpath_result.confidence,
            extract=fi.extract,
            attribute_name=fi.attribute_name
        ))

    from models.schemas import CrawlConfig as CC
    return CC(
        page_type=analysis_page_type,
        container_xpath=container_xpath,
        fields=fields
    )
