"""Backup, restore, deletion, key-rotation and migration lifecycle for CW-018.

CW-018 (Issue #520) proves lifecycle protection across primary and derived state
under ADR-0039 as ratified with Amendment A1 and the migration, compatibility and
recovery contract. It adds no dependency and no capability: the Workspace package
still holds no filesystem, network, process or dynamic-import capability, so backups
are produced and consumed as bytes and the caller owns where they are kept.

Guarantees, each exercised by the CW-018 acceptance and adversarial suites:

* **encrypted backup** -- the transaction-consistent store snapshot is encrypted as
  one AES-256-GCM envelope under a backup key derived with HKDF-SHA-256 under a
  distinct label, the backup identity, and a fresh per-backup salt. No store key
  encrypts a backup, and no key material or payload plaintext is in the backup;
* **integrity manifest** -- a versioned plaintext manifest lists identities, types,
  revisions, content digests, tombstones, the audit head and the body digest. It is
  bound as the envelope's associated data, so altering any byte fails closed;
* **quarantine restore** -- a verified backup is loaded only into an empty store
  recorded as ``QUARANTINE``, which normal live mode refuses to open;
* **no silent overwrite** -- promotion only adds state the live store lacks and is
  refused when the live store holds anything the backup does not; rollback is
  refused unless the backup's audit chain is an ancestor of the live chain;
* **deleted content stays deleted** -- every deletion records a tombstone in the
  same transaction; restore, promotion and rollback never resurrect a revision the
  user deleted, and derived graph, view, dataset and export state that has become
  stale is removed by :func:`reconcile_deletions`;
* **migrations** -- a manifest, an eleven-point preflight that runs before any
  mutation, a checkpoint journal committed atomically with every step, deterministic
  resume, postcondition validation, and an explicit rollback class declared before
  the migration starts;
* **audit** -- backup, promotion, rollback, migration and key-rotation events carry
  identities, counts and digests only, never payload content.

Recorded limits: the quarantine store records no audit event of its own because its
content must equal the backup exactly (the ``RESTORE`` event is written to the live
store on promotion or rollback); the backup key comes from the same root secret as
the store keys, so root-secret loss loses both; disk space is not measured by this
package and must be declared by the caller. The journal state, store role and
tombstone reasons are declared plaintext metadata (A1.10): someone able to write the
store file can edit them, as they can already roll back the whole store (A1.5). Every
decision that could destroy or resurrect content is therefore bound to authenticated
audit evidence (the PREPARED migration event, ``object_delete`` events), while the
normal-open refusals driven by journal state and role guard against operator error,
not against a malicious writer; the CW-019 security lane owns attacking them.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.aead import decrypt_payload, encrypt_payload
from medscale_workspace.audit import (
    AuditEvent,
    AuditEventType,
    AuditTrail,
    prepare_event_following,
    prepare_next_event,
    verified_chain_from_objects,
)
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.dataset import (
    delete_dataset_collection,
    delete_export_manifest,
    read_dataset_collection,
    read_export_manifest,
)
from medscale_workspace.encounter import EncounterState, read_session
from medscale_workspace.errors import (
    BackupFormatError,
    BackupIntegrityError,
    DatasetCollectionStaleError,
    EnvelopeAuthenticationError,
    EnvelopeFormatError,
    ExportStagingStaleError,
    GraphStaleError,
    KeyRotationError,
    LifecycleError,
    MigrationError,
    MigrationPreflightError,
    MigrationValidationError,
    ObjectNotFoundError,
    RestoreConflictError,
    StoreRoleError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.keyprovider import KeyProvider, new_salt
from medscale_workspace.patient_graph import (
    delete_edge,
    delete_node,
    read_edge,
    read_node,
    read_view,
    view_binding,
)
from medscale_workspace.provenance import content_digest_of, provenance_binding_for
from medscale_workspace.storage import (
    TERMINAL_JOURNAL_STATES,
    JournalEntry,
    JournalState,
    JournalUpdate,
    KeyState,
    MigrationLogRow,
    ObjectWrite,
    SnapshotObject,
    StoreRole,
    Tombstone,
    TombstoneReason,
    WorkspaceStore,
)
from medscale_workspace.versions import (
    ENCRYPTION_FORMAT_VERSION,
    POLICY_VERSION,
    SCHEMA_V2_MIGRATION_CLASS,
    SCHEMA_V2_MIGRATION_ID,
    SUPPORTED_BACKUP_FORMAT_VERSIONS,
    SUPPORTED_DOWNGRADE_TARGETS,
    WORKSPACE_SCHEMA_VERSION,
)

LIFECYCLE_NAMESPACE = uuid5(UUID(int=0), "mesc-clinical-workspace-lifecycle/1")
BACKUP_MAGIC = b"MSWSBAK1"
BACKUP_ENVELOPE_KEY_VERSION = 1
BACKUP_FORMAT = 1
MAXIMUM_BACKUP_MANIFEST_BYTES = 8 * 1024 * 1024
MAXIMUM_BACKUP_BYTES = 256 * 1024 * 1024
MIGRATION_SPACE_FACTOR = 2
LIFECYCLE_TOOL_VERSION = "mesc-clinical-workspace-lifecycle/1"
_MANIFEST_LENGTH_BYTES = 4
_MAXIMUM_MIGRATION_ID_LENGTH = 64
_MIGRATION_ID_CHARACTERS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
_ACTIVE_CAPTURE_STATES = frozenset({EncounterState.CAPTURING, EncounterState.PAUSED})


class MigrationClass(StrEnum):
    """Migration classes M0-M5 from the migration contract section 4."""

    M0 = "M0"
    M1 = "M1"
    M2 = "M2"
    M3 = "M3"
    M4 = "M4"
    M5 = "M5"


class RollbackStrategy(StrEnum):
    """Rollback classes from the migration contract section 10."""

    APPLICATION_ROLLBACK = "application_rollback_without_schema_rollback"
    SNAPSHOT_ROLLBACK = "state_rollback_from_protected_snapshot"
    FORWARD_REPAIR = "forward_repair"


# ---------------------------------------------------------------------------
# Deletion policy (data_security.md section 17; migration contract sections 12, 19)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeletionPolicyEntry:
    """One declared deletion rule across primary, derived and retained state."""

    scope: str
    rule: str


DELETION_POLICY = (
    DeletionPolicyEntry(
        scope="object revisions",
        rule="removed from the store and tombstoned (USER_DELETION) in the same transaction",
    ),
    DeletionPolicyEntry(
        scope="audit events",
        rule="retained; a deletion event keeps identity, type, revision and digest only",
    ),
    DeletionPolicyEntry(
        scope="provenance records",
        rule="removed together with the object they describe by each unit's delete path",
    ),
    DeletionPolicyEntry(
        scope="graph nodes, edges and views",
        rule=(
            "stale on read once a bound source or member is gone (CW-011); removed with "
            "their provenance by reconcile_deletions"
        ),
    ),
    DeletionPolicyEntry(
        scope="dataset collections and export manifests",
        rule=(
            "stale on read once a pinned view or staged source is gone (CW-017 repair); "
            "removed by reconcile_deletions"
        ),
    ),
    DeletionPolicyEntry(
        scope="backups",
        rule=(
            "a backup is immutable bytes held by the caller; restore, promotion and "
            "rollback never resurrect a USER_DELETION tombstone, and the caller expires "
            "retained backups"
        ),
    ),
    DeletionPolicyEntry(
        scope="indexes, embeddings, caches and temporary files",
        rule=(
            "none exist outside the store: the Workspace package has no filesystem "
            "capability and no embedding index"
        ),
    ),
    DeletionPolicyEntry(
        scope="external or connector-side copies",
        rule="none exist: no connector write or external write authority is granted",
    ),
    DeletionPolicyEntry(
        scope="cryptographic erasure",
        rule=(
            "not claimed: secure_delete=ON is defense in depth only (A1.11) and key "
            "retirement does not erase copies held elsewhere"
        ),
    ),
)


# ---------------------------------------------------------------------------
# Shared admission helpers
# ---------------------------------------------------------------------------


def _canonical_bytes(document: object) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_store(store: object, *, label: str) -> WorkspaceStore:
    if not isinstance(store, WorkspaceStore):
        raise LifecycleError(f"{label} must be a workspace store")
    return store


def _admit_migration_id(raw: object) -> str:
    if not isinstance(raw, str) or not raw:
        raise MigrationError("migration id must be a non-empty string")
    if len(raw) > _MAXIMUM_MIGRATION_ID_LENGTH:
        raise MigrationError("migration id is longer than the admitted maximum")
    if any(character not in _MIGRATION_ID_CHARACTERS for character in raw):
        raise MigrationError("migration id admits lowercase letters, digits and hyphens only")
    return raw


def _admit_positive_int(raw: object, *, label: str) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 1:
        raise MigrationError(f"{label} must be a positive integer")
    return raw


def _object_key(binding: ObjectBinding) -> tuple[str, str]:
    return (str(binding.object_id), binding.object_revision)


def _tombstone_key(tombstone: Tombstone) -> tuple[str, str]:
    return (str(tombstone.object_id), tombstone.object_revision)


def _audit_write(event: AuditEvent) -> ObjectWrite:
    return ObjectWrite(binding=event.binding(), payload=event.canonical_bytes())


def _type_counts(objects: tuple[SnapshotObject, ...]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for item in objects:
        name = item.binding.object_type.value
        counts[name] = counts.get(name, 0) + 1
    return tuple(sorted(counts.items()))


# ---------------------------------------------------------------------------
# Backup format
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class BackupObjectEntry:
    """One object revision named by a backup manifest (identity and digest only)."""

    object_id: UUID
    object_type: WorkspaceObjectType
    object_revision: str
    content_digest: str

    def to_document(self) -> list[str]:
        return [
            str(self.object_id),
            self.object_type.value,
            self.object_revision,
            self.content_digest,
        ]


@dataclass(frozen=True, slots=True)
class BackupManifest:
    """The versioned, plaintext, integrity-bound description of one backup."""

    backup_format_version: int
    backup_id: UUID
    workspace_id: UUID
    created_at: str
    application_version: str
    workspace_schema_version: int
    policy_version: str
    encryption_format_version: int
    key_salt_hex: str
    included_data_classes: tuple[str, ...]
    included_object_types: tuple[str, ...]
    objects: tuple[BackupObjectEntry, ...]
    tombstones: tuple[Tombstone, ...]
    audit_event_count: int
    audit_head_digest: str | None
    body_digest: str

    def to_document(self) -> dict[str, object]:
        return {
            "application_version": self.application_version,
            "audit_event_count": self.audit_event_count,
            "audit_head_digest": self.audit_head_digest,
            "backup_format_version": self.backup_format_version,
            "backup_id": str(self.backup_id),
            "body_digest": self.body_digest,
            "created_at": self.created_at,
            "encryption_format_version": self.encryption_format_version,
            "included_data_classes": list(self.included_data_classes),
            "included_object_types": list(self.included_object_types),
            "key_salt_hex": self.key_salt_hex,
            "objects": [entry.to_document() for entry in self.objects],
            "policy_version": self.policy_version,
            "tombstones": [_tombstone_document(item) for item in self.tombstones],
            "workspace_id": str(self.workspace_id),
            "workspace_schema_version": self.workspace_schema_version,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_bytes(self.to_document())


@dataclass(frozen=True, slots=True)
class VerifiedBackup:
    """A backup whose manifest, envelope, body and bindings all verified."""

    manifest: BackupManifest
    objects: tuple[SnapshotObject, ...]
    tombstones: tuple[Tombstone, ...]


_MANIFEST_MEMBERS = frozenset(
    {
        "application_version",
        "audit_event_count",
        "audit_head_digest",
        "backup_format_version",
        "backup_id",
        "body_digest",
        "created_at",
        "encryption_format_version",
        "included_data_classes",
        "included_object_types",
        "key_salt_hex",
        "objects",
        "policy_version",
        "tombstones",
        "workspace_id",
        "workspace_schema_version",
    }
)


def _tombstone_document(tombstone: Tombstone) -> list[str]:
    return [
        str(tombstone.object_id),
        tombstone.object_type.value,
        tombstone.object_revision,
        tombstone.reason.value,
    ]


def _manifest_string(document: dict[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value:
        raise BackupFormatError(f"backup manifest member {name!r} must be a non-empty string")
    return value


def _manifest_int(document: dict[str, object], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise BackupFormatError(f"backup manifest member {name!r} must be a non-negative integer")
    return value


def _manifest_uuid(document: dict[str, object], name: str) -> UUID:
    raw = _manifest_string(document, name)
    try:
        return UUID(raw)
    except ValueError as error:
        raise BackupFormatError(f"backup manifest member {name!r} is not a UUID") from error


def _manifest_hex(raw: str, *, label: str, length: int) -> str:
    if len(raw) != length or any(character not in "0123456789abcdef" for character in raw):
        raise BackupFormatError(f"backup manifest {label} is not {length} lowercase hex digits")
    return raw


def _manifest_string_list(document: dict[str, object], name: str) -> tuple[str, ...]:
    value = document.get(name)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BackupFormatError(f"backup manifest member {name!r} must be a list of strings")
    return tuple(str(item) for item in value)


def _entry_from_document(raw: object) -> BackupObjectEntry:
    if not isinstance(raw, list) or len(raw) != 4 or not all(isinstance(x, str) for x in raw):
        raise BackupFormatError("a backup object entry must be four strings")
    object_id, object_type, object_revision, digest = (str(x) for x in raw)
    try:
        return BackupObjectEntry(
            object_id=UUID(object_id),
            object_type=WorkspaceObjectType(object_type),
            object_revision=object_revision,
            content_digest=digest,
        )
    except ValueError as error:
        raise BackupFormatError("a backup object entry is not well formed") from error


def _tombstone_from_document(raw: object) -> Tombstone:
    if not isinstance(raw, list) or len(raw) != 4 or not all(isinstance(x, str) for x in raw):
        raise BackupFormatError("a backup tombstone must be four strings")
    object_id, object_type, object_revision, reason = (str(x) for x in raw)
    try:
        return Tombstone(
            object_id=UUID(object_id),
            object_type=WorkspaceObjectType(object_type),
            object_revision=object_revision,
            reason=TombstoneReason(reason),
        )
    except ValueError as error:
        raise BackupFormatError("a backup tombstone is not well formed") from error


def _split_backup(data: object) -> tuple[bytes, bytes]:
    if not isinstance(data, bytes):
        raise BackupFormatError("a backup must be bytes")
    if len(data) > MAXIMUM_BACKUP_BYTES:
        raise BackupFormatError("the backup is larger than the admitted maximum")
    header_size = len(BACKUP_MAGIC) + _MANIFEST_LENGTH_BYTES
    if len(data) < header_size or data[: len(BACKUP_MAGIC)] != BACKUP_MAGIC:
        raise BackupFormatError("the bytes are not a CW-018 workspace backup")
    manifest_length = int.from_bytes(data[len(BACKUP_MAGIC) : header_size], "big")
    if manifest_length < 2 or manifest_length > MAXIMUM_BACKUP_MANIFEST_BYTES:
        raise BackupFormatError("the backup manifest length is outside the admitted range")
    manifest_bytes = data[header_size : header_size + manifest_length]
    envelope = data[header_size + manifest_length :]
    if len(manifest_bytes) != manifest_length or not envelope:
        raise BackupFormatError("the backup is truncated")
    return manifest_bytes, envelope


def read_backup_manifest(data: bytes) -> BackupManifest:
    """Parse and structurally validate a backup manifest without decrypting anything.

    The result is untrusted until :func:`open_backup` authenticates it: the manifest is
    the envelope's associated data, so any alteration fails authentication there.
    """

    manifest_bytes, _envelope = _split_backup(data)
    try:
        document = json.loads(manifest_bytes.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as error:
        raise BackupFormatError("the backup manifest is not ASCII JSON") from error
    if not isinstance(document, dict) or set(document) != _MANIFEST_MEMBERS:
        raise BackupFormatError("the backup manifest does not have the admitted members")
    if _canonical_bytes(document) != manifest_bytes:
        raise BackupFormatError("the backup manifest is not in canonical form")
    format_version = _manifest_int(document, "backup_format_version")
    if format_version not in SUPPORTED_BACKUP_FORMAT_VERSIONS:
        raise BackupFormatError("the backup format version is not supported by this application")
    raw_objects = document.get("objects")
    raw_tombstones = document.get("tombstones")
    if not isinstance(raw_objects, list) or not isinstance(raw_tombstones, list):
        raise BackupFormatError("backup manifest objects and tombstones must be lists")
    head = document.get("audit_head_digest")
    if head is not None:
        if not isinstance(head, str):
            raise BackupFormatError("backup audit head digest must be a string or null")
        head = _manifest_hex(head, label="audit head digest", length=64)
    return BackupManifest(
        backup_format_version=format_version,
        backup_id=_manifest_uuid(document, "backup_id"),
        workspace_id=_manifest_uuid(document, "workspace_id"),
        created_at=_manifest_string(document, "created_at"),
        application_version=_manifest_string(document, "application_version"),
        workspace_schema_version=_manifest_int(document, "workspace_schema_version"),
        policy_version=_manifest_string(document, "policy_version"),
        encryption_format_version=_manifest_int(document, "encryption_format_version"),
        key_salt_hex=_manifest_hex(
            _manifest_string(document, "key_salt_hex"), label="key salt", length=32
        ),
        included_data_classes=_manifest_string_list(document, "included_data_classes"),
        included_object_types=_manifest_string_list(document, "included_object_types"),
        objects=tuple(_entry_from_document(item) for item in raw_objects),
        tombstones=tuple(_tombstone_from_document(item) for item in raw_tombstones),
        audit_event_count=_manifest_int(document, "audit_event_count"),
        audit_head_digest=head,
        body_digest=_manifest_hex(
            _manifest_string(document, "body_digest"), label="body digest", length=64
        ),
    )


def _body_bytes(
    objects: tuple[SnapshotObject, ...],
    tombstones: tuple[Tombstone, ...],
) -> bytes:
    return _canonical_bytes(
        {
            "objects": [
                [
                    str(item.binding.object_id),
                    item.binding.object_type.value,
                    item.binding.object_revision,
                    item.payload.hex(),
                ]
                for item in objects
            ],
            "tombstones": [_tombstone_document(item) for item in tombstones],
        }
    )


def create_backup(
    store: WorkspaceStore,
    key_provider: KeyProvider,
    *,
    actor_id: str,
    occurred_at: str,
) -> bytes:
    """Create an encrypted, integrity-manifested backup of a live store.

    The snapshot is transaction-consistent. A ``BACKUP`` audit event naming the backup
    identity, counts and body digest is appended after the snapshot, so the backup
    describes the state immediately before its own event.
    """

    live = _require_store(store, label="the backed-up store")
    if live.role is not StoreRole.LIVE or live.maintenance:
        raise StoreRoleError("backups are taken from a live store opened in normal mode")
    if not isinstance(key_provider, KeyProvider):
        raise MigrationError("a key provider is required")
    trail = AuditTrail(live)
    report = trail.verify()
    snapshot = live.export_snapshot()
    audit_count = sum(
        1
        for item in snapshot.objects
        if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
    )
    if audit_count != report.events_verified:
        raise BackupIntegrityError("the snapshot and the verified audit chain disagree")
    body = _body_bytes(snapshot.objects, snapshot.tombstones)
    body_digest = _sha256_hex(body)
    backup_id = uuid5(
        LIFECYCLE_NAMESPACE,
        f"backup|{live.workspace_id}|{body_digest}|{occurred_at}",
    )
    salt = new_salt()
    manifest = BackupManifest(
        backup_format_version=BACKUP_FORMAT,
        backup_id=backup_id,
        workspace_id=live.workspace_id,
        created_at=occurred_at,
        application_version=snapshot.versions.application_version,
        workspace_schema_version=snapshot.versions.workspace_schema_version,
        policy_version=snapshot.versions.policy_version,
        encryption_format_version=snapshot.versions.encryption_format_version,
        key_salt_hex=salt.hex(),
        included_data_classes=(synthetic_data_class_value(),),
        included_object_types=tuple(name for name, _count in _type_counts(snapshot.objects)),
        objects=tuple(
            BackupObjectEntry(
                object_id=item.binding.object_id,
                object_type=item.binding.object_type,
                object_revision=item.binding.object_revision,
                content_digest=content_digest_of(item.payload),
            )
            for item in snapshot.objects
        ),
        tombstones=snapshot.tombstones,
        audit_event_count=report.events_verified,
        audit_head_digest=report.head_event_digest,
        body_digest=body_digest,
    )
    event = prepare_next_event(
        trail,
        event_type=AuditEventType.BACKUP,
        actor_id=actor_id,
        occurred_at=occurred_at,
        metadata=(
            ("backup_id", str(backup_id)),
            ("backup_format_version", str(BACKUP_FORMAT)),
            ("object_count", str(len(snapshot.objects))),
            ("tombstone_count", str(len(snapshot.tombstones))),
            ("body_digest", body_digest),
        ),
    )
    manifest_bytes = manifest.canonical_bytes()
    if len(manifest_bytes) > MAXIMUM_BACKUP_MANIFEST_BYTES:
        raise BackupFormatError("the backup manifest is larger than the admitted maximum")
    key = key_provider.backup_key(workspace_id=live.workspace_id, backup_id=backup_id, salt=salt)
    envelope = encrypt_payload(
        key=key,
        plaintext=body,
        associated_data=manifest_bytes,
        key_version=BACKUP_ENVELOPE_KEY_VERSION,
    )
    data = (
        BACKUP_MAGIC
        + len(manifest_bytes).to_bytes(_MANIFEST_LENGTH_BYTES, "big")
        + manifest_bytes
        + envelope
    )
    if len(data) > MAXIMUM_BACKUP_BYTES:
        raise BackupFormatError("the backup is larger than the admitted maximum")
    live.put_objects_atomic((_audit_write(event),))
    return data


def open_backup(
    data: bytes,
    key_provider: KeyProvider,
    *,
    workspace_id: UUID,
) -> VerifiedBackup:
    """Authenticate, decrypt and reconcile a backup for one expected workspace."""

    manifest = read_backup_manifest(data)
    if not isinstance(workspace_id, UUID):
        raise BackupFormatError("the expected workspace id must be a UUID value")
    if manifest.workspace_id != workspace_id:
        raise WorkspaceIsolationError("the backup belongs to a different workspace")
    if manifest.workspace_schema_version > WORKSPACE_SCHEMA_VERSION:
        raise BackupFormatError(
            "the backup was written by a newer workspace schema; a downgrade restore is "
            f"refused (supported downgrade targets: {list(SUPPORTED_DOWNGRADE_TARGETS)})"
        )
    if manifest.workspace_schema_version < WORKSPACE_SCHEMA_VERSION:
        raise BackupFormatError(
            "the backup predates every workspace schema this application restores"
        )
    if manifest.policy_version != POLICY_VERSION:
        raise BackupFormatError("the backup policy version is not the current policy")
    if manifest.encryption_format_version != ENCRYPTION_FORMAT_VERSION:
        raise BackupFormatError("the backup encryption format version is not supported")
    if not isinstance(key_provider, KeyProvider):
        raise BackupFormatError("a key provider is required")
    manifest_bytes, envelope = _split_backup(data)
    key = key_provider.backup_key(
        workspace_id=manifest.workspace_id,
        backup_id=manifest.backup_id,
        salt=bytes.fromhex(manifest.key_salt_hex),
    )
    try:
        body = decrypt_payload(envelope=envelope, key=key, associated_data=manifest_bytes)
    except (EnvelopeAuthenticationError, EnvelopeFormatError) as error:
        raise BackupIntegrityError(
            "the backup failed authentication; its manifest, body, key or salt changed"
        ) from error
    if _sha256_hex(body) != manifest.body_digest:
        raise BackupIntegrityError("the backup body digest does not match its manifest")
    objects, tombstones = _parse_body(body, workspace_id=manifest.workspace_id)
    _reconcile_manifest(manifest, objects, tombstones)
    return VerifiedBackup(manifest=manifest, objects=objects, tombstones=tombstones)


def _parse_body(
    body: bytes,
    *,
    workspace_id: UUID,
) -> tuple[tuple[SnapshotObject, ...], tuple[Tombstone, ...]]:
    try:
        document = json.loads(body.decode("ascii"))
    except (UnicodeDecodeError, ValueError) as error:
        raise BackupIntegrityError("the backup body is not ASCII JSON") from error
    if not isinstance(document, dict) or set(document) != {"objects", "tombstones"}:
        raise BackupIntegrityError("the backup body does not have the admitted members")
    raw_objects = document["objects"]
    raw_tombstones = document["tombstones"]
    if not isinstance(raw_objects, list) or not isinstance(raw_tombstones, list):
        raise BackupIntegrityError("backup body objects and tombstones must be lists")
    objects: list[SnapshotObject] = []
    for raw in raw_objects:
        if not isinstance(raw, list) or len(raw) != 4 or not all(isinstance(x, str) for x in raw):
            raise BackupIntegrityError("a backup body object must be four strings")
        object_id, object_type, object_revision, payload_hex = (str(x) for x in raw)
        try:
            binding = ObjectBinding(
                workspace_id=workspace_id,
                object_id=UUID(object_id),
                object_type=WorkspaceObjectType(object_type),
                object_revision=object_revision,
            ).validated()
            payload = bytes.fromhex(payload_hex)
        except ValueError as error:
            raise BackupIntegrityError("a backup body object is not well formed") from error
        if not payload:
            raise BackupIntegrityError("a backup body object has an empty payload")
        objects.append(SnapshotObject(binding=binding, payload=payload))
    tombstones: list[Tombstone] = []
    for raw in raw_tombstones:
        try:
            tombstones.append(_tombstone_from_document(raw))
        except BackupFormatError as error:
            raise BackupIntegrityError("a backup body tombstone is not well formed") from error
    return tuple(objects), tuple(tombstones)


def _reconcile_manifest(
    manifest: BackupManifest,
    objects: tuple[SnapshotObject, ...],
    tombstones: tuple[Tombstone, ...],
) -> None:
    if len(objects) != len(manifest.objects):
        raise BackupIntegrityError("the backup object count does not match its manifest")
    seen: set[tuple[str, str]] = set()
    for item, entry in zip(objects, manifest.objects, strict=True):
        binding = item.binding
        if (
            binding.object_id != entry.object_id
            or binding.object_type is not entry.object_type
            or binding.object_revision != entry.object_revision
        ):
            raise BackupIntegrityError("a backup object does not match its manifest entry")
        if content_digest_of(item.payload) != entry.content_digest:
            raise BackupIntegrityError("a backup object digest does not match its manifest")
        key = _object_key(binding)
        if key in seen:
            raise BackupIntegrityError("a backup names one object revision twice")
        seen.add(key)
    if tombstones != manifest.tombstones:
        raise BackupIntegrityError("the backup tombstones do not match its manifest")
    tombstone_keys = {_tombstone_key(item) for item in tombstones}
    if len(tombstone_keys) != len(tombstones):
        raise BackupIntegrityError("a backup names one tombstone twice")
    if tombstone_keys & seen:
        raise BackupIntegrityError("a backup object revision is also tombstoned")
    audit_count = sum(
        1 for item in objects if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
    )
    if audit_count != manifest.audit_event_count:
        raise BackupIntegrityError("the backup audit event count does not match its manifest")
    if manifest.included_object_types != tuple(name for name, _ in _type_counts(objects)):
        raise BackupIntegrityError("the backup included object types do not match its body")
    if manifest.included_data_classes != (synthetic_data_class_value(),):
        raise BackupIntegrityError("the backup declares a data class other than synthetic")


# ---------------------------------------------------------------------------
# Quarantine restore, promotion and rollback
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class QuarantineReport:
    """The verified result of restoring a backup into a quarantine store."""

    backup_id: UUID
    workspace_id: UUID
    quarantine_store_path: str
    object_count: int
    tombstone_count: int
    audit_events_verified: int
    type_counts: tuple[tuple[str, int], ...]


def restore_backup_to_quarantine(
    data: bytes,
    key_provider: KeyProvider,
    *,
    workspace_id: UUID,
    quarantine_root: str,
    application_version: str,
) -> QuarantineReport:
    """Verify a backup and restore it into a new, empty quarantine store.

    The quarantine store cannot be opened in normal live mode. Every restored object
    is re-read and reconciled against the backup digests, the restored audit chain is
    verified against the manifest's head anchor, and SQLite integrity is checked.
    """

    verified = open_backup(data, key_provider, workspace_id=workspace_id)
    manifest = verified.manifest
    with WorkspaceStore.open(
        store_root=quarantine_root,
        workspace_id=workspace_id,
        key_provider=key_provider,
        application_version=application_version,
        role=StoreRole.QUARANTINE,
    ) as quarantine:
        quarantine.import_snapshot(
            objects=verified.objects,
            tombstones=verified.tombstones,
            restored_backup_id=manifest.backup_id,
        )
        restored = quarantine.export_snapshot()
        if tuple(
            (item.binding, content_digest_of(item.payload)) for item in restored.objects
        ) != tuple((item.binding, content_digest_of(item.payload)) for item in verified.objects):
            raise BackupIntegrityError("the quarantine store does not reproduce the backup")
        if restored.tombstones != verified.tombstones:
            raise BackupIntegrityError("the quarantine tombstones do not reproduce the backup")
        chain = AuditTrail(quarantine).verify(expected_head_event_digest=manifest.audit_head_digest)
        quarantine.integrity_check()
        path = quarantine.store_path
    return QuarantineReport(
        backup_id=manifest.backup_id,
        workspace_id=workspace_id,
        quarantine_store_path=path,
        object_count=len(verified.objects),
        tombstone_count=len(verified.tombstones),
        audit_events_verified=chain.events_verified,
        type_counts=_type_counts(verified.objects),
    )


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """What a quarantine promotion added to, and left out of, the live store."""

    backup_id: UUID
    restored_objects: int
    skipped_deleted: int
    recorded_tombstones: int
    audit_event_digest: str


@dataclass(frozen=True, slots=True)
class RollbackReport:
    """What a snapshot rollback discarded from, and returned to, the live store."""

    backup_id: UUID
    discarded_objects: int
    returned_objects: int
    kept_deleted: int
    audit_event_digest: str
    journal_migration_id: str | None


def _require_quarantine_pair(live: WorkspaceStore, quarantine: WorkspaceStore) -> UUID:
    _require_store(live, label="the live store")
    _require_store(quarantine, label="the quarantine store")
    if live.role is not StoreRole.LIVE:
        raise StoreRoleError("the promotion or rollback target must be a live store")
    if quarantine.role is not StoreRole.QUARANTINE:
        raise StoreRoleError("the promotion or rollback source must be a quarantine store")
    if live.workspace_id != quarantine.workspace_id:
        raise WorkspaceIsolationError("a quarantine store cannot cross workspace identities")
    if live.store_path == quarantine.store_path:
        raise StoreRoleError("the live and quarantine stores must be different stores")
    backup_id = quarantine.restored_backup_id
    if backup_id is None:
        raise RestoreConflictError("the quarantine store holds no verified restored backup")
    AuditTrail(quarantine).verify()
    return backup_id


def _audited_deletions(objects: tuple[SnapshotObject, ...]) -> set[tuple[str, str]]:
    """Revisions an authenticated ``object_delete`` audit event says the user deleted.

    Tombstone reasons are plaintext store metadata; the audit chain is encrypted and
    digest-linked. A revision named by a verified deletion event is treated as a user
    deletion even if its tombstone reason was altered, so editing plaintext metadata can
    never make promotion or rollback resurrect deleted content.
    """

    chain = verified_chain_from_objects(
        tuple(
            (item.binding, item.payload)
            for item in objects
            if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
        )
    )
    deleted: set[tuple[str, str]] = set()
    for event in chain:
        if event.event_type is AuditEventType.OBJECT_DELETE:
            for reference in event.object_refs:
                deleted.add((str(reference.object_id), reference.object_revision))
    return deleted


def _digest_map(
    objects: tuple[SnapshotObject, ...],
) -> dict[tuple[str, str], tuple[SnapshotObject, str]]:
    return {_object_key(item.binding): (item, content_digest_of(item.payload)) for item in objects}


def promote_quarantine(
    live: WorkspaceStore,
    quarantine: WorkspaceStore,
    *,
    actor_id: str,
    occurred_at: str,
) -> PromotionReport:
    """Add a quarantined backup's missing state to a live store without overwriting.

    Refused when the live store holds any object revision the backup does not (newer
    or divergent state) and when a shared revision differs. Revisions the live store
    has tombstoned are not resurrected. The added objects, the carried tombstones and
    the ``RESTORE`` audit event commit in one transaction.
    """

    backup_id = _require_quarantine_pair(live, quarantine)
    if live.maintenance:
        raise StoreRoleError("promotion targets a live store opened in normal mode")
    AuditTrail(live).verify()
    source = quarantine.export_snapshot()
    target = live.export_snapshot()
    source_map = _digest_map(source.objects)
    target_map = _digest_map(target.objects)
    newer = sorted(key for key in target_map if key not in source_map)
    if newer:
        raise RestoreConflictError(
            f"the live store holds {len(newer)} object revision(s) absent from the backup; "
            "promotion would silently roll back newer or divergent state and is refused"
        )
    for key, (item, digest) in target_map.items():
        source_item, source_digest = source_map[key]
        if item.binding != source_item.binding or digest != source_digest:
            raise RestoreConflictError("a revision differs between the live store and the backup")
    live_deleted = {_tombstone_key(item) for item in target.tombstones}
    live_deleted |= _audited_deletions(target.objects)
    additions: list[SnapshotObject] = []
    skipped = 0
    for key in sorted(source_map):
        if key in target_map:
            continue
        if key in live_deleted:
            skipped += 1
            continue
        additions.append(source_map[key][0])
    carried = tuple(item for item in source.tombstones if _tombstone_key(item) not in live_deleted)
    restored_head = _chain_head(source.objects)
    event = prepare_event_following(
        restored_head,
        workspace_id=live.workspace_id,
        event_type=AuditEventType.RESTORE,
        actor_id=actor_id,
        occurred_at=occurred_at,
        metadata=(
            ("mode", "promote"),
            ("backup_id", str(backup_id)),
            ("restored_objects", str(len(additions))),
            ("skipped_deleted", str(skipped)),
            ("recorded_tombstones", str(len(carried))),
        ),
    )
    live.apply_state_change(
        writes=(
            *tuple(ObjectWrite(binding=item.binding, payload=item.payload) for item in additions),
            _audit_write(event),
        ),
        record_tombstones=carried,
    )
    AuditTrail(live).verify(expected_head_event_digest=event.event_digest)
    return PromotionReport(
        backup_id=backup_id,
        restored_objects=len(additions),
        skipped_deleted=skipped,
        recorded_tombstones=len(carried),
        audit_event_digest=event.event_digest,
    )


def _chain_head(objects: tuple[SnapshotObject, ...]) -> AuditEvent | None:
    """Return the verified head of a snapshot's audit chain, or ``None`` if empty."""

    chain = verified_chain_from_objects(
        tuple(
            (item.binding, item.payload)
            for item in objects
            if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
        )
    )
    return chain[-1] if chain else None


def rollback_to_quarantine(
    live: WorkspaceStore,
    quarantine: WorkspaceStore,
    *,
    actor_id: str,
    occurred_at: str,
    journal_migration_id: str | None = None,
) -> RollbackReport:
    """Return a live store to a quarantined snapshot's state (contract section 10).

    Preconditions: the snapshot's audit chain is an ancestor of the live chain, so the
    snapshot cannot be newer than, or forked from, the live store. Effects, in one
    transaction with the ``RESTORE`` event and, when named, the journal transition to
    ``ROLLED_BACK``:

    * live revisions created after the snapshot are discarded (``ROLLBACK_DISCARDED``);
    * snapshot revisions a migration or earlier rollback removed are returned;
    * snapshot revisions the user deleted after the snapshot stay deleted;
    * every audit event is kept, because audit survives rollback.
    """

    backup_id = _require_quarantine_pair(live, quarantine)
    source = quarantine.export_snapshot()
    target = live.export_snapshot()
    source_map = _digest_map(source.objects)
    target_map = _digest_map(target.objects)
    source_audit = {
        key
        for key, (item, _digest) in source_map.items()
        if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
    }
    target_audit = {
        key
        for key, (item, _digest) in target_map.items()
        if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
    }
    if not source_audit <= target_audit:
        raise RestoreConflictError(
            "the snapshot's audit chain is not an ancestor of the live chain; the snapshot "
            "is newer than or forked from the live store and rollback is refused"
        )
    live_tombstones = {_tombstone_key(item): item for item in target.tombstones}
    audited_deletions = _audited_deletions(target.objects)
    discard: list[ObjectBinding] = []
    returned: list[SnapshotObject] = []
    kept_deleted = 0
    for key, (item, digest) in sorted(target_map.items()):
        if key in target_audit:
            continue
        if key not in source_map:
            discard.append(item.binding)
            continue
        source_item, source_digest = source_map[key]
        if item.binding != source_item.binding or digest != source_digest:
            raise RestoreConflictError("a revision differs between the live store and the snapshot")
    for key, (item, _digest) in sorted(source_map.items()):
        if key in source_audit or key in target_map:
            continue
        tombstone = live_tombstones.get(key)
        if tombstone is None:
            raise RestoreConflictError(
                "a snapshot revision is absent from the live store without a tombstone; the "
                "absence is untracked and rollback is refused"
            )
        if tombstone.reason is TombstoneReason.USER_DELETION or key in audited_deletions:
            kept_deleted += 1
            continue
        returned.append(item)
    journal: JournalUpdate | None = None
    if journal_migration_id is not None:
        entry = _journal_entry(live, _admit_migration_id(journal_migration_id))
        if entry.state in TERMINAL_JOURNAL_STATES:
            raise MigrationError("a finished migration cannot be rolled back through its journal")
        document = _journal_document(entry)
        document["result"] = JournalState.ROLLED_BACK.value
        document["rollback_backup_id"] = str(backup_id)
        journal = JournalUpdate(
            entry=JournalEntry(
                migration_id=entry.migration_id,
                migration_class=entry.migration_class,
                state=JournalState.ROLLED_BACK,
                checkpoint=entry.checkpoint,
                manifest=_canonical_bytes(document).decode("ascii"),
            )
        )
    elif _unfinished(live):
        raise MigrationError("an unfinished migration must be named when rolling back")
    event = prepare_next_event(
        AuditTrail(live),
        event_type=AuditEventType.RESTORE,
        actor_id=actor_id,
        occurred_at=occurred_at,
        metadata=(
            ("mode", "rollback"),
            ("backup_id", str(backup_id)),
            ("discarded_objects", str(len(discard))),
            ("returned_objects", str(len(returned))),
            ("kept_deleted", str(kept_deleted)),
            ("migration_id", journal_migration_id or "none"),
        ),
    )
    live.apply_state_change(
        deletions=tuple(discard),
        writes=(
            *tuple(ObjectWrite(binding=item.binding, payload=item.payload) for item in returned),
            _audit_write(event),
        ),
        tombstone_reason=TombstoneReason.ROLLBACK_DISCARDED,
        journal=journal,
    )
    AuditTrail(live).verify(expected_head_event_digest=event.event_digest)
    return RollbackReport(
        backup_id=backup_id,
        discarded_objects=len(discard),
        returned_objects=len(returned),
        kept_deleted=kept_deleted,
        audit_event_digest=event.event_digest,
        journal_migration_id=journal_migration_id,
    )


# ---------------------------------------------------------------------------
# Migration manifest, preflight and journaled execution
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MigrationManifest:
    """The migration manifest of contract section 5 (identities and counts only)."""

    migration_id: str
    migration_class: MigrationClass
    workspace_id: UUID
    source_app_version: str
    target_app_version: str
    source_workspace_schema_version: int
    target_workspace_schema_version: int
    source_policy_version: str
    target_policy_version: str
    source_encryption_format_version: int
    target_encryption_format_version: int
    required_key_versions: tuple[int, ...]
    affected_object_types: tuple[WorkspaceObjectType, ...]
    affected_projection_types: tuple[WorkspaceObjectType, ...]
    preconditions: tuple[str, ...]
    expected_object_counts: tuple[tuple[str, int], ...]
    pre_migration_snapshot_identity: UUID | None
    steps: tuple[str, ...]
    postconditions: tuple[str, ...]
    rollback_strategy: RollbackStrategy
    irreversible_operations: tuple[str, ...]
    external_side_effects: tuple[str, ...]
    tool_version: str
    started_at: str
    completed_at: str | None = None
    result: str | None = None

    def validated(self) -> MigrationManifest:
        _admit_migration_id(self.migration_id)
        if not isinstance(self.migration_class, MigrationClass):
            raise MigrationError("migration class must be an admitted MigrationClass")
        if not isinstance(self.rollback_strategy, RollbackStrategy):
            raise MigrationError("the rollback class must be declared before migration starts")
        if not isinstance(self.workspace_id, UUID):
            raise MigrationError("manifest workspace id must be a UUID value")
        for label, value in (
            ("source application version", self.source_app_version),
            ("target application version", self.target_app_version),
            ("source policy version", self.source_policy_version),
            ("target policy version", self.target_policy_version),
            ("tool version", self.tool_version),
            ("start time", self.started_at),
        ):
            if not isinstance(value, str) or not value.strip():
                raise MigrationError(f"manifest {label} must be recorded")
        for label, number in (
            ("source schema", self.source_workspace_schema_version),
            ("target schema", self.target_workspace_schema_version),
            ("source format", self.source_encryption_format_version),
            ("target format", self.target_encryption_format_version),
        ):
            _admit_positive_int(number, label=f"manifest {label} version")
        if self.target_workspace_schema_version < self.source_workspace_schema_version:
            raise MigrationError("migrations are forward-only; a lower target schema is refused")
        if not self.required_key_versions:
            raise MigrationError("a migration must name its required key versions")
        for key_version in self.required_key_versions:
            _admit_positive_int(key_version, label="required key version")
        for object_type in self.affected_object_types + self.affected_projection_types:
            if not isinstance(object_type, WorkspaceObjectType):
                raise MigrationError("affected types must be admitted workspace object types")
        if not self.steps or not self.postconditions:
            raise MigrationError("a migration must declare its steps and postconditions")
        if self.external_side_effects:
            raise MigrationError(
                "external side effects are not authorized; a migration naming any is refused"
            )
        if self.pre_migration_snapshot_identity is not None and not isinstance(
            self.pre_migration_snapshot_identity, UUID
        ):
            raise MigrationError("the snapshot identity must be a UUID value")
        return self

    def to_document(self) -> dict[str, object]:
        return {
            "affected_object_types": [item.value for item in self.affected_object_types],
            "affected_projection_types": [item.value for item in self.affected_projection_types],
            "completed_at": self.completed_at,
            "expected_object_counts": [
                [name, count] for name, count in self.expected_object_counts
            ],
            "external_side_effects": list(self.external_side_effects),
            "irreversible_operations": list(self.irreversible_operations),
            "migration_class": self.migration_class.value,
            "migration_id": self.migration_id,
            "postconditions": list(self.postconditions),
            "pre_migration_snapshot_identity": (
                None
                if self.pre_migration_snapshot_identity is None
                else str(self.pre_migration_snapshot_identity)
            ),
            "preconditions": list(self.preconditions),
            "required_key_versions": list(self.required_key_versions),
            "result": self.result,
            "rollback_strategy": self.rollback_strategy.value,
            "source_app_version": self.source_app_version,
            "source_encryption_format_version": self.source_encryption_format_version,
            "source_policy_version": self.source_policy_version,
            "source_workspace_schema_version": self.source_workspace_schema_version,
            "started_at": self.started_at,
            "steps": list(self.steps),
            "target_app_version": self.target_app_version,
            "target_encryption_format_version": self.target_encryption_format_version,
            "target_policy_version": self.target_policy_version,
            "target_workspace_schema_version": self.target_workspace_schema_version,
            "tool_version": self.tool_version,
            "workspace_id": str(self.workspace_id),
        }


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """The eleven preflight checks of contract section 6, all passed before mutation."""

    migration_id: str
    checks: tuple[tuple[str, str], ...]
    required_bytes: int


@dataclass(frozen=True, slots=True)
class MigrationReport:
    """The outcome of a migration run or resume."""

    migration_id: str
    migration_class: MigrationClass
    state: JournalState
    migrated_objects: int
    evidence: tuple[tuple[str, str, str, str, str], ...] = field(default=())


def _journal_entry(store: WorkspaceStore, migration_id: str) -> JournalEntry:
    for entry in store.journal_entries():
        if entry.migration_id == migration_id:
            return entry
    raise MigrationError(f"migration {migration_id!r} has no journal entry")


def _unfinished(store: WorkspaceStore) -> tuple[JournalEntry, ...]:
    return tuple(
        entry for entry in store.journal_entries() if entry.state not in TERMINAL_JOURNAL_STATES
    )


def _journal_document(entry: JournalEntry) -> dict[str, object]:
    try:
        document = json.loads(entry.manifest)
    except ValueError as error:
        raise MigrationError("a journal manifest is not JSON") from error
    if not isinstance(document, dict):
        raise MigrationError("a journal manifest must be a JSON object")
    return document


def _content_set(objects: tuple[SnapshotObject, ...]) -> set[tuple[tuple[str, str], str]]:
    """Identity and digest of every non-audit object, for snapshot currency checks."""

    return {
        (_object_key(item.binding), content_digest_of(item.payload))
        for item in objects
        if item.binding.object_type is not WorkspaceObjectType.AUDIT_EVENT
    }


def _active_captures(store: WorkspaceStore) -> tuple[UUID, ...]:
    session_ids = sorted(
        {
            object_id
            for object_id, _ in store.object_revisions(WorkspaceObjectType.ENCOUNTER_SESSION)
        },
        key=str,
    )
    active: list[UUID] = []
    for session_id in session_ids:
        record = read_session(store, session_id)
        if record.state in _ACTIVE_CAPTURE_STATES:
            active.append(session_id)
    return tuple(active)


def _type_count(store: WorkspaceStore, object_type: WorkspaceObjectType) -> int:
    return len(store.object_revisions(object_type))


def expected_object_counts(
    store: WorkspaceStore,
    object_types: tuple[WorkspaceObjectType, ...],
) -> tuple[tuple[str, int], ...]:
    """Inventory the total object count plus each named type, for a manifest."""

    counts = [("total", store.object_count())]
    counts.extend((item.value, _type_count(store, item)) for item in object_types)
    return tuple(sorted(counts))


def preflight(
    store: WorkspaceStore,
    manifest: MigrationManifest,
    key_provider: KeyProvider,
    *,
    available_bytes: int,
    snapshot: bytes | None = None,
) -> PreflightReport:
    """Run the eleven section-6 checks; any failure raises before mutation."""

    target = _require_store(store, label="the migrated store")
    admitted = manifest.validated()
    checks: list[tuple[str, str]] = []

    unfinished = _unfinished(target)
    if unfinished:
        raise MigrationPreflightError(
            "another migration holds the exclusive migration lock: "
            + ", ".join(entry.migration_id for entry in unfinished)
        )
    if any(entry.migration_id == admitted.migration_id for entry in target.journal_entries()):
        raise MigrationPreflightError("this migration id already has a journal entry")
    checks.append(("exclusive_migration_lock", "PASS"))

    if admitted.workspace_id != target.workspace_id:
        raise MigrationPreflightError("the manifest names a different workspace")
    checks.append(("workspace_identity", "PASS"))

    versions = target.versions
    if (
        versions.application_version != admitted.source_app_version
        or versions.workspace_schema_version != admitted.source_workspace_schema_version
        or versions.policy_version != admitted.source_policy_version
        or versions.encryption_format_version != admitted.source_encryption_format_version
    ):
        raise MigrationPreflightError("the recorded version tuple is not the manifest source")
    checks.append(("source_versions", "PASS"))

    target.integrity_check()
    AuditTrail(target).verify()
    checks.append(("database_and_audit_integrity", "PASS"))

    in_use = target.object_key_versions()
    if not set(in_use) <= set(admitted.required_key_versions):
        raise MigrationPreflightError("stored rows use a key version the manifest does not name")
    target.verify_key_availability(admitted.required_key_versions)
    checks.append(("key_availability", "PASS"))

    required = MIGRATION_SPACE_FACTOR * target.stored_envelope_bytes()
    if not isinstance(available_bytes, int) or isinstance(available_bytes, bool):
        raise MigrationPreflightError("available space must be declared as an integer")
    if available_bytes < required:
        raise MigrationPreflightError(
            f"declared free space {available_bytes} is below the required {required} bytes"
        )
    checks.append(("sufficient_space", "PASS"))

    active = _active_captures(target)
    if active:
        raise MigrationPreflightError("an encounter capture is active; migration is refused")
    checks.append(("no_active_capture", "PASS"))

    if admitted.rollback_strategy is RollbackStrategy.SNAPSHOT_ROLLBACK:
        if snapshot is None or admitted.pre_migration_snapshot_identity is None:
            raise MigrationPreflightError("a snapshot rollback requires a verified snapshot")
        verified = open_backup(snapshot, key_provider, workspace_id=target.workspace_id)
        if verified.manifest.backup_id != admitted.pre_migration_snapshot_identity:
            raise MigrationPreflightError("the snapshot is not the one the manifest names")
        current = target.export_snapshot()
        if _content_set(verified.objects) != _content_set(current.objects):
            raise MigrationPreflightError("the snapshot does not capture the current state")
        checks.append(("snapshot_integrity", "PASS"))
    else:
        checks.append(("snapshot_integrity", "NOT_REQUIRED_BY_ROLLBACK_CLASS"))

    affected = tuple(
        item for item in admitted.affected_object_types + admitted.affected_projection_types
    )
    if expected_object_counts(target, affected) != tuple(sorted(admitted.expected_object_counts)):
        raise MigrationPreflightError("the object inventory does not match the manifest counts")
    checks.append(("object_inventory", "PASS"))

    checks.append(("external_side_effects_classified", "NONE"))
    checks.append(("fail_before_mutation", "PASS"))
    return PreflightReport(
        migration_id=admitted.migration_id,
        checks=tuple(checks),
        required_bytes=required,
    )


def migrate_schema_to_current(
    *,
    store_root: str,
    workspace_id: UUID,
    key_provider: KeyProvider,
    source_application_version: str,
    target_application_version: str,
    available_bytes: int,
    actor_id: str,
    occurred_at: str,
) -> MigrationReport:
    """Run the M1 additive migration (schema 1 -> 2) with manifest and preflight.

    The whole migration -- new tables, recorded role, version metadata, migration log,
    journal and audit event -- is one SQLite transaction, so an interruption leaves the
    store at schema 1 (``NOT_STARTED``) and the migration can simply run again. Its
    declared rollback class is forward repair: once schema 2 is committed, an
    application that reads only schema 1 refuses the store rather than guessing.
    """

    with WorkspaceStore.open_for_maintenance(
        store_root=store_root,
        workspace_id=workspace_id,
        key_provider=key_provider,
        application_version=source_application_version,
    ) as store:
        versions = store.versions
        if versions.workspace_schema_version == WORKSPACE_SCHEMA_VERSION:
            raise MigrationError("the store is already at the current workspace schema")
        manifest = MigrationManifest(
            migration_id=SCHEMA_V2_MIGRATION_ID,
            migration_class=MigrationClass(SCHEMA_V2_MIGRATION_CLASS),
            workspace_id=workspace_id,
            source_app_version=versions.application_version,
            target_app_version=target_application_version,
            source_workspace_schema_version=versions.workspace_schema_version,
            target_workspace_schema_version=WORKSPACE_SCHEMA_VERSION,
            source_policy_version=versions.policy_version,
            target_policy_version=versions.policy_version,
            source_encryption_format_version=versions.encryption_format_version,
            target_encryption_format_version=versions.encryption_format_version,
            required_key_versions=store.object_key_versions() or (store.active_key_version,),
            affected_object_types=(),
            affected_projection_types=(),
            preconditions=("schema 1 store", "no unfinished migration", "keys available"),
            expected_object_counts=expected_object_counts(store, ()),
            pre_migration_snapshot_identity=None,
            steps=(
                "create deletion_tombstones and migration_journal tables",
                "record store role LIVE",
                "record workspace schema 2 and readable range 2..2",
                "append migration log, completed journal row and migration audit event",
            ),
            postconditions=(
                "object count unchanged",
                "audit chain verifies",
                "store opens in normal mode at schema 2",
            ),
            rollback_strategy=RollbackStrategy.FORWARD_REPAIR,
            irreversible_operations=("schema 2 metadata commit",),
            external_side_effects=(),
            tool_version=LIFECYCLE_TOOL_VERSION,
            started_at=occurred_at,
        ).validated()
        preflight(store, manifest, key_provider, available_bytes=available_bytes)
        before_count = store.object_count()
        completed = replace(
            manifest,
            completed_at=occurred_at,
            result=JournalState.COMPLETED.value,
        )
        event = prepare_next_event(
            AuditTrail(store),
            event_type=AuditEventType.MIGRATION,
            actor_id=actor_id,
            occurred_at=occurred_at,
            metadata=(
                ("migration_id", manifest.migration_id),
                ("migration_class", manifest.migration_class.value),
                ("source_workspace_schema_version", str(manifest.source_workspace_schema_version)),
                ("target_workspace_schema_version", str(manifest.target_workspace_schema_version)),
                ("rollback_strategy", manifest.rollback_strategy.value),
                ("result", JournalState.COMPLETED.value),
            ),
        )
        store.apply_schema_v2_migration(
            target_application_version=target_application_version,
            journal_manifest=_canonical_bytes({"manifest": completed.to_document()}).decode(
                "ascii"
            ),
            audit_write=_audit_write(event),
        )
    with WorkspaceStore.open(
        store_root=store_root,
        workspace_id=workspace_id,
        key_provider=key_provider,
        application_version=target_application_version,
    ) as migrated:
        if migrated.object_count() != before_count + 1:
            raise MigrationValidationError("the object count changed across the M1 migration")
        AuditTrail(migrated).verify(expected_head_event_digest=event.event_digest)
        migrated.integrity_check()
        state = _journal_entry(migrated, manifest.migration_id).state
    return MigrationReport(
        migration_id=manifest.migration_id,
        migration_class=manifest.migration_class,
        state=state,
        migrated_objects=0,
    )


class SemanticTransform:
    """A reviewed, code-defined M2 representation change applied object by object.

    Subclasses implement :meth:`transform` and :meth:`validate`. Transforms are code,
    never content: nothing in a payload can select or alter the transform.
    """

    def transform(self, binding: ObjectBinding, payload: bytes) -> bytes:
        raise MigrationError("the semantic transform does not implement transform()")

    def validate(self, binding: ObjectBinding, payload: bytes) -> bool:
        raise MigrationError("the semantic transform does not implement validate()")


def _migrated_revision(binding: ObjectBinding, migration_id: str) -> str:
    return f"{binding.object_revision}+{migration_id}"


def begin_semantic_migration(
    store: WorkspaceStore,
    manifest: MigrationManifest,
    transform: SemanticTransform,
    key_provider: KeyProvider,
    *,
    available_bytes: int,
    snapshot: bytes | None,
    actor_id: str,
    occurred_at: str,
) -> MigrationReport:
    """Preflight, journal and run an M2 semantic migration over the affected types."""

    target = _require_store(store, label="the migrated store")
    admitted = manifest.validated()
    if admitted.migration_class is not MigrationClass.M2:
        raise MigrationError("begin_semantic_migration runs M2 semantic migrations only")
    if not admitted.affected_object_types:
        raise MigrationError("an M2 migration must name the object types it rewrites")
    if WorkspaceObjectType.AUDIT_EVENT in admitted.affected_object_types:
        raise MigrationError("audit events are never rewritten by a migration")
    if not isinstance(transform, SemanticTransform):
        raise MigrationError("an M2 migration requires a SemanticTransform")
    preflight(target, admitted, key_provider, available_bytes=available_bytes, snapshot=snapshot)
    inventory: list[list[str]] = []
    for object_type in admitted.affected_object_types:
        for object_id, revision in target.object_revisions(object_type):
            binding = ObjectBinding(
                workspace_id=target.workspace_id,
                object_id=object_id,
                object_type=object_type,
                object_revision=revision,
            ).validated()
            new_revision = _migrated_revision(binding, admitted.migration_id)
            ObjectBinding(
                workspace_id=target.workspace_id,
                object_id=object_id,
                object_type=object_type,
                object_revision=new_revision,
            ).validated()
            inventory.append([str(object_id), object_type.value, revision])
    inventory.sort()
    document: dict[str, object] = {
        "manifest": admitted.to_document(),
        "inventory": inventory,
        "evidence": [],
        "result": None,
    }
    event = prepare_next_event(
        AuditTrail(target),
        event_type=AuditEventType.MIGRATION,
        actor_id=actor_id,
        occurred_at=occurred_at,
        metadata=(
            ("migration_id", admitted.migration_id),
            ("migration_class", admitted.migration_class.value),
            ("phase", JournalState.PREPARED.value),
            ("inventory_count", str(len(inventory))),
            ("inventory_digest", _sha256_hex(_canonical_bytes(inventory))),
            ("manifest_digest", _sha256_hex(_canonical_bytes(document["manifest"]))),
            ("rollback_strategy", admitted.rollback_strategy.value),
        ),
    )
    target.apply_state_change(
        writes=(_audit_write(event),),
        journal=JournalUpdate(
            entry=JournalEntry(
                migration_id=admitted.migration_id,
                migration_class=admitted.migration_class.value,
                state=JournalState.PREPARED,
                checkpoint=0,
                manifest=_canonical_bytes(document).decode("ascii"),
            )
        ),
    )
    return resume_semantic_migration(
        target,
        admitted.migration_id,
        transform,
        actor_id=actor_id,
        occurred_at=occurred_at,
    )


def resume_semantic_migration(
    store: WorkspaceStore,
    migration_id: str,
    transform: SemanticTransform,
    *,
    actor_id: str,
    occurred_at: str,
) -> MigrationReport:
    """Continue a journaled M2 migration from its last committed checkpoint.

    Each object step deletes the old revision (``MIGRATION_SUPERSEDED``), writes the
    transformed revision and advances the checkpoint in one transaction, so resume is
    deterministic: it restarts at the first uncommitted inventory position.
    """

    target = _require_store(store, label="the migrated store")
    if not isinstance(transform, SemanticTransform):
        raise MigrationError("an M2 migration requires a SemanticTransform")
    entry = _journal_entry(target, _admit_migration_id(migration_id))
    if entry.state in TERMINAL_JOURNAL_STATES:
        raise MigrationError("the migration has already finished")
    if entry.state is JournalState.FAILED_REQUIRES_INTERVENTION:
        raise MigrationError(
            "the migration failed validation and requires intervention (snapshot rollback)"
        )
    document = _journal_document(entry)
    raw_inventory = document.get("inventory")
    evidence_raw = document.get("evidence")
    if not isinstance(raw_inventory, list) or not isinstance(evidence_raw, list):
        raise MigrationError("the journal manifest lacks its inventory or evidence")
    try:
        inventory = [
            ObjectBinding(
                workspace_id=target.workspace_id,
                object_id=UUID(str(item[0])),
                object_type=WorkspaceObjectType(str(item[1])),
                object_revision=str(item[2]),
            ).validated()
            for item in raw_inventory
        ]
        evidence: list[list[str]] = [[str(value) for value in item] for item in evidence_raw]
    except (TypeError, ValueError, IndexError) as error:
        raise MigrationError("the journal inventory or evidence is not well formed") from error
    if any(len(item) != 5 for item in evidence) or entry.checkpoint > len(inventory):
        raise MigrationError("the journal checkpoint or evidence is inconsistent")
    _require_authenticated_journal(target, entry, raw_inventory, document)
    checkpoint = entry.checkpoint
    state = entry.state
    if state in (JournalState.PREPARED, JournalState.MUTATING):
        while checkpoint < len(inventory):
            old = inventory[checkpoint]
            payload = target.get_object(old)
            new_binding = ObjectBinding(
                workspace_id=old.workspace_id,
                object_id=old.object_id,
                object_type=old.object_type,
                object_revision=_migrated_revision(old, entry.migration_id),
            ).validated()
            new_payload = transform.transform(old, payload)
            if not isinstance(new_payload, bytes) or not new_payload:
                raise MigrationError("a semantic transform must return non-empty bytes")
            evidence.append(
                [
                    str(old.object_id),
                    old.object_revision,
                    content_digest_of(payload),
                    new_binding.object_revision,
                    content_digest_of(new_payload),
                ]
            )
            checkpoint += 1
            document["evidence"] = evidence
            target.apply_state_change(
                deletions=(old,),
                writes=(ObjectWrite(binding=new_binding, payload=new_payload),),
                tombstone_reason=TombstoneReason.MIGRATION_SUPERSEDED,
                journal=_journal_update(entry, JournalState.MUTATING, checkpoint, document),
            )
        state = JournalState.VALIDATING
        target.apply_state_change(
            journal=_journal_update(entry, state, checkpoint, document),
        )
    if state is JournalState.VALIDATING:
        failure = _validate_semantic(target, inventory, evidence, transform, document)
        if failure is not None:
            document["result"] = failure
            event = prepare_next_event(
                AuditTrail(target),
                event_type=AuditEventType.MIGRATION,
                actor_id=actor_id,
                occurred_at=occurred_at,
                metadata=(
                    ("migration_id", entry.migration_id),
                    ("migration_class", entry.migration_class),
                    ("phase", JournalState.FAILED_REQUIRES_INTERVENTION.value),
                ),
            )
            target.apply_state_change(
                writes=(_audit_write(event),),
                journal=_journal_update(
                    entry, JournalState.FAILED_REQUIRES_INTERVENTION, checkpoint, document
                ),
            )
            raise MigrationValidationError(failure)
        state = JournalState.SWITCHED
        target.apply_state_change(journal=_journal_update(entry, state, checkpoint, document))
    if state is JournalState.SWITCHED:
        document["result"] = JournalState.COMPLETED.value
        manifest_document = document.get("manifest")
        if isinstance(manifest_document, dict):
            manifest_document["completed_at"] = occurred_at
            manifest_document["result"] = JournalState.COMPLETED.value
        event = prepare_next_event(
            AuditTrail(target),
            event_type=AuditEventType.MIGRATION,
            actor_id=actor_id,
            occurred_at=occurred_at,
            metadata=(
                ("migration_id", entry.migration_id),
                ("migration_class", entry.migration_class),
                ("phase", JournalState.COMPLETED.value),
                ("migrated_objects", str(len(evidence))),
                ("evidence_digest", _sha256_hex(_canonical_bytes(evidence))),
            ),
        )
        versions = target.versions
        target.apply_state_change(
            writes=(_audit_write(event),),
            journal=JournalUpdate(
                entry=JournalEntry(
                    migration_id=entry.migration_id,
                    migration_class=entry.migration_class,
                    state=JournalState.COMPLETED,
                    checkpoint=checkpoint,
                    manifest=_canonical_bytes(document).decode("ascii"),
                ),
                log_row=MigrationLogRow(
                    source_workspace_schema_version=versions.workspace_schema_version,
                    target_workspace_schema_version=versions.workspace_schema_version,
                    source_encryption_format_version=versions.encryption_format_version,
                    target_encryption_format_version=versions.encryption_format_version,
                    result=JournalState.COMPLETED.value,
                ),
            ),
        )
        state = JournalState.COMPLETED
    return MigrationReport(
        migration_id=entry.migration_id,
        migration_class=MigrationClass(entry.migration_class),
        state=state,
        migrated_objects=len(evidence),
        evidence=tuple((item[0], item[1], item[2], item[3], item[4]) for item in evidence),
    )


def _require_authenticated_journal(
    store: WorkspaceStore,
    entry: JournalEntry,
    raw_inventory: list[object],
    document: dict[str, object],
) -> None:
    """Refuse a journal whose inventory or manifest differs from its PREPARED event.

    The journal is plaintext store metadata, while the PREPARED ``migration`` event is
    encrypted and chain-linked. Resume acts only on an inventory and manifest whose
    digests that event recorded, so editing the journal cannot redirect a migration at
    other objects.
    """

    prepared = [
        dict(event.metadata)
        for event in AuditTrail(store).events()
        if event.event_type is AuditEventType.MIGRATION
        and dict(event.metadata).get("migration_id") == entry.migration_id
        and dict(event.metadata).get("phase") == JournalState.PREPARED.value
    ]
    if len(prepared) != 1:
        raise MigrationError("the migration has no single authenticated PREPARED audit event")
    recorded = prepared[0]
    if recorded.get("inventory_digest") != _sha256_hex(_canonical_bytes(raw_inventory)):
        raise MigrationError("the journal inventory differs from its authenticated audit event")
    if recorded.get("manifest_digest") != _sha256_hex(_canonical_bytes(document.get("manifest"))):
        raise MigrationError("the journal manifest differs from its authenticated audit event")


def _journal_update(
    entry: JournalEntry,
    state: JournalState,
    checkpoint: int,
    document: dict[str, object],
) -> JournalUpdate:
    return JournalUpdate(
        entry=JournalEntry(
            migration_id=entry.migration_id,
            migration_class=entry.migration_class,
            state=state,
            checkpoint=checkpoint,
            manifest=_canonical_bytes(document).decode("ascii"),
        )
    )


def _validate_semantic(
    store: WorkspaceStore,
    inventory: list[ObjectBinding],
    evidence: list[list[str]],
    transform: SemanticTransform,
    document: dict[str, object],
) -> str | None:
    manifest_document = document.get("manifest")
    if not isinstance(manifest_document, dict):
        return "the journal manifest is missing"
    raw_counts = manifest_document.get("expected_object_counts")
    raw_affected = manifest_document.get("affected_object_types")
    if not isinstance(raw_counts, list) or not isinstance(raw_affected, list):
        return "the journal manifest lacks expected object counts or affected types"
    try:
        affected = tuple(WorkspaceObjectType(str(name)) for name in raw_affected)
        expected = {str(item[0]): int(item[1]) for item in raw_counts}
    except (TypeError, ValueError, IndexError):
        return "the journal manifest counts or affected types are not well formed"
    for object_type in affected:
        if _type_count(store, object_type) != expected.get(object_type.value):
            return f"object count for {object_type.value} was not reconciled"
    if len(evidence) != len(inventory):
        return "not every inventoried object has old/new digest evidence"
    for old, item in zip(inventory, evidence, strict=True):
        new_binding = ObjectBinding(
            workspace_id=old.workspace_id,
            object_id=old.object_id,
            object_type=old.object_type,
            object_revision=item[3],
        )
        try:
            payload = store.get_object(new_binding)
        except ObjectNotFoundError:
            return "a migrated revision is missing"
        if content_digest_of(payload) != item[4]:
            return "a migrated revision digest does not match its evidence"
        if not transform.validate(new_binding, payload):
            return "semantic validation rejected a migrated revision"
    store.integrity_check()
    AuditTrail(store).verify()
    return None


# ---------------------------------------------------------------------------
# Key rotation (M3) orchestration over the CW-002 A1.6 state machine
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RotationReport:
    """The outcome of a (possibly resumed) key rotation."""

    active_key_version: int
    retired_key_versions: tuple[int, ...]
    rotated_objects: int
    resumed: bool


def rotate_workspace_key(
    store: WorkspaceStore,
    *,
    new_key_version: int,
    batch_size: int,
    actor_id: str,
    occurred_at: str,
) -> RotationReport:
    """Rotate to ``new_key_version``, or resume an interrupted rotation to it.

    The persisted A1.6 state machine makes every step resumable: an interrupted run
    leaves the prior key ``ROTATING`` (decrypt-only) and the new key ``ACTIVE``; a rerun
    re-encrypts the remaining rows, finalizes, and retires every emptied key. A
    ``KEY_ROTATION`` audit event records the begin and the completion.
    """

    target = _require_store(store, label="the rotated store")
    _admit_positive_int(new_key_version, label="new key version")
    _admit_positive_int(batch_size, label="rotation batch size")
    trail = AuditTrail(target)
    states = dict(target.key_states())
    resumed = False
    if states.get(new_key_version) is KeyState.ACTIVE and (
        KeyState.ROTATING in states.values() or KeyState.RETIRING in states.values()
    ):
        resumed = True
    elif new_key_version in states:
        raise KeyRotationError("the target key version already exists and is not resumable")
    else:
        previous = target.active_key_version
        target.begin_key_rotation(new_key_version)
        trail.append(
            event_type=AuditEventType.KEY_ROTATION,
            actor_id=actor_id,
            occurred_at=occurred_at,
            metadata=(
                ("phase", "begin"),
                ("previous_key_version", str(previous)),
                ("new_key_version", str(new_key_version)),
            ),
        )
    rotated = 0
    while True:
        moved = target.rotate_pending(max_objects=batch_size)
        if moved == 0:
            break
        rotated += moved
    target.finalize_key_rotation()
    retired: list[int] = []
    for key_version, state in target.key_states():
        if state is KeyState.RETIRING:
            target.retire_key_version(key_version)
            retired.append(key_version)
    trail.append(
        event_type=AuditEventType.KEY_ROTATION,
        actor_id=actor_id,
        occurred_at=occurred_at,
        metadata=(
            ("phase", "completed"),
            ("active_key_version", str(target.active_key_version)),
            ("retired_key_versions", ",".join(str(item) for item in retired) or "none"),
            ("rotated_objects", str(rotated)),
            ("resumed", "true" if resumed else "false"),
        ),
    )
    return RotationReport(
        active_key_version=target.active_key_version,
        retired_key_versions=tuple(retired),
        rotated_objects=rotated,
        resumed=resumed,
    )


# ---------------------------------------------------------------------------
# Deletion reconciliation across derived state
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeletionReconciliationReport:
    """Stale derived records removed so no deleted source survives in derived state."""

    removed_edges: tuple[UUID, ...]
    removed_nodes: tuple[UUID, ...]
    removed_views: tuple[UUID, ...]
    removed_collections: tuple[UUID, ...]
    removed_exports: tuple[UUID, ...]


def _ids_of(store: WorkspaceStore, object_type: WorkspaceObjectType) -> tuple[UUID, ...]:
    return tuple(
        sorted({object_id for object_id, _ in store.object_revisions(object_type)}, key=str)
    )


def reconcile_deletions(
    store: WorkspaceStore,
    *,
    actor_id: str,
    occurred_at: str,
) -> DeletionReconciliationReport:
    """Remove derived graph, view, dataset and export records a deletion made stale.

    Only records whose owning module reports them stale are removed, each through
    that module's own audited delete path; a record that fails for any other reason
    is refused rather than silently deleted.
    """

    target = _require_store(store, label="the reconciled store")
    if target.role is not StoreRole.LIVE:
        raise StoreRoleError("deletion reconciliation runs on a live store")
    trail = AuditTrail(target)
    removed_edges: list[UUID] = []
    for edge_id in _ids_of(target, WorkspaceObjectType.GRAPH_EDGE):
        try:
            read_edge(target, edge_id)
        except GraphStaleError:
            delete_edge(target, trail, edge_id, actor_id, occurred_at)
            removed_edges.append(edge_id)
    removed_nodes: list[UUID] = []
    for node_id in _ids_of(target, WorkspaceObjectType.GRAPH_NODE):
        try:
            read_node(target, node_id)
        except GraphStaleError:
            delete_node(target, trail, node_id, actor_id, occurred_at)
            removed_nodes.append(node_id)
    removed_views: list[UUID] = []
    for view_id in _ids_of(target, WorkspaceObjectType.GRAPH_VIEW):
        try:
            read_view(target, view_id)
        except GraphStaleError:
            binding = view_binding(target.workspace_id, view_id)
            for doomed in (binding, provenance_binding_for(binding)):
                try:
                    trail.record_object_deletion(
                        binding=doomed, actor_id=actor_id, occurred_at=occurred_at
                    )
                except ObjectNotFoundError:
                    continue
            removed_views.append(view_id)
    removed_collections: list[UUID] = []
    for collection_id in _ids_of(target, WorkspaceObjectType.WORKSPACE_DATASET_COLLECTION):
        try:
            read_dataset_collection(target, collection_id)
        except DatasetCollectionStaleError:
            delete_dataset_collection(target, trail, collection_id, actor_id, occurred_at)
            removed_collections.append(collection_id)
    removed_exports: list[UUID] = []
    for export_id in _ids_of(target, WorkspaceObjectType.WORKSPACE_EXPORT_MANIFEST):
        try:
            read_export_manifest(target, export_id)
        except ExportStagingStaleError:
            delete_export_manifest(target, trail, export_id, actor_id, occurred_at)
            removed_exports.append(export_id)
    trail.verify()
    return DeletionReconciliationReport(
        removed_edges=tuple(removed_edges),
        removed_nodes=tuple(removed_nodes),
        removed_views=tuple(removed_views),
        removed_collections=tuple(removed_collections),
        removed_exports=tuple(removed_exports),
    )


__all__ = [
    "BACKUP_MAGIC",
    "DELETION_POLICY",
    "BackupManifest",
    "BackupObjectEntry",
    "DeletionPolicyEntry",
    "DeletionReconciliationReport",
    "MigrationClass",
    "MigrationManifest",
    "MigrationReport",
    "PreflightReport",
    "PromotionReport",
    "QuarantineReport",
    "RollbackReport",
    "RollbackStrategy",
    "RotationReport",
    "SemanticTransform",
    "VerifiedBackup",
    "begin_semantic_migration",
    "create_backup",
    "expected_object_counts",
    "migrate_schema_to_current",
    "open_backup",
    "preflight",
    "promote_quarantine",
    "read_backup_manifest",
    "reconcile_deletions",
    "restore_backup_to_quarantine",
    "resume_semantic_migration",
    "rollback_to_quarantine",
    "rotate_workspace_key",
]
