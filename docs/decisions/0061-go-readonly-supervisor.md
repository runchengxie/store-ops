# 0061: Go supervisor with Python read-only workers

Status: accepted

Introduce an optional small Go supervisor for durable periodic dispatch, concurrency bounds and receipt reconciliation. Retain Python business/analysis and existing per-store pause and run locks. The only worker interface is a fixed local Python module with validated store and task identity; no arbitrary shell commands or credentials in Go.

Persist intent before spawn. Uncertain outcomes require correlated receipt reconciliation and block store re-entry. Cancellation is cooperative; timeout does not prove termination. Windows deployment must replace exactly one automatic scheduling authority with backup and rollback, preserving manual/server tasks and existing credential identity.

Go is chosen for this independent cross-platform service boundary. A full rewrite would duplicate tested spreadsheet, API and analysis functionality without an established bottleneck. Rust, C/C++ and C# are viable alternatives with different complexity/ecosystem tradeoffs; long-running reliability still depends on durable state and supervision, not language alone.
