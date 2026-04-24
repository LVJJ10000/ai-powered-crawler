# Depth Traversal Design

## Summary

Add a `--depth` runtime parameter to control how many traversal levels the crawler follows from the start page.

`depth` is a traversal-level limit, not a pagination limit:

- A start page is depth `1`.
- `list -> detail` moves to depth `2`.
- `detail -> detail` moves one depth level deeper each time.
- Pagination does not consume depth and remains controlled by `--max-list-pages`.

The default `depth` is `2`.

## Goals

- Add `--depth` to the CLI and runtime config with a default of `2`.
- Support list-start runs that stop at discovery mode when `depth=1`.
- Support detail-start runs that extract the start detail page at `depth=1`.
- Support breadth-first traversal of deeper `detail -> detail` levels up to the configured depth.
- Keep `--max-pages` as the global cap on extracted detail pages across all depth levels.
- Preserve the existing JSON output shape for normal extraction runs.

## Non-Goals

- Redefining pagination behavior.
- Adding recursive traversal through arbitrary list-to-list links beyond existing pagination flow.
- Changing the AI analysis prompts or the field extraction format.
- Refactoring unrelated services or export structures beyond what `depth=1` discovery mode requires.

## User-Facing Behavior

### CLI

Add a new optional CLI parameter:

```bash
--depth
```

Rules:

- Type: integer
- Default: `2`
- Minimum valid value: `1`

Examples:

- List start + `--depth 1`: discover detail URLs from the list layer and export those URLs without extracting detail records.
- List start + `--depth 2`: discover detail URLs from the list layer, then extract those detail pages.
- Detail start + `--depth 1`: extract only the start detail page.
- Detail start + `--depth 2`: extract the start detail page and then its discovered sub-detail pages.

### Depth Semantics

Depth is counted by traversal level:

- Depth `1` is always the start page layer.
- Following discovered detail links increments depth by `1`.
- Paginated list pages stay within the same list depth layer and do not increment depth.

### Interaction With Existing Limits

- `--max-list-pages` still limits how many paginated list pages are followed.
- `--max-pages` still limits the total number of extracted detail pages across the entire run.
- `--depth` only controls how many traversal layers may be followed.
- When a depth layer contains more candidate detail URLs than the remaining `--max-pages` budget allows, only the first budgeted subset should be fetched and extracted from that layer.

## Architecture

### Recommended Structure

Introduce a new traversal coordinator owned by the orchestrator.

Responsibilities:

- Track queued URLs with their depth.
- Process traversal breadth-first by depth level.
- Enforce the global `max_pages` budget.
- Maintain a visited set for followed detail URLs.
- Decide when traversal stops because of `depth`, `max_pages`, or URL exhaustion.

This keeps page-type-specific logic narrow:

- List handling discovers detail URLs from the list layer.
- Detail handling extracts detail records and discovers candidate sub-detail URLs.
- Traversal policy lives in one place instead of being split across CLI, orchestrator, and both pipelines.

### Component Boundaries

#### CLI and Config

Update:

- `src/app/cli.py`
- `src/domain/models.py`

Changes:

- Parse `--depth`.
- Add `depth: int` to `RunConfig`.
- Validate that `depth >= 1`.

#### Orchestrator

Update:

- `src/app/orchestrator.py`

Changes:

- Keep start-page fetch and initial page-type analysis.
- Delegate subsequent traversal work to the new traversal coordinator.
- Preserve the existing export handoff pattern.

#### Traversal Coordinator

Add:

- `src/services/traversal_coordinator.py` or equivalent under `src/services/`

Responsibilities:

- Accept the analyzed start page context and `RunConfig`.
- For list starts:
  - paginate list pages
  - discover and dedupe detail URLs
  - stop at discovery mode when `depth=1`
  - otherwise enqueue detail URLs at depth `2`
- For detail starts:
  - enqueue the start detail URL at depth `1`
- For each detail depth layer:
  - fetch queued detail pages
  - extract records
  - decrement the remaining `max_pages` budget
  - discover next-layer sub-detail URLs if current depth is below the configured limit

#### Pipelines and Services

List and detail logic should remain specialized rather than recursive.

Desired responsibilities:

- List-side logic returns discovered detail URLs and the best export config for the detail shape when available.
- Detail-side logic processes a single depth layer and returns:
  - extracted records
  - the detail config used
  - next-layer candidate URLs

The pipelines should not own traversal recursion.

#### Exporter

Update:

- `src/storage/exporter.py`

Changes:

- Add support for an optional top-level `detail_urls` field.
- Preserve current fields for normal extraction runs.

## Data Flow

### List Start

1. Fetch and analyze the start page.
2. Follow pagination up to `--max-list-pages`.
3. Evaluate list-page link XPath candidates and collect detail URLs.
4. Dedupe the discovered detail URLs.
5. If `depth=1`, export discovery output and stop.
6. If `depth>=2`, enqueue discovered detail URLs at depth `2`.
7. Traverse detail levels breadth-first until the `depth` limit, `max_pages` limit, or URL exhaustion is reached.

### Detail Start

1. Fetch and analyze the start page.
2. Enqueue the start detail URL at depth `1`.
3. Extract the queued detail layer.
4. If current depth is below `--depth`, discover sub-detail URLs and enqueue the next unseen layer.
5. Continue breadth-first until limits are reached.

### Breadth-First Traversal

Breadth-first traversal is preferred over recursive depth-first traversal because it gives `depth` a clear level-based meaning and makes `max_pages` enforcement more predictable across sibling URLs discovered at the same level.

## Output Contract

### Normal Extraction Runs

Preserve the current JSON shape:

- `source_url`
- `page_type`
- `total_records`
- `fields_definition`
- `pages`

In these runs, `pages` remains the extracted detail-record output.

### Discovery Mode

Discovery mode applies only when:

- the start page is a list page
- `depth=1`

Output rules:

- `page_type` remains `list`
- `total_records` is `0`
- `fields_definition` is an empty list
- `pages` is an empty list
- `detail_urls` is a top-level list containing the discovered detail URLs

Example shape:

```json
{
  "source_url": "https://example.com/list",
  "page_type": "list",
  "total_records": 0,
  "fields_definition": [],
  "pages": [],
  "detail_urls": [
    "https://example.com/detail/1",
    "https://example.com/detail/2"
  ]
}
```

Normal extraction runs should omit `detail_urls` unless the implementation later chooses to expose it as optional debug metadata.

## Caching and Reuse

The traversal coordinator may cache analyzed detail configs by domain during one run so deeper detail layers can reuse extraction structure instead of re-analyzing every page template from scratch.

This is an implementation optimization, not a user-visible requirement. The design should allow it without making it mandatory for the first iteration.

## Error Handling

- If a list start produces no detail URLs, export an empty result rather than exiting with an error.
- If a detail page fails during traversal, log the failure and continue processing the rest of the queued layer.
- Duplicate discovered URLs should be filtered by the visited set without user-visible noise.
- If a depth layer contains more queued URLs than the remaining `max_pages` budget, trim the layer to the budgeted subset before fetching. After that subset is processed, stop traversal and do not enqueue another depth layer.
- Invalid `depth` values should fail fast during CLI argument handling.

## Testing

Add or update tests to cover:

- CLI parsing for default `depth=2`
- CLI parsing for explicit `--depth`
- validation failure for `depth < 1`
- propagation of `depth` into `RunConfig`
- list start with `depth=1` exporting `detail_urls` and no records
- list start with `depth=2` extracting first-layer detail pages
- detail start with `depth=1` extracting only the start detail page
- detail start with `depth=2` including sub-detail pages
- pagination not consuming depth
- `max_pages` capping total extracted detail pages across all depth levels
- exporter including `detail_urls` only for discovery mode

## Implementation Notes

- Prefer adding the new traversal coordinator instead of embedding recursion into `ListPipeline` or `DetailPipeline`.
- Keep existing page analysis and extraction APIs recognizable where possible to minimize unrelated regressions.
- Avoid changing the on-disk JSON contract for normal extraction users beyond the optional `detail_urls` addition in discovery mode.

## Open Decisions Resolved

- `depth` is traversal-level based, not pagination-based.
- Pagination does not consume depth.
- Default `depth` is `2`.
- `max_pages` remains the global extracted-detail cap.
- List start + `depth=1` exports discovered detail URLs at top level via `detail_urls`.
- Detail start + `depth=1` extracts only the start detail page.
- Deeper detail traversal proceeds breadth-first through `detail -> detail` levels.
