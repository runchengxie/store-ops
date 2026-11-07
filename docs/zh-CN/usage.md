# 使用、CLI 与证据契约

可选[单商品价格API](emag-write-readiness.md#单商品价格-api)仅限管理员、默认关闭，独立于本地工作台审批，没有前端提交按钮。准备和批准只在本地进行，执行要求精确摘要、明确确认和已配置的店铺绑定。

[英文权威版本](../usage.md)

## 日常流程

登录后默认打开 `/workbench`：左侧显示四项店铺证据指标和最多三条优先核查建议，右侧常驻 Agent 对话。“更多”保留详细工具与账户设置。对话默认只显示输入、发送和当前执行权限，其余控制在“选项”中展开。桌面以一屏显示为目标；窄屏通过“概况 / 建议 / 对话”切换，切换时保留对话。

“问助手”只把店铺、快照和商品引用带入输入框，由你点击发送才调用已配置的 Agent。切换概况中的店铺不会改变已有对话的所属店铺和快照。为新店铺开始对话需明确点击新建；有任务运行时须先等待或停止。历史仅记录此浏览器中各用户的店铺与会话引用，不是跨设备完整历史。

公开 Pages 演示使用同样的简化布局，回复明确标为预设演示，不调用真实模型。演示历史仅存在内存中，“更多”只显示已支持的演示详情页；刷新会重置所有演示对话。

项目网站提供交互式 eMAG 演示，使用工作台组件、虚构数据和内存模拟接口。刷新会重置演示修改。演示不能连接后端，也不提供真实平台操作；界面目前主要为中文。源码安装是独立的。

采集或显式导入 eMAG RO 快照，先核对来源时间、覆盖与限制，再查看经营页面。核实异常后记录本地方案，管理员可填写说明，以当前 snapshot 和 revision 批准。实际人工执行需单独记录，再采集新快照复查。

驾驶舱和调研页使用本店证据，商品分布不是市场需求或份额。Listing 是本地文案，不会提交上架。采购成本未补齐时不计算利润或推荐售价。

eMAG 驾驶舱提供当前快照的管理视角和专员视角。指标卡在数据可用时显示采集到的商品、订单、库存、单据和异常观测，缺失的数据标为未接入。异常数量仅覆盖已观察到的标记，价格状态、资料状态和库存未知数量单独显示；缺少未知数量时不会当作零。专员视角可进入巡检流程。页面保留数据来源、采集时间和订单筛选窗口；切换视角不会修改快照或执行平台操作。

待审批中的 eMAG 本地记录与通用 Agent 授权分开。同意 Agent 请求可能继续命令或文件写入，本地方案批准不会执行这些操作。

巡检页可按商品、异常类型、库存和本地处理状态筛选已观察到的异常。专员视角链接会打开指定店铺当前快照中的对应异常；店铺或异常不可用时会提示，不会静默切换到其他店铺。详情显示采集到的售价、库存、可用的平台说明和本地处理记录。未来平台写入的准备条件见 [eMAG 写入 API 的准备工作](emag-write-readiness.md)。

## CLI

### 可选的 Windows SSH 手动任务

在安装 PowerShell 7 的 Windows 上，如果 SSH 会话无法读取保存的凭据，可以让已登录的交互式用户会话按需运行现有 eMAG 只读任务。在源码目录下，以持有凭据的账号安装，然后以同一用户从 SSH 触发：

```powershell
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action install -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action run -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action status -StoreId example-ro
pwsh -NoProfile -File scripts/emag-ssh-task.ps1 -Action uninstall -StoreId example-ro
```

`example-ro` 是占位标签。安装仅创建按需运行的任务，不创建定时触发器，且不会覆盖已有任务。Windows 用户必须保持登录，源码目录及其服务器 venv 必须保持在安装时的位置，该账号还需要有 eMAG 凭据和 API 访问权限。运行默认最多等待 180 秒以获取新回执；超时不会取消正在运行的任务，重试前应查看状态。状态可能显示旧回执，应核对时间和运行 ID。卸载只移除受管任务，保留凭据和数据。该任务不会写入平台。本机测试成功不保证所有 Windows SSH 或任务配置都能读取凭据。

集成将最新控制回执和触发锁保存在 `%LOCALAPPDATA%/ivyeaops/emag-ssh-task/<store>/`，与应用配置的数据目录及其备份分开。任务使用自身用户会话的环境和服务器 `.env`，可能与 SSH 进程的环境和代理设置不同。请从永久保留的源码目录安装，不要从临时 worktree 安装。迁移源码目录时，请先从旧路径卸载，再从新路径重新安装。

请通过 `run` 入口触发受管任务。直接调用任务计划程序不会取得该入口的调用锁，若同时从外部触发，回执可能无法明确归属。`-Days` 在安装时固定；需要修改时请卸载后重新安装。

单件只读 SKU 核查可在 Windows 运行 `.venv/Scripts/python.exe -m app.emag_cli --sku example-sku`，Unix 使用 `.venv/bin/python`。命令按 `part_number` 查询并输出带采集时间的精简商品证据，不导入快照或修改平台数据。`found` 需要唯一精确匹配，`not_found` 表示没有返回结果；多条、不匹配、格式错误或请求失败为 `incomplete`。无结果不代表商品已下架。`--sku` 不能与 `--store-id` 同用；`--describe --sku example-sku` 不发送请求。匹配结果中的 `evidence_truncated` 标记文本或状态证据是否被截断。输出可能包含店铺私有数据。


在 `src/server` 使用安装的 venv：

```powershell
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --from-latest
.venv/Scripts/python.exe -m app.emag_job_cli --store-id example-ro --days 29
.venv/Scripts/python.exe -m app.emag_workflow_cli --store-id example-ro
```

Unix 改用 `.venv/bin/python`。`example-ro` 是占位标签，不会查找账号。`app.emag_cli` 采集商品，`app.emag_business_cli` 采集组合证据，`app.emag_job_cli` 增加比较、报告与回执。

job 退出码 0 表示报告/回执阶段完成，1 表示已记录的阶段失败，2 表示入口无效、存储问题或运行锁占用。检查回执，不把旧成功当作本次成功，强制中止可能没有新回执。

人工状态变更需 `--snapshot-id`、`--issue-id`、`--state`、`--revision`、`--note`。复查还需明确核对过的更新 `--review-snapshot-id`。状态顺序为 `pending` → `proposed` → `approved` → `executed` → `reviewed`，没有自动批准或退回修改状态。

`app.emag_cli --describe` 只说明采集范围，不读取凭证或调用 eMAG。`--prompt` 支持在终端隐藏输入凭证。组合业务采集和新采集任务使用 Windows 已保存凭证；离线 `--from-latest` 不需要凭证。

对支持的结构化审核错误，新采集在每个状态中最多保留 8 条精简 `error_details`：`code`、`section`、平台的 `en_GB` 说明和可选的 `extra_info`。每个文本字段最多 256 字符，URL 和邮箱地址会被替换。`error_details_truncated` 表示有条目被省略或缩短。完整提交商品资料和错误标识不会保留。平台说明仍可能包含其他敏感内容，因此快照仍需保密。旧快照保留原有占位说明，不会自动补全。

## Artifacts

快照和报告位于数据目录的 `store-artifacts`，每个产物上限 2 MB。报告绑定已有 `snapshot_id` 并包含来源证据。store/report ID 为 1–80 个 ASCII 字母、数字、下划线或连字符，首位为字母或数字。`captured_at` 必须有时区。

以下仅为最小合成导入示例，不是真实店铺证据：

```json
{
  "store_id": "example-ro",
  "platform": "emag",
  "marketplace": "RO",
  "captured_at": "2026-10-28T00:00:00Z",
  "source": "synthetic-example",
  "coverage": ["offers"],
  "limitations": ["Synthetic example, not verified store data"],
  "data": {"offers": []}
}
```

保存为本地文件，在已安装的后端环境执行 `python -m app.store_cli import-snapshot FILE`。`read-snapshot STORE_ID`、`read-report REPORT_ID` 读取已存产物。读取会返回导入版本的 `snapshot_id`，最新指最后导入，不保证采集时间最新。

回执位于 `store-artifacts/jobs/<store>/`，模式为 `fresh_collection` 或 `existing_snapshot`，记录 stage、status、来源/基线 ID、report ID 和时间。变化预览最多 200 项、64 KB，用 `change_count`、`changes_truncated` 标记总数和截断。省略内容仍由引用的完整快照提供证据。

人工巡检报告最多列出 100 条当前异常，包括 SKU、库存、精简平台证据，以及当前快照和最多 50 个先前导入快照中最早观测到该异常的时间。历史仅比较店铺、站点、来源和 coverage 相同的快照，并标记不完整扫描。该时间不代表异常开始时间。新采集使用兼容的前一快照作为基线；本次未观测到异常不代表问题已解决。报告最多列出 50 条本次未观测到的基线异常。离线重放没有变化基线。现有回执和快照格式保持不变。

库存缺失不是 0，数字 10 和字符串 `10.00` 视为相同。商品未出现不等于已下架。发票保留原始符号和币种，不证明付款、成本或利润；退货申请不证明已退款。

## API 与 MCP

管理员 REST 接口位于 `/api/emag`，包括店铺、board、workspace、draft、issue transition 和回执。网页未开放读取凭据或启动 job 的接口，浏览器写请求保留会话与 Origin 检查。

| MCP tool | scope | 行为 |
|---|---|---|
| `ivyea_store_snapshot` | `read` | 读取导入证据 |
| `ivyea_emag_job_status` | `read` | 读取最近记录的手动运行 |
| `ivyea_report_read` | `read` | 读取本地报告 |
| `ivyea_report_save` | `write` | 保存绑定来源的本地报告 |

`/api/mcp` 使用 bearer token，网页会话不能替代 token。这些工具不修改平台，Amazon keyword tool 已下线，仅提供已启用 adapter 的能力。

## 计划准备

`/schedules` 按服务器时区预览 cron，导出含 `enabled=false`、`registered=false`、`scheduler_connected=false` 的 JSON，没有调度器消费它。`/schedules?tab=agent` 是现有依赖模型的提示词调度器。草稿或手动回执不代表自动运行 eMAG。

## 货源与运营场景

分析工具提供本地货源记录。填写规范的 HTTPS 1688 商品链接、供应商规格并人工确认对应关系。系统不自动选择供应商，也未定时跟踪1688报价。

费用均按件输入，缺失时不计算单件贡献；确认无该项费用后再填 0。人民币兑列伊汇率由用户填写。eMAG原始sale_price为税前售价，直接作为扣费用前收入，不再重复扣VAT。填写的VAT率只用于构造含税价格，以计算用户输入的佣金比例假设；这不代表已核实平台真实佣金口径。结果不是会计利润，不自动判断采购 VAT 抵扣或企业税。参考报价和实际采购输入分别标识。

补货使用人工填写的日均需求、补货周期、安全天数、在途和预留库存，按需求覆盖天数减去可用库存后向上取整。结果是场景建议，采购前需核对退货取消、可售库存、起订量及包装数量。

价格和库存预览绑定当前快照，只展示修改前后值，不能执行平台更新。异常负责人跨快照保留；审批仍绑定原快照，不自动沿用。

## 确定性诊断交接

新快照携带 schema_version=1。旧文件缺少版本时按版本1读取，不重写历史文件。证据契约新增类型、店铺商品及快照身份、字段路径和依赖；旧文本默认属于推断。

管理员诊断接口返回有数量限制的规则诊断。本地提案保存诊断，审批时复核当前实体、快照、字段值和已注册的动作依赖。真实零库存保留为观察值，缺失或无效值为 null 并说明原因。当前未给估算及任意计算注册决策验证器。旧提案缺少结构化诊断时，需要针对新证据重新拟案。

巡检报告区分已验证的输出条目和全部异常，明确总数、验证数与截断状态。这保证内部证据一致性，不能证明平台原始数据一定准确。

市场调研页按商品归类已采集退货申请原因并去重，显示缺失原因、未匹配商品和异常格式的数量。申请不代表退款，也不代表全部客户满意度。Listing 草稿针对部分认证、功能和尺寸声明提示人工核实；未标记不等于合规，不检查图片。

## 货源修改历史

货源记录不再限制最多修改100次。每个版本独立归档到原有私有数据库，并与最新记录在同一事务中保存。旧版内嵌历史在下次成功修改时迁移；归档内容冲突会中止修改，不覆盖历史。新版本记录来源快照，旧版本保留原始字段，不补造来源。

最新记录仍只附带最近100条历史。管理员可通过 GET /api/emag/stores/{store_id}/commerce/{product_id}/history 分页读取更早版本，以 next_before 作为下一页的 before_revision，每页最多100条。沿用原有认证与备份机制。

## 现有库存消化

驾驶舱与打法页提供清库存视图，不执行采购、补货或平台修改。已知有库存且带价格、资料或封锁标记的商品排在前面，其次是已核对的180天以上库存，再是其他有库存商品；未知与零库存分别展示。组内按365天以上、181天以上数量及库存排序，不生成预测评分。

库龄参与排序前，七个分段必须完整、为非负整数，并与库存合计一致。未知和不一致的库龄会标记，不计入老库存小计。未观察到受阻标记不代表已确认可售。

库存复盘寻找扫描范围内最接近、且至少7天前的同口径快照，比较共同且库存已知的商品。新出现和未观察到的商品单独计数，不把消失当销量或零库存。实际间隔可能超过7天，库存减少也可能来自退货、调整或调拨。订单原始状态数量不等于已售或回款，不推算清完库存天数。

可跳转处理异常，或拟定绑定快照的本地清库存方案。具体降价和回款测算仍需人工核对历史成本与费用，不自动调价或下采购单。


价格口径修正：旧版场景曾把原始售价当成含税价，可能低估收入。保留原始输入和历史报告，当前场景按修正后的税前契约重算。官方将recommended_price定义为折扣前建议零售价，min_sale_price/max_sale_price为卖家自设边界，均不能当作已核实的恢复阈值。来源：https://marketplace-api.emag.ro/api-doc。

### 清仓复查

管理员接口 `GET /api/emag/stores/{store_id}/clearance-review?baseline_snapshot_id=...` 和 read 权限 MCP `ivyea_emag_clearance_review` 返回已导入快照的清仓队列及可选的明确历史基线比较。只看队列时省略基线。队列不是审批，库存下降或价格拒绝消失不代表已成交、前台可购买或已结算。来源和覆盖范围必须一致、采集时间必须前进，SKU/PNK 不一致的行排除比较。配合[价格验证 Skill](../../skills/emag/price-validation/SKILL.md)及另行授权的浏览器工具使用；未新增浏览器写入接口。
