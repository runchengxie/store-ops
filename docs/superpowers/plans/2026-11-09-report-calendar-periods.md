# Correct unavailable report periods

The owner reported that delivered daily/weekly reports expose unavailable period
figures despite saved dated records. Fix the existing reporting deliverable;
preserve physical-time uncertainty rather than fabricate a verified timezone.

## Diagnosis and approach

The current collector returns naive API calendar labels and records the exact
naive strings sent in createdAfter/createdBefore or date_start/date_end. The
report builder incorrectly requires timezone-aware instants for every kind of
period statistic. Keep that requirement for instant-based statistics, but add
explicitly labelled **platform calendar date** counts for compatible naive
records/windows from the known complete eMAG collector contract. This is not
conversion into Europe/Bucharest or a verified time-zone claim. Keep all guards
for incomplete coverage, missing/mixed dates and conflicting identities.

Official source: https://marketplace-api.emag.ro/api-doc (OpenAPI 4.5.2,
retrieved 2026-11-09): OrderSave.date is cart submission timestamp;
OrderReadFilter.createdAfter/createdBefore and RMAReadFilter.date_start/date_end
filter the relevant dates in YYYY-mm-dd HH:ii:ss format. Orders have statuses
0 canceled, 1 new, 2 in progress, 3 prepared, 4 finalized, 5 returned; RMA
request statuses are a separate code set. This source does not establish the
timezone, and the fix must not assert it does.

## Work and verification

- [ ] Add RED tests for naive calendar daily/weekly counts, source/coverage
  binding, mixed/missing dates, incomplete windows, DST date labels and distinct
  order/RMA status summaries. Preserve verified-instant tests.
- [ ] Implement calendar-date basis, period comparisons and localized report
  wording that distinguishes date labels from schedule/capture timezone.
- [ ] Add an explicit correction ID to manual delivery only. Require a confirmed
  delivered original, preserve the original ledger row and payload, and dedupe
  repeated correction invocations. Unknown originals cannot be resent through
  this path. Scheduled sends never use correction IDs.
- [ ] Verify against private saved evidence and bounded read-only API checks;
  retain network/access failures honestly. Do not migrate credentials, change
  security settings or republish source snapshots just to validate.
- [ ] Update bilingual docs/changelog and ADR, full tests/lint, independent
  review, owner-repository PR/current-target checks, then merge/deploy under
  standing authorization. Send clearly marked corrected reports to the same
  authorized owner-only conversation, read them back, verify timer/dedupe,
  and remove only this task's temporary verification task/branch/worktree.
