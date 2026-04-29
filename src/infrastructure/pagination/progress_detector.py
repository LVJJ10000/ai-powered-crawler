import hashlib

from lxml import html as lhtml

from crawler.url_utils import normalize_url
from domain.pagination_models import ProgressSnapshot


class ProgressDetector:
    def capture_snapshot(self, page_url: str, page_html: str) -> ProgressSnapshot:
        tree = lhtml.fromstring(page_html)
        anchors = tree.xpath("//a[@href]")
        hrefs: list[str] = []
        for anchor in anchors:
            href = anchor.get("href")
            normalized = normalize_url(href, page_url)
            hrefs.append(normalized or href or "")
        main_text = tree.text_content()[:4000]
        fingerprint = hashlib.md5(main_text.encode("utf-8", errors="ignore")).hexdigest()
        href_fingerprint = hashlib.md5("\n".join(hrefs[:200]).encode("utf-8", errors="ignore")).hexdigest()
        return ProgressSnapshot(
            url=page_url,
            html_fingerprint=fingerprint,
            anchor_count=len(anchors),
            href_fingerprint=href_fingerprint,
        )

    def has_progress(self, previous: ProgressSnapshot, current: ProgressSnapshot) -> bool:
        if previous.url != current.url:
            return True
        if previous.html_fingerprint != current.html_fingerprint:
            return True
        if previous.href_fingerprint != current.href_fingerprint:
            return True
        if current.anchor_count > previous.anchor_count:
            return True
        return False
