from dataclasses import dataclass, field

from domain.extraction_entities import CrawlPlan, ExtractionRecord


@dataclass
class CrawlOutcome:
    records: list[ExtractionRecord] = field(default_factory=list)
    export_plan: CrawlPlan | None = None
    detail_urls: list[str] = field(default_factory=list)


@dataclass
class DetailCrawlResult(CrawlOutcome):
    pass
