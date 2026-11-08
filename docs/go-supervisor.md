# Go task supervisor

[简体中文](zh-CN/go-supervisor.md)

The optional supervisor schedules fixed read-only eMAG workers. Go owns dispatch and durable task status; Python retains collection, credentials, snapshot publication, business checks and authoritative monitoring pause controls. The TypeScript UI remains unchanged.

## Build and configure

Build from `src/supervisor` with the Go version named in its module and CI:

```bash
go test -race ./...
go vet ./...
go build -o /private/release/store-ops-supervisor ./cmd/store-ops-supervisor
```

Use `configs/supervisor.example.json` as a schema example. Keep actual configuration under the configured private configuration root. Set absolute `python`, `server_dir` and `data_dir`; the latter is the supervisor's private state directory, distinct from the Python runtime root. Run Python from the stable release's server directory so existing settings and credentials load normally. Never point an installed service at a temporary worktree. No credentials belong in supervisor configuration. The current live Python collector uses one Windows credential target. Set `IVYEA_OPS_SUPERVISOR_ACCOUNT_STORE_ID` in the private launcher to that account’s known store ID; missing/mismatched binding rejects live work before collection. Multiple scheduling slots do not yet provide multiple live credential accounts.

```bash
store-ops-supervisor run --config /private/config/supervisor.json
store-ops-supervisor status --config /private/config/supervisor.json
```

First dispatch is due after the configured interval, not immediately on installation. Missed intervals coalesce into one future opportunity instead of a backlog. The default concurrency is two; tasks for the same store remain serial. Waiting for network does not require rewriting existing Python analyses in Go.

## Recovery and pause

The supervisor persists intent before spawning a fixed `app.supervisor_bridge` worker. It never accepts arbitrary shell commands or marketplace writes. The bridge correlates a task identity with the existing Python audit receipt and refuses to execute the same task twice.

The `status` command reads durable task state; verify the operating-system service/task separately for liveness. Existing per-store monitoring pause remains authoritative. Paused queued work rechecks at most once every 30 seconds. Pausing stops new dispatch; active Python collection stops cooperatively at existing request/publication checkpoints. A timeout requests job-specific cancellation and does not pause the entire store. A cancellation request is not proof of termination. No broad process kills are used.

After a supervisor crash, in-flight jobs need receipt reconciliation. A final correlated receipt can settle the record; missing or unknown outcomes block another task for that store and require owner inspection. Never delete a running/unknown record to force a retry. A state/configuration error fails closed. Inspect actual worker activity, receipt identity and existing per-store locks before resolving uncertain state.

This is periodic read-only monitoring, not guaranteed uninterrupted availability: laptop sleep, logout, network and platform outages still affect freshness. The Python application and its Agent scheduler are not replaced.

## Windows rollout and rollback

Use the same interactive Windows identity that can access the existing credential target. Back up the exact old daily task XML, executable/configuration and state. Confirm no collector is running. Install the supervisor in a stable release path; preserve the server task and manual collection task. Disable only the replaced daily trigger before enabling the new scheduling authority. Never let both automatic schedulers own the same store.

Verify startup, a real correlated receipt, pause behavior and restart recovery before considering migration complete. On failure, stop only the identified supervisor, confirm no worker remains active, then restore the backed-up daily task. Do not reset credentials, environment secrets or password hashes to make deployment easier. Deployment-specific paths, task identifiers and validation receipts stay private.

## Language choice

A full Go rewrite is technically possible, but requires replacing tested API, spreadsheet, analysis and knowledge code. This phase deliberately keeps those mature Python components. Rust offers compiler-checked ownership and memory safety, useful where resource control is central; it adds development complexity here. C/C++ offer low-level control without a current demonstrated need. C#/.NET is also viable, especially on Windows, and supports single-file publishing. Go was selected for this small cross-platform task-management boundary, not because the alternatives cannot host long-running services.

References: [Go concurrency](https://go.dev/doc/effective_go#concurrency), [Rust ownership](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html), [.NET single-file publishing](https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview).
