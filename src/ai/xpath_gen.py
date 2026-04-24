"""
XPath Generation: code-based (fast, free) and AI-based (Prompt B, for hard cases).
"""

import json
import logging
from lxml import etree
from openai import OpenAI
from models.schemas import (
    XPathResult, ClassifiedElement, FieldInfo, ExtractType, AttrClassification
)
from preprocessing.classifier import format_classified_element_for_prompt
import config

logger = logging.getLogger(__name__)

PROMPT_B_TEMPLATE = '''You are an XPath expert. Generate a production-ready XPath for
the target element described below.

== TARGET ELEMENT ==
Tag: {tag}
Purpose: {field_description}
Sample text content: "{sample_text}"

== ATTRIBUTE CLASSIFICATION ==
Each attribute is labeled. STABLE = safe to use. RANDOM = never use.
BUSINESS = never use for exact match (changes per item).

{formatted_attribute_classifications}

== TARGET DOM CONTEXT ==
{target_dom_context}

== ANCESTOR CHAIN (with classifications) ==
{formatted_ancestor_chain}

== SIBLING CONTEXT ==
Previous sibling: {prev_sibling}
Next sibling: {next_sibling}

== RULES ==
1. ONLY use attributes marked STABLE in your XPath
2. NEVER use RANDOM attributes - they change between page loads or builds
3. NEVER use BUSINESS attributes for exact value match - they differ per item.
   You MAY check existence (e.g., .//*[@data-product-id]) only if no STABLE
   alternative exists, but NEVER match the value.
4. For class selectors: ALWAYS use contains(@class, 'stable-token'),
   NEVER match the full class string exactly.
5. NEVER use data-aid attributes - they are synthetic and temporary.
6. Attribute selection priority (highest to lowest):
   a. @data-testid, @data-test, @data-cy
   b. @role, @aria-label
   c. @id (only if STABLE)
   d. @class (only STABLE tokens, via contains())
   e. Semantic tag names (article, main, section, h1-h6, time, img)
   f. Structural position as LAST RESORT (set confidence < 0.5)
7. XPath must be RELATIVE to the container (start with .// )
8. For text extraction, return the element XPath itself (NO /text()).
   Text will be read from the selected element in code.
9. For attribute extraction, end with /@{attribute_name}
10. The XPath must work across ALL pages with the same template,
    not just this specific page.

== CONTAINER ==
Container XPath: {container_xpath}
(Your XPath will be evaluated within this container context)

Return valid JSON only, no markdown fences, no other text:
{{
  "xpath": ".//span[@data-testid='price']/text()",
  "strategy": "short description of approach used",
  "confidence": 0.95,
  "fallback_xpath": ".//span[contains(@class,'price')]/text()",
  "attributes_used": ["data-testid=price"]
}}'''


def generate_xpath(
    element,
    classified: ClassifiedElement,
    field_info: FieldInfo,
    tree,
    container_element=None,
    container_xpath=None,
    client=None
) -> XPathResult:
    """Generate XPath for a field element. Try code first, then AI."""
    

    # Try AI to generation first
    if client:
        logger.info(f"Using AI for XPath generation: {field_info.name}")
        ai_result = generate_xpath_by_ai(
            classified,
            field_info,
            container_xpath,
            client,
            target_element=element,
            tree=tree,
            container_element=container_element,
        )
        if ai_result:
            return ai_result
        
    #  Fall back to code-based generation first
    code_result = generate_xpath_by_code(element, classified, field_info, tree, container_element)
    if code_result:
        logger.info(f"Code-generated XPath for {field_info.name}: {code_result.xpath}")
        return code_result
    
    # Last resort: positional XPath
    logger.warning(f"Using positional XPath for {field_info.name}")
    xpath = _build_positional_xpath(element, tree, container_element, field_info)
    return XPathResult(
        xpath=xpath,
        strategy="positional (last resort)",
        confidence=0.3,
        attributes_used=[]
    )


def generate_xpath_by_code(
    element, classified: ClassifiedElement, field_info: FieldInfo, tree, container_element
) -> XPathResult | None:
    """Try code-based XPath generation strategies in priority order."""
    tag = element.tag
    is_list = container_element is not None
    context = container_element if is_list else tree

    # Strategy 1: data-testid / data-test / data-cy
    for attr_name in ['data-testid', 'data-test', 'data-cy']:
        value = element.get(attr_name)
        if value:
            xpath = f".//{tag}[@{attr_name}='{value}']"
            xpath_with_extract = _append_extraction(xpath, field_info)
            if _test_xpath_unique(xpath, context, tree, is_list):
                return XPathResult(
                    xpath=xpath_with_extract,
                    strategy=f"code: {attr_name}",
                    confidence=0.98,
                    attributes_used=[f"{attr_name}={value}"]
                )

    # Strategy 2: id (only if classified STABLE)
    id_val = element.get("id")
    if id_val:
        for attr in classified.attributes:
            if attr.attr_name == "id" and attr.classification == AttrClassification.STABLE:
                xpath = f".//{tag}[@id='{id_val}']"
                xpath_with_extract = _append_extraction(xpath, field_info)
                if _test_xpath_unique(xpath, context, tree, is_list):
                    return XPathResult(
                        xpath=xpath_with_extract,
                        strategy="code: stable id",
                        confidence=0.95,
                        attributes_used=[f"id={id_val}"]
                    )

    # Strategy 3: class (STABLE tokens only, using contains())
    stable_tokens = [ct.token for ct in classified.class_tokens if ct.classification == AttrClassification.STABLE]
    for token in stable_tokens:
        xpath = f".//{tag}[contains(@class, '{token}')]"
        xpath_with_extract = _append_extraction(xpath, field_info)
        if _test_xpath_unique(xpath, context, tree, is_list):
            return XPathResult(
                xpath=xpath_with_extract,
                strategy=f"code: stable class token '{token}'",
                confidence=0.9,
                attributes_used=[f"class~={token}"]
            )

    # Strategy 4: Other STABLE data-* attributes
    for attr in classified.attributes:
        if (attr.classification == AttrClassification.STABLE and
            attr.attr_name.startswith("data-") and
            attr.attr_name != "data-aid"):
            xpath = f".//{tag}[@{attr.attr_name}='{attr.attr_value}']"
            xpath_with_extract = _append_extraction(xpath, field_info)
            if _test_xpath_unique(xpath, context, tree, is_list):
                return XPathResult(
                    xpath=xpath_with_extract,
                    strategy=f"code: stable {attr.attr_name}",
                    confidence=0.9,
                    attributes_used=[f"{attr.attr_name}={attr.attr_value}"]
                )

    # Strategy 5: role + aria-label
    role = element.get("role")
    aria_label = element.get("aria-label")
    if role:
        xpath = f".//{tag}[@role='{role}']"
        if aria_label:
            xpath = f".//{tag}[@role='{role}' and @aria-label='{aria_label}']"
        xpath_with_extract = _append_extraction(xpath, field_info)
        if _test_xpath_unique(xpath, context, tree, is_list):
            attrs_used = [f"role={role}"]
            if aria_label:
                attrs_used.append(f"aria-label={aria_label}")
            return XPathResult(
                xpath=xpath_with_extract,
                strategy="code: role/aria-label",
                confidence=0.85,
                attributes_used=attrs_used
            )

    # Strategy 6: Unique tag under parent
    xpath = f".//{tag}"
    if _test_xpath_unique(xpath, context, tree, is_list):
        xpath_with_extract = _append_extraction(xpath, field_info)
        return XPathResult(
            xpath=xpath_with_extract,
            strategy="code: unique tag",
            confidence=0.7,
            attributes_used=[]
        )

    # Strategy 7: Combine with ancestor stable class
    combined = _combine_ancestor_xpath(element, classified, tree, container_element, field_info)
    if combined:
        return combined

    return None


def _test_xpath_unique(xpath: str, context_element, tree, is_list: bool) -> bool:
    """Test if XPath uniquely identifies the target element."""
    try:
        if is_list:
            results = context_element.xpath(xpath)
            return len(results) == 1
        else:
            results = tree.xpath(xpath)
            return len(results) == 1
    except Exception:
        return False


def _append_extraction(xpath: str, field_info: FieldInfo) -> str:
    """Append text() or @attr extraction suffix to xpath."""
    if field_info.extract == ExtractType.TEXT:
        return xpath
    elif field_info.extract == ExtractType.ATTRIBUTE and field_info.attribute_name:
        return xpath + f"/@{field_info.attribute_name}"
    return xpath


def _strip_text_predicates(xpath: str) -> str:
    """Remove text-content predicates from XPath — they break on other list items.

    Strips patterns like:
      [contains(text(), '具体文字')]
      [text()='具体文字']
      and contains(text(), '具体文字')
      [contains(., '具体文字')]
      [normalize-space(text())='具体文字']
      [normalize-space(.)='具体文字']
    """
    import re
    str_lit = r"(?:'[^']*'|\"[^\"]*\")"
    text_expr = rf"(?:contains\(\s*text\(\)\s*,\s*{str_lit}\s*\)|contains\(\s*\.\s*,\s*{str_lit}\s*\)|normalize-space\(\s*text\(\)\s*\)\s*=\s*{str_lit}|normalize-space\(\s*\.\s*\)\s*=\s*{str_lit}|text\(\)\s*=\s*{str_lit})"

    # Remove standalone text predicates
    xpath = re.sub(rf"\[\s*{text_expr}\s*\]", "", xpath)
    # Remove text comparisons inside compound predicates
    xpath = re.sub(rf"\s+and\s+{text_expr}", "", xpath)
    xpath = re.sub(rf"{text_expr}\s+and\s+", "", xpath)

    # Clean up empty predicates []
    xpath = re.sub(r"\[\s*\]", "", xpath)
    return xpath


def _fix_extraction_suffix(xpath: str, field_info: FieldInfo) -> str:
    """Ensure the XPath ends with the correct extraction suffix for the field type.

    The AI sometimes generates /text() for an attribute field or vice versa.
    Strip any existing suffix and reapply the correct one.
    """
    import re
    # Strip existing extraction suffix
    base = re.sub(r'/(text\(\)|@[\w-]+)$', '', xpath)

    if field_info.extract == ExtractType.TEXT:
        return base
    elif field_info.extract == ExtractType.ATTRIBUTE and field_info.attribute_name:
        return base + f"/@{field_info.attribute_name}"
    return xpath


def _build_target_dom_context(target_element) -> str:
    """Build structured DOM context around the target element for prompt quality."""
    if target_element is None:
        return "Not available"

    import re
    from preprocessing.classifier import RANDOM_PATTERNS, classify_single_attribute

    def _norm_text(text: str, limit: int = 100) -> str:
        clean = re.sub(r"\s+", " ", (text or "")).strip()
        return clean[:limit]

    def _safe_value(value: str, limit: int = 80) -> str:
        return (value or "").replace('"', "'")[:limit]

    def _format_attr(name: str, value: str) -> str:
        if name == "data-aid":
            return ""
        if name == "class":
            tokens = value.split()
            token_parts = []
            for token in tokens[:10]:
                label = "STABLE"
                if any(re.match(pattern, token) for pattern in RANDOM_PATTERNS):
                    label = "RANDOM"
                token_parts.append(f"{token}[{label}]")
            class_value = " ".join(token_parts)
            return f'class="{class_value}"'

        cls = classify_single_attribute(name, value).value.upper()
        return f'{name}="{_safe_value(value)}" [{cls}]'

    def _format_node(node) -> str:
        attrs = []
        for attr_name, attr_value in list(node.attrib.items())[:10]:
            formatted = _format_attr(attr_name, attr_value)
            if formatted:
                attrs.append(formatted)
        attr_part = (" " + " ".join(attrs)) if attrs else ""
        return f"<{node.tag}{attr_part}>"

    lines = []
    lines.append(f"Target: {_format_node(target_element)}")
    if hasattr(target_element, "text_content"):
        raw_target_text = target_element.text_content()
    else:
        raw_target_text = "".join(target_element.itertext())
    target_text = _norm_text(raw_target_text)
    if target_text:
        lines.append(f'Target text: "{target_text}"')

    lines.append("Ancestors (nearest first):")
    current = target_element.getparent()
    depth = 0
    while current is not None and isinstance(current.tag, str) and depth < 6:
        lines.append(f"  - {_format_node(current)}")
        current = current.getparent()
        depth += 1

    parent = target_element.getparent()
    lines.append("Siblings (same parent):")
    if parent is not None and isinstance(parent.tag, str):
        siblings = [c for c in parent if isinstance(c.tag, str)]
        target_idx = None
        for idx, sibling in enumerate(siblings):
            if sibling is target_element:
                target_idx = idx
                break
        if target_idx is not None:
            start = max(0, target_idx - 3)
            end = min(len(siblings), target_idx + 4)
            for i in range(start, end):
                if i == target_idx:
                    continue
                marker = "prev" if i < target_idx else "next"
                lines.append(f"  - {marker}: {_format_node(siblings[i])}")

    descendants = [d for d in target_element.iterdescendants() if isinstance(d.tag, str)]
    lines.append("Descendants (depth<=2):")
    count = 0
    for desc in descendants:
        depth_from_target = 0
        current = desc
        while current is not None and current is not target_element:
            current = current.getparent()
            depth_from_target += 1
        if depth_from_target <= 2:
            lines.append(f"  - {_format_node(desc)}")
            count += 1
            if count >= 8:
                break
    if count == 0:
        lines.append("  - None")

    return "\n".join(lines)


def _strip_extraction_suffix(xpath: str) -> str:
    """Strip trailing /text() or /@attr suffix for structural validation."""
    import re
    return re.sub(r'/(text\(\)|@[\w:-]+)$', '', xpath)


def _validate_xpath_for_target(xpath: str, target_element, tree, container_element) -> bool:
    """Validate XPath by checking it can match the current target element."""
    if target_element is None or tree is None:
        return True

    base_xpath = _strip_extraction_suffix(xpath)
    context = container_element if container_element is not None else tree

    try:
        results = context.xpath(base_xpath)
    except Exception:
        return False

    if not isinstance(results, list) or not results:
        return False

    # Reject overly broad selectors:
    # - In list-item context (container provided), field xpath should resolve to exactly one node.
    # - In detail/root context, allow a small amount of ambiguity.
    max_matches = 1 if container_element is not None else 3
    if len(results) > max_matches:
        return False

    return any(node is target_element for node in results)


def _combine_ancestor_xpath(element, classified, tree, container_element, field_info) -> XPathResult | None:
    """Try combining with nearest identifiable ancestor."""
    tag = element.tag
    is_list = container_element is not None
    context = container_element if is_list else tree

    current = element.getparent()
    depth = 0
    while current is not None and isinstance(current.tag, str) and depth < 5:
        # Check if ancestor has stable class
        anc_class = current.get("class", "")
        if anc_class:
            for token in anc_class.split():
                # Quick check: not random-looking
                import re
                is_random = False
                from preprocessing.classifier import RANDOM_PATTERNS
                for pattern in RANDOM_PATTERNS:
                    if re.match(pattern, token):
                        is_random = True
                        break
                if not is_random and len(token) > 2:
                    xpath = f".//{'*'}[contains(@class, '{token}')]//{tag}"
                    if _test_xpath_unique(xpath, context, tree, is_list):
                        xpath_with_extract = _append_extraction(xpath, field_info)
                        return XPathResult(
                            xpath=xpath_with_extract,
                            strategy=f"code: ancestor class '{token}' + tag",
                            confidence=0.7,
                            attributes_used=[f"ancestor-class~={token}"]
                        )

        # Check if ancestor has stable id
        anc_id = current.get("id")
        if anc_id:
            xpath = f".//*[@id='{anc_id}']//{tag}"
            if _test_xpath_unique(xpath, context, tree, is_list):
                xpath_with_extract = _append_extraction(xpath, field_info)
                return XPathResult(
                    xpath=xpath_with_extract,
                    strategy=f"code: ancestor id '{anc_id}' + tag",
                    confidence=0.75,
                    attributes_used=[f"ancestor-id={anc_id}"]
                )

        current = current.getparent()
        depth += 1

    return None


def generate_xpath_by_ai(
    classified: ClassifiedElement,
    field_info: FieldInfo,
    container_xpath: str | None,
    client: OpenAI,
    target_element=None,
    tree=None,
    container_element=None,
) -> XPathResult | None:
    """Generate XPath using AI (Prompt B)."""
    formatted = format_classified_element_for_prompt(classified)
    target_dom_context = _build_target_dom_context(target_element)

    # Build ancestor chain text
    ancestor_text = ""
    for anc in classified.ancestor_chain:
        parts = []
        for a in anc.get("attributes", []):
            parts.append(f'{a["name"]}="{a["value"]}" [{a["classification"].upper()}]')
        attr_str = " ".join(parts) if parts else ""
        ancestor_text += f'  <{anc["tag"]} {attr_str}>\n'

    prompt = PROMPT_B_TEMPLATE.format(
        tag=classified.tag,
        field_description=field_info.description,
        sample_text=classified.text_sample,
        formatted_attribute_classifications=formatted,
        target_dom_context=target_dom_context,
        formatted_ancestor_chain=ancestor_text,
        prev_sibling=str(classified.prev_sibling) if classified.prev_sibling else "None",
        next_sibling=str(classified.next_sibling) if classified.next_sibling else "None",
        container_xpath=container_xpath or "None (detail page, use absolute XPath)",
        attribute_name=field_info.attribute_name or "N/A"
    )

    try:
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        data = json.loads(content)

        # Strip hardcoded text predicates — they break on other list items
        xpath = data["xpath"]
        xpath = _strip_text_predicates(xpath)
        # Enforce correct extraction suffix — AI sometimes ignores the field type
        xpath = _fix_extraction_suffix(xpath, field_info)
        fallback = data.get("fallback_xpath")
        if fallback:
            fallback = _strip_text_predicates(fallback)
            fallback = _fix_extraction_suffix(fallback, field_info)

        primary_valid = _validate_xpath_for_target(xpath, target_element, tree, container_element)
        fallback_valid = bool(fallback) and _validate_xpath_for_target(
            fallback, target_element, tree, container_element
        )

        confidence = data.get("confidence", 0.8)

        if not primary_valid:
            if fallback_valid:
                logger.warning("AI primary XPath failed validation; using fallback XPath")
                xpath = fallback
                fallback = None
                confidence = min(confidence, 0.75)
            else:
                logger.warning("AI XPath failed validation (primary and fallback)")
                return None
        elif fallback and not fallback_valid:
            fallback = None

        return XPathResult(
            xpath=xpath,
            strategy=data.get("strategy", "AI generated"),
            confidence=confidence,
            fallback_xpath=fallback,
            attributes_used=data.get("attributes_used", [])
        )
    except Exception as e:
        logger.error(f"AI XPath generation failed: {e}")
        return None


def generate_container_xpath(
    container_element, classified_container: ClassifiedElement, tree, client: OpenAI
) -> str | None:
    """Generate XPath for the repeating container element."""
    tag = container_element.tag

    # Try code-based: find stable class tokens
    stable_tokens = [ct.token for ct in classified_container.class_tokens
                     if ct.classification == AttrClassification.STABLE]

    for token in stable_tokens:
        xpath = f"//{tag}[contains(@class, '{token}')]"
        try:
            results = tree.xpath(xpath)
            if 1 < len(results) < 200:
                logger.info(f"Container XPath by class token: {xpath} ({len(results)} matches)")
                return xpath
        except Exception:
            continue

    # Try by tag + parent structure
    parent = container_element.getparent()
    if parent is not None and isinstance(parent.tag, str):
        parent_class = parent.get("class", "")
        if parent_class:
            for token in parent_class.split():
                import re
                from preprocessing.classifier import RANDOM_PATTERNS
                is_random = any(re.match(p, token) for p in RANDOM_PATTERNS)
                if not is_random and len(token) > 2:
                    xpath = f"//*[contains(@class, '{token}')]/{tag}"
                    try:
                        results = tree.xpath(xpath)
                        if 1 < len(results) < 200:
                            logger.info(f"Container XPath by parent: {xpath} ({len(results)} matches)")
                            return xpath
                    except Exception:
                        continue

    # Try just by tag under parent with id/class
    if parent is not None:
        parent_id = parent.get("id")
        if parent_id:
            xpath = f"//*[@id='{parent_id}']/{tag}"
            try:
                results = tree.xpath(xpath)
                if 1 < len(results) < 200:
                    return xpath
            except Exception:
                pass

    # Fallback: use data-testid or other stable attrs
    for attr in classified_container.attributes:
        if attr.classification == AttrClassification.STABLE and attr.attr_name != "data-aid":
            xpath = f"//{tag}[@{attr.attr_name}='{attr.attr_value}']"
            try:
                results = tree.xpath(xpath)
                if 1 < len(results) < 200:
                    return xpath
            except Exception:
                continue

    # Fallback: if container is a wrapper (ul, ol, div, tbody) with multiple
    # same-tag children, use those children as the repeating items instead
    import re
    from preprocessing.classifier import RANDOM_PATTERNS
    children = [c for c in container_element if isinstance(c.tag, str)]
    if len(children) >= 2:
        child_tags = {}
        for c in children:
            child_tags[c.tag] = child_tags.get(c.tag, 0) + 1
        most_common_tag = max(child_tags, key=child_tags.get)
        if child_tags[most_common_tag] >= 2:
            # Build xpath to these children
            if parent is not None and isinstance(parent.tag, str):
                parent_class = parent.get("class", "")
                parent_id = parent.get("id", "")
                if parent_id:
                    xpath = f"//*[@id='{parent_id}']/{tag}/{most_common_tag}"
                    try:
                        results = tree.xpath(xpath)
                        if 1 < len(results) < 200:
                            logger.info(f"Container XPath via parent id + children: {xpath} ({len(results)} matches)")
                            return xpath
                    except Exception:
                        pass
                if parent_class:
                    for token in parent_class.split():
                        is_random = any(re.match(p, token) for p in RANDOM_PATTERNS)
                        if not is_random and len(token) > 2:
                            xpath = f"//*[contains(@class, '{token}')]/{tag}/{most_common_tag}"
                            try:
                                results = tree.xpath(xpath)
                                if 1 < len(results) < 200:
                                    logger.info(f"Container XPath via children: {xpath} ({len(results)} matches)")
                                    return xpath
                            except Exception:
                                continue
            # Last resort: just tag/child_tag
            xpath = f"//{tag}/{most_common_tag}"
            try:
                results = tree.xpath(xpath)
                if 1 < len(results) < 200:
                    logger.info(f"Container XPath via tag/child: {xpath} ({len(results)} matches)")
                    return xpath
            except Exception:
                pass

    logger.warning("Could not generate container XPath by code")
    return None


def _build_positional_xpath(element, tree, container_element, field_info: FieldInfo) -> str:
    """Build a positional XPath as last resort."""
    # Walk up to build a path
    parts = []
    current = element
    while current is not None and isinstance(current.tag, str):
        parent = current.getparent()
        if parent is not None:
            siblings = [c for c in parent if isinstance(c.tag, str) and c.tag == current.tag]
            if len(siblings) > 1:
                idx = siblings.index(current) + 1
                parts.append(f"{current.tag}[{idx}]")
            else:
                parts.append(current.tag)
        else:
            parts.append(current.tag)
        current = parent

    parts.reverse()
    xpath = "//" + "/".join(parts[-3:])  # Use last 3 levels
    return _append_extraction(xpath, field_info)
