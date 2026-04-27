# Full `src` Tree OOP Refactor

## Summary

Refactor the entire `src` tree into an explicit object-oriented architecture with four layers:

- `domain`
- `application`
- `infrastructure`
- `interfaces`

The rewrite removes the current mix of procedural helpers, thin service wrappers, direct OpenAI calls, console output in business logic, and ad hoc mutable crawl state. The end state is a crawler whose runtime behavior is driven by cohesive objects with clear ownership, inward-only dependencies, and testable ports.

The user selected a complete refactor of the whole `src` tree rather than a partial or incremental adapter-only cleanup. Although this is a big-bang rewrite in scope, the implementation will still proceed in controlled internal slices so tests can remain useful while the old tree is replaced.

## Goals

- Refactor the whole `src` tree into a consistent OOP design.
- Separate business objects, use-case orchestration, and infrastructure adapters.
- Replace tuple-oriented and function-heavy coordination with explicit domain and application objects.
- Remove `print()` and `sys.exit()` from domain/application behavior.
- Move OpenAI, lxml, httpx, Playwright, filesystem, and JSON formatting concerns into infrastructure.
- Consolidate duplicated or disconnected crawl logic into one coherent runtime flow.
- Replace ad hoc mutable extraction state with session-owned objects.
- Preserve the current CLI contract and JSON export contract unless a compatibility-breaking defect forces a change.
- Keep or improve existing test coverage while shifting tests toward use cases and ports.

## Non-Goals

- Changing the user-facing command name or primary CLI flags.
- Redesigning the underlying crawling product goals.
- Expanding scope into new crawler features unrelated to the refactor.
- Introducing a new output format version unless current behavior is incorrect.
- Keeping every existing file path or package name stable internally.
- Preserving dead code, checked-in runtime artifacts, or disconnected execution paths.

## Current Problems

The current `src` tree already contains classes, but the core architecture is not object-oriented in a meaningful way.

### Structural Issues

- Application flow, console output, process termination, and file persistence are mixed together.
- Interfaces exist in `src/domain/interfaces.py` but are not the actual basis of composition.
- Large procedural modules still hold the core behavior:
  - `src/ai/analyzer.py`
  - `src/ai/xpath_gen.py`
  - `src/ai/healer.py`
  - `src/crawler/extractor.py`
  - `src/crawler/discovery.py`
- `src/models/schemas.py` mixes domain concepts, AI payload schemas, extraction config, health state, and export shapes in one file.
- Extraction healing state is recreated per batch instead of being owned by a long-lived crawl session.
- Some public inputs are not meaningfully wired through the main runtime path, especially depth-oriented traversal behavior.

### Behavioral Issues

- `print()` is embedded throughout orchestration and services.
- `sys.exit()` is used inside orchestrator code.
- OpenAI calls are buried inside helper modules instead of living behind stable ports.
- Mutable crawl configuration is rewritten deep inside extraction internals.
- Legacy and newer flows coexist without a clean ownership model.

## Target Architecture

The refactor replaces the current package-by-package organization with four explicit layers.

### Domain Layer

The `domain` layer owns the crawler's business language and rules. It must not import OpenAI, lxml, httpx, Playwright, the filesystem, or console/reporting code.

Responsibilities:

- crawl entities
- pagination entities
- extraction entities
- analysis entities
- value objects
- scoring and health policies
- port definitions
- domain-level exceptions

Examples of domain objects:

- `CrawlRequest`
- `CrawlResult`
- `PageSnapshot`
- `FieldDefinition`
- `ExtractionRecord`
- `PaginationTrace`
- `LinkCandidate`
- `LinkSelection`
- `HealthState`
- `DomainError` subclasses

### Application Layer

The `application` layer owns use cases and workflow coordination. It depends on domain objects and ports, but not on infrastructure implementations.

Responsibilities:

- use-case orchestration
- request/response DTOs between use cases
- coordination of analysis, pagination, discovery, extraction, healing, and export
- emitting progress events to a reporter port

Key use cases:

- `CrawlWebsite`
- `AnalyzeStartPage`
- `PaginateListing`
- `DiscoverDetailUrls`
- `CrawlDetailPages`
- `CoordinateExtraction`
- `HealSelectors`
- `ExportCrawlResult`

### Infrastructure Layer

The `infrastructure` layer owns all external integration and implementation details.

Responsibilities:

- OpenAI-compatible model integration
- HTML cleaning, annotation, classification, and DOM inspection
- XPath generation and validation
- HTTP fetching
- Playwright fetching and pagination sessions
- JSON export
- console reporting
- adapter-specific DTO parsing and validation

### Interfaces Layer

The `interfaces` layer owns entrypoints and bootstrap wiring.

Responsibilities:

- CLI argument parsing
- composition root
- mapping errors to terminal messages and exit codes
- creating the application object graph

### Dependency Rule

Dependencies point inward only:

- `interfaces -> application -> domain`
- `infrastructure -> domain`
- `infrastructure -> application` only where implementing an application port requires the application's port types

Domain code must never depend outward on infrastructure or interfaces.

## Component Model And Runtime Flow

The main runtime entrypoint becomes one use case: `CrawlWebsite`.

### `CrawlWebsite`

`CrawlWebsite` accepts a `CrawlRequest` and returns a `CrawlResult`.

It does not:

- print to the console
- write files directly
- terminate the process

It may emit progress events through a `RunReporter` port and return the final structured result.

### Main Runtime Flow

1. Fetch the start page through a `PageSource`.
2. Analyze the start page through `AnalyzeStartPage`.
3. Branch into list-page or detail-page crawling.
4. Coordinate extraction and healing through one session-owned extraction coordinator.
5. Produce a final `CrawlResult`.
6. Export or present the result through interface/infrastructure adapters.

### `AnalyzeStartPage`

Responsibilities:

- fetch or receive the initial page snapshot
- clean and annotate HTML
- classify page type
- produce either `ListAnalysis` or `DetailAnalysis`
- compile the initial selector/config objects needed by downstream use cases

### `ListingCrawler`

Responsibilities:

- paginate list pages
- discover detail URLs
- group detail URLs into crawl batches
- delegate detail crawling

Collaborators:

- `PaginationCoordinator`
- `DetailUrlDiscovery`
- `DetailCrawler`

### `DetailCrawler`

Responsibilities:

- crawl direct detail pages
- crawl detail URLs discovered from lists
- reuse a cached per-domain extraction template when multiple detail URLs share the same domain-specific page structure
- support sub-detail traversal where enabled by the selected runtime rules

### `ExtractionCoordinator`

Responsibilities:

- own extraction-session state
- coordinate field extraction, field health updates, and healing decisions
- apply reanalysis or selector repair when the health policy requires it

This replaces the current design where `FieldHealthTracker` is recreated inside `extract_pages()`.

### `ResultExporter`

Responsibilities:

- transform `CrawlResult` into the export payload
- write the payload through an output/storage port
- avoid embedding JSON formatting logic in application code

## Ports And Adapters

The refactor introduces explicit ports as the stable seams between application code and infrastructure.

### Core Ports

- `PageSource`
- `BatchPageSource`
- `PaginationSessionFactory`
- `LanguageModelGateway`
- `HtmlPreprocessor`
- `HtmlAnnotator`
- `ElementClassifier`
- `XPathGenerator`
- `XPathEvaluator`
- `OutputWriter`
- `RunReporter`

### Expected Adapter Split

#### AI Adapters

Current procedural modules:

- `src/ai/analyzer.py`
- `src/ai/xpath_gen.py`
- `src/ai/healer.py`

Target adapters:

- `OpenAiPageClassifier`
- `OpenAiFieldAnalyzer`
- `OpenAiXPathGenerator`
- `OpenAiSelectorHealer`
- `OpenAiJsonResponseParser`

#### HTML And DOM Adapters

Current modules:

- `src/preprocessing/cleaner.py`
- `src/preprocessing/annotator.py`
- `src/preprocessing/classifier.py`
- part of `src/crawler/extractor.py`

Target adapters/services:

- `HtmlCleaner`
- `HtmlAnnotator`
- `ElementClassifier`
- `LxmlXPathEvaluator`
- `XPathValidationPolicy`
- `TextExpansionPolicy`
- `LxmlFieldExtractor`

#### Fetching And Pagination Adapters

Current modules:

- `src/crawler/fetcher.py`
- `src/crawler/playwright_session.py`
- `src/services/pagination_engine.py`
- `src/services/playwright_pagination_engine.py`
- `src/services/pagination_strategies.py`
- `src/services/progress_detector.py`

Target adapters/services:

- `HttpPageSource`
- `PlaywrightPageSource`
- `PlaywrightPaginationSessionFactory`
- `PaginationCoordinator`
- strategy objects for link, click, load-more, and infinite-scroll behavior
- `ProgressSnapshotFactory`

#### Output And Reporting Adapters

Current modules:

- `src/storage/exporter.py`
- console output spread across orchestrators and services

Target adapters:

- `JsonOutputWriter`
- `ConsoleRunReporter`

## Data Model Strategy

The current split between `src/domain/models.py`, `src/domain/pagination_models.py`, and `src/models/schemas.py` will be replaced by a clearer model taxonomy.

### Domain Models

Domain models represent crawler concepts, not API payloads or framework-specific parsing structures.

Examples:

- `CrawlRequest`
- `CrawlResult`
- `PageSnapshot`
- `FieldDefinition`
- `ExtractionRecord`
- `LinkCandidate`
- `LinkSelection`
- `PaginationConfig`
- `PaginationTrace`
- `HealthState`

These should be dataclasses or frozen value objects.

### Application DTOs

Application DTOs represent use-case handoffs.

Examples:

- `StartPageAnalysis`
- `ListAnalysis`
- `DetailAnalysis`
- `ExtractionBatchResult`
- `DetailCrawlResult`

These stay out of infrastructure-specific schema files.

### Infrastructure Schemas

Pydantic remains only where external input/output validation is useful:

- AI JSON response payloads
- export payload validation if needed
- adapter-local parsing helpers

The current `src/models/schemas.py` will not survive as a monolithic shared schema file.

### Data Rules

- no mutable list defaults
- no OpenAI types outside infrastructure
- no lxml element types outside infrastructure
- no file paths in domain models
- no console formatting data in domain/application models

## Package Layout

The target top-level layout under `src` is:

- `src/domain/`
  - `crawl_entities.py`
  - `analysis_entities.py`
  - `pagination_entities.py`
  - `extraction_entities.py`
  - `ports.py`
  - `policies.py`
  - `errors.py`

- `src/application/`
  - `dto/`
  - `services/`
  - `use_cases/`

- `src/infrastructure/`
  - `ai/`
  - `fetching/`
  - `html/`
  - `pagination/`
  - `storage/`
  - `reporting/`

- `src/interfaces/`
  - `cli/`
  - `bootstrap/`

This layout is preferred over preserving the current buckets:

- `app`
- `services`
- `crawler`
- `preprocessing`
- `storage`
- `ai`

Those old buckets encode implementation style rather than architectural responsibility.

## Error Handling

The new design removes process control from business logic.

### Rules

- application and domain code may raise typed exceptions or return explicit failure results
- only the CLI or interface layer may translate failures into exit codes
- only the CLI or reporting layer may format human-facing terminal messages

### Exception Families

Examples:

- `AnalysisError`
- `FetchError`
- `PaginationError`
- `ExtractionError`
- `HealingError`
- `ExportError`

The final naming can vary, but the separation of concerns cannot.

## Compatibility Requirements

The refactor must preserve the current public behavior unless a bug or architectural contradiction requires a change.

### CLI Compatibility

Preserve:

- the `ai-powered-crawler` script entrypoint
- the existing core flags
- the current argument semantics

`interfaces/cli` may replace the current module layout, but the external command contract must stay compatible.

### Export Compatibility

Preserve the existing JSON export structure unless a correctness issue requires adjustment.

Expected fields include:

- `source_url`
- `page_type`
- `total_records`
- `fields_definition`
- `pages`

If export changes are required, they must be intentional, documented, and covered by tests.

## Legacy Code Disposition

The rewrite is complete only when the legacy tree is removed or reduced to thin compatibility shims that delegate to the new implementation.

### To Remove Or Collapse

- unused protocol shells that no longer match the new ports
- dead traversal paths that are not part of the chosen runtime design
- `src/test.py`
- checked-in `__pycache__` artifacts
- procedural helpers whose responsibilities are fully absorbed by new classes

### To Preserve In Meaning, Not In Shape

- link candidate scoring behavior
- pagination behavior
- exporter behavior
- CLI defaults
- start-page routing behavior

## Testing Strategy

Because this is a full-tree rewrite, tests must prove behavior at the new seams rather than only reproducing the old module layout.

### High-Value Existing Behaviors To Preserve

- CLI defaults and argument mapping
- routing between list and detail flows
- pagination coordination behavior
- link selection and pattern scoring
- exporter output shape
- Playwright pagination session behavior

### New Test Focus

- domain object and policy tests
- application use-case tests using fake ports
- adapter tests for OpenAI parsing
- adapter tests for XPath validation and extraction
- adapter tests for fetcher implementations
- compatibility tests for CLI and export behavior

### Refactor Completion Standard

The rewrite is not complete when the new classes merely exist. It is complete when:

- the main runtime path is driven by the new use cases
- legacy modules are removed or reduced to trivial delegation
- tests target the new object graph
- the full verification suite passes

## Implementation Shape

Although the user chose a full rewrite, the work will still be executed in internal slices.

### Slice 1: Core Structure

- create the new package layout
- define the new domain entities, errors, and ports
- add initial tests for core objects and use-case boundaries

### Slice 2: Application Flow

- implement the new `CrawlWebsite` use case and its collaborators
- replace top-level orchestration with the new use cases
- keep compatibility at the CLI boundary

### Slice 3: Infrastructure Migration

- migrate HTML, AI, fetching, pagination, extraction, and export behavior into infrastructure adapters
- wire adapters through the composition root

### Slice 4: Legacy Collapse

- remove or collapse old modules
- update tests to point at the new architecture
- remove dead code and checked-in runtime artifacts

## Risks And Mitigations

### Risk: Regression During Whole-Tree Rewrite

Mitigation:

- preserve high-value behavior tests
- add use-case tests before implementation
- keep compatibility expectations explicit

### Risk: Reproducing Old Coupling Under New Names

Mitigation:

- enforce inward-only dependencies
- keep external libraries out of domain/application
- split large procedural modules by responsibility, not by original filename

### Risk: Unclear Ownership Of Crawl State

Mitigation:

- make extraction and healing session state explicit
- make reporting and exporting explicit ports
- make pagination state and traces owned by dedicated objects

## Decision

Adopt a full `src` tree OOP refactor with a new layered architecture and a new composition root. The refactor will preserve the public CLI and export contract, but it will replace the current internal structure wholesale rather than wrapping existing modules in superficial classes.
