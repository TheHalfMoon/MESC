# CW-018 Canonical Closeout Evidence

- **Task:** CW-018 -- Backup, restore, deletion, and key rotation
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main)
- **Parent issue:** [#520](https://github.com/TheHalfMoon/MESC/issues/520) -- CW-018 activation
- **Implementation PR:** [#521](https://github.com/TheHalfMoon/MESC/pull/521) -- `codex/feat/cw-018-lifecycle`
- **Qualified head:** `f6699adb0111681dd3befae311bbff91251239ed` (tree `9d6977b929b0f2fa35148d74ce881d16ba08952c`)
- **Implementation merge:** `ebb87c7a2389a796fd415df28f0fe62b9d0e06c5` (tree `9d6977b929b0f2fa35148d74ce881d16ba08952c`)
- **Contracts:** [ADR-0039 ratification with Amendment A1](adr-0039-founder-ratification.md), [migration and recovery](migration_recovery.md), [data security](data_security.md), [recovery runbook](recovery_runbook.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`. It creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, telemetry, or autonomous-action authority. CW-018 proves lifecycle protection for synthetic local stores. It does **not** make the workspace production-ready or PHI-ready, and it does **not** protect against an attacker who can write the store file beyond what is stated in section 7.

## 1. Governance state entering implementation

```text
CW-001 through CW-017 CLOSED_CANONICAL
CW-017 closeout merge                8675cb7b27233d1d972119097dbff80b7a75fef7
CW-018                               activated under Issue 520 on 2026-09-29 as the single active unit under R4
                                     (Founder standing activation authority for ordinary units through CW-020)
gating contracts                     no new ADR: ADR-0039 as ratified with Amendment A1 already prescribes
                                     forward-only M1-M3 migrations, a manifest for every state-changing migration,
                                     a checkpoint table, downgrade refusal (decision 6), backups/snapshots in the
                                     leakage surface (decision 10, A1.9), the rotation state machine (A1.6) and
                                     root-secret-loss recovery semantics exercised in CW-018
model contract                       NONE -- no model selected, admitted, or ratified
authorization                        synthetic fixtures only; no network, no cloud or remote backup target, no model,
                                     no paid compute, no PHI, no production use, no real-data migration
new dependencies                     none; no boundary-guard widening
Issues 429, 450, 464                separately governed and untouched
```

## 2. Implementation history (preserved as it happened)

### 2.1 Commits on the qualified head

```text
ac040c87  feat: implement CW-018 backup, restore, deletion, and key-rotation lifecycle
f6699adb  fix: bind CW-018 destructive decisions to authenticated audit evidence
```

`ebb87c7a` is the merge of `f6699adb` into `8675cb7b`. No head was superseded after CI started. PR #521 changed 12 files (+5433/-105): `storage.py`, `lifecycle.py` (new), `audit.py`, `keyderive.py`, `keyprovider.py`, `versions.py`, `errors.py`, `apps/workspace/README.md`, `recovery_runbook.md` (new), two new test suites, and two expectations in `test_clinical_workspace_storage_v1.py`.

### 2.2 Attribution discrepancy (forward-only record, not concealed)

The PR #521 description and the `f6699adb` commit message both attribute all four Jev-driven fixes (section 4.2) to `f6699adb`. That is inaccurate. Three of them were applied to the uncommitted working tree after the first Jev screen and were first committed in `ac040c87`:
- the journal inventory binding to the authenticated PREPARED event;
- the audited-deletion override for rollback and promotion;
- the unused-parameter removal.

`f6699adb` contains the `USER_DELETION` no-weakening rule, the store-level journal transition enforcement (the OCR finding), the limitation documentation, and the regression and coverage tests. The merged PR body and commit are not rewritten. This record is the corrected account.

### 2.3 What CW-018 delivered

```text
schema 2 (M1 additive)       deletion_tombstones and migration_journal tables and a LIVE/QUARANTINE store role;
                             a real schema 1 -> 2 migration run as ONE SQLite transaction (tables, role,
                             versions, migration log, completed journal row, migration audit event); normal mode
                             refuses schema-1 stores, unfinished journals and quarantine stores
encrypted backup             transaction-consistent snapshot encrypted as one AES-256-GCM envelope under a
                             backup key derived with HKDF-SHA-256 (label mesc-clinical-workspace-backup-hkdf-
                             sha256/1, backup id, fresh per-backup 16-byte salt); no key material, no payload
                             plaintext outside the envelope
integrity manifest           versioned canonical manifest (format 1): identities, types, revisions, content
                             digests, tombstones, audit event count and head digest, body digest, explicit
                             included data class SYNTHETIC; bound as the envelope's associated data
quarantine restore           restore only into an empty QUARANTINE store (read-only apart from one import);
                             every object re-read and reconciled; audit chain verified against the manifest's
                             head anchor; SQLite integrity_check and foreign_key_check
promotion                    adds only state the live store lacks; refused when the live store holds any revision
                             absent from the backup or a differing shared revision; skips revisions the live
                             store deleted
rollback                     requires the snapshot's audit chain to be an ancestor of the live chain; discards
                             post-snapshot revisions (ROLLBACK_DISCARDED), returns migration-superseded ones, keeps
                             user deletions deleted (tombstone USER_DELETION or an authenticated object_delete
                             event), keeps every audit event; untracked absence refused
deletion tombstones          written in the same transaction as every deletion; a USER_DELETION tombstone can never
                             be weakened; re-creation of a revision by a writer holding its plaintext clears it
deletion reconciliation      reconcile_deletions removes stale graph edges, nodes and views, dataset collections and
                             export manifests through each unit's audited delete path; DELETION_POLICY declares
                             the policy for audit, provenance, backups, indexes/caches (none exist), external
                             copies (none exist) and cryptographic erasure (not claimed)
migration engine             section-5 manifest; eleven preflight checks before any mutation; each M2 step
                             (tombstone old revision, write new revision, advance checkpoint) is one transaction;
                             journal states PREPARED, MUTATING, VALIDATING, SWITCHED, COMPLETED, ROLLED_BACK,
                             FAILED_REQUIRES_INTERVENTION; deterministic resume bound to the authenticated
                             PREPARED audit event; store refuses to reopen a finished entry or start a second
                             unfinished migration
key rotation                 rotate_workspace_key resumes the persisted A1.6 state machine after interruption at
                             any boundary and retires every emptied key; retired keys cannot decrypt or write
downgrade semantics          readable schema 2..2; SUPPORTED_DOWNGRADE_TARGETS = (); newer store schemas refused
                             in normal and maintenance mode; newer or older backups refused at restore
audit coverage               backup, restore (promote and rollback), migration (PREPARED, COMPLETED, FAILED),
                             key_rotation (begin, completed); identities, counts and digests only
recovery runbook             recovery_runbook.md: backup, disaster recovery, snapshot rollback, M1, M2 resume and
                             failure, downgrade, key rotation, deletion reconciliation, limits, non-grants
```

## 3. Test evidence

```text
tests/test_clinical_workspace_lifecycle_v1.py              23 acceptance tests
tests/test_clinical_workspace_lifecycle_adversarial_v1.py  21 adversarial tests
Clinical Workspace suites (local, py3.12)                  640 passed (596 baseline + 44 new)
tests/test_clinical_workspace_storage_v1.py                two expectations moved to schema 2: a new store records
                                                           schema 2 and migration log (0 -> 2); the newer-schema test
                                                           writes schema 3 and still asserts the downgrade refusal
```

Adversarial coverage includes:
- **Tampered backups:** flipped manifest digest, flipped envelope byte, truncation, wrong magic, oversized length, non-canonical manifest, non-bytes input.
- **Spliced manifests and wrong keys:** a manifest spliced from another backup; a wrong workspace; a wrong root secret; the unavailable platform provider.
- **Forged backups with consistent encryption:** wrong digest, missing object, data class `PHI`, audit count, schema 3, schema 1, production policy, format 2, duplicate object, object also tombstoned.
- **Quarantine and promotion misuse:** restore aimed at a live root; double restore; divergent revisions; a foreign or empty quarantine; forked or newer snapshots; untracked absence.
- **Preflight refusals:** every refusal case proven to leave the store unmutated, plus stale snapshots, active capture, and the exclusive lock.
- **Crash and journal integrity:** M1 atomicity under a mid-transaction crash; a crash after `SWITCHED`; journal and tombstone CHECK constraints; a tampered checkpoint; a tampered journal inventory; an edited tombstone reason; tombstone weakening; journal transition enforcement.
- **Leakage and inert content:** leakage across the backup, the quarantine database, `-wal` and `-shm`; hostile payload text staying inert.

Full-repository suite on the Windows host: the only failures are pre-existing host failures. For every affected file, the failing node set was identical on unmodified `main` `8675cb7b` and on the branch (34 = 34, FHIR CLI, HF publication and MRL files); `test_mesc_mrl_0808_sandbox_v1.py` needs POSIX `fcntl`. The complete local run was later stopped by the host for low memory and was not restarted. CI (Linux, py3.11 and py3.12) ran the full suite at the exact head and passed; it is the authoritative lane.

Static at the qualified head: ruff check, ruff format --check, strict mypy (531 source files), Clinical Workspace boundary guard, docs link hygiene, `git diff --check` -- all PASS.

## 4. Jev record (preserved exactly; YES signals are not rewritten)

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)
PROBES      = 32 per code scope: the 18 mandated classes plus 14 CW-018-specific
              (silent overwrite, deleted-content resurrection, backup key leak, backup plaintext leak,
              backup tamper acceptance, quarantine escape, downgrade acceptance, migration without
              preflight, non-atomic checkpoint, nondeterministic resume, retired-key resurrection,
              wrong exception class, dead or unused code, resource leak)
```

### 4.1 Screens

```text
lifecycle.py, pre-commit working tree (sha256 2b35fbde...c46dfb)
  30 NO / 2 YES: malicious_content_authority 0.53, dead_or_unused_code 0.56
lifecycle.py at ac040c87 (sha256 275a5ac0...cf6876)
  30 NO / 2 YES: malicious_content_authority 0.54, dead_or_unused_code 0.54
core module diff (storage, audit, keyprovider, keyderive, versions, errors) at ac040c87
  30 NO / 2 YES: malicious_content_authority 0.77, deleted_content_resurrection 0.73
FINAL lifecycle.py at f6699adb (sha256 1ac837f4...55f9c)
  30 NO / 2 YES: malicious_content_authority 0.53, dead_or_unused_code 0.57
  (deleted_content_resurrection 0.04, silent_overwrite 0.04, quarantine_escape 0.04,
   migration_without_preflight 0.03, non_atomic_checkpoint 0.05, production_creep 0.39)
FINAL core module diff at f6699adb
  30 NO / 2 YES: malicious_content_authority 0.74, production_creep 0.80
  (deleted_content_resurrection 0.25, resource_leak 0.34, ehr_external_write_creep 0.29)
FINAL pre-existing test changes at f6699adb
  3 NO: tests_weakened 0.10, expected_values_unjustified 0.05, newer_schema_refusal_lost 0.16
```

Diagnostic sub-probes (narrow yes/no questions used to locate what drives a compound signal):

```text
on lifecycle.py at ac040c87
  YES abstract_interface_unused_args 0.74, unused_private_helpers 0.67,
      unused_parameters_in_concrete_functions 0.57, authenticated_manifest_steers_behavior 0.52,
      caller_strings_steer_behavior 0.52
  NO  plaintext_journal_steers_resume 0.07, plaintext_tombstone_reason_steers_rollback 0.07,
      transform_selected_by_content 0.05, payload_bytes_steer_behavior 0.28, unused_imports 0.37,
      unreachable_branches 0.40, unauthenticated_manifest_steers_before_auth 0.37
on the core diff at ac040c87
  YES tombstone_cleared_on_reput 0.96, tombstone_reason_downgrade 0.82,
      import_snapshot_resurrects 0.55, journal_state_plaintext_gates_open 0.53
  NO  store_role_plaintext_gates_open 0.45, tombstone_reason_plaintext 0.44,
      restored_backup_id_plaintext 0.41, payload_steers_storage 0.27, audit_prepare_event_misuse 0.14
on the core diff at f6699adb
  YES production_upgrade_path 0.88
  NO  enables_real_data_migration 0.48, production_word_only 0.16, production_key_provider_enabled 0.07,
      policy_version_changed 0.06, journal_state_plaintext_gates_open 0.29, role_plaintext_gates_open 0.25,
      tombstone_reason_downgrade 0.05, journal_limitation_disclosed 0.19
```

### 4.2 Valid defects found and fixed before the qualified head

```text
1 unused semantic-validation parameter   _validate_semantic(store, entry, ...) never read entry
                                         (dead_or_unused_code; ruff ARG001 confirmed) -- fixed in ac040c87
2 editable journal redirecting resume    the plaintext journal inventory decided which objects a resumed
                                         M2 migration transformed and tombstoned -- fixed in ac040c87:
                                         the PREPARED migration audit event records inventory and manifest
                                         digests, and resume refuses a journal that differs
3 editable tombstone reason              rollback returned any revision whose plaintext tombstone reason
  (resurrection risk)                    was not USER_DELETION -- fixed in ac040c87: revisions named by an
                                         authenticated object_delete audit event are kept deleted
4 USER_DELETION tombstone weakening      INSERT OR REPLACE let a later tombstone write replace
                                         USER_DELETION with a weaker reason -- fixed in f6699adb:
                                         ON CONFLICT ... WHERE reason <> 'USER_DELETION'
```

Reproduction against the unfixed code, and passing results after the fix:

```text
defect 3  test_edited_tombstone_reason_cannot_resurrect_an_audited_user_deletion
          pre-fix module (sha256 2b35fbde...): FAIL  AssertionError: assert 1 == 0 (the deletion was returned)
          fixed: PASS
defect 2  test_edited_journal_inventory_cannot_redirect_a_resumed_migration
          pre-fix module: FAIL  AuditError: stored audit event is not canonical ASCII JSON
          (resume transformed an audit event named by the edited inventory)
          fixed: PASS
defect 4  test_a_user_deletion_tombstone_can_never_be_weakened
          storage at ac040c87: FAIL  reason became ROLLBACK_DISCARDED instead of USER_DELETION
          fixed: PASS
defect 1  structural (unused parameter); ruff --select ARG on the final head reports only the
          fail-closed interface base methods (KeyProvider, SemanticTransform)
```

### 4.3 Host adjudication of the remaining YES signals

```text
malicious_content_authority 0.53 / 0.74   NOT A DEFECT after the fixes above. Backup manifest fields act only
                                          after authentication, as checks and descriptions; caller strings form
                                          identities only (migration_id charset admitted; revision collisions
                                          fail closed); re-put clearing a tombstone is an explicit re-creation by
                                          a writer holding the plaintext. The residual driver, plaintext
                                          journal state and store role gating normal open, is a recorded
                                          limitation (section 7), not a claimed protection.
dead_or_unused_code 0.57                  NOT A DEFECT. The remaining unused arguments belong to the fail-closed
                                          abstract SemanticTransform interface (the KeyProvider pattern). An AST
                                          scan shows every module-level helper and constant is used.
production_creep 0.80                     NOT A DEFECT. The M1 upgrade engine is the canonical CW-018 acceptance
                                          scope (upgrade/downgrade semantics, migration manifest and preflight).
                                          It cannot reach real data: the production key-provider resolver fails
                                          closed (tested), and the policy version stays synthetic-only.
                                          enables_real_data_migration scored 0.48 NO.
tombstone_cleared_on_reput 0.96 (diag)    NOT A DEFECT, by design. Re-creation is an explicit write carrying its own
                                          audit event, and CW-017 tests rely on re-creating a revision after
                                          deletion. Promotion and rollback never re-create a user deletion.
import_snapshot_resurrects 0.55 (diag)    NOT A DEFECT. A quarantine store is never live. Promotion and rollback
                                          re-apply deletions.
```

No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent to Jev. Jev is a screening lane, not a merge gate.

## 5. Alibaba Open Code Review record

```text
OCR_VERSION = open-code-review v1.12.9 (bccbc15f) windows/amd64, built 2026-09-22T11:06:41Z
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
ocr delegate preview 8675cb7b..HEAD: 7 reviewable / 12 total
  reviewed: audit.py, errors.py, keyderive.py, keyprovider.py, lifecycle.py, storage.py, versions.py
  excluded: apps/workspace/README.md and recovery_runbook.md (unsupported_ext); the three test files (default_path)
ocr delegate rule on the 7 files: one Python rule group (typos, dead code, mutable defaults, boundary and
  edge cases, error handling, identity comparisons, resource management, performance, concurrency),
  applied by host review
finding: boundary handling on journal transitions (a finished journal entry could be reopened, and a
  second unfinished migration could be started) -- fixed in f6699adb with store-level enforcement and
  test_journal_transitions_are_enforced_by_the_store
final-diff rerun at f6699adb: identical rule group, no new findings
OCR_FINAL_DIFF_REVIEWED = TRUE
```

No provider key is configured and paid compute is not authorized, so no review content was sent anywhere and no LLM review is claimed. No OCR source, workflow, dependency or configuration was added to MESC.

## 6. Exact-head qualification, approved merge, and fresh main

```text
EXACT HEAD  f6699adb0111681dd3befae311bbff91251239ed (tree 9d6977b929b0f2fa35148d74ce881d16ba08952c)
            on base 8675cb7b27233d1d972119097dbff80b7a75fef7
  CI        36614424459 (pull_request): SUCCESS -- static py3.11/py3.12, eight pytest shards, quality
  CodeQL    36614424420 (pull_request): SUCCESS
  state     OPEN, not draft, MERGEABLE, CLEAN, reviews 0, unresolved threads 0, Issue 520 OPEN

APPROVAL    explicit Founder exact-head approval for PR 521 at f6699adb (tree 9d6977b9, base 8675cb7b,
            CI 36614424459, CodeQL 36614424420), ordinary merge commit only, given 2026-09-29T20:06:33Z
MERGE       gh pr merge 521 --merge --match-head-commit f6699adb... run 2026-09-29T20:06:48Z
  SHA       ebb87c7a2389a796fd415df28f0fe62b9d0e06c5
  PARENTS   8675cb7b27233d1d972119097dbff80b7a75fef7, f6699adb0111681dd3befae311bbff91251239ed
  TREE      9d6977b929b0f2fa35148d74ce881d16ba08952c (= approved head tree; no mutation at merge)
  MERGED    2026-09-29T20:06:50Z

FRESH MAIN ebb87c7a2389a796fd415df28f0fe62b9d0e06c5
  CI                          36624035813 (push): SUCCESS
  CodeQL                      36624035849 (push): SUCCESS
  Optional Extras / Backends  36624035789 (push): SUCCESS
  HF Publication              36624035831 (push): SUCCESS
```

## 7. Recorded limitations (not hidden, not claimed as protected)

```text
plaintext lifecycle metadata  journal state, store role and tombstone reasons are declared plaintext metadata
                              (ADR-0039 A1.10). A writer of the store file can edit them, just as it can roll
                              back the whole store (A1.5). Decisions that could destroy or resurrect content
                              are bound to authenticated audit evidence. The normal-open refusals driven by
                              journal state and role guard against operator error, NOT against a malicious
                              writer. CW-019 owns attacking this surface (writable-store, journal, role,
                              tombstone and rollback tampering, authenticated-vs-plaintext authority confusion)
root-secret loss              store keys and backup keys both derive from the root secret; losing it loses both
whole-store rollback          AES-256-GCM still cannot detect a valid historical whole-store rollback (A1.5);
                              CW-018 adds one externally retained anchor (the backup manifest's audit head) and
                              audit-chain ancestry checks at promotion and rollback
audit spine                   no database-level write-once trigger and no audit append checkpointing were added;
                              every append still re-verifies the chain (cost grows with trail length)
migration classes             M1 (schema 1 -> 2), a generic journaled M2 engine and M3 rotation orchestration; M0,
                              M4 and M5 have no dedicated engine (M4 uses each unit's deterministic rebuild; no
                              connector contract migration exists because no connector write authority exists)
disk space                    not measured inside the package; the caller declares it and preflight refuses below
                              twice the stored envelope size
backup expiry                 backups are immutable bytes held by the caller; expiring them is an operator duty;
                              deleting a revision does not erase copies inside retained backups
no filesystem capability      backups are produced and consumed as bytes; the package still cannot resolve links
                              (CW-004 limitation unchanged)
no platform key provider      the production resolver still fails closed (CW-002 limitation unchanged)
prior limitations             as declared in earlier closeouts unless explicitly resolved elsewhere
```

## 8. Result

```text
CW_018 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW-001 through CW-018 = CLOSED_CANONICAL
CW-019 = ELIGIBLE_NOT_ACTIVATED (depends on CW-010, CW-012, CW-014, CW-015, CW-016, CW-018, all CLOSED_CANONICAL)
CW-020 = BLOCKED_DEPENDENCY (depends on CW-019)
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 520 = close with this closeout (activation fulfilled; do not rewrite the historical activation body)
Issue 429, 450, 464 = separately governed and untouched
```

## 9. Explicit non-grants preserved

```text
CW_018_MODEL_AUTHORITY = NONE
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
PRODUCTION_UPGRADE = NOT_GRANTED
PRODUCTION_READINESS = NOT_CLAIMED
PHI_READINESS = NOT_CLAIMED
MALICIOUS_STORE_WRITER_PROTECTION = NOT_CLAIMED (see section 7)
FOUNDER_COST = ZERO (no paid API, LLM, cloud, GPU, SaaS, storage, reviewer, or CI upgrade)
```

## 10. Closeout-diff qualification (docs-only increment)

This section qualifies the closeout increment itself: this file plus the `tasks.md` and `README.md` reconciliation. No implementation code or test is altered by this increment.

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)
JEV_SCOPE = final closeout diff, screened against a ground-truth block re-verified live from the
GitHub API, git, and the raw implementation Jev outputs
JEV_PROBES = 16 (fabricated evidence, false SHA/run IDs, incorrect merge parents/tree, premature
CLOSED_CANONICAL, hidden limitation removal, Jev-history rewriting, OCR-history rewriting, false
production readiness, false PHI readiness, false malicious-writer protection, false downgrade
protection, false backup guarantees, dependency promotion error, hidden authority expansion,
defect concealment, attribution concealment)
JEV_RESULTS = 14 NO / 2 YES -- false_backup_guarantees 0.58 YES, dependency_promotion_error 0.53 YES;
fabricated_evidence 0.24, false_sha_or_run_ids 0.14, incorrect_merge_parents_or_tree 0.03,
premature_closed_canonical 0.08, hidden_limitation_removal 0.04, jev_history_rewriting 0.19,
ocr_history_rewriting 0.05, false_production_readiness 0.02, false_phi_readiness 0.02,
false_malicious_writer_protection 0.03, false_downgrade_protection 0.06,
hidden_authority_expansion 0.03, defect_concealment 0.02, attribution_concealment 0.03
DIAGNOSTIC SUB-PROBES -- backup: protection_after_root_secret_loss 0.03, cryptographic_erasure 0.03,
remote_or_offsite_backup 0.03, backup_metadata_confidential 0.07,
independent_of_store_key_compromise 0.04, tamper_detection_without_key 0.15,
backup_limits_stated 0.98 YES; ledger: cw019_marked_eligible_before_cw018_closed 0.68 YES,
cw019_dependency_missing 0.06, unit_activated 0.12, cw020_promoted 0.09
HOST ADJUDICATION -- false_backup_guarantees: NOT A DEFECT; every specific backup overclaim answers
NO and the limits are stated (0.98). dependency_promotion_error: NOT A DEFECT; recording CW-019 as
ELIGIBLE in the same increment that records CW-018 closed is the established closeout convention
(the CW-017 closeout in PR #519 did the same), the ledger becomes canonical only when this closeout
merges and fresh main passes, no dependency is missing, and nothing is activated.
JEV_FINAL_RESCREEN = 16 NO / 0 YES on the diff including the lines above -- false_backup_guarantees
0.40, dependency_promotion_error 0.33, fabricated_evidence 0.28, jev_history_rewriting 0.24,
false_sha_or_run_ids 0.17, all others <= 0.08
JEV_FINDINGS = no valid findings
JEV_FINAL_DIFF_REVIEWED = TRUE
```

Jev is a screening lane, not a merge gate. No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent. The closeout diff was re-screened after this section was added; the record above reflects the final diff apart from these result lines themselves.

```text
OCR_VERSION = open-code-review v1.12.9 (bccbc15f) windows/amd64, built 2026-09-22T11:06:41Z
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
OCR_MODE = official local/no-LLM lane (delegate preview) over the closeout diff
MARKDOWN = UNSUPPORTED_EXT
OCR_FINAL_DIFF_REVIEWED = TRUE
```

All three closeout files are Markdown, which the official tool excludes as `unsupported_ext` (0 reviewable / 3 total), so no semantic OCR review of Markdown is claimed. Instead, every closeout fact was host-reviewed against live GitHub and git truth:
- Issue #520 activation.
- The PR #521 commits, files and line counts.
- The head, tree, merge SHA, parents and timestamps.
- The approval and merge-command timestamps, taken from the session transcript.
- The exact-head CI and CodeQL runs, and the four post-merge runs on main.
- Every Jev figure, re-read from the raw JSON outputs and bound to module sha256 hashes.
- The OCR preview counts and rule-group findings.
- The existence of the four regression tests.
- The `ac040c87`/`f6699adb` attribution.
- The `tasks.md` dependency math and the README frontier.
- The recorded limitations and the non-grants.

Host review: PASS, with no defects carried to commit.

Closeout increment checks:
- Relative links in the changed and linked specification files: 100 checked, 0 missing. The repository link checker covers root and `docs/` Markdown only: PASS, 128 files.
- Boundary guard: PASS.
- `git diff --check`: clean.
- CW-018 lifecycle and storage regression suites on `ebb87c7a`: 72 passed locally, with an explicit writable basetemp. CI on py3.11 and py3.12 is authoritative.
