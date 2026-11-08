# Usage, CLI and evidence contracts

The optional [single-offer price API](emag-write-readiness.md#single-offer-price-api) is admin-only, disabled by default and separate from local workspace approvals. It has no frontend submission button; preparation and approval are local, while execution requires an exact digest, explicit confirmation and configured store binding.

[简体中文](zh-CN/usage.md)

## Daily workflow

After login, `/workbench` opens a compact store overview with four evidence metrics, up to three prioritized checks and a permanent Agent conversation. More opens detailed tools and account settings. Chat defaults to text, send/stop and the effective permission state; Options reveals the remaining controls. The view is designed for a desktop screen; narrow screens switch between Overview, Suggestions and Conversation without clearing the conversation.

Ask assistant (问助手) prefills a question with the selected store, snapshot and exact product references; only Send calls the configured Agent. An existing conversation remains bound to its original store and snapshot after changing the overview store. Start a new conversation for the selected store explicitly, after waiting for or stopping an active task. History lists this browser's per-user store/session references, not a complete cross-device history.

The public Pages demo uses the same compact layout with labelled preset replies, no real model calls and memory-only history. Its More menu exposes only supported demo detail pages; refresh resets all demo conversations.

The project site includes an interactive eMAG demo built from the workbench components. It uses fictional data and an in-memory mock; refresh resets its changes. The demo cannot connect to a backend and does not provide real marketplace operations. Its interface is currently mostly Chinese. The source installation remains separate.

1. Collect or explicitly import an eMAG RO snapshot.
2. Inspect source time, coverage and limitations before using the business pages.
3. Investigate issues and record a proposal locally.
4. An administrator can approve a current-source proposal with a note and revision check.
5. Record any actual manual execution separately, then collect a newer snapshot for review.

The cockpit and research pages use own-store evidence. Catalog distribution is not market demand or share. Listing drafts are local text, not submitted listings. Costs are missing until supplied, so profit and recommended selling prices are not computed.

The eMAG dashboard offers management and specialist views of the current snapshot. Its cards show collected offer, order, stock, invoice and issue observations where available; absent figures are marked unavailable. Issue counts cover observed flags, with unknown price status, documentation status and stock shown separately; absent unknown counts are not treated as zero. The specialist view links to the inspection workflow. The data source, capture time and order window remain visible. Views do not change the snapshot or trigger marketplace operations.

The page labelled Approvals separates local eMAG records from general Agent permission requests. Accepting an Agent request may resume a command or file write. An eMAG local approval does not perform that action.

The inspection page filters observed issues by product, reason, stock and local workflow state. Specialist links open the matching issue in the specified store’s current snapshot; an unavailable store or issue is reported instead of silently selecting another. Details show captured price, stock and available platform messages alongside local history. See [eMAG write API readiness](emag-write-readiness.md) for prerequisites for future marketplace writes.

## CLI

### Optional manual Windows task for SSH

On Windows with PowerShell 7, an interactive user session can run the existing read-only eMAG job on demand when an SSH session cannot read its saved credential. From a source checkout, install the optional task under the account that owns the credential, then trigger it from SSH as the same user:

```powershell
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action install -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action run -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action status -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action uninstall -StoreId example-ro
```

`example-ro` is a placeholder. Install creates an on-demand task with no scheduled triggers and refuses to overwrite an existing task. The Windows account must remain logged in, the checkout and its server venv must remain at the installed path, and the account needs access to the eMAG credential and API. Run waits up to 180 seconds by default for a new job receipt; a timeout does not cancel a running task. Check status before retrying. Status can show an older receipt, so compare its time and run ID. Uninstall removes the managed task only and retains credentials and data. No marketplace writes are performed. A successful local test does not guarantee every Windows SSH or task configuration can access the credential.

The integration keeps its latest control receipt and trigger lock under `%LOCALAPPDATA%/ivyeaops/emag-ssh-task/<store>/`; these files are separate from the application's configured data directory and its backups. The task uses its own user-session environment and server `.env`, which can differ from the SSH process environment and proxy settings. Install from the permanent checkout, not a temporary worktree. If the checkout moves, uninstall from the old path and reinstall at the new path.

Use the `run` entry point to trigger this managed task. Direct Task Scheduler calls bypass its caller lock, so a simultaneous external trigger can make the receipt ambiguous. `-Days` is fixed at installation; uninstall and reinstall to change it.

For a single read-only SKU check, run `.venv/Scripts/python.exe -m app.emag_cli --sku example-sku` on Windows (use `.venv/bin/python` on Unix). This queries `part_number` and prints bounded offer evidence with a capture time; it does not import a snapshot or change marketplace data. `found` requires one exact match, `not_found` means no result was returned, and ambiguous, malformed or failed responses are `incomplete`. A missing result is not proof of delisting. Do not combine `--sku` with `--store-id`; `--describe --sku example-sku` makes no request. `evidence_truncated` flags truncated text or status evidence on found results. Output may contain private seller data.


From `src/server`, using the installed venv:

```powershell
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --from-latest
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --days 29
.venv/Scripts/python.exe -m app.emag_workflow_cli --store-id example-ro
```

On Unix, use `.venv/bin/python` instead. `example-ro` is a placeholder, not an account lookup. `app.emag_cli` collects offer evidence, `app.emag_business_cli` collects the combined selected evidence, and `app.emag_job_cli` adds comparison, report and receipt handling.

`app.emag_cli --describe` describes collection without reading credentials or calling eMAG. `--prompt` accepts hidden interactive credentials on supported terminal platforms. The combined business/job collection path uses the saved Windows credential; offline `--from-latest` needs no credential.

For supported structured validation errors, new collections retain up to eight compact `error_details` entries per status: `code`, `section`, the platform's `en_GB` message and optional `extra_info`. Text is limited to 256 characters per field; URLs and email addresses are replaced. `error_details_truncated` indicates omitted or shortened entries. The full submitted product document and error identifiers are not retained. Other sensitive content may remain in platform messages, so snapshots remain private. Older snapshots keep their original placeholder and are not retroactively enriched.

Job exits: 0 means the report/receipt stage completed, 1 means a recorded stage failed, 2 means an invalid/unavailable job entry, storage problem or busy lock. Check the receipt rather than treating an old successful run as the current result. Forceful termination can leave no new receipt.

For a manual local transition, supply `--snapshot-id`, `--issue-id`, `--state`, `--revision`, `--note`. Review additionally requires the explicitly inspected newer `--review-snapshot-id`. State order is `pending` → `proposed` → `approved` → `executed` → `reviewed`. There is no automatic approval or rejection/rework transition.

## Artifacts

Snapshots and reports live below `store-artifacts` in the data directory. Each artifact is limited to 2 MB. Reports bind an existing `snapshot_id` and include its source evidence. Store/report identifiers allow 1–80 ASCII letters, digits, underscores or hyphens, beginning with a letter or digit. `captured_at` requires a timezone.

Minimal synthetic import example, not real store evidence:

```json
{
  "store_id": "example-ro",
  "platform": "emag",
  "marketplace": "RO",
  "captured_at": "2026-10-28T00:00:00Z",
  "source": "synthetic-example",
  "coverage": ["offers"],
  "limitations": ["Synthetic example, not verified store data"],
  "data": {"offers": []}
}
```

Save it as a local file and run `python -m app.store_cli import-snapshot FILE` from the installed backend environment. `read-snapshot STORE_ID` and `read-report REPORT_ID` read stored artifacts. The snapshot read tool returns the import's `snapshot_id`; latest means the latest import, not necessarily the newest collection timestamp.

Run receipts are in `store-artifacts/jobs/<store>/`. Modes are `fresh_collection` and `existing_snapshot`. A receipt records stage, status, source/baseline IDs, report ID and timestamps. The change preview is limited to 200 entries and 64 KB, with `change_count` and `changes_truncated`. Full referenced snapshots remain the evidence for omitted changes.

The manual audit report lists up to 100 current issue records with SKU, stock, compact platform evidence and the earliest observation in the current snapshot and at most 50 earlier imported snapshots with matching store, marketplace, source and coverage. It labels an incomplete history scan. This is not the time the issue began. For fresh collection, a compatible prior snapshot supplies the baseline; a missing observation is not proof of resolution. Up to 50 baseline issues not observed in the current snapshot are listed. Replay has no change baseline. The existing receipt and snapshot formats remain unchanged.

Missing stock is not zero. Numeric 10 and string `10.00` compare as the same value. An absent product is an observation, not confirmed delisting. Invoice amounts preserve reported signs/currencies and do not establish payment, cost or profit. Return requests are not proof of refunds.

## APIs and MCP

Administrator REST routes under `/api/emag` include store listing, boards, workspace, drafts, local issue transitions and job receipt reads. The browser does not expose a credential-read or job-run endpoint. Browser mutations retain session/Origin checks.

| MCP tool | Scope | Effect |
|---|---|---|
| `ivyea_store_snapshot` | `read` | Read imported evidence |
| `ivyea_emag_job_status` | `read` | Read latest recorded manual run |
| `ivyea_report_read` | `read` | Read saved local report |
| `ivyea_report_save` | `write` | Save a local source-bound report |

MCP uses bearer tokens at `/api/mcp`; session login does not replace the token. These tools do not modify a marketplace. Amazon keyword tools are retired; only enabled adapter capabilities are exposed.

## Schedule preparation

`/schedules` previews a future cron in server timezone and exports a JSON draft with `enabled=false`, `registered=false`, `scheduler_connected=false`. No current scheduler consumes it. `/schedules?tab=agent` is the existing model-dependent prompt scheduler. Do not infer automatic eMAG execution from a draft or from a manual run receipt.

## Procurement and operating scenarios

The Analysis tools workbench provides local, revision-checked supplier records for products in the current eMAG RO snapshot. Enter a canonical HTTPS 1688 offer URL, exact supplier specification and explicit human confirmation. Search similarity is not evidence of an actual procurement match. No supplier is automatically selected and no 1688 quote tracking is scheduled.

All expense inputs are per unit. Missing values block the contribution estimate; enter zero only when the expense is confirmed absent. CNY-to-RON conversion is an explicit user input. The raw eMAG sale_price excludes VAT and is used directly as revenue before expenses. The entered VAT rate is applied only to construct a hypothetical VAT-inclusive price for the user-entered gross-price commission assumption. This commission basis is a scenario input, not a verified platform fee rule; subtract it and the entered unit expenses without deducting VAT from net revenue again. It does not infer recoverable purchase VAT, corporate tax or accounting profit. Reference quotations and actual procurement inputs remain distinguishable. The quote timestamp and source notes should record provenance; no current exchange rate is fetched.

Replenishment uses explicitly entered daily demand, lead time, safety days, inbound and reserved stock. It computes ceil(max(0, demand*(lead+safety)-(captured stock+inbound-reserved))). These are manual planning scenarios, not verified forecasts or purchase orders. Validate usable stock, cancellation/return effects, supplier MOQ and case sizes before purchasing.

Price/stock previews bind the current snapshot and show old/new values. They cannot execute marketplace updates. Issue ownership is independently versioned and persists across snapshots; proposal approvals retain their original snapshot binding and do not carry forward automatically.

## Deterministic diagnostic handoffs

New snapshots include schema_version=1. Old snapshots without that field load as version 1 without rewriting their files. Evidence/Finding/Action retain legacy fields and add typed evidence, entity/version references, field paths and explicit dependencies. Legacy notes default to inference.

The administrator diagnostics endpoint returns bounded, deterministic platform-issue review findings. Local proposals retain their diagnosis; approval checks the current store, product, snapshot, captured field values and registered rule/action dependencies. Missing values are null with a reason; valid stock zero remains observed. Estimates and arbitrary derived values have no decision-grade verifier in this version. Historical proposals without structured diagnosis require a new proposal against fresh evidence.

Job reports include bounded JSON diagnostic handoffs. decision_gate reports included_findings_valid, findings_checked, findings_total, truncated and all_findings_verified separately. A truncated report is not verification of every store issue. These checks establish internal evidence consistency, not marketplace source accuracy.

The research page groups captured return-request reasons by product and normalized reported text, deduplicating repeated cases. It reports missing reasons, unmatched products and malformed rows. These requests are not confirmed refunds and cannot represent overall satisfaction. Local Listing drafts receive conservative claim warnings for selected certifications, functions and measurements; no flag is a compliance pass, and images are not inspected.

## Procurement revision history

Procurement edits no longer stop at 100 revisions. Each revision is archived separately in the existing private commerce database, within the same transaction as the latest record. Existing inline history is copied on the next successful edit; conflicting archive data aborts the edit instead of overwriting evidence. New revisions record the source snapshot ID; legacy revisions retain their original fields without invented provenance.

Latest records still include only the most recent 100 history entries. Administrators can page older history with GET /api/emag/stores/{store_id}/commerce/{product_id}/history and the exclusive before_revision cursor returned as next_before. Each page contains at most 100 entries. Existing authentication and backup boundaries apply.

## Existing-stock clearance

The dashboard and playbook provide an existing-inventory clearance view. It performs no procurement, replenishment or marketplace updates. Known positive stock with tracked price/documentation/block flags sorts first, followed by positive stock with reconciled inventory older than 180 days, then remaining positive stock. Unknown and zero stock are separate. Within a group, verified 365+ and 181+ quantities and stock break ties; there is no predictive business score.

Aging priority requires all seven known bands (0-30, 31-60, 61-90, 91-180, 181-270, 271-365, 365+) to be nonnegative integers and reconcile to captured total stock. Unknown/mismatched aging is labelled and excluded from aged-unit subtotals. Observed blocker flags are not a complete check that an offer is sellable.

A stock-change review uses the closest compatible scanned snapshot at least seven days earlier. It reports matched known-stock products and net inventory decrease, separately counting newly observed and unobserved products. The interval may exceed seven days; disappearance is not treated as a sale or zero stock. Returns, transfers and adjustments can also move stock. Raw order-status counts remain observations, not verified sales, cash receipts or sell-through forecasts.

Operators can follow issue links or create a local source-bound playbook draft for a product. Exact price changes and cash-recovery estimates still require human review and historical cost/fee evidence. No automatic markdown or purchase order is generated.


Price-basis correction: previous scenario results treated raw sale_price as VAT-inclusive and could understate net revenue. Inputs and historical reports are preserved; current scenarios recalculate using the corrected contract. The official API defines recommended_price as pre-discount recommended retail price, and min_sale_price/max_sale_price as seller limits; none is a verified recovery threshold. See https://marketplace-api.emag.ro/api-doc.

### Clearance follow-up

Administrator `GET /api/emag/stores/{store_id}/clearance-review?baseline_snapshot_id=...` and read-scope MCP `ivyea_emag_clearance_review` return imported-stock priorities and an optional explicit earlier baseline comparison. Omit the baseline to inspect the queue only. The queue is not approval; stock decrease and disappeared price rejection do not prove sales, storefront availability or settled cash. Source and coverage must match, capture time must advance, and SKU/PNK mismatches are excluded. Use [the portable price-validation skill](../skills/emag/price-validation/SKILL.md) with separately authorized browser tools; no browser-write endpoint is added.
