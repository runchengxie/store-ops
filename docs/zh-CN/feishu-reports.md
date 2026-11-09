# 飞书经营日报与周报

[English](../feishu-reports.md)

从已保存的 eMAG 证据生成摘要，通过现有 Lark CLI 机器人发送。Hermes 无需运行。
报告不会触发平台采集、修改商品或自动执行建议的检查。

## 报告口径

日报对应前一个自然日；周报对应上一周的周一至周日。默认业务时区为
`Europe/Bucharest`，包含夏令时变化。每条消息显示包含首尾两天的业务日期及最近
数据更新时间。库存是采集时点的观测，不是历史日／周库存，也不代表销量。

订单和退货的**记录数**包含取消等状态。报告区分两种日期口径：

- **平台日历日期**（`date_basis: platform_calendar`）：对现有完整 RO 采集器返回的
  无时区日期，直接按筛选这些记录的同一套无时区日期标签分组。必须匹配官方来源
  URL、资源覆盖和已知采集窗口契约；所有记录的日期必须兼容且位于窗口内。
  分别检查窗口是否完整覆盖本期及上期。不分配 UTC 偏移，不宣称已换算成可靠的
  罗马尼亚时刻；调度与采集时间仍使用配置时区。
- **已核实时区的时刻**（`verified_timezone`）：来源日期及覆盖窗口均需带时区，
  可信生成端独立核实筛选契约后，才可明确写入布尔值
  `commercial_summary.window.timezone_verified: true`。缺少负面备注不等于验证通过，
  单改标记也不能验证数据。

同一标识去重。标识冲突、日期混用或缺失、来源契约不支持、覆盖不足时，相关指标仍
显示不可用，不按零处理。当前采集器通常使用第一种口径；窗口总数与本期数据分开。
订单状态是采集时观测到的状态，并按原下单日期分组；“已完成”不表示已结算利润，
也不表示当天完成的订单数。退货按申请插入日期计数，不按退款完成日期计数。
字段依据见 [eMAG 官方 API 契约](https://marketplace-api.emag.ro/api-doc) 中的
`OrderSave.date`、订单日期筛选、RMA 日期筛选及各自的状态代码。

库存缺失显示未知，不按零计算。超过 24 小时的数据标记过期。报告最多列三项检查，
涵盖采集新鲜度、零库存、库存未知及日期证据缺失；它们是复核提示，不是已确认的
根因。不计算销售额、利润或建议售价。发送的 JSON 不包含客户身份、来源自由文本、
凭据或原始快照。完整证据保留在本地。

面向客户端的正文集中展示本期结果、对比和优先检查，不反复展示采集窗口总数、
原始快照 ID 或“未计算某某指标”的固定说明。这些属于证据说明，不是运行报错。
结构化 `evidence` 和 `details_markdown` 保留窗口来源、快照标识及口径限制；
`--save` 在本地保存含这些依据的完整报告。机器人只发送精简 `markdown`。
数据过期、覆盖不足、库存未知等影响判断的问题，仍在客户端正文提示。

## 本地生成

在稳定安装的 `src/server` 目录，使用该安装的 Python 环境：

```bash
python -m app.emag_digest_cli --store-id example-ro --kind daily
python -m app.emag_digest_cli --store-id example-ro --kind weekly --locale zh-CN --save
```

`--save` 额外通过现有报告存储，把不可变报告保存到 `IVYEA_OPS_DATA_DIR` 下。
不加该参数时只读。没有快照会生成明确的数据不可用报告；损坏或不可读的证据会返回
固定错误，不会伪装成空店铺。默认英文，可用 `--locale zh-CN` 选择中文；生成与
发送端的 `--timezone` 和语言必须一致。

## 发送配置

把 [digest-delivery.example.json](../../configs/digest-delivery.example.json) 复制到
机主私有部署配置目录。根据本机已配置的根目录解析真实路径；示例路径只是占位符。
真实应用、收件人标识和 SSH 命令保留在私有配置中。

- `enabled`：明确启用开关，示例为 `false`。
- `store_id`、`app_id`、`recipient_open_id`：准确的来源店铺、现有 CLI 应用及机主在
  **该应用下的** Open ID。不同应用的 Open ID 不能混用。始终以机器人发送，不使用
  用户令牌。
- `cli_command`：以现有 CLI 或仅允许机器人的包装器绝对路径开头的参数数组。
  凭据仍由原 CLI 保存。发送前核对应用身份；身份就绪不等于具备实际发送权限。
- `source_commands.daily` / `.weekly`：以可执行程序绝对路径开头的固定可信参数
  数组，返回生成器 JSON。示例假定工作目录为 `src/server`。跨机时可复用现有
  batch-mode SSH，运行稳定安装中的固定生成命令，只返回有界报告 JSON，不返回
  原始快照。无需新监听端口或复制密钥；不能指向临时 worktree。
- `state_dir`：私有数据目录的绝对路径，与配置和凭据目录分开。SQLite 账本保存
  发送前消息、目标身份、区间和快照引用。
- `timeout_seconds`：每个命令的超时，大于零且不超过 120 秒。

定时服务必须使用已验证手动发送的本地身份、CLI 凭据及运行环境。使用 Python
绝对路径，并明确指定稳定的 `src/server` 工作目录。Windows 没有系统 IANA 时区库
时，生成器需要 `tzdata`，已加入仅限 Windows 的服务端依赖；Linux 继续使用系统
时区数据库。

先预览，不发送也不创建发送账本：

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --preview
```

检查实际报告后，在私有部署配置中设 `enabled: true`，明确发送首份日报／周报：

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily
python -m app.emag_digest_delivery --config /private/config/digest.json --kind weekly
```

不加 `--kind` 时只处理到期报告：当地时间每天 09:00 以后处理日报，每周一 09:10
以后处理周报。可通过独立的 systemd 用户 timer 每 15 分钟运行一次，只补最新一期
已到期日报、周报，不补发历史消息队列。09:00 前不会补上一份错过的日报。业务时区
独立于主机时区。

保留现有采集调度权。报告只读采集结果，不能在 supervisor 运行时同时启用旧的每日
采集任务。笔记本休眠、网络中断和主机注销仍可能延迟发送；需分别检查操作系统
timer／service 状态及来源快照时间。

## 回执与结果不确定

成功必须同时满足 CLI 退出码为 0、JSON `ok: true`、机器人身份及返回 `message_id`。
仅有 HTTP 200 或 CLI 退出码为 0 不够。发送 ID 同时作为 CLI 幂等键。发送前先提交
账本意图，使并发调用不会重复提交同一期。准备好的消息在账本中保持不变，后续
采集更新也不会替换它。

- `delivered`：回执包含已验证的消息 ID。
- `rejected`：收到结构化 CLI 错误，保留结果，不自动重试。
- `unknown`：超时、响应损坏、含糊的非零退出结果，或被中断的 `sending` 意图。
  **永不自动重试**，重启或服务器去重窗口到期后也一样。

读取来源或身份预检失败发生在提交前，可在后续 timer 运行时重试。已有的 unknown／
rejected 不阻塞后续报告周期。退出码 1 表示保留了未成功回执；退出码 2 表示固定的
配置／来源／预检错误。修改前检查私有账本和 CLI 环境。对照目标单聊、发送键及
消息内容核对 unknown 结果，不要删除账本行来强制重发。得到明确更正授权后，对
已确认发送成功的报告使用固定更正 ID 和明确类型：

```bash
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --correction-id calendar-metrics --preview
python -m app.emag_digest_delivery --config /private/config/digest.json --kind daily --correction-id calendar-metrics
```

新消息明确标为更正版，账本引用原发送记录，并保留原记录及原文。同一更正 ID
重复运行不会重发。原结果为 unknown 或 rejected 时拒绝更正发送；定时模式不能
启用更正。预览不写发送账本，也不证明原记录存在。停止新报告时只停报告 timer 或
设 `enabled: false`，保留账本及原采集任务。
