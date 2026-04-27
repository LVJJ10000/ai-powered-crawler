class DomainError(Exception):
    """Base error for domain layer failures."""


class AnalysisError(DomainError):
    """Raised when analysis entities or flows are invalid."""


class ExtractionError(DomainError):
    """Raised when extraction entities or flows are invalid."""


class PaginationError(DomainError):
    """Raised when pagination entities or flows are invalid."""
