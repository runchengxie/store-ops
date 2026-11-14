# eMAG write phase 1: campaign participation

Status: proposed. This document defines the first write capability and the
evidence required before any code exists. It does not authorise a marketplace
change.

## Why this phase first

Campaign participation is the missing input, not a discount percentage. On
2026-11-14 the live snapshot showed 184 offers, 183 without `campaign_id`, and
only `ghostlight` inside "Chillmas Deals 2026". eMAG's own Black Friday on
2026-11-06 produced two orders for the store on that day, against a 30-day
average of about one order per day.

The same snapshot found 48 offers with stock (45 of them carrying 181+ day units)
and five offers blocked while holding 52 units. Phase 1 therefore targets
enrolling existing, approved offers into a campaign with an explicit campaign
price; it does not create products.

## Non-goals

- Stock, listing content, order and delisting writes.
- Bulk enrolment without an individual digest per offer.
- Any scheduled or automatic enrolment; a scheduler must not own this.
- Automatic retry or automatic recovery after an uncertain response.
- Treating an MCP scope, a local issue approval or an agent instruction as
  approval.

## Unknowns to verify before implementation

Each item must be answered with a recorded observation, not an assumption.

1. **Enumeration.** Is there an authenticated endpoint that lists campaign
   definitions (id, name, window, eligibility)? Is `campaign_id`/`campaign_name`
   on the offer read model the same identity space?
2. **Enrolment.** Is enrolment a dedicated endpoint, or a field on
   `POST /api-3/offer/save`? Which exact field carries the campaign id and which
   carries the campaign price?
3. **Eligibility.** Which conditions (category, stock, price bounds, account
   rights, FBE/seller fulfilment) decide whether an offer can join?
4. **Deadline semantics.** Can an offer join after the campaign starts? Can it
   leave? What happens to the price at the campaign end?
5. **Error semantics.** The existing documentation already warns that an error
   response can accompany a saved offer. Confirm whether this also applies to
   campaign fields and whether any idempotency key exists.
6. **Rights and network.** API rights, market binding, IP allowlisting and the
   exact credential target. No new credential location is introduced.
7. **Read-back.** Which field proves enrolment — `campaign_id` on the offer,
   an eligibility list, or a separate campaign membership resource?

If item 2 or 7 cannot be answered with a stable contract, stop: the phase
stays a manual seller-portal workflow and this document becomes the record of
why it was not automated.

## Proposed flow

The flow mirrors the approved single-offer price API (ADR-0052).

1. **Propose** — input: snapshot id, product id, campaign id, campaign price.
   Refuse stale snapshots, ambiguous ids, non-approved offers, prices outside
   observed seller bounds and offers already in the target campaign. Store the
   exact old/new values and a SHA-256 digest locally.
2. **Approve** — administrator supplies the digest and a note. Approval is
   per proposal and does not survive a changed digest.
3. **Preflight** — live read of the campaign (active, eligible), the offer
   (identity, price, stock) and the seller bounds. A snapshot or campaign change
   after approval stops the attempt.
4. **Execute** — one request, no redirects, no retry. Persist the attempt before
   sending. A timeout is `uncertain`, not failure.
5. **Read back** — confirm enrolment and price through the read model. A match
   proves the field, not restored saleability or future sales.
6. **Reconcile** — read-only follow-up. An `uncertain` result blocks that offer
   from further submissions until a human resolves it.

## Data and evidence

- A separate local ledger (for example `emag-api-changes.sqlite3`, as used by
  the price API) records proposal, approval, attempt, response hash and
  read-back.
- Receipts keep store id, product id, campaign id, old/new price, proposal
  digest and observation timestamps; they never keep credentials or raw platform
  bodies.
- Read-scoped MCP tools may expose proposals and receipts. Writing remains
  disabled by default and is never registered as an agent tool.

## Acceptance criteria

- A synthetic offer can move through propose, approve, preflight and a mocked
  execute with a durable receipt, without any network call.
- An ambiguous response blocks the offer and cannot be replayed.
- A snapshot or campaign change between approval and preflight refuses the
  execution.
- The store's campaign membership read-back matches the proposal after a
  verified manual change.
- No new dependency is required for the contract tests.

## Rollout

Disabled by default and store-bound, following the price API's environment
gates. First live use is one offer, one campaign, with read-back and a written
receipt. If any step is uncertain, stop and reconcile before the second offer.
