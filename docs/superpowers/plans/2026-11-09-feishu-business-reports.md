# Feishu business reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver source-labelled daily/weekly store summaries to the owner's existing Feishu bot conversation.

**Architecture:** The laptop generates bounded deterministic JSON from existing eMAG snapshots. Linux retrieves it through a fixed private SSH command and invokes the existing bot-only Lark CLI. A durable SQLite ledger prevents duplicate or uncertain resends.

**Tech Stack:** Python 3.11+, zoneinfo/tzdata, SQLite, existing Lark CLI, SSH, systemd user timer.

**Spec:** `docs/superpowers/specs/2026-11-09-feishu-business-reports-design.md`

## Global Constraints

- Marketplace access remains read-only; reporting does not trigger collection.
- Europe/Bucharest business timezone; daily 09:00, weekly Monday 09:10; Chinese deployment, English default.
- Credentials remain in existing CLI storage; no new listener.
- Missing, ambiguous, stale and partial evidence stays visible; no revenue/profit promise.
- Any uncertain send becomes unknown and is never automatically retried.

## Review Focus

- DST and Sunday/Monday boundaries must not select a future or partial week.
- Naive source timestamps and incompatible collection windows must not become precise sales figures.
- A crash after submission must not permit another invocation to resend.
- CLI nonzero exit, malformed JSON and wrong app must not become delivered.
- A remote report for the wrong store/period/language must never be sent.

### Task 1: Source-backed report builder and generation CLI

**Files:** create `src/server/app/services/emag_digest.py`, `src/server/app/emag_digest_cli.py`, `src/server/app/tests/test_emag_digest.py`; reuse existing artifacts/read-only summaries.

**Interfaces:** `period(kind, now, timezone_name) -> dict`; `build(snapshot, kind, now, timezone_name='Europe/Bucharest', locale='en') -> dict` returns versioned bounded report JSON; CLI accepts store/kind/timezone/locale and optional save.

- [ ] Write tests for DST periods, known/unknown stock, duplicate/missing/naive order dates, compatible aware windows, prior-period comparisons, stale/missing snapshots and privacy-safe rendering.
- [ ] Run new tests; expect missing module failures before implementation.
- [ ] Implement builder and CLI with localized fixed templates, independent raw-record counts and explicit capture-window context.
- [ ] Run builder and existing eMAG tests; expect pass. Commit the deliverable.

### Task 2: CLI delivery and durable due scheduling

**Files:** create `src/server/app/services/emag_digest_delivery.py`, `src/server/app/emag_digest_delivery.py`, `src/server/app/tests/test_emag_digest_delivery.py`, `configs/digest-delivery.example.json`.

**Interfaces:** `run(config, now, kind=None, preview=False) -> list[dict]`; private `source_commands[kind]` returns Task 1 JSON. `state_dir` holds SQLite ledger and immutable prepared payload. Commands use argv, stdin, explicit bot, timeout, bounded output and fixed diagnostics.

- [ ] Write subprocess-boundary tests with a real temporary fake executable: wrong app, correct success JSON, malformed/nonzero replies, timeout, mismatched report, concurrent invocations and crash/unknown terminal state.
- [ ] Run tests; expect missing module failure.
- [ ] Implement strict config/report validation, app preflight, due periods, durable intent before sending and verified message ID receipt. Preview must not send or mark delivered.
- [ ] Run both new test files; expect pass. Commit the deliverable.

### Task 3: Documentation, review and deployed delivery

**Files:** create `docs/feishu-reports.md`, `docs/zh-CN/feishu-reports.md`, indexed ADR; update README language counterparts and changelog.

**Interfaces:** private Linux configuration calls the merged laptop CLI; Linux timer runs merged delivery CLI. Existing canonical data/config roots remain authoritative.

- [ ] Document limitations, defaults, standalone modes, private configuration, unknown reconciliation and deployment/rollback. Run maintained-doc checker; expect pass.
- [ ] Run backend lint, backend test suites and required CI; record actual outcomes and dependency/security checks. Obtain independent whole-branch review and fix material findings with regression tests.
- [ ] Push only to runchengxie/store-ops, open PR, validate current target/combined result and merge under standing authorization.
- [ ] Fast-forward clean primary checkouts; preview real report, send to owner and verify message receipt. Install/verify scoped Linux timer under private configuration, verify no collector ownership changed. Remove only merged task branch/worktree.
