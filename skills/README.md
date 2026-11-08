# Bundled eMAG skills

[简体中文](README.zh-CN.md)

store-ops ships only these platform skills:

| Skill | Purpose |
|---|---|
| `emag/store-audit` | Source-bound review of imported eMAG evidence through scoped MCP tools |
| `emag/price-validation` | Check a concrete eMAG price proposal against evidence and the existing approval boundary |

`app/core/skill_paths.py` seeds bundled skills into the configured application `SKILLS_ROOT`, without overwriting existing skill files. `agent_skills.register_roots()` exposes only the existing `emag` directory to the Agent, merges it with arbitrary user roots, and removes the exact historical application-managed Amazon mount. It does not delete private skills or replace unrelated configuration. Corrupt settings remain unchanged and are reported.

A fresh installation needs the shared Agent runtime configured before it can execute skills; mounting instructions does not grant MCP or marketplace write permissions. The layout is `<domain>/<skill>/SKILL.md` with optional referenced assets. Amazon implementations are removed; Git history retains the old source records.

Independent supplier and browser tools are not bundled or automatically registered. See [external tool setup](../docs/external-tools.md) and [supplier research guidance](../docs/supplier-research.md) for the Agent-mediated workflow. This guidance adds no new skill mount or marketplace permission.
