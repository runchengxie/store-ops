# Fee and Payout Reconciliation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Deliver source-backed fee/payout reconciliation and an optional report section without changing existing marketplace execution.
**Architecture:** Local evidence imports and exact-decimal reconciliation in an isolated SQLite artifact store, a CLI and optional digest integration. No automatic financial collectors until real structured formats are validated; use a documented bounded manual JSON contract.
**Tech Stack:** Existing Python/FastAPI server, sqlite3, Decimal, pytest; no new dependency.
**Spec:** docs/superpowers/specs/2026-11-10-reconciliation.md

## Global Constraints
No payments, automatic accounting, bank ingestion or ERPNext deployment. Preserve legacy digests when no financial data exists. Respect artifact data root and frozen bundle paths. No private host paths in documentation. Money must not use binary float arithmetic. Imported evidence is untrusted input.

## Review Focus
- Same identifiers in different stores/entities/document types cannot collide.
- Duplicate reimports and changed estimates must not double count.
- Partial/many-to-many allocations cannot over-allocate or silently clear credits.
- Missing coverage, currency mismatch and missing actual event timestamps must fail closed or remain unknown.
- Presentation must not interpolate arbitrary source text/URLs into executable commands or unbounded messages.

### Task 1: Evidence import and reconciliation
Files: create app/services/emag_reconciliation.py, app/emag_reconciliation_cli.py and tests/test_emag_reconciliation.py under src/server; add focused schema/examples documentation.
Interfaces: import_batch(store_id, payload) -> receipt; reconcile(store_id) -> source-backed typed result; render(result, locale) -> bounded Markdown. Follow existing store_artifacts validation and private root patterns. Store append-only source versions, explicit stable identities, coverage, dates, currency and exact decimal amount strings. Use reviewed manual evidence contract; reject unknown/malformed records. Confirmed allocations require source references; unconfirmed suggestions never alter confirmed balances. Preserve provisional estimate-to-processed links explicitly.
- [ ] Write failing tests for idempotency/version changes, signed amounts, mixed currencies, cross-entity identity, partial allocations, over-allocation, unsupported/missing data, and a fee already in payout not deducted twice.
- [ ] Run focused tests and observe failure.
- [ ] Implement service, CLI import/reconcile commands and source-backed report. Inputs from local JSON only, no external API calls or credentials.
- [ ] Run focused tests and ruff; commit.

### Task 2: Optional operational report integration and documentation
Files: modify app/services/emag_digest.py only through a small optional integration, new focused digest tests; docs/fee-payout-reconciliation.md and docs/zh-CN/fee-payout-reconciliation.md, docs/changelog.md and relevant index link.
Consumes service API above. Do not turn a source-backed pure build into uncontrolled runtime I/O: load optional reconciliation explicitly at CLI/source boundary as needed, default absent for old callers.
- [ ] Write failing tests for absent evidence compatibility, partial coverage, estimated versus processed labels, and report size limits.
- [ ] Implement optional financial summary using existing locale conventions; do not claim bank receipt or accounting profit.
- [ ] Verify existing digest/delivery and reconciliation suites, run backend pytest and ruff. No frontend changes planned.
- [ ] Document exact manual import schema, synthetic examples, source limitations, unknowns and operation commands; commit.

### Task 3: Whole-change review and integration
- [ ] Independent review against spec, including adversarial imports and source/currency invariants.
- [ ] Fix actual issues and rerun affected checks; record existing failures separately.
- [ ] Verify push destination and auth, create PR in runchengxie/store-ops; validate current target combined result; merge under standing user authorization when applicable checks pass.
- [ ] Verify merged revision and authorized task deployment; clean only completed task branches/worktree.
