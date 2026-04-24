import logging
from dataclasses import dataclass, field

from domain.pagination_models import (
    PaginationConfig,
    PaginationMode,
    PaginationResult,
    PaginationRoundTrace,
    StopReason,
)
from services.pagination_strategies import (
    ClickNextStrategy,
    InfiniteScrollStrategy,
    LinkNextStrategy,
    LoadMoreStrategy,
    PaginationContext,
)
from services.progress_detector import ProgressDetector

logger = logging.getLogger(__name__)


@dataclass
class PaginationState:
    pages: list[tuple[str, str]] = field(default_factory=list)
    visited: set[str] = field(default_factory=set)
    no_progress_rounds: int = 0
    traces: list[PaginationRoundTrace] = field(default_factory=list)


class PaginationEngine:
    def __init__(self, fetcher, progress_detector: ProgressDetector):
        self.fetcher = fetcher
        self.progress_detector = progress_detector
        self._strategy_registry = {
            PaginationMode.LINK: LinkNextStrategy(),
            PaginationMode.CLICK: ClickNextStrategy(),
            PaginationMode.LOAD_MORE: LoadMoreStrategy(),
            PaginationMode.INFINITE_SCROLL: InfiniteScrollStrategy(),
        }

    async def run(
        self,
        start_html: str,
        start_url: str,
        pagination_xpath: str | None,
        pagination_type,
        config: PaginationConfig,
    ) -> PaginationResult:
        state = PaginationState(
            pages=[(start_url, start_html)],
            visited={start_url},
            no_progress_rounds=0,
            traces=[],
        )
        previous_snapshot = self.progress_detector.capture_snapshot(start_url, start_html)

        for round_index in range(1, config.max_rounds + 1):
            if len(state.pages) >= config.max_target_pages:
                return PaginationResult(state.pages, StopReason.TARGET_REACHED, state.traces)
            if state.no_progress_rounds >= config.max_no_progress_rounds:
                return PaginationResult(state.pages, StopReason.NO_PROGRESS_LIMIT, state.traces)

            current_url, current_html = state.pages[-1]
            context = PaginationContext(pagination_xpath=pagination_xpath, pagination_type=pagination_type)

            advanced = False
            for mode in config.strategy_order:
                strategy = self._strategy_registry[mode]
                result = strategy.find_next_url(
                    page_url=current_url,
                    page_html=current_html,
                    context=context,
                    visited=state.visited,
                )
                if not result.advanced or not result.next_url:
                    state.traces.append(
                        PaginationRoundTrace(
                            round_index=round_index,
                            strategy=mode.value,
                            candidate_count=result.candidate_count,
                            selected_target=None,
                            progress=False,
                            reason=result.reason,
                            total_pages=len(state.pages),
                        )
                    )
                    continue

                try:
                    next_html = await self.fetcher.fetch(result.next_url)
                except Exception as exc:
                    logger.debug("Pagination fetch failed for %s: %s", result.next_url, exc)
                    state.traces.append(
                        PaginationRoundTrace(
                            round_index=round_index,
                            strategy=mode.value,
                            candidate_count=result.candidate_count,
                            selected_target=result.next_url,
                            progress=False,
                            reason=f"fetch_error:{exc}",
                            total_pages=len(state.pages),
                        )
                    )
                    continue

                current_snapshot = self.progress_detector.capture_snapshot(result.next_url, next_html)
                has_progress = self.progress_detector.has_progress(previous_snapshot, current_snapshot)
                if has_progress and result.next_url not in state.visited:
                    state.visited.add(result.next_url)
                    state.pages.append((result.next_url, next_html))
                    previous_snapshot = current_snapshot
                    state.no_progress_rounds = 0
                    advanced = True
                    state.traces.append(
                        PaginationRoundTrace(
                            round_index=round_index,
                            strategy=mode.value,
                            candidate_count=result.candidate_count,
                            selected_target=result.next_url,
                            progress=True,
                            reason=result.reason,
                            total_pages=len(state.pages),
                        )
                    )
                    break

                state.traces.append(
                    PaginationRoundTrace(
                        round_index=round_index,
                        strategy=mode.value,
                        candidate_count=result.candidate_count,
                        selected_target=result.next_url,
                        progress=False,
                        reason="no_progress_after_fetch",
                        total_pages=len(state.pages),
                    )
                )

            if not advanced:
                state.no_progress_rounds += 1

        if state.no_progress_rounds >= config.max_no_progress_rounds:
            stop_reason = StopReason.NO_PROGRESS_LIMIT
        elif len(state.pages) >= config.max_target_pages:
            stop_reason = StopReason.TARGET_REACHED
        else:
            stop_reason = StopReason.MAX_ROUNDS
        if len(state.pages) == 1 and state.no_progress_rounds > 0:
            stop_reason = StopReason.NO_STRATEGY_ADVANCED
        return PaginationResult(state.pages, stop_reason, state.traces)

