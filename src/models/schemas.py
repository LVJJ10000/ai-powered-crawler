from pydantic import BaseModel
from typing import Optional
from enum import Enum


class PageType(str, Enum):
    LIST = "list"
    DETAIL = "detail"


class ExtractType(str, Enum):
    TEXT = "text"
    ATTRIBUTE = "attribute"


class AttrClassification(str, Enum):
    STABLE = "stable"
    RANDOM = "random"
    BUSINESS = "business"
    BUSINESS_CATEGORY = "business_category"
    CONDITIONAL = "conditional"
    UNKNOWN = "unknown"


class PaginationType(str, Enum):
    LINK = "link"
    LOAD_MORE = "load_more"
    INFINITE_SCROLL = "infinite_scroll"


# --- Prompt A output ---

class FieldInfo(BaseModel):
    name: str
    aid: str
    extract: ExtractType
    attribute_name: Optional[str] = None
    description: str


class PaginationInfo(BaseModel):
    next_aid: Optional[str] = None
    type: Optional[PaginationType] = None


class AnalysisResult(BaseModel):
    page_type: PageType
    container_aid: Optional[str] = None
    fields: list[FieldInfo]
    pagination: Optional[PaginationInfo] = None


class PageTypeDetectionResult(BaseModel):
    page_type: PageType
    confidence: float
    reason: Optional[str] = None


class DetailLinkXPathCandidate(BaseModel):
    xpath: str
    confidence: float = 0.5
    reason: Optional[str] = None


class ListFieldAnalysisResult(BaseModel):
    page_type: PageType
    container_aid: Optional[str] = None
    primary_detail_link_xpath: Optional[str] = None
    detail_link_xpath_candidates: list[DetailLinkXPathCandidate] = []
    pagination: Optional[PaginationInfo] = None


class DetailFieldAnalysisResult(BaseModel):
    page_type: PageType
    fields: list[FieldInfo]


# --- Attribute classification ---

class ClassifiedAttribute(BaseModel):
    attr_name: str
    attr_value: str
    classification: AttrClassification


class ClassifiedClassToken(BaseModel):
    token: str
    classification: AttrClassification


class ClassifiedElement(BaseModel):
    tag: str
    text_sample: str = ""
    attributes: list[ClassifiedAttribute]
    class_tokens: list[ClassifiedClassToken] = []
    ancestor_chain: list[dict] = []       # list of {tag, attributes, class_tokens}
    prev_sibling: Optional[dict] = None
    next_sibling: Optional[dict] = None


# --- Prompt B output ---

class XPathResult(BaseModel):
    xpath: str
    strategy: str
    confidence: float
    fallback_xpath: Optional[str] = None
    attributes_used: list[str] = []


# --- Crawl configuration ---

class FieldXPath(BaseModel):
    name: str
    description: str
    xpath: str                              # relative to container (for list) or absolute (for detail)
    fallback_xpath: Optional[str] = None
    confidence: float
    extract: ExtractType
    attribute_name: Optional[str] = None
    sample_value: Optional[str] = None      # for healing context


class CrawlConfig(BaseModel):
    page_type: PageType
    container_xpath: Optional[str] = None   # for list pages
    fields: list[FieldXPath]
    pagination_xpath: Optional[str] = None
    pagination_type: Optional[PaginationType] = None


# --- Health tracking ---

class FieldHealth(BaseModel):
    name: str
    recent_results: list[Optional[str]] = []  # last N extraction values (None = failed)
    heal_attempts: int = 0
    sample_values: list[str] = []             # last N successful values for healing context


# --- Output ---

class PageData(BaseModel):
    url: str
    data: dict[str, Optional[str]]


class CrawlOutput(BaseModel):
    source_url: str
    page_type: str
    total_pages: int
    fields_definition: list[dict]
    pages: list[PageData]
