"""
HTML Annotator - adds unique data-aid attributes to every element.
"""

from lxml import etree, html


def annotate_html(cleaned_html: str) -> tuple[str, etree._Element]:
    """Add data-aid to every element. Returns the annotated HTML and parsed tree."""
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
    results = tree.xpath(f'//*[@data-aid="{aid}"]')
    return results[0] if results else None


def get_element_text(element) -> str:
    text = element.text_content().strip()
    if len(text) > 100:
        return text[:100] + "..."
    return text


def get_sibling_elements(element, container_element) -> list:
    """Find sibling elements with the same tag and similar class usage."""
    if container_element is None:
        parent = element.getparent()
        if parent is None:
            return []
    else:
        parent = container_element.getparent()
        if parent is None:
            return []

    tag = container_element.tag if container_element is not None else element.tag
    target = container_element if container_element is not None else element
    target_class = target.get("class", "")

    siblings = []
    for child in parent:
        if not isinstance(child.tag, str):
            continue
        if child.tag != tag:
            continue
        child_class = child.get("class", "")
        if target_class and child_class:
            if set(target_class.split()) & set(child_class.split()):
                siblings.append(child)
        elif not target_class and not child_class:
            siblings.append(child)
    return siblings
