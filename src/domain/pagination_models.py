from dataclasses import dataclass, field
from enum import Enum


class PaginationMode(str, Enum):
    AUTO = "auto"
    LINK = "link"
    CLICK = "click"
    LOAD_MORE = "load_more"
    INFINITE_SCROLL = "infinite_scroll"


class StopReason(str, Enum):
    MAX_ROUNDS = "MAX_ROUNDS"
    NO_PROGRESS_LIMIT = "NO_PROGRESS_LIMIT"
    NO_STRATEGY_ADVANCED = "NO_STRATEGY_ADVANCED"
    TARGET_REACHED = "TARGET_REACHED"


@dataclass
class PaginationConfig:
    max_rounds: int
    max_no_progress_rounds: int = 2
    max_target_pages: int = 10
    strategy_order: list[PaginationMode] = field(
        default_factory=lambda: [
            PaginationMode.LINK,
            PaginationMode.CLICK,
            PaginationMode.LOAD_MORE,
            PaginationMode.INFINITE_SCROLL,
        ]
    )


@dataclass
class ProgressSnapshot:
    url: str
    html_fingerprint: str
    anchor_count: int


@dataclass
class StrategyResult:
    strategy: PaginationMode
    advanced: bool
    next_url: str | None = None
    reason: str = ""
    candidate_count: int = 0


@dataclass
class PaginationRoundTrace:
    round_index: int
    strategy: str
    candidate_count: int
    selected_target: str | None
    progress: bool
    reason: str
    total_pages: int


@dataclass
class PaginationResult:
    pages: list[tuple[str, str]]
    stop_reason: StopReason
    traces: list[PaginationRoundTrace]

