# Repository layout

Independent supplier/browser tools remain outside this repository. Their [integration guide](external-tools.md) and [supplier workflow](supplier-research.md) define Agent use; the [reference inventory](../configs/external-tools.reference.json) records observed versions without vendoring source or registering tools.

Source code lives in `src/client` and `src/server`. Management scripts use English names under `scripts`; maintained docs use kebab-case under `docs`. Root README.md, AGENTS.md and tool entry points remain conventional; `docs/license` and `docs/version` hold source metadata, and Ruff rule files are in `configs`. Frozen bundles retain a root `VERSION` for compatibility. `.github/CONTRIBUTING.md` and `.github/SECURITY.md` link to their canonical document bodies.

See [installation](installation.md) for source/bundle differences, safe environment migration, systemd migration and Windows/Unix commands. See [configuration](configuration.md) for settings precedence. Private `data` remains outside `src` and outside commits.

The sidebar keeps task/automation and eMAG daily pages visible. “All tools” defaults to eMAG daily operations. System terminal, monitoring, external Agents, freight and user management are grouped as advanced tools. Search covers all permitted categories. Pinning, direct routes and keyboard navigation remain available. Hiding navigation does not change backend permission checks.
