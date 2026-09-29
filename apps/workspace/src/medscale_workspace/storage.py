"""Encrypted local workspace store for CW-002.

This is the only Workspace module permitted to import ``sqlite3``, the only module
permitted to open the store, and the only module that may hand a store path to
``sqlite3.connect`` — and that path must come from
:func:`medscale_workspace.store_path.resolve_workspace_store_path`.

Behaviour fixed by ADR-0039 as amended by A1:

* sensitive payloads are stored only as AES-256-GCM envelopes whose associated data
  binds workspace, object, type, immutable revision, key version and format version;
* the key-version state machine is ``ACTIVE -> ROTATING -> RETIRING -> RETIRED``,
  new writes use the single active key, prior keys stay decrypt-only while rows
  migrate, retired keys cannot write again, and an interrupted rotation resumes
  deterministically because its state is persisted;
* durability and integrity pragmas are asserted, not assumed: ``journal_mode=WAL``,
  ``synchronous=FULL``, ``foreign_keys=ON``, ``secure_delete=ON`` and an explicit
  busy timeout;
* no plaintext fallback exists: an unavailable key provider, a missing key version,
  an unsupported version tuple or any authentication failure aborts the operation.

Known limits, recorded rather than hidden:

* ``secure_delete=ON`` is defense in depth only and is never proof of cryptographic
  erasure (A1.11);
* AES-256-GCM does not defeat a valid historical whole-store rollback performed with
  a still-valid key, and CW-002 implements no rollback detector (A1.5);
* SQLite structural data and the explicitly declared plaintext metadata listed in
  :meth:`WorkspaceStore.plaintext_metadata_scope` remain visible in a copied store
  (A1.10);
* CW-018 (Issue #520) adds workspace schema 2: a deletion-tombstone ledger written in
  the same transaction as every deletion, a migration checkpoint journal, and an
  explicit store role (``LIVE`` or ``QUARANTINE``). A schema-1 store, a store holding
  an unfinished journaled migration, and a quarantine store are never opened in
  normal live mode; the manifest/preflight/rollback policy lives in ``lifecycle.py``.
* CW-019 (Issue #523) adds workspace schema 3: a keyed integrity seal (HMAC-SHA-256
  under a seal key derived from the root secret) over every metadata table, the
  key-version state, tombstones, the migration journal and log, and a digest of every
  object row. It is rewritten inside every mutating transaction and verified on every
  open, so editing, deleting or inserting rows outside this API fails closed. It does
  not detect replacement of the whole store with an older consistent copy (A1.5).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from medscale_workspace.aead import (
    KEY_SIZE_BYTES,
    decrypt_payload,
    encrypt_payload,
    parse_envelope_header,
)
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.errors import (
    EnvelopeFormatError,
    KeyMaterialUnavailableError,
    KeyRotationError,
    KeyStateError,
    ObjectNotFoundError,
    StoreConflictError,
    StoreIntegrityError,
    StoreMigrationRequiredError,
    StoreRoleError,
    StoreSealError,
    StoreVersionError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.keyprovider import KeyProvider, new_salt
from medscale_workspace.store_path import resolve_workspace_store_path
from medscale_workspace.versions import (
    ENCRYPTION_FORMAT_VERSION,
    INITIALIZATION_MIGRATION_CLASS,
    INITIALIZATION_MIGRATION_ID,
    MAXIMUM_READABLE_WORKSPACE_SCHEMA,
    MIGRATABLE_WORKSPACE_SCHEMAS,
    MINIMUM_READABLE_WORKSPACE_SCHEMA,
    POLICY_VERSION,
    SCHEMA_V2_MIGRATION_CLASS,
    SCHEMA_V2_MIGRATION_ID,
    SCHEMA_V3_MIGRATION_CLASS,
    SCHEMA_V3_MIGRATION_ID,
    WORKSPACE_SCHEMA_VERSION,
    unreadable_schema_reason,
)

DEFAULT_BUSY_TIMEOUT_MS = 5000
INITIAL_KEY_VERSION = 1

_METADATA_KEYS = (
    "application_version",
    "workspace_schema_version",
    "minimum_readable_workspace_schema",
    "maximum_readable_workspace_schema",
    "policy_version",
    "encryption_format_version",
    "workspace_id",
    "store_role",
)
_RESTORED_BACKUP_METADATA_KEY = "restored_backup_id"
_SEAL_METADATA_KEY = "integrity_seal"
_SEAL_SALT_METADATA_KEY = "seal_salt"
_SEAL_FORMAT = "mesc-clinical-workspace-store-seal/1"
_SCHEMA_V2 = 2

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE store_metadata (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE key_versions (
        key_version INTEGER PRIMARY KEY,
        state TEXT NOT NULL CHECK (state IN ('ACTIVE', 'ROTATING', 'RETIRING', 'RETIRED')),
        salt BLOB NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX key_versions_single_active ON key_versions(state)
        WHERE state = 'ACTIVE'
    """,
    """
    CREATE TABLE objects (
        workspace_id TEXT NOT NULL,
        object_id TEXT NOT NULL,
        object_type TEXT NOT NULL,
        object_revision TEXT NOT NULL,
        key_version INTEGER NOT NULL REFERENCES key_versions(key_version),
        encryption_format_version INTEGER NOT NULL,
        envelope BLOB NOT NULL,
        PRIMARY KEY (workspace_id, object_id, object_revision)
    )
    """,
    """
    CREATE TABLE migration_log (
        migration_id TEXT PRIMARY KEY,
        migration_class TEXT NOT NULL,
        source_workspace_schema_version INTEGER NOT NULL,
        target_workspace_schema_version INTEGER NOT NULL,
        source_encryption_format_version INTEGER NOT NULL,
        target_encryption_format_version INTEGER NOT NULL,
        result TEXT NOT NULL
    )
    """,
)

_SCHEMA_V2_STATEMENTS = (
    """
    CREATE TABLE deletion_tombstones (
        workspace_id TEXT NOT NULL,
        object_id TEXT NOT NULL,
        object_type TEXT NOT NULL,
        object_revision TEXT NOT NULL,
        reason TEXT NOT NULL CHECK (
            reason IN ('USER_DELETION', 'MIGRATION_SUPERSEDED', 'ROLLBACK_DISCARDED')
        ),
        PRIMARY KEY (workspace_id, object_id, object_revision)
    )
    """,
    """
    CREATE TABLE migration_journal (
        migration_id TEXT PRIMARY KEY,
        migration_class TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN (
            'NOT_STARTED', 'PREPARED', 'MUTATING', 'VALIDATING', 'SWITCHED',
            'ROLLING_BACK', 'COMPLETED', 'ROLLED_BACK', 'FAILED_REQUIRES_INTERVENTION'
        )),
        checkpoint INTEGER NOT NULL CHECK (checkpoint >= 0),
        manifest TEXT NOT NULL
    )
    """,
)

_OBJECT_COLUMNS = "workspace_id, object_id, object_type, object_revision, key_version"


class StoreRole(StrEnum):
    """Whether a store is the live workspace or a quarantined restore target."""

    LIVE = "LIVE"
    QUARANTINE = "QUARANTINE"


class TombstoneReason(StrEnum):
    """Why an object revision left the store; restore and rollback honour it."""

    USER_DELETION = "USER_DELETION"
    MIGRATION_SUPERSEDED = "MIGRATION_SUPERSEDED"
    ROLLBACK_DISCARDED = "ROLLBACK_DISCARDED"


class JournalState(StrEnum):
    """Migration checkpoint states (migration contract section 8, plus ROLLED_BACK)."""

    NOT_STARTED = "NOT_STARTED"
    PREPARED = "PREPARED"
    MUTATING = "MUTATING"
    VALIDATING = "VALIDATING"
    SWITCHED = "SWITCHED"
    ROLLING_BACK = "ROLLING_BACK"
    COMPLETED = "COMPLETED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED_REQUIRES_INTERVENTION = "FAILED_REQUIRES_INTERVENTION"


TERMINAL_JOURNAL_STATES = frozenset({JournalState.COMPLETED, JournalState.ROLLED_BACK})


class KeyState(StrEnum):
    """The CW-002 key-version state machine (ADR-0039 amendment A1.6)."""

    ACTIVE = "ACTIVE"
    ROTATING = "ROTATING"
    RETIRING = "RETIRING"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class ObjectWrite:
    """One immutable object revision and the sensitive payload bound to it."""

    binding: ObjectBinding
    payload: bytes


@dataclass(frozen=True, slots=True)
class Tombstone:
    """The recorded absence of one object revision and why it was removed."""

    object_id: UUID
    object_type: WorkspaceObjectType
    object_revision: str
    reason: TombstoneReason


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One migration checkpoint row; the manifest holds identities, counts and digests."""

    migration_id: str
    migration_class: str
    state: JournalState
    checkpoint: int
    manifest: str


@dataclass(frozen=True, slots=True)
class MigrationLogRow:
    """A completed migration's version transition, appended to ``migration_log``."""

    source_workspace_schema_version: int
    target_workspace_schema_version: int
    source_encryption_format_version: int
    target_encryption_format_version: int
    result: str


@dataclass(frozen=True, slots=True)
class JournalUpdate:
    """A journal transition committed atomically with the objects it describes."""

    entry: JournalEntry
    log_row: MigrationLogRow | None = None


@dataclass(frozen=True, slots=True)
class SnapshotObject:
    """One decrypted object revision captured by a consistent store snapshot."""

    binding: ObjectBinding
    payload: bytes


@dataclass(frozen=True, slots=True)
class StoreSnapshot:
    """A transaction-consistent plaintext view of every object and tombstone."""

    versions: StoreVersions
    role: StoreRole
    objects: tuple[SnapshotObject, ...]
    tombstones: tuple[Tombstone, ...]


@dataclass(frozen=True, slots=True)
class StoreVersions:
    """The recorded version tuple of a workspace store."""

    application_version: str
    workspace_schema_version: int
    minimum_readable_workspace_schema: int
    maximum_readable_workspace_schema: int
    policy_version: str
    encryption_format_version: int


@dataclass(frozen=True, slots=True)
class StorePragmas:
    """The effective pragma values a store is running under."""

    journal_mode: str
    synchronous: int
    foreign_keys: int
    secure_delete: int
    busy_timeout_ms: int


def _read_metadata(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute("SELECT name, value FROM store_metadata").fetchall()
    return {str(name): str(value) for name, value in rows}


def _schema_present(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'store_metadata'"
    ).fetchone()
    return row is not None


def _existing_table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return tuple(str(name) for (name,) in rows)


def _required_metadata(metadata: dict[str, str], name: str) -> str:
    value = metadata.get(name)
    if value is None:
        raise StoreVersionError(f"recorded store metadata is missing {name!r}")
    return value


def _required_int_metadata(metadata: dict[str, str], name: str) -> int:
    raw = _required_metadata(metadata, name)
    try:
        return int(raw)
    except ValueError as error:
        raise StoreVersionError(f"recorded store metadata {name!r} is not an integer") from error


def _recorded_versions(
    metadata: dict[str, str],
    *,
    allow_migratable: bool = False,
) -> StoreVersions:
    versions = StoreVersions(
        application_version=_required_metadata(metadata, "application_version"),
        workspace_schema_version=_required_int_metadata(metadata, "workspace_schema_version"),
        minimum_readable_workspace_schema=_required_int_metadata(
            metadata, "minimum_readable_workspace_schema"
        ),
        maximum_readable_workspace_schema=_required_int_metadata(
            metadata, "maximum_readable_workspace_schema"
        ),
        policy_version=_required_metadata(metadata, "policy_version"),
        encryption_format_version=_required_int_metadata(metadata, "encryption_format_version"),
    )
    if versions.encryption_format_version != ENCRYPTION_FORMAT_VERSION:
        raise StoreVersionError("recorded encryption format version is not supported here")
    recorded = versions.workspace_schema_version
    if allow_migratable and recorded in MIGRATABLE_WORKSPACE_SCHEMAS:
        return versions
    reason = unreadable_schema_reason(recorded)
    if reason is not None:
        if recorded in MIGRATABLE_WORKSPACE_SCHEMAS:
            raise StoreMigrationRequiredError(reason)
        raise StoreVersionError(reason)
    return versions


def _seal_rows(connection: sqlite3.Connection, query: str) -> list[list[object]]:
    rows = connection.execute(query).fetchall()
    admitted: list[list[object]] = []
    for row in rows:
        admitted.append([value.hex() if isinstance(value, bytes) else value for value in row])
    return admitted


def _compute_seal(connection: sqlite3.Connection, seal_key: bytes) -> str:
    """Return the keyed seal over every store table, excluding the seal row itself."""

    objects_digest = hashlib.sha256()
    for row in connection.execute(
        "SELECT workspace_id, object_id, object_type, object_revision, key_version, "
        "encryption_format_version, envelope FROM objects "
        "ORDER BY workspace_id, object_id, object_revision"
    ):
        *identity, envelope = row
        line = json.dumps(
            [*identity, hashlib.sha256(bytes(envelope)).hexdigest()],
            separators=(",", ":"),
            ensure_ascii=True,
        )
        objects_digest.update(line.encode("ascii") + b"\n")
    document = {
        "format": _SEAL_FORMAT,
        "metadata": _seal_rows(
            connection,
            "SELECT name, value FROM store_metadata WHERE name <> "
            f"'{_SEAL_METADATA_KEY}' ORDER BY name",
        ),
        "key_versions": _seal_rows(
            connection, "SELECT key_version, state, salt FROM key_versions ORDER BY key_version"
        ),
        "tombstones": _seal_rows(
            connection,
            "SELECT workspace_id, object_id, object_type, object_revision, reason "
            "FROM deletion_tombstones ORDER BY workspace_id, object_id, object_revision",
        ),
        "journal": _seal_rows(
            connection,
            "SELECT migration_id, migration_class, state, checkpoint, manifest "
            "FROM migration_journal ORDER BY migration_id",
        ),
        "migration_log": _seal_rows(
            connection,
            "SELECT migration_id, migration_class, source_workspace_schema_version, "
            "target_workspace_schema_version, source_encryption_format_version, "
            "target_encryption_format_version, result FROM migration_log ORDER BY migration_id",
        ),
        "objects": objects_digest.hexdigest(),
    }
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hmac.new(seal_key, canonical, hashlib.sha256).hexdigest()


def _write_seal(connection: sqlite3.Connection, seal_key: bytes) -> None:
    connection.execute(
        "INSERT INTO store_metadata (name, value) VALUES (?, ?) "
        "ON CONFLICT (name) DO UPDATE SET value = excluded.value",
        (_SEAL_METADATA_KEY, _compute_seal(connection, seal_key)),
    )


def _verify_seal(connection: sqlite3.Connection, seal_key: bytes) -> None:
    row = connection.execute(
        "SELECT value FROM store_metadata WHERE name = ?",
        (_SEAL_METADATA_KEY,),
    ).fetchone()
    if row is None:
        raise StoreSealError("the store integrity seal is missing")
    if not hmac.compare_digest(str(row[0]), _compute_seal(connection, seal_key)):
        raise StoreSealError(
            "the store integrity seal does not match the store contents; the store was "
            "modified outside the store API"
        )


def _admit_seal_key(key: object) -> bytes:
    if not isinstance(key, bytes) or len(key) != KEY_SIZE_BYTES:
        raise KeyMaterialUnavailableError(
            "the key provider returned seal key material of an unusable size"
        )
    return key


def _recorded_seal_salt(metadata: dict[str, str]) -> bytes:
    raw = metadata.get(_SEAL_SALT_METADATA_KEY)
    if raw is None:
        raise StoreSealError("the store integrity seal salt is missing")
    try:
        salt = bytes.fromhex(raw)
    except ValueError as error:
        raise StoreSealError("the store integrity seal salt is not hex") from error
    if len(salt) != 16:
        raise StoreSealError("the store integrity seal salt has the wrong size")
    return salt


def _recorded_role(metadata: dict[str, str]) -> StoreRole:
    raw = _required_metadata(metadata, "store_role")
    try:
        return StoreRole(raw)
    except ValueError as error:
        raise StoreIntegrityError("recorded store role is not an admitted role") from error


def _unfinished_journal(connection: sqlite3.Connection) -> tuple[str, ...]:
    terminal = tuple(sorted(state.value for state in TERMINAL_JOURNAL_STATES))
    rows = connection.execute(
        "SELECT migration_id FROM migration_journal WHERE state NOT IN (?, ?) "
        "ORDER BY migration_id",
        terminal,
    ).fetchall()
    return tuple(str(migration_id) for (migration_id,) in rows)


def _apply_pragmas(connection: sqlite3.Connection, busy_timeout_ms: int) -> None:
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA secure_delete = ON")
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")


def _read_pragmas(connection: sqlite3.Connection) -> StorePragmas:
    return StorePragmas(
        journal_mode=str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower(),
        synchronous=int(connection.execute("PRAGMA synchronous").fetchone()[0]),
        foreign_keys=int(connection.execute("PRAGMA foreign_keys").fetchone()[0]),
        secure_delete=int(connection.execute("PRAGMA secure_delete").fetchone()[0]),
        busy_timeout_ms=int(connection.execute("PRAGMA busy_timeout").fetchone()[0]),
    )


def _admitted_pragmas(pragmas: StorePragmas, busy_timeout_ms: int) -> None:
    """Fail closed unless every durability/integrity pragma is effectively applied."""

    if pragmas.journal_mode != "wal":
        raise StoreIntegrityError("the workspace store could not enter WAL journal mode")
    if pragmas.synchronous != 2:
        raise StoreIntegrityError("the workspace store is not running with synchronous=FULL")
    if pragmas.foreign_keys != 1:
        raise StoreIntegrityError("the workspace store is not running with foreign_keys=ON")
    if pragmas.secure_delete != 1:
        raise StoreIntegrityError("the workspace store is not running with secure_delete=ON")
    if pragmas.busy_timeout_ms != busy_timeout_ms:
        raise StoreIntegrityError("the workspace store did not adopt the explicit busy timeout")


class WorkspaceStore:
    """A single-workspace, single-file encrypted store for CW-002."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        path: str,
        workspace_id: UUID,
        key_provider: KeyProvider,
        versions: StoreVersions,
        salt_by_version: dict[int, bytes],
        role: StoreRole = StoreRole.LIVE,
        maintenance: bool = False,
        seal_key: bytes | None = None,
    ) -> None:
        self._connection = connection
        self._role = role
        self._maintenance = maintenance
        self._seal_key = seal_key
        self._path = path
        self._workspace_id = workspace_id
        self._key_provider = key_provider
        self._versions = versions
        self._salt_by_version = salt_by_version
        self._active_key_version = 0
        self._active_key = b""
        self._refresh_active_key()

    @classmethod
    def open(
        cls,
        *,
        store_root: str,
        workspace_id: UUID,
        key_provider: KeyProvider,
        application_version: str,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
        role: StoreRole = StoreRole.LIVE,
    ) -> WorkspaceStore:
        """Open (or initialize) the store in normal mode, failing closed before any write.

        Normal mode refuses a schema-1 store that still needs the CW-018 migration, a
        store holding an unfinished journaled migration, and a store whose recorded
        role differs from ``role``.
        """

        return cls._open(
            store_root=store_root,
            workspace_id=workspace_id,
            key_provider=key_provider,
            application_version=application_version,
            busy_timeout_ms=busy_timeout_ms,
            role=role,
            maintenance=False,
        )

    @classmethod
    def open_for_maintenance(
        cls,
        *,
        store_root: str,
        workspace_id: UUID,
        key_provider: KeyProvider,
        application_version: str,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> WorkspaceStore:
        """Open an existing live store for migration, resume, or recovery only.

        Maintenance mode admits a migratable schema-1 store and an unfinished journal
        so the CW-018 lifecycle engine can finish, resume or roll back; it never
        initializes a new store.
        """

        return cls._open(
            store_root=store_root,
            workspace_id=workspace_id,
            key_provider=key_provider,
            application_version=application_version,
            busy_timeout_ms=busy_timeout_ms,
            role=StoreRole.LIVE,
            maintenance=True,
        )

    @classmethod
    def _open(
        cls,
        *,
        store_root: str,
        workspace_id: UUID,
        key_provider: KeyProvider,
        application_version: str,
        busy_timeout_ms: int,
        role: StoreRole,
        maintenance: bool,
    ) -> WorkspaceStore:
        if not isinstance(application_version, str) or not application_version.strip():
            raise StoreVersionError("application version must be recorded explicitly")
        if not isinstance(workspace_id, UUID):
            raise StoreIntegrityError("workspace id must be a UUID value")
        if not isinstance(busy_timeout_ms, int) or busy_timeout_ms <= 0:
            raise StoreIntegrityError("busy timeout must be a positive integer")
        if not isinstance(role, StoreRole):
            raise StoreRoleError("store role must be an admitted StoreRole value")
        key_provider.require_available()
        seal_key: bytes | None = None
        path = resolve_workspace_store_path(store_root, workspace_id)
        connection = sqlite3.connect(path, isolation_level=None, timeout=busy_timeout_ms / 1000)
        try:
            _apply_pragmas(connection, busy_timeout_ms)
            _admitted_pragmas(_read_pragmas(connection), busy_timeout_ms)
            if _schema_present(connection):
                metadata = _read_metadata(connection)
                versions = _recorded_versions(metadata, allow_migratable=maintenance)
                if _required_metadata(metadata, "workspace_id") != str(workspace_id):
                    raise WorkspaceIsolationError(
                        "the store belongs to a different workspace than the opened id"
                    )
                if versions.workspace_schema_version == WORKSPACE_SCHEMA_VERSION:
                    seal_key = _admit_seal_key(
                        key_provider.seal_key(
                            workspace_id=workspace_id,
                            salt=_recorded_seal_salt(metadata),
                        )
                    )
                    _verify_seal(connection, seal_key)
                if versions.workspace_schema_version >= 2:
                    recorded_role = _recorded_role(metadata)
                    if recorded_role is not role:
                        raise StoreRoleError(
                            f"the store is recorded as {recorded_role.value}, not {role.value}"
                        )
                    if _unfinished_journal(connection) and not maintenance:
                        raise StoreMigrationRequiredError(
                            "the store holds an unfinished migration and cannot open in "
                            "normal mode; resume or roll it back in maintenance mode"
                        )
            else:
                if maintenance:
                    raise StoreIntegrityError(
                        "maintenance mode opens an existing store only; it never initializes"
                    )
                existing_tables = _existing_table_names(connection)
                if existing_tables:
                    raise StoreIntegrityError(
                        "the target file is an existing database that is not a CW-002 "
                        "workspace store; adopting it is refused"
                    )
                versions = StoreVersions(
                    application_version=application_version,
                    workspace_schema_version=WORKSPACE_SCHEMA_VERSION,
                    minimum_readable_workspace_schema=MINIMUM_READABLE_WORKSPACE_SCHEMA,
                    maximum_readable_workspace_schema=MAXIMUM_READABLE_WORKSPACE_SCHEMA,
                    policy_version=POLICY_VERSION,
                    encryption_format_version=ENCRYPTION_FORMAT_VERSION,
                )
                seal_salt = new_salt()
                seal_key = _admit_seal_key(
                    key_provider.seal_key(workspace_id=workspace_id, salt=seal_salt)
                )
                cls._initialise(
                    connection,
                    workspace_id=workspace_id,
                    versions=versions,
                    role=role,
                    seal_salt=seal_salt,
                    seal_key=seal_key,
                )
            salt_by_version = cls._read_salts(connection)
            store = cls(
                connection,
                path=path,
                workspace_id=workspace_id,
                key_provider=key_provider,
                versions=versions,
                salt_by_version=salt_by_version,
                role=role,
                maintenance=maintenance,
                seal_key=seal_key,
            )
        except BaseException:
            connection.close()
            raise
        return store

    @staticmethod
    def _initialise(
        connection: sqlite3.Connection,
        *,
        workspace_id: UUID,
        versions: StoreVersions,
        role: StoreRole,
        seal_salt: bytes,
        seal_key: bytes,
    ) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA_STATEMENTS + _SCHEMA_V2_STATEMENTS:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO key_versions (key_version, state, salt) VALUES (?, ?, ?)",
                (INITIAL_KEY_VERSION, KeyState.ACTIVE.value, new_salt()),
            )
            metadata = {
                "application_version": versions.application_version,
                "workspace_schema_version": str(versions.workspace_schema_version),
                "minimum_readable_workspace_schema": str(
                    versions.minimum_readable_workspace_schema
                ),
                "maximum_readable_workspace_schema": str(
                    versions.maximum_readable_workspace_schema
                ),
                "policy_version": versions.policy_version,
                "encryption_format_version": str(versions.encryption_format_version),
                "workspace_id": str(workspace_id),
                "store_role": role.value,
            }
            for name in _METADATA_KEYS:
                connection.execute(
                    "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                    (name, metadata[name]),
                )
            connection.execute(
                "INSERT INTO migration_log ("
                "migration_id, migration_class, source_workspace_schema_version, "
                "target_workspace_schema_version, source_encryption_format_version, "
                "target_encryption_format_version, result"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    INITIALIZATION_MIGRATION_ID,
                    INITIALIZATION_MIGRATION_CLASS,
                    0,
                    versions.workspace_schema_version,
                    0,
                    versions.encryption_format_version,
                    "COMPLETED",
                ),
            )
            connection.execute(
                "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                (_SEAL_SALT_METADATA_KEY, seal_salt.hex()),
            )
            _write_seal(connection, seal_key)
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")

    @staticmethod
    def _read_salts(connection: sqlite3.Connection) -> dict[int, bytes]:
        rows = connection.execute("SELECT key_version, salt FROM key_versions").fetchall()
        if not rows:
            raise StoreIntegrityError("the workspace store has no key version state")
        salt_by_version: dict[int, bytes] = {}
        for key_version, salt in rows:
            salt_by_version[int(key_version)] = bytes(salt)
        return salt_by_version

    def _refresh_active_key(self) -> None:
        rows = self._connection.execute(
            "SELECT key_version FROM key_versions WHERE state = ?",
            (KeyState.ACTIVE.value,),
        ).fetchall()
        if len(rows) != 1:
            raise StoreIntegrityError("the workspace store must have exactly one active key")
        active = int(rows[0][0])
        self._active_key_version = active
        self._active_key = self._derive_key(active)

    def _derive_key(self, key_version: int) -> bytes:
        salt = self._salt_by_version.get(key_version)
        if salt is None:
            raise KeyStateError(f"key version {key_version} is not a known key version")
        key = self._key_provider.key_for_version(
            workspace_id=self._workspace_id,
            key_version=key_version,
            salt=salt,
        )
        if len(key) != KEY_SIZE_BYTES:
            raise KeyMaterialUnavailableError(
                "the key provider returned key material of an unusable size"
            )
        return key

    def _require_workspace(self, binding: ObjectBinding) -> None:
        if binding.workspace_id != self._workspace_id:
            raise WorkspaceIsolationError("object binding belongs to a different workspace")

    @property
    def store_path(self) -> str:
        return self._path

    @property
    def workspace_id(self) -> UUID:
        return self._workspace_id

    @property
    def versions(self) -> StoreVersions:
        return self._versions

    @property
    def active_key_version(self) -> int:
        return self._active_key_version

    @property
    def role(self) -> StoreRole:
        return self._role

    @property
    def maintenance(self) -> bool:
        return self._maintenance

    @property
    def restored_backup_id(self) -> UUID | None:
        """The backup a quarantine store was restored from, or ``None``."""

        row = self._connection.execute(
            "SELECT value FROM store_metadata WHERE name = ?",
            (_RESTORED_BACKUP_METADATA_KEY,),
        ).fetchone()
        if row is None:
            return None
        try:
            return UUID(str(row[0]))
        except ValueError as error:
            raise StoreIntegrityError("recorded restored backup id is not a UUID") from error

    def _verify_before_change(self) -> None:
        """Refuse to mutate a store whose seal no longer matches (schema 3 only).

        Called right after ``BEGIN IMMEDIATE``, while this connection holds the write
        lock, so a change made to the file by anything else since the last commit is
        detected before this transaction can reseal over it.
        """

        if self._versions.workspace_schema_version != WORKSPACE_SCHEMA_VERSION:
            return
        if self._seal_key is None:
            raise StoreSealError("the store integrity seal key is unavailable")
        _verify_seal(self._connection, self._seal_key)

    def _reseal(self) -> None:
        """Rewrite the integrity seal inside the current transaction (schema 3 only)."""

        if self._versions.workspace_schema_version != WORKSPACE_SCHEMA_VERSION:
            return
        if self._seal_key is None:
            raise StoreSealError("the store integrity seal key is unavailable")
        _write_seal(self._connection, self._seal_key)

    def _require_current_schema(self) -> None:
        if self._versions.workspace_schema_version != WORKSPACE_SCHEMA_VERSION:
            raise StoreMigrationRequiredError(
                "this operation requires the current workspace schema; run the CW-018 "
                "migration first"
            )

    def _require_writable(self) -> None:
        self._require_current_schema()
        if self._role is not StoreRole.LIVE:
            raise StoreRoleError(
                "a quarantine store is read-only apart from its single restore import"
            )

    def pragmas(self) -> StorePragmas:
        return _read_pragmas(self._connection)

    def plaintext_metadata_scope(self) -> tuple[str, ...]:
        """Return the metadata that intentionally remains visible in a copied store."""

        return (
            "sqlite_structural_metadata",
            "store_metadata_versions",
            "workspace_id",
            "object_ids_and_types",
            "object_revision_ids",
            "object_key_version",
            "object_encryption_format_version",
            "envelope_header_magic_format_and_key_version",
            "envelope_ciphertext_byte_size",
            "key_version_states",
            "key_derivation_salts",
            "store_role",
            "restored_backup_id",
            "deletion_tombstone_ids_types_revisions_and_reasons",
            "migration_journal_ids_states_checkpoints_and_manifests",
            "migration_log_version_transitions",
            "integrity_seal_and_seal_salt",
        )

    def key_states(self) -> tuple[tuple[int, KeyState], ...]:
        rows = self._connection.execute(
            "SELECT key_version, state FROM key_versions ORDER BY key_version"
        ).fetchall()
        return tuple((int(key_version), KeyState(str(state))) for key_version, state in rows)

    def key_state(self, key_version: int) -> KeyState:
        for known_version, state in self.key_states():
            if known_version == key_version:
                return state
        raise KeyStateError(f"key version {key_version} is not a known key version")

    def object_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) FROM objects").fetchone()
        return int(row[0])

    def object_revisions(
        self,
        object_type: WorkspaceObjectType,
    ) -> tuple[tuple[UUID, str], ...]:
        """List ``(object_id, object_revision)`` for one admitted object type.

        Read-only, workspace-scoped and deterministically ordered. CW-003 uses it to
        enumerate the append-only audit spine; it exposes no payload content and no
        key material.
        """

        rows = self._connection.execute(
            "SELECT object_id, object_revision FROM objects WHERE workspace_id = ? "
            "AND object_type = ? ORDER BY object_id, object_revision",
            (str(self._workspace_id), object_type.value),
        ).fetchall()
        return tuple((UUID(str(object_id)), str(revision)) for object_id, revision in rows)

    def _prepare_writes(
        self,
        writes: tuple[ObjectWrite, ...],
    ) -> list[tuple[ObjectBinding, bytes]]:
        prepared: list[tuple[ObjectBinding, bytes]] = []
        for write in writes:
            binding = write.binding.validated()
            self._require_workspace(binding)
            if not isinstance(write.payload, bytes) or not write.payload:
                raise StoreIntegrityError("object payload must be non-empty bytes")
            envelope = encrypt_payload(
                key=self._active_key,
                plaintext=write.payload,
                associated_data=binding.canonical_associated_data(
                    key_version=self._active_key_version,
                    encryption_format_version=self._versions.encryption_format_version,
                ),
                key_version=self._active_key_version,
            )
            prepared.append((binding, envelope))
        return prepared

    def _insert_object(self, binding: ObjectBinding, envelope: bytes) -> None:
        self._connection.execute(
            "INSERT INTO objects ("
            "workspace_id, object_id, object_type, object_revision, key_version, "
            "encryption_format_version, envelope"
            ") VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(binding.workspace_id),
                str(binding.object_id),
                binding.object_type.value,
                binding.object_revision,
                self._active_key_version,
                self._versions.encryption_format_version,
                envelope,
            ),
        )
        if self._versions.workspace_schema_version >= 2:
            self._connection.execute(
                "DELETE FROM deletion_tombstones WHERE workspace_id = ? AND object_id = ? "
                "AND object_revision = ?",
                (str(binding.workspace_id), str(binding.object_id), binding.object_revision),
            )

    def _delete_with_tombstone(self, binding: ObjectBinding, reason: TombstoneReason) -> int:
        cursor = self._connection.execute(
            "DELETE FROM objects WHERE workspace_id = ? AND object_id = ? AND object_revision = ?",
            (str(binding.workspace_id), str(binding.object_id), binding.object_revision),
        )
        deleted = int(cursor.rowcount)
        if deleted > 0:
            self._insert_tombstone(binding, reason)
        return deleted

    def _insert_tombstone(self, binding: ObjectBinding, reason: TombstoneReason) -> None:
        """Record a revision's absence; a USER_DELETION reason is never weakened.

        A later tombstone for the same revision may strengthen its reason to
        ``USER_DELETION`` but can never replace ``USER_DELETION`` with a migration or
        rollback reason, so no subsequent write can make a user deletion returnable.
        """

        self._connection.execute(
            "INSERT INTO deletion_tombstones ("
            "workspace_id, object_id, object_type, object_revision, reason"
            ") VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (workspace_id, object_id, object_revision) DO UPDATE SET "
            "object_type = excluded.object_type, reason = excluded.reason "
            "WHERE deletion_tombstones.reason <> 'USER_DELETION'",
            (
                str(binding.workspace_id),
                str(binding.object_id),
                binding.object_type.value,
                binding.object_revision,
                reason.value,
            ),
        )

    def put_objects_atomic(self, writes: tuple[ObjectWrite, ...]) -> None:
        """Encrypt and insert immutable object revisions in one transaction.

        Re-creating a revision that was deleted earlier clears its tombstone in the
        same transaction, so the tombstone ledger always describes current absence.
        Re-creation is an explicit write by a caller that holds the plaintext; the
        CW-018 promotion and rollback paths never re-create a user-deleted revision.
        """

        self._require_writable()
        if not writes:
            raise StoreIntegrityError("at least one object write is required")
        prepared = self._prepare_writes(writes)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            for binding, envelope in prepared:
                self._insert_object(binding, envelope)
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError(
                "object revision already exists or violated a store constraint"
            ) from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def delete_and_put_atomic(
        self,
        *,
        deletions: tuple[ObjectBinding, ...],
        writes: tuple[ObjectWrite, ...],
    ) -> int:
        """Delete object revisions and insert new ones in one transaction.

        CW-003 uses this so "remove content, record the deletion in the audit spine"
        is one atomic state transition: either both happen or neither does. CW-018
        records a ``USER_DELETION`` tombstone for every removed revision in that
        same transaction.
        """

        if not deletions and not writes:
            raise StoreIntegrityError("at least one deletion or write is required")
        return self.apply_state_change(deletions=deletions, writes=writes)

    def apply_state_change(
        self,
        *,
        deletions: tuple[ObjectBinding, ...] = (),
        writes: tuple[ObjectWrite, ...] = (),
        tombstone_reason: TombstoneReason = TombstoneReason.USER_DELETION,
        record_tombstones: tuple[Tombstone, ...] = (),
        journal: JournalUpdate | None = None,
    ) -> int:
        """Commit deletions, writes, tombstones and a journal transition atomically.

        This is the single CW-018 commit primitive: a lifecycle step and its audit
        event (passed among ``writes``) and its checkpoint either all commit or none
        do, so a crash leaves the previous checkpoint intact.
        """

        self._require_writable()
        if not isinstance(tombstone_reason, TombstoneReason):
            raise StoreIntegrityError("tombstone reason must be an admitted TombstoneReason")
        if not deletions and not writes and not record_tombstones and journal is None:
            raise StoreIntegrityError("a state change must change something")
        admitted_deletions: list[ObjectBinding] = []
        for binding in deletions:
            admitted = binding.validated()
            self._require_workspace(admitted)
            admitted_deletions.append(admitted)
        admitted_tombstones = tuple(self._admitted_tombstone(item) for item in record_tombstones)
        prepared = self._prepare_writes(writes)
        if journal is not None and not isinstance(journal, JournalUpdate):
            raise StoreIntegrityError("journal update must be a JournalUpdate value")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        deleted = 0
        try:
            for admitted in admitted_deletions:
                deleted += self._delete_with_tombstone(admitted, tombstone_reason)
            for binding, envelope in prepared:
                self._insert_object(binding, envelope)
            for tombstone_binding, reason in admitted_tombstones:
                self._insert_tombstone(tombstone_binding, reason)
            if journal is not None:
                self._write_journal(journal)
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError("atomic state change violated a store constraint") from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return deleted

    def _admitted_tombstone(self, tombstone: Tombstone) -> tuple[ObjectBinding, TombstoneReason]:
        if not isinstance(tombstone, Tombstone):
            raise StoreIntegrityError("recorded tombstones must be Tombstone values")
        if not isinstance(tombstone.reason, TombstoneReason):
            raise StoreIntegrityError("tombstone reason must be an admitted TombstoneReason")
        binding = ObjectBinding(
            workspace_id=self._workspace_id,
            object_id=tombstone.object_id,
            object_type=tombstone.object_type,
            object_revision=tombstone.object_revision,
        ).validated()
        return binding, tombstone.reason

    def _write_journal(self, update: JournalUpdate) -> None:
        entry = update.entry
        if not isinstance(entry, JournalEntry) or not isinstance(entry.state, JournalState):
            raise StoreIntegrityError("journal entry must carry an admitted JournalState")
        if not isinstance(entry.checkpoint, int) or entry.checkpoint < 0:
            raise StoreIntegrityError("journal checkpoint must be a non-negative integer")
        existing = self._connection.execute(
            "SELECT migration_class, state FROM migration_journal WHERE migration_id = ?",
            (entry.migration_id,),
        ).fetchone()
        if existing is None:
            if _unfinished_journal(self._connection):
                raise StoreIntegrityError(
                    "another migration is unfinished; only one migration may be in flight"
                )
            self._connection.execute(
                "INSERT INTO migration_journal ("
                "migration_id, migration_class, state, checkpoint, manifest"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    entry.migration_id,
                    entry.migration_class,
                    entry.state.value,
                    entry.checkpoint,
                    entry.manifest,
                ),
            )
        else:
            if str(existing[0]) != entry.migration_class:
                raise StoreIntegrityError("a journal entry cannot change its migration class")
            if JournalState(str(existing[1])) in TERMINAL_JOURNAL_STATES:
                raise StoreIntegrityError("a finished migration journal entry is immutable")
            self._connection.execute(
                "UPDATE migration_journal SET state = ?, checkpoint = ?, manifest = ? "
                "WHERE migration_id = ?",
                (entry.state.value, entry.checkpoint, entry.manifest, entry.migration_id),
            )
        if update.log_row is not None:
            row = update.log_row
            self._connection.execute(
                "INSERT INTO migration_log ("
                "migration_id, migration_class, source_workspace_schema_version, "
                "target_workspace_schema_version, source_encryption_format_version, "
                "target_encryption_format_version, result"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.migration_id,
                    entry.migration_class,
                    row.source_workspace_schema_version,
                    row.target_workspace_schema_version,
                    row.source_encryption_format_version,
                    row.target_encryption_format_version,
                    row.result,
                ),
            )

    def get_object(self, binding: ObjectBinding) -> bytes:
        """Decrypt and return one object revision, failing closed on any mismatch."""

        admitted = binding.validated()
        self._require_workspace(admitted)
        row = self._connection.execute(
            "SELECT object_type, key_version, encryption_format_version, envelope FROM objects "
            "WHERE workspace_id = ? AND object_id = ? AND object_revision = ?",
            (str(admitted.workspace_id), str(admitted.object_id), admitted.object_revision),
        ).fetchone()
        if row is None:
            raise ObjectNotFoundError("the requested object revision is not in this store")
        stored_type, stored_key_version, stored_format_version, envelope = row
        return self._decrypt_row(
            admitted,
            stored_type=str(stored_type),
            stored_key_version=int(stored_key_version),
            stored_format_version=int(stored_format_version),
            envelope=bytes(envelope),
        )

    def _decrypt_row(
        self,
        admitted: ObjectBinding,
        *,
        stored_type: str,
        stored_key_version: int,
        stored_format_version: int,
        envelope: bytes,
    ) -> bytes:
        if stored_type != admitted.object_type.value:
            raise WorkspaceIsolationError("stored object type does not match the requested type")
        try:
            object_type = WorkspaceObjectType(stored_type)
        except ValueError as error:
            raise StoreIntegrityError(
                "stored object type is not an admitted object type"
            ) from error
        key_version = stored_key_version
        format_version = stored_format_version
        if format_version != self._versions.encryption_format_version:
            raise StoreVersionError("stored object uses an unsupported encryption format version")
        header = parse_envelope_header(envelope)
        if header.key_version != key_version:
            raise EnvelopeFormatError(
                "envelope key version does not match the recorded object key version"
            )
        if header.encryption_format_version != format_version:
            raise EnvelopeFormatError(
                "envelope format version does not match the recorded object format version"
            )
        state = self.key_state(key_version)
        if state is KeyState.RETIRED:
            raise KeyStateError("a retired key version cannot be used to read or write objects")
        recorded_binding = ObjectBinding(
            workspace_id=admitted.workspace_id,
            object_id=admitted.object_id,
            object_type=object_type,
            object_revision=admitted.object_revision,
        )
        return decrypt_payload(
            envelope=envelope,
            key=self._derive_key(key_version),
            associated_data=recorded_binding.canonical_associated_data(
                key_version=key_version,
                encryption_format_version=format_version,
            ),
        )

    def delete_object(self, binding: ObjectBinding) -> bool:
        """Delete one object revision.

        ``secure_delete=ON`` reclaims the freed pages as defense in depth. This is
        not cryptographic erasure and no erasure claim is made (A1.11).
        """

        self._require_writable()
        admitted = binding.validated()
        self._require_workspace(admitted)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            deleted = self._delete_with_tombstone(admitted, TombstoneReason.USER_DELETION)
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return deleted > 0

    def begin_key_rotation(self, new_key_version: int) -> None:
        """Start a rotation: the new version becomes the only writing key."""

        self._require_writable()
        if not isinstance(new_key_version, int) or new_key_version < 2:
            raise KeyRotationError("a rotation target must be a key version of 2 or greater")
        known = [key_version for key_version, _ in self.key_states()]
        if new_key_version in known:
            raise KeyRotationError(f"key version {new_key_version} already exists")
        if new_key_version <= max(known):
            raise KeyRotationError("a rotation target must be greater than every known key version")
        if any(state is KeyState.ROTATING for _, state in self.key_states()):
            raise KeyRotationError("a key rotation is already in progress in this store")
        if self.key_state(self._active_key_version) is not KeyState.ACTIVE:
            raise KeyRotationError("the store is not in a rotatable ACTIVE state")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._connection.execute(
                "UPDATE key_versions SET state = ? WHERE state = ?",
                (KeyState.ROTATING.value, KeyState.ACTIVE.value),
            )
            salt = new_salt()
            self._connection.execute(
                "INSERT INTO key_versions (key_version, state, salt) VALUES (?, ?, ?)",
                (new_key_version, KeyState.ACTIVE.value, salt),
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        self._salt_by_version[new_key_version] = salt
        self._refresh_active_key()

    def rotate_pending(self, *, max_objects: int) -> int:
        """Re-encrypt up to ``max_objects`` non-active rows; resumable and deterministic."""

        self._require_writable()
        if not isinstance(max_objects, int) or max_objects <= 0:
            raise KeyRotationError("rotation batch size must be a positive integer")
        active = self._active_key_version
        rows = self._connection.execute(
            f"SELECT {_OBJECT_COLUMNS}, envelope FROM objects WHERE key_version <> ? "
            "ORDER BY object_id, object_revision LIMIT ?",
            (active, max_objects),
        ).fetchall()
        if not rows:
            return 0
        prepared: list[tuple[bytes, str, str, str, str]] = []
        for (
            workspace_id,
            object_id,
            object_type,
            object_revision,
            key_version,
            envelope,
        ) in rows:
            state = self.key_state(int(key_version))
            if state is KeyState.RETIRED:
                raise KeyStateError(
                    "a row bound to a retired key version is refused rather than silently migrated"
                )
            source_binding = self._binding_from_row(
                workspace_id=str(workspace_id),
                object_id=str(object_id),
                object_type=str(object_type),
                object_revision=str(object_revision),
            )
            plaintext = decrypt_payload(
                envelope=bytes(envelope),
                key=self._derive_key(int(key_version)),
                associated_data=source_binding.canonical_associated_data(
                    key_version=int(key_version),
                    encryption_format_version=self._versions.encryption_format_version,
                ),
            )
            rotated = encrypt_payload(
                key=self._active_key,
                plaintext=plaintext,
                associated_data=source_binding.canonical_associated_data(
                    key_version=active,
                    encryption_format_version=self._versions.encryption_format_version,
                ),
                key_version=active,
            )
            prepared.append(
                (
                    rotated,
                    str(workspace_id),
                    str(object_id),
                    str(object_revision),
                    object_type,
                )
            )
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            for rotated, workspace_id, object_id, object_revision, object_type in prepared:
                self._connection.execute(
                    "UPDATE objects SET key_version = ?, envelope = ? WHERE workspace_id = ? "
                    "AND object_id = ? AND object_revision = ? AND object_type = ?",
                    (
                        active,
                        rotated,
                        workspace_id,
                        object_id,
                        object_revision,
                        object_type,
                    ),
                )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return len(prepared)

    def finalize_key_rotation(self) -> int:
        """Move every ROTATING key to RETIRING once no row still uses it."""

        self._require_writable()
        if self._rows_off_active_key():
            raise KeyRotationError("rotation cannot finalize while rows still use an older key")
        rotating = [version for version, state in self.key_states() if state is KeyState.ROTATING]
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._connection.execute(
                "UPDATE key_versions SET state = ? WHERE state = ?",
                (KeyState.RETIRING.value, KeyState.ROTATING.value),
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return len(rotating)

    def retire_key_version(self, key_version: int) -> None:
        """Retire a RETIRING key version that no stored object references."""

        self._require_writable()
        state = self.key_state(key_version)
        if state is not KeyState.RETIRING:
            raise KeyRotationError("only a RETIRING key version can be retired")
        if self._pending_rotation_rows(key_version):
            raise KeyRotationError("a key version that still protects rows cannot be retired")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._connection.execute(
                "UPDATE key_versions SET state = ? WHERE key_version = ?",
                (KeyState.RETIRED.value, key_version),
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def _pending_rotation_rows(self, key_version: int) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM objects WHERE key_version = ?",
            (key_version,),
        ).fetchone()
        return int(row[0])

    def _rows_off_active_key(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM objects WHERE key_version <> ?",
            (self._active_key_version,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _binding_from_row(
        *,
        workspace_id: str,
        object_id: str,
        object_type: str,
        object_revision: str,
    ) -> ObjectBinding:
        try:
            admitted_type = WorkspaceObjectType(object_type)
        except ValueError as error:
            raise StoreIntegrityError(
                "stored object type is not an admitted object type"
            ) from error
        return ObjectBinding(
            workspace_id=UUID(workspace_id),
            object_id=UUID(object_id),
            object_type=admitted_type,
            object_revision=object_revision,
        )

    def tombstones(self) -> tuple[Tombstone, ...]:
        """List every recorded deletion tombstone in deterministic order."""

        self._require_current_schema()
        rows = self._connection.execute(
            "SELECT workspace_id, object_id, object_type, object_revision, reason "
            "FROM deletion_tombstones ORDER BY object_type, object_id, object_revision"
        ).fetchall()
        return tuple(self._tombstone_from_row(row) for row in rows)

    def _tombstone_from_row(self, row: tuple[object, ...]) -> Tombstone:
        workspace_id, object_id, object_type, object_revision, reason = row
        if str(workspace_id) != str(self._workspace_id):
            raise WorkspaceIsolationError("a tombstone crossed the workspace boundary")
        try:
            return Tombstone(
                object_id=UUID(str(object_id)),
                object_type=WorkspaceObjectType(str(object_type)),
                object_revision=str(object_revision),
                reason=TombstoneReason(str(reason)),
            )
        except ValueError as error:
            raise StoreIntegrityError("a recorded tombstone is not well formed") from error

    def journal_entries(self) -> tuple[JournalEntry, ...]:
        """List every migration journal row in deterministic order."""

        if self._versions.workspace_schema_version < 2:
            return ()
        rows = self._connection.execute(
            "SELECT migration_id, migration_class, state, checkpoint, manifest "
            "FROM migration_journal ORDER BY migration_id"
        ).fetchall()
        entries: list[JournalEntry] = []
        for migration_id, migration_class, state, checkpoint, manifest in rows:
            try:
                admitted_state = JournalState(str(state))
            except ValueError as error:
                raise StoreIntegrityError("a journal row has an unknown state") from error
            entries.append(
                JournalEntry(
                    migration_id=str(migration_id),
                    migration_class=str(migration_class),
                    state=admitted_state,
                    checkpoint=int(checkpoint),
                    manifest=str(manifest),
                )
            )
        return tuple(entries)

    def integrity_check(self) -> None:
        """Run SQLite's integrity and foreign-key checks, failing closed on any finding."""

        result = self._connection.execute("PRAGMA integrity_check").fetchall()
        if [str(row[0]) for row in result] != ["ok"]:
            raise StoreIntegrityError("SQLite integrity_check reported a problem")
        if self._connection.execute("PRAGMA foreign_key_check").fetchall():
            raise StoreIntegrityError("SQLite foreign_key_check reported a violation")

    def stored_envelope_bytes(self) -> int:
        """Return the total stored envelope size, for migration space estimates."""

        row = self._connection.execute(
            "SELECT COALESCE(SUM(LENGTH(envelope)), 0) FROM objects"
        ).fetchone()
        return int(row[0])

    def object_key_versions(self) -> tuple[int, ...]:
        """Return the distinct key versions that currently protect stored rows."""

        rows = self._connection.execute(
            "SELECT DISTINCT key_version FROM objects ORDER BY key_version"
        ).fetchall()
        return tuple(int(key_version) for (key_version,) in rows)

    def verify_key_availability(self, key_versions: tuple[int, ...]) -> None:
        """Derive every named key version, failing before any mutation if one is missing."""

        for key_version in key_versions:
            if self.key_state(key_version) is KeyState.RETIRED:
                raise KeyStateError(f"key version {key_version} is retired")
            self._derive_key(key_version)

    def export_snapshot(self) -> StoreSnapshot:
        """Return a transaction-consistent decrypted copy of every object and tombstone.

        The snapshot is held in process memory only; CW-018 encrypts it under a
        separate backup key before it leaves this process.
        """

        self._require_current_schema()
        self._connection.execute("BEGIN")
        try:
            # CW-019: a snapshot feeds backups and promotion decisions, so it is taken only
            # from state that still matches the seal inside the same read transaction.
            self._verify_before_change()
            rows = self._connection.execute(
                "SELECT workspace_id, object_id, object_type, object_revision, key_version, "
                "encryption_format_version, envelope FROM objects "
                "ORDER BY object_type, object_id, object_revision"
            ).fetchall()
            tombstone_rows = self._connection.execute(
                "SELECT workspace_id, object_id, object_type, object_revision, reason "
                "FROM deletion_tombstones ORDER BY object_type, object_id, object_revision"
            ).fetchall()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        objects: list[SnapshotObject] = []
        for (
            workspace_id,
            object_id,
            object_type,
            object_revision,
            key_version,
            format_version,
            envelope,
        ) in rows:
            if str(workspace_id) != str(self._workspace_id):
                raise WorkspaceIsolationError("a stored object crossed the workspace boundary")
            binding = self._binding_from_row(
                workspace_id=str(workspace_id),
                object_id=str(object_id),
                object_type=str(object_type),
                object_revision=str(object_revision),
            ).validated()
            payload = self._decrypt_row(
                binding,
                stored_type=str(object_type),
                stored_key_version=int(key_version),
                stored_format_version=int(format_version),
                envelope=bytes(envelope),
            )
            objects.append(SnapshotObject(binding=binding, payload=payload))
        tombstones = tuple(self._tombstone_from_row(row) for row in tombstone_rows)
        return StoreSnapshot(
            versions=self._versions,
            role=self._role,
            objects=tuple(objects),
            tombstones=tombstones,
        )

    def import_snapshot(
        self,
        *,
        objects: tuple[SnapshotObject, ...],
        tombstones: tuple[Tombstone, ...],
        restored_backup_id: UUID,
    ) -> None:
        """Load a verified backup into an empty quarantine store in one transaction.

        Refused on a live store and on any quarantine store that already holds state:
        a restore never overwrites anything.
        """

        self._require_current_schema()
        if self._role is not StoreRole.QUARANTINE:
            raise StoreRoleError("backups are restored into a quarantine store only")
        if not isinstance(restored_backup_id, UUID):
            raise StoreIntegrityError("restored backup id must be a UUID value")
        if self.object_count() or self.tombstones() or self.restored_backup_id is not None:
            raise StoreConflictError(
                "the quarantine store already holds state; a restore never overwrites"
            )
        writes = tuple(ObjectWrite(binding=item.binding, payload=item.payload) for item in objects)
        prepared = self._prepare_writes(writes)
        admitted_tombstones = tuple(self._admitted_tombstone(item) for item in tombstones)
        object_keys = {(binding.object_id, binding.object_revision) for binding, _ in prepared}
        for tombstone_binding, _reason in admitted_tombstones:
            if (tombstone_binding.object_id, tombstone_binding.object_revision) in object_keys:
                raise StoreIntegrityError("a restored object cannot also be tombstoned")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._verify_before_change()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            for binding, envelope in prepared:
                self._insert_object(binding, envelope)
            for tombstone_binding, reason in admitted_tombstones:
                self._connection.execute(
                    "INSERT INTO deletion_tombstones ("
                    "workspace_id, object_id, object_type, object_revision, reason"
                    ") VALUES (?, ?, ?, ?, ?)",
                    (
                        str(tombstone_binding.workspace_id),
                        str(tombstone_binding.object_id),
                        tombstone_binding.object_type.value,
                        tombstone_binding.object_revision,
                        reason.value,
                    ),
                )
            self._connection.execute(
                "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                (_RESTORED_BACKUP_METADATA_KEY, str(restored_backup_id)),
            )
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError("restored state violated a store constraint") from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        try:
            self._reseal()
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def apply_schema_v2_migration(
        self,
        *,
        target_application_version: str,
        journal_manifest: str,
        audit_write: ObjectWrite,
    ) -> StoreVersions:
        """Run the CW-018 M1 additive migration (schema 1 -> 2) as one transaction.

        The new tables, the recorded role, the version metadata, the migration log
        row, the completed journal row and the migration audit event commit together;
        a crash leaves the store exactly at schema 1 (``NOT_STARTED``).
        """

        if not self._maintenance:
            raise StoreMigrationRequiredError("schema migration runs in maintenance mode only")
        if self._versions.workspace_schema_version != 1:
            raise StoreVersionError("the schema 1 -> 2 migration applies to schema 1 stores only")
        if not isinstance(target_application_version, str) or not target_application_version:
            raise StoreVersionError("target application version must be recorded explicitly")
        if not isinstance(journal_manifest, str) or not journal_manifest:
            raise StoreIntegrityError("the migration journal manifest must be recorded")
        prepared = self._prepare_writes((audit_write,))
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA_V2_STATEMENTS:
                self._connection.execute(statement)
            self._connection.execute(
                "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                ("store_role", StoreRole.LIVE.value),
            )
            # The schema 1 -> 2 step always lands on schema 2; later steps are separate
            # migrations (CW-019 adds 2 -> 3), so the current-schema constants are not used.
            for name, value in (
                ("workspace_schema_version", str(_SCHEMA_V2)),
                ("minimum_readable_workspace_schema", str(_SCHEMA_V2)),
                ("maximum_readable_workspace_schema", str(_SCHEMA_V2)),
                ("application_version", target_application_version),
            ):
                cursor = self._connection.execute(
                    "UPDATE store_metadata SET value = ? WHERE name = ?",
                    (value, name),
                )
                if cursor.rowcount != 1:
                    raise StoreIntegrityError(f"recorded store metadata is missing {name!r}")
            self._connection.execute(
                "INSERT INTO migration_log ("
                "migration_id, migration_class, source_workspace_schema_version, "
                "target_workspace_schema_version, source_encryption_format_version, "
                "target_encryption_format_version, result"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    SCHEMA_V2_MIGRATION_ID,
                    SCHEMA_V2_MIGRATION_CLASS,
                    1,
                    _SCHEMA_V2,
                    self._versions.encryption_format_version,
                    self._versions.encryption_format_version,
                    JournalState.COMPLETED.value,
                ),
            )
            self._connection.execute(
                "INSERT INTO migration_journal ("
                "migration_id, migration_class, state, checkpoint, manifest"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    SCHEMA_V2_MIGRATION_ID,
                    SCHEMA_V2_MIGRATION_CLASS,
                    JournalState.COMPLETED.value,
                    1,
                    journal_manifest,
                ),
            )
            for binding, envelope in prepared:
                self._insert_object(binding, envelope)
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError("the schema migration violated a store constraint") from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        self._versions = _recorded_versions(_read_metadata(self._connection), allow_migratable=True)
        return self._versions

    def apply_schema_v3_migration(
        self,
        *,
        target_application_version: str,
        journal_manifest: str,
        audit_write: ObjectWrite,
    ) -> StoreVersions:
        """Run the CW-019 M1 additive migration (schema 2 -> 3) as one transaction.

        It records a fresh seal salt, derives the seal key, bumps the version metadata,
        appends the migration log row, the completed journal row and the migration audit
        event, and writes the first integrity seal over the result. A crash leaves the
        store exactly at schema 2.
        """

        if not self._maintenance:
            raise StoreMigrationRequiredError("schema migration runs in maintenance mode only")
        if self._versions.workspace_schema_version != 2:
            raise StoreVersionError("the schema 2 -> 3 migration applies to schema 2 stores only")
        if not isinstance(target_application_version, str) or not target_application_version:
            raise StoreVersionError("target application version must be recorded explicitly")
        if not isinstance(journal_manifest, str) or not journal_manifest:
            raise StoreIntegrityError("the migration journal manifest must be recorded")
        if _unfinished_journal(self._connection):
            raise StoreMigrationRequiredError(
                "an unfinished migration must be resumed or rolled back before the schema 3 "
                "migration"
            )
        seal_salt = new_salt()
        seal_key = _admit_seal_key(
            self._key_provider.seal_key(workspace_id=self._workspace_id, salt=seal_salt)
        )
        prepared = self._prepare_writes((audit_write,))
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                "INSERT INTO store_metadata (name, value) VALUES (?, ?)",
                (_SEAL_SALT_METADATA_KEY, seal_salt.hex()),
            )
            for name, value in (
                ("workspace_schema_version", str(WORKSPACE_SCHEMA_VERSION)),
                ("minimum_readable_workspace_schema", str(MINIMUM_READABLE_WORKSPACE_SCHEMA)),
                ("maximum_readable_workspace_schema", str(MAXIMUM_READABLE_WORKSPACE_SCHEMA)),
                ("application_version", target_application_version),
            ):
                cursor = self._connection.execute(
                    "UPDATE store_metadata SET value = ? WHERE name = ?",
                    (value, name),
                )
                if cursor.rowcount != 1:
                    raise StoreIntegrityError(f"recorded store metadata is missing {name!r}")
            self._connection.execute(
                "INSERT INTO migration_log ("
                "migration_id, migration_class, source_workspace_schema_version, "
                "target_workspace_schema_version, source_encryption_format_version, "
                "target_encryption_format_version, result"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    SCHEMA_V3_MIGRATION_ID,
                    SCHEMA_V3_MIGRATION_CLASS,
                    2,
                    WORKSPACE_SCHEMA_VERSION,
                    self._versions.encryption_format_version,
                    self._versions.encryption_format_version,
                    JournalState.COMPLETED.value,
                ),
            )
            self._connection.execute(
                "INSERT INTO migration_journal ("
                "migration_id, migration_class, state, checkpoint, manifest"
                ") VALUES (?, ?, ?, ?, ?)",
                (
                    SCHEMA_V3_MIGRATION_ID,
                    SCHEMA_V3_MIGRATION_CLASS,
                    JournalState.COMPLETED.value,
                    1,
                    journal_manifest,
                ),
            )
            for binding, envelope in prepared:
                self._insert_object(binding, envelope)
            _write_seal(self._connection, seal_key)
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError("the schema migration violated a store constraint") from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        self._seal_key = seal_key
        self._versions = _recorded_versions(_read_metadata(self._connection))
        return self._versions

    def migration_log(self) -> tuple[tuple[str, str, int, int, str], ...]:
        rows = self._connection.execute(
            "SELECT migration_id, migration_class, source_workspace_schema_version, "
            "target_workspace_schema_version, result FROM migration_log ORDER BY migration_id"
        ).fetchall()
        return tuple(
            (str(migration_id), str(migration_class), int(source), int(target), str(result))
            for migration_id, migration_class, source, target, result in rows
        )

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> WorkspaceStore:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()
