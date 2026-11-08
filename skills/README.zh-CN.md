# 内置 eMAG 技能

[English](README.md)

store-ops 仅提供以下平台技能：

| 技能 | 用途 |
|---|---|
| `emag/store-audit` | 通过有权限的 MCP 工具，基于导入资料复核 eMAG 店铺 |
| `emag/price-validation` | 基于证据与既有审批边界，核对具体 eMAG 改价方案 |

`app/core/skill_paths.py` 将内置技能补入配置的应用 `SKILLS_ROOT`，不覆盖已有技能文件。`agent_skills.register_roots()` 仅将存在的 `emag` 目录提供给 Agent，与用户自有目录合并，并移除本应用原先精确管理的 Amazon 目录注册。不删除私有技能或覆盖无关设置；损坏的配置保持不变并报告。

首次安装仍需配置共享 Agent 运行时。挂载说明不授予 MCP 或平台写入权限。目录结构为 `<domain>/<skill>/SKILL.md`，可附带引用资源。Amazon 实现已移除，原始记录保留在 Git 历史中。
