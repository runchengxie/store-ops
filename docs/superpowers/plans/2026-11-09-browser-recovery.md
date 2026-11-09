# Browser-assisted FBE checks implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Persist a fixed read-only FBE check independently of API monitoring, with explicit human verification and safe resume.

**Architecture:** SQLite owns versioned browser task intent and a process lock. A fixed Node MCP reader owns one inspection tab; Python validates its bounded result, preserves immutable evidence, and exposes only sanitized task summaries through authenticated operations routes. The existing Go API collector remains untouched.

**Tech Stack:** Python/FastAPI/SQLite, Node and the already installed MCP SDK, React/TypeScript.

**Spec:** User-approved API-first, independent browser-wait exploration; public behavior recorded in [Browser-assisted FBE checks](../../browser-checks.md).

## Global constraints

- Exactly one enabled platform: eMAG RO. Fixed read-only browser operations, no arbitrary tools or URLs.
- Runtime records outside Git; private store/account binding in the established deployment environment.
- No automatic CAPTCHA attempts; no external messages, contract acceptance, or merchant writes.
- Global monitoring pause prevents browser claims and publication. Browser waits never change API scheduling or consume Go slots.
- Preserve unknown outcomes and old successful evidence. UI text in English/Chinese catalogs.

## Review focus

- Concurrent resume and stale revisions must not start duplicate workers.
- Browser account mismatch or truncated evidence must never publish a successful check.
- Restart during a read must recover to an explicit review state without replaying writes.
- Offline/login/challenge states must retain one task and keep API collection enabled.
- A paused store or switched UI store must not permit late publication or resume against another store.

### Task 1: Durable task protocol and authenticated routes

Files: `app/services/browser_tasks.py`, `app/routers/platform_operations.py`, `app/platforms/registry.py`, `app/tests/test_browser_tasks.py`.

- [x] Write failing tests for deduplicated creation, versioned resume, store isolation, pause, lock ownership, restart and retained success.
- [x] Run pytest and confirm the new tests fail because the protocol is absent.
- [x] Implement SQLite compare-and-swap transitions, fixed `fbe_inventory` kind, sanitized summaries, immutable source references and fixed worker dispatch. Expose list/create/resume admin routes; overview includes summaries.
- [x] Verify new tests plus platform, supervisor and pause regressions; commit.

### Task 2: Fixed browser reader and worker

Files: `scripts/browser-fbe-reader.mjs`, `scripts/browser-fbe-contract.mjs`, `scripts/browser-fbe-reader.test.mjs`, `app/browser_worker.py`.

- [x] Write failing tests using representative accessibility snapshots: known account, exact inventory rows, challenge, login, missing/partial data and mismatched account.
- [x] Implement only MCP new-tab/navigate/snapshot/close, a bounded single-page observation, strict account binding, and explicit partial coverage. Never claim all FBE inventory from a single page. Persist row observations separately from API snapshots.
- [x] Add fixed subprocess worker with timeout and exclusive bridge lock, redacted bounded diagnostics and explicit waiting states. Run tests and commit.

### Task 3: Minimal UI, documentation and integration

Files: workbench status components/catalogs, status regression tests, docs/browser-checks.md and Chinese counterpart, changelog, indexed ADR.

- [x] Add a regression for the browser notice model before implementation.
- [x] Show at most one browser task notice and a versioned “I've verified; continue” action; do not replace main API status. Expose start/check again action without demo changes.
- [x] Run frontend typecheck/i18n/build, real App harness validation, Python suites/lint, Node reader tests and unchanged Go regressions.
- [ ] Publish PR, verify all applicable CI on combined target and merge using standing authorization. Independent review completed; all six findings have regression fixes.
- [ ] Fast-forward clean laptop checkout, preserve private settings, restart only identified backend service, verify a real read-only task and unchanged API control; retain evidence privately. Clean only merged task branch/worktree.

## Execution record

- Native implementation in the task worktree, baseline origin/main 1c216a7.
- Protocol regressions RED→GREEN; targeted Python suite 52 passed before review, 49 passed after pause serialization regression.
- Full Python suite before final review fix: 1337 passed, 19 skipped. Final suite is rerun for the reviewed fix revision.
- Real App harness at mobile and desktop sizes: no page errors, no horizontal overflow, browser verification→queued action works while main API status stays working.
- Independent fresh review found six issues (exact account binding, quantity parsing, truncated rows, stale DOM, pause/publication race, orphan reader exclusivity). All addressed with failing regressions followed by passing tests. Node-owned loopback lease supplements the Python lease.
- Live laptop reader probe: complete, 25 visible-page product observations; no marketplace writes and no API snapshot replacement.
- No deferred review findings or scope deviations. Initial network retries remain explicit/manual as documented; no new external notification transport.
