# Supplier research through an external Agent tool

[简体中文](zh-CN/supplier-research.md)

Use the independently installed 1688 CLI to discover supplier candidates, then record their evidence for a human comparison. store-ops has no direct CLI invocation or automatic result importer in this stage. See [tool setup and ownership](external-tools.md) before a task.

1. Confirm the requested item, required specifications and whether the user wants search or comparison. When starting from an eMAG item, retain store, offer ID, SKU and PNK when available; missing identity remains unknown. Product-image resemblance does not establish an exact match.
2. Resolve the external installation and record its actual commit, declared skill version and runtime. Read its `SKILL.md` and the relevant `references/capabilities/` document before choosing `text_search`, `image_search`, `link_search` or `compare`. Use the referenced syntax; this guide does not duplicate version-sensitive command parameters.
3. Use the external tool's existing authorization. If it is missing, the CLI fails or returns `success: false`, report the unavailable capability and preserve a redacted error. Do not invent candidates, use web/browser search as an unapproved substitute, or retry uncertain operations blindly.
4. Retain the returned structured `data` and the external tool's required presentation. Keep your analysis separate from its output. Save evidence privately only after checking it for tokens and other credentials; do not publish raw responses into the repository.
5. Record each candidate's source URL and product ID, supplier identity, exact variant/SKU, price and currency, quantity tier/minimum order, observation time with timezone and the query/image/link reference. Keep absent fields unknown. Distinguish API observation time from a supplier-confirmed quote-validity period.
6. Record specification differences, shipping/tax/packaging exclusions, stock or availability limitations and any missing evidence. Do not compare prices across different quantities or specifications without stating the assumptions. A search result is neither a landed-cost calculation nor a binding supplier quote.
7. Associate a candidate with a store item only after the identifiers and specifications have been checked. Label the association as proposed until verified. In the existing procurement record, use the reference-cost state for unconfirmed quotations; mark supplier confirmation or actual procurement cost only when separate supporting evidence exists. This guide adds no new API or import schema.

Keep the task ID, tool revision, source evidence and interpretation together in the configured private evidence location. Document what was manually entered into store-ops and which record it belongs to. Recheck price, variant, quantity and availability before a procurement decision. This workflow does not place orders, make payments, edit marketplace listings or approve marketplace writes.
