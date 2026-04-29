"""
XPath extraction and healing helpers for HTML detail/list extraction.
"""

import logging

import ai.healer as healer_module
from ai.healer import FieldHealthTracker
from domain.analysis_entities import ExtractType, PageType
from infrastructure.html.annotator import annotate_html, get_sibling_elements, resolve_aid
from infrastructure.html.cleaner import clean_html
from infrastructure.html.text_policies import (
    extract_broader_container_text,
    is_long_text_field,
    is_low_quality_content,
    merge_text_nodes,
    normalize_text,
)
from lxml import html
from models.schemas import CrawlConfig, FieldXPath, PageData

logger = logging.getLogger(__name__)


class HealingExtractionBatchProcessor:
    def __init__(self, healer=healer_module):
        self.healer = healer

    def extract_batch(
        self,
        batch: list[tuple[str, str]],
        crawl_plan: CrawlConfig,
        health_tracker=None,
        client=None,
        label: str = "",
    ) -> tuple[list[PageData], CrawlConfig]:
        if crawl_plan is None:
            return [], crawl_plan

        tracker = health_tracker or FieldHealthTracker(crawl_plan.fields)
        results: list[PageData] = []

        for index, (url, page_html) in enumerate(batch, 1):
            try:
                cleaned = clean_html(page_html)
                annotated, tree = annotate_html(cleaned)
                data, crawl_plan = extract_with_healing(
                    html_str=page_html,
                    url=url,
                    crawl_config=crawl_plan,
                    health_tracker=tracker,
                    healer_module=self.healer,
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
                    print(f"    [{index}/{len(batch)}]{tag} {url}  ->  {len(data)} items")
                else:
                    populated = sum(1 for value in data.values() if value)
                    print(
                        f"    [{index}/{len(batch)}]{tag} {url}  ->  "
                        f"{populated}/{len(data)} fields"
                    )
            except Exception as exc:
                logger.error("Error processing %s: %s", url, exc)
                print(f"    [{index}/{len(batch)}] {url}  ->  ERROR: {exc}")

        return results, crawl_plan


def extract_data(html_str: str, config: CrawlConfig) -> list[dict] | dict:
    tree = html.fromstring(html_str)

    if config.page_type == PageType.LIST:
        if not config.container_xpath:
            logger.warning("List page but no container XPath")
            return []

        containers = tree.xpath(config.container_xpath)
        if not containers:
            logger.warning("Container XPath matched 0 elements: %s", config.container_xpath)
            return []

        results = []
        for container in containers:
            row = {}
            for field in config.fields:
                row[field.name] = _extract_field(container, field)
            results.append(row)
        return results

    result = {}
    for field in config.fields:
        result[field.name] = _extract_field(tree, field)
    return result


def _extract_field(context, field: FieldXPath) -> str | None:
    try:
        results = context.xpath(field.xpath)
        value = _extract_value(results, field)
        if value:
            return _maybe_expand_text_from_parent(context, field.xpath, field, value)
        if field.extract == ExtractType.TEXT and field.xpath.endswith("/text()"):
            element_xpath = field.xpath[: -len("/text()")]
            elements = context.xpath(element_xpath)
            if elements and hasattr(elements[0], "text_content"):
                text = normalize_text(elements[0].text_content())
                if text:
                    return text
            if is_long_text_field(field):
                broader_text = extract_broader_container_text(context, element_xpath)
                if broader_text:
                    return broader_text
    except Exception as exc:
        logger.debug("XPath failed for %s: %s - %s", field.name, field.xpath, exc)

    if field.fallback_xpath:
        try:
            results = context.xpath(field.fallback_xpath)
            value = _extract_value(results, field)
            if value:
                return _maybe_expand_text_from_parent(context, field.fallback_xpath, field, value)
            if field.extract == ExtractType.TEXT and field.fallback_xpath.endswith("/text()"):
                element_xpath = field.fallback_xpath[: -len("/text()")]
                elements = context.xpath(element_xpath)
                if elements and hasattr(elements[0], "text_content"):
                    text = normalize_text(elements[0].text_content())
                    if text:
                        return text
                if is_long_text_field(field):
                    broader_text = extract_broader_container_text(context, element_xpath)
                    if broader_text:
                        return broader_text
        except Exception as exc:
            logger.debug(
                "Fallback XPath failed for %s: %s - %s",
                field.name,
                field.fallback_xpath,
                exc,
            )

    return None


def _extract_value(xpath_result, field: FieldXPath) -> str | None:
    if not xpath_result:
        return None

    if isinstance(xpath_result, list):
        if field.extract == ExtractType.TEXT and is_long_text_field(field) and len(xpath_result) > 1:
            merged = merge_text_nodes(xpath_result)
            if merged:
                return merged
        result = xpath_result[0]
    else:
        result = xpath_result

    if hasattr(result, "text_content"):
        text = normalize_text(result.text_content())
        return text if text else None
    if isinstance(result, str):
        text = normalize_text(result)
        return text if text else None

    text = normalize_text(str(result))
    return text if text else None


def _maybe_expand_text_from_parent(context, xpath: str, field: FieldXPath, current_value: str) -> str:
    if not current_value:
        return current_value
    if field.extract != ExtractType.TEXT or not is_long_text_field(field):
        return current_value
    if not xpath.endswith("/text()"):
        return current_value

    element_xpath = xpath[: -len("/text()")]
    try:
        elements = context.xpath(element_xpath)
    except Exception:
        return current_value

    if not elements or not hasattr(elements[0], "text_content"):
        broader_text = extract_broader_container_text(context, element_xpath)
        return broader_text if broader_text else current_value

    full_text = normalize_text(elements[0].text_content())
    if not full_text:
        broader_text = extract_broader_container_text(context, element_xpath)
        return broader_text if broader_text else current_value

    if is_low_quality_content(current_value) and len(full_text) > len(current_value):
        return full_text
    if len(full_text) >= max(120, len(current_value) * 2):
        return full_text

    broader_text = extract_broader_container_text(context, element_xpath)
    if broader_text and len(broader_text) >= max(120, len(current_value) * 2):
        return broader_text
    return current_value


def extract_with_healing(
    html_str: str,
    url: str,
    crawl_config: CrawlConfig,
    health_tracker: FieldHealthTracker,
    healer_module,
    annotated_html: str | None,
    tree,
    client,
) -> tuple[list[dict] | dict, CrawlConfig]:
    data = extract_data(html_str, crawl_config)

    if isinstance(data, list):
        if data:
            for field in crawl_config.fields:
                health_tracker.record(field.name, data[0].get(field.name))
        else:
            for field in crawl_config.fields:
                health_tracker.record(field.name, None)
    else:
        for field in crawl_config.fields:
            health_tracker.record(field.name, data.get(field.name))

    if health_tracker.check_cascade():
        logger.warning("Cascade failure detected on page: %s", url)
        if annotated_html and client:
            try:
                new_config = _full_reanalyze(html_str, client)
                if new_config:
                    if new_config.page_type == crawl_config.page_type and new_config.fields:
                        data = extract_data(html_str, new_config)
                        return data, new_config

                    logger.info(
                        "Page %s has different type (%s), skipping config update",
                        url,
                        new_config.page_type.value,
                    )
                    data = extract_data(html_str, new_config)
                    return data, crawl_config
            except Exception as exc:
                logger.error("Full re-analysis failed: %s", exc)

    if annotated_html and client:
        from infrastructure.html.classifier import classify_element

        config_changed = False
        for index, field in enumerate(crawl_config.fields):
            if not health_tracker.needs_healing(field.name):
                continue
            if not health_tracker.can_heal(field.name):
                logger.warning("Field %s permanently broken (max heal attempts)", field.name)
                continue

            logger.info("Healing field: %s", field.name)
            container_element = None
            if crawl_config.container_xpath and tree is not None:
                try:
                    containers = tree.xpath(crawl_config.container_xpath)
                    if containers:
                        container_element = containers[0]
                except Exception:
                    container_element = None

            new_field = healer_module.perform_healing(
                field=field,
                health_tracker=health_tracker,
                tree=tree,
                annotated_html=annotated_html,
                container_element=container_element,
                container_xpath=crawl_config.container_xpath or "",
                client=client,
                classified_element_fn=classify_element,
            )

            if new_field:
                crawl_config.fields[index] = new_field
                config_changed = True
                logger.info("Healed field %s: %s", field.name, new_field.xpath)

        if config_changed:
            data = extract_data(html_str, crawl_config)

    return data, crawl_config


def _full_reanalyze(html_str: str, client) -> CrawlConfig | None:
    from ai.analyzer import analyze_page_v2
    from ai.xpath_gen import generate_container_xpath, generate_xpath
    from infrastructure.html.classifier import classify_element

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
            container_xpath = generate_container_xpath(
                container_element,
                classified_container,
                tree,
                client,
            )

    fields = []
    for field_info in analysis_fields:
        element = resolve_aid(tree, field_info.aid)
        if element is None:
            continue
        siblings = get_sibling_elements(element, container_element) if container_element is not None else []
        classified = classify_element(element, siblings, tree)
        xpath_result = generate_xpath(
            element,
            classified,
            field_info,
            tree,
            container_element,
            container_xpath,
            client,
        )
        fields.append(
            FieldXPath(
                name=field_info.name,
                description=field_info.description,
                xpath=xpath_result.xpath,
                fallback_xpath=xpath_result.fallback_xpath,
                confidence=xpath_result.confidence,
                extract=field_info.extract,
                attribute_name=field_info.attribute_name,
            )
        )

    return CrawlConfig(
        page_type=analysis_page_type,
        container_xpath=container_xpath,
        fields=fields,
    )
