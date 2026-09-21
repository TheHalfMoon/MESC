# CW-003 Canonical Closeout Evidence

- **Task:** CW-003 — Provenance and audit spine
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#471](https://github.com/TheHalfMoon/MESC/issues/471) — CW-003 activation
- **Implementation PR:** [#472](https://github.com/TheHalfMoon/MESC/pull/472) — `feat/cw-003-provenance-audit`
- **Qualified PR head:** `2b3274f2edd53aa51654f4ac5c54f20181dbf830`
- **Base:** `6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56`
- **Canonical merge SHA:** `c47bab9aa3b0805b4939eba47ee1c3c296995155`
- **Canonical merge tree:** `7336adecf50e530859aaea4fe85fa61243603566`
- **Merge parents:** `6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56` (previous canonical `main`), `2b3274f2edd53aa51654f4ac5c54f20181dbf830` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md) sections 11 (identity and provenance) and 12 (audit), [data security and threat model](data_security.md), [migration/recovery contract](migration_recovery.md)

This record documents closure evidence that already exists on canonical `main`; it creates no
clinical, PHI, training, publication, research-admission or runtime authority.

## 1. Governance state entering implementation

```text
CW-001 and CW-002                CLOSED_CANONICAL
CW-002 closeout merge            6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56
CW-003                           activated under Issue #471 on 2026-09-22
gating contracts                 already Founder-ratified through the canonically effective
                                 CW-000 planning package; no new ADR was required by the
                                 ledger, and none was invented
```

## 2. Pre-merge exact-head evidence

Exact head `2b3274f2edd53aa51654f4ac5c54f20181dbf830` on base `6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56`:

- CI run `35661837211`: SUCCESS — `static (py3.11)`, `static (py3.12)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`;
- CodeQL run `35661837207`: SUCCESS (`analyze (python)` job `106538638454`);
- the required checks were present and passing on that exact head;
- unresolved review threads immediately before merge: 0.

### 2.1 Review lane, recorded honestly

```text
Alibaba Open Code Review   NOT INSTALLED in this environment; not used, and no tool-side
                           review is claimed
Jev screening              NOT PERFORMED: remote-model egress of repository content is
                           prohibited by this program's standing non-grants
host-agent review          PERFORMED on the complete diff, attributed to the host agent
reviewing GitHub bots      cubic (skipping), CodeRabbit (review skipped: manual review
                           required) — no finding produced
```

### 2.2 Review-driven repairs inside PR #472

| Found on head | Finding | Repair commit |
|---|---|---|
| `4d70b43` | audit events shared an object identity derived only from the event digest, so two different events could claim the same chain position and leave the trail unverifiable — a wedge rather than a silent accept | `2b3274f` |
| `4d70b43` | a stored event document whose `event_id` was not derived from its digest was rejected only during full-chain verification | `2b3274f` |
| `4d70b43` | the occurrence time accepted any printable ASCII string | `2b3274f` |

The repair also added adversarial coverage for well-formed and malformed ISO-8601 occurrence
times (11 hostile shapes, 4 benign shapes) and documented two accepted costs: every append
re-verifies the whole chain, and tail-truncation detection needs a head digest retained
outside the store.

### 2.3 Negative and superseded evidence

```text
4d70b43   superseded head; its in-flight CI was superseded by the repair push and is
          recorded as superseded, not as a success
```

No MRL-0809-frozen source (`pyproject.toml`, `uv.lock`, workflows, MRL modules, MRL evidence)
was touched by this increment, and the CW-002 test that binds both lock sources to their
recorded MRL-0809 digests still passes on the merged tree.

## 3. Protected merge

PR #472 merged through the repository's protected merge path — ruleset `MedScale canonical main
protection v1`: pull request required, review-thread resolution required, required status
checks under a strict up-to-date policy, `merge` as the allowed merge method. No bypass, no
force-push, no rebase, no history rewrite, no gate weakening.

```text
BASE  = 6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56
HEAD  = 2b3274f2edd53aa51654f4ac5c54f20181dbf830
MERGE = c47bab9aa3b0805b4939eba47ee1c3c296995155
TREE  = 7336adecf50e530859aaea4fe85fa61243603566
```

## 4. Fresh-main qualification

Workflows triggered by merge commit `c47bab9aa3b0805b4939eba47ee1c3c296995155`:

- CI run `35666094491`: SUCCESS;
- CodeQL run `35666094490`: SUCCESS;
- Optional Extras / Backends run `35666094472`: SUCCESS;
- Hugging Face Publication Qualification run `35666094473`: SUCCESS.

Local supporting evidence on the merged tree, never a substitute for the GitHub gates above:

```text
Clinical Workspace suites (CW-001 + CW-002 + CW-003)   171 passed
strict mypy                                            no issues in 499 source files
ruff check . / ruff format --check .                   clean
docs link hygiene                                      PASS
boundary guard                                         CW-002 workspace boundary PASS
```

## 5. What CW-003 delivered

```text
provenance spine   one immutable provenance object per object revision: producer identity
                   (human/import/model), explicit source references with kind, id, revision
                   and optional locator, review state, recorded content digest, provenance
                   format version and policy version
provenance rules   generated content must reference at least one source; the recorded digest
                   is re-verified against stored content rather than trusted; provenance
                   records carry no payload content and are encrypted by the CW-002 store
audit spine        one immutable object per event, digest-derived event identity, chain-
                   position object identity, predecessor-digest chaining from a genesis
                   digest, contiguity/link/identity/digest verification
append-only        replay of a stored event and a concurrent attempt to occupy an existing
                   chain position both collide with the stored object; the trail is never
                   left silently doubled
deletion           deleting content and recording that deletion is one store transaction, so
                   audit metadata (id, type, revision, content digest) survives while the
                   deleted content does not
no clock           the caller supplies a validated ISO-8601 occurrence time with an explicit
                   zone; the package imports no clock, no logging and no network capability
storage support    additive only: object_revisions(object_type) and delete_and_put_atomic;
                   encryption, AAD binding, key handling, pragmas and the single-store-path
                   rule are unchanged
boundary guard     one new mechanical rule: only storage.py may touch the private store
                   connection
tests              42 CW-003 tests (20 focused, 22 adversarial) plus the extended boundary
                   suite, with hostile and benign cases tested independently
```

## 6. Recorded limitations

```text
write-once storage        append-only is enforced by the API, by digest-derived identity,
                          chain position and chain verification; there is no database-level
                          write-once trigger
tail truncation           a removed tail event verifies internally unless a head digest is
                          retained outside the store; the module states this, and the anchored
                          verification path is tested
append cost               every append re-verifies the whole chain, so cost grows with trail
                          length; checkpointing belongs to CW-018
schema version            CW-003 adds no schema change: audit and provenance records are
                          ordinary encrypted objects, so no migration class was needed and
                          CW-018 still owns the M1-M3 machinery
concurrency               the store remains single-writer per workspace, as CW-002 documented
```

## 7. Result

```text
CW_003 = CLOSED_CANONICAL
CW_004 = ELIGIBLE_NOT_ACTIVATED (depends on CW-001 and CW-003; requires its own activation)
CW_005_THROUGH_CW_021 = BLOCKED_DEPENDENCY
Issue #464 = open, separate CW-001 follow-up work unit
MRL-0809 (#429/#450) = separately governed and untouched
```

CW-003 grants no PHI ingestion, real patient import, clinical production use, real EHR write,
autonomous clinical action, remote model egress, Workspace-data training or research
evaluation/admission, model promotion, external publication, paid compute, MRL contract
mutation or new MRL Stage-4 attempt.
