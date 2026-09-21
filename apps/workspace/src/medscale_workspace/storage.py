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
* this module implements store initialization only; the remaining migration classes
  and their manifest/preflight/rollback machinery belong to CW-018.
"""

from __future__ import annotations

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
    MINIMUM_READABLE_WORKSPACE_SCHEMA,
    POLICY_VERSION,
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
)

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

_OBJECT_COLUMNS = "workspace_id, object_id, object_type, object_revision, key_version"


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


def _recorded_versions(metadata: dict[str, str]) -> StoreVersions:
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
    reason = unreadable_schema_reason(versions.workspace_schema_version)
    if reason is not None:
        raise StoreVersionError(reason)
    return versions


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
    ) -> None:
        self._connection = connection
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
    ) -> WorkspaceStore:
        """Open (or initialize) the store, failing closed before any write."""

        if not isinstance(application_version, str) or not application_version.strip():
            raise StoreVersionError("application version must be recorded explicitly")
        if not isinstance(workspace_id, UUID):
            raise StoreIntegrityError("workspace id must be a UUID value")
        if not isinstance(busy_timeout_ms, int) or busy_timeout_ms <= 0:
            raise StoreIntegrityError("busy timeout must be a positive integer")
        key_provider.require_available()
        path = resolve_workspace_store_path(store_root, workspace_id)
        connection = sqlite3.connect(path, isolation_level=None, timeout=busy_timeout_ms / 1000)
        try:
            _apply_pragmas(connection, busy_timeout_ms)
            _admitted_pragmas(_read_pragmas(connection), busy_timeout_ms)
            if _schema_present(connection):
                metadata = _read_metadata(connection)
                versions = _recorded_versions(metadata)
                if _required_metadata(metadata, "workspace_id") != str(workspace_id):
                    raise WorkspaceIsolationError(
                        "the store belongs to a different workspace than the opened id"
                    )
            else:
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
                cls._initialise(connection, workspace_id=workspace_id, versions=versions)
            salt_by_version = cls._read_salts(connection)
            store = cls(
                connection,
                path=path,
                workspace_id=workspace_id,
                key_provider=key_provider,
                versions=versions,
                salt_by_version=salt_by_version,
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
    ) -> None:
        connection.execute("BEGIN IMMEDIATE")
        try:
            for statement in _SCHEMA_STATEMENTS:
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

    def put_objects_atomic(self, writes: tuple[ObjectWrite, ...]) -> None:
        """Encrypt and insert immutable object revisions in one transaction."""

        if not writes:
            raise StoreIntegrityError("at least one object write is required")
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
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            for binding, envelope in prepared:
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
        except sqlite3.IntegrityError as error:
            self._connection.execute("ROLLBACK")
            raise StoreConflictError(
                "object revision already exists or violated a store constraint"
            ) from error
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

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
        if str(stored_type) != admitted.object_type.value:
            raise WorkspaceIsolationError("stored object type does not match the requested type")
        try:
            object_type = WorkspaceObjectType(str(stored_type))
        except ValueError as error:
            raise StoreIntegrityError(
                "stored object type is not an admitted object type"
            ) from error
        key_version = int(stored_key_version)
        format_version = int(stored_format_version)
        if format_version != self._versions.encryption_format_version:
            raise StoreVersionError("stored object uses an unsupported encryption format version")
        header = parse_envelope_header(bytes(envelope))
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
            envelope=bytes(envelope),
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

        admitted = binding.validated()
        self._require_workspace(admitted)
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = self._connection.execute(
                "DELETE FROM objects WHERE workspace_id = ? AND object_id = ? "
                "AND object_revision = ?",
                (str(admitted.workspace_id), str(admitted.object_id), admitted.object_revision),
            )
            deleted = cursor.rowcount
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return deleted > 0

    def begin_key_rotation(self, new_key_version: int) -> None:
        """Start a rotation: the new version becomes the only writing key."""

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
        self._connection.execute("COMMIT")
        self._salt_by_version[new_key_version] = salt
        self._refresh_active_key()

    def rotate_pending(self, *, max_objects: int) -> int:
        """Re-encrypt up to ``max_objects`` non-active rows; resumable and deterministic."""

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
        self._connection.execute("COMMIT")
        return len(prepared)

    def finalize_key_rotation(self) -> int:
        """Move every ROTATING key to RETIRING once no row still uses it."""

        if self._rows_off_active_key():
            raise KeyRotationError("rotation cannot finalize while rows still use an older key")
        rotating = [version for version, state in self.key_states() if state is KeyState.ROTATING]
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                "UPDATE key_versions SET state = ? WHERE state = ?",
                (KeyState.RETIRING.value, KeyState.ROTATING.value),
            )
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")
        return len(rotating)

    def retire_key_version(self, key_version: int) -> None:
        """Retire a RETIRING key version that no stored object references."""

        state = self.key_state(key_version)
        if state is not KeyState.RETIRING:
            raise KeyRotationError("only a RETIRING key version can be retired")
        if self._pending_rotation_rows(key_version):
            raise KeyRotationError("a key version that still protects rows cannot be retired")
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            self._connection.execute(
                "UPDATE key_versions SET state = ? WHERE key_version = ?",
                (KeyState.RETIRED.value, key_version),
            )
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
