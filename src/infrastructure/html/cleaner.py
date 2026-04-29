"""
HTML Cleaner - removes noise elements to prepare for AI analysis.
"""

from lxml import etree, html

from config import MAX_HTML_SIZE


def clean_html(raw_html: str) -> str:
    """Clean HTML by removing noise elements."""
    tree = html.fromstring(raw_html)

    _remove_tags(tree, ["script", "style", "noscript", "svg", "iframe"])
    for element in tree.xpath("//link[@rel='stylesheet']"):
        _strip_element(element)

    for element in tree.xpath("//*[@style]"):
        style = element.get("style", "")
        if "display:none" in style or "display: none" in style:
            _strip_element(element)
    for element in tree.xpath("//*[@aria-hidden='true']"):
        _strip_element(element)
    for element in tree.xpath("//*[@hidden]"):
        _strip_element(element)

    for tag in ["nav", "footer", "header"]:
        elements = tree.xpath(f"//{tag}")
        if not elements:
            continue

        backup = etree.tostring(tree, encoding="unicode")
        for element in elements:
            _strip_element(element)
        remaining = etree.tostring(tree, encoding="unicode")
        remaining_text = html.fromstring(remaining).text_content()
        if len(remaining_text.strip()) < 500:
            tree = html.fromstring(backup)

    for comment in tree.xpath("//comment()"):
        parent = comment.getparent()
        if parent is not None:
            parent.remove(comment)

    _remove_empty_elements(tree)

    for element in tree.xpath("//*[@style]"):
        del element.attrib["style"]

    for element in tree.xpath("//*[@src]"):
        src = element.get("src", "")
        if src.startswith("data:image/svg+xml"):
            element.set("src", "")

    for element in tree.iter():
        if not isinstance(element.tag, str):
            continue
        for attr_name, attr_value in list(element.attrib.items()):
            if len(attr_value) > 100:
                element.set(attr_name, attr_value[:100] + "...")

    result = etree.tostring(tree, encoding="unicode", method="html")
    if len(result) > MAX_HTML_SIZE:
        result = _truncate_html(tree)
    return result


def _remove_tags(tree, tags: list[str]) -> None:
    for tag in tags:
        for element in tree.xpath(f"//{tag}"):
            _strip_element(element)


def _strip_element(element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _is_empty(element) -> bool:
    if not isinstance(element.tag, str):
        return False
    if element.tag in ("img", "input", "br", "hr", "meta", "link"):
        return False
    if element.text_content().strip():
        return False
    for child in element:
        if isinstance(child.tag, str) and child.tag in ("img", "input"):
            return False
    return True


def _remove_empty_elements(tree) -> None:
    changed = True
    while changed:
        changed = False
        for element in tree.iter():
            if not isinstance(element.tag, str):
                continue
            if element.tag in ("html", "body", "head"):
                continue
            if _is_empty(element) and len(element) == 0:
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
                    changed = True


def _detect_repeating_containers(tree) -> list[tuple[object, list[object], str]]:
    results = []
    for parent in tree.iter():
        if not isinstance(parent.tag, str):
            continue
        groups: dict[str, list[object]] = {}
        for child in parent:
            if not isinstance(child.tag, str):
                continue
            key = f"{child.tag}.{child.get('class', '')}"
            groups.setdefault(key, []).append(child)
        for key, children in groups.items():
            if len(children) >= 3:
                results.append((parent, children, key))
    return results


def _truncate_html(tree) -> str:
    for parent, children, _key in _detect_repeating_containers(tree):
        if len(children) <= 3:
            continue
        for child in children[3:]:
            parent.remove(child)
        parent.append(etree.Comment(f" truncated {len(children) - 3} items "))

    result = etree.tostring(tree, encoding="unicode", method="html")
    if len(result) <= MAX_HTML_SIZE:
        return result
    return result[:MAX_HTML_SIZE]
