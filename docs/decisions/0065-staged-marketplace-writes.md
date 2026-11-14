# ADR-0065: Staged marketplace writes, not a general write API

Date: 2026-11-14. Status: proposed.

## Context

The fork reads eMAG RO data, records local proposals and executes at most a
single approved price change through a disabled-by-default API (ADR-0052).
A November 2026 review of the live store found the real constraint was not
tooling: 183 of 184 offers belonged to no campaign, 52 units were blocked while
holding stock, 136 offers had zero stock and 199 units were older than 181 days.
eMAG's own Black Friday (2026-11-06) produced no order spike because the store
had not enrolled anything.

The owner asked whether to add listing, stock, campaign and order writes, and
whether the project should become an agent plugin or runtime.

## Decision

Add marketplace writes only in three gated phases, each reusing the pattern the
price API already proved: proposal, digest-bound approval, one attempt, read-back
and read-only reconciliation; an uncertain result blocks that offer and is never
retried automatically.

1. Campaign participation and campaign price — highest store value, because
   campaign enrolment is the missing input rather than a discount percentage.
2. Stock updates for existing offers.
3. Listing content repair for offers rejected by documentation validation.

Order, delisting and bulk flows stay out of scope until the earlier phases prove
recovery behaviour. Do not build a general write API, a second scheduler or a
background auto-optimiser.

Expose the read surface to agents through the existing scoped MCP tools. Keep
write tools unregistered by default and require explicit per-run authorization;
a token scope is not an approval. Do not turn the project into an agent runtime:
it remains a self-hosted web application plus a local supervisor, and agents
consume it as tools.

## Consequences

Each phase needs its own endpoint verification, permissions, IP allowlisting and
receipt evidence before implementation; none of that is assumed here. The write
surface stays narrow and auditable. Campaign enrolment remains a seller-portal
operation until an eligible API is confirmed and documented in
[phase 1](../emag-write-phase1.md).

Agents can inspect, propose and explain; they cannot silently change the
marketplace. An error response may still mean the platform accepted a write, so
recovery is manual and evidence-bound rather than automatic.
