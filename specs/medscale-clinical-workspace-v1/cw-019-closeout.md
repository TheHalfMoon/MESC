# CW-019 Canonical Closeout Evidence

- **Task:** CW-019 -- Security and privacy closure
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main)
- **Parent issue:** [#523](https://github.com/TheHalfMoon/MESC/issues/523) -- CW-019 activation
- **Implementation PR:** [#524](https://github.com/TheHalfMoon/MESC/pull/524) -- `codex/feat/cw-019-security-closure`
- **Qualified head:** `f706155f627b8c8a618ec5cfdb2106c58a173c50` (tree `6f8256462d846378deb019054af83500fcff881d`)
- **Implementation merge:** `ef1d6f7272eeb961af6ed65b537da99291f554fd` (tree `6f8256462d846378deb019054af83500fcff881d`)
- **Review record:** [cw-019-security-review.md](cw-019-security-review.md) (findings register, residual risks, lane results, threat-model reconciliation)
- **Contracts:** [data security and threat model](data_security.md), [migration and recovery](migration_recovery.md), [ADR-0039 ratification with Amendment A1](adr-0039-founder-ratification.md), [recovery runbook](recovery_runbook.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`. It creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, telemetry, or autonomous-action authority. CW-019 attacked the synthetic/local implementation and fixed what the attacks found. It does **not** make the workspace production-ready or PHI-ready. It does **not** protect against every attacker who can write the store file: whole-store rollback to an older valid sealed copy remains undetected (R1, section 7). **No human independent security review has been performed** (R7).

## 1. Governance state entering implementation

```text
CW-001 through CW-018 CLOSED_CANONICAL
CW-018 closeout merge                a93de06713b723931df8a63e391eef26137a7327
CW-019                               activated under Issue 523 (created 2026-09-29T22:37:47Z) as the single active
                                     unit under R4 (Founder standing activation authority for ordinary units
                                     through CW-020)
gating contracts                     no new ADR: ADR-0039 as ratified with Amendment A1 already prescribes the
                                     forward-only M1 migration class, the A1.6 retired-key invariant, A1.5
                                     (whole-store rollback) and A1.10 (plaintext metadata) exercised here
model contract                       NONE -- no model selected, admitted, or ratified
authorization                        synthetic fixtures only; no network, no model, no paid compute, no PHI,
                                     no production use, no real-data migration, no paid or external reviewer
new dependencies                     none; no boundary-guard widening
Issues 429, 450, 464                separately governed and untouched
```

Carried-forward limitations that Issue #523 required CW-019 to attack rather than assume: the CW-018 plaintext journal state, store role and tombstone reasons; the CW-002 plaintext key-version table and salts (the A1.6 invariant); and the CW-002 deferral of an exception-text leakage assertion.

## 2. Implementation history (preserved as it happened)

### 2.1 Commits on the qualified head

```text
99800001  feat: implement CW-019 security closure with a keyed store integrity seal
6e94e43f  fix: verify the CW-019 seal before every write and gate legacy sealing
1e1e5c89  fix: verify the CW-019 seal before taking a store snapshot
f706155f  refactor: bind the CW-019 seal metadata query parameter
```

`ef1d6f72` is the merge of `f706155f` into `a93de067`. PR #524 was opened at 2026-09-29T23:15:44Z, after `f706155f` was committed (23:15:07Z), so no head was superseded after CI started. PR #524 changed 15 files (+1631/-127): `storage.py`, `lifecycle.py`, `keyderive.py`, `keyprovider.py`, `versions.py`, `errors.py`, `apps/workspace/README.md`, `recovery_runbook.md`, `cw-019-security-review.md` (new), the new `tests/test_clinical_workspace_security_closure_v1.py`, and five existing Clinical Workspace test files.

### 2.2 What the attacks found on canonical main

The attacker is anyone who can write the store file (another local process, or a copied-then-returned file) but does not hold the root secret. A raw-tampering probe against canonical `main` `a93de067` recorded, verbatim:

```text
A_retired_key_resumes_writes:        EXPLOITABLE: active=1 rows_on_key1=(1, 2)
B_role_flip:                         EXPLOITABLE: quarantine store opened and written as LIVE
C_journal_state_flip:                EXPLOITABLE: normal open of unfinished migration; journal=['COMPLETED']
D_tombstone_row_removed_accepted:    EXPLOITABLE: tombstone silently removed; state accepted
E_audit_tail_truncation:             EXPLOITABLE: truncated chain verifies internally: events=2
F_silent_row_deletion:               EXPLOITABLE: silent row deletion accepted; count=1
```

So before CW-019 a malicious store-file writer could:
- reactivate a retired key, so that new writes used it again (breaking the ADR-0039 A1.6 invariant);
- flip the store role, so that a quarantine store opened and was written as LIVE;
- complete a half-migration, by flipping the journal state to COMPLETED so the store opened normally;
- delete tombstones;
- truncate the audit tail, with the shortened chain still verifying internally;
- delete object rows.

The same probe against the CW-019 branch refused all six with `StoreSealError: the store integrity seal does not match the store contents; the store was modified outside the store API`.

### 2.3 Findings register (preserved exactly from the review record)

```text
ID   SEVERITY                    FINDING                                                  STATUS
F1   HIGH                        editing key_versions re-activated a RETIRED key          FIXED: integrity seal
F2   MEDIUM                      editing store_role opened QUARANTINE as LIVE             FIXED: integrity seal
F3   MEDIUM                      journal state COMPLETED opened a half-migrated store     FIXED: integrity seal
F4   MEDIUM                      tombstone rows deleted or edited silently                FIXED: integrity seal
F5   MEDIUM                      audit rows deleted, tail truncated, chain verified       FIXED against row edits: integrity seal
F6   MEDIUM                      object rows deleted, inserted or re-pointed undetected   FIXED: integrity seal
F7   LOW (test quality)          CW-002 AAD tests reopened with a random root secret,     FIXED: tests reopen with the genuine
                                 so they failed for the wrong reason                      secret and still pass
F8   LOW                         first seal draft did not validate the seal-key size      FIXED before commit: 32 bytes required
F9   MEDIUM (self-introduced)    the 1->2 migration step wrote the current-schema         FIXED before commit: step pinned to
                                 constants and jumped to an unsealed "schema 3"           schema 2 (caught by CW-018 tests)
F10  MEDIUM (Jev, 99800001)      seal verified only at open; state tampered while open    FIXED in 6e94e43f: every mutating
                                 was resealed, and so blessed, by the next write          transaction verifies the seal first
F11  MEDIUM (Jev, 99800001)      stripping the seal and marking schema 2 made a store     MITIGATED in 6e94e43f: legacy sealing
                                 look legacy; M1 would then seal the tampered state       needs acknowledge_unsealed_legacy_state=True;
                                                                                          residual R3 remains
F12  LOW (host review)           export_snapshot read state tampered while open           FIXED in 1e1e5c89: snapshots verify
                                 without checking the seal                                the seal first
OCR  (rule lane, host-applied)   seal metadata SQL assembled with an f-string from a      FIXED in f706155f: bound as a parameter
                                 module constant
```

No residual risk is rated HIGH or CRITICAL. The only HIGH finding (F1) is fixed. None of these findings is hidden or downgraded by this record.

### 2.4 The integrity seal (workspace schema 3)

```text
algorithm            HMAC-SHA-256
seal key             derived with HKDF-SHA-256 from the root secret under a distinct label
                     (derive_seal_key, SEAL_KEY_DERIVATION_LABEL) with the workspace id and a per-store
                     random 16-byte salt; separate from every data-encryption and backup key; never
                     encrypts anything; never persisted
size validation      the provider's derived key must be exactly 32 bytes (keyprovider.py), and storage
                     refuses seal key material of any other size (storage.py)
coverage             every metadata row, the key-version table (state and salt), tombstones, the migration
                     journal and migration log, and a digest of every object row (identity, key version,
                     format version and envelope digest); audit events are stored as AUDIT_EVENT object
                     rows, so the object digest is what detects F5
comparison           hmac.compare_digest
verification         on every open, in both normal and maintenance mode, before role and journal state are
                     trusted; at the start of every mutating transaction, right after taking the write lock
                     (F10); before every snapshot (F12)
reseal               rewritten before every mutating transaction commits
migration            forward-only M1 step 2 -> 3 writes the first seal; schema-1 and schema-2 stores are
                     migratable but never opened normally; sealing unsealed legacy state requires
                     acknowledge_unsealed_legacy_state=True (F11)
```

### 2.5 Merge authority (forward-only record, not concealed)

No explicit exact-head merge approval for `f706155f627b8c8a618ec5cfdb2106c58a173c50` is provable from the available record before PR #524 merged. The implementing session presented the MERGE_READY packet and stopped for exact-head approval at 2026-09-29T23:59:40Z. That session transcript records no later user message, and no other session transcript on this host records an approval of PR #524. The GitHub record shows no PR review (0 reviews, 0 review threads). The merge was then executed under the Founder/operator credential (`TheHalfMoon`, mergedAt 2026-09-30T00:29:49Z) as an ordinary merge commit. Its parents are the expected base and the qualified head, and its tree equals the qualified head tree (section 6).

No approval is fabricated here and none is claimed retroactively. No history was rewritten, no timestamp was changed, and no evidence was altered to conceal this. The treatment is forward-only annotation in this record. All substantive pre-merge gates were met at the exact head (section 6), and fresh-main qualification succeeded. **Approving the closeout PR with knowledge of this section constitutes post-merge ratification of the #524 merge**; a separate standalone ratification remains available if the Founder requires it.

Canonical basis: under R1-R7 and `docs/governance/roles_and_authority.md` the Founder is the final decision-maker, and no canonical rule requires a separate post-hoc ratification of a Founder-executed merge of a fully qualified head. This is the same treatment used in [cw-013-closeout.md](cw-013-closeout.md) section 2.5, [cw-015-closeout.md](cw-015-closeout.md) section 2.0, [cw-016-closeout.md](cw-016-closeout.md) section 2.0 and [cw-017-closeout.md](cw-017-closeout.md) section 2.4.

## 3. Test evidence

```text
tests/test_clinical_workspace_security_closure_v1.py   30 tests (17 test functions, parametrized)
Clinical Workspace suites (local, py3.12, at f706155f)  670 passed (640 baseline + 30 new)
```

The new suite covers:
- 14 tampering classes, each in normal and maintenance mode (`test_the_integrity_seal_refuses_every_raw_tampering_class`);
- the A1.6 retired-key attack, wrong-secret refusal, seal-key separation and size, and the seal rewritten on every API path;
- the F10, F11 and F12 regressions;
- whole-store rollback asserted as an **undetected residual** (`test_whole_store_rollback_remains_undetected_by_the_seal`);
- runtime and static no-egress proofs (`test_no_hidden_egress_across_the_full_lifecycle`);
- a no-backflow sweep over every data class (`test_no_workspace_data_class_can_flow_into_research_core`);
- exception-text leakage, closing the CW-002 deferral (`test_failure_messages_never_carry_payload_or_key_material`);
- supply chain and license (`test_the_admitted_runtime_dependency_surface_is_pinned_and_permissive`);
- the recovery runbook exercised end to end (`test_the_recovery_runbook_exercises_pass_end_to_end`).

Failing-before and passing-after regressions:

```text
F1-F6   raw-tampering probe: EXPLOITABLE on a93de067 (section 2.2); StoreSealError on the branch
F10     test_tampering_while_the_store_is_open_is_not_blessed_by_the_next_write
        99800001 source: FAIL  DID NOT RAISE StoreSealError (seal checked only at open)
        6e94e43f and later: PASS
F11     test_an_unsealed_legacy_store_is_not_sealed_without_explicit_acknowledgement
        99800001 source: FAIL  DID NOT RAISE MigrationError (no acknowledgement gate)
        6e94e43f and later: PASS
F12     test_a_backup_is_never_taken_from_state_tampered_while_open
        99800001 and 6e94e43f source: FAIL  DID NOT RAISE StoreSealError (snapshot read unverified)
        1e1e5c89 and later: PASS
        (re-executed for this closeout: the final test file run against each commit's source tree,
        with the import path confirmed to be that commit's apps/workspace/src; 3 failed at 99800001,
        1 failed + 2 passed at 6e94e43f, 3 passed at 1e1e5c89)
F7      CW-002 AAD-binding tests reopened with the genuine root secret; their assertions are
        unchanged and still pass, so the AAD binding itself is proven
F9      caught by the existing CW-018 legacy-migration regression tests before commit
```

Existing CW-002, CW-003 and CW-018 tamper tests now reopen with the **genuine** root secret and reseal the raw edit (via `storage._write_seal` with the provider's seal key). Their assertions are unchanged, and they keep proving the AEAD, audit and lifecycle layers behind the seal. Each resealed tampering class is separately proven to be detected by the seal in the security-closure suite. Schema expectations moved from 2 to 3, and the "newer schema" cases now use schema 4.

Static at the qualified head: ruff check, ruff format --check, strict mypy (532 source files), Clinical Workspace boundary guard, docs link hygiene (128 Markdown files), and `git diff --check` all PASS. CI (Linux, py3.11 and py3.12) ran the full suite at the exact head and passed; it is the authoritative lane.

## 4. Jev record (preserved exactly; YES signals are not rewritten)

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)
PROBES      = source diff: 28 (the 18 mandated classes plus 10 seal probes: seal bypass on open, seal not
              rewritten on some write, seal coverage gap, seal-key misuse, timing-unsafe comparison,
              rollback-protection overclaim, legacy store opened normally, migration step skips schema,
              wrong exception class, dead or unused code)
              pre-existing test changes: 4; review record: 6
INPUT BINDING each source-diff screen input is byte-identical (sha256) to `git diff a93de067 <commit> --
              apps/workspace/src` at the named commit
```

### 4.1 Screens

```text
source diff at 99800001 (sha256 6474abffdb20...)   25 NO / 3 YES
  stale_state_acceptance 0.61, malicious_content_authority 0.89, production_creep 0.68
source diff at 6e94e43f (sha256 d6eb40eaaeab...)   25 NO / 3 YES
  stale_state_acceptance 0.62, malicious_content_authority 0.88, production_creep 0.74
source diff at 1e1e5c89 (sha256 5acbd1d14b0c...)   25 NO / 3 YES
  stale_state_acceptance 0.54, malicious_content_authority 0.89, production_creep 0.73
FINAL source diff at f706155f (sha256 d13702d994fb...)   25 NO / 3 YES
  stale_state_acceptance 0.59, malicious_content_authority 0.87, production_creep 0.71
  (audit_bypass 0.42, seal_coverage_gap 0.37, dead_or_unused_code 0.34, seal_bypass_on_open 0.28,
   seal_not_rewritten_on_some_write 0.20, legacy_store_opened_normally 0.04,
   migration_step_skips_schema 0.05, seal_key_misuse 0.03, timing_unsafe_comparison 0.02,
   rollback_protection_overclaim 0.02, research_core_backflow 0.06, hidden_network 0.04,
   phi_creep 0.10, all others <= 0.26)
pre-existing test changes at 99800001 / 6e94e43f / 1e1e5c89 (= final; f706155f changes no test)
  4 NO each (assertion_removed_or_loosened 0.36 / 0.36 / 0.37, tamper_hidden_by_reseal 0.11 / 0.10 / 0.10)
review record at 99800001 / 6e94e43f / 1e1e5c89 (= final; f706155f changes no document)
  6 NO / 6 NO / 5 NO + 1 YES: fabricated_evidence 0.47 / 0.45 / 0.50 YES
```

### 4.2 Diagnostic sub-probes (narrow yes/no questions used to locate what drives a signal)

```text
set 1                                  99800001   6e94e43f   1e1e5c89
tamper_while_open_blessed_by_reseal    0.51 YES   0.09       0.08
seal_checked_only_at_open              0.82 YES   0.10       0.09
metadata_values_steer_behavior         0.70 YES   0.77 YES   0.75 YES
migration_upgrade_path_production      0.86 YES   0.82 YES   0.80 YES
journal_manifest_content_steers        0.49       0.47       0.54 YES
real_data_migration_enabled            0.35       0.44       0.49
seal_salt_attacker_controlled          0.20       0.17       0.16
sql_built_from_content                 0.08       0.08       0.10
production_key_or_policy_enabled       0.11       0.10       0.10

set 2 (added after the F10/F11 fixes)          1e1e5c89   f706155f (final)
write_unverified                               0.38       0.36
reads_between_tamper_and_write_unverified      0.29       0.33
snapshot_unverified                            0.07       0.06
legacy_seal_without_ack                        0.08       0.07
pre_seal_metadata_grants_more_than_refusal     0.52 YES   0.51 YES
```

Set 1 was not rerun at `f706155f`, whose only change is the parameterized seal metadata query.

### 4.3 Valid findings from Jev

```text
tamper_while_open_blessed_by_reseal 0.51 (99800001)   VALID -> F10. After the fix the sub-probe fell to
                                                       0.09 / 0.08, and seal_checked_only_at_open fell from
                                                       0.82 to 0.10 / 0.09; write_unverified is 0.36 at the
                                                       final head
metadata_values_steer_behavior 0.70 (99800001)         VALID -> F11. The sub-probe itself stayed YES
                                                       (0.77, 0.75), because pre-seal metadata still selects
                                                       the seal salt and the legacy path. The narrower
                                                       legacy_seal_without_ack question, added after the fix,
                                                       scores 0.08 / 0.07 NO. The residual is recorded as R3,
                                                       not claimed as closed
```

### 4.4 Host adjudication of the remaining YES signals

```text
stale_state_acceptance 0.59            NOT A DEFECT. The remaining window is residual R8: pure reads between a
                                       mid-session tamper and the next write, snapshot or open. Every write and
                                       every snapshot re-verifies the seal, and object content stays AEAD-protected
malicious_content_authority 0.87       NOT A DEFECT. On a schema-3 store, pre-seal metadata values can only cause
pre_seal_metadata 0.51 (diag)          a refusal or a key derivation that then fails verification. The journal is
metadata_values_steer 0.75 (diag)      sealed and bound to authenticated audit. The unsealed-legacy case is R3
journal_manifest_content 0.54 (diag)
production_creep 0.71                  NOT A DEFECT. The schema 2 -> 3 migration chain is canonical CW-019 scope.
migration_upgrade_path 0.80 (diag)     The production key-provider resolver fails closed (tested), the policy
                                       stays synthetic-only, and real_data_migration_enabled scores 0.49 NO
fabricated_evidence 0.50 (review)      NOT A DEFECT. Every cited test (48) exists, and the 14-class count and
                                       the raw-probe outputs were re-verified. This closeout re-verified the
                                       cited test names and the raw probe outputs again (section 10)
```

No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent to Jev. Jev is a screening lane, not a merge gate.

## 5. Alibaba Open Code Review record

```text
OCR_VERSION = open-code-review v1.12.9 (bccbc15f) windows/amd64, built 2026-09-22T11:06:41Z
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
ocr delegate preview origin/main..HEAD at 1e1e5c89: 6 reviewable / 15 total
  reviewed: errors.py, keyderive.py, keyprovider.py, lifecycle.py, storage.py, versions.py
  excluded: apps/workspace/README.md, cw-019-security-review.md, recovery_runbook.md (unsupported_ext);
            the six test files (default_path)
ocr delegate rule on the 6 files: one Python rule group (typos, dead code, mutable defaults, boundary and
  edge cases, error handling, identity comparisons, resource management, and further categories),
  applied by host review
finding: the seal's metadata query assembled SQL with an f-string from a module constant (not from
  content) -- fixed in f706155f by binding it as a parameter
final head f706155f: ocr delegate preview rerun reported 6 reviewable / 15 total (same file set); the
  rule group is selected by file set, so it is unchanged
OCR_FINAL_DIFF_REVIEWED = TRUE (official local lanes only)
```

The finding came from host review applying the official rule group, not from an OCR LLM verdict. No provider key is configured, and paid compute is not authorized. So no review content was sent anywhere and no LLM review is claimed. No OCR source, workflow, dependency or configuration was added to MESC.

Other bot signals on PR #524 are recorded, and none is claimed as review evidence or substitutes for Alibaba Open Code Review: Qodo was billing-paused and produced no review, CodeRabbit skipped the repository (fewer than 10 stars), and cubic wrote an auto-summary only.

## 6. Exact-head qualification, merge, and fresh main

```text
EXACT HEAD  f706155f627b8c8a618ec5cfdb2106c58a173c50 (tree 6f8256462d846378deb019054af83500fcff881d)
            on base a93de06713b723931df8a63e391eef26137a7327
  CI        36644241328 (pull_request): SUCCESS -- static py3.11/py3.12, eight pytest shards, quality
  CodeQL    36644241411 (pull_request): SUCCESS
  state     at 2026-09-29T23:59:26Z: OPEN, not draft, MERGEABLE, CLEAN, reviews 0, unresolved threads 0,
            Issue 523 OPEN

APPROVAL    none provable before merge (section 2.5); closeout approval is the forward-only ratification
MERGE       executed under the TheHalfMoon credential (merge-commit method; no squash, no rebase)
  SHA       ef1d6f7272eeb961af6ed65b537da99291f554fd
  PARENTS   a93de06713b723931df8a63e391eef26137a7327, f706155f627b8c8a618ec5cfdb2106c58a173c50
  TREE      6f8256462d846378deb019054af83500fcff881d (= qualified head tree; no mutation at merge)
  MERGED    2026-09-30T00:29:49Z

FRESH MAIN ef1d6f7272eeb961af6ed65b537da99291f554fd
  CI                          36650615864 (push): SUCCESS
  CodeQL                      36650615693 (push): SUCCESS
  Optional Extras / Backends  36650615853 (push): SUCCESS
  HF Publication              36650615739 (push): SUCCESS
```

## 7. Residual risks (preserved exactly; not claimed as protected)

```text
R1  MEDIUM  whole-store rollback     replacing the store with an older, internally consistent copy (including
                                     its seal) still opens (ADR-0039 A1.5); asserted by
                                     test_whole_store_rollback_remains_undetected_by_the_seal. Partial
                                     mitigations: the backup manifest's retained audit-head anchor and
                                     audit-chain ancestry checks at promotion and rollback. Full detection needs
                                     a trusted monotonic counter outside the store (a platform capability).
                                     Carried to the CW-020 risk register
R2  MEDIUM  no platform key provider the production resolver fails closed. ARCHITECTURE BLOCKED: no production
                                     or PHI store can open. Platform protected-secret storage needs governance
                                     (ADR-0039 A1.7, A1.8)
R3  MEDIUM  unsealed legacy state    a schema-1 or schema-2 store, genuine or produced by stripping a seal (F11),
                                     cannot be verified; an acknowledged migration seals it as found. Only
                                     synthetic legacy stores exist, and no real-data migration is authorized
R4  LOW     lexical export           links are not resolved, because the package has no filesystem capability;
            containment              containment is path algebra (CW-004 limitation unchanged)
R5  LOW     metadata readable        identities, types, revisions, salts, tombstones and journal manifests stay
                                     visible in a copied store (A1.10); the seal protects their integrity, not
                                     their confidentiality
R6  LOW     O(n) seal cost           the seal and audit verification are both linear in store size per write
R7  MEDIUM  no human independent     no human independent security review has been performed; the zero-cost
            review                   directive admits no paid or external reviewer. Carried to CW-020
R8  LOW     pure-read tamper window  get_object, key_states, tombstones and journal_entries can return tampered
                                     plaintext metadata between a mid-session tamper and the next write,
                                     snapshot or open; object content stays AEAD-authenticated
```

Prior limitations stand as declared in earlier closeouts unless explicitly resolved above. CW-019 resolves, against row-level edits by a writer without the root secret, the CW-018 plaintext journal/role/tombstone limitation and the CW-003 audit-tail truncation limitation. It does not resolve them against whole-store rollback (R1). Root-secret loss still loses both store and backup keys (CW-018 limitation unchanged).

## 8. Result

```text
CW_019 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW-001 through CW-019 = CLOSED_CANONICAL
CW-020 = ELIGIBLE_NOT_ACTIVATED (depends on CW-019 only; evidence/readiness unit, confers no PHI authority)
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
         (NOT AUTHORIZED)
Issue 523 = close with this closeout (activation fulfilled; do not rewrite the historical activation body)
Issue 429, 450, 464 = separately governed and untouched
```

## 9. Explicit non-grants preserved

```text
CW_019_MODEL_AUTHORITY = NONE
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED
REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED
NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED
EHR_WRITE_AUTHORIZATION = NOT_GRANTED
EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED
TRAINING_AUTHORIZATION = NOT_GRANTED
PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED
RESEARCH_ADMISSION_OF_WORKSPACE_DATA = NOT_GRANTED
REAL_DATA_MIGRATION = NOT_GRANTED
PRODUCTION_READINESS = NOT_CLAIMED
PHI_READINESS = NOT_CLAIMED
WHOLE_STORE_ROLLBACK_PROTECTION = NOT_CLAIMED (R1)
MALICIOUS_STORE_WRITER_PROTECTION = PARTIAL: row-level edits without the root secret are detected;
                                   whole-store rollback (R1), unsealed legacy state (R3) and the pure-read
                                   window (R8) are not protected
HUMAN_INDEPENDENT_SECURITY_REVIEW = NOT_PERFORMED (R7)
FOUNDER_COST = ZERO (no paid API, LLM, cloud, GPU, SaaS, storage, reviewer, or CI upgrade)
```

## 10. Closeout-diff qualification (docs-only increment)

This section qualifies the closeout increment itself: this file plus the `tasks.md` and `README.md` reconciliation. No implementation code or test is altered by this increment.

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)
JEV_SCOPE = final closeout diff (this file, tasks.md, README.md), screened against a ground-truth block
re-verified live from the GitHub API, git, the implementing session transcript, and the raw
implementation Jev, OCR and probe files
JEV_PROBES = 18 (fabricated implementation evidence, fabricated merge authority, false SHA, wrong merge
parents/tree, false workflow claims, hidden HIGH/CRITICAL findings, false "no residual risk", false PHI
readiness, false production readiness, false malicious-writer protection, Jev-history rewriting,
OCR-history rewriting, false human independent review, premature CLOSED_CANONICAL, wrong CW-020
dependency promotion, hidden authority expansion, seal overclaim, regression evidence misstated)
JEV_RESULTS = 18 NO / 0 YES -- fabricated_implementation_evidence 0.23, regression_evidence_misstated
0.15, false_workflow_claims 0.12, jev_history_rewriting 0.09, premature_closed_canonical 0.08,
false_sha 0.07, wrong_cw020_dependency_promotion 0.07, seal_overclaim 0.06, ocr_history_rewriting 0.05,
fabricated_merge_authority 0.04, hidden_high_critical_findings 0.04, wrong_merge_parents_or_tree 0.03,
false_no_residual_risk 0.03, false_phi_readiness 0.03, false_production_readiness 0.03,
false_malicious_writer_protection 0.02, false_human_independent_review 0.02,
hidden_authority_expansion 0.02
SENSITIVITY CHECK -- the same 18 probes rerun on three deliberately corrupted copies of this diff:
  fabricated pre-merge approval line   fabricated_implementation_evidence 0.78 YES,
                                       fabricated_merge_authority 0.73 YES (detected)
  R1 rewritten as CLOSED/detected      0 YES; false_no_residual_risk 0.05 (NOT detected)
  final Jev line rewritten to 28 NO    0 YES; jev_history_rewriting 0.11 (NOT detected)
  The broad probes miss single-line corruption of a long diff, so narrow per-claim probes were added:
NARROW DIAGNOSTICS    real diff | fabricated approval | R1 closed | Jev rewritten
  approval_claimed_before_merge        0.07 | 0.79 YES | 0.07     | 0.07
  r1_softened                          0.03 | 0.04     | 0.72 YES | 0.03
  any_residual_marked_closed           0.12 | 0.12     | 0.77 YES | 0.12
  final_jev_scores_mismatch            0.07 | 0.07     | 0.07     | 0.85 YES
  metadata_steer_reduction_claimed     0.04 | 0.04     | 0.04     | 0.04
JEV_FINAL_RESCREEN = on the diff including this section: 18 NO / 0 YES (fabricated_implementation_evidence
0.15, jev_history_rewriting 0.14, false_workflow_claims 0.12, regression_evidence_misstated 0.12,
false_sha 0.09, all others <= 0.07); narrow diagnostics 5 NO / 0 YES (any_residual_marked_closed 0.12,
final_jev_scores_mismatch 0.09, all others <= 0.07)
JEV_YES_SIGNALS = none on the real closeout diff; YES appears only on the corrupted copies
JEV_HOST_ADJUDICATION = no signal to adjudicate on the real diff. The broad probes' blind spot is
recorded rather than hidden; every closeout number was additionally host-checked line by line (below)
JEV_FINDINGS = no valid findings
JEV_FINAL_DIFF_REVIEWED = TRUE
```

Jev is a screening lane, not a merge gate. No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent. The first screens ran before this section was added; the final rescreen covers the diff including it, apart from the rescreen result lines themselves.

```text
OCR_VERSION = open-code-review v1.12.11 (a758d9c) windows/amd64, built 2026-09-29T14:36:10Z -- the current
official release, installed for this closeout from the release binary (sha256 2bb9ec31...f1f5f, matching
the release sha256sum.txt); the implementation lanes in section 5 ran on v1.12.9
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
OCR_MODE = official local/no-LLM lanes: delegate preview over origin/main..HEAD (0 reviewable / 3 total,
identical on v1.12.9 and v1.12.11) and delegate rule on the three files (one generic "system / default"
rule group: correctness, security, performance, maintainability, test coverage), applied by host review
MARKDOWN = UNSUPPORTED_EXT
OCR_FINDINGS = none
OCR_FINAL_DIFF_REVIEWED = TRUE
```

All three closeout files are Markdown, which the official tool excludes as `unsupported_ext`, so no semantic OCR review of Markdown is claimed. Instead, every closeout fact was host-reviewed against live GitHub and git truth:
- Issue #523: the activation body and its creation time.
- PR #524: its commits, files and line counts, reviews (0) and review threads (0), and the bot comments.
- The head, the tree, the merge SHA, the parents, the merge tree and the merge timestamp.
- The merge-authority evidence: every user message in the implementing session transcript, and a search of every session transcript on this host for an approval of PR #524.
- The exact-head CI and CodeQL runs (including the CI job list) and the four fresh-main runs.
- Every Jev figure: re-read from the raw JSON, with each source-diff input bound by sha256 to `git diff a93de067 <commit>`.
- The OCR preview counts, the rule output, and the command sequence around `f706155f`.
- The raw-tampering probe outputs on main and on the branch.
- The seal implementation in `storage.py`, `keyderive.py` and `keyprovider.py`.
- The failing-before and passing-after regressions, re-executed (section 3).
- The existence of all 51 test functions cited by the review record and this closeout.
- Residual risks R1-R8, the threat-model reconciliation, and the non-grants.
- The `tasks.md` dependency math (CW-020 depends only on CW-019; CW-021 is the last unit and needs separate Founder authorization).

Host review: PASS, with no defects carried to commit. A secret scan of the added lines found nothing.

Closeout increment checks:
- Relative links in the changed and linked specification files: 111 checked, 0 missing. The repository link checker covers root and `docs/` Markdown only: PASS, 128 files.
- Boundary guard: PASS.
- `ruff check`: PASS.
- `git diff --check`: clean.
- Clinical Workspace regression suites on `ef1d6f72`: 670 passed locally, with an explicit writable basetemp. CI on py3.11 and py3.12 is authoritative.
