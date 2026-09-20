# Clinical Workspace V1 — Migration, Compatibility, and Recovery Contract

- **Status:** Proposed planning contract
- **Date:** 2026-09-20
- **Parent:** [Clinical Workspace V1](README.md)
- **Security model:** [data_security.md](data_security.md)
- **Task ledger:** [tasks.md](tasks.md)
- **Authority:** planning only; no PHI or production-clinical authority

## 1. Objective

A local-first clinical workspace must survive software upgrades, schema changes, key rotation, index/graph rebuilds, model/runtime changes, and interrupted migrations without losing source data or silently changing clinical meaning.

Migration is therefore a governed state transition, not an incidental database library feature.

The invariant is:

```text
SOURCE CLINICAL STATE MUST REMAIN IDENTIFIABLE, RECOVERABLE, AND AUDITABLE
ACROSS EVERY SUPPORTED MIGRATION.
```

Derived state may be rebuilt. Source state may not be silently reinterpreted.

## 2. Version identities

Every persisted Workspace installation records at minimum:

```text
workspace_schema_version
object_schema_versions
policy_version
encryption_format_version
key_version
graph_projection_version
search_index_version
application_version
research_interface_version
connector_schema_versions
```

Model/runtime identity belongs to generated artifacts, not to the global workspace schema alone.

A migration plan must name the exact source and target version tuple.

## 3. State categories

### Authoritative source state

Examples:
- imported FHIR/resource revisions;
- transcript source revisions;
- reviewed/finalized note revisions;
- human edits/assertions;
- consent/policy records;
- source documents;
- audit/provenance records.

Rule:
**preserve exactly or fail the migration.**

### Derived rebuildable state

Examples:
- search indexes;
- embeddings;
- graph projections;
- cached summaries;
- thumbnails;
- model-derived convenience views.

Rule:
**may be discarded and rebuilt from bound source revisions.**

### Secret/key state

Examples:
- wrapped DEKs;
- connector credentials;
- root-key references.

Rule:
**migrate only under explicit key-management procedure; never copy to plaintext fallback.**

### External state

Examples:
- EHR resources;
- remote evidence provider state;
- remote connector cursors.

Rule:
**do not assume rollback is possible. Reconcile against external version/idempotency identity.**

## 4. Migration classes

### M0 — application-only

No persisted schema/format change.

Requirements:
- compatibility check;
- no database mutation.

### M1 — additive schema

Adds optional tables/fields/indexes without changing existing interpretation.

Requirements:
- backward-safe read strategy where supported;
- index creation resumable;
- no source-value rewrite unless separately classified.

### M2 — semantic schema migration

Changes representation or meaning of persisted objects.

Requirements:
- explicit migration manifest;
- object-by-object old/new digest evidence;
- reversible mapping or pre-migration protected backup;
- semantic validation;
- manual review for ambiguous transformations.

### M3 — encryption/key format migration

Changes encryption envelope, key version, or protected storage layout.

Requirements:
- separate security review;
- crash-safe resumability;
- old key retained only as long as required for verified completion/rollback;
- no mixed untracked encryption state.

### M4 — projection/index rebuild

Changes graph/search/embedding format only.

Requirements:
- source bindings unchanged;
- old projection may be discarded after verified rebuild;
- product indicates degraded/rebuilding state instead of presenting stale results.

### M5 — connector/external contract migration

Changes API versions, resource mappings, cursor formats, or write semantics.

Requirements:
- separate connector compatibility evidence;
- read-only qualification first;
- external-state reconciliation;
- no silent destructive conversion.

## 5. Migration manifest

Every state-changing migration must produce a manifest containing:

```text
migration_id
migration_class
source_app_version
target_app_version
source_workspace_schema_version
target_workspace_schema_version
source_policy_version
target_policy_version
source_encryption_format_version
target_encryption_format_version
required_key_versions[]
affected_object_types[]
affected_projection_types[]
preconditions[]
expected_object_counts
pre_migration_snapshot_identity
steps[]
postconditions[]
rollback_strategy
irreversible_operations[]
external_side_effects[]
tool_version
started_at
completed_at
result
```

The manifest contains identities/counts, not sensitive payload content.

## 6. Preflight

Before mutation:

1. acquire exclusive migration lock;
2. verify workspace identity;
3. verify application/source versions;
4. verify database/integrity checks;
5. verify key availability;
6. verify sufficient disk space for migration + protected backup/temp state;
7. verify no active encounter capture/write transaction;
8. verify backup/snapshot integrity when required;
9. inventory authoritative and derived object counts;
10. classify any external side effects;
11. fail before mutation if a prerequisite is missing.

A migration must never begin simply because the application version changed.

## 7. Write strategy

Prefer:

```text
prepare new state
-> validate new state
-> atomically switch active identity/pointer
-> retain bounded rollback material
-> asynchronously rebuild non-critical derived state
-> verify
-> expire rollback material under policy
```

Avoid in-place destructive rewriting of the only authoritative copy.

Where the storage engine cannot support atomic switching, the implementation ADR must define an equivalent journal/checkpoint protocol.

## 8. Crash recovery

Every migration step is:
- idempotent; or
- journaled with a deterministic resume/rollback state.

On restart the system must identify:

```text
NOT_STARTED
PREPARED
MUTATING
VALIDATING
SWITCHED
ROLLING_BACK
COMPLETED
FAILED_REQUIRES_INTERVENTION
```

The application must not open a partially migrated workspace in normal mode.

## 9. Validation

Post-migration validation includes:

- authoritative object count reconciliation;
- content/source digest reconciliation where representation is unchanged;
- semantic validation where representation changed;
- audit/provenance chain readability;
- security label retention;
- consent/policy readability;
- patient/encounter/workspace foreign-key/reference integrity;
- encrypted object decrypt/re-encrypt checks using the intended key versions;
- graph/index projection version;
- Research Core no-backflow guard;
- backup restore smoke test when migration changed storage/encryption format.

A successful process exit alone is not migration evidence.

## 10. Rollback

Rollback classes:

### Application rollback without schema rollback

Allowed only when the prior application declares compatibility with the current workspace format.

### State rollback from protected snapshot

Use when target migration validation fails before external irreversible side effects.

Requirements:
- restore into quarantine;
- validate snapshot identity;
- verify key availability;
- reconcile audit/migration events;
- atomically return to prior state only after validation.

### Forward repair

Required when:
- an external side effect cannot safely be undone;
- old application cannot read the new format;
- security policy forbids restoring old vulnerable state.

The migration manifest must say which rollback class applies before migration starts.

## 11. Downgrade policy

Downgrade is **not assumed**.

Each application release declares:

```text
minimum_readable_workspace_schema
maximum_readable_workspace_schema
supported_downgrade_targets[]
```

If unsupported:
- application refuses to open the workspace in write mode;
- user receives a clear compatibility state;
- no best-effort parsing.

## 12. Graph/index migration

Graph, search, and embedding state is derived.

Rules:
- version each projection;
- bind projection to exact source revision set;
- never migrate an inferred edge by dropping its epistemic state;
- prefer rebuild over opaque transform when deterministic rebuild is available;
- stale projection is not served as current during rebuild;
- deletion tombstones/source deletion must be applied before projection becomes active.

CW-011 is therefore a direct dependency of CW-018.

## 13. FHIR semantic migration

FHIR version/profile changes may alter meaning.

Rules:
- no automatic FHIR R4 -> another major-version semantic conversion without separate adapter/version decision;
- retain original imported bytes/identity where policy allows;
- transformed resource is a new derived/import-normalized revision with provenance;
- terminology/profile changes do not rewrite historical validation state;
- failed revalidation is visible.

## 14. Model/runtime migration

Changing a local model/runtime does not rewrite old generated content.

Old artifact:
- retains original model/revision/runtime/template/input identities.

New generation:
- creates a new artifact revision.

A model upgrade cannot silently regenerate/finalize all historical notes.

## 15. Research Core interface compatibility

Workspace may consume a versioned Research Core interface.

Rules:
- bind Workspace release to a declared compatible Research interface range;
- Research Core upgrade cannot migrate Workspace patient data;
- incompatible Research interface fails at boundary;
- MRL/research evidence is never rewritten to satisfy Workspace compatibility.

## 16. Connector migration

For read connectors:
- new connector version proves mapping compatibility with fixture snapshots.

For future write connectors:
- migration requires explicit external-side-effect analysis;
- idempotency keys/reconciliation IDs preserved;
- pending writes drained or frozen before upgrade;
- no replay of a previously completed clinical write solely because local schema changed.

## 17. Backup migration

Backup format is versioned separately.

A newer application may:
- restore a supported older backup into quarantine and migrate forward; or
- reject unsupported backup explicitly.

It must not mutate the only backup in place.

## 18. Migration audit

Audit records include:
- migration start/end;
- actor/process identity;
- source/target versions;
- result;
- rollback/forward-repair state;
- counts/digests sufficient for verification;
- no patient payload.

Migration audit records survive rollback as security/operational metadata where policy permits.

## 19. Required adversarial tests

At minimum:

| Scenario | Required result |
|---|---|
| power loss mid-migration | deterministic resume or rollback state |
| disk fills during prepare | no active-state corruption |
| wrong key version | fail before destructive mutation |
| corrupted backup | restore rejected |
| object count mismatch | migration not activated |
| graph rebuild fails | source remains intact; graph marked unavailable/stale |
| stale search index | not served as current |
| old app opens newer unsupported schema | read/write refused |
| external connector contract changes | compatibility failure, no hidden write |
| migration tries to copy Workspace state into Research Core | no-backflow guard fails closed |
| consent/security labels lost in transform | postcondition fails |
| crash after atomic switch before cleanup | new state validates; cleanup resumes safely |
| rollback would resurrect deleted sensitive data | rollback blocked or deletion re-applied under explicit policy |

## 20. CW-018 acceptance extension

CW-018 must include:

- migration manifest implementation;
- preflight;
- checkpoint/resume state;
- at least one additive migration fixture;
- at least one semantic migration fixture;
- encrypted backup/restore;
- key rotation;
- graph/index rebuild;
- deletion reconciliation;
- downgrade refusal;
- rollback or forward-repair exercise;
- exact evidence tying test results to canonical code.

## 21. Architecture rollback

If the Option B isolation model itself proves unworkable before PHI authorization:

- no Research Core evidence changes are needed;
- Workspace code/state boundaries are moved to the Option C separate-product topology;
- Domain R/W/X semantics remain;
- donor/license evidence remains reusable;
- no patient data is migrated during architecture rollback because PHI remains unauthorized at this phase.

## 22. Non-grants

This migration contract does not authorize:

```text
REAL_DATA_MIGRATION
PHI_IMPORT
PRODUCTION_UPGRADE
EHR_SIDE_EFFECT
MODEL_UPGRADE_EXECUTION
RESEARCH_DATA_ADMISSION
```
