# 0057: A shared core with one eMAG adapter

Date: 2026-11-08

Expose a minimal source-labelled store overview through an explicit adapter registry, currently containing only eMAG RO. Keep specialized eMAG workflows and raw evidence rather than invent a universal ERP schema. Common orchestration retains authentication, capability fail-closed behavior, approvals, revisions and audit; platform code owns endpoint/credential/field interpretation.

Delete executable Amazon product features and startup/provider provisioning, not merely hide them behind legacy flags. Preserve historical/private data and external user configuration; reject known retired task references before dispatch. Retain useful shared image/reporting helpers after consumer checks. Separate external Agent releases remain outside this repository's source deletion boundary.

This makes future platform work additive but deliberately provides no speculative marketplace writer. Existing eMAG interfaces and stored identifiers remain compatible during extraction. The cost is that eMAG-specific extensions are still explicit rather than flattened into shared models.
