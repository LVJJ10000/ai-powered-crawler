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
