# 0059: Independent tools with repository-owned workflow contracts

Date: 2026-11-08

Keep supplier discovery and browser transport independently installed. store-ops owns store identity, evidence interpretation, local records and approval rules. The first stage is Agent-mediated documentation with a reference version inventory, not an application adapter or automatically registered skill.

Prefer this boundary over a submodule, which pins source but does not configure credentials or browser sessions, and over vendoring or rewriting tools, which adds maintenance and redistribution obligations before a concrete application consumer exists. No license file was found in the inspected supplier checkout; no source is copied. Revisit a small structured adapter when an actual application workflow requires it.

The cost is explicit local installation/configuration and per-task version recording. Observed versions do not prove authenticated compatibility. Private evidence and credentials remain under their existing authoritative contracts. Archive integrity does not establish coverage of later records or the outcome of marketplace actions. See the [operating guide](../external-tools.md) and [supplier research instructions](../supplier-research.md).
