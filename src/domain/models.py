from dataclasses import dataclass, field

from domain.crawl_entities import CrawlRequest as RunConfig
from domain.crawl_entities import LinkCandidate as XPathCandidate
from domain.crawl_entities import LinkCandidateEvaluation as XPathCandidateEvaluation
from domain.crawl_entities import LinkSelection as SelectedLinksResult
from domain.crawl_entities import PatternModel
from models.schemas import CrawlConfig, PageData


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
