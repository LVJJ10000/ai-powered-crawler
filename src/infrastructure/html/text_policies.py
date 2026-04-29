import re


def is_long_text_field(field) -> bool:
    text = f"{field.name} {field.description}".lower()
    keywords = ("content", "article", "body", "正文", "内容")
    return any(keyword in text for keyword in keywords)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def merge_text_nodes(nodes) -> str | None:
    parts: list[str] = []
    for node in nodes:
        if hasattr(node, "text_content"):
            text = normalize_text(node.text_content())
        else:
            text = normalize_text(str(node))

        if not text:
            continue
        if parts and text == parts[-1]:
            continue
        parts.append(text)

    if not parts:
        return None

    return "\n".join(parts)


def is_low_quality_content(text: str) -> bool:
    value = text.strip().lower()
    if not value:
        return True

    patterns = (
        "未经许可",
        "请勿转载",
        "版权所有",
        "copyright",
        "all rights reserved",
    )
    return any(pattern in value for pattern in patterns)


def extract_broader_container_text(context, element_xpath: str) -> str | None:
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
        text = normalize_text(elements[0].text_content())
        if text and len(text) >= 80:
            return text
    return None
