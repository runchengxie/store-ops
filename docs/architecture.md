# Architecture

Optional marketplace price execution is a separate admin API and SQLite ledger. It does not reuse local issue approval or MCP report-write permission. See [ADR-0052](decisions/0052-separate-emag-price-api.md) and [price API](emag-write-readiness.md) for store binding, live preflight, uncertain-delivery blocking and read-back semantics.

[简体中文](zh-CN/architecture.md)

## Components and ownership

| Component | Responsibility | Boundary |
|---|---|---|
| `src/client` | React/Vite UI, local display preferences and provider-specific interfaces | Presentation does not authorize backend actions |
| `src/server` | FastAPI authentication, APIs, evidence storage, local records and integrations | eMAG workspace endpoints require an administrator |
| `scripts` | Installation, launch, update and deployment helpers | Dry-run dispatch resolves an action without executing it |
| `data` | Configured private application state | Excluded from commits, including store evidence and local reports |
| IvyeaAgent | External Agent runtime and provider integration | An installed dependency accessed over its CLI/HTTP contracts, not a submodule |

The inspected checkout has no `.gitmodules` and no gitlinks. The vendored Agent frontend lives inside this repository. This audit did not initialize a missing repository, upgrade a gitlink or change a sibling checkout.

`app/core/layout.py` separates repository root from code root. Source checkouts use `src/client` and `src/server`. Frozen archives keep `client` and `server` beside their runtime resources. Repository-level docs, skills and `data` are not moved under `src`.

## eMAG evidence flow

`emag_business.collect` uses fixed RO read endpoints and projects selected fields. `publish` stores a versioned snapshot after complete collection. Sequential API reads are not an atomic marketplace view. Order timestamps, invoice dates and service periods have different meanings. Platform filter timezone interpretation remains unverified.

Periodic reports may group compatible naive dates from the known collector by
explicitly labelled platform calendar dates, checking source and full-period
coverage without assigning an offset. This is separate from verified-instant
reporting; see [report date bases](feishu-reports.md).

The manual job reads or collects evidence, compares observations where a baseline exists, saves a source-bound report and publishes a receipt. A per-store lock prevents overlapping runs through this entry point. Collection failure keeps the prior snapshot. A process crash or storage failure may prevent a new receipt, so check its run ID and timestamp.

Snapshots and reports are append-only through these APIs. Files are ordinary local files, not tamper-proof storage. `StoreSnapshot` has source, coverage, limitations and timezone-aware `captured_at`. Existing schema-version-1 snapshots remain compatible without rewriting old artifacts. Store/snapshot/report IDs and structured keys are not translated.

Local drafts and workflow records use SQLite. Drafts bind store, snapshot and product. Workflow transitions use snapshot freshness and revision checks. Current states are `pending`, `proposed`, `approved`, `executed`, `reviewed`. `executed` is a manual record. There is no rejection/rework state or marketplace executor in this flow.

## Agent, MCP and scheduling

The console's general Agent permission flow can resume commands or file writes after an accepted decision. It is separate from local eMAG proposal approval.

MCP exposes imported evidence and local reports through bearer-token scopes. It does not expose account passwords or a general eMAG write proxy. The adapter registry enables only eMAG; retired Amazon tools and startup jobs are absent. See [adapter boundaries](platform-adapters.md).

The existing scheduler runs Agent prompts. The eMAG schedule page only prepares commands, previews server cron times and downloads disabled JSON drafts. These drafts are not consumed by either the Agent scheduler or an OS scheduler.

## Localization

The Agent frontend has its own i18next instance and locale resources. The main workbench is largely Chinese and has no application-wide locale switch. Documentation localization does not imply a fully localized product. See the [audit](maintenance-audit.md) for locale identifiers, fallback behavior and validation.

Implementation references: `src/server/app/core/config.py`, `src/server/app/core/layout.py`, `src/server/app/services/store_artifacts.py`, `src/server/app/services/emag_jobs.py`, `src/server/app/services/emag_operations.py`, `src/server/app/routers/mcp_server.py` and `src/client/src/lib/navRegistry.ts`.
