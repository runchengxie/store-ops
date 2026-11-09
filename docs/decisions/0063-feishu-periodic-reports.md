# ADR-0063: Evidence-bound reports through the existing bot CLI

Date: 2026-11-09

Status: accepted

## Decision

Store-ops owns deterministic daily/weekly reports from existing saved evidence.
Use stdlib `zoneinfo` and a Windows-only `tzdata` requirement because Windows
does not generally provide an IANA timezone database.
Delivery invokes the owner's existing Lark CLI with explicit bot identity and
an expected application ID. The private deployment may fetch bounded report
JSON over existing SSH; credentials remain at the CLI host. Hermes is not an
automatic runtime dependency, and no listener or marketplace writer is added.

A durable intent is committed before sending. CLI success requires `ok: true`,
bot identity and a message ID. Uncertain outcomes are retained without automatic
resubmission. Prepared payload and identity remain in the delivery ledger.

## Alternatives and consequences

A webhook is suitable for groups but does not serve the selected existing-bot
direct conversation. A Hermes cron job adds agent availability and cost to a
deterministic task. Copying application secrets to each generator duplicates
credential management. Reusing a fixed CLI preserves the existing auth boundary
at the cost of an explicit deployment dependency and CLI output contract.

Naive platform dates and the current unverified API filter timezone cannot
prove calendar-day/week sales. Reports label those period figures unavailable,
show captured-window context separately, and preserve stock/return/source
limitations. Sales, revenue or profit require separately verified contracts.

See [usage and recovery](../feishu-reports.md).

## Correction: calendar date labels are useful without a verified offset

The initial report builder withheld every period count for the current collector,
making daily and weekly messages effectively the same window summary. Keep the
verified-instant guard, but separately permit source-bound API calendar-label
counts when the known naive window and all record dates are compatible and
cover the complete requested period. Label this basis explicitly; do not set
`timezone_verified` or rewrite historical snapshots. Independently check prior
coverage and keep unknown values distinct from zero. A bounded private live
read verified the API's date-filter results against saved record identities.

Use manual, stable correction IDs to deliver corrected already-confirmed reports
without deleting their original ledger entries or weakening unknown-send gates.

## Client content and local evidence

The generated report separates compact delivery `markdown` from local
`details_markdown` and structured `evidence`. Normal bot messages show operating
results, date basis, last update and priority checks. Window-wide counts, raw
snapshot identities and fixed statements about metrics not calculated remain
in the local detailed report saved by `--save`. Material stale/missing/partial
evidence remains visible in the client message. JSON period boundaries retain
their exclusive-end contract; human dates show the actual inclusive last day.
