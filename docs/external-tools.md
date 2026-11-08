# Independent supplier and browser tools

[简体中文](zh-CN/external-tools.md)

Use independently installed tools through your configured Agent when supplier research or browser inspection is needed. store-ops does not directly invoke the sibling tool directories. Neither tool is required to start the application or replay imported evidence.

## Responsibilities and versions

| Component | Owns | Does not provide |
|---|---|---|
| store-ops | Store identity, evidence interpretation, local records, approval and audit rules | Automatic supplier search or a bundled browser executor |
| `1688-product-find` | External CLI for supplier search and comparison | Confirmed purchasing cost, procurement or eMAG identity matching |
| `@playwright/mcp` | Browser transport exposed to a consuming Agent | Business approval or proof that an operation succeeded |

The [reference inventory](../configs/external-tools.reference.json) records the inspected supplier revision and installed browser package version. It is not loaded by the application and does not pin or install tools automatically. Metadata inspection is not an authenticated compatibility test. Keep a local record of the actual source revision/package version, Python or Node runtime and tool configuration used for each task. Before an upgrade, verify the interface against the new version in an isolated task and preserve its evidence; do not silently treat a new version as the recorded baseline.

Keep supplier source independently checked out at the recorded revision, or record the replacement revision explicitly. Manage Playwright MCP in an independent npm installation with an exact dependency version and its lockfile; use that installation's lockfile for repeatable reinstalls. Do not install dependencies or check out another revision merely to read this guide. The supplier checkout inspected here has no license file; this stage does not copy or redistribute its source.

## Local configuration

Resolve tool installation paths explicitly in your private Agent/launcher configuration. Sibling directory names and the current working directory are not discovery contracts. There are no new store-ops environment keys or tool settings in this stage.

The external supplier tool owns its authorization. Its inspected skill names `ALI_1688_AK`; preserve the existing authoritative credential storage and follow that tool's reference instructions. Do not copy credentials into this inventory, shell history, reports or repository files. Missing authorization is an unavailable capability, not permission to invent results or bypass the tool through a browser search.

For browser use, configure the independently installed MCP server in the consuming Agent using its private settings and existing browser connection. A JSON template or helper directory is not automatically registered. Preserve extension tokens and browser login state; do not export cookies. An existing persistent diagnostic worker is optional and does not register tools for store-ops.

## Agent workflows

For supplier discovery, follow [supplier research](supplier-research.md). This is documentation for a configured Agent, not another automatically mounted Skill. Search can produce candidates; associating them with an eMAG offer and confirming actual cost remains a separate recorded decision.

For eMAG browser work, use the existing [price-validation instructions](../skills/emag/price-validation/SKILL.md). Keep one MCP connection per task, inspect its current tool definitions and page state, and verify seller, market and exact offer identity. Installing a tool or approving this integration design does not authorize marketplace changes. Preserve exact-action approval, fresh preflight, selected-count checks and outcome read-back. A timeout or unknown result stops submissions; never replay an uncertain write automatically.

## Evidence and private data

Use the established project data configuration; see [configuration](configuration.md). For a new Agent task, an optional organizational convention is `external-tools/<task-id>/` beneath the resolved application data directory (`IVYEA_OPS_DATA_DIR`). This is a manual folder convention, not a new automatic importer or application setting. If your project has a separate authoritative evidence root, use that explicit contract instead. Do not derive permanent paths from a temporary worktree or create a new data root by guessing.

Retain task identity, tool revision/version, query or authorized operation, observation time with timezone, source identifiers, raw private evidence, interpretation and limitations. Redact credentials before saving evidence. Shared `current` or `latest` pointers require a separate coordinated publication step. Existing files remain where they are until their consumers and retention requirements have been inventoried.

The machine-local 2026-11-03 browser exploration archive had 33 manifest entries verified by size and SHA-256 during this stage. Later browser records also exist outside that archive. Archive integrity does not establish complete coverage, merchant-write outcomes or present tool readiness. No historical records were relocated or deleted.

## Future application integration

Add a small supplier adapter only when a concrete application workflow needs it. Define structured input/output, version compatibility, credential ownership, timeouts, error handling and evidence import before connecting a UI or scheduler. Keep business interpretation and approvals in store-ops. Source vendoring, submodules, tool upgrades and automatic registration are separate decisions; see [ADR-0059](decisions/0059-independent-external-tools.md).
