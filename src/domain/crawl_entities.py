from dataclasses import dataclass, field


@dataclass
class CrawlRequest:
    start_url: str
    output_path: str
    max_pages: int
    max_list_pages: int
    use_playwright: bool = False
    depth: int = 2


@dataclass
class LinkCandidate:
    xpath: str
    confidence: float = 0.5
    reason: str = ""


@dataclass
class LinkSelection:
    selected_urls: list[str] = field(default_factory=list)
    selected_xpaths: list[str] = field(default_factory=list)
    evaluations: list[object] = field(default_factory=list)
