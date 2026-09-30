# Clinical Workspace V1 — Incident Response Procedure

- **Status:** CW-020 incident-response procedure (synthetic-only)
- **Date:** 2026-09-30
- **Parent:** [Clinical Workspace V1](README.md)
- **Activation:** [Issue #526](https://github.com/TheHalfMoon/MESC/issues/526)
- **Contracts:** [data security and threat model](data_security.md), [recovery runbook](recovery_runbook.md), [CW-019 security review](cw-019-security-review.md), [task ledger](tasks.md) CW-020
- **Authority:** none. This procedure covers synthetic stores only. It grants no PHI, production, network, model, EHR-write, external-write, training, paid-compute or research-admission authority, and it is **not** a clinical incident, breach-notification or regulatory reporting process.

This procedure maps each security signal the Workspace package actually raises to a response. Every error class named below exists in `apps/workspace/src/medscale_workspace/errors.py`. `tests/test_clinical_workspace_phi_readiness_packet_v1.py` checks that each named class exists, and that every class in the required incident set is covered here. Recovery steps refer to the [recovery runbook](recovery_runbook.md) and do not restate it.

## 1. Standing rules for every incident

1. **Stop writing.** Do not call any mutating store or lifecycle entry point on the affected store until the incident is classified.
2. **Do not repair in place.** Never reseal, edit, or hand-migrate a store file that raised an integrity signal. Never bypass a fail-closed refusal.
3. **Preserve the evidence.** Keep a copy of the affected store root and any backup bytes involved, byte for byte, separate from the live root.
4. **Record outside the store.** The Workspace audit trail lives inside the store, so it cannot be trusted to record its own compromise. Security failures are **not** written to the audit trail today (packet gap G4). Record the incident in the operator's own log, with the exception class, the time, and the store and workspace identities. Record no payload content.
5. **Synthetic only.** If an incident suggests that real patient data entered a synthetic store (incident I11), stop entirely and escalate to the Founder. No PHI handling authority exists.

## 2. Incident classes

| ID | Signal (exception class) | Meaning | Containment | Recovery | Residual limit |
|---|---|---|---|---|---|
| I1 | `StoreSealError` | the store was modified outside the store API, or opened with the wrong root secret | stop writing; preserve the file; confirm the root secret | [runbook 5.0](recovery_runbook.md): if the secret is correct, treat the store as compromised and recover from a verified backup into a fresh live root (runbook section 3) | a whole-store rollback to an older sealed copy raises nothing (R1); see I10 |
| I2 | `EnvelopeAuthenticationError`, `EnvelopeFormatError` | an object envelope failed AEAD authentication or its format check | stop writing; preserve the file | recover from a verified backup (runbook section 3) | none beyond R1 |
| I3 | `AuditChainError`, `AuditReplayError` | the audit chain is broken, reordered, or replayed | stop writing; keep the retained external head anchor | compare against the last backup manifest's audit head; recover from a verified backup | tail truncation by a store-file writer is caught by the seal (I1), not by the chain alone |
| I4 | `BackupIntegrityError`, `BackupFormatError` | a backup was tampered with, truncated, forged, or is from another workspace | do not restore it; keep the bytes | use an older verified backup; call `open_backup` to check candidates without restoring | backups do not expire themselves; expiring them is an operator duty |
| I5 | `KeyProviderUnavailableError`, `KeyMaterialUnavailableError` | no key provider or unusable key material (for example the platform provider, or a wrong-size key) | do not create a new store to "get unstuck" | restore the correct root secret from its protected storage | **root-secret loss is data loss** (runbook section 1); no platform key provider exists (R2) |
| I6 | `ResearchBackflowError`, `TelemetryBackflowError`, `SecretEgressError`, `UndeclaredFlowError`, `ExportAdmissionError`, `UnavailableAuthorityError`, `ExportBoundaryError` | a flow toward Research Core, telemetry, secret egress, an unauthorized capability (network, model, EHR write), or outside the export boundary was attempted and refused | treat the calling code path as suspect; keep the refusal record | fix the caller; the refusal already prevented the flow | refusals are raised, not audited (G4) |
| I7 | `StoreMigrationRequiredError` on an unexpected schema-1 or schema-2 store | an unsealed legacy store, genuine or produced by stripping a seal (F11) | do not pass `acknowledge_unsealed_legacy_state=True` for a store that was ever sealed | recover from a verified backup; acknowledge only a store known never to have been sealed ([runbook 5.1](recovery_runbook.md)) | nothing inside the file proves it was never sealed (R3) |
| I8 | `MigrationPreflightError`, `MigrationValidationError`, `MigrationError` | a migration was refused before mutation, or failed validation | leave the journal as it is | [runbook 5.2](recovery_runbook.md): resume or roll back from the protected snapshot | none beyond R1 |
| I9 | `StoreRoleError`, `RestoreConflictError` | a quarantine store was opened as live, or a promotion or rollback conflicts with newer or divergent state | do not force the operation | investigate the divergence; [runbook sections 3 and 4](recovery_runbook.md) | untracked absence needs operator investigation |
| I10 | none (no signal) | a **suspected** whole-store rollback: the store opens, but its audit head is older than a head retained outside the store | stop writing | compare the audit head with the last backup manifest and any externally retained anchor; recover from the newest verified backup | undetectable by the package (R1); detection depends entirely on anchors held outside the store |
| I11 | none (operator observation) | real patient data, or anything that could be PHI, appears in a synthetic store or fixture | **stop entirely**; do not copy, back up, export or delete ad hoc | escalate to the Founder; no PHI authority exists | this procedure is not a breach process |
| I12 | `AsrManifestError`, `AsrRevisionError`, `AsrModelUnavailableError` | the local ASR artifact does not match its ratified identity, or is missing | do not substitute another model or allow a download | restore the pinned artifact (ADR-0040) | no network fallback exists by design |

## 3. After every incident

- Record the root cause, the exception class and the recovery taken in the operator log, and record an issue in the repository if code or procedure changed.
- If the root cause is a defect, fix it forward under an activated unit with a failing-before regression test.
- Update this procedure when a new signal class is added to `errors.py`.

## 4. What this procedure does not provide

- no human on-call rota, paging, drills or tabletop exercises have been performed (packet gap G7);
- no breach-notification, regulatory, or clinical-safety reporting process (none is authorized, because no PHI or clinical use is authorized);
- no automatic security-failure audit record (G4) and no external tamper-evident log;
- no detection of whole-store rollback (R1).

## 5. Non-grants

```text
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
CLINICAL_INCIDENT_PROCESS = NOT_PROVIDED
BREACH_NOTIFICATION_PROCESS = NOT_PROVIDED
```
