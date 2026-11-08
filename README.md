# store-ops

[简体中文](docs/zh-CN/readme.md)

[Project website and documentation](https://runchengxie.github.io/store-ops/)

[Interactive eMAG demo](https://runchengxie.github.io/store-ops/demo/) · Synthetic data; changes reset on refresh.

A self-hosted eMAG RO operations workspace, forked from [Hector-xue/IvyeaOps](https://github.com/Hector-xue/IvyeaOps). The fork uses imported evidence for inspections, business summaries and local drafts. It separates shared operations infrastructure from a single enabled eMAG adapter. Amazon execution paths are removed.

See [platform adapter boundaries](docs/platform-adapters.md) for the common contract and upgrade behavior.

## Current capabilities

- Read-only eMAG RO collection for offers, selected seller/FBE orders, returns, invoices and VAT data.
- Versioned snapshots, deterministic manual audit reports, bounded change previews and run receipts.
- Administrator workspaces for inspection records, own-catalog research, plans and local Listing drafts.
- [Source-linked local playbooks](docs/emag-playbooks.md) for repair, Listing checks, variants, comparable offers, advertising reviews, inbound packing and cost evidence.
- Local proposal approvals bound to the current snapshot and revision. Approval does not execute a marketplace change.
- A separate, disabled-by-default [admin price API](docs/emag-write-readiness.md) for exact single-offer approval, submission and read-back.
- Read-scoped MCP tools for snapshots, receipts and reports. Saving a local report requires a write-scoped token.
- A schedule preparation page with server-time previews and disabled plan export. No scheduler consumes these eMAG plan drafts.

Purchase costs require seller inputs; scenario estimates are not accounting profit or recommended prices. Market-wide search volume and competitor sales are unavailable. Existing workspaces remain local-only; optional price execution uses the separate API above. No eMAG listing, stock or order writer is exposed. Browser chat and image translation require their configured providers. The deterministic audit CLI needs neither an open console page nor a model.

## Run from source

Source code is in `src/client` and `src/server`. Installers accept Python 3.11+ and Node.js 20+; CI builds use Node.js 22. The locally verified environment is Windows, Python 3.12.13, Node.js 24.22.1 and an installed `ivyea-agent` 1.16.9. Other CI matrix environments are configured, not independently verified by that local run.

Windows:

```powershell
powershell -NoProfile -File scripts/manage.ps1 -Action install
powershell -NoProfile -File scripts/manage.ps1 -Action start
```

Linux/macOS:

```bash
bash scripts/manage.sh install
bash scripts/manage.sh start
```

Installers can install dependencies and optional components. Run them only when you intend those changes. For a command-resolution preview, use `-DryRun` on Windows or `--dry-run` on the Unix entry point. The standard application uses session authentication. A private local development adapter is not part of the distributed login flow.

No fork release containing these source changes is assumed to exist. Upstream release archives do not contain the fork's eMAG changes. Frozen Windows/macOS archives retain their internal `client/` and `server/` layout. Read the [installation and migration guide](docs/installation.md) before upgrading an existing source installation.

## Manual audit

From `src/server`, using its Python environment:

```powershell
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --from-latest
# Read-only network collection using saved Windows credentials
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --days 29
```

`example-ro` is a placeholder for your imported store label. Offline replay requires an existing snapshot and does not claim a fresh collection. Windows network collection reads the Generic Credential target `IvyeaOps/eMAG/RO`. Platform API permissions and IP allowlisting are still required.

## Documentation

English is canonical. Chinese translations follow the same facts and identifiers.

| Topic | English | zh-CN |
|---|---|---|
| eMAG capabilities and migration | [capability map](docs/emag-capability-map.md) | [能力边界与迁移](docs/zh-CN/emag-capability-map.md) |
| Architecture | [architecture](docs/architecture.md) | [架构](docs/zh-CN/architecture.md) |
| Installation | [installation](docs/installation.md) | [安装](docs/zh-CN/installation.md) |
| Configuration | [configuration](docs/configuration.md) | [配置](docs/zh-CN/configuration.md) |
| Usage and contracts | [usage](docs/usage.md) | [使用](docs/zh-CN/usage.md) |
| Operations | [operations](docs/operations.md) | [运维](docs/zh-CN/operations.md) |

See also [repository layout](docs/repository-layout.md), [verification and audit evidence](docs/maintenance-audit.md), [contributing](docs/contributing.md), [security](docs/security.md) and [changelog](docs/changelog.md). Historical decision records and internal plans are not all bilingual.

## License

AGPL-3.0. See [LICENSE](docs/license). Upstream attribution and existing license obligations remain in effect.

- [Market research and profitability](docs/emag-market-research.md)

- [Store status home](docs/store-status-home.md)

- [Optional Go task supervisor](docs/go-supervisor.md)
- [Operational knowledge and checks](docs/operational-knowledge.md)
