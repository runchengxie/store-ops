# 0058: Durable automatic monitoring pause control

Status: accepted

The homepage needs a real pause acknowledgement rather than a cosmetic animation toggle. Store pause intent in a per-store SQLite database under the runtime data root and expose a versioned admin control through the common operations API. The eMAG adapter remains the only enabled platform.

Keep Windows schedules intact. All current scheduled eMAG monitoring enters the serialized audit worker, which checks pause intent before collection, at outbound request boundaries, and before publication. Reuse its cross-process SQLite lock to distinguish pausing from paused. Resume enables future invocations without silently launching a new collection. Existing in-flight HTTP calls may finish; forceful process termination is not used.

The control intentionally governs automatic monitoring rather than explicit conversations or separately approved marketplace writes. The development demo provides a local simulation. A backend failure never produces an optimistic paused state.
