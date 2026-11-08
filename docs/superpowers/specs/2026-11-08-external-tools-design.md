# External tools: first-stage integration design

Date: 2026-11-08
Status: Proposed; implementation awaits scope approval.

## Intent and scope

Keep supplier discovery and browser automation independently installed while store-ops owns business interpretation, evidence and approvals. This stage documents an Agent-mediated workflow; it adds no application endpoint, runtime dependency, browser executor or automatic tool registration.

## Observed baseline

- No direct application invocation of the sibling 1688 CLI or browser helper directory was found in the inspected source, scripts or configuration.
- Supplier discovery source: `next-1688/1688-product-find`, revision `2c7d8ee014ec24c730e5ddc966c70f2495891543`; its skill declares version `1.7.0`. No license file was found in the local checkout. Record this as an observed revision, not an end-to-end compatibility claim.
- Browser transport: independently installed `@playwright/mcp` version `0.0.84`. Existing eMAG price-validation instructions already require a persistent authorized connection and exact scoped approval for submissions.
- Historical browser evidence has a 33-entry hash manifest. Later browser records also exist outside that archive. Neither the presence of the archive nor old README claims establish complete coverage or the outcome of later actions.

## Approaches

1. Selected proposal: independent tools plus repository-owned contracts and Agent guidance. Retains independent upgrades and avoids copying private runtime files; requires explicit local configuration and version recording.
2. Submodule/gitlink: pins source but burdens consumers with another checkout and does not solve credentials, browser connections or evidence handling.
3. Vendoring or rewriting: increases maintenance and redistribution obligations before application-level integration is needed. Reconsider a small API adapter only when a concrete UI or automation requirement exists.

## Deliverables

- Bilingual external-tools guide linked from configuration/layout documentation.
- A machine-readable reference inventory containing public source, observed revision/version, role, integration mode and verification limits. It is documentation, not an installer or executable allowlist.
- Repository-owned supplier-research Agent instructions: inspect the external CLI references, use structured returned data, retain supplier/specification/source/time and uncertainty, and explicitly separate candidate quotations from confirmed procurement cost.
- Preserve current browser approval rules; link guidance rather than duplicate a second executor.
- An indexed ADR documenting this boundary and its alternatives.
- Correct the local browser README's retired-path statement without modifying connection configuration or claiming historical writes did not occur.

## Data and configuration

Private credentials and MCP settings remain in their existing authoritative locations. Resolve application evidence storage from the established project configuration; document project data roots without inventing machine paths. Read-only inventory/hash verification is allowed. No data relocation, deletion, latest-pointer update, merchant action, credential change, external-source modification or tool installation belongs to this stage.

## Validation and follow-up

Check JSON parsing, referenced files/anchors, EN/zh-CN parity, diff whitespace and absence of personal paths/secrets in new public files. Report archive integrity separately from later-record coverage. No fresh 1688 API call or browser action is required, and no claim of runtime compatibility follows from these document checks. Application UI, transport adapters and archive consolidation remain future scoped work.
