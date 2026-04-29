class DomainError(Exception):
    """Base error for domain layer failures."""


class AnalysisError(DomainError):
    """Raised when analysis entities or flows are invalid."""


class InvalidStartPageError(AnalysisError):
    """Base error for invalid start-page analysis outcomes."""


class MissingLinkCandidatesError(InvalidStartPageError):
    def __init__(self):
        super().__init__("missing_link_candidates")


class MissingDetailFieldsError(InvalidStartPageError):
    def __init__(self):
        super().__init__("missing_detail_fields")


class ExtractionError(DomainError):
    """Raised when extraction entities or flows are invalid."""


class PaginationError(DomainError):
    """Raised when pagination entities or flows are invalid."""


class MissingApiKeyError(DomainError):
    def __init__(self):
        super().__init__("OPENAI_API_KEY is not set")
