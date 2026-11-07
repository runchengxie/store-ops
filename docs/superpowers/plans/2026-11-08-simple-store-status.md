# Simple Store Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the demo and authenticated home understandable at a glance without chat.
**Architecture:** Shared React status presentation, pure evidence-to-view adapter, existing authenticated workspace/job reads. Preserve separate tools and conversation routes.
**Tech Stack:** React, CSS, existing FastAPI read endpoints, Node tests and real App harness.
**Spec:** ../specs/2026-11-08-simple-store-status.md

## Global Constraints
No fabricated live actions, no platform writes, no credential/config replacement. Default English with explicit Chinese switch. Preserve unknowns and snapshot timestamps. Mobile and reduced-motion accessible.

## Review Focus
- Historical completed/running receipts cannot masquerade as a fresh active task.
- Store switching, delayed/failed requests cannot expose another store's data.
- Timer effects must not leak or animate against user pause/reduced-motion/hidden tab.
- Demo must visibly remain synthetic and offline.
- Laptop deployment must preserve existing config, data, schedule and authentication.

### Task 1: Evidence adapter and shared status home
Files: status/data.mjs, declarations, catalogs, StatusHome.tsx, CSS; e2e/store-status.test.mjs.
Interface: deriveStatus(data, job, now) produces state, action keys and bounded metrics. Receipt freshness capped at120s for running only. Snapshot staleness24h explicitly labelled. Job failure supersedes waiting. Carousel pure presentation, no model or write.
- [ ] Tests RED: completed vs running, old running, failure, missing/unknown metrics, source snapshot consistency, catalog parity.
- [ ] Implement state derivation and bilingual presentation; tests GREEN; commit.

### Task 2: Production/demo integration
Files: StoreWorkbench.tsx, demo/main.tsx, App.tsx/nav only as needed, harness mock boundary, e2e/store-status-ui.mjs.
Interface: status home default at/workbench; /console remains conversation; existing detail routes unchanged. Poll workspace/job every30s when visible, generation guards and cleared stale data; job read failure does not imply active work.
- [ ] Real App regression RED for status hero/no composer, implement bindings and demo finite sequence.
- [ ] Verify desktop/mobile, locales/persistence, carousel pause/manual/reduced motion, empty/failure/offline/stale and delayed store switching; typecheck/i18n/build/demo GREEN; commit.

### Task 3: Review, publishing and laptop readiness
Files: bilingual user guide, changelog, indexed ADR.
- [ ] Inspect exact laptop launcher/config/data and latest task error without exposing secrets. Diagnose collection failure read-only first; separate any fix requiring gated platform/security changes.
- [ ] Run maintained checks, independent whole-branch review and regression fixes, PR/required checks/current-main validation; merge under standing authorization.
- [ ] Update only identified clean laptop checkout and generated frontend, preserve env and data, restart identified service; verify authenticated actual routes and retained store evidence. Verify public demo deployment and merged CI; cleanup only task artifacts.
