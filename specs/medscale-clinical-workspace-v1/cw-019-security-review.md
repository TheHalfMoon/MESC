# CW-019 Security and Privacy Review

- **Status:** CW-019 review record (synthetic/local implementation only)
- **Date:** 2026-09-30
- **Activation:** [Issue #523](https://github.com/TheHalfMoon/MESC/issues/523)
- **Reviewed revision:** canonical `main` `a93de06713b723931df8a63e391eef26137a7327`, plus the CW-019 fixes recorded here
- **Contracts:** [data security and threat model](data_security.md), [migration and recovery](migration_recovery.md), [ADR-0039 ratification](adr-0039-founder-ratification.md), [recovery runbook](recovery_runbook.md), [task ledger](tasks.md)
- **Authority:** none. This review grants no PHI, production, network, model, training, EHR/external-write, paid-compute or research-admission authority, and it is **not** PHI-readiness evidence (that is CW-020, which also confers no PHI authority).

## 1. Method and independence

CW-019 attacks the implementation rather than restating its documentation. Each protection below is claimed only where a test proves it. Each residual risk is recorded with a severity and a reason.

Review lanes used:
- adversarial test suites, with the new cases in `tests/test_clinical_workspace_security_closure_v1.py`;
- Jev screening, with YES signals preserved and adjudicated;
- Alibaba Open Code Review official local lanes (the full LLM lane is blocked by the provider-credential boundary);
- host review.

The Founder's zero-cost directive admits no paid or external reviewers. **No human independent security review has been performed.** This is recorded as residual risk R7 and carried to CW-020's independent-review item.

## 2. Findings register

Severity reflects impact on the synthetic/local implementation. The attacker for F1 to F6 is anyone who can write the store file (for example another local process or a copied-then-returned file) but does not hold the root secret.

| ID | Severity | Finding | Status |
|---|---|---|---|
| F1 | HIGH | Editing the plaintext `key_versions` table re-activated a RETIRED key, so new writes used it again. This silently defeated the ADR-0039 A1.6 invariant that retired keys never resume writes. | FIXED: integrity seal |
| F2 | MEDIUM | Editing `store_role` opened a QUARANTINE store as LIVE and allowed writes (CW-018 limitation). | FIXED: integrity seal |
| F3 | MEDIUM | Editing the journal state to COMPLETED opened a half-migrated store in normal mode (CW-018 limitation). | FIXED: integrity seal |
| F4 | MEDIUM | Deleting or editing tombstone rows was accepted silently. A tombstone for a non-audited deletion could be removed and the revision later resurrected by promotion (CW-018 limitation). | FIXED: integrity seal |
| F5 | MEDIUM | Deleting audit-event rows, including the chain tail, was accepted, and the truncated chain verified internally (CW-003 limitation). | FIXED against row edits: integrity seal |
| F6 | MEDIUM | Object rows could be deleted, inserted or re-pointed outside the API without detection. | FIXED: integrity seal |
| F7 | LOW (test quality) | Several CW-002 AAD-binding tests reopened a store with a fresh random root secret. Authentication failed because of the wrong key, not because of the ciphertext relocation under test. | FIXED: tests now reopen with the genuine secret and still pass, so AAD binding is proven |
| F8 | LOW | The first CW-019 seal draft did not validate the seal key's size, so a provider returning a short key would weaken the seal. | FIXED before commit: the seal key must be 32 bytes |
| F9 | MEDIUM (self-introduced) | While schema 3 was being introduced, the schema 1 to 2 migration step wrote the current-schema constants and jumped straight to an unsealed "schema 3". | FIXED before commit: caught by the CW-018 legacy-migration regression tests; the step is pinned to schema 2 |

**The integrity seal (fix for F1 to F6).** Workspace schema 3 records a keyed seal:
- HMAC-SHA-256 under a seal key derived with HKDF-SHA-256 from the root secret, with a distinct label, the workspace id and a per-store random salt;
- computed over every metadata row, the key-version table (state and salt), tombstones, the migration journal and log, and a digest of every object row (identity, key version, format version and envelope digest).

The seal is rewritten inside every mutating transaction and verified on every open, in both normal and maintenance mode, before role and journal state are trusted. Schema-1 and schema-2 stores are migratable but are never opened normally; the forward-only M1 step from 2 to 3 writes their first seal.

Failing-before evidence, from the raw-tampering probe against canonical `main` `a93de067`:
- **A:** a retired key resumes writes; after the edit, rows sit on key versions (1, 2).
- **B:** a quarantine store opens and is written as LIVE.
- **C:** an unfinished migration opens normally, with its journal showing COMPLETED.
- **D:** a tombstone is silently removed and the state is accepted.
- **E:** the truncated audit chain verifies (2 events).
- **F:** a silent row deletion is accepted.

All six are **EXPLOITABLE** on main. On the CW-019 branch all six are refused with `StoreSealError`. `test_the_integrity_seal_refuses_every_raw_tampering_class` covers 14 tampering classes, each in both normal and maintenance mode.

## 3. Residual risks (not claimed as protected)

| ID | Severity | Risk | Disposition |
|---|---|---|---|
| R1 | MEDIUM | **Whole-store rollback.** Replacing the store with an older, internally consistent copy (including its seal) still opens (ADR-0039 A1.5). `test_whole_store_rollback_remains_undetected_by_the_seal` asserts this residual explicitly. | Partial mitigations: the backup manifest's retained audit-head anchor, and audit-chain ancestry checks at promotion and rollback. Full detection needs a trusted monotonic counter outside the store, which is a platform capability. Carried to the CW-020 risk register. |
| R2 | MEDIUM | **No platform key provider.** The production resolver fails closed. | ARCHITECTURE BLOCKED: no production or PHI store can open. Implementing platform protected-secret storage needs governance (ADR-0039 A1.7, A1.8). |
| R3 | LOW | **Pre-seal legacy tampering.** A schema-1 or schema-2 store tampered before its M1 migration is sealed as found. | Only synthetic stores exist, and no real-data migration is authorized. Recorded. |
| R4 | LOW | **Lexical export containment.** Links are not resolved because the package has no filesystem capability. | No export is written to disk; containment is path algebra (CW-004 limitation). Recorded for the first unit that obtains a filesystem capability. |
| R5 | LOW | **Plaintext metadata remains readable.** Identities, types, revisions, salts, tombstones and journal manifests stay visible in a copied store (A1.10); the seal protects their integrity, not their confidentiality. | Declared in `plaintext_metadata_scope()` and tested by `test_store_declares_which_metadata_stays_plaintext`. |
| R6 | LOW | **O(n) write cost.** The seal and audit verification are both linear in store size per write. | Acceptable at synthetic scale; a performance item, not a security one. |
| R7 | MEDIUM | **No human independent review.** | See section 1; carried to CW-020. |

No residual risk is rated HIGH or CRITICAL. The only HIGH finding (F1) is fixed.

## 4. Review lanes

| Lane | Attacks and evidence | Result |
|---|---|---|
| Application security | Exception text across backup, restore, open and store failures carries no payload marker, root secret or backup key, in text or hex, anywhere in the cause chain (`test_failure_messages_never_carry_payload_or_key_material`, which closes the CW-002 deferral). The boundary guard rejects reflective, dunder and binding-form capability access. | PASS |
| Supply chain | The Workspace runtime third-party surface is exactly `cryptography` (AEAD module only), plus `torch` and `transformers` in `asr.py` only. `cryptography==50.0.1` is pinned in CI, and the installed version and license are verified (`test_the_admitted_runtime_dependency_surface_is_pinned_and_permissive`). The guard allowlist is asserted. | PASS |
| Prompt injection / tool boundary | Hostile content stays inert throughout: `test_malicious_payload_stays_inert_data`, `test_malicious_text_grants_no_capability`, `test_malicious_metric_text_grants_no_capability`, `test_hostile_content_and_labels_stay_inert_through_the_lifecycle`. There is no tool-execution or model-action surface: `test_no_network_model_or_write_surface_in_module`. | PASS |
| Local storage / key management | The integrity seal, with F1 to F6 fixed (section 2). Seal-key separation and size checks. The wrong root secret is refused at open. A1.6 retired keys stay retired even under state edits. AAD binding is proven with the genuine key (F7). | PASS, with R1 and R2 |
| Connector security | Least-privilege manifests, the destination allowlist, mechanically disabled writes, credential material never entering the store or audit, cross-workspace refusal, offline and timeout bounds: `test_capability_manifest_least_privilege`, `test_destination_allowlist_enforced`, `test_writes_mechanically_disabled`, `test_credential_material_never_enters_store_or_audit`, `test_cross_workspace_fetch_refused`, `test_timeout_retry_bounds_and_offline_state`. Connectors run only against injected fixture transports. | PASS |
| Backup / delete | The recovery runbook exercised end to end: failed-migration snapshot rollback, rotation after recovery, and disaster recovery into a fresh store (`test_the_recovery_runbook_exercises_pass_end_to_end`). CW-018 suites cover tombstones, reconciliation, no resurrection and tamper-refusing backups. Tombstones are now sealed (F4). | PASS, with R1 |
| Privacy / data flow | No hidden egress: sockets, name resolution, subprocess and `urlopen` are forbidden at runtime across the full lifecycle (`test_no_hidden_egress_across_the_full_lifecycle`). A static sweep finds no network, process, dynamic-import or `eval`/`exec` use in the package. No Workspace data class can flow into Research Core, with or without an explicit request (`test_no_workspace_data_class_can_flow_into_research_core`). | PASS |
| Provenance / audit | Audit rows can no longer be deleted, truncated or re-pointed outside the API without detection (F5). Chain verification, replay refusal and anchored head checks are unchanged from CW-003. | PASS, with R1 |
| License / provenance | `cryptography` is Apache-2.0 or BSD-3-Clause (verified from installed metadata). No third-party source was copied into the Workspace package. No new dependency was added by CW-019. | PASS |

## 5. Threat-model reconciliation

### 5.1 `data_security.md` section 19

| Scenario | Implementation | Evidence |
|---|---|---|
| Malicious imported document instructs model to export data | content is inert data; export needs an explicit boolean request and quarantine containment | `test_malicious_payload_stays_inert_data`, `test_hostile_export_paths_are_refused` |
| Model outputs unsupported medication/order | drafts keep unsupported facts unsupported; no downstream write exists | `test_unsupported_fact_remains_unsupported`, `test_invented_fact_cannot_become_source_backed` |
| Connector token appears in exception | credentials never enter the store or audit; failure text carries no secrets | `test_credential_material_never_enters_store_or_audit`, `test_failure_messages_never_carry_payload_or_key_material` |
| Database copied from disk | AES-256-GCM rows; the seal refuses a wrong root secret at open | `test_copied_store_is_unreadable_without_the_original_root_secret`, `test_the_wrong_root_secret_is_refused_before_any_envelope_is_read` |
| Backup stolen | backup encrypted under a separate backup key; no key material or plaintext | `test_backup_key_is_separate_from_every_store_key`, `test_backup_and_quarantine_files_hold_no_plaintext_or_key_material` |
| Recording process crashes | chunk and state commits reconciled; orphans detected | `test_crash_between_chunk_and_state_commits_detected`, `test_crash_recovery_fixture` |
| User deletes encounter | cascade over session and chunks; derived state reconciled; tombstones sealed | `test_delete_cascade_removes_session_and_chunks`, `test_deletion_reconciliation_removes_stale_graph_state_and_rebuilds` |
| Workspace export copied toward Research Core | the no-backflow guard refuses every data class | `test_no_workspace_data_class_can_flow_into_research_core`, `test_direct_workspace_to_research_core_write_fails_closed` |
| De-identified export requested | lands only in Domain X; never Research Core | `test_staging_an_export_into_a_research_root_is_refused_even_when_deidentified` |
| FHIR Bundle partially accepted by server | not reachable: no EHR write or connector write authority exists | `test_writes_mechanically_disabled` (N/A until write authority) |
| Evidence source contradicts another | contradiction dominates support and never promotes | `test_contradicted_verdict_dominates_support` |
| Graph inference conflicts with explicit source | epistemic states stay distinct | `test_epistemic_states_stay_distinct` |
| Network disappears | no network path exists; offline operation | `test_no_hidden_egress_across_the_full_lifecycle`, `test_workspace_shell_runs_offline_with_deterministic_synthetic_identity` |
| Local model missing | named dependency failure; `local_files_only=True` and `trust_remote_code=False` are enforced | `test_missing_optional_deps_fail_cleanly` |
| Plugin requests undeclared capability | capability manifests are least privilege; the guard rejects capability escalation forms | `test_capability_manifest_least_privilege`, `test_workspace_boundary_guard_rejects_reflective_capability_access` |

### 5.2 `migration_recovery.md` section 19

| Scenario | Evidence |
|---|---|
| power loss mid-migration | `test_interrupted_semantic_migration_resumes_deterministically`, `test_m1_migration_is_atomic_under_a_mid_transaction_crash` |
| disk fills during prepare | preflight refuses below the declared space (`test_preflight_refusals_happen_before_any_mutation`) |
| wrong key version | `test_preflight_refusals_happen_before_any_mutation` (required key versions) |
| corrupted backup | `test_tampered_backup_bytes_fail_closed`, `test_forged_backups_with_consistent_encryption_are_still_refused` |
| object count mismatch | `test_preflight_refusals_happen_before_any_mutation` (inventory) |
| graph rebuild fails / stale index | `test_deletion_reconciliation_removes_stale_graph_state_and_rebuilds`; stale graph reads raise `GraphStaleError` |
| old app opens newer unsupported schema | `test_supported_upgrade_and_downgrade_refusal_semantics` |
| external connector contract changes | no write connector exists; `test_stale_version_metadata_yields_new_identity` |
| migration copies Workspace state into Research Core | `test_no_workspace_data_class_can_flow_into_research_core` |
| consent/security labels lost in transform | M2 validation must pass (`test_failed_validation_is_rolled_back_from_the_protected_snapshot`) |
| crash after atomic switch before cleanup | `test_crash_after_switch_resumes_to_completion` |
| rollback would resurrect deleted data | `test_rollback_discards_newer_state_and_keeps_user_deletions`, `test_edited_tombstone_reason_cannot_resurrect_an_audited_user_deletion` |

## 6. Acceptance mapping

```text
all high/critical findings resolved or architecture blocked   F1 (HIGH) fixed; no open HIGH/CRITICAL;
                                                              R2 architecture blocked (production key
                                                              provider fails closed)
threat model reconciled with implementation                   section 5
no hidden egress                                              runtime and static proofs (section 4)
no Research Core backflow                                     every data class refused (section 4)
recovery exercises pass                                       runbook exercise end to end (section 4)
```

## 7. Non-grants

```text
MODEL_AUTHORITY = NONE
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
PHI_READINESS = NOT_CLAIMED
PRODUCTION_READINESS = NOT_CLAIMED
WHOLE_STORE_ROLLBACK_PROTECTION = NOT_CLAIMED (R1)
```
