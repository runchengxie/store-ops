# 0062: Independent browser-assisted checks

Accepted: 2026-11-09.

The Go supervisor only understands correlated, non-replayable API worker receipts. Reusing those IDs for resumable browser interaction would conflate verification waits with unknown API outcomes and block unrelated collection.

Use a separate SQLite task ledger for one fixed read-only eMAG FBE reader. An optional post-success hook on the existing supervisor starts it; it owns no independent API schedule. Human verification waits release browser/task locks and require explicit resume. Recorded in-flight reads become reviewable after a crash. Store pause remains authoritative. No writes or arbitrary browser tools are available through this task protocol.

Normalized browser page observations retain explicit partial coverage and their own timestamps. They do not replace API snapshots or become settlement/profit evidence. The private seller binding and Romanian page contract fail closed. The cost is an optional Node/MCP deployment prerequisite and a shared interactive-browser availability boundary. A future marketplace writer needs a separate approval, idempotency and outcome-reconciliation protocol.

See [operations](../browser-checks.md).
