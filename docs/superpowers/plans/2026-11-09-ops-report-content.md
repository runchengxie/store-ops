# Operations report content Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver compact, richer product/inventory reports with complete local evidence.
**Architecture:** Preserve current source/date guards; derive units from selected finalized orders, reuse snapshot-bound clearance checks, render only bounded catalog identifiers. Keep client markdown separate from detailed local reports.
**Tech Stack:** Existing Python report builder, tests, immutable snapshots and Lark delivery.
**Spec:** `docs/superpowers/specs/2026-11-09-ops-report-content-design.md`

## Global Constraints

- Existing recipients, credentials, collector scheduling and marketplace boundaries remain unchanged.
- Unknown quantities and aging remain unknown, not zero; period coverage gates stay intact.
- No amount metrics or physical timezone claims; use finalized-order current line quantities.

## Review Focus

- Canceled/returned orders and inactive lines cannot inflate finalized units.
- Missing quantity/status/product identity cannot fabricate zero or a complete ranking.
- Tied products must not be presented as uniquely best selling.
- Catalog labels cannot inject Markdown images, URLs, HTML or mentions.
- Unreconciled aging must not become a complete old-stock total.

### Task 1: Client copy and local evidence

- [x] RED tests distinguish compact messages and complete saved details, preserving real stale/unknown warnings and machine-neutral evidence.
- [x] Implement `markdown`, `details_markdown`, `evidence`; save local details and keep inclusive display dates separate from machine period boundaries.
- [x] Focused suite passed; independent review identified localized machine placeholders, reproduced and fixed to null.

### Task 2: Product and inventory metrics

Files: new `app/services/emag_digest_metrics.py` and tests; update `app/services/emag_digest.py` integration and report tests.
Interfaces: `products(current_rows, previous_rows, offers) -> dict`; `inventory(snapshot) -> dict`; selected period rows are derived only when existing period counts are available.

- [ ] Write RED tests for finalized/active-only quantities, zero vs missing, invalid IDs, deterministic ties, label sanitization, reconciled aging and priority stock.
- [ ] Implement pure metrics and guarded period-row selection. Render unit comparison, bounded product ranking and inventory issues/aging, with material partial-coverage notices.
- [ ] Run focused and complete suites, lint and doc checks; expect all pass. Verify real saved evidence without marketplace writes.

### Task 3: Review, integration and delivery

- [ ] Update bilingual docs/changelog around final scope. Obtain independent full-branch review and fix material findings with RED→GREEN tests.
- [ ] Push owner-repository PR, pass checks for current target/combined result and merge under standing authorization.
- [ ] Deploy stable generator/worker revisions, preview real content, deliver one clearly marked updated daily/weekly pair through existing correction gate, read back and verify dedupe/timer.
- [ ] Retain task evidence and clean only this task's merged branch/worktree.
