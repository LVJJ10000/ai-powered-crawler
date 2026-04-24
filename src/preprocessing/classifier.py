"""
Attribute Classifier - classifies every attribute on an element as
STABLE, RANDOM, BUSINESS, or BUSINESS_CATEGORY.
"""

import re
from models.schemas import (
    AttrClassification, ClassifiedAttribute, ClassifiedClassToken,
    ClassifiedElement
)

# Regex patterns matching generated/random values
RANDOM_PATTERNS = [
    r'^[a-z]{2,4}-[a-zA-Z0-9]{4,}$',     # css-3fJ8kL, sc-bdnxRM
    r'^[a-f0-9]{8,}$',                     # hex hashes
    r'^_?[a-zA-Z]+_[a-zA-Z0-9]{4,}$',     # _ngcontent_abc123
    r'^__[\w]+-[\w]+$',                     # __next-el-0x7f2a
    r'^[a-zA-Z0-9]{20,}$',                 # long random strings
    r'[0-9a-f]{8}-[0-9a-f]{4}-',           # UUIDs
    r'^\d+$',                               # pure numbers
]

# Known framework-generated attribute prefixes
FRAMEWORK_ATTRS = [
    'data-reactid', 'data-react-checksum',
    'data-v-',          # Vue scoped
    '_ngcontent-',      # Angular
    'data-styled-',     # styled-components
    'jsname', 'jsaction', 'jscontroller',   # Google
]

# Known stable attribute names
STABLE_ATTRS = [
    'data-testid', 'data-test', 'data-cy',
    'role', 'aria-label', 'aria-labelledby',
    'itemprop', 'itemtype',   # schema.org microdata
    'name',  # on form elements
]


def classify_single_attribute(attr_name: str, attr_value: str) -> AttrClassification:
    """Rule-based classification without cross-element comparison."""
    # Skip our synthetic attr
    if attr_name == "data-aid":
        return AttrClassification.UNKNOWN

    # Known stable attributes
    if attr_name in STABLE_ATTRS:
        return AttrClassification.STABLE

    # Framework-generated attributes
    for prefix in FRAMEWORK_ATTRS:
        if attr_name.startswith(prefix) or attr_name == prefix:
            return AttrClassification.RANDOM

    # Check value against random patterns
    for pattern in RANDOM_PATTERNS:
        if re.match(pattern, attr_value):
            return AttrClassification.RANDOM

    return AttrClassification.UNKNOWN


def classify_attribute(attr_name: str, attr_value: str, sibling_values: list[str]) -> AttrClassification:
    """Full classification with cross-element comparison."""
    # Try single-attribute classification first
    result = classify_single_attribute(attr_name, attr_value)
    if result != AttrClassification.UNKNOWN:
        return result

    # Cross-element comparison
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
    """Split class string into tokens, classify each independently."""
    tokens = class_string.split()
    total_siblings = len(sibling_class_strings)
    results = []

    for token in tokens:
        # Check random patterns
        is_random = False
        for pattern in RANDOM_PATTERNS:
            if re.match(pattern, token):
                is_random = True
                break

        if is_random:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.RANDOM))
            continue

        if total_siblings < 2:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.UNKNOWN))
            continue

        # Count frequency across siblings
        frequency = sum(1 for s in sibling_class_strings if token in s.split())

        if frequency == total_siblings:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.STABLE))
        elif frequency < total_siblings * 0.3 and frequency > 0:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.CONDITIONAL))
        elif frequency <= 1:
            # Check if looks like business data
            if re.match(r'.*\d+.*', token) or re.match(r'^[a-z]+-[a-z]+-', token):
                results.append(ClassifiedClassToken(token=token, classification=AttrClassification.BUSINESS))
            else:
                results.append(ClassifiedClassToken(token=token, classification=AttrClassification.RANDOM))
        else:
            results.append(ClassifiedClassToken(token=token, classification=AttrClassification.STABLE))

    return results


def classify_element(element, sibling_elements: list, tree) -> ClassifiedElement:
    """Complete classification of an element for Prompt B input."""
    tag = element.tag
    text_sample = (element.text_content() or "").strip()[:100]

    # Classify attributes
    attributes = []
    class_tokens = []

    for attr_name, attr_value in element.attrib.items():
        if attr_name == "data-aid":
            continue

        sibling_values = collect_sibling_attr_values(sibling_elements, attr_name)

        if attr_name == "class":
            sibling_class_strings = sibling_values
            class_tokens = classify_class_tokens(attr_value, sibling_class_strings)
            # Also classify the full class attribute
            classification = classify_attribute(attr_name, attr_value, sibling_values)
            attributes.append(ClassifiedAttribute(
                attr_name=attr_name, attr_value=attr_value, classification=classification
            ))
        else:
            classification = classify_attribute(attr_name, attr_value, sibling_values)
            attributes.append(ClassifiedAttribute(
                attr_name=attr_name, attr_value=attr_value, classification=classification
            ))

    # Build ancestor chain (max 10 levels)
    ancestor_chain = []
    current = element.getparent()
    depth = 0
    while current is not None and depth < 10 and isinstance(current.tag, str):
        anc_attrs = []
        anc_class_tokens = []
        for attr_name, attr_value in current.attrib.items():
            if attr_name == "data-aid":
                continue
            cls = classify_single_attribute(attr_name, attr_value)
            anc_attrs.append({"name": attr_name, "value": attr_value, "classification": cls.value})
            if attr_name == "class":
                for token in attr_value.split():
                    token_cls = AttrClassification.STABLE  # Ancestor classes often stable
                    for pattern in RANDOM_PATTERNS:
                        if re.match(pattern, token):
                            token_cls = AttrClassification.RANDOM
                            break
                    anc_class_tokens.append({"token": token, "classification": token_cls.value})

        ancestor_chain.append({
            "tag": current.tag,
            "attributes": anc_attrs,
            "class_tokens": anc_class_tokens
        })
        current = current.getparent()
        depth += 1

    # Get sibling info
    prev_sibling = None
    next_sibling = None
    parent = element.getparent()
    if parent is not None:
        children = list(parent)
        idx = None
        for i, child in enumerate(children):
            if child is element:
                idx = i
                break
        if idx is not None:
            if idx > 0 and isinstance(children[idx - 1].tag, str):
                prev = children[idx - 1]
                prev_sibling = {"tag": prev.tag, "class": prev.get("class", ""), "text": (prev.text_content() or "").strip()[:50]}
            if idx < len(children) - 1 and isinstance(children[idx + 1].tag, str):
                nxt = children[idx + 1]
                next_sibling = {"tag": nxt.tag, "class": nxt.get("class", ""), "text": (nxt.text_content() or "").strip()[:50]}

    return ClassifiedElement(
        tag=tag,
        text_sample=text_sample,
        attributes=attributes,
        class_tokens=class_tokens,
        ancestor_chain=ancestor_chain,
        prev_sibling=prev_sibling,
        next_sibling=next_sibling
    )


def collect_sibling_attr_values(sibling_elements: list, attr_name: str) -> list[str]:
    """Extract one attribute's value from all sibling elements."""
    values = []
    for el in sibling_elements:
        values.append(el.get(attr_name, ""))
    return values


def format_classified_element_for_prompt(ce: ClassifiedElement) -> str:
    """Format ClassifiedElement as human-readable text for Prompt B."""
    lines = []
    lines.append(f'Tag: <{ce.tag}>')
    lines.append(f'Sample text: "{ce.text_sample}"')
    lines.append("")
    lines.append("Attributes:")

    for attr in ce.attributes:
        if attr.attr_name == "class":
            lines.append(f"  class:")
            for ct in ce.class_tokens:
                label = ct.classification.value.upper()
                hint = _classification_hint(ct.classification)
                lines.append(f'    "{ct.token}"  -> {label} ({hint})')
        else:
            label = attr.classification.value.upper()
            hint = _classification_hint(attr.classification)
            lines.append(f'  {attr.attr_name}:')
            lines.append(f'    "{attr.attr_value}"  -> {label} ({hint})')

    lines.append("")
    lines.append("Ancestor chain:")
    for anc in ce.ancestor_chain:
        parts = []
        for a in anc.get("attributes", []):
            label = a["classification"].upper()
            parts.append(f'{a["name"]}="{a["value"]}" [{label}]')
        attr_str = " ".join(parts) if parts else ""
        lines.append(f'  <{anc["tag"]} {attr_str}>')

    return "\n".join(lines)


def _classification_hint(cls: AttrClassification) -> str:
    """Get hint text for a classification."""
    hints = {
        AttrClassification.STABLE: "safe to use",
        AttrClassification.RANDOM: "never use",
        AttrClassification.BUSINESS: "never use exact value",
        AttrClassification.BUSINESS_CATEGORY: "category, use with caution",
        AttrClassification.CONDITIONAL: "state-dependent, use with caution",
        AttrClassification.UNKNOWN: "unknown stability",
    }
    return hints.get(cls, "unknown")
