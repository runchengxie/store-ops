# Go supervisor implementation plan

Goal: one durable, bounded, read-only eMAG task supervisor; keep Python business work and existing pause/locking authoritative.
Spec: approved `docs/superpowers/specs/2026-11-08-go-supervisor-design.zh-CN.md`.
Execution: root coordinates independent Go runner and Python fixed bridge; one whole-branch review. Separate from knowledge feature PR.

## Constraints and review focus

- No shell commands from jobs; executable/config absolute and owner-controlled; only fixed Python module `app.supervisor_bridge` with validated action/store/job.
- No credentials in Go, public examples, responses or logs. Existing runtime roots, snapshot guards, pause intent and per-store locks preserved.
- Durable job records before spawn; startup in-flight becomes needs_review, blocks store until owner reconciliation; never automatically retry unknown outcomes.
- One scheduler process per data root via OS-released exclusive lock; maximum concurrency 2 default, bounded 1..8; per-store serialized; bounded retained history 1000 and output 64KiB (discard overflow and fail result).
- Pause stops future dispatch; timeout/cancel requests are cooperative and job-specific. No process killing. Running beyond grace remains blocking/needs_review, never claims stopped.
- State JSON writes must be atomic and durable with cross-platform file replace; validate corrupt/malformed config/state and fail closed. Prefer Go standard library unless a demonstrated requirement needs a small dependency.
- Only queued jobs safe to resume. Periodic due coalesces missed intervals once; unique period identity prevents duplicate dispatch after restart.
- Unknown subprocess/result/bridge error is needs_review with no automatic rerun. Failed jobs need explicit retry/new occurrence policy; no platform-write support.

## Task 1: Go task manager
Files `src/supervisor/` Go module, cmd/store-ops-supervisor, focused internal package/tests; `configs/supervisor.example.json`; Go CI job.
Bridge contract: invoke absolute configured Python with working directory `<repo>/src/server`, `-m app.supervisor_bridge --action status|run|cancel|receipt --store-id ID [--job-id UUID]`. stdout single JSON <=64KiB, stderr discarded. IDs ASCII alnum/-/_ <=80, job UUID hex32. status JSON `{paused:bool,state:string}`; run/receipt `{job_id,store_id,status:complete|paused|failed|running|unknown,receipt_id?:string}`; cancel `{job_id,store_id,cancel_requested:true}`. Missing receipt uses status unknown. `run` exits0 only complete/paused.
- [ ] RED synthetic executor tests: durable claim, concurrent stores, serial same-store, pause, timeout cooperative cancellation, interrupted process recovery, malformed/corrupt state, clock catchup, duplicate supervisor lock, malicious job/config input and bounded output.
- [ ] Implement fixed-argv runner, filesystem state, OS lock and CLI `run --config`, `status --config`; config includes Python/server_dir/data_dir/stores[{store_id,interval_seconds,days?}] (days omit first version use29), max_concurrency, timeout_seconds. Validation exact bounded values.
- [ ] GREEN `go test -race ./...`, go vet, Linux build and GOOS=windows GOARCH=amd64 build; add CI with stable pinned supported version. Record commands and versions.

## Task 2: Python fixed bridge
Files new `app/supervisor_bridge.py`, `app/services/supervisor_bridge.py`, focused tests; narrow `automation_control.checkpoint` extension through ContextVar for job-specific cancellation.
- [ ] RED deny arbitrary action/store/job/path, exact receipt correlation, claimed-before-work, existing pause propagation, cancellation before publication, duplicate job replay, malformed metadata and unknown previous execution.
- [ ] Implement bridge validates fixed args, no configurable command. Use settings.data_dir/emag/supervisor-jobs/<job_id>.json plus cancel marker, atomic immutable identity and guarded updates. Python run calls existing emag_jobs.run with existing credential collection like emag_job_cli. Never read original training files, add merchant writes or expose credentials. Check cancel marker in existing checkpoint using additional ContextVar without weakening pause. New cancellation does not pause whole store.
- [ ] GREEN targeted + full backend checks/Ruff, current monitor regression tests.

## Task 3: Integration, docs and rollout
- [ ] End-to-end Go→Python fake/test data on loopback/no marketplace, restart and timeout verification; review combined current main and both implementations.
- [ ] English/Chinese operation docs, ADR and changelog; explicit limitations and rollback, no claim real stores run in parallel until exercised.
- [ ] PR/checks/merge to user fork; Linux/Windows binary build receipts outside source.
- [ ] Laptop backup and inventory exact task triggers/principals; deploy stable supervisor binary/config and interactive-user launch task. Confirm no old collector in progress, disable only replaced daily trigger after backup; retain manual task and server task. Go inherits existing Python env/runtime root and credentials remain Python-only.
- [ ] Verify status, pause/checkpoint, actual read-only execution through interactive identity and runtime receipts; confirm old trigger disabled/new authority only. Roll back if exact identity/cancel/recovery cannot be verified. Never reset credentials or enable duplicate scheduling.
- [ ] Verify merged checks, clean only this task branch/worktree after deployment validation.
