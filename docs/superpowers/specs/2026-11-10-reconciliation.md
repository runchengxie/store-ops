# Fee and payout reconciliation: proposed first slice

Status: approved design. Date: 2026-11-10.
Chosen direction: lightweight fee and payout reconciliation inside store-ops.
Source revision: 8ca226257830a58bc1d39b4ef1f11adb0d5daca8 (local and fetched origin/main agree).

## Outcome
Explain which platform charges belong to which payout, what remains unmatched, and whether a payout is estimated or processed. Never treat an order, credit, allocation, or estimated payout as bank cash received.

## Current implementation verified
- emag_business.py projects bounded order/return evidence and invoice category/number/date/net/tax/gross/currency, with duplicate-identity and pagination checks. It does not currently project payout batches or document-allocation relations.
- emag_commerce.py already stores supplier SKU and cost inputs with revisions. Its contribution calculation is explicitly a scenario, not accounting profit. Supplier SKU is not yet a general effective-dated item mapping model.
- emag_digest.py / emag_digest_metrics.py group orders by source calendar dates and use the captured current order state. This is not a timestamped fulfillment/refund/settlement event ledger.
- Existing operations and exact-price execution safety boundaries remain in place.

## ERPNext concepts to adopt
1. Payment reconciliation allocates existing payments/credits to invoices; it is distinct from bank movement.
2. Corrections retain the old record and link a reversal/replacement rather than silently rewriting history.
3. Source document references and detail-row identity matter as much as a displayed balance.
4. Stock ledger/reconciliation and internal item identity are useful later; do not create stock movements from snapshot differences.
Reviewed docs are current/unversioned; source examples inspected from version-15 are illustrative, not a pinned deployment or exhaustive source audit. No source code will be copied as part of this design.

## First-release scope
- Local read-only platform evidence import, reconciliation calculation and a Chinese/English report section using the existing locale convention.
- First source path: owner-provided official structured exports or bounded manual transcription with source reference and review status. Support actual formats only after inspecting samples. No assumed private API, PDF parser, browser scraper or recurring collection schedule in this slice.
- No payment, marketplace writes, automatic ledger posting, ERPNext installation, bank account ingestion or formally reconciled profit calculation.
- Roll out reporting only after evidence coverage and identity checks pass. Missing financial data must not break existing operational reports.

## Records
- ImportBatch: store/company/counterparty/marketplace, source kind, capture time, raw artifact reference, content hash, schema version, coverage/completeness.
- FeeDocument and FeeLine: external document identity and type, line identity when supplied, currency, exact decimal signed amounts, VAT basis, document/service/due dates, source version and reversal links. Duplicate document IDs in different types/entities must not collide.
- PayoutObservation: stable external batch ID if supplied, otherwise a distinct provisional identity for a dated estimate; status, capture time, projected sales receipts, fees, adjustments and net amount. A later processed batch is explicitly linked, never assumed identical based on date alone.
- Allocation: source-backed document/line to payout relation, amount, currency, source reference and confirmation state. Many-to-many; partial allocations supported. Manual suggestions remain unconfirmed and cannot clear a debt.
- ReconciliationIssue: missing coverage, unmatched documents, ambiguous identity, inconsistent totals or currency mismatch.

## Rules
- Store decimal values without binary-float money arithmetic; preserve source signs and distinguish VAT-inclusive/exclusive values.
- Repeated identical imports do not create new charges. Changed content creates a linked observation/version. Never deduplicate by amount/date alone.
- Sum only within the same store, legal entity, counterparty scope and currency. Do not automatically net an unallocated credit against overdue debit.
- A fee already represented in a payout is not deducted a second time from the payout net.
- Estimate revisions change the latest forecast view while retaining history. Processed payout still does not prove bank receipt.
- If only current order state/modified timestamp exists, record an observation; do not invent a refund occurrence date.
- Reports show source time and coverage, estimated net and confirmed allocations separately. When complete relations are absent, outstanding-to-pay remains unknown rather than inferred from unrelated totals.

## Acceptance examples
1. Reimporting a file leaves counts and amounts unchanged.
2. A correction retains both source versions without double charging.
3. One document allocated across two payouts and one payout covering several documents reconcile without over-allocation.
4. An estimate becoming processed retains the original estimate and requires an explicit identity link.
5. A late refund preserves service/occurrence/observation dates where actually provided.
6. Missing fields are unknown, mixed currencies refused, incomplete pagination/import coverage visible.
7. An unallocated credit cannot silently clear a charge; the platform headline and payout forecast are not added together without line-level evidence.
8. Every summary total drills down to source documents and allocations. Legacy report operation survives absent reconciliation evidence.

## Dependencies before implementation
Inspect one actual structured payout export and fee/document export, including identity, status, currency, sign, date and allocation columns. If unavailable, implement only the bounded manual evidence import and mark reconciliation coverage partial. Choose no hidden endpoints from rendered UI requests.

## References
- https://docs.frappe.io/erpnext/payment-reconciliation
- https://docs.frappe.io/erpnext/immutable-ledger-in-erpnext
- https://docs.frappe.io/erpnext/stock-reconciliation
- https://docs.frappe.io/erpnext/maintaining-suppliers-part-no-in-item
- https://raw.githubusercontent.com/frappe/erpnext/version-15/erpnext/accounts/doctype/payment_entry/payment_entry.py
- https://raw.githubusercontent.com/frappe/erpnext/version-15/erpnext/stock/doctype/stock_ledger_entry/stock_ledger_entry.json

Retirement: retain as design evidence; supersede by an approved repository spec if implementation proceeds. Runtime dependencies: none. No production configuration changed.
