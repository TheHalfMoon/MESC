# CW-002 Canonical Closeout Evidence

- **Task:** CW-002 — Local protected storage and key abstraction
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#467](https://github.com/TheHalfMoon/MESC/issues/467) — CW-002 activation: Founder ratification of ADR-0039
- **Governance increment:** PR [#468](https://github.com/TheHalfMoon/MESC/pull/468) — `docs/adr-0039-founder-ratification`
- **Implementation PR:** [#469](https://github.com/TheHalfMoon/MESC/pull/469) — `feat/cw-002-protected-storage`
- **Qualified PR head:** `9f9a02112a60cc281447db46c2ac876323af1dd4`
- **Base:** `ed0d003d647227ca103d260e1d6e5efa86ac4107`
- **Canonical merge SHA:** `19743d6b6b46f7729883e67f4cee26e72be2b323`
- **Canonical merge tree:** `bcf4685a8fe26b197607767691defd5ad4f47596`
- **Merge parents:** `ed0d003d647227ca103d260e1d6e5efa86ac4107` (previous canonical `main`), `9f9a02112a60cc281447db46c2ac876323af1dd4` (qualified head)
- **Contract:** [ADR-0039](../../docs/adr/0039-local-protected-storage-and-key-management.md) as amended by A1, with the controlling [Founder ratification record](adr-0039-founder-ratification.md)

This record documents closure evidence that already exists on canonical `main`; it creates no
clinical, PHI, training, publication, research-admission or runtime authority.

## 1. Governance state entering implementation

```text
CW-001                          CLOSED_CANONICAL
ADR-0039                        Accepted by Founder under R6, 2026-09-21, Amendment A1
CW-002                          activated under Issue #467
governance merge                ed0d003d647227ca103d260e1d6e5efa86ac4107
governance merge tree           fbe1fd431d624a86df5ef3f4501f2c84c0b68f3f
governance fresh-main           CI 35640057625 SUCCESS, CodeQL 35640057652 SUCCESS,
                                Optional Extras/Backends 35640057690 SUCCESS,
                                HF Publication Qualification 35640057735 SUCCESS
```

Implementation began only after that state was canonical, so the ADR amendment, the ledger
activation and the implementation all exist on canonical `main` in that order.

## 2. Pre-merge exact-head evidence

Exact head `9f9a02112a60cc281447db46c2ac876323af1dd4` on base `ed0d003d647227ca103d260e1d6e5efa86ac4107`:

- CI run `35643263934`: SUCCESS — `static (py3.11)`, `static (py3.12)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`;
- CodeQL run `35643264049`: SUCCESS (`analyze (python)` job `106477482879`);
- the required checks were present and passing on that exact head;
- unresolved review threads immediately before merge: 0; submitted reviews: 0.

### 2.1 Review lane, recorded honestly

```text
Alibaba Open Code Review   NOT INSTALLED in this environment (no binary found);
                           not used, and no tool-side review is claimed
Jev screening              NOT PERFORMED: submitting an implementation description to an
                           external model API is remote-model egress, which this program's
                           standing non-grants prohibit; the attempt was refused before any
                           content left the machine
host-agent review          PERFORMED on the complete diff, attributed to the host agent
reviewing GitHub bots      cubic (skipping), CodeRabbit (review skipped: manual review
                           required), qodo (trial ended) — none produced a finding
```

The host-agent review is attributed as host-agent work. It is not presented as independent
tooling, and it is not evidence of security correctness.

### 2.2 Review-driven repairs inside PR #469

| Found on head | Finding | Repair commit |
|---|---|---|
| `d68a94f4c90c3fcb7ffbae5081df50d75d34df1c` | `rotate_pending` would have silently migrated a tampered row bound to a `RETIRED` key version instead of refusing it, contrary to A1.6 | `4b3285d95ecaf06b40a65769dab6be9a7c8d6c4b` |
| `4b3285d95ecaf06b40a65769dab6be9a7c8d6c4b` (exact-head CI) | the root `pyproject.toml`/`uv.lock` change drifted the frozen MRL-0809 static prerequisite identity (`static prerequisite source drifted: pyproject.toml`) | `9f9a02112a60cc281447db46c2ac876323af1dd4` |

Both repairs added the tests that now protect the repaired property: a hostile retired-key
rotation test, and tests asserting that the frozen lock sources still match their recorded
MRL-0809 digests and that CI is the only place the Workspace AEAD dependency is supplied.

### 2.3 Negative and superseded evidence

```text
d68a94f4c90c3fcb7ffbae5081df50d75d34df1c   superseded before CI completed
4b3285d95ecaf06b40a65769dab6be9a7c8d6c4b   CI FAILED: shard 2 (py3.11), shard 2 (py3.12)
                                           and shard 3 (py3.12) failed on the MRL-0809
                                           prerequisite drift; this is a real failure and is
                                           recorded as such, not as a success
root lock drift                            the frozen bytes were restored and verified against
                                           specs/mesc-experiment-0/mrl-0809-static-prerequisites-v1.json
```

No MRL-0809 manifest, receipt, trust root, gate code or evidence was modified, and no MRL
Stage-4 authority was consumed, created or reinterpreted by this work.

## 3. Protected merge

PR #469 merged through the repository's protected merge path — ruleset `MedScale canonical
main protection v1`: pull request required, review-thread resolution required, required status
checks under a strict up-to-date policy, and `merge` as the allowed merge method. No bypass, no
force-push, no rebase, no history rewrite, no gate weakening.

```text
BASE  = ed0d003d647227ca103d260e1d6e5efa86ac4107
HEAD  = 9f9a02112a60cc281447db46c2ac876323af1dd4
MERGE = 19743d6b6b46f7729883e67f4cee26e72be2b323
TREE  = bcf4685a8fe26b197607767691defd5ad4f47596
```

## 4. Fresh-main qualification

Workflows triggered by the merge commit `19743d6b6b46f7729883e67f4cee26e72be2b323`:

- CI run `35648150131`: SUCCESS — `static (py3.11)`, `static (py3.12)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`;
- CodeQL run `35648150292`: SUCCESS;
- Optional Extras / Backends run `35648150159`: SUCCESS;
- Hugging Face Publication Qualification run `35648150146`: SUCCESS.

The `MESC P01-04B` qualification and `MESC P01-04B2D` qualification workflows are path-filtered
and did not trigger for this merge commit; they ran and succeeded on the superseded branch head
`4b3285d95ecaf06b40a65769dab6be9a7c8d6c4b` (runs `35640882919`, `35640882982`), which is
recorded as superseded-head evidence rather than as merge-commit qualification.

Local supporting evidence on the merged tree, never a substitute for the GitHub gates above:

```text
scripts/check_clinical_workspace_boundary.py     CW-002 workspace boundary PASS
CW-002 suites + docs link hygiene                126 passed
strict mypy                                      no issues in 497 source files
ruff check . / ruff format --check .             clean
neighbouring suites on the branch head           399 passed
```

## 5. What CW-002 delivered

```text
storage engine            standard-library sqlite3, WAL, synchronous=FULL on the write path,
                          foreign_keys=ON, secure_delete=ON, explicit busy timeout,
                          every pragma asserted at open
payload protection        AES-256-GCM envelopes; 96-bit random per-operation nonce stored in
                          the envelope; AAD binds workspace id, object id, object type,
                          immutable revision, key version and encryption-format version
key derivation            HKDF-SHA-256 in reviewed code, checked against RFC 5869 A.1/A.3
key lifecycle             ACTIVE -> ROTATING -> RETIRING -> RETIRED with persisted state,
                          at most one ACTIVE key, decrypt-only rotation, deterministic resume,
                          retired keys refused for both read and rotation paths
key provider              capability-declaring abstraction; unavailable protected storage
                          fails closed before any store file is created
dependency               cryptography==50.0.1 for the AEAD primitive only, installed by CI
                          outside the frozen Research Core lock
boundary guard            sqlite3 only in storage.py; cryptography only in aead.py; one store
                          path resolver; every sqlite3.connect sourced from it; fixed 96-bit
                          nonce constant; no reachable in-memory test provider
tests                     113 CW-002 tests across a benign suite, a hostile suite and the
                          extended boundary suite, with hostile and benign cases independent
```

## 6. Recorded limitations

These are part of the accepted state, not open defects:

```text
platform protected secret storage   no platform provider is implemented; the production path
                                    fails closed (A1.7)
whole-store rollback                AES-256-GCM does not defeat a valid historical rollback
                                    performed with a still-valid key; no rollback detector
                                    exists, and none is claimed (A1.5)
plaintext metadata                  SQLite structural data and the declared metadata remain
                                    visible in a copied store (A1.10)
secure_delete=ON                    defense in depth only, never proof of cryptographic
                                    erasure (A1.11)
migration classes                   store initialization is the only implemented migration
                                    class; the M1-M3 manifest/preflight/rollback machinery
                                    belongs to CW-018
exception-text assertion            none of the reviewed paths embeds payload or key bytes in
                                    an error message, and no workspace module can import
                                    `logging` under the guard allowlist, but there is no
                                    dedicated assertion yet that exception text excludes
                                    payload bytes; that assertion belongs to the independent
                                    security lane at CW-019
```

## 7. Result

```text
CW_002 = CLOSED_CANONICAL
CW_003 = ELIGIBLE_NOT_ACTIVATED (depends on CW-001 and CW-002; requires its own activation)
CW_004_THROUGH_CW_021 = BLOCKED_DEPENDENCY
```

CW-002 grants no PHI ingestion, real patient import, clinical production use, real EHR write,
autonomous clinical action, remote model egress, Workspace-data training or research
evaluation/admission, model promotion, external publication, paid compute, MRL contract
mutation or new MRL Stage-4 attempt.
