# store-ops 工作台

[英文权威版本](../../README.md)

[飞书经营日报与周报](feishu-reports.md)

[项目网站与文档](https://runchengxie.github.io/store-ops/zh-CN/)

[eMAG 交互演示](https://runchengxie.github.io/store-ops/demo/) · 使用虚构数据，刷新后重置。

本项目是 [Hector-xue/IvyeaOps](https://github.com/Hector-xue/IvyeaOps) 的自托管 fork，聚焦 eMAG RO 的证据巡检、经营摘要与本地草稿，采用通用运营底座与唯一 eMAG adapter，Amazon 执行入口已下线。

[带来源的运营检查与记录](emag-playbooks.md)覆盖审核修复、Listing、变体、竞品观察、广告复盘、入仓装箱和成本依据，全部保留为本地工作流。

[费用与结算对账](fee-payout-reconciliation.md)：人工证据导入、来源可追溯，不付款或自动采集财务资料。

## 当前能力与范围

- 只读采集商品及选定的自发货/FBE 订单、退货、发票和 VAT 数据。
- 保存版本化快照、人工巡检报告、有界变化预览和运行回执。
- 管理员可查看店铺证据，保存调研、方案与本地 Listing 草稿。
- 本地方案批准绑定当前快照和 revision，不执行平台改动。
- 独立管理员[价格API](emag-write-readiness.md)支持具体单商品改价的批准、提交和回读，默认关闭。
- MCP 可读取快照、回执和报告，保存本地报告需要 write scope。
- 计划准备页提供服务器时区预览和停用草稿下载，当前没有调度器执行这些 eMAG 草稿。

采购成本需要卖家输入，场景估算不等于会计利润或推荐售价。全市场搜索量和竞品销量尚未提供。现有工作台仍只记录本地数据，可选改价使用上述独立API，不开放商品资料、库存或订单写入。对话和图片翻译需要配置相应模型服务，确定性巡检 CLI 不依赖打开的 console 或模型。

## 从源码运行

源码位于 `src/client` 和 `src/server`。安装脚本接受 Python 3.11+ 和 Node.js 20+，CI 构建使用 Node.js 22。本次本机验证环境为 Windows、Python 3.12.13、Node.js 24.22.1、已安装的 `ivyea-agent` 1.16.9。CI 中配置的平台矩阵不等于本机已验证所有环境。

```powershell
powershell -NoProfile -File scripts/manage.ps1 -Action install
powershell -NoProfile -File scripts/manage.ps1 -Action start
```

Linux/macOS 使用 `bash scripts/manage.sh install` 和 `bash scripts/manage.sh start`。安装器可能安装依赖或可选组件，只有准备执行这些操作时才运行。Windows 的 `-DryRun`、Unix 的 `--dry-run` 只解析入口。标准应用仍启用会话认证，私有本地开发适配器不属于发布的登录流程。

不假设本 fork 已发布包含这些改动的安装包。上游发行包不包含本 fork 的 eMAG 改动。冻结 Windows/macOS 包仍使用包内 `client/`、`server/`。升级前请阅读[安装与迁移](installation.md)。

## 手动巡检

进入 `src/server`，使用其 Python 环境：

```powershell
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --from-latest
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --days 29
```

`example-ro` 需替换为自己的已导入店铺标签。离线重放需要已有快照，不代表新采集。联网入口读取 Windows Generic Credential `IvyeaOps/eMAG/RO`，仍需要平台 API 权限和 IP 白名单。

## 文档

英文为 canonical，中文同步相同事实和标识。优先文档包括 [eMAG 能力边界与迁移](emag-capability-map.md)、[架构](architecture.md)、[安装](installation.md)、[配置](configuration.md)、[使用](usage.md)、[运维](operations.md)。另见英文[审计记录](../maintenance-audit.md)、[贡献说明](../contributing.md)、[安全策略](../security.md)和[changelog](../changelog.md)。历史决策与内部计划不全部双语。

许可为 [AGPL-3.0](../license)，保留上游归属和许可义务。

- [市场调研与盈利情景](emag-market-research.md)

- [店铺状态首页](store-status-home.md)
