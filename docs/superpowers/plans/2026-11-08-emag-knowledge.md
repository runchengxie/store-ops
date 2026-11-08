# eMAG Knowledge and Operational Checks Implementation Plan

Goal: runtime citations, snapshot-bound guidance and preflight, and explicit promotion economics, deployed on the existing laptop.
Architecture: private local index + pure deterministic checks + one bilingual secondary page. Reuse existing commerce/evidence/auth/MCP; no marketplace writes or training corpus in source.
Spec: `docs/superpowers/specs/2026-11-08-emag-knowledge-design.md`.
Execution: parallel independent domain owners in one task worktree, coordinated through the exact API contracts; root owns wiring, private import, integration, review and deployment. User already authorized this scope; routine implementation choices proceed autonomously.

## Global constraints

- English default, Chinese switch; locale catalogs, stable machine codes.
- Private pack under configured runtime data, no real files/text/paths/tokens in Git or CI.
- Current snapshot binding, explicit unknowns, no merchant write or automatic eligibility assertion.
- Preserve primary user work and private configuration; only task-owned worktree/branch cleanup.

## Review focus

- Malformed/oversized/untrusted index packs preserve existing index and cannot expose files or execute prompts.
- Two-character Chinese and wildcard queries, no imported corpus, and conflict-bearing historical results remain honest.
- XLSX unknown layouts, annotations/sample data, formulas, ZIP bombs and incomplete reads cannot appear platform-approved.
- Cost gaps, stale product/snapshot identity, VAT basis, fee reductions, unknown stacking and subsidies cannot silently improve an estimate.
- Non-admin access, stale network responses and store switching never leak or misapply private results.

## Task 1 — Private knowledge retrieval

Files: new `app/services/emag_knowledge.py`, `app/routers/emag_knowledge.py`, `app/emag_knowledge_cli.py`, associated tests. Root later owns `main.py`, MCP registration and skill routing.
Interfaces: `status()`, `search(query,limit=5)`, `source(source_id)`, `import_library(path)`; HTTP shapes exactly as spec. CLI `python -m app.emag_knowledge_cli import --library <path-to-library.json>` and `status`/`search --query`. Import existing generated library shape; chunk curated locators first, full text with explicit line locators where no physical location is known; keep ASR/conflict classifications. Do not return filesystem paths.
- [x] RED: CJK2, literal `%/_`, no corpus, bounded results, conflict citations, invalid import preserving revision, protected routes.
- [x] Implement private SQLite import/search/source and owner CLI; synthetic fixtures only.
- [x] GREEN: affected tests + Ruff, record output/source revision.

## Task 2 — Deterministic store checks

Files: new `app/services/emag_preflight.py`, `emag_promotion.py`, `emag_decision_support.py`, `app/routers/emag_assistance.py`, tests. Do not alter existing commerce calculation semantics or workspaces.
Interfaces: HTTP shapes per spec. Services reuse artifacts/commerce and output knowledge query strings; no dependency on knowledge implementation needed. Snapshot guards and store/product identity validation apply.
- [x] RED: missing/stale/complete costs; stacking explicit; gross fee-relative reduction; no subsidy conflation; cross-store and stale snapshot rejection.
- [x] Implement promotion estimates with Decimal and existing calculator.
- [x] RED: synthetic old/new XLSX layouts, missing required values, family mismatch, guidance-only file, malformed/oversized zip, formula/no-layout/manual checks.
- [x] Implement bounded local preflight using existing openpyxl dependency, no network/recalculation.
- [x] RED: observed existing-stock priorities with missing fields/unsupported root causes.
- [x] Implement source-bound suggestion read; GREEN affected suites + Ruff.

## Task 3 — Secondary operational UI

Files owned: new `src/client/src/pages/workbench/insights/`, new locale catalogs and tests; modifications App.tsx, lib/navRegistry.ts, status/StatusHome.tsx + status catalogs only for secondary menu entry; new `harness/insightsFixture.ts` and narrow hook in mockApi.ts; browser tests.
Interfaces: exact API contracts above. Auth from `useAuth` in App; no private reads before admin role confirmed. Keep public demo/static homepage layout unchanged. Knowledge usable without a connected store; store checks require a selected current snapshot.
- [x] RED: real App shows admin page, no calls for non-admin; empty index, source detail/conflict, errors, race/switching and cost gaps.
- [x] Implement compact bilingual panels for knowledge, suggestions, XLSX preflight and promotion, progressive detail/citations.
- [x] GREEN: typecheck, locale checks, production/demo build, real App desktop/mobile.

## Task 4 — Root integration and private deployment

Files: main.py, routers/mcp_server.py, eMAG bundled skills, docs/ADR/changelog + Chinese docs; deployment/import scripts stay private outside source.
- [x] Add read-scoped `ivyea_emag_knowledge_search`; preserve generic knowledge tool, reject unknown args, keep scope/rate/auth checks.
- [x] Register routes and document evidence/trust/data contracts and import operation.
- [x] Import real private pack in isolated data root; verify representative queries with citations/conflicts; prepare bounded normalized export for laptop (no original videos or private public files).
- [x] Full backend tests, Ruff, frontend prescribed checks, actual App browser and isolated live service smoke.
- [x] One fresh whole-branch review; fix important findings with regressions; validate combined current target.
- [ ] PR to user fork, required checks, merge; deploy matching backend/frontend and private pack on canonical laptop path. Preserve env/password hash/credentials/known tasks, verify HTTP/auth, knowledge queries, 184-offer data and protected APIs; no marketplace writes.
- [ ] Verify merged CI/Pages as applicable, retain private validation evidence, remove task branch/worktree only.
