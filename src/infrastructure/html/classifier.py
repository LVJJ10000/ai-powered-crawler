"""
Attribute classifier for annotated HTML elements.
"""

import re

from models.schemas import (
    AttrClassification,
    ClassifiedAttribute,
    ClassifiedClassToken,
    ClassifiedElement,
)

RANDOM_PATTERNS = [
    r"^[a-z]{2,4}-[a-zA-Z0-9]{4,}$",
    r"^[a-f0-9]{8,}$",
    r"^_?[a-zA-Z]+_[a-zA-Z0-9]{4,}$",
    r"^__[\w]+-[\w]+$",
    r"^[a-zA-Z0-9]{20,}$",
    r"[0-9a-f]{8}-[0-9a-f]{4}-",
    r"^\d+$",
]

FRAMEWORK_ATTRS = [
    "data-reactid",
    "data-react-checksum",
    "data-v-",
    "_ngcontent-",
    "data-styled-",
    "jsname",
    "jsaction",
    "jscontroller",
]

STABLE_ATTRS = [
    "data-testid",
    "data-test",
    "data-cy",
    "role",
    "aria-label",
    "aria-labelledby",
    "itemprop",
    "itemtype",
    "name",
]


def classify_single_attribute(attr_name: str, attr_value: str) -> AttrClassification:
    if attr_name == "data-aid":
        return AttrClassification.UNKNOWN
    if attr_name in STABLE_ATTRS:
        return AttrClassification.STABLE
    for prefix in FRAMEWORK_ATTRS:
        if attr_name.startswith(prefix) or attr_name == prefix:
            return AttrClassification.RANDOM
    for pattern in RANDOM_PATTERNS:
        if re.match(pattern, attr_value):
            return AttrClassification.RANDOM
    return AttrClassification.UNKNOWN


def classify_attribute(attr_name: str, attr_value: str, sibling_values: list[str]) -> AttrClassification:
    result = classify_single_attribute(attr_name, attr_value)
    if result != AttrClassification.UNKNOWN:
        return result
    if len(sibling_values) < 2:
        return AttrClassification.UNKNOWN

    unique_count = len(set(sibling_values))
    total = len(sibling_values)
    if unique_count == 1:
        return AttrClassification.STABLE
    if unique_count == total:
        return AttrClassification.BUSINESS
    if unique_count / total < 0.3:
        return AttrClassification.BUSINESS_CATEGORY
    return AttrClassification.RANDOM


def classify_class_tokens(class_string: str, sibling_class_strings: list[str]) -> list[ClassifiedClassToken]:
    tokens = class_string.split()
    total_siblings = len(sibling_class_strings)
    results = []

    for token in tokens:
        if any(re.match(pattern, token) for pattern in RANDOM_PATTERNS):
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.RANDOM))
            continue

        if total_siblings < 2:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.UNKNOWN))
            continue

        frequency = sum(1 for value in sibling_class_strings if token in value.split())
        if frequency == total_siblings:
            classification = AttrClassification.STABLE
        elif 0 < frequency < total_siblings * 0.3:
            classification = AttrClassification.CONDITIONAL
        elif frequency <= 1:
            if re.match(r".*\d+.*", token) or re.match(r"^[a-z]+-[a-z]+-", token):
                classification = AttrClassification.BUSINESS
            else:
                classification = AttrClassification.RANDOM
        else:
            classification = AttrClassification.STABLE
        results.append(ClassifiedClassToken(token=token, classification=classification))

    return results


def classify_element(element, sibling_elements: list, tree) -> ClassifiedElement:
    attributes = []
    class_tokens = []

    for attr_name, attr_value in element.attrib.items():
        if attr_name == "data-aid":
            continue
        sibling_values = collect_sibling_attr_values(sibling_elements, attr_name)
        if attr_name == "class":
            class_tokens = classify_class_tokens(attr_value, sibling_values)
        attributes.append(
            ClassifiedAttribute(
                attr_name=attr_name,
                attr_value=attr_value,
                classification=classify_attribute(attr_name, attr_value, sibling_values),
            )
        )

    ancestor_chain = []
    current = element.getparent()
    depth = 0
    while current is not None and depth < 10 and isinstance(current.tag, str):
        ancestor_attributes = []
        ancestor_class_tokens = []
        for attr_name, attr_value in current.attrib.items():
            if attr_name == "data-aid":
                continue
            classification = classify_single_attribute(attr_name, attr_value)
            ancestor_attributes.append(
                {"name": attr_name, "value": attr_value, "classification": classification.value}
            )
            if attr_name == "class":
                for token in attr_value.split():
                    token_classification = AttrClassification.STABLE
                    if any(re.match(pattern, token) for pattern in RANDOM_PATTERNS):
                        token_classification = AttrClassification.RANDOM
                    ancestor_class_tokens.append(
                        {"token": token, "classification": token_classification.value}
                    )

        ancestor_chain.append(
            {
                "tag": current.tag,
                "attributes": ancestor_attributes,
                "class_tokens": ancestor_class_tokens,
            }
        )
        current = current.getparent()
        depth += 1

    prev_sibling = None
    next_sibling = None
    parent = element.getparent()
    if parent is not None:
        children = list(parent)
        element_index = None
        for idx, child in enumerate(children):
            if child is element:
                element_index = idx
                break
        if element_index is not None:
            if element_index > 0 and isinstance(children[element_index - 1].tag, str):
                prev = children[element_index - 1]
                prev_sibling = {
                    "tag": prev.tag,
                    "class": prev.get("class", ""),
                    "text": (prev.text_content() or "").strip()[:50],
                }
            if element_index < len(children) - 1 and isinstance(children[element_index + 1].tag, str):
                nxt = children[element_index + 1]
                next_sibling = {
                    "tag": nxt.tag,
                    "class": nxt.get("class", ""),
                    "text": (nxt.text_content() or "").strip()[:50],
                }

    return ClassifiedElement(
        tag=element.tag,
        text_sample=(element.text_content() or "").strip()[:100],
        attributes=attributes,
        class_tokens=class_tokens,
        ancestor_chain=ancestor_chain,
        prev_sibling=prev_sibling,
        next_sibling=next_sibling,
    )


def collect_sibling_attr_values(sibling_elements: list, attr_name: str) -> list[str]:
    return [element.get(attr_name, "") for element in sibling_elements]


def format_classified_element_for_prompt(classified_element: ClassifiedElement) -> str:
    lines = [
        f"Tag: <{classified_element.tag}>",
        f'Sample text: "{classified_element.text_sample}"',
        "",
        "Attributes:",
    ]

    for attr in classified_element.attributes:
        if attr.attr_name == "class":
            lines.append("  class:")
            for class_token in classified_element.class_tokens:
                label = class_token.classification.value.upper()
                hint = _classification_hint(class_token.classification)
                lines.append(f'    "{class_token.token}"  -> {label} ({hint})')
        else:
            label = attr.classification.value.upper()
            hint = _classification_hint(attr.classification)
            lines.append(f"  {attr.attr_name}:")
            lines.append(f'    "{attr.attr_value}"  -> {label} ({hint})')

    lines.append("")
    lines.append("Ancestor chain:")
    for ancestor in classified_element.ancestor_chain:
        parts = []
        for attr in ancestor.get("attributes", []):
            parts.append(f'{attr["name"]}="{attr["value"]}" [{attr["classification"].upper()}]')
        attr_text = " ".join(parts) if parts else ""
        lines.append(f'  <{ancestor["tag"]} {attr_text}>')

    return "\n".join(lines)


def _classification_hint(classification: AttrClassification) -> str:
    hints = {
        AttrClassification.STABLE: "structural/consistent",
        AttrClassification.RANDOM: "generated/unstable",
        AttrClassification.BUSINESS: "content-specific",
        AttrClassification.BUSINESS_CATEGORY: "content category/grouping",
        AttrClassification.CONDITIONAL: "present on some siblings only",
        AttrClassification.UNKNOWN: "unknown",
    }
    return hints.get(classification, "unknown")
