"""
URL utilities for consistent link normalization and filtering.
"""

from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit


BLOCKED_PREFIXES = ("javascript:", "mailto:", "tel:", "data:", "#")


def normalize_url(
    raw_url: str | None,
    base_url: str | None = None,
    keep_query: bool = True,
) -> str | None:
    """Resolve to absolute HTTP(S) URL and canonicalize for dedupe."""
    if not raw_url:
        return None

    href = raw_url.strip()
    if not href:
        return None

    if href.lower().startswith(BLOCKED_PREFIXES):
        return None

    absolute = urljoin(base_url, href) if base_url else href
    parts = urlsplit(absolute)

    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None

    query = parts.query if keep_query else ""
    path = parts.path or "/"

    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def get_domain(url: str) -> str:
    """Return normalized netloc for a URL."""
    return urlparse(url).netloc.lower()


def is_same_domain(url: str, domain: str) -> bool:
    """Check if URL belongs to the specified domain."""
    return get_domain(url) == domain.lower()
