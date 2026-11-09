# Operations and verification

[简体中文](zh-CN/operations.md)

## Preserve state

Keep the configured data directory, environment files and credential store out of Git. The source-layout migration preserves their contents; it does not make a backup for you. Inspect a backup before relying on it. Never publish raw store evidence or credentials with a test report.

Source frontend changes require `npm run build` in `src/client`. Backend changes require restarting the specific local service. Verify its PID and ownership first. The Windows stop helper checks this install's executable/command before stopping a PID. Do not kill unrelated listeners merely because they use port 8001.

No eMAG task is registered by the schedule preparation page. The generic Agent scheduler has a different execution path and requires a working Agent/model. This audit did not enable existing or new tasks.

## Checks used by the project

From `src/client`:

```bash
npm run typecheck
npm run test:i18n
npm run test:render
node scripts/check-errtext.mjs
npm run build
```

From `src/server`, using its Python environment:

```bash
python -m pytest tests -q --timeout=120 --timeout-method=thread
python -m pytest app/tests -q --timeout=180 --timeout-method=thread
ruff check .
```

CI separates the backend suites and platform matrix. The server test matrix covers Linux and Windows; macOS CI is temporarily disabled. Install test and MCP-test requirements to avoid dependency-based skips. The local evidence table records actual results, not inferred CI success. The real-component harness uses Vite on 127.0.0.1:5199; it replaces API responses with synthetic fixtures while rendering the production App tree. Never use synthetic fixtures as store evidence.

The repository currently has no configured coverage threshold, dedicated security-scanner gate or dependency-audit CI gate. Do not describe these as passing. `uv pip check` checks installed dependency compatibility, not vulnerability status. `npm audit` needs a registry that supports the audit endpoint; a mirror may return an implementation error.

## Known limits and external boundaries

- A run interrupted before receipt publication may leave only an older receipt. Inspect timestamps and referenced IDs.
- Platform API windows/timezones and invoice service periods are not interchangeable.
- The quality page displays the backend `stock_unknown` summary, including missing, malformed and negative stock values.
- Agent locale resources do not localize the entire workbench. `en-US` is not the saved language ID exposed by the language list.
- IvyeaAgent is an external installed dependency. This audit checks the repository's adapters and installed runtime version, not every upstream release or provider behavior.
- Binary packages and systemd changes require their own environment validation before deployment.

See [maintenance-audit.md](maintenance-audit.md) for the inspected commit/worktree context, findings, checks that ran and checks not executed.

From the repository root, `python scripts/check-docs.py` checks local file links in the maintained entry documents. It does not validate external URLs or heading anchors.

[Browser-assisted FBE checks](browser-checks.md)
