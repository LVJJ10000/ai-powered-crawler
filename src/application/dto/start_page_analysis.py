from dataclasses import dataclass, field

from domain.analysis_entities import PageType
from domain.crawl_entities import LinkCandidate
from domain.extraction_entities import CrawlPlan


@dataclass
class StartPageAnalysis:
    page_type: PageType
    crawl_plan: CrawlPlan
    link_candidates: list[LinkCandidate] = field(default_factory=list)
