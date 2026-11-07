# Platform adapters

[简体中文](zh-CN/platform-adapters.md)

store-ops retains a shared operations core and **one enabled adapter: eMAG RO**. There is no disabled Amazon implementation to reactivate. A store is an account/market instance, not a separate adapter class.

The common core owns authentication, permissions, AI sessions, MCP transport/tokens, generic scheduling, approvals/audit, evidence storage and the status UI. The eMAG adapter owns endpoint and field interpretation, credentials, pagination, platform validation, fee assumptions and specialized workflows. Existing eMAG services remain implementation details behind this small port; this is not a universal ERP resource schema.

## Common read port

Administrator endpoints under `/api/operations`:

- `GET /platforms`: enabled descriptors, adapter versions and capability declarations.
- `GET /stores`: current source-labelled store references.
- `GET /stores/{store_id}/overview`: platform/market/currency/timezone, snapshot/source/time/coverage/limitations, bounded product/issue/stock metrics and collection receipt.

The registry explicitly enables `emag` and fails closed for other adapters. Capabilities distinguish supported, unsupported and unverified. Runtime readiness is separate: a supported implementation may still need configuration or complete evidence. `price_update` identifies the existing separate opt-in workflow; the common read port does not authorize or dispatch writes. Existing `/api/emag` extension endpoints preserve their own administrator, snapshot/revision and approval checks.

Unknown data remains unknown. Current overview aggregation does not normalize raw PNK or other vendor identifiers into a fabricated universal product ID. Platform-specific source fields and projections remain in the original evidence. Existing IDs, snapshots, CLI and `IVYEA_OPS_*` keys remain compatible; old snapshots are not rewritten by this extraction.

## Retired features

Amazon-specific pages, endpoints, algorithms, background initialization/jobs, MCP handlers, skills and provider provisioning are removed. Old product URLs/APIs return ordinary not-found behavior. Generic reporting/image/math helpers are retained only where shared consumers exist. Current product prompts no longer assume ASIN/BSR or Amazon policies.

Stored historical snapshots/databases, credentials, unknown private setting values and task records are retained. Exactly application-managed Amazon skill roots are retired without deleting files or arbitrary user roots. Default settings/catalog responses no longer offer the retired providers. Existing external MCP configuration is not rewritten.

Tasks explicitly referencing known retired application skill/tool identifiers fail before Agent dispatch with a capability-retired result; their original records remain. Arbitrary prose is not classified with keyword guesses. A separately installed external Agent and user-owned private tools are outside this repository's removal guarantee. store-ops does not provision its former Amazon integrations into those runtimes.

## Adding another platform later

Implement a descriptor and the minimal operations port, validate account/market identity and source semantics, declare actual supported capabilities and register the adapter explicitly. Preserve provenance, completeness and vendor extensions. Add a write capability only with concrete endpoint allowlists, credential binding, approval scope, revision/live-preflight and read-back contracts; an HTTP POST may be a platform read endpoint, so verbs alone do not establish side effects.
