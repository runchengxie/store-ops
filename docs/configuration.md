# Configuration

[简体中文](zh-CN/configuration.md)

## Startup and runtime settings

A reference template is available at [`configs/server.env.example`](../configs/server.env.example). For a new installation, copy it to `src/server/.env` in a source checkout or `server/.env` in a frozen bundle. Fill in the required values and preserve any existing configuration.

Startup environment variables are read by `src/server/app/core/config.py`. Source installations load `src/server/.env`, falling back to legacy `server/.env` when needed. Frozen installs retain `server/.env`. `IVYEA_OPS_ROOT` can explicitly select the runtime root. Existing process environment values take precedence over dotenv values.

The standard runtime dependencies include SOCKS support for HTTP proxy environments.

Runtime-editable settings are stored in `hub_settings.json` under the configured data directory and managed through the application's system settings. Fallback rules are integration-specific. Do not assume every empty runtime key has an environment fallback. `src/server/app/core/hub_settings.py` and the consuming integration define the actual keys.

| Key | Default/meaning |
|---|---|
| `IVYEA_OPS_HOST` | `127.0.0.1` |
| `IVYEA_OPS_PORT` | `8001` |
| `IVYEA_OPS_DEV` | `0`; development CORS/cookie behavior differs |
| `IVYEA_OPS_SECRET` | Generated temporarily when absent. Set a stable secret for persistent sessions |
| `IVYEA_OPS_USER` | `admin` |
| `IVYEA_OPS_PASSWORD_HASH` | bcrypt password hash |
| `ADMIN_PASSWORD` | Startup plaintext alternative when no hash is configured, converted to a hash |
| `IVYEA_OPS_ALLOWED_ORIGINS` | Comma-separated allowed browser origins for state-changing requests |
| `IVYEA_OPS_COOKIE_DOMAIN` | Empty, host-only cookie |
| `IVYEA_OPS_DATA_DIR` | `<runtime-root>/data` |

Set `IVYEA_OPS_DATA_DIR=~/data/ivyeaops/runtime` in the local environment file to keep runtime data outside the checkout. `~` expands to the current user's home. Stop the service and back up existing data before copying it to a new location; changing this setting does not migrate files. CLI and server processes must use the same value. Process environment variables override the environment file. Other tools and local scripts may use separate paths.

The server and CLI must also run under the same user account when using `~`. Local logs and diagnostic output may still contain absolute paths; moving the data directory does not redact existing records. If the old data contains `.master.key`, preserve it with the encrypted settings.

For localhost browser use, configure the actual origin, such as `http://127.0.0.1:8001`. A reverse proxy needs its own HTTPS origin. Development mode changes security behavior and is not a production shortcut.

## eMAG credentials and modes

Optional price execution reads `IVYEA_OPS_EMAG_WRITES_ENABLED` (default `0`) and `IVYEA_OPS_EMAG_WRITE_STORE_ID` (default empty) at server startup. Both must permit the exact store. See [price API](emag-write-readiness.md). These settings do not grant existing local approvals or MCP tokens marketplace submission rights.

The network job CLI reads the Windows Generic Credential target `IvyeaOps/eMAG/RO`. Saving a website password in the browser is not equivalent. This target is not an environment key or a public API field. The browser UI does not read the password. Platform API credentials must have the required access and IP allowlisting.

`--days` accepts integers 1–29, default 29. `--from-latest` reads an existing snapshot without network collection or credential access. Import/replay can be used on other platforms, but the current saved-credential network entry is Windows-specific.

The standard application still has session authentication and administrator checks. A machine-local development adapter is outside the published authentication contract.

## Models and integrations

Supplier discovery and browser inspection use independently configured Agent tools; see [external tools](external-tools.md) for version records, private configuration and evidence boundaries. The [reference inventory](../configs/external-tools.reference.json) is documentation and is not loaded at startup.

Console chat and image translation need their configured providers. Image translation supports RO/BG/HU as target languages, not additional connected eMAG stores. Deterministic evidence collection, offline audits and local drafts do not require a model.

Only the eMAG commerce adapter is enabled. Retired Amazon provider defaults and automatic registrations are removed; existing private values are preserved. Generic external Agents remain separate integrations. Installing a skill does not grant platform access. GBrain is no longer the knowledge base runtime; old GBrain setup instructions and environment examples should not be used.

## Locale configuration

Only the Agent subtree currently has i18next localization. Its stable English resource ID is `en`, not `en-US`. `zh-CN` is the default saved preference, and missing translations fall back to `en`. Unsupported saved values fall back to the default. The main workbench has no global locale setting. Locale selection is presentation and must not change API keys, schemas, IDs, evidence or calculations.
