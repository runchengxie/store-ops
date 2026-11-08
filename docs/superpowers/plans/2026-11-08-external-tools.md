# External Tools Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in the existing task worktree. Follow the user's standing validation, PR, merge and cleanup authorization.

**Goal:** Make independent supplier/browser tools reproducible and explain their Agent-mediated use without adding runtime integrations.

**Architecture:** Independent tools retain their credentials and installation. Repository documentation owns workflow, evidence and approval boundaries. A reference inventory records observations, not executable configuration.

**Tech Stack:** Markdown and JSON; no new dependencies.

**Spec:** [Approved design](../specs/2026-11-08-external-tools-design.md).

## Global constraints

No application endpoint, runtime dependency, browser executor or automatic tool registration. No source copying, credential changes, data relocation or deletion. Preserve existing approval requirements and unknown values.

## Review focus

Version observations must not imply runtime verification; missing tools must not be installed automatically. Relative documentation links must work. Translations must retain the same limitations. Supplier quotations must not become confirmed costs. Archive integrity must not imply coverage of later actions.

## Task 1: Document the independent tool contract

- [x] Add `configs/external-tools.reference.json` with public source, observed version/revision, integration mode and verification limits.
- [x] Add `docs/external-tools.md` and `docs/zh-CN/external-tools.md` covering installation ownership, optional configuration, evidence storage and browser boundaries.
- [x] Add `docs/supplier-research.md` and its zh-CN counterpart as Agent instructions; retain the two existing bundled skills unchanged.
- [x] Link configuration, layout and skill indexes; add indexed ADR-0059 and a changelog entry.
- [x] Correct the local browser README without changing MCP configuration. Record archive integrity and incomplete later-record coverage honestly.

## Task 2: Verify and integrate

- [x] Parse the JSON inventory; check all new relative links, translation coverage, public-path hygiene and `git diff --check`.
- [x] Review the whole branch against the design using requesting-code-review. No runtime suite is needed for documentation-only changes; required remote checks still apply.
- [ ] Commit, verify push destination/account, push and open a PR against the owner's `main`. Check the latest target revision and required checks before merging; preserve branch protections.
- [ ] Verify the merge, synchronize the clean primary checkout and remove only this task's clean worktree and merged branch.

## Execution record

- Ruling: put supplier Agent guidance in documentation, not a new registered Skill, to preserve the current bundled-skill contract.
- Baseline: task updated to `ee07958` before implementation. Only documentation/reference JSON and the local browser README are in scope.
- Historical archive: all 33 manifest entries passed byte-count and SHA-256 checks; later browser records remain separate. No archive publication or relocation is authorized by this check.

- Validation: JSON and observed versions matched; 19 new-document relative links resolved; bilingual structure and technical identifiers matched; 15 files passed personal-path/credential-pattern checks; diff whitespace passed. No runtime suite or live API/browser test was run for this documentation-only change.
- Review: no Critical or Important findings. Corrected the Minor wording issue so supplier_confirmed denotes manual link/specification verification, not supplier confirmation.
