# Client-facing operations report content

## Intent and selected direction

The owner requested cleaner client-facing reports and selected product units,
top products and inventory risks as the next enrichment priority. Keep the
existing bot, recipient, scheduler, source snapshots and marketplace boundaries.

Use the existing complete saved snapshots and deterministic calculations. A new
collector is unnecessary for this scope; amount metrics require additional
currency/discount/refund contracts and are a separate future change. The
alternative of adding every possible field to the message would obscure the
operating priorities, so show a compact summary and retain full local evidence.

## Message and evidence

- Main message: inclusive human-readable business dates, last data update,
  current/prior orders and return requests, finalized-order product units,
  up to three top products, inventory risks and at most three useful actions.
- Remove rolling-window totals, raw snapshot IDs and fixed lists of metrics
  not calculated from the normal client message. Keep these in structured
  evidence and the saved local full report. Sending uses only the compact
  `markdown`; `details_markdown` retains evidence for local saved reports.
- Keep source-date basis visible in the date label. Material stale data,
  missing period coverage, unknown quantities and inventory/aging mismatches
  remain visible beside affected figures. Do not conceal real data problems.

## Product metrics

- Group by the same verified-instant or source-calendar periods already used
  for order counts. Do not weaken source/coverage/duplicate/date guards.
- Count current quantities only from finalized orders (`status=4`) and active
  product lines (`status=1`). Whole canceled/returned orders and canceled lines
  do not contribute. The metric is **finalized-order product units at capture,
  grouped by original order date**, not settled sales or goods finalized that day.
- Zero is valid only with a complete period and compatible product evidence.
  Missing/invalid order status, product arrays, line status or quantity prevents
  a complete unit total. Preserve a known subtotal in local evidence only.
- Rank products by units with stable identity and deterministic tie handling.
  Explicitly show ties; do not imply an arbitrary three of five equal products
  outsold the rest. Render only bounded sanitized own-catalog names/SKUs or
  validated product identifiers; no order/customer notes, links or mentions.

## Inventory risks

- Reuse existing snapshot-bound clearance rules for positive-stock products
  with observed validation issues, including product/unit totals and at most
  three SKU-level priorities. These are observed checks, not certified causes
  or automatic repair instructions.
- Show 181+ day units only from complete age bands reconciled to captured
  stock. If other products have unreconciled/missing age data, show the known
  subtotal as partial and the number needing verification; never present a
  partial subtotal as complete inventory aging.
- Prefer positive-stock blockers and reconciled old stock over a blanket
  replenishment instruction for every zero-stock listing. No demand/lead-time
  forecast, automatic purchasing or price changes are added.

## Verification and delivery

Tests cover quantity/status validation, canceled/returned lines, empty periods,
partial evidence, identity/ties, product-label sanitization, reconciled aging,
compact versus local detailed content and existing delivery bounds/idempotency.
Run backend suites/lint/docs and final-head CI, obtain independent review,
merge under standing authorization, deploy stable source/worker and verify
compact real previews. Send a single clearly marked updated daily/weekly pair
to the same authorized owner conversation using the existing correction gate;
keep original messages, receipts and schedule. Clean only this task's branch
and worktree after successful merge/deployment.

Status: owner approved this short specification on 2026-11-09.
