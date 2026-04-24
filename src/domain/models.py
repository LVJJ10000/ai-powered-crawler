from dataclasses import dataclass, field


@dataclass
class RunConfig:
    start_url: str
    output_path: str
    max_pages: int
    max_list_pages: int
    use_playwright: bool = False


@dataclass
class XPathCandidate:
    xpath: str
    confidence: float = 0.5
    reason: str = ""


@dataclass
class XPathCandidateEvaluation:
    candidate: XPathCandidate
    urls: list[str] = field(default_factory=list)
    basic_valid_ratio: float = 0.0
    pattern_coverage: float = 0.0
    top_pattern_support: float = 0.0
    score: float = 0.0


@dataclass
class PatternModel:
    segment_schema: list[str] = field(default_factory=list)
    pattern_counts: dict[str, int] = field(default_factory=dict)
    total_urls: int = 0


@dataclass
class SelectedLinksResult:
    selected_urls: list[str] = field(default_factory=list)
    selected_xpaths: list[str] = field(default_factory=list)
    evaluations: list[XPathCandidateEvaluation] = field(default_factory=list)

