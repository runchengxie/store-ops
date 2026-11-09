# Daily and weekly Feishu reports

[简体中文](zh-CN/feishu-reports.md)

Generate a source-labelled eMAG summary from saved evidence and deliver it
through an existing Lark CLI bot. Hermes is not required to run. Reports never
collect from the marketplace, change an offer, or execute a suggested check.

## What a report means

Daily reports describe the previous calendar day; weekly reports describe the
previous Monday through Sunday. The default business timezone is
`Europe/Bucharest`, including daylight saving changes. Every message states its
inclusive business dates and last data update. Stock is a capture-time
observation, not historical daily/weekly stock or verified sales.

Order and return **record** counts include cancelled and other statuses.
The report distinguishes two date bases:

- **Platform calendar dates** (`date_basis: platform_calendar`): the existing
  complete RO collector's naive record dates are grouped directly under the
  same naive date filters that selected them. Its official source URL, resource
  coverage and known collector window contract must match; all records must
  have compatible dates inside that window. Coverage of the full current and
  previous periods is checked independently. No UTC offset is assigned and no
  verified Romania-time instants are claimed. Scheduling and capture timestamps
  still use the configured timezone.
- **Verified timezone instants** (`verified_timezone`): aware source dates plus
  a covering aware window require explicit boolean
  `commercial_summary.window.timezone_verified: true` from a trusted producer
  that has independently verified the filter contract. Missing/negative notes
  are not verification, and changing the flag alone cannot verify data.

Repeated identities are deduplicated. Conflicting identities, mixed/missing
dates, unsupported source contracts or incomplete coverage keep the affected
figures unavailable; they do not become zero. The current collector normally
uses the first basis. Window totals remain separate from period figures.
Order statuses are those observed at capture, grouped by the original order
date: finalized does not mean settled profit or an order finalized that day.
Return counts use request insertion date, not a completed-refund date.
See the official [eMAG API contracts](https://marketplace-api.emag.ro/api-doc)
for `OrderSave.date`, order date filters, RMA filters and the separate status codes.

Missing inventory is unknown, never zero. Data older than 24 hours is marked
stale. Reports include up to three deterministic checks, prioritizing stocked
offers with validation issues and reconciled older stock, alongside material
missing data. These are review prompts, not proven
root causes. No revenue, profit or recommended prices are calculated. No
customer identities, free-text source notes, credentials or raw snapshots are
included in the delivered JSON. Full source evidence remains local.

The client message contains period results, comparisons and priority checks.
It omits rolling-window totals, raw snapshot IDs and fixed statements listing
metrics that are not calculated. These are evidence notes, not runtime errors.
The structured `evidence` and `details_markdown` retain window provenance,
snapshot identity and interpretation limits; `--save` stores the full detailed
report locally. Bot delivery uses only compact `markdown`. Material stale data,
missing coverage and unknown inventory stay visible in the client message.

## Product units and inventory risks

Finalized-order product units sum current nonnegative integer quantities on
active lines (`status: 1`) of finalized orders (`status: 4`), grouped by the
same source-date period as order counts. Canceled/returned/pending orders and
canceled lines do not contribute. Missing statuses, quantities or finalized
product arrays prevent a complete total; known subtotals remain in local
evidence. Zero requires complete period evidence. Current/prior comparisons
use the same rule. These are capture-time quantities, not units fulfilled or
settled during the period.

Show up to three products by units with stable product-identity tie ordering,
and explicitly indicate ties that extend beyond the displayed products.
Missing product identity prevents a complete ranking even when unit quantities
are known. Display bounded sanitized own-catalog SKUs or validated product IDs;
never use customer/order notes or render source links/mentions.

Inventory risk metrics reuse the existing clearance checks: positive-stock
products with observed validation issues, involved units and up to three SKU
priorities. 181+ day units include only complete age bands reconciled to
captured stock. Unreconciled/missing products remain a visible verification
count and the known aging subtotal is labelled partial. A zero-stock listing
does not automatically imply a purchase requirement. These checks do not set
prices, execute repairs, forecast inventory coverage days or place orders.

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
operation. For an explicitly authorized correction to a confirmed delivered
period, use a stable correction ID and explicit kind:

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --correction-id calendar-metrics --preview
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --correction-id calendar-metrics
```

The new message is visibly marked as a correction and links back to the original
delivery in the ledger. Its original row/content is preserved. Repeating the
same correction ID cannot resend it. Unknown or rejected originals are refused;
scheduled mode cannot enable corrections. Preview remains read-only with
respect to the delivery ledger, and does not establish that an original exists.
Disable only the reporting timer or set `enabled: false` to stop
new reports; preserve ledger history and existing collection tasks.

## Optional PNG report images

[简体中文](zh-CN/feishu-reports.md#png-图片报告)

Set `"image_enabled": true` in the existing private delivery configuration to send
one PNG long image after each successful text digest. The default is false. No
change to the bot application, recipient or source commands is needed after both
source and delivery installations have been updated. New source digests include a
bounded `visual` payload derived from the same saved snapshot. For a one-time migration, optionally set `image_legacy_before` to an explicit
timezone-aware timestamp at the moment image mode is first enabled. Keep this
cutoff fixed; do not advance it on later deployments. Invalid/naive/future
cutoffs are rejected before external I/O. Only confirmed text deliveries whose
controller-persisted `created_at` is strictly before that cutoff, with no
`visual` field or explicit omission marker, return `image_status: skipped_legacy`
without rendering, uploading or sending, and the CLI exits successfully.
Without an explicit cutoff, missing visual data is `unavailable`. The source
report generation time is never used to classify a legacy delivery. Fresh
reports that omit optional content to fit the serialization budget remain
failures rather than being silently treated as old periods. Existing text receipts are preserved; old periods are
not backfilled automatically. Use a new deliberate correction after updating
the source to send a fresh text/image pair. An explicit invalid or omitted
visual payload remains `unavailable` and is still a delivery failure.

The image contains period KPIs, previous comparisons, a seven-day order-creation
trend, tied top-product ranking, observed order states, current inventory risks,
optional fee/payout observations and priorities. Snapshot stock is not period
sales; estimated or processed payout is not bank receipt. Missing or incomplete
series never become zero bars. Aged stock is labeled as the reconciled portion.
Source dates and current observation times remain distinct.

Pillow is already a runtime dependency. Chinese rendering requires a local CJK
font. The renderer checks the configured `font_path` (absolute path), then the
`IVYEA_OPS_REPORT_FONT` environment variable and supported installed Noto/Windows
font locations. An explicit invalid font does not silently fall back. Every rendered character is checked for a missing glyph, including mixed-language
product labels in English reports; unsupported glyphs fail closed. Single-line
labels are fitted to available pixel width. Financial panels show their own
capture time and coverage, and superseded estimates are labeled rather than
presented as current payouts. Rendering failure leaves text delivery intact
and returns `image_status: render_failed`; a later run may retry rendering.

Text and images use independent persisted delivery claims. Images are rendered
from the confirmed text's retained payload, rather than a newly generated report.
The image is uploaded as binary stdin to the configured bot CLI; no arbitrary
source-supplied local path or URL is uploaded. Success requires the bot identity,
an uploaded image key and the separate sent image's `message_id`. Upload success
alone is not delivery. Interrupted/uncertain image submission is terminal
`unknown`, and explicit rejection is retained without automatic replay. Existing
text is never resent just to retry an image. Use a new reviewed correction ID for
an intentionally new text/image pair. A disabled image mode preserves the old
receipt shape and behavior. Preview does not render, upload, send or claim.

Images live under the configured private delivery `state_dir/images`, named by
the delivery key. Use a stable private state path, never a temporary worktree.
`font_path` is machine-local configuration and must not be committed.

To render a saved source digest without sending:

```bash
python -m app.emag_digest_cli --store-id example-ro --kind weekly --locale zh-CN > /private/data/report.json
python -m app.emag_digest_visual_cli --report /private/data/report.json --output-id weekly-preview
```

The output is created under `IVYEA_OPS_DATA_DIR/digest-images/<store>/`; existing
output IDs are not overwritten. The renderer returns the path and snapshot ID.
The width is 1120 pixels; height and file size are bounded. Inspect real daily and
weekly images for missing glyphs, wrapped labels and complete source notes before
enabling scheduled image delivery. Financial coverage in the image is only as
good as the explicitly imported reconciliation evidence.

The Ubuntu `app-tests` CI job explicitly installs `fonts-noto-cjk` so Chinese
rendering tests run against real glyphs on clean runners; they are not skipped
when a CI image omits system fonts. Production hosts still need their own font
installation or explicit `font_path`.
