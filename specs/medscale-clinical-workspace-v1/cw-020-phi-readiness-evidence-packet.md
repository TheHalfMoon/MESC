# CW-020 PHI-Readiness Evidence Packet

- **Task:** CW-020 -- PHI-readiness evidence packet
- **Activation:** [Issue #526](https://github.com/TheHalfMoon/MESC/issues/526)
- **Evidence revision:** canonical `main` `3b3efa1c02b641a9107060bc51788960a4256b7f` (tree `fa685bd33c1e6a0ecbec9f2b34563a747699b649`), the CW-019 closeout merge
- **Contracts:** [task ledger](tasks.md) CW-020, [data security and threat model](data_security.md) section 20, [ADR-0038](../../docs/adr/0038-local-clinical-workspace-boundary.md) Clinical Workspace invariants, [CW-019 security review](cw-019-security-review.md), [incident response](incident_response.md), [recovery runbook](recovery_runbook.md)
- **Mechanical binding:** `tests/test_clinical_workspace_phi_readiness_packet_v1.py`

```text
PHI_READINESS_EVIDENCE = NOT PHI AUTHORITY
PHI_READY != PHI_AUTHORIZED
```

This packet assembles the evidence that bears on whether the Clinical Workspace architecture could later be **considered** for a bounded real-data pilot. It is an assessment, not a grant. It ingests no PHI, and it grants no PHI, production, clinical, model, network, EHR-write, external-write, training, paid-compute or research-admission authority. Completing it does not authorize CW-021.

## 1. Verdict

```text
PHI_READINESS = NOT_READY
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_READINESS = NOT_READY
PRODUCTION_AUTHORIZATION = NOT_GRANTED
QUALIFICATION_SCOPE = SYNTHETIC_ONLY
CW-021 = NOT AUTHORIZED
```

The synthetic/local implementation is well evidenced for encryption, integrity, backup, deletion, audit, no-backflow, offline operation, connector least privilege, prompt-injection inertness and model isolation. It is **not** PHI-ready. Blocking gaps, each recorded in sections 4, 5 and 6:
- **Architecture blocked:** no platform protected-key provider exists, so no production or PHI store can open (R2).
- **Missing controls:** there is no user authentication or patient/encounter access control (G1), and reads are never audited (G2).
- **No independent review:** no human independent security review or penetration assessment has been performed (R7).
- **No governing scope or policy:** no PHI-scope ADR exists (G5), and there is no privacy or retention policy for real data (G6).
- **Undetected rollback:** whole-store rollback remains undetected (R1).

## 2. Evidence binding

```text
EVIDENCE_REVISION   3b3efa1c02b641a9107060bc51788960a4256b7f
  parents           ef1d6f7272eeb961af6ed65b537da99291f554fd, b70aaab86e01b9432c957e7c3558332759a9742a
  tree              fa685bd33c1e6a0ecbec9f2b34563a747699b649
  fresh-main CI                          36685836567 (push): SUCCESS
  fresh-main CodeQL                      36685836641 (push): SUCCESS
  fresh-main Optional Extras / Backends  36685836544 (push): SUCCESS
  fresh-main HF Publication              36685836545 (push): SUCCESS
WORKSPACE_CODE      identical at ef1d6f72 and 3b3efa1c (the CW-019 closeout changed documentation only)
IDENTITIES          WORKSPACE_SCHEMA_VERSION = 3
                    ENCRYPTION_FORMAT_VERSION = 1
                    POLICY_VERSION = mesc-clinical-workspace-synthetic-only/1
                    AEAD dependency cryptography==50.0.1
```

**Scope.** This packet assesses the Clinical Workspace package (`apps/workspace/`) and its specifications only. Research Core, MRL, model qualification and the Hugging Face publication path were **not** assessed for PHI handling. They stay synthetic-only, and PHI must never reach them: the Workspace-side no-backflow guard refuses every flow toward Research Core (section 7), but this packet is not a PHI assessment of those components.

Every test cited below exists at the evidence revision. The binding test checks that each cited test function exists, and that each identity above equals the code constant. CI runs the whole suite at every head, so the cited evidence is re-executed at the head that carries this packet.

## 3. Acceptance mapping (tasks.md CW-020)

| Acceptance item | Status | Evidence |
|---|---|---|
| all security/data-flow evidence bound to exact canonical revision | EVIDENCED_SYNTHETIC | section 2; section 7 data-flow diagram; the binding test |
| runtime/model identities | PARTIAL | ASR identity is pinned and enforced (section 8). No real generation model is admitted: the draft engine uses synthetic placeholder identities (`test_mutable_model_revision_rejected`, `test_no_ehr_write_or_remote_api_exists`) |
| connector scope | EVIDENCED_SYNTHETIC | fixture-only (`fixture://` allowlist) and read-only, with writes mechanically disabled: `test_capability_manifest_least_privilege`, `test_destination_allowlist_enforced`, `test_writes_mechanically_disabled`, `test_credential_material_never_enters_store_or_audit`, `test_cross_workspace_fetch_refused`, `test_timeout_retry_bounds_and_offline_state`. No real connector exists |
| retention/deletion | PARTIAL | deletion is evidenced (gate row "deletion tests"). Retention is a single synthetic class, `session-scoped` v1, with no time-based expiry and no real-data retention policy (G6) |
| incident response | PARTIAL | [incident_response.md](incident_response.md) maps every raised security signal to a response and is mechanically bound to `errors.py`; it has never been drilled with humans (G7) |
| unresolved risk register | EVIDENCED_SYNTHETIC | section 6 |
| independent review | NOT_MET | **no human independent security review has been performed** (R7); every review so far is agent and tool lanes (tests, Jev, Alibaba Open Code Review local lanes, host review) |

## 4. PHI-readiness gate (data_security.md section 20)

| Gate item | Status | Evidence | Blocking risks |
|---|---|---|---|
| accepted scope ADR | NOT_MET | ADR-0038 is accepted, but it keeps `PHI_INGESTION = NOT_AUTHORIZED`; no ADR scopes a PHI pilot | G5 |
| data-flow diagram matches implementation | EVIDENCED_SYNTHETIC | section 7, with each edge bound to tests | R4 |
| encryption/key tests | EVIDENCED_SYNTHETIC | `test_payload_round_trips_through_the_store`, `test_every_encryption_uses_a_fresh_96_bit_nonce`, `test_derived_keys_are_separated_per_workspace_and_key_version`, `test_tampered_envelopes_fail_closed`, `test_swapping_ciphertext_between_objects_fails_authentication`, `test_a_retired_key_version_cannot_read_or_write_objects`, `test_rotation_retires_the_previous_key_after_verified_migration`, `test_copied_store_is_unreadable_without_the_original_root_secret`, `test_the_integrity_seal_refuses_every_raw_tampering_class`, `test_platform_provider_is_unavailable_and_fails_closed_before_any_file` | R1, R2, R5 |
| backup/restore tests | EVIDENCED_SYNTHETIC | `test_backup_is_encrypted_and_carries_a_versioned_integrity_manifest`, `test_backup_key_is_separate_from_every_store_key`, `test_restore_lands_in_quarantine_that_normal_mode_refuses`, `test_promotion_never_overwrites_newer_live_state`, `test_tampered_backup_bytes_fail_closed`, `test_forged_backups_with_consistent_encryption_are_still_refused`, `test_a_backup_is_never_taken_from_state_tampered_while_open`, `test_the_recovery_runbook_exercises_pass_end_to_end` | R1 |
| deletion tests | EVIDENCED_SYNTHETIC | `test_delete_removes_the_row_and_makes_the_object_unreadable`, `test_every_deletion_path_records_a_tombstone`, `test_delete_cascade_removes_session_and_chunks`, `test_deletion_reconciliation_removes_stale_graph_state_and_rebuilds`, `test_deletion_policy_declares_every_required_scope`, `test_rollback_discards_newer_state_and_keeps_user_deletions`, `test_a_user_deletion_tombstone_can_never_be_weakened`, `test_deletion_makes_no_cryptographic_erasure_claim` | no cryptographic erasure; copies in retained backups persist |
| audit tests | PARTIAL | the chain, tamper and replay properties are evidenced: `test_removing_a_middle_event_breaks_the_chain`, `test_tail_truncation_is_only_detected_with_an_external_anchor`, `test_replaying_an_event_object_is_refused`, `test_provenance_and_audit_do_not_leak_payload_into_documents`, `test_audit_events_cover_lifecycle`, `test_lifecycle_audit_events_carry_no_payload_content`. Coverage is incomplete: reads, logins and security failures are never audited | G2, G3, G4, R1 |
| no-backflow tests | EVIDENCED_SYNTHETIC | `test_no_workspace_data_class_can_flow_into_research_core`, `test_direct_workspace_to_research_core_write_fails_closed`, `test_staging_an_export_into_a_research_root_is_refused_even_when_deidentified` | none |
| offline/no-hidden-egress tests | EVIDENCED_SYNTHETIC | `test_no_hidden_egress_across_the_full_lifecycle`, `test_no_workspace_module_imports_a_process_network_or_environment_capability`, `test_workspace_shell_runs_offline_with_deterministic_synthetic_identity` | none |
| connector least-privilege tests | EVIDENCED_SYNTHETIC | `test_capability_manifest_least_privilege`, `test_destination_allowlist_enforced`, `test_writes_mechanically_disabled` | fixture transports only |
| prompt-injection/tool-boundary tests | EVIDENCED_SYNTHETIC | `test_malicious_payload_stays_inert_data`, `test_malicious_text_grants_no_capability`, `test_hostile_content_and_labels_stay_inert_through_the_lifecycle`, `test_no_network_model_or_write_surface_in_module`, `test_workspace_boundary_guard_rejects_reflective_capability_access` | no real generation model has been exercised |
| model isolation | EVIDENCED_SYNTHETIC | `test_manifest_matches_ratified_identities`, `test_trust_flags_enforced`, `test_revision_mismatch_fails_closed`, `test_missing_snapshot_fails_closed`, `test_research_core_unreachable`, `test_missing_optional_deps_fail_cleanly` | ASR only; no generation model |
| dependency/source/license review | EVIDENCED_SYNTHETIC | `test_the_admitted_runtime_dependency_surface_is_pinned_and_permissive`, `test_workspace_package_declares_exactly_one_aead_dependency`, `test_identity_and_license_drift_rejected`; the CW-019 supply-chain and license lanes | self-review only (R7) |
| threat-model review | PARTIAL | [cw-019-security-review.md](cw-019-security-review.md) section 5 reconciles every `data_security.md` section 19 and `migration_recovery.md` section 19 scenario with a test; the review was performed by agent and tool lanes only | R7 |
| security review / penetration assessment appropriate to deployment | NOT_MET | no human security review and no penetration assessment exist, and no deployment environment is defined | R7 |
| privacy/retention policy | NOT_MET | only the synthetic `session-scoped` v1 retention class exists; there is no privacy policy, retention schedule or data-subject process for real data | G6 |
| incident/recovery runbook | PARTIAL | [recovery_runbook.md](recovery_runbook.md), exercised end to end by `test_the_recovery_runbook_exercises_pass_end_to_end`; [incident_response.md](incident_response.md), not drilled | G7 |

## 5. ADR-0038 Clinical Workspace invariants

ADR-0038 requires the Workspace specification to enforce these invariants before any PHI-capable implementation is authorized.

| Invariant | Status | Evidence | Blocking risks |
|---|---|---|---|
| local-first operation for the core path | EVIDENCED_SYNTHETIC | `test_workspace_shell_runs_offline_with_deterministic_synthetic_identity`, `test_no_hidden_egress_across_the_full_lifecycle` | none |
| explicit network boundaries and no silent cloud fallback | EVIDENCED_SYNTHETIC | `test_no_workspace_module_imports_a_process_network_or_environment_capability`, `test_trust_flags_enforced`, `test_destination_allowlist_enforced` | none |
| encryption-at-rest and protected key material | ARCHITECTURE_BLOCKED | encryption is evidenced (section 4), but protected key material needs a platform key provider, and none exists: `test_platform_provider_is_unavailable_and_fails_closed_before_any_file`, `test_in_memory_test_provider_is_not_production_selectable` | R2 |
| encounter/patient access controls | NOT_MET | no authentication or authorization layer exists | G1 |
| immutable audit events for reads, writes, exports, deletion, model actions, and connector actions | PARTIAL | writes, deletion, model actions and connector reads are audited: `test_audit_events_cover_lifecycle`, `test_store_provenance_and_audit`, `test_synthetic_draft_validates_and_stores` (AI generation), `test_writes_mechanically_disabled` (connector read), `test_query_audit_records_evidence_query`. Exports: FHIR staging emits an `export` event, but no test asserts it, and dataset export staging is audited as `object_create`. **Reads are never audited** | G2, G3, G4, G8 |
| explicit retention and deletion semantics for audio, transcripts, notes, embeddings/indexes, graphs, and backups | PARTIAL | the deletion policy covers every scope: `test_deletion_policy_declares_every_required_scope`, `test_delete_cascade_removes_session_and_chunks`, `test_chunk_identity_order_digests_and_retention`; retention is one synthetic class with no expiry | G6 |
| human review before any drafted clinical note, order, code, or other write is treated as final | EVIDENCED_SYNTHETIC | `test_direct_draft_to_finalized_is_forbidden`, `test_no_finalization_api_exists`, `test_edited_text_cannot_retain_supported_status`, `test_finalize_audit_uses_note_finalize` | synthetic actor identities (G1) |
| source linkage/provenance for AI-generated clinical content | EVIDENCED_SYNTHETIC | `test_all_five_support_states_first_class`, `test_unsupported_fact_remains_unsupported`, `test_invented_fact_cannot_become_source_backed` | no real generation model |
| no automatic training or model-improvement upload from local clinical content | EVIDENCED_SYNTHETIC | `test_no_workspace_data_class_can_flow_into_research_core`, `test_no_hidden_egress_across_the_full_lifecycle` | none |
| fail-closed behavior when a required local model, evidence source, validator, or security capability is unavailable | EVIDENCED_SYNTHETIC | `test_missing_optional_deps_fail_cleanly`, `test_missing_snapshot_fails_closed`, `test_a_store_without_an_active_key_fails_closed`, `test_platform_provider_is_unavailable_and_fails_closed_before_any_file` | none |

Additional safeguards that bear on PHI readiness:

| Safeguard | Status | Evidence |
|---|---|---|
| consent gate before capture | EVIDENCED_SYNTHETIC | `test_consent_required_before_simulated_capture`; the vocabulary is synthetic-only consent (CW-017) |
| failure text carries no payload or key material | EVIDENCED_SYNTHETIC | `test_failure_messages_never_carry_payload_or_key_material` |
| every Workspace data class refused toward Research Core | EVIDENCED_SYNTHETIC | `test_no_workspace_data_class_can_flow_into_research_core`; derived-sensitivity inheritance (`data_security.md` section 4) is not separately tested |

Threat-model domains (`data_security.md` sections 5 to 18):

| Domain | Status | Evidence | Blocking risks |
|---|---|---|---|
| Encryption and key lifecycle | ARCHITECTURE_BLOCKED | section 4 encryption/key tests; no platform key provider | R2, R1, R5 |
| Identity, tenancy, and authorization | PARTIAL | workspace ownership and cross-workspace refusal: `test_two_workspaces_are_isolated_in_separate_stores`, `test_a_store_file_cannot_be_adopted_as_another_workspace`, `test_cross_workspace_fetch_refused`, `test_cross_workspace_traversal_fails`. No authorization, and actor identities are caller-supplied | G1 |
| Recording and audio lifecycle | PARTIAL | simulated capture only: `test_consent_required_before_simulated_capture`, `test_consent_revocation_forces_stop`, `test_writes_after_stop_fail_closed`, `test_crash_between_chunk_and_state_commits_detected`, `test_delete_cascade_removes_session_and_chunks`. No microphone or device path and no visible recording-state UI exist | G6 |
| Transcript and note integrity | EVIDENCED_SYNTHETIC | `test_edit_forces_draft_and_invalidates_support`, `test_edited_text_cannot_retain_supported_status`, `test_invented_fact_cannot_become_source_backed` | synthetic actors (G1) |
| Prompt injection and untrusted content | EVIDENCED_SYNTHETIC | section 4 prompt-injection row; `test_injection_content_stays_inert_data` | no real generation model |
| Model isolation | EVIDENCED_SYNTHETIC | section 4 model-isolation row | ASR only |
| Connector security | EVIDENCED_SYNTHETIC | section 4 connector row; TLS and identity validation are not applicable because no network transport exists | fixture-only |
| FHIR import/export threats | EVIDENCED_SYNTHETIC | `test_workspace_patient_binding_checked`, `test_security_labels_retained_where_present`, `test_cross_workspace_reference_refused`, `test_export_path_escape_refused`, `test_oversized_payload_refused_at_parse_stage`, `test_malformed_and_unsupported_fail_explicitly` | structural validity only; R4; G8 |
| Evidence retrieval threats | EVIDENCED_SYNTHETIC | `test_provenance_tampering_detected`, `test_replay_after_member_deletion_fails_closed`, `test_no_network_remote_model_or_write_capability`, `test_contradicted_verdict_dominates_support` | lexical ranking only |
| Graph threats | EVIDENCED_SYNTHETIC | `test_edge_requires_epistemic_and_source_refs`, `test_deleted_source_makes_edge_stale`, `test_malicious_edge_text_grants_no_authority`, `test_mixed_workspace_path_refused` | none |
| Plugin and supply-chain threats | EVIDENCED_SYNTHETIC | no plugin loader exists; `test_workspace_boundary_guard_rejects_dynamic_import`, `test_workspace_boundary_guard_rejects_nonallowlisted_stdlib`, `test_the_admitted_runtime_dependency_surface_is_pinned_and_permissive` | self-review only (R7) |
| Backup and restore | EVIDENCED_SYNTHETIC | section 4 backup/restore row | R1 |
| Deletion | EVIDENCED_SYNTHETIC | section 4 deletion row | no cryptographic erasure |
| Logging and diagnostics | EVIDENCED_SYNTHETIC | the package cannot import `logging` (boundary guard allowlist); `test_failure_messages_never_carry_payload_or_key_material`, `test_audit_events_carry_no_clinical_text`, `test_lifecycle_audit_events_carry_no_payload_content` | no security-failure record (G4) |

## 6. Unresolved risk register

### 6.1 CW-019 residual risks (severities exactly as in the CW-019 review record)

| ID | Severity | Risk | State for PHI readiness |
|---|---|---|---|
| R1 | MEDIUM | whole-store rollback to an older valid sealed copy remains undetected; detection needs a trusted monotonic counter outside the store | OPEN, blocking |
| R2 | MEDIUM | no platform protected-key provider; the production resolver fails closed, so no production or PHI store can open | ARCHITECTURE_BLOCKED |
| R3 | MEDIUM | unsealed legacy state (schema 1 or 2, genuine or seal-stripped) cannot be verified; an acknowledged migration seals it as found (F11 is mitigated, not fixed) | OPEN |
| R4 | LOW | lexical export containment: links are not resolved because the package has no filesystem capability | OPEN |
| R5 | LOW | plaintext metadata (identities, types, revisions, salts, tombstones, journal manifests) stays readable in a copied store; the seal protects integrity, not confidentiality | OPEN |
| R6 | LOW | O(n) write cost: the seal and audit verification are linear in store size per write | OPEN |
| R7 | MEDIUM | no human independent security review | OPEN, blocking |
| R8 | LOW | pure-read window: `get_object`, `key_states`, `tombstones` and `journal_entries` can return tampered plaintext metadata between a mid-session tamper and the next verified write, snapshot or open | OPEN |

### 6.2 PHI-readiness gaps found by this packet

| ID | Severity for PHI readiness | Gap | Evidence |
|---|---|---|---|
| G1 | HIGH | no user authentication and no patient/encounter access control. ADR-0038 requires "encounter/patient access controls" before any PHI-capable implementation; actor identities are caller-supplied synthetic strings | no authentication or authorization module in `apps/workspace/src/medscale_workspace/` |
| G2 | HIGH | reads are never audited. `AuditEventType.PATIENT_READ` and `AuditEventType.ENCOUNTER_READ` are declared but have no emission site, while ADR-0038 requires immutable audit events for reads | binding test `test_declared_but_unemitted_audit_event_types_match_the_packet` |
| G3 | MEDIUM | session events are never audited. `LOGIN`, `WORKSPACE_OPEN` and `WORKSPACE_CLOSE` are declared but have no emission site | same binding test |
| G4 | MEDIUM | security failures are never audited. `SECURITY_FAILURE` is declared but has no emission site; seal, AEAD and backflow refusals raise exceptions without an audit record, and no external tamper-evident log exists | same binding test; [incident_response.md](incident_response.md) section 1 |
| G5 | HIGH | no accepted ADR scopes any PHI use (environment, users, data class, connectors, retention, runtime, stop conditions) | ADR list `docs/adr/`; ADR-0038 `PHI_INGESTION = NOT_AUTHORIZED` |
| G6 | MEDIUM | no privacy or retention policy for real data; one synthetic retention class with no time-based expiry | `RETENTION_CLASS = "session-scoped"`, `RETENTION_VERSION = 1` in `encounter.py` |
| G7 | LOW | incident response has never been drilled; there is no on-call, paging, breach-notification or clinical-safety reporting process | [incident_response.md](incident_response.md) section 4 |
| G8 | LOW | export audit is untested and inconsistent: FHIR export staging emits an `export` audit event that no test asserts, and dataset export staging is recorded only as `object_create` | `apps/workspace/src/medscale_workspace/fhir_r4.py`, `apps/workspace/src/medscale_workspace/dataset.py` |

Also declared but never emitted are `TRANSCRIPT_EDIT`, `TRANSCRIPT_DELETE` and `CONNECTOR_WRITE`. No transcript-edit path exists and connector writes are mechanically disabled, so these three are recorded as consistent with the current scope rather than as gaps. The binding test checks the whole declared-but-unemitted set, so this record goes stale loudly if emission changes.

### 6.3 Limitations carried from earlier closeouts (unchanged unless stated)

```text
CW-002  secure_delete=ON is defense in depth only, never cryptographic erasure (A1.11); single-writer store
CW-003  no database-level write-once trigger; append cost grows with the trail (tail truncation now sealed, CW-019)
CW-004  lexical containment only; the guard performs no I/O (= R4)
CW-005  audio payloads capped at 65536 bytes and 4096 chunks; no microphone, device, streaming or codec path;
        session-scoped retention v1 only
CW-006  no WER, accuracy, language-quality or clinical-quality claim for ASR
CW-007  no real generation model; synthetic placeholder identities only; no generation-quality claim
CW-008  FINALIZED is terminal with no addendum path; synthetic human actor identities
CW-009  lexical-overlap ranking only; no web, remote or connector retrieval
CW-010  link stances are caller-supplied; no textual entailment
CW-011  epistemic states are caller-supplied; bounded graph views and path depth
CW-012  link kinds are caller-supplied; frozen derived state
CW-013  FHIR structural validity only; no terminology validation; no EHR, SMART-on-FHIR or production endpoint
CW-014  fixture-only connectors; no real endpoint, credential or network policy
CW-015  analytics derive from stored review revisions only
CW-016  no patient path into Research Core views; views pin caller-supplied identities only
CW-017  synthetic-only consent, rights and reference-only de-identification vocabularies; staging records a
        manifest only
CW-018  root-secret loss loses both store and backup keys; backups are not expired by the package; disk space is
        declared by the caller
all     no multi-writer merge; bounded inputs are refused, not truncated; Issue #464 typing and version items separate
```

## 7. Data-flow diagram (implementation, not intent)

```text
                      explicit boolean export request only
  +--------------------+  (dataset.py manifest; no file write) +-----------------------+
  | W  Workspace store |-------------------------------------->| X  export quarantine  |
  |  SQLite, AES-256-GCM|                                       |  manifest records only|
  |  rows, HMAC seal   |                                        +-----------+-----------+
  +--+------+------+---+                                                    |
     ^      ^      |                                                        x  automatic admission REFUSED
     |      |      x  W -> R direct flow REFUSED (nobackflow.py)            v
     |      |      +-------------------------------------------------> [ R  Research Core ]
     |      |                                                               |
     |      +---- versioned read-only interfaces, pinned identities --------+
     |            (research_view.py; no patient context passed)
     |
     +---- E  connectors: fixture:// transports only, read-only, writes disabled (connector.py)
     +---- P  local ASR: pinned Whisper artifact, local_files_only, no remote code (asr.py)

  hidden telemetry / sockets / DNS / subprocess / urlopen: REFUSED at runtime and absent statically
```

| Edge | Implemented behaviour | Evidence |
|---|---|---|
| W -> R | refused for every data class | `test_no_workspace_data_class_can_flow_into_research_core`, `test_direct_workspace_to_research_core_write_fails_closed` |
| W -> X | explicit export request only; manifest only | `test_staging_an_export_into_a_research_root_is_refused_even_when_deidentified`, `test_hostile_export_paths_are_refused` |
| X -> R | no automatic admission | `test_no_workspace_data_class_can_flow_into_research_core` |
| R -> W | versioned, pinned, read-only; no patient context | `test_descriptor_admission_is_versioned`, `test_research_core_is_read_only_by_default`, `test_no_patient_context_can_be_supplied` |
| E -> W | fixture-only read | `test_destination_allowlist_enforced`, `test_writes_mechanically_disabled` |
| P <-> W | local-only model runtime | `test_trust_flags_enforced`, `test_revision_mismatch_fails_closed` |
| W -> hidden egress | refused | `test_no_hidden_egress_across_the_full_lifecycle` |

## 8. Runtime and model identities

```text
ASR MODEL_ID          openai/whisper-large-v3-turbo
ASR MODEL_REVISION    41f01f3fe87f28c78e2fbf8b568835947dd65ed9 (immutable; ADR-0040)
ASR RUNTIME           transformers 5.16.1, torch 2.13.0 (optional extra asr-local)
ASR FLAGS             trust_remote_code = False, local_files_only = True (enforced)
GENERATION MODEL      NONE admitted -- draft engine uses synthetic placeholder identities only
AEAD                  cryptography==50.0.1 (AES-256-GCM, HKDF-SHA-256, HMAC-SHA-256)
PYTHON                CI py3.11 and py3.12
```

## 9. Prerequisites before any CW-021 authorization could be considered

These prerequisites are necessary, not sufficient. Meeting them would still grant nothing: CW-021 requires the separate explicit Founder and governance authorization defined in `tasks.md`.

1. An accepted PHI-scope ADR that names the environment, users, data class, connectors, retention, runtime and stop conditions (G5).
2. A platform protected-key provider, designed and ratified under ADR-0039 A1.7 and A1.8 (R2).
3. User authentication plus patient/encounter access control (G1).
4. Read, session, export and security-failure audit, including an external tamper-evident record (G2, G3, G4, G8).
5. A human independent security review and a penetration assessment appropriate to the named deployment (R7).
6. A decision on whole-store rollback: an external monotonic anchor, or an explicitly accepted residual (R1).
7. A privacy and retention policy for real data (G6).
8. A drilled incident-response process, with breach and clinical-safety reporting paths (G7).
9. Separate model ADRs and qualification for any generation model that would touch real data.

## 10. Non-grants

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
PHI_READINESS = NOT_READY
PRODUCTION_READINESS = NOT_READY
CLINICAL_PILOT_AUTHORIZATION = NOT_GRANTED (CW-021 NOT AUTHORIZED)
```
