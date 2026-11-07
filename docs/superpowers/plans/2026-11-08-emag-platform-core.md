# eMAG Platform Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:dispatching-parallel-agents for independent removal domains with file ownership; TDD, one coordinated Git branch and a final independent whole-branch review.

**Goal:** Keep shared operations infrastructure and exactly one eMAG adapter, removing executable Amazon product features.
**Architecture:** Introduce a small versioned adapter registry and canonical overview port. Reuse eMAG workflows without flattening platform extensions; remove Amazon routes/algorithms/skills/startup jobs and reject explicitly retired task references.
**Tech Stack:** Existing FastAPI/Pydantic/SQLite, React, existing test/harness tools. No new dependencies.
**Spec:** ../specs/2026-11-08-emag-platform-core.zh-CN.md (approved)

## Global Constraints
Only eMAG registered; no dormant Amazon adapter. Preserve existing private artifacts/config/credentials/task records and eMAG IDs/CLI compatibility. No marketplace write/scheduler/security configuration expansion. New platform APIs remain admin-only. Unsupported capability distinct from unknown/readiness. Use English canonical docs and aligned Chinese guides.

## Review Focus
- Deleted services still referenced lazily from common modules or startup.
- Existing user MCP configuration or skill roots accidentally overwritten.
- Retired explicit skills/tools still dispatched to an external Agent.
- Store identity/platform/source mismatch or unknown metrics misrepresented by canonical overview.
- Hidden Amazon UI/provider assumptions in common settings, prompts and transport.

### Task 1: Canonical platform operations (root)
Files: app/platforms/{contracts,registry,emag/adapter}.py, routers/platform_operations.py, tests/test_platform_operations.py; client/status controller/adapter tests and harness generic boundary.
Interface: registry has only descriptor emag. GET /api/operations/platforms, /stores, /stores/{id}/overview; overview returns store_id/platform/market/currency/timezone/snapshot_id/captured_at/metrics{products,issues,stock}/collection receipt. Existing /emag endpoints retained for explicit extensions. UI consumes generic envelope and endpoints.
- [ ] Write RED tests for sole adapter/capability failure-closed, auth, exact identity, metadata/unknown metrics and unchanged existing snapshot semantics.
- [ ] Implement minimal port delegating existing eMAG services; GREEN tests and UI/harness behavior. Root owns only new platform files/router and client status files.

### Task 2: Retire Amazon backend (backend worker)
Files: app/main.py registrations/startup, Amazon-only routers/services/tools and their exclusive tests; ivyea_ops_tools.py, evidence_trace.py; no schedules.py/agent_skills/hermes_config_sync/agents synchronizer ownership.
Interface: root supplies app.routers.platform_operations.router to register at /api/operations. eMAG/shared services retained. Old Amazon APIs/tools absent, no startup Amazon jobs or provider calls.
- [ ] RED executable catalog/startup/consumer regressions, then remove exclusive implementations and repair shared imports.
- [ ] Run relevant shared/eMAG tests and Ruff; report deletions, retained shared helpers, unresolved consumers. No Git mutation.

### Task 3: Retire Amazon frontend (frontend worker)
Files: src/client except pages/workbench/status and its root-owned tests/harness; App/nav/settings/API clients/Amazon-only components and exclusive fixtures/tests.
Interface: retain current eMAG routes, status home, auth/AI/approvals/settings; remove legacy Amazon routes/pages/Lingxing integration and platform-specific provider UI. Old URLs ordinary404, not hidden dormant components.
- [ ] RED route/catalog assertions, remove exclusive features and update meaningful shared tests. Do not weaken generic tests.
- [ ] Typecheck/i18n/build and retained App route validation; report shared dependencies. No Git mutation.

### Task 4: Retire Amazon skill/provider/task registration (registration worker)
Files: agent_skills, hermes_config_sync, agents synchronizer, services/schedules and related exclusive files/tests, skills/amazon, Sellersprite bridge. Coordinate any main.py changes through backend worker.
Interface: no new app-managed Amazon root/provider synchronization; preserve external private config and arbitrary roots/files. Explicit known retired skill/tool references fail closed before job dispatch; records retained. No keyword guessing for arbitrary prompts.
- [ ] RED upgrade/root/registry/config-preservation/schedule dispatch tests.
- [ ] Remove Amazon defaults/skills/prompts, implement precise retired-capability guard; run tests/Ruff. No Git mutation.

### Task 5: Integration, documentation and delivery (root)
- [ ] Inspect every worker diff/consumer report, run full backend suites separately plus frontend checks, no-Amazon catalogs/startup tests and real App retained routes/platform home.
- [ ] Update current architecture/README/config/usage/skills docs and translations, indexed ADR/changelog; retain attribution and factual historical records.
- [ ] Independent whole-branch review; reproduce/fix Important findings RED→GREEN in one pass.
- [ ] PR/required checks/current-target validation, authorized merge, laptop source/frontend update with env/data/task fingerprints preserved, public demo and merged CI verification. Cleanup only this task's branch/worktree.
