# Integration boundaries

The deterministic eMAG collectors and replay CLI operate without a chat model. The console, image translation and knowledge features use their configured providers or Agent services. Installing optional tools is a separate user action, not a prerequisite for reading imported evidence.

| Integration | Current role | Limitation |
|---|---|---|
| eMAG RO API | Selected read-only evidence through CLI | Requires platform access and IP allowlisting; no writer exposed |
| IvyeaAgent | Agent runtime and knowledge integration | External installed dependency; provider behavior depends on the selected runtime/configuration |
| External MCP clients | Read imported snapshots/receipts and save scoped local reports | Separate bearer token; no credential access or general REST proxy |
| Image provider | Image generation/translation | Requires configured provider and human review |
| Hermes, Codex, Claude and other external tools | Optional runner/session integrations | Tool installation and versions are not guaranteed by a catalog label |
| Retired platform integrations | Amazon/Lingxing/Sorftime/SellerSprite/SIF implementations and automatic registrations removed | Existing private external configuration and historical records are not deleted |

The optional Hermes installer points to `hermes-agent.nousresearch.com`. The previous description of an Anthropic Hermes gateway was incorrect. This audit did not install or test that external product.

Runtime integration paths and provider secrets are edited through system settings. Environment fallbacks are defined per integration. Read [configuration](configuration.md), [external Agents](external-agents.md) and [usage](usage.md) for the active contracts. GBrain is no longer the knowledge runtime.
