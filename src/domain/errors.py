class DomainError(Exception):
    """Base error for domain layer failures."""


class AnalysisError(DomainError):
    """Raised when analysis entities or flows are invalid."""


class InvalidStartPageError(AnalysisError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)

    @classmethod
    def missing_link_candidates(cls):
        return cls("missing_link_candidates")

    @classmethod
    def missing_detail_fields(cls):
        return cls("missing_detail_fields")


class ExtractionError(DomainError):
    """Raised when extraction entities or flows are invalid."""


class PaginationError(DomainError):
    """Raised when pagination entities or flows are invalid."""


class MissingApiKeyError(DomainError):
    def __init__(self):
        super().__init__("OPENAI_API_KEY is not set")
