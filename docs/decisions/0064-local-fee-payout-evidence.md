# ADR 0064: Local source-backed fee and payout evidence

Date: 2026-11-10. Status: accepted.

## Context

Operational snapshots and cost scenarios cannot establish whether a charge was allocated to an estimated or processed payout. Source export shapes have not been validated, and order status does not establish cash receipt.

## Decision

Add an append-only, scoped manual-evidence store and exact-decimal reconciliation. Explicit revision-bound allocation links can associate many documents with many payout observations; estimates remain separate from processed batches. Keep original source references, versions, dates and unallocated credits. Add the report section at the digest CLI I/O boundary, leaving pure operational builders unchanged.

Start with a documented bounded JSON transcription contract. Do not guess private marketplace endpoints, parse arbitrary PDF/CSV formats or create a recurring financial collector. Keep payment and bank/accounting execution outside this component. Borrow ERPNext's separation of source documents and payment allocation without adding an ERPNext dependency or copying its source.

## Consequences

The first release exposes evidence gaps and cannot declare an amount payable or bank receipt. Manual review and source identity are required; a later official format adapter must be validated separately. Existing operational reports remain usable without financial evidence. See [usage and schema](../fee-payout-reconciliation.md).
