# Browser-assisted FBE checks

[简体中文](zh-CN/browser-checks.md)

The workbench can run a fixed read-only FBE inventory page check alongside API monitoring. When Edge needs human verification or login, only that browser check waits. Complete the verification in Edge, then choose **I’ve verified; continue** in the workbench. The application never solves CAPTCHAs or confirms prices, sends messages, accepts contracts or changes offers.

## What is collected

The worker verifies the configured seller name in the eMAG RO navigation, then records visible product IDs and available quantities. An explicit unavailable quantity remains unknown. Ambiguous formatted quantities or a missing quantity cell require review. A successful check covers **the visible page only**, not all warehouse inventory, aged stock, sales, fees or settlement. Browser observations live separately from the authoritative API snapshots and never replace the API stock totals. The workbench shows their own last successful check time; an old result remains available while a later attempt waits.

The current reader requires the Romanian inventory page contract. An unknown layout, account mismatch or incomplete snapshot requires review instead of producing a success. It creates one task-marked inspection tab and tries to reuse it. A login redirect can remove the marker; close obsolete inspection tabs manually. Keep other automation away from this shared browser while a check runs.

## Private setup

Use the existing logged-in Edge extension bridge on `http://127.0.0.1:8931/mcp`; do not expose it publicly. Configure these environment values in the existing private backend launcher and, for automatic checks, supervisor launcher:

- `IVYEA_OPS_BROWSER_STORE_ID`: exact existing eMAG RO store ID.
- `IVYEA_OPS_BROWSER_ACCOUNT`: exact seller name shown in eMAG navigation.
- `IVYEA_OPS_BROWSER_NODE`: absolute path to the Node executable.
- `IVYEA_OPS_BROWSER_SDK_ROOT`: absolute path to the installed `@modelcontextprotocol/sdk` package directory containing `dist/esm/client/index.js`.
- `IVYEA_OPS_BROWSER_AUTO_CHECK=1`: optional. A successful existing supervisor API run queues a browser check if none exists or the last successful check is at least 24 hours old. Waiting tasks are never automatically retried.

No new scheduler or MCP token copy is required. A short-lived Node-owned loopback listener on port `8932` prevents overlapping readers even if their Python parent exits; it accepts no commands and closes with the reader. A port conflict leaves the check waiting. The bridge owns extension authentication. Node/MCP SDK must already be installed on the browser machine; these are optional prerequisites, not new Python server dependencies. This source-checkout worker needs `scripts/browser-fbe-reader.mjs` and its contract/lease modules; frozen packages must include those assets before enabling it. Restart the specifically identified backend after changing its environment. Keep settings private, outside source and worktrees.

## Durable state and recovery

`IVYEA_OPS_DATA_DIR/browser-checks` holds SQLite task intent, exclusive task/browser leases and immutable normalized observations. Records contain no raw MCP transcripts, login tokens or CAPTCHA answers. One FBE task per store coalesces repeated interruptions. Revisions reject stale resume requests; task and browser locks prevent concurrent readers. A process restart releases its SQLite lease; a recorded in-flight read becomes `needs_review`. Queued work can be explicitly dispatched again. Only this fixed read-only task supports retry; never apply its replay model to merchant writes or support messages.

Global monitoring pause prevents dispatch. Final publication is serialized with pause acknowledgement using the control database transaction. It does not cancel a browser read already waiting on a bounded tool call. The browser wait does not reserve a Go API slot. Browser errors must not change an already successful API receipt. The initial version has no automatic network retry loop or external notifications: retry explicitly from the workbench. Local browser availability still depends on the laptop, logged-in desktop, extension and platform session.

Authenticated administrator endpoint: `POST /api/operations/stores/{store_id}/browser-check`, `{}` to create or re-dispatch queued work, or `{"revision": N}` to resume/check again. Overview includes `browser_check` and `browser_check_available`; it does not return filesystem paths or full observations. The fixed owner CLI `python -m app.browser_worker STORE_ID TASK_ID` can execute queued intent using the same private settings.

For server migration, first separate API credentials from the current Windows credential target and validate account binding and deployment independently. Moving the API scheduler cannot remove website verification or make the laptop browser continuously available.
