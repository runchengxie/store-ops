# 架构

可选平台价格执行使用独立管理员API及SQLite台账，不复用本地异常审批或MCP报告写入权限。店铺绑定、实时预检、不确定送达阻塞和回读语义见[ADR-0052](../decisions/0052-separate-emag-price-api.md)及[价格API](emag-write-readiness.md)。

[英文权威版本](../architecture.md)

## 组件边界

| 组件 | 职责 | 边界 |
|---|---|---|
| `src/client` | React/Vite 页面、显示偏好和模型服务界面 | 前端显示不授予后端权限 |
| `src/server` | FastAPI 认证、API、证据、本地记录与集成 | eMAG 工作台接口要求管理员 |
| `scripts` | 安装、启动、更新和部署辅助 | DryRun 只解析，不执行操作 |
| `data` | 配置指定的私有状态 | 不提交店铺证据和报告 |
| IvyeaAgent | 外部 Agent 运行环境与模型服务集成 | 通过已安装依赖的 CLI/HTTP 契约消费，不是 submodule |

当前检出的仓库没有 `.gitmodules` 或 gitlink。Agent 前端代码随本仓库保存。本次没有初始化缺失仓库、升级 gitlink 或修改相邻仓库。

`app/core/layout.py` 区分仓库根与源码根。源码在 `src/client`、`src/server`，冻结包保留资源目录旁的 `client`、`server`。仓库级 docs、skills 和 `data` 不移入 `src`。

## eMAG 证据流程

`emag_business.collect` 使用固定 RO 只读端点并投影选定字段，完整采集后由 `publish` 保存新快照。顺序 API 读取不是平台的原子视图。订单时间、发票日期和服务期间含义不同，平台筛选时区仍未核实。

手动任务读取或采集证据，存在基线时比较观测，保存绑定来源的报告和回执。每店锁防止此入口并发运行。采集失败保留旧快照，进程崩溃或存储失败可能没有新回执，须检查 run ID 和时间。

这些 API 以追加方式保存快照和报告，普通本地文件不是防篡改存储。`StoreSnapshot` 包含源码、coverage、limitations 和带时区的 `captured_at`。原有 schema version 1 快照保持兼容，不自动改写历史资料。ID 和结构化键不翻译。

本地草稿和处理记录使用 SQLite，绑定店铺、快照和商品。状态为 `pending`、`proposed`、`approved`、`executed`、`reviewed`，受新旧版本和 revision 校验。`executed` 是人工记录，流程没有退回修改状态或平台执行器。

## Agent、MCP 与调度

通用 Agent 授权在接受后可能继续命令或文件写入，与 eMAG 本地方案批准不同。MCP 用 bearer token scope 提供证据和本地报告，不开放账号密码或通用 eMAG 写代理。仅启用 eMAG adapter；Amazon 工具和启动任务已下线，见[平台适配边界](platform-adapters.md)。

原调度器运行 Agent 提示词。eMAG 页面只生成命令、预览服务器 cron 和下载停用 JSON，Agent/操作系统调度器都不执行此草稿。

## 本地化

Agent 子界面有独立 i18next 和资源，主工作台仍主要为中文，没有全局语言开关。文档双语不代表整个产品已国际化。locale 标识、回退和验证见[英文审计](../maintenance-audit.md)。

实现位置与英文架构文档一致，包括 `src/server/app/core/config.py`、`src/server/app/core/layout.py`、`src/server/app/services/store_artifacts.py`、`src/server/app/services/emag_jobs.py`、`src/server/app/services/emag_operations.py`、`src/server/app/routers/mcp_server.py`、`src/client/src/lib/navRegistry.ts`。
