# Clinical Workspace V1 — Recovery Runbook

- **Status:** CW-018 operational runbook (synthetic-only)
- **Date:** 2026-09-29
- **Parent:** [Clinical Workspace V1](README.md)
- **Contracts:** [migration and recovery](migration_recovery.md), [data security](data_security.md), [ADR-0039 ratification](adr-0039-founder-ratification.md), [task ledger](tasks.md) CW-018
- **Authority:** synthetic fixtures only; no PHI, real-data migration, production upgrade, network, cloud backup target, or external write

This runbook covers each recovery situation the CW-018 lifecycle code handles. Every entry point is in `apps/workspace/src/medscale_workspace/lifecycle.py` or on `WorkspaceStore` in `storage.py`. The Workspace package has no filesystem capability, so the operator (the calling application) decides where backup bytes and store roots live. Keep quarantine and recovery roots separate from the live root.

## 1. What is protected, and what is not

| State | Protection | Recovery path |
|---|---|---|
| Authoritative object revisions | AES-256-GCM rows under the active key | backup, then quarantine restore, then promotion or rollback |
| Audit chain | digest-linked, append-only | never rewritten; survives rollback; verified on every lifecycle step |
| Deletions | tombstone in the same transaction as the delete | honoured by promotion and rollback; never resurrected |
| Derived graph, view, dataset and export records | stale on read | `reconcile_deletions`, then rebuild from bound sources |
| Key material | never persisted by the store, never in a backup | the root secret held by the platform key provider |

Limits that are recorded, not hidden:

- **Root secret loss means data loss.** Store keys and backup keys both derive from the root secret (HKDF-SHA-256, with distinct labels and salts). A backup cannot be opened without the root secret it was made under. Keep the root secret recoverable in its own protected storage.
- AES-256-GCM does not detect a whole-store rollback made with a valid key (A1.5). Rollback detection comes from the audit-chain ancestry check at promotion and rollback, and from an anchored head digest held outside the store.
- `secure_delete=ON` is defense in depth only and is not cryptographic erasure (A1.11). Deleting a revision does not erase copies inside backups the operator still holds; expiring backups is an operator duty.
- Free disk space cannot be measured inside the package. The caller declares it to preflight, which refuses anything below twice the stored envelope size.
- Journal state, store role, tombstone reasons and key-version state stay readable plaintext (A1.10). Since CW-019 (workspace schema 3), a keyed integrity seal covering them and every object row is verified on every open. An edit made outside the store API fails with `StoreSealError`. Replacing the whole store with an older, internally consistent copy still opens (A1.5); the backup manifest's audit anchor and the promotion/rollback ancestry checks are the only mitigations.

## 2. Routine protected backup

1. Open the live store in normal mode and call `create_backup(store, key_provider, actor_id=..., occurred_at=...)`.
2. Store the returned bytes where the operator chooses. They contain a canonical plaintext manifest (identities, types, revisions, content digests, tombstones, audit head, body digest) and one AES-256-GCM envelope. They contain no payload plaintext and no key material.
3. A `backup` audit event records the backup id, object count, tombstone count and body digest.
4. To check a backup without restoring it, call `open_backup(data, key_provider, workspace_id=...)`. It authenticates the manifest as associated data, decrypts, and reconciles every digest.

## 3. Disaster recovery (live store lost or unusable)

1. Create a new, empty live store root.
2. Call `restore_backup_to_quarantine(data, key_provider, workspace_id=..., quarantine_root=..., application_version=...)`.
   - It refuses a foreign workspace, a newer or older schema, an unsupported format, a wrong root secret, and any tampering.
   - It loads only into an empty store recorded as `QUARANTINE`. Normal live mode refuses to open that store, and quarantine stores refuse ordinary writes.
   - It re-reads every restored object, verifies the audit chain against the manifest's head anchor, and runs the SQLite integrity checks.
3. Open the empty live store normally and the quarantine store with `role=StoreRole.QUARANTINE`, then call `promote_quarantine(live, quarantine, actor_id=..., occurred_at=...)`.
4. Promotion adds only state the live store lacks. It is refused when the live store holds anything the backup does not (newer or divergent state), or when a shared revision differs. Revisions the live store has tombstoned are skipped. A `restore` audit event (`mode=promote`) commits with the added objects.
5. Run `reconcile_deletions` if derived records may be stale, then discard the quarantine root.

## 4. State rollback from a protected snapshot

Use this when a change must be undone before any external side effect. No external side effect is authorized in V1.

1. Restore the snapshot backup into quarantine as in section 3, step 2.
2. Call `rollback_to_quarantine(live, quarantine, actor_id=..., occurred_at=..., journal_migration_id=...)`.
3. Preconditions: the snapshot's audit chain must be an ancestor of the live chain. A newer or forked snapshot is refused.
4. Effects, in one transaction with a `restore` audit event (`mode=rollback`):
   - revisions created after the snapshot are discarded, with tombstone reason `ROLLBACK_DISCARDED`;
   - revisions removed by a migration are returned;
   - revisions the user deleted stay deleted;
   - all audit events are kept.
5. A snapshot revision that is absent from the live store without a tombstone is an untracked absence. Rollback refuses it and an operator must investigate.

## 5. Migrations

Every state-changing migration has a manifest (contract section 5) and runs the eleven preflight checks (section 6) before any mutation: exclusive lock, workspace identity, source versions, database and audit integrity, key availability, declared space, no active encounter capture, snapshot integrity when the rollback class needs it, object inventory, no external side effects, and failure before mutation.

### 5.0 Integrity seal failure

- Symptom: open raises `StoreSealError`, which means the store was modified outside the store API or opened with the wrong root secret.
- Action: do not repair the store in place, and do not reseal it. Confirm that the correct root secret is in use. If it is, treat the store as compromised: recover from a verified backup using section 3 into a fresh live root, then investigate how the file was modified.

### 5.1 Schema-1 or schema-2 store (M1 additive, 1 to 2 to 3)

- Symptom: normal open raises `StoreMigrationRequiredError`.
- First decide whether the store could ever have been at schema 3. If it could, it presents as legacy only because its seal was stripped, so treat it as compromised and recover from a verified backup (section 3). Migrate only a store known never to have been sealed, and pass `acknowledge_unsealed_legacy_state=True`: the first seal is written over whatever the store holds.
- Action: `migrate_schema_to_current(store_root=..., workspace_id=..., key_provider=..., source_application_version=..., target_application_version=..., available_bytes=..., actor_id=..., occurred_at=...)`.
- Each step is one SQLite transaction. Step 1 to 2 adds the tables, store role, version metadata, migration log row, completed journal row and `migration` audit event. Step 2 to 3 (CW-019) adds the seal salt and version metadata, its own log and journal rows and audit event, and writes the first integrity seal. An interruption leaves the store at the last completed schema, and the migration is simply rerun.
- Rollback class: forward repair. An application that reads only schema 1 refuses a schema-2 store rather than guessing.

### 5.2 Semantic migration (M2) and checkpoint resume

- Start: `begin_semantic_migration(store, manifest, transform, key_provider, available_bytes=..., snapshot=..., actor_id=..., occurred_at=...)` with a `SNAPSHOT_ROLLBACK` manifest naming a fresh backup.
- Each object step (tombstone the old revision, write the new revision, advance the checkpoint) is one transaction, and the journal records old/new digest evidence.
- After an interruption (process death, power loss): normal open raises `StoreMigrationRequiredError`. Open with `WorkspaceStore.open_for_maintenance(...)` and call `resume_semantic_migration(store, migration_id, transform, actor_id=..., occurred_at=...)`. Resume restarts at the first uncommitted inventory position and produces the same result as an uninterrupted run.
- Journal states: `PREPARED`, `MUTATING`, `VALIDATING`, `SWITCHED`, then `COMPLETED`. A crash after `SWITCHED` resumes straight to completion.
- If validation fails, the journal enters `FAILED_REQUIRES_INTERVENTION` and normal open is refused. Recover with section 4, passing `journal_migration_id`; the journal becomes `ROLLED_BACK`.

### 5.3 Downgrade

- Supported downgrade targets are none. A newer store schema is refused in both normal and maintenance mode, and a backup from a newer schema is refused at restore. Nothing is parsed on a best-effort basis.

## 6. Key rotation (M3) and interrupted rotation

- Rotate with `rotate_workspace_key(store, new_key_version=..., batch_size=..., actor_id=..., occurred_at=...)`.
- The A1.6 state machine (`ACTIVE`, `ROTATING`, `RETIRING`, `RETIRED`) is persisted. After an interruption at any boundary, rerun the same call with the same target version: it resumes, re-encrypts the remaining rows, finalizes, and retires every emptied key.
- Retired keys cannot decrypt or write. `key_rotation` audit events record the begin and the completion.
- A backup made before a rotation still restores after it, because backup keys are separate from store keys.

## 7. Deletion reconciliation

- After deleting a source, call `reconcile_deletions(store, actor_id=..., occurred_at=...)`. It removes graph edges, nodes and views, dataset collections, and export manifests that their owning module reports as stale. Each removal goes through that module's audited delete path.
- Rebuild projections from the surviving bound sources. Rebuilds are deterministic, so an unchanged member set yields the same view identity.

## 8. Non-grants

This runbook authorizes nothing beyond synthetic local operation:

```text
REAL_DATA_MIGRATION = NOT_AUTHORIZED
PHI_IMPORT = NOT_AUTHORIZED
PRODUCTION_UPGRADE = NOT_AUTHORIZED
CLOUD_OR_REMOTE_BACKUP_TARGET = NOT_AUTHORIZED
EHR_SIDE_EFFECT = NOT_AUTHORIZED
RESEARCH_DATA_ADMISSION = NOT_AUTHORIZED
```
