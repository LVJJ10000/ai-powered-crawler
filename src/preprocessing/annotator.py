"""
HTML Annotator - adds unique data-aid attribute to every element.
"""

from lxml import html, etree


def annotate_html(cleaned_html: str) -> tuple[str, etree._Element]:
    """Add data-aid to every element. Returns (annotated HTML string, tree object)."""
    tree = html.fromstring(cleaned_html)
    counter = 0
    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        element.set("data-aid", f"e{counter}")
        counter += 1
    annotated = etree.tostring(tree, encoding="unicode", method="html")
    return annotated, tree


def resolve_aid(tree, aid: str):
    """Find element by data-aid value."""
    results = tree.xpath(f'//*[@data-aid="{aid}"]')
    return results[0] if results else None


def get_element_text(element) -> str:
    """Get text content of element, truncated to 100 chars."""
    text = element.text_content().strip()
    if len(text) > 100:
        return text[:100] + "..."
    return text


def get_sibling_elements(element, container_element) -> list:
    """
    For list pages: given one item element inside a container,
    find all sibling elements that share the same tag and similar class.
    """
    if container_element is None:
        parent = element.getparent()
        if parent is None:
            return []
    else:
        parent = container_element.getparent()
        if parent is None:
            return []

    tag = container_element.tag if container_element is not None else element.tag
    target_class = (container_element if container_element is not None else element).get("class", "")

    siblings = []
    for child in parent:
        if not isinstance(child.tag, str):
            continue
        if child.tag == tag:
            child_class = child.get("class", "")
            # Check class similarity
            if target_class and child_class:
                target_tokens = set(target_class.split())
                child_tokens = set(child_class.split())
                if target_tokens & child_tokens:  # Any common class tokens
                    siblings.append(child)
            elif child.tag == tag and not target_class and not child_class:
                siblings.append(child)
    return siblings
