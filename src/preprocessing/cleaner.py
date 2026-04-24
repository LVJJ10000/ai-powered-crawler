"""
HTML Cleaner - removes noise elements to prepare for AI analysis.
"""

import re
from lxml import html, etree
from config import MAX_HTML_SIZE


def clean_html(raw_html: str) -> str:
    """Clean HTML by removing noise elements."""
    tree = html.fromstring(raw_html)

    # 1. Remove tags: script, style, noscript, svg, iframe, link[rel=stylesheet]
    _remove_tags(tree, ["script", "style", "noscript", "svg", "iframe"])
    for el in tree.xpath("//link[@rel='stylesheet']"):
        _strip_element(el)

    # 2. Remove hidden elements
    for el in tree.xpath("//*[@style]"):
        style = el.get("style", "")
        if "display:none" in style or "display: none" in style:
            _strip_element(el)
    for el in tree.xpath("//*[@aria-hidden='true']"):
        _strip_element(el)
    for el in tree.xpath("//*[@hidden]"):
        _strip_element(el)

    # 3. Remove nav, footer, header (but keep if removing leaves too little content)
    for tag in ["nav", "footer", "header"]:
        elements = tree.xpath(f"//{tag}")
        if elements:
            # Check if removing would leave enough content
            backup = etree.tostring(tree, encoding="unicode")
            for el in elements:
                _strip_element(el)
            remaining = etree.tostring(tree, encoding="unicode")
            remaining_text = html.fromstring(remaining).text_content()
            if len(remaining_text.strip()) < 500:
                # Restore - too much removed
                tree = html.fromstring(backup)

    # 4. Remove all comments
    for comment in tree.xpath("//comment()"):
        parent = comment.getparent()
        if parent is not None:
            parent.remove(comment)

    # 5. Remove empty elements recursively
    _remove_empty_elements(tree)

    # 6. Strip style attributes
    for el in tree.xpath("//*[@style]"):
        del el.attrib["style"]

    # 7. Strip SVG data URIs
    for el in tree.xpath("//*[@src]"):
        src = el.get("src", "")
        if src.startswith("data:image/svg+xml"):
            el.set("src", "")

    # 8. Truncate long attribute values
    for el in tree.iter():
        if not isinstance(el.tag, str):
            continue
        for attr_name, attr_value in list(el.attrib.items()):
            if len(attr_value) > 100:
                el.set(attr_name, attr_value[:100] + "...")

    # 9. Serialize
    result = etree.tostring(tree, encoding="unicode", method="html")

    # 10. Truncate if too large
    if len(result) > MAX_HTML_SIZE:
        result = _truncate_html(tree, result)

    return result


def _remove_tags(tree, tags: list[str]):
    """Remove all elements with specified tags."""
    for tag in tags:
        for el in tree.xpath(f"//{tag}"):
            _strip_element(el)


def _strip_element(element):
    """Remove element from tree."""
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _is_empty(element) -> bool:
    """Check if element has no meaningful text content."""
    if not isinstance(element.tag, str):
        return False
    # Keep elements with certain tags
    if element.tag in ("img", "input", "br", "hr", "meta", "link"):
        return False
    text = element.text_content().strip()
    if text:
        return False
    # Check if has meaningful children
    for child in element:
        if isinstance(child.tag, str) and child.tag in ("img", "input"):
            return False
    return True


def _remove_empty_elements(tree):
    """Remove empty elements recursively."""
    changed = True
    while changed:
        changed = False
        for el in tree.iter():
            if not isinstance(el.tag, str):
                continue
            if el.tag in ("html", "body", "head"):
                continue
            if _is_empty(el) and len(el) == 0:
                parent = el.getparent()
                if parent is not None:
                    parent.remove(el)
                    changed = True


def _detect_repeating_containers(tree) -> list:
    """Find sibling groups with same tag+class (potential list items)."""
    results = []
    for parent in tree.iter():
        if not isinstance(parent.tag, str):
            continue
        groups = {}
        for child in parent:
            if not isinstance(child.tag, str):
                continue
            key = f"{child.tag}.{child.get('class', '')}"
            if key not in groups:
                groups[key] = []
            groups[key].append(child)
        for key, children in groups.items():
            if len(children) >= 3:
                results.append((parent, children, key))
    return results


def _truncate_html(tree, current_html: str) -> str:
    """Truncate HTML to fit within MAX_HTML_SIZE."""
    # Strategy 1: Truncate repeating containers
    containers = _detect_repeating_containers(tree)
    for parent, children, key in containers:
        if len(children) > 3:
            for child in children[3:]:
                parent.remove(child)
            # Add comment about truncated items
            comment = etree.Comment(f" truncated {len(children) - 3} items ")
            parent.append(comment)

    result = etree.tostring(tree, encoding="unicode", method="html")
    if len(result) <= MAX_HTML_SIZE:
        return result

    # Strategy 2: Simply truncate
    return result[:MAX_HTML_SIZE]
