# Playwright Pagination Redesign

## Summary

Redesign list-page pagination for `--use-playwright` runs so pagination is driven by a live browser session instead of URL inference from static HTML.

The new design introduces a Playwright-first pagination engine for list pages that:

- keeps one browser page alive for the full pagination session
- advances the list by browser actions instead of guessed next URLs
- trusts AI-provided `pagination_xpath` when present
- falls back to scrolling by one viewport when no usable control is available
- preserves every successful list state as a snapshot, even when the URL does not change

This is a stronger long-term architecture for modern sites that use JS-driven next buttons, load-more controls, infinite scroll, or virtualized lists.

## Goals

- Replace Playwright list pagination's URL-centric behavior with a live-session action model.
- Keep non-Playwright pagination on the existing engine.
- Support same-page pagination progress when URL does not change.
- Treat each successful click or screen scroll as one consumed `max_list_pages` slot.
- Preserve successful list snapshots so downstream detail-link discovery can inspect the full pagination history.
- Handle virtualized lists where older items disappear from the DOM while new items become visible.
- Keep the rest of the crawler compatible with the existing `(url, html)` pagination result shape.

## Non-Goals

- Redesigning detail-page fetching or extraction around browser sessions.
- Adding generic DOM-text/class heuristics for pagination-control discovery.
- Changing AI prompts or field-extraction formats beyond what current pagination hints already provide.
- Replacing the non-Playwright pagination engine.
- Expanding scope into unrelated crawler refactors.

## User-Facing Behavior

### Scope

This redesign applies only when:

- `--use-playwright` is enabled
- the crawler is paginating list pages

Non-Playwright runs continue using the current URL-based pagination flow.

### Pagination Behavior

For Playwright list runs:

- the crawler opens the start URL once in a live browser page
- each pagination round performs exactly one browser action
- successful actions produce an additional list snapshot
- snapshots may repeat the same URL when the page changes in place

### Action Policy

The Playwright path uses this priority order:

1. If AI provided `pagination_xpath` and it resolves to a visible, enabled control at runtime, use it.
2. If AI provided `pagination_xpath` but it does not resolve to a usable control at runtime, fall back to scrolling.
3. If AI did not provide `pagination_xpath`, fall back to scrolling.

Explicitly out of scope:

- generic DOM heuristics for finding "next" or "load more" controls
- static next-URL guessing in the Playwright path

### Interaction With Existing Limits

- `max_list_pages` remains the cap on list-pagination progress.
- The initial page counts as the first list snapshot, matching current behavior.
- Each additional successful click or successful screen scroll consumes one list-page slot.
- Failed actions do not consume a successful slot, but they do count toward the no-progress stop limit.

## Architecture

### Recommended Structure

Keep `PaginationService.follow()` as the entry point, but split execution into two engines:

- existing URL-based engine for non-Playwright runs
- new Playwright session engine for Playwright list runs

This avoids forcing the current URL-based design to absorb same-page browser actions and snapshot-history concerns.

### Component Boundaries

#### Pagination Service

Update:

- `src/services/pagination_service.py`

Responsibilities:

- choose the pagination engine based on the active fetch/runtime mode
- keep the public pagination API stable for the list pipeline

#### Playwright Pagination Engine

Add:

- `src/services/playwright_pagination_engine.py` or equivalent

Responsibilities:

- own one browser page for the entire list-pagination run
- navigate to the start URL once
- capture ordered pagination snapshots
- choose and execute browser actions
- wait for navigation or same-page content updates
- enforce stop conditions

#### Playwright Pagination Actions

Add a small action layer instead of reusing URL-returning strategies.

Responsibilities:

- inspect the live browser page using the AI-provided `pagination_xpath`
- decide whether the next action is:
  - click control
  - scroll one viewport
- perform only one action per round

The action layer should not guess next URLs.

#### Page Fetcher

Update:

- `src/crawler/fetcher.py`

Responsibilities:

- keep existing one-shot fetch behavior for ordinary fetches
- expose a Playwright session helper for pagination instead of making `fetch()` itself stateful

This keeps browser-session complexity local to pagination.

#### Progress Detector

Update:

- `src/services/progress_detector.py`

Responsibilities:

- continue supporting the current URL-based engine
- add Playwright-oriented progress detection for same-URL, same-session list updates

#### Pagination Result

Preserve the existing high-level output shape:

- ordered `pages` snapshots as `(url, html)` pairs

Behavioral update:

- repeated URLs are valid in Playwright pagination results when the DOM changes in place

## Runtime Flow

### Session Lifecycle

1. Open a Playwright browser page.
2. Navigate to the list start URL once.
3. Wait for the initial rendered state.
4. Capture the first snapshot as `(page.url, page.content())`.
5. Repeat pagination rounds until a stop condition is reached.
6. Close the browser page when the pagination run completes.

### Per-Round Flow

1. Inspect the current live page.
2. Decide one action for the round:
   - click the AI-selected pagination control if usable
   - otherwise scroll down by one viewport
3. Perform the action.
4. Wait for either:
   - navigation
   - meaningful same-page update
   - bounded timeout
5. Capture the resulting page state.
6. Evaluate whether the new state represents meaningful progress.
7. If progress occurred, append a new snapshot.
8. If not, record a no-progress round.

### Stop Conditions

Stop when any of these happens:

- the successful snapshot count reaches `max_list_pages`
- the no-progress limit is reached
- the page can no longer be advanced by usable control click or scroll fallback

## Progress Model

### Why DOM Growth Alone Is Not Enough

Virtualized lists may remove older items from the DOM while exposing newer ones. In those cases:

- DOM size may stay flat
- anchor count may stay flat
- old elements may disappear

but the crawler is still making real pagination progress.

### Required Progress Rule

For Playwright pagination, progress means the page exposes meaningfully new list content after one action.

Acceptable indicators include:

- changed rendered content fingerprint
- newly visible link targets or content blocks
- navigation to a new page state

Progress must not require total DOM growth.

### Snapshot Preservation

Every successful progress round should be stored as a separate snapshot, even if:

- the URL is unchanged
- older content has disappeared from the live DOM

This ensures downstream detail-link discovery can inspect earlier and later list states together.

## Detail-Link Discovery Implications

The list pipeline should continue receiving ordered list snapshots.

Required behavior:

- evaluate detail-link candidates across the full snapshot history
- globally dedupe discovered detail URLs across all snapshots

This is essential for scroll-driven and virtualized pages where the final DOM may not contain items seen earlier.

## Error Handling

- If the Playwright session cannot start or the start page cannot load, fail the pagination run as a fetch/runtime error.
- If `pagination_xpath` exists but the element is not visible or not clickable at runtime, treat that as "no usable control" and fall back to scrolling.
- If a click or scroll action completes without meaningful progress, record a no-progress round.
- If waiting for navigation or same-page update times out and the resulting state is not meaningfully different, record a no-progress round.
- Keep the existing no-progress stop behavior so dead-end pagination exits cleanly.
- Do not attempt generic selector guessing when the AI selector is missing or unusable.

## Testing

Add or update tests to cover:

- pagination-service routing between URL-based and Playwright-based engines
- Playwright pagination preserving multiple snapshots with the same URL
- successful AI-selector click progress
- AI selector present but unusable at runtime, then scroll fallback succeeds
- no AI selector, scroll fallback succeeds
- control/scroll attempts with no meaningful progress hitting the no-progress limit
- virtualized-list behavior where old items disappear and new items appear
- list-pipeline detail-link discovery across full snapshot history
- global dedupe of detail URLs across repeated or overlapping snapshots
- `max_list_pages` counting successful clicks and successful scrolls consistently

## Implementation Notes

- Keep the non-Playwright engine unchanged except for any shared model adjustments needed to allow repeated URLs in pagination results.
- Prefer adding a new Playwright-specific engine over heavily branching the current engine.
- Keep the public list-pipeline contract stable so this refactor stays contained.

## Open Decisions Resolved

- Long-term direction: use the stronger Playwright architecture, not the minimal patch.
- Control selection: trust AI-provided `pagination_xpath`.
- Generic heuristics: do not use them.
- Scroll fallback: use it only when there is no usable control at runtime.
- Scroll semantics: treat the page as one continuously updated page.
- Progress semantics: accept meaningful content change, not just DOM growth.
- Virtualized lists: preserve snapshot history and dedupe detail URLs globally.
