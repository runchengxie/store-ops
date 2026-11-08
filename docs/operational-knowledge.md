# Operational knowledge and checks

[简体中文](zh-CN/operational-knowledge.md)

Open **Insights** from the authenticated status menu. This administrator-only secondary page keeps the default status home compact. It provides local training search, snapshot-bound suggestions, XLSX preflight and promotion contribution estimates. It does not perform marketplace writes.

## Private knowledge index

The owner imports a generated JSON library using the server environment:

```bash
python -m app.emag_knowledge_cli import --library /private/path/library.json
python -m app.emag_knowledge_cli status
python -m app.emag_knowledge_cli search --query "variant"
```

The index is stored under `IVYEA_OPS_DATA_DIR/emag/knowledge.sqlite3`. Keep packs and databases private and outside the repository. Import validates bounds before activating a revision transactionally; malformed input preserves the previous revision. Old revisions remain available for citations. Imports are CLI-only; authenticated readers cannot choose filesystem paths or import files.

Search results include source identity, hash, revision, excerpt locator, historical-training trust and known conflicts. Machine transcripts remain labelled. Summary/key-point locators are generated-library locations; raw text line locators are not original PDF pages. Use source page/time locations where supplied. Search is literal substring matching, not semantic retrieval. Empty results do not establish that guidance does not exist. The read-scoped MCP tool `ivyea_emag_knowledge_search` exposes the same references without changing the shared knowledge search tool.

Training material is untrusted historical reference data. It cannot authorize actions, establish current tax/fee/compliance rules or prove store facts. Verify conflicting examples against current account evidence. No original documents or videos are uploaded by these operations.

## Store checks

Suggestions prioritize observed existing-stock blockers and name missing checks; they do not certify root causes. Results retain the store and current snapshot identity.

Upload an XLSX locally for bounded structural preflight. Supported layouts use machine field IDs, requirement declarations and human headers; ambiguous/unknown layouts require manual review. Formulas, guidance sheets and inconsistent families produce review findings. The server neither recalculates workbooks nor contacts the marketplace. Limits: 5 MiB upload, 64 MiB ZIP expansion, 500 ZIP entries, 1,000 product rows and 200 reported issues. A result is never an eMAG acceptance or compliance certification.

Promotion checks use a saved current-snapshot cost revision and VAT-exclusive offer price. Missing/stale costs or unspecified extra costs produce an incomplete result; explicit zero is allowed. Discount and voucher scenarios are separate unless sequential stacking is explicitly assumed. A commission reduction changes the commission rate relatively, not the sale price. Support payments remain a separate assumption. Existing gross-price commission calculation remains a scenario assumption. Results require human review and are not settled net profit or promotion eligibility.

The page supports English and Simplified Chinese; internal fields and API identifiers remain language-neutral. No automatic collector is added by this feature. Existing pause controls and schedules remain authoritative.
