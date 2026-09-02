# Mission Completion Criteria

*Mission Zero is complete when every box below is objectively, mechanically
checkable as true — not when it feels done. Scope decisions (doing more than the
minimum) belong to the founder; finishing below the minimum is not completion.*

## Screening

- [x] All **16 uncertain-duplicate groups** resolved (`screen status` shows 0 unresolved;
  repository evidence: Session 002 / `6c678b4`, with 16 canonical rows in
  `data/litdb/screening/uncertain_resolutions.jsonl`).
- [ ] **Q2 (148 records) and Q6 (143 records) fully screened** — 0 pending in both;
  UNCERTAINs from the first pass resolved by a second pass (final UNCERTAIN count
  for these queries: 0).
- [ ] Minimum **300 total screening decisions** in the review log (duplicates
  resolution included), all attributed to the mission reviewer id.

## Evidence

- [x] ADR-0018 decided **before** the first real evidence object (hard gate).
- [ ] Minimum **25 Evidence Objects** extracted from mission-INCLUDEd records.
- [ ] **≥ 90% `source_verified`**; every unverified object has an MZ-issue
  explaining why (an honestly-unverified object with a documented cause counts as
  success; a worked-around check counts as mission failure).

## Verification & snapshots

- [ ] `medscale check` CLEAN at every session boundary — **zero** DIRTY commits in
  mission history.
- [ ] Minimum **3 milestone snapshots** captured, committed, and each re-verifying
  (`snapshot --verify`) at capture+1 session: post-duplicates, post-Q2/Q6,
  post-extraction.
- [ ] The final mission snapshot verifies on a **fresh clone** of the repository.

## Benchmark

- [ ] **One real benchmark** specified against a committed mission snapshot, gold
  annotated by the mission reviewer.
- [ ] `bench validate` passes; `gold-oracle` = 1.0, `empty` = 0.0.
- [ ] The run **reproduces**: two executions, byte-identical `results_id`.

## Documentation

- [ ] Every session has a journal entry; every incident an MZ-issue with class,
  reproduction, impact, and proposed fix.
- [ ] PRISMA stats exported and committed (`medscale stats > ...`) at mission end.
- [ ] **No manual repository edits** under `data/litdb` occurred at any point
  (auditable: every data change in git history corresponds to a logged session).

## Retrospective

- [ ] The [lessons-learned](lessons_learned.md) retrospective is written, with every
  recommendation citing mission evidence (MZ-issues, journal entries, or metric
  values) — and ends with the founder's implementation verdicts.

**Formal close:** a final `study(mission-zero): mission complete` commit containing
the exported stats, the final snapshot, and the retrospective.
