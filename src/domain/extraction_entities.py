from dataclasses import asdict, dataclass, field

from domain.analysis_entities import ExtractType, PageType, PaginationType


class _CompatDataclassMixin:
    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class FieldDefinition(_CompatDataclassMixin):
    name: str
    description: str
    xpath: str
    confidence: float
    extract: ExtractType
    fallback_xpath: str | None = None
    attribute_name: str | None = None
    sample_value: str | None = None


@dataclass
class CrawlPlan(_CompatDataclassMixin):
    page_type: PageType
    fields: list[FieldDefinition] = field(default_factory=list)
    container_xpath: str | None = None
    pagination_xpath: str | None = None
    pagination_type: PaginationType | None = None


@dataclass
class ExtractionRecord(_CompatDataclassMixin):
    url: str
    data: dict[str, str | None]
