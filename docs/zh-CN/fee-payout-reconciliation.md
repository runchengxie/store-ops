# 本地费用与结算对账

[English](../fee-payout-reconciliation.md)

首版支持有来源的人工 JSON 证据导入，展示费用单据、结算观测和明确的抵扣关联。预计结算、已处理结算与银行到账分别保留；不付款、不自动记账，不接入银行，也不部署 ERPNext。

## 使用

在稳定安装的服务端目录，使用其 Python 环境：

```bash
python -m app.emag_reconciliation_cli --store-id example-ro import --file /private/data/manual-evidence.json
python -m app.emag_reconciliation_cli --store-id example-ro report --locale zh-CN
python -m app.emag_reconciliation_cli --store-id example-ro history
python -m app.emag_digest_cli --store-id example-ro --kind weekly --locale zh-CN --save
```

原始证据保存在私有数据根目录，以稳定标识填入 `source_ref`。运行数据位于 `IVYEA_OPS_DATA_DIR/store-artifacts/reconciliation/evidence.sqlite3`。读取不存在的证据库不会创建空库。日报/周报 CLI 显式读取可选财务证据；纯报告构造函数保持原样。无财务证据时不增加财务部分；资料损坏时保留经营指标并显示财务资料暂不可用。摘要限制展示范围和批次数，并以 `truncated` 标识截断；完整独立报告与历史记录保留来源引用。

实际 eMAG 导出格式尚未验收，当前只接受明确标为 `manual` 的 JSON 转录，不可声称已经自动同步。导入仅保存所提供的事实，不验证其真实性。

## 数据契约

完整字段与合成示例见[英文契约](../fee-payout-reconciliation.md#manual-json-contract)，机器字段不翻译：

- 一个批次只有一个店铺、法律主体 `company`、交易方 `counterparty`、市场和币种，不跨范围相加或核销。
- `schema_version` 为整数 1；`source_kind` 为 `manual`；`review_status` 为 `reviewed` 或 `unreviewed`；`coverage` 为 `partial` 或 `complete`。出现部分覆盖或未复核批次，整个范围仍按部分资料展示。标记完整不等于已审计。
- 每条记录有 `kind`、`id`、`revision`。修订需要新版本及指向当前前版的 `supersedes`；重导入旧版本不会回退最新记录。同一版本不可修改，仅新增批次/来源不能把旧记录变成已复核。
- `document` 包含单据类型、带符号金额及含税口径。可单独记录单据日期、服务期间、到期日、发生时间、观测时间。缺失发生时间不推断。可选明细保留行 ID，合计必须等于单据；红冲须明确关联原单据版本并使用相反符号。
- `payout` 包含日期、预计/已处理状态、带符号构成与净额，构成合计须等于净额。预计转已处理使用不同 ID 并通过 `estimate_id` 明确关联，保留预计观测；不允许在同一 ID 下把预计版本重分类为已处理；不能仅凭日期/金额猜测。已处理仍不证明银行到账。
- `allocation` 明确引用单据类型/ID/版本及结算 ID/版本，支持部分和多对多关联；可选 `document_line_id` 指向存在的费用明细，同时校验行容量与单据总额。确认关联、引用的单据版本与结算版本均须有已复核来源，并使用可比较的含税金额；引用版本须在同一范围的历史中真实存在，不能把编造的版本当作过期资料；未确认建议不改变合计。源单据或结算版本改变后，旧关联标为待复核。

金额必须是精确十进制字符串，不接收浮点数、非有限值、科学计数法或超过两位小数；上限为 12 位整数。日期使用 `YYYY-MM-DD`，时间戳必须带时区。拒绝未知字段和重复 JSON 键。每批最多 1 MB、500 条记录；每范围最多 2,000 条当前记录；每单据最多 200 行、每结算最多 30 项构成。ID 是有长度限制的机器标识，不是任意说明文字。

确认关联不得超过单据金额；正费用关联也不得超过该批次负构成的容量，贷方须保留负号且不超过正构成容量。这只是合理性校验，不证明具体费用已被扣除；仍需来源明确的关联证据。

## 解释

英文示例中，结算净额仍为 50.00 RON，单据未关联金额为 60.00 RON，不再从净额扣一遍费用。`unallocated_amount` 表示当前已复核证据尚未关联的金额，并不等于到期应付金额。关联预计批次不证明已完成结算。未分配贷方不能自动抵扣费用；首版 `outstanding_to_pay` 保持未知。

更正使用关联的新版本，不能直接改数据库或删历史强凑余额。汇总可追到单据、结算、批次哈希与待核对事项；异常不是付款指令。
