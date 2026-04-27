from dataclasses import dataclass, field

from domain.crawl_entities import CrawlRequest as RunConfig
from domain.crawl_entities import LinkCandidate as XPathCandidate
from domain.crawl_entities import LinkSelection as SelectedLinksResult
from models.schemas import CrawlConfig, PageData


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
class ListDiscoveryResult:
    detail_urls: list[str] = field(default_factory=list)
    selected_xpaths: list[str] = field(default_factory=list)


@dataclass
class DetailLayerResult:
    records: list[PageData] = field(default_factory=list)
    next_detail_urls: list[str] = field(default_factory=list)
    export_config: CrawlConfig | None = None
    config_cache: dict[str, CrawlConfig] = field(default_factory=dict)


@dataclass
class TraversalResult:
    records: list[PageData] = field(default_factory=list)
    export_config: CrawlConfig | None = None
    detail_urls: list[str] = field(default_factory=list)
