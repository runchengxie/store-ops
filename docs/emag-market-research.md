# eMAG market research and profitability

[简体中文](zh-CN/emag-market-research.md)

Use **Market research** (`/market`) to save product opportunities and observed competitor quotes. Use **Analysis tools** (`/tools`) for saved procurement costs and read-only price scenarios. A current eMAG RO snapshot and administrator session are required. No research record purchases stock, edits a marketplace offer or spends advertising money.

## Research records

Each observation retains the exact PNK, market, currency, price basis, source link, observation time, source type and research status. Official reports, third-party estimates and manual observations remain distinct labels supplied by the operator, not certifications by this application. An empty price is unknown; explicit zero remains zero. Use an ISO timestamp with timezone and optional paired reporting-period boundaries.

Choose **Opportunity** for a candidate product, or **Competitor quote** for a seller observation. Quotes require a seller and a comparison key describing comparable specifications, quantity and delivery conditions. PNK matching uses the exact current own-catalog field; multiple own offers are marked ambiguous. An absent match does not prove the product is absent from the marketplace.

Saving creates an immutable revision with the authenticated actor. Editing requires the latest revision; a changed snapshot requires reload. Older-snapshot records remain visible with a warning. The screen shows the latest 2000 revisions and warns when history is partial; the database retains all revisions.

Price changes compare two latest distinct observation times for the same PNK, market, currency, tax basis, seller and comparison key. Unknown tax basis is not comparable. These are historical sample changes, not a continuous price feed. Minimum price does not guarantee Buy Button ownership. No automatic currency or VAT conversion is performed.

## CSV import

Upload UTF-8 CSV with 1–500 rows (maximum 1 MB). Fields use stable machine keys. Validation is atomic: one invalid row rejects the whole import. Import creates new observation records; it does not overwrite earlier research. Reimporting the same file creates additional records, so check the ledger first.

Required columns: `kind,pnk,name,market,currency,price_basis,source_url,source_type,observed_at`.

Optional columns: `price,seller,comparison_key,buy_button,period_start,period_end,performance_label,status,note`.

Values:

- `kind`: `opportunity` / `quote`.
- `market`: `RO` / `BG` / `HU`; currency: `RON` / `EUR` / `HUF`. Currency is explicit evidence metadata, not inferred from the country.
- `price_basis`: `inclusive_vat` / `exclusive_vat` / `unknown`.
- `source_type`: `official` / `estimated` / `manual`.
- `buy_button`: `yes` / `no` / `unknown` (default).
- `status`: `research` (default) / `costing` / `hold` / `approved`. Approval is a research status, not execution authorization.

```csv
kind,pnk,name,market,currency,price_basis,price,source_url,source_type,observed_at,status,note
opportunity,EXAMPLE123,Illustrative product,RO,RON,inclusive_vat,,https://www.emag.ro/,manual,2026-11-07T00:00:00Z,research,Synthetic example; replace with observed evidence
```

## Profitability

The existing raw `sale_price` is exclusive of VAT. Contribution subtracts per-unit procurement, transport, duties, fulfilment, other costs, return allowance and the user-entered commission assumption. Commission is calculated on the VAT-inclusive price **as an explicit scenario assumption**, not as a verified current fee rule. Advertising/storage not otherwise represented must be included in explicit costs. Actual procurement inputs still yield an estimate, not accounting net profit.

Contribution margin = contribution / revenue excluding VAT. Zero revenue has no margin. Break-even and target-margin prices solve the same model in reverse and round upward to the next cent. An infeasible denominator yields no price. Missing costs stay unknown. Target margin uses revenue excluding VAT as its denominator.

The price-scenario action uses the selected product, current snapshot and saved costs; it neither saves changed costs nor submits a platform price. Review old cost records against the current snapshot before relying on the result. Procurement revisions are retained by the existing commerce ledger.

## Data integrations and next steps

Checked 2026-11-08:

- [Top eMAG](https://marketplace.emag.ro/infocenter/emag-academy/emag-marketplace-analytics/top-emag/?lang=en) documents RO top-50 rankings updated daily. Its average displayed price is not actual checkout price. This project has not verified a public API for the entire ranking.
- [My Opportunities](https://marketplace.emag.ro/infocenter/emag-academy/my-opportunities/my-opportunities-existing-products-section/?lang=en) describes recent product opportunity labels; full content requires a seller account. Access in the seller UI does not establish a third-party API contract.
- [MASAT MCP](https://masat.ro/tools/masat-claude/) documents a read-only X Scan connector at `https://app.masat.ro/api/mcp`, Professional subscription and account authorization. Seller Dashboard/Expenses through that connector are described as coming later. No connector, subscription or seller authorization was configured by this change.
- [Datomy](https://datomy.eu/) remains a candidate; this inspection did not obtain a readable public API contract. Do not treat its webpage as an integration contract.

Start with authorized exports and manual evidence. Confirm fields, estimation method, coverage, data-use rights, authentication and quotas before enabling automatic collection. Keep credentials in private configuration and do not paste them into observations or CSV. Fees, VAT, warehouse addresses and advertising rules require current account-specific confirmation; historical course materials are references.

Missing or old saved costs on a matched own product create a cost-verification prompt. Own-price gap prompts require a current exact single match, RO/RON and an explicitly tax-exclusive quote; delivery/specifications still need human confirmation. Historical price and Buy Button changes create review prompts, never execution instructions. Observations at equivalent UTC times are grouped; conflicting price/button values are flagged rather than arbitrarily selected. A zero-cost target-price scenario uses a minimum positive price of 0.01 RON so its margin has a defined denominator.

## Pinterest trend leads

Choose **Pinterest trend** in Market research. Record the keyword, exact source region or country group, observation time and a Pinterest Trends HTTPS link. PNK is optional and can be added by editing the record after identifying a candidate. Revisions retain earlier observations. The market field identifies the target marketplace, while source region identifies the Pinterest audience. Verify candidates against eMAG RO offers and saved costs. This workflow uses manual observations.
