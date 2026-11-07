# Repository working agreement

This is the canonical instruction file for coding agents. User and session instructions, including existing publishing authorization, take precedence.

## Project and layout

This AGPL-3.0 fork has shared operations infrastructure and exactly one enabled eMAG RO adapter. Do not reintroduce Amazon implementations, provider registrations or legacy routes; preserve private historical data during migration. React/Vite code is in `src/client`, FastAPI code in `src/server`, management entry points in `scripts`, and maintained docs in `docs`. Data, credentials and private exploration belong in ignored local storage, never personal notes unless the user requests it.

Use `IVYEA_OPS_DATA_DIR` from the local server environment or process environment for application data; see `configs/server.env.example` and `docs/configuration.md`. Keep private exploration and generated artifacts outside tracked files. Do not publish personal absolute paths or credentials.

## Work process

Use the five-step flow: understand scope, design, review the design, implement fully, verify. Do not skip required confirmation when scope is unapproved. Existing authorization remains valid; do not repeatedly ask for an already authorized action.

Before editing, verify consumer contracts, actual sources and runtime/tool versions. Inspect branch, remotes, worktrees and submodules. Preserve existing changes. Do not initialize missing submodules or advance gitlinks just to complete an audit.

Validate UI changes in the real App component tree through `src/client/harness`, using computed browser values and an isolated profile. Do not substitute handwritten mock pages. Check every consumer of an interface change. Report actual evidence before claiming success.

## Commands

```bash
cd src/client
npm run typecheck
npm run test:i18n
npm run build
```

From `src/server`, use its Python environment for `python -m pytest` and `ruff check .`. CI configuration is in `.github/workflows/ci.yml`. Frontend changes require a build. Backend changes require restarting the specifically identified authorized local service. Never use broad process-name kills.

## Documentation and tests

English is canonical. Maintain the priority `docs/zh-CN` translations without adding facts absent from English. Keep machine identifiers, schemas, parameters and artifact semantics unchanged. Do not imply whole-product i18n from the Agent subtree's localization. New or edited test diagnostics/comments default to English except localized fixtures.

Record user-visible changes in `docs/changelog.md`. Add an indexed ADR for architectural decisions or dependency tradeoffs. Internal historical notes need not all be bilingual. Do not rewrite history into claims about the present implementation.

Do not delete valid tests, widen ignores, lower thresholds or change expected values to hide defects. Record lint, typecheck, test, coverage, security and dependency-check baselines. Distinguish existing failures, regressions and checks that could not run. Do not claim a configured CI job actually ran.

## Publishing and cleanup

Push, PR, merge, release, deployment and cleanup require applicable user/session authorization. Honor standing authorization already granted. Use PRs for the selected target branch, preserve protections, and never force-push to bypass them. Do not publish a binary release without resolving its intended IvyeaAgent release reference.

After an authorized merge, verify the tested commits are in the target before deleting only this task's merged branches or safely owned temporary worktree. Keep the main workspace and user data. Preserve unresolved work when checks fail.

## Compatibility

Preserve source and frozen-bundle layouts through `app/core/layout.py`. Keep existing environment secrets and password hashes during migration. Use public package registry URLs in the lockfile. Environment keys use `IVYEA_OPS_*`; integration-specific exceptions are defined by code. New local services bind to loopback and use the established authentication boundary. Review source configuration and current runtime settings rather than assuming that a changed default changes stored behavior.
