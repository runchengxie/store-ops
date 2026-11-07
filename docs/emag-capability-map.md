# eMAG capability map

[简体中文](zh-CN/emag-capability-map.md)

This map describes the current fork, not the complete eMAG Marketplace API. The implemented collection targets eMAG RO and produces local evidence. Platform permissions and an allowed source IP are still required.

The [eMAG API overview](https://marketplace.emag.ro/infocenter/emag-academy/how-to-add-a-product/product-import-through-api-or-feeds/?lang=en) describes product and offer listing, stock and price updates, and order processing. Platform support does not mean this fork implements them or that a particular seller account has permission to use them.

| Area | Available now | Boundary |
|---|---|---|
| Offers | Read selected fields and inspect pagination-complete snapshots | No marketplace listing or offer submission |
| Orders and returns | Read selected seller/FBE counts and source-labelled records | No order acceptance, fulfilment or refund execution |
| Inventory and price | Inspect collected fields; separate opt-in single-offer price API | No inventory sync, automatic repricing or verified profit; see [price API](emag-write-readiness.md) |
| Local operations | Create snapshot-bound drafts, proposals and manual execution records | Approval and execution records do not call marketplace write APIs |
| Reports and agents | Create manual receipts and local reports; scoped MCP tools read evidence | Tokens and administrator permissions still apply; no password or general eMAG write proxy |
| Scheduling | Preview a server-time schedule and export a disabled draft | No scheduler currently consumes eMAG drafts |
| Research and translation | Explore the store's own catalog; configured providers can translate images | Catalog distribution is not market demand or competitor sales |

The fork now enables only the eMAG adapter. Amazon-specific APIs, legacy pages, skills and background tasks have been retired; private historical data and credentials are preserved. The separate price API is disabled by default; production permissions and concrete values still require verification. Product content, stock and order writes remain unimplemented.

## Moving toward an eMAG-focused project

1. Inventory consumers of each legacy route, API, CLI, skill and stored artifact.
2. Match each required workflow to verified eMAG data and platform capabilities; record gaps and permissions.
3. Provide data retention and migration instructions, then announce deprecation to actual consumers.
4. Retire a legacy capability only after its consumers have migrated and the replacement has been validated.

These are evaluation steps, not a promise that all marketplace operations are already supported.

See [architecture](architecture.md), [usage](usage.md) and the [code audit](code-audit-2026-10.md) for evidence and remaining limitations.
