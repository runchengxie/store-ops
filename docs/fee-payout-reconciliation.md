# Local fee and payout reconciliation

[简体中文](zh-CN/fee-payout-reconciliation.md)

Import source-backed manual evidence to see fee documents, payout observations and explicit allocation links. Estimated payouts, processed payouts and bank receipts remain distinct. This release has no bank ingestion, payment, accounting posting, private eMAG endpoint collector or ERPNext dependency.

## Source and scope

The first supported source is a bounded manual JSON transcription. Real eMAG export formats have not been validated; do not rename an arbitrary CSV/PDF as JSON or claim automatic synchronization. Keep original evidence under your private data root and put its stable identifier in `source_ref`. Importing evidence records what was supplied; it does not verify its truth.

Each import has exactly one store (CLI argument), legal `company`, `counterparty`, `marketplace` and ISO-style three-letter `currency`. Amounts in other scopes are never summed or allocated together. `coverage` is `partial` or `complete` as declared by the operator; any partial/unreviewed batch keeps the scope partial. Complete does not mean audited or bank-reconciled.

From the stable server directory, using its Python environment:

```bash
python -m app.emag_reconciliation_cli --store-id example-ro import --file /private/data/manual-evidence.json
python -m app.emag_reconciliation_cli --store-id example-ro report --locale en
python -m app.emag_reconciliation_cli --store-id example-ro history
python -m app.emag_digest_cli --store-id example-ro --kind weekly --locale en --save
```

Evidence is stored in `store-artifacts/reconciliation/evidence.sqlite3` under `IVYEA_OPS_DATA_DIR`. Ordinary report reads do not create a missing database. The optional digest section is loaded explicitly by the CLI; pure digest builders are unchanged. Missing evidence adds no financial section, invalid local financial evidence shows an unavailable notice while retaining operations figures. Financial summaries have bounded scope/payout rows and an explicit `truncated` flag; the standalone report/history contains source references for tracing totals.

## Manual JSON contract

All fields shown below are required unless marked optional. Unknown fields, repeated JSON keys, float numbers for money, non-finite amounts, scientific notation and more than two decimal places are rejected. Limits: 1 MB input, 500 records per batch, 2,000 current records per scope, 200 lines per document and 30 signed components per payout. Monetary values are decimal strings, bounded to 12 integral digits. Dates use `YYYY-MM-DD`; timestamps require an explicit timezone. External IDs are bounded machine labels, not free-form descriptions.

Synthetic example:

```json
{
  "schema_version": 1,
  "company": "example-company",
  "counterparty": "example-platform",
  "marketplace": "RO",
  "currency": "RON",
  "captured_at": "2026-11-10T10:00:00Z",
  "source_ref": "retained-export-1",
  "source_kind": "manual",
  "review_status": "reviewed",
  "coverage": "partial",
  "records": [
    {"kind":"document","id":"fee-1","revision":"v1","document_type":"fee","amount":"100.00","vat_basis":"inclusive"},
    {"kind":"payout","id":"estimate-1","revision":"v1","status":"estimated","payout_date":"2026-11-17","components":{"receipts":"150.00","fees":"-100.00"},"net_amount":"50.00"},
    {"kind":"allocation","id":"link-1","revision":"v1","document_id":"fee-1","document_type":"fee","document_revision":"v1","payout_id":"estimate-1","payout_revision":"v1","amount":"40.00","confirmed":true,"source_ref":"allocation-export-1"}
  ]
}
```

- Every record has `kind`, `id` and `revision`; a changed observation uses a new revision and `supersedes` naming its current predecessor. Reimporting a previously known revision never rolls back latest evidence. A source revision cannot be mutated; a new batch/provenance alone cannot promote an old record from unreviewed to reviewed.
- `document` also requires `document_type`, signed `amount` and `vat_basis` (`inclusive`, `exclusive`, `unknown`). Optional `document_date`, `service_start`, `service_end`, `due_date`, `observed_at`, `occurred_at` are retained independently. Missing occurrence time is not synthesized from capture time. Optional `lines` contains `{id,amount}` rows whose sum equals the document amount. Optional `reverses_id`, `reverses_type`, `reverses_revision` must be supplied together and refer to an opposite-sign source document.
- `payout` requires `status` (`estimated` or `processed`), `payout_date`, signed `components` and `net_amount` equal to their sum. A processed batch uses a distinct identity and explicitly names `estimate_id` when linked to an imported estimate; reclassifying an estimate under the same identity is rejected. Matching dates or amounts do not establish identity. The estimate remains visible with `superseded_by_processed`. `bank_received` stays unknown even for a processed payout.
- `allocation` references the exact document type/ID/revision and payout ID/revision, signed `amount`, boolean `confirmed` and its own `source_ref`. Optional `document_line_id` targets an existing fee line and enforces its signed capacity as well as the document total. Many-to-many and partial links are supported. Confirmed links require reviewed allocation, document and payout source revisions, plus a VAT-inclusive document amount. Referenced revisions must exist in the same scope; a fabricated revision is rejected rather than classified stale. Unconfirmed suggestions do not change allocated totals. Changed document or payout revisions make old links stale until explicitly corrected.

A positive allocation cannot exceed its document or the payout's negative-component capacity; a credit link must retain its negative sign and fit positive-component capacity. Component capacity is only a consistency bound: it is not proof of which specific fee was deducted. Only source-backed explicit links assert that association. Source identity, document type and currency must already be correct; the importer does not discover them.

## Interpretation

The example keeps payout net **50.00** and document unallocated amount **60.00**. It never deducts the same fee again from payout net. `unallocated_amount` means not linked by current reviewed evidence, not necessarily due for payment. Links to an estimated batch are not proof of completed settlement. Positive fees and negative credits remain separate; there is no automatic netting of unrelated credits. `outstanding_to_pay` remains unknown because the first release does not establish a complete payable/bank reconciliation.

Correct source data with new linked versions; never edit SQLite rows or delete history to force a balance. Reports include original document/payout amounts, source references, batch hashes and issues (unmatched documents or stale links). Treat material mismatches as work to investigate, not instructions to pay.
