# Contributing

Read [AGENTS.md](../AGENTS.md) before editing. The fork's source is in `src/client` and `src/server`; private state belongs outside tracked files.

English is the canonical language for maintained public documentation. Synchronize the priority `zh-CN` documents after checking the implementation. Keep API fields, CLI arguments, configuration keys, artifact meanings and stable identifiers unchanged across translations. New or modified test comments and diagnostics should be English unless testing localized output.

Use the commands in [operations](operations.md) and the dependency files under `src/server`. Do not delete valid tests, widen ignores, lower thresholds or change expected results to hide defects. Report pre-existing failures and environment limitations separately from regressions.

Inspect branch, remotes, worktrees and submodules before changing them. Do not initialize missing submodules or upgrade gitlinks as part of a documentation audit. Preserve existing work. Follow the session's publishing authorization and use PRs for protected branches. Explain the problem, resulting behavior and actual validation in the PR.

Changes are licensed under [AGPL-3.0](license). Preserve upstream attribution.

## Upstream review baseline

`upstream/main` from [Hector-xue/IvyeaOps](https://github.com/Hector-xue/IvyeaOps) has been reviewed through [`8083402` (v1.13.12)](https://github.com/Hector-xue/IvyeaOps/commit/8083402a3235e77981de2c564a0645c23fda1f89).

- Adopted the Agent console mobile title and floating panel sizing fixes from [#167](https://github.com/Hector-xue/IvyeaOps/pull/167).
- Removed the unused legacy SVG favicon from [#166](https://github.com/Hector-xue/IvyeaOps/pull/166). The app uses the PNG favicon.
- Shared authentication, download and Agent reliability fixes were already ported in [fork #33](https://github.com/runchengxie/store-ops/pull/33). The remaining upstream changes affect retired features or upstream-specific presentation and release files.

Fetch upstream before checking for new commits. Advance this baseline after reviewing the new range and recording adoption decisions.

```sh
git fetch upstream
git log --oneline 8083402..upstream/main
```
