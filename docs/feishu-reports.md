# Daily and weekly Feishu reports

[简体中文](zh-CN/feishu-reports.md)

Generate a source-labelled eMAG summary from saved evidence and deliver it
through an existing Lark CLI bot. Hermes is not required to run. Reports never
collect from the marketplace, change an offer, or execute a suggested check.

## What a report means

Daily reports describe the previous calendar day; weekly reports describe the
previous Monday through Sunday. The default business timezone is
`Europe/Bucharest`, including daylight saving changes. Every message states its
period, snapshot identity, capture time and freshness. Stock is a capture-time
observation, not historical daily/weekly stock or verified sales.

Order and return **record** counts include cancelled and other statuses. Counts
for a period and its preceding period require explicit, aware source dates and
a verified collection window covering that period. A trusted producer must
explicitly set the boolean `commercial_summary.window.timezone_verified: true`
after independently verifying the source filter contract; a missing/negative
note is not verification, and changing this flag alone cannot verify data.
Repeated identities are
deduplicated; inconsistent identities make the count unavailable. The current
collector labels its API filter timezone unverified and normally saves naive
order dates. Such snapshots show **unavailable period counts** and separately
labelled captured-window totals. They do not imply yesterday/week sales or a
verified sales trend. Reporting does not silently repair this source contract.

Missing inventory is unknown, never zero. Data older than 24 hours is marked
stale. Reports include up to three deterministic checks for freshness, zero or
unknown stock, and missing date evidence. These are review prompts, not proven
root causes. No revenue, profit or recommended prices are calculated. No
customer identities, free-text source notes, credentials or raw snapshots are
included in the delivered JSON. Full source evidence remains local.

## Generate locally

From a stable installation's `src/server`, use its Python environment:

```bash
python -m app.emag_digest_cli --store-id example-ro --kind daily
python -m app.emag_digest_cli --store-id example-ro --kind weekly --locale zh-CN --save
```

`--save` additionally writes an immutable report through the existing report
artifact store under `IVYEA_OPS_DATA_DIR`. Without it, generation is read-only.
A missing snapshot produces an explicitly unavailable report; invalid or
unreadable evidence fails with a fixed diagnostic, not an apparently empty
store. Reports default to English; select `--locale zh-CN` for Chinese. Use the
same `--timezone` and locale in generation and delivery.

## Configure delivery

Copy the schema example [digest-delivery.example.json](../configs/digest-delivery.example.json)
to the owner's private deployment configuration directory. Resolve real paths
from the machine's configured roots; examples are placeholders, not installation
paths. Keep actual app/recipient identifiers and SSH commands private.

- `enabled`: explicit opt-in; defaults in the example to `false`.
- `store_id`, `app_id`, `recipient_open_id`: the exact source store, existing
  CLI app and owner's **app-scoped** Open ID. An Open ID from a different app
  cannot be reused. Delivery always uses bot identity, never the user's token.
- `cli_command`: argv beginning with an absolute existing CLI or bot-only
  wrapper. Existing credential storage remains authoritative. Bot readiness is
  checked against `app_id` before a send, but is not proof of sending permission.
- `source_commands.daily` / `.weekly`: fixed trusted argv, beginning with an
  absolute executable, returning the generator's JSON. The example assumes the
  working directory is `src/server`. For cross-machine use, configure existing
  batch-mode SSH to a fixed generator command in a stable installation. Return
  only bounded report JSON, not raw snapshots. No listener or secret copy is
  needed. Do not point at temporary worktrees.
- `state_dir`: absolute private data directory for delivery receipts, separate
  from configuration and credentials. The durable SQLite ledger contains the
  prepared message, target identity, period and snapshot reference.
- `timeout_seconds`: per-command limit, greater than zero and at most 120.

The scheduled service must have the same local identity, CLI credentials and
executable environment as the verified manual send. Use an absolute Python
executable and an explicit stable `src/server` working directory. Windows
generators need `tzdata` for IANA timezone names when the operating system has
no zone database. It is included as a Windows-only server requirement; Linux
continues to use its system timezone database.

Preview without sending or creating a delivery ledger:

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --preview
```

After checking the actual report, set `enabled` to `true` in private deployment
configuration and explicitly send the first daily/weekly report:

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily
python -m app.emag_digest_delivery --config /private/config/digest.json --kind weekly
```

Without `--kind`, delivery selects due reports: daily after 09:00 local time,
weekly after Monday 09:10. Run it periodically, for example every 15 minutes
with a scoped systemd user timer. It catches up only the latest eligible daily
and weekly periods; it does not replay a historical backlog. Before 09:00 a
missed prior daily message is not sent. Schedule interpretation uses the
configured business timezone, independent of the host timezone.

Keep the existing collector's scheduling authority unchanged. Reporting reads
its results; it must not enable the old daily collector alongside a supervisor.
Laptop sleep, network loss and host logout can still delay delivery. Check the
OS timer/service and source snapshot timestamps separately.

## Receipts and uncertain outcomes

Success requires CLI exit 0, JSON `ok: true`, bot identity and a returned
`message_id`. Merely getting HTTP 200 or a CLI exit 0 is not sufficient. The
delivery ID is also passed as the CLI's idempotency key. A committed intent
precedes submission, so overlapping invocations cannot submit the same period
twice. Prepared payloads are immutable in the ledger, even if newer source
data becomes available later.

- `delivered`: receipt contains the verified message ID.
- `rejected`: a structured CLI error was received; retained without automatic retry.
- `unknown`: a timeout, malformed response, nonzero ambiguous response, or
  interrupted `sending` intent. It is **never automatically retried**, including
  after a restart or the server's deduplication window expires.

A source-read or app-preflight failure occurs before submission and may be
retried on a later timer tick. Terminal unknown/rejected periods do not block
later periods. Exit 1 indicates a retained non-success receipt; exit 2 is a
fixed configuration/source/preflight failure. Inspect the private ledger and
CLI/environment before changing anything. Reconcile an unknown result against
the target conversation and its delivery key/message content. Do not delete a
row to force a resend; a deliberate corrected resend is a separately reviewed
operation. Disable only the reporting timer or set `enabled: false` to stop
new reports; preserve ledger history and existing collection tasks.
