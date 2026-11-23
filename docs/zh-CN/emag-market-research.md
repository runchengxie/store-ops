# eMAG 市场调研与盈利情景

[English](../emag-market-research.md)

在“市场调研”（`/market`）保存商品机会和竞争报价观察；在“分析工具”（`/tools`）维护采购成本并计算售价情景。需要当前 eMAG RO 快照及管理员登录。保存调研记录不会采购、修改平台报价或投放广告。

## 调研记录

每条观察保留精确 PNK、市场、币种、价格税费口径、来源链接、观察时间、来源类型及调研状态。“官方报表”“第三方估算”“人工观察”由录入者标注，不代表系统认证。价格留空表示未知，明确填写 0 才是零。时间须为含时区的 ISO 格式；统计周期的起止时间需同时填写。

候选商品选择“商品机会”；卖家报价选择“竞争报价”，并填写卖家以及可比规格、数量和配送条件标识。系统按当前本店目录的精确 PNK 匹配；对应多个商品时提示歧义。没有匹配到本店商品，不代表平台没有该商品。

保存会新增不可变修订并记录登录操作者。编辑必须基于最新修订；快照更新后需重新读取。旧快照记录保留并提示核对。界面显示最新 2000 个修订，超出会提示历史不完整；数据库仍保留全部修订。

价格变化仅比较同 PNK、市场、币种、税费口径、卖家和可比条件下，最近两个不同观察时间的记录。未知税费口径不参与比较。这是历史样本变化，不是连续行情；最低价不保证获得购买按钮。系统不会自动换汇或换算 VAT。

## CSV 导入

支持 UTF-8 CSV，每次 1–500 行，最大 1 MB。字段使用固定标识；任意一行有误则全部不导入。导入创建新观察，不覆盖既有记录。重复导入同一文件会新增记录，操作前请检查历史。

必需列：`kind,pnk,name,market,currency,price_basis,source_url,source_type,observed_at`。

可选列：`price,seller,comparison_key,buy_button,period_start,period_end,performance_label,status,note`。

允许值：

- `kind`：`opportunity`（机会）或 `quote`（报价）。
- `market`：`RO/BG/HU`；币种：`RON/EUR/HUF`。币种为明确记录的元数据，不按国家推断。
- `price_basis`：`inclusive_vat`（含税）、`exclusive_vat`（税前）、`unknown`（未知）。
- `source_type`：`official/estimated/manual`。
- `buy_button`：`yes/no/unknown`，默认未知。
- `status`：`research/costing/hold/approved`，默认待研究。“通过”仅表示调研状态，不授予执行权限。

```csv
kind,pnk,name,market,currency,price_basis,price,source_url,source_type,observed_at,status,note
opportunity,EXAMPLE123,Illustrative product,RO,RON,inclusive_vat,,https://www.emag.ro/,manual,2026-11-07T00:00:00Z,research,Synthetic example; replace with observed evidence
```

## 盈利测算

原始 `sale_price` 是税前售价。贡献利润扣除按件采购、运输、税费、履约、其他成本、退货预留和用户填写的佣金假设。佣金按含税售价计算仅是明确的情景假设，并非已核实的现行平台规则。尚未列出的广告和仓储等费用需计入明确成本。即使填写实际采购成本，结果仍是估算，不是会计净利润。

贡献利润率的分母是税前收入；收入为零时利润率未知。保本价和目标利润率售价反向求解同一模型，并向上取整到分。目标无法达到时不返回价格；成本缺失保持未知。目标利润率同样以税前收入为分母。

情景计算使用选中商品、当前快照和已保存成本，不保存修改后的成本，也不提交平台售价。使用旧成本前需按当前快照复核；采购修订由既有成本记录保留。

## 接入条件与下一步

核查日期：2026-11-08。

- [Top eMAG](https://marketplace.emag.ro/infocenter/emag-academy/emag-marketplace-analytics/top-emag/?lang=en)：官方说明为 RO 每日更新的前 50 名；平均展示价不是实际结账价。本项目尚未核实全榜单的公开 API。
- [My Opportunities](https://marketplace.emag.ro/infocenter/emag-academy/my-opportunities/my-opportunities-existing-products-section/?lang=en)：介绍近期机会标签，完整内容需要卖家账户；后台可访问不等于第三方具有 API 契约。
- [MASAT MCP](https://masat.ro/tools/masat-claude/)：公开只读 X Scan 接口 `https://app.masat.ro/api/mcp`，需要 Professional 订阅与账户授权；该连接器的 Seller Dashboard、Expenses 仍标为后续能力。本次未配置连接器、订阅或卖家授权。
- [Datomy](https://datomy.eu/)：仍作为候选，本次未取得可读的公开 API 契约，不能把网页介绍当接入契约。

先使用有权取得的导出及人工证据。自动采集前需确认字段、估算方法、覆盖、数据使用权限、认证和限流。凭证存放在私有配置中，不要放入观察或 CSV。费用、VAT、仓库地址和广告规则需按当前账号确认，历史教程仅作参考。

匹配到本店商品但已保存成本缺失或过期时，系统生成成本核查提示。本店价差提示仅适用于当前快照的唯一精确匹配、RO/RON 且明确税前的竞争报价，规格和配送仍需人工确认。历史价格与购买按钮观察变化会生成复核提示，不会变成执行指令。同一 UTC 时刻的观察会合并判断；价格或按钮状态冲突时提示核查，不任意选取。零成本的目标售价情景使用最低 0.01 RON，避免收入为零导致利润率无定义。

## Pinterest 趋势线索

在市场调研选择 **Pinterest 趋势**，保存关键词、完整来源地区或国家组、观察时间和 Pinterest Trends HTTPS 链接。PNK 可留空，找到候选商品后通过编辑补充。历史版本保留早期观察。市场字段表示目标市场，来源地区表示 Pinterest 受众。候选商品需结合 eMAG RO 报价和已保存成本核验。此流程使用人工观察。
