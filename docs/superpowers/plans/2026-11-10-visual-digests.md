# Visual Daily and Weekly Digests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Send source-backed daily/weekly PNG long images alongside existing text via the existing bot.
**Architecture:** Derive bounded visual data at source report CLI boundary, render with existing Pillow and installed/configured CJK fonts, upload/send through the existing bot CLI. Track text/image delivery independently; absent image configuration retains old behavior.
**Tech Stack:** Existing Python, Pillow, sqlite3, Lark CLI; no AI-generated charts or browser capture.
**Spec:** docs/superpowers/specs/2026-11-10-visual-digests.zh-CN.md

## Global Constraints
Provider fee-payout reconciliation must merge first. No hidden financial endpoints. No fabricated zero/unknown metrics; same digest snapshot feeds all image/text values. Never resend uncertain image submissions or text already delivered. No merchant writes.

## Review Focus
- Long labels and Chinese font availability cannot produce unreadable or missing-glyph images.
- Missing data and incomplete date coverage must not become zero-valued bars.
- Tie-aware ranking and observed order states must retain correct meaning.
- Text-success/image-failure and image-unknown must not duplicate text/image messages.
- Imported labels, image paths and CLI outputs must be bounded/untrusted, with exact bot identity and artifact-root confinement.

### Task 1: Source data and rendering
Create app/services/emag_digest_visual.py plus focused tests. No edits to provider-owned emag_digest_cli.py until coordinated. Build visual payload from the same saved snapshot/report and derive platform-date trends only with complete coverage, including prior comparable data when available. Render at 1080–1200px width with readable bounded variable height. Include headline metrics, trends, ranked product units, observed order state, inventory/aging risk, optional reconciliation and priority actions, period/update/source/coverage notes. Report render errors explicitly; fall back to text.
- [ ] Tests first for values, absent/partial data, dates, ties, fonts, long untrusted labels and image dimension bounds.
- [ ] Implement derivation/rendering with Pillow and explicit installed/configured font resolution.
- [ ] Render synthetic fixtures, inspect PNGs, run focused tests, commit.

### Task 2: Bot delivery and documentation
Modify delivery config and ledger with optional image mode; create a standalone visual CLI if needed. Coordinate minimal source CLI integration after provider commit. Use existing lark-cli help/reference to implement upload and send, verify JSON bot identity, app and returned image/message IDs. Distinct idempotency state for images; no repeat when sending outcome unknown. Upload-success is not message-success. Preview must not send or alter delivery ledger. Validate image artifact metadata/same snapshot and prevent arbitrary file upload.
- [ ] Tests first for old config, text/image partial failure, uncertain upload/send, correction IDs, app/path/snapshot mismatch and bounds.
- [ ] Implement delivery and stable private artifact paths, no browser or credential changes.
- [ ] Maintain English and Chinese setup docs/changelog; document font dependency and failure behavior.
- [ ] Run focused and existing delivery suites, ruff; commit.

### Task 3: Independent review, integration, deployment
- [ ] Review and fix; rebase/merge provider main before combined validation.
- [ ] PR to user fork; applicable checks and final target validation before merge, preserve contributor identity.
- [ ] Deploy stable worker/source paths under existing authorized configuration. Render real daily/weekly reports, visually verify and send a text/image pair each with deliberate correction IDs. Verify message IDs; clean only this task's merged resources.
