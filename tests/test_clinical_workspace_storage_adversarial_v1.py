"""CW-002 adversarial tests: hostile cases, tested independently of the benign suite.

Every case here attacks a property that ADR-0039 as amended by A1 requires the
implementation to hold. None of them may be satisfied by a benign-path assertion,
and none of them establishes readiness, acceptance or authority.

The synthetic fixtures remain synthetic. This module performs no research
admission, no training, no publication and no clinical action.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open. These adversarial tests import it at
# runtime through sys.path; declaring the missing import here keeps that deferral
# explicit instead of silently widening the typing surface.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_MODULES = WORKSPACE_SRC / "medscale_workspace"
RATIFICATION_RECORD = (
    REPOSITORY_ROOT
    / "specs"
    / "medscale-clinical-workspace-v1"
    / "adr-0039-founder-ratification.md"
)

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402
from medscale_workspace.aead import HEADER_SIZE_BYTES, parse_envelope_header  # noqa: E402
from medscale_workspace.binding import MAXIMUM_REVISION_LENGTH, ObjectBinding  # noqa: E402
from medscale_workspace.errors import (  # noqa: E402
    EnvelopeAuthenticationError,
    EnvelopeFormatError,
    KeyMaterialUnavailableError,
    KeyRotationError,
    KeyStateError,
    ObjectBindingError,
    StoreConflictError,
    StoreIntegrityError,
    StorePathError,
    StoreVersionError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType  # noqa: E402
from medscale_workspace.keyprovider import (  # noqa: E402
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.storage import (  # noqa: E402
    KeyState,
    ObjectWrite,
    WorkspaceStore,
)
from medscale_workspace.store_path import resolve_workspace_store_path  # noqa: E402

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("1a3d7c22-42f4-4b76-9d6f-0c2c8db0f3a1")
PATIENT_OBJECT = UUID("2f1b7c8e-6a4d-4f9c-8f1e-5b6a7c8d9e0f")
ENCOUNTER_OBJECT = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
PAYLOAD_A = b"SYNTHETIC-NOT-REAL:alpha-payload"
PAYLOAD_B = b"SYNTHETIC-NOT-REAL:beta-payload"


def binding_for(
    object_id: UUID = PATIENT_OBJECT,
    object_type: WorkspaceObjectType = WorkspaceObjectType.PATIENT,
    revision: str = "rev-0001",
    workspace_id: UUID = WORKSPACE_ALPHA,
) -> ObjectBinding:
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=object_id,
        object_type=object_type,
        object_revision=revision,
    )


def open_store(
    root: Path,
    *,
    workspace_id: UUID = WORKSPACE_ALPHA,
    root_secret: bytes | None = None,
) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(root_secret or new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def raw(store_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(store_path)
    connection.isolation_level = None
    return connection


def raw_execute(store_path: str, statement: str, parameters: tuple[object, ...] = ()) -> None:
    connection = raw(store_path)
    try:
        connection.execute(statement, parameters)
    finally:
        connection.close()


def raw_fetch(
    store_path: str, statement: str, parameters: tuple[object, ...] = ()
) -> tuple[object, ...]:
    connection = raw(store_path)
    try:
        row = connection.execute(statement, parameters).fetchone()
    finally:
        connection.close()
    assert row is not None
    return tuple(row)


def stored_envelope(store_path: str, object_id: UUID, revision: str = "rev-0001") -> bytes:
    row = raw_fetch(
        store_path,
        "SELECT envelope FROM objects WHERE object_id = ? AND object_revision = ?",
        (str(object_id), revision),
    )
    value = row[0]
    assert isinstance(value, bytes)
    return value


def seeded_store(tmp_path: Path, root_secret: bytes) -> str:
    """Create a store holding two object types, return its path (store closed)."""

    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (
                ObjectWrite(binding=binding_for(), payload=PAYLOAD_A),
                ObjectWrite(
                    binding=binding_for(
                        object_id=ENCOUNTER_OBJECT,
                        object_type=WorkspaceObjectType.ENCOUNTER,
                    ),
                    payload=PAYLOAD_B,
                ),
            )
        )
        return str(store.store_path)


# ---------------------------------------------------------------------------
# 1. Relocation, swapping and binding attacks
# ---------------------------------------------------------------------------


def test_swapping_ciphertext_between_objects_fails_authentication(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    encounter_envelope = stored_envelope(store_path, ENCOUNTER_OBJECT)
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ?",
        (encounter_envelope, str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path) as store, pytest.raises(EnvelopeAuthenticationError):
        store.get_object(binding_for())


def test_swapping_ciphertext_between_revisions_fails_authentication(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (
                ObjectWrite(binding=binding_for(revision="rev-0001"), payload=PAYLOAD_A),
                ObjectWrite(binding=binding_for(revision="rev-0002"), payload=PAYLOAD_B),
            )
        )
        store_path = store.store_path
    second = stored_envelope(store_path, PATIENT_OBJECT, "rev-0002")
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ? AND object_revision = ?",
        (second, str(PATIENT_OBJECT), "rev-0001"),
    )
    with (
        open_store(tmp_path, root_secret=root_secret) as store,
        pytest.raises(EnvelopeAuthenticationError),
    ):
        store.get_object(binding_for(revision="rev-0001"))


def test_ciphertext_from_another_workspace_fails_authentication(tmp_path: Path) -> None:
    shared_root_secret = new_root_secret()
    alpha_path = seeded_store(tmp_path, shared_root_secret)
    alpha_envelope = stored_envelope(alpha_path, PATIENT_OBJECT)
    with open_store(tmp_path, workspace_id=WORKSPACE_BETA, root_secret=shared_root_secret) as beta:
        beta_path = beta.store_path
    raw_execute(
        beta_path,
        "INSERT INTO objects (workspace_id, object_id, object_type, object_revision, "
        "key_version, encryption_format_version, envelope) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(WORKSPACE_BETA), str(PATIENT_OBJECT), "Patient", "rev-0001", 1, 1, alpha_envelope),
    )
    with (
        open_store(tmp_path, workspace_id=WORKSPACE_BETA, root_secret=shared_root_secret) as beta,
        pytest.raises(EnvelopeAuthenticationError),
    ):
        beta.get_object(binding_for(workspace_id=WORKSPACE_BETA))


def test_recording_a_different_object_type_is_refused(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE objects SET object_type = ? WHERE object_id = ?",
        ("Encounter", str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path) as store:
        with pytest.raises(WorkspaceIsolationError):
            store.get_object(binding_for())
        with pytest.raises(EnvelopeAuthenticationError):
            store.get_object(
                binding_for(object_type=WorkspaceObjectType.ENCOUNTER),
            )


def test_an_object_type_outside_the_admitted_set_fails_closed(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE objects SET object_type = ? WHERE object_id = ?",
        ("Observation", str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path) as store, pytest.raises(WorkspaceIsolationError):
        store.get_object(binding_for())
    with open_store(tmp_path) as store:
        store.begin_key_rotation(2)
        with pytest.raises(StoreIntegrityError):
            store.rotate_pending(max_objects=10)


def test_a_binding_without_an_immutable_revision_is_refused() -> None:
    with pytest.raises(ObjectBindingError):
        binding_for(revision="   ").validated()
    with pytest.raises(ObjectBindingError):
        binding_for(revision="rev with space").validated()
    with pytest.raises(ObjectBindingError):
        binding_for(revision="r" * (MAXIMUM_REVISION_LENGTH + 1)).validated()
    with pytest.raises(ObjectBindingError):
        binding_for(revision="rev\n0001").validated()
    with pytest.raises(ObjectBindingError):
        binding_for(revision="rev-0001").canonical_associated_data(
            key_version=0, encryption_format_version=1
        )
    with pytest.raises(ObjectBindingError):
        binding_for(revision="rev-0001").canonical_associated_data(
            key_version=1, encryption_format_version=0
        )


# ---------------------------------------------------------------------------
# 2. Envelope tampering
# ---------------------------------------------------------------------------


def test_envelope_key_version_mismatch_with_the_row_is_refused(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE objects SET key_version = 2 WHERE object_id = ?",
        (str(PATIENT_OBJECT),),
    )
    with open_store(tmp_path) as store, pytest.raises(EnvelopeFormatError):
        store.get_object(binding_for())


def test_envelope_format_version_mismatch_with_the_row_is_refused(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE objects SET encryption_format_version = 2 WHERE object_id = ?",
        (str(PATIENT_OBJECT),),
    )
    with open_store(tmp_path) as store, pytest.raises(StoreVersionError):
        store.get_object(binding_for())


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "truncated_header",
        "truncated_ciphertext",
        "bad_magic",
        "unsupported_format_byte",
        "zero_key_version",
        "flipped_nonce",
        "flipped_ciphertext",
        "flipped_tag",
    ],
)
def test_tampered_envelopes_fail_closed(tmp_path: Path, mutation: str) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    envelope = stored_envelope(store_path, PATIENT_OBJECT)
    if mutation == "empty":
        tampered = b""
    elif mutation == "truncated_header":
        tampered = envelope[: HEADER_SIZE_BYTES - 1]
    elif mutation == "truncated_ciphertext":
        tampered = envelope[:-1]
    elif mutation == "bad_magic":
        tampered = b"MSWSENVX" + envelope[8:]
    elif mutation == "unsupported_format_byte":
        tampered = envelope[:8] + bytes([9]) + envelope[9:]
    elif mutation == "zero_key_version":
        tampered = envelope[:9] + (0).to_bytes(4, "big") + envelope[13:]
    elif mutation == "flipped_nonce":
        tampered = envelope[:13] + bytes([envelope[13] ^ 0x01]) + envelope[14:]
    elif mutation == "flipped_ciphertext":
        tampered = (
            envelope[:HEADER_SIZE_BYTES]
            + bytes([envelope[HEADER_SIZE_BYTES] ^ 0x01])
            + envelope[HEADER_SIZE_BYTES + 1 :]
        )
    elif mutation == "flipped_tag":
        tampered = envelope[:-1] + bytes([envelope[-1] ^ 0x01])
    else:  # pragma: no cover - the parametrisation is closed
        raise AssertionError(mutation)
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ?",
        (tampered, str(PATIENT_OBJECT)),
    )
    with (
        open_store(tmp_path) as store,
        pytest.raises((EnvelopeFormatError, EnvelopeAuthenticationError)),
    ):
        store.get_object(binding_for())


def test_envelope_never_contains_the_plaintext_it_protects(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    envelope = stored_envelope(store_path, PATIENT_OBJECT)
    assert PAYLOAD_A not in envelope
    assert envelope[HEADER_SIZE_BYTES:] != PAYLOAD_A
    header = parse_envelope_header(envelope)
    assert header.key_version == 1
    assert header.encryption_format_version == 1


def test_decryption_failure_never_returns_bytes(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    envelope = stored_envelope(store_path, PATIENT_OBJECT)
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ?",
        (envelope[:-1], str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path) as store:
        try:
            result = store.get_object(binding_for())
        except (EnvelopeFormatError, EnvelopeAuthenticationError):
            return
        raise AssertionError(f"a failed decryption returned {result!r}")


def test_store_bootstrap_refuses_key_material_of_the_wrong_size(tmp_path: Path) -> None:
    class ShortKeyProvider:
        """A provider that claims availability but returns unusable key material."""

        def __init__(self, root_secret: bytes) -> None:
            if len(root_secret) < 32:
                raise ValueError("test root secret must be at least 32 bytes")

        def require_available(self) -> None:
            return None

        def key_for_version(self, *, workspace_id: UUID, key_version: int, salt: bytes) -> bytes:
            del workspace_id, key_version, salt
            return b"\x00" * 16

    store_path = Path(resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA))
    with pytest.raises(KeyMaterialUnavailableError):
        WorkspaceStore.open(
            store_root=str(tmp_path),
            workspace_id=WORKSPACE_ALPHA,
            key_provider=ShortKeyProvider(new_root_secret()),
            application_version=APPLICATION_VERSION,
        )
    # An unusable key must leave no persistable object state behind. Store structure
    # alone is not sensitive payload state, so it is permitted to exist.
    assert store_path.exists()
    connection = sqlite3.connect(str(store_path))
    try:
        has_objects = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'objects'"
        ).fetchone()
        if has_objects is not None:
            assert connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# 3. Key-version state machine attacks
# ---------------------------------------------------------------------------


def test_two_active_key_versions_are_rejected_by_the_store_schema(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    with pytest.raises(sqlite3.IntegrityError):
        raw_execute(
            store_path,
            "INSERT INTO key_versions (key_version, state, salt) VALUES (?, ?, ?)",
            (7, "ACTIVE", b"\x01" * 16),
        )


def test_a_store_without_an_active_key_fails_closed(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(store_path, "DELETE FROM key_versions WHERE key_version = 1")
    with pytest.raises(StoreIntegrityError):
        open_store(tmp_path)


def test_a_retired_key_version_cannot_read_or_write_objects(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic((ObjectWrite(binding=binding_for(), payload=PAYLOAD_A),))
        retirement_envelope = stored_envelope(store.store_path, PATIENT_OBJECT)
        store.begin_key_rotation(2)
        assert store.rotate_pending(max_objects=10) == 1
        assert store.finalize_key_rotation() == 1
        store.retire_key_version(1)
        store_path = store.store_path
    raw_execute(
        store_path,
        "INSERT INTO objects (workspace_id, object_id, object_type, object_revision, "
        "key_version, encryption_format_version, envelope) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            str(WORKSPACE_ALPHA),
            str(PATIENT_OBJECT),
            "Patient",
            "rev-retired",
            1,
            1,
            retirement_envelope,
        ),
    )
    with open_store(tmp_path, root_secret=root_secret) as store:
        assert store.key_state(1) is KeyState.RETIRED
        with pytest.raises(KeyStateError):
            store.get_object(binding_for(revision="rev-retired"))


def test_an_unknown_key_version_row_fails_closed(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    envelope = stored_envelope(store_path, PATIENT_OBJECT)
    forged = envelope[:9] + (99).to_bytes(4, "big") + envelope[13:]
    raw_execute(
        store_path,
        "UPDATE objects SET key_version = 99, envelope = ? WHERE object_id = ?",
        (forged, str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path) as store, pytest.raises(KeyStateError):
        store.get_object(binding_for())


def test_rotation_refuses_to_migrate_a_row_bound_to_a_retired_key(tmp_path: Path) -> None:
    """A retired key must not silently resume work, even through the rotation path."""

    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic((ObjectWrite(binding=binding_for(), payload=PAYLOAD_A),))
        retirement_envelope = stored_envelope(store.store_path, PATIENT_OBJECT)
        store.begin_key_rotation(2)
        assert store.rotate_pending(max_objects=10) == 1
        assert store.finalize_key_rotation() == 1
        store.retire_key_version(1)
        store_path = store.store_path
    raw_execute(
        store_path,
        "UPDATE objects SET key_version = 1, envelope = ? WHERE object_id = ?",
        (retirement_envelope, str(PATIENT_OBJECT)),
    )
    with open_store(tmp_path, root_secret=root_secret) as store:
        assert store.key_state(1) is KeyState.RETIRED
        store.begin_key_rotation(3)
        with pytest.raises(KeyStateError):
            store.rotate_pending(max_objects=10)


def test_rotation_preconditions_fail_closed(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        with pytest.raises(KeyRotationError):
            store.begin_key_rotation(1)
        with pytest.raises(KeyRotationError):
            store.begin_key_rotation(0)
        store.put_objects_atomic((ObjectWrite(binding=binding_for(), payload=PAYLOAD_A),))
        store.begin_key_rotation(2)
        with pytest.raises(KeyRotationError):
            store.begin_key_rotation(3)
        with pytest.raises(KeyRotationError):
            store.finalize_key_rotation()
        with pytest.raises(KeyRotationError):
            store.rotate_pending(max_objects=0)
        with pytest.raises(KeyRotationError):
            store.retire_key_version(2)
        assert store.rotate_pending(max_objects=10) == 1
        assert store.finalize_key_rotation() == 1
        with pytest.raises(KeyRotationError):
            store.retire_key_version(2)


# ---------------------------------------------------------------------------
# 4. Store integrity, versioning and boundary attacks
# ---------------------------------------------------------------------------


def test_a_foreign_database_file_is_not_adopted(tmp_path: Path) -> None:
    store_path = Path(resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA))
    connection = sqlite3.connect(str(store_path))
    try:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(StoreIntegrityError):
        open_store(tmp_path)


def test_a_missing_version_metadata_row_makes_the_store_unreadable(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "DELETE FROM store_metadata WHERE name = ?",
        ("policy_version",),
    )
    with pytest.raises(StoreVersionError):
        open_store(tmp_path)


def test_a_downgrade_to_an_older_schema_is_refused(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE store_metadata SET value = '0' WHERE name = 'workspace_schema_version'",
    )
    with pytest.raises(StoreVersionError):
        open_store(tmp_path)


def test_a_non_integer_version_metadata_value_is_refused(tmp_path: Path) -> None:
    store_path = seeded_store(tmp_path, new_root_secret())
    raw_execute(
        store_path,
        "UPDATE store_metadata SET value = 'one' WHERE name = 'workspace_schema_version'",
    )
    with pytest.raises(StoreVersionError):
        open_store(tmp_path)


@pytest.mark.parametrize(
    "store_root",
    [
        "",
        "   ",
        "relative/path",
        "..",
        "../escape",
        "/tmp/../escape",
        "C:\\data\\..\\escape",
        "C:\\data/mixed",
        "C:/data\\mixed",
    ],
)
def test_unsafe_store_roots_are_refused(store_root: str) -> None:
    with pytest.raises(StorePathError):
        resolve_workspace_store_path(store_root, WORKSPACE_ALPHA)


def test_the_store_path_resolver_rejects_a_non_uuid_workspace() -> None:
    invalid_workspace: Any = "not-a-uuid"
    with pytest.raises(StorePathError):
        resolve_workspace_store_path("C:\\synthetic-root", invalid_workspace)


def test_atomic_write_conflict_rolls_back_every_write(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        store.put_objects_atomic((ObjectWrite(binding=binding_for(), payload=PAYLOAD_A),))
        with pytest.raises(StoreConflictError):
            store.put_objects_atomic(
                (
                    ObjectWrite(binding=binding_for(revision="rev-0002"), payload=PAYLOAD_B),
                    ObjectWrite(binding=binding_for(), payload=PAYLOAD_B),
                )
            )
        assert store.object_count() == 1
        from medscale_workspace.errors import ObjectNotFoundError

        with pytest.raises(ObjectNotFoundError):
            store.get_object(binding_for(revision="rev-0002"))


def test_empty_payloads_and_empty_write_sets_are_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        with pytest.raises(StoreIntegrityError):
            store.put_objects_atomic(())
        with pytest.raises(StoreIntegrityError):
            store.put_objects_atomic((ObjectWrite(binding=binding_for(), payload=b""),))
        assert store.object_count() == 0


def test_a_binding_from_another_workspace_is_refused_by_the_store(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        with pytest.raises(WorkspaceIsolationError):
            store.put_objects_atomic(
                (ObjectWrite(binding=binding_for(workspace_id=WORKSPACE_BETA), payload=PAYLOAD_A),)
            )
        with pytest.raises(WorkspaceIsolationError):
            store.delete_object(binding_for(workspace_id=WORKSPACE_BETA))
        assert store.object_count() == 0


# ---------------------------------------------------------------------------
# 5. No-plaintext-fallback and limitation honesty
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", ["aead.py", "storage.py"])
def test_no_crypto_path_swallows_an_exception(module_name: str) -> None:
    tree = ast.parse((WORKSPACE_MODULES / module_name).read_text(encoding="utf-8"))
    handlers = [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]
    assert handlers, f"{module_name} must fail closed through an explicit handler"
    for handler in handlers:
        assert handler.body, f"{module_name} has an empty except handler"
        assert isinstance(handler.body[-1], ast.Raise), (
            f"{module_name}:{handler.lineno}: an except handler must re-raise; a swallowed "
            "crypto failure is a plaintext-fallback risk"
        )


def test_no_workspace_module_imports_a_process_network_or_environment_capability() -> None:
    forbidden = {"ctypes", "importlib", "multiprocessing", "os", "pathlib", "socket", "subprocess"}
    for path in sorted(WORKSPACE_MODULES.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not (imported & forbidden), f"{path.name} imports {sorted(imported & forbidden)}"


def test_rollback_limitation_is_documented_and_not_overclaimed() -> None:
    record = RATIFICATION_RECORD.read_text(encoding="utf-8").lower()
    assert "wrong workspace" in record and "relocation" in record
    assert "rollback" in record
    assert "does not by itself defeat" in record
    storage_source = (WORKSPACE_MODULES / "storage.py").read_text(encoding="utf-8").lower()
    assert "rollback" in storage_source
    assert "implements no rollback detector" in storage_source
    for overclaim in ("rollback protection is implemented", "rollback-proof", "prevents rollback"):
        assert overclaim not in storage_source


def test_secure_delete_is_only_claimed_as_defense_in_depth() -> None:
    storage_source = (WORKSPACE_MODULES / "storage.py").read_text(encoding="utf-8").lower()
    assert "secure_delete=on" in storage_source
    assert "defense in depth" in storage_source
    for overclaim in (
        "cryptographic erasure is guaranteed",
        "guarantees erasure",
        "cryptographically erased",
    ):
        assert overclaim not in storage_source
