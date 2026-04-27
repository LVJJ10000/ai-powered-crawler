from domain.pagination_models import PaginationConfig, PaginationResult, PaginationRoundTrace, StopReason


class PlaywrightPaginationEngine:
    def __init__(self, session_factory, progress_detector):
        self.session_factory = session_factory
        self.progress_detector = progress_detector

    async def run(
        self,
        start_url: str,
        pagination_xpath: str | None,
        config: PaginationConfig,
    ) -> PaginationResult:
        session = await self.session_factory(start_url)
        try:
            current_url, current_html = await session.capture_snapshot()
            pages = [(current_url, current_html)]
            traces: list[PaginationRoundTrace] = []
            previous_snapshot = self.progress_detector.capture_snapshot(current_url, current_html)
            no_progress_rounds = 0

            for round_index in range(1, config.max_rounds + 1):
                if len(pages) >= config.max_target_pages:
                    return PaginationResult(pages, StopReason.TARGET_REACHED, traces)
                if no_progress_rounds >= config.max_no_progress_rounds:
                    return PaginationResult(pages, StopReason.NO_PROGRESS_LIMIT, traces)

                used_click = False
                if pagination_xpath:
                    used_click = await session.click_if_possible(pagination_xpath)
                if not used_click:
                    await session.scroll_viewport()

                next_url, next_html = await session.capture_snapshot()
                current_snapshot = self.progress_detector.capture_snapshot(next_url, next_html)
                has_progress = self.progress_detector.has_progress(previous_snapshot, current_snapshot)

                traces.append(
                    PaginationRoundTrace(
                        round_index=round_index,
                        strategy="playwright_click" if used_click else "playwright_scroll",
                        candidate_count=1 if pagination_xpath else 0,
                        selected_target=pagination_xpath if used_click else next_url,
                        progress=has_progress,
                        reason="ai_xpath_click" if used_click else "scroll_fallback",
                        total_pages=len(pages) + (1 if has_progress else 0),
                    )
                )

                if has_progress:
                    pages.append((next_url, next_html))
                    previous_snapshot = current_snapshot
                    no_progress_rounds = 0
                    if len(pages) >= config.max_target_pages:
                        return PaginationResult(pages, StopReason.TARGET_REACHED, traces)
                else:
                    no_progress_rounds += 1

            if no_progress_rounds >= config.max_no_progress_rounds:
                return PaginationResult(pages, StopReason.NO_PROGRESS_LIMIT, traces)
            return PaginationResult(pages, StopReason.MAX_ROUNDS, traces)
        finally:
            await session.close()
