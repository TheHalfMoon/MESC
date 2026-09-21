"""CW-002 focused acceptance tests for local protected storage and key management.

Scope and honesty statements:

* every fixture here is synthetic; this module creates no patient, clinical, research
  or publication authority;
* the store under test is exercised through the CW-002 public surface only, except
  where a test deliberately tampers with raw SQLite state to prove fail-closed
  behaviour (those cases live in the companion adversarial module);
* the RFC 5869 vectors below are the published RFC A.1-A.3 vectors, so the local
  HKDF implementation is checked against the standard rather than against itself.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open. These tests import it at runtime through
# sys.path; declaring the missing import here keeps that deferral explicit instead of
# silently widening the typing surface.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_PACKAGE = REPOSITORY_ROOT / "apps" / "workspace" / "pyproject.toml"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402
from medscale_workspace.aead import (  # noqa: E402
    HEADER_SIZE_BYTES,
    NONCE_SIZE_BYTES,
    parse_envelope_header,
)
from medscale_workspace.binding import ObjectBinding  # noqa: E402
from medscale_workspace.errors import (  # noqa: E402
    EnvelopeAuthenticationError,
    KeyProviderUnavailableError,
    ObjectNotFoundError,
    StoreVersionError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType  # noqa: E402
from medscale_workspace.keyderive import (  # noqa: E402
    derive_workspace_key,
    hkdf_sha256,
    hkdf_sha256_extract,
)
from medscale_workspace.keyprovider import (  # noqa: E402
    InMemoryTestKeyProvider,
    new_root_secret,
    resolve_platform_key_provider,
)
from medscale_workspace.storage import (  # noqa: E402
    KeyState,
    ObjectWrite,
    WorkspaceStore,
)
from medscale_workspace.store_path import (  # noqa: E402
    STORE_FILENAME_SUFFIX,
    resolve_workspace_store_path,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("1a3d7c22-42f4-4b76-9d6f-0c2c8db0f3a1")
PATIENT_OBJECT = UUID("2f1b7c8e-6a4d-4f9c-8f1e-5b6a7c8d9e0f")
ENCOUNTER_OBJECT = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
SENSITIVE_SYNTHETIC_PAYLOAD = (
    b'SYNTHETIC-NOT-REAL:{"note":"synthetic chest pain follow-up","medication":"synthetic-drug-A"}'
)

#: RFC 5869 appendix A test vectors (SHA-256).
RFC5869_A1 = {
    "ikm": bytes.fromhex("0b" * 22),
    "salt": bytes.fromhex("000102030405060708090a0b0c"),
    "info": bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
    "length": 42,
    "prk": ("077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5"),
    "okm": ("3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"),
}
RFC5869_A3 = {
    "ikm": bytes.fromhex("0b" * 22),
    "salt": b"",
    "info": b"",
    "length": 42,
    "okm": ("8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"),
}


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


def read_envelope(store_path: str, object_id: UUID, revision: str) -> bytes:
    connection = sqlite3.connect(store_path)
    try:
        row = connection.execute(
            "SELECT envelope FROM objects WHERE object_id = ? AND object_revision = ?",
            (str(object_id), revision),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, "the synthetic object revision must have been stored"
    return bytes(row[0])


def read_salt(store_path: str, key_version: int) -> bytes:
    connection = sqlite3.connect(store_path)
    try:
        row = connection.execute(
            "SELECT salt FROM key_versions WHERE key_version = ?", (key_version,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    return bytes(row[0])


def store_files(store_path: str) -> tuple[Path, ...]:
    primary = Path(store_path)
    candidates = [primary, Path(f"{store_path}-wal"), Path(f"{store_path}-shm")]
    return tuple(candidate for candidate in candidates if candidate.exists())


# ---------------------------------------------------------------------------
# Dependency and derivation contracts
# ---------------------------------------------------------------------------


def test_workspace_package_declares_exactly_one_aead_dependency() -> None:
    import tomllib

    configuration = tomllib.loads(WORKSPACE_PACKAGE.read_text(encoding="utf-8"))
    assert configuration["project"]["dependencies"] == ["cryptography==50.0.1"], (
        "ADR-0039 decision 5 admits exactly one runtime dependency, for the AEAD primitive"
    )
    root_configuration = tomllib.loads(
        (REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    assert root_configuration["project"]["dependencies"] == [], (
        "the Research Core package must stay free of runtime dependencies"
    )
    assert "cryptography>=50.0.1" in root_configuration["dependency-groups"]["dev"], (
        "the authoritative CI environment must install the workspace AEAD dependency"
    )


def test_hkdf_sha256_matches_rfc5869_vector_a1() -> None:
    pseudorandom_key = hkdf_sha256_extract(
        salt=RFC5869_A1["salt"],
        input_key_material=RFC5869_A1["ikm"],
    )
    assert pseudorandom_key.hex() == RFC5869_A1["prk"]
    okm = hkdf_sha256(
        salt=RFC5869_A1["salt"],
        input_key_material=RFC5869_A1["ikm"],
        info=RFC5869_A1["info"],
        length=RFC5869_A1["length"],
    )
    assert okm.hex() == RFC5869_A1["okm"]


def test_hkdf_sha256_matches_rfc5869_vector_a3_with_empty_salt_and_info() -> None:
    okm = hkdf_sha256(
        salt=RFC5869_A3["salt"],
        input_key_material=RFC5869_A3["ikm"],
        info=RFC5869_A3["info"],
        length=RFC5869_A3["length"],
    )
    assert okm.hex() == RFC5869_A3["okm"]


def test_derived_keys_are_separated_per_workspace_and_key_version() -> None:
    root_secret = new_root_secret()
    salt = hashlib.sha256(b"cw-002-synthetic-salt").digest()[:16]
    alpha_v1 = derive_workspace_key(
        root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, salt=salt, key_version=1
    )
    alpha_v2 = derive_workspace_key(
        root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, salt=salt, key_version=2
    )
    beta_v1 = derive_workspace_key(
        root_secret=root_secret, workspace_id=WORKSPACE_BETA, salt=salt, key_version=1
    )
    assert len(alpha_v1) == 32
    assert len({alpha_v1, alpha_v2, beta_v1}) == 3


def test_workspace_sources_never_use_the_reserved_password_kdf() -> None:
    for path in sorted((WORKSPACE_SRC / "medscale_workspace").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        assert "scrypt" not in source, (
            f"{path.name}: A1.1/A1.2 replace the workspace KDF with HKDF-SHA-256"
        )


# ---------------------------------------------------------------------------
# Envelope behaviour
# ---------------------------------------------------------------------------


def test_payload_round_trips_through_the_store(tmp_path: Path) -> None:
    store_path = resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA)
    with open_store(tmp_path) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        assert store.get_object(binding_for()) == SENSITIVE_SYNTHETIC_PAYLOAD
        assert store.object_count() == 1
        assert store.store_path == store_path


def test_every_encryption_uses_a_fresh_96_bit_nonce(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        for index in range(64):
            store.put_objects_atomic(
                (
                    ObjectWrite(
                        binding=binding_for(revision=f"rev-{index:04d}"),
                        payload=SENSITIVE_SYNTHETIC_PAYLOAD,
                    ),
                )
            )
        envelopes = [
            read_envelope(store.store_path, PATIENT_OBJECT, f"rev-{index:04d}")
            for index in range(64)
        ]
    headers = [parse_envelope_header(envelope) for envelope in envelopes]
    nonces = [header.nonce for header in headers]
    assert all(len(nonce) == NONCE_SIZE_BYTES == 12 for nonce in nonces)
    assert len(set(nonces)) == len(nonces), "a nonce was reused with the same key"
    assert len(set(envelopes)) == len(envelopes), "identical payloads produced identical bytes"
    assert all(header.key_version == 1 for header in headers)
    assert all(header.encryption_format_version == 1 for header in headers)


def test_envelope_size_is_header_plus_payload_plus_tag(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        envelope = read_envelope(store.store_path, PATIENT_OBJECT, "rev-0001")
    assert len(envelope) == HEADER_SIZE_BYTES + len(SENSITIVE_SYNTHETIC_PAYLOAD) + 16


# ---------------------------------------------------------------------------
# Leakage surface (A1.9) and declared plaintext metadata scope (A1.10)
# ---------------------------------------------------------------------------


def test_synthetic_payload_plaintext_is_absent_from_every_store_artifact(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        store_path = store.store_path
        envelope = read_envelope(store_path, PATIENT_OBJECT, "rev-0001")
        salt = read_salt(store_path, 1)
    derived_key = derive_workspace_key(
        root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, salt=salt, key_version=1
    )
    files = store_files(store_path)
    assert files, "the store must have persisted at least one file"
    blob = b"".join(path.read_bytes() for path in files)
    # Non-vacuity control: the ciphertext really is persisted, and it really does
    # not contain the plaintext.
    assert envelope[HEADER_SIZE_BYTES : HEADER_SIZE_BYTES + 16] in blob
    assert SENSITIVE_SYNTHETIC_PAYLOAD not in envelope
    assert SENSITIVE_SYNTHETIC_PAYLOAD not in blob
    assert b"synthetic chest pain follow-up" not in blob
    assert derived_key not in blob
    assert root_secret not in blob


def test_store_declares_which_metadata_stays_plaintext(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        scope = store.plaintext_metadata_scope()
    assert "sqlite_structural_metadata" in scope
    assert "object_revision_ids" in scope
    assert "key_derivation_salts" in scope
    assert "sensitive_payload" not in scope
    # The declared scope is a real property of the store, not prose: object identity
    # is visible while payload content is not.
    with open_store(tmp_path) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        store_path = store.store_path
    blob = b"".join(path.read_bytes() for path in store_files(store_path))
    assert str(PATIENT_OBJECT).encode("ascii") in blob
    assert b"rev-0001" in blob
    assert SENSITIVE_SYNTHETIC_PAYLOAD not in blob


# ---------------------------------------------------------------------------
# Pragma, version and migration state
# ---------------------------------------------------------------------------


def test_durability_and_integrity_pragmas_are_effective_not_defaults(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        pragmas = store.pragmas()
    assert pragmas.journal_mode == "wal"
    assert pragmas.synchronous == 2
    assert pragmas.foreign_keys == 1
    assert pragmas.secure_delete == 1
    assert pragmas.busy_timeout_ms == 5000


def test_version_tuple_is_recorded_first_class(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        versions = store.versions
        migration_log = store.migration_log()
    assert versions.application_version == APPLICATION_VERSION
    assert versions.workspace_schema_version == 1
    assert versions.minimum_readable_workspace_schema == 1
    assert versions.maximum_readable_workspace_schema == 1
    assert versions.policy_version == "mesc-clinical-workspace-synthetic-only/1"
    assert versions.encryption_format_version == 1
    assert migration_log == (("cw-002-store-initialization", "M1", 0, 1, "COMPLETED"),)


def test_versions_survive_reopening_with_the_same_key_provider(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
    with open_store(tmp_path, root_secret=root_secret) as reopened:
        assert reopened.versions.application_version == APPLICATION_VERSION
        assert reopened.get_object(binding_for()) == SENSITIVE_SYNTHETIC_PAYLOAD
        assert reopened.key_states() == ((1, KeyState.ACTIVE),)


def test_a_store_file_cannot_be_adopted_as_another_workspace(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        alpha_path = Path(store.store_path)
    beta_path = Path(resolve_workspace_store_path(str(tmp_path), WORKSPACE_BETA))
    beta_path.write_bytes(alpha_path.read_bytes())
    with pytest.raises(WorkspaceIsolationError):
        open_store(tmp_path, workspace_id=WORKSPACE_BETA)


# ---------------------------------------------------------------------------
# Workspace isolation
# ---------------------------------------------------------------------------


def test_two_workspaces_are_isolated_in_separate_stores(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with (
        open_store(tmp_path, workspace_id=WORKSPACE_ALPHA, root_secret=root_secret) as alpha,
        open_store(tmp_path, workspace_id=WORKSPACE_BETA, root_secret=root_secret) as beta,
    ):
        alpha.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        beta.put_objects_atomic(
            (
                ObjectWrite(
                    binding=binding_for(workspace_id=WORKSPACE_BETA),
                    payload=b"SYNTHETIC-NOT-REAL:beta-workspace-only",
                ),
            )
        )
        assert alpha.get_object(binding_for()) == SENSITIVE_SYNTHETIC_PAYLOAD
        assert beta.object_count() == 1
        assert alpha.store_path != beta.store_path
        with pytest.raises(WorkspaceIsolationError):
            alpha.get_object(binding_for(workspace_id=WORKSPACE_BETA))


def test_store_paths_stay_inside_the_supplied_root(tmp_path: Path) -> None:
    resolved = resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA)
    assert resolved.startswith(str(tmp_path))
    assert resolved.endswith(f"{WORKSPACE_ALPHA}{STORE_FILENAME_SUFFIX}")
    assert Path(resolved).parent == tmp_path


# ---------------------------------------------------------------------------
# Key rotation state machine (A1.6)
# ---------------------------------------------------------------------------


def test_rotation_retires_the_previous_key_after_verified_migration(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        for index in range(3):
            store.put_objects_atomic(
                (
                    ObjectWrite(
                        binding=binding_for(revision=f"rev-{index:04d}"),
                        payload=SENSITIVE_SYNTHETIC_PAYLOAD + str(index).encode("ascii"),
                    ),
                )
            )
        before = read_envelope(store.store_path, PATIENT_OBJECT, "rev-0001")
        store.begin_key_rotation(2)
        assert store.active_key_version == 2
        assert store.key_state(1) is KeyState.ROTATING
        assert store.key_state(2) is KeyState.ACTIVE
        assert store.rotate_pending(max_objects=2) == 2
        assert store.rotate_pending(max_objects=2) == 1
        assert store.rotate_pending(max_objects=2) == 0
        assert store.finalize_key_rotation() == 1
        assert store.key_state(1) is KeyState.RETIRING
        store.retire_key_version(1)
        assert store.key_state(1) is KeyState.RETIRED
        after = read_envelope(store.store_path, PATIENT_OBJECT, "rev-0001")
        assert store.get_object(binding_for(revision="rev-0001")) == (
            SENSITIVE_SYNTHETIC_PAYLOAD + b"1"
        )
        assert after != before
        assert parse_envelope_header(after).key_version == 2
        assert parse_envelope_header(after).nonce != parse_envelope_header(before).nonce
        assert [version for version, _ in store.key_states()] == [1, 2]


def test_interrupted_rotation_resumes_deterministically(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        for index in range(3):
            store.put_objects_atomic(
                (
                    ObjectWrite(
                        binding=binding_for(revision=f"rev-{index:04d}"),
                        payload=SENSITIVE_SYNTHETIC_PAYLOAD,
                    ),
                )
            )
        store.begin_key_rotation(2)
        assert store.rotate_pending(max_objects=1) == 1
    # A crash-equivalent restart: reopening must observe the persisted rotation state.
    with open_store(tmp_path, root_secret=root_secret) as reopened:
        assert reopened.active_key_version == 2
        assert reopened.key_state(1) is KeyState.ROTATING
        assert reopened.rotate_pending(max_objects=1) == 1
        assert reopened.rotate_pending(max_objects=1) == 1
        assert reopened.rotate_pending(max_objects=1) == 0
        assert reopened.finalize_key_rotation() == 1
        assert reopened.key_state(1) is KeyState.RETIRING
    with open_store(tmp_path, root_secret=root_secret) as finalized:
        assert finalized.active_key_version == 2
        assert finalized.key_state(1) is KeyState.RETIRING
        assert finalized.rotate_pending(max_objects=5) == 0
        for index in range(3):
            assert (
                finalized.get_object(binding_for(revision=f"rev-{index:04d}"))
                == SENSITIVE_SYNTHETIC_PAYLOAD
            )


def test_new_writes_after_rotation_use_the_new_active_key(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(revision="rev-0001"), payload=b"SYNTHETIC-first"),)
        )
        store.begin_key_rotation(2)
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(revision="rev-0002"), payload=b"SYNTHETIC-second"),)
        )
        assert (
            parse_envelope_header(
                read_envelope(store.store_path, PATIENT_OBJECT, "rev-0002")
            ).key_version
            == 2
        )
        assert store.rotate_pending(max_objects=5) == 1
        assert (
            parse_envelope_header(
                read_envelope(store.store_path, PATIENT_OBJECT, "rev-0001")
            ).key_version
            == 2
        )
        assert store.finalize_key_rotation() == 1
        assert store.get_object(binding_for(revision="rev-0002")) == b"SYNTHETIC-second"


# ---------------------------------------------------------------------------
# Deletion semantics
# ---------------------------------------------------------------------------


def test_delete_removes_the_row_and_makes_the_object_unreadable(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
        assert store.delete_object(binding_for()) is True
        assert store.object_count() == 0
        assert store.delete_object(binding_for()) is False
        with pytest.raises(ObjectNotFoundError):
            store.get_object(binding_for())


def test_deletion_makes_no_cryptographic_erasure_claim() -> None:
    source = (WORKSPACE_SRC / "medscale_workspace" / "storage.py").read_text(encoding="utf-8")
    lowered = " ".join(source.lower().split())
    assert "defense in depth" in lowered
    assert "not cryptographic erasure" in lowered
    assert "cryptographically erased" not in lowered


# ---------------------------------------------------------------------------
# Fail-closed provider behaviour
# ---------------------------------------------------------------------------


def test_platform_provider_is_unavailable_and_fails_closed_before_any_file(tmp_path: Path) -> None:
    provider = resolve_platform_key_provider()
    assert provider.capabilities.protected_secret_storage is False
    assert provider.capabilities.available is False
    assert provider.capabilities.production_selectable is True
    store_path = Path(resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA))
    with pytest.raises(KeyProviderUnavailableError):
        WorkspaceStore.open(
            store_root=str(tmp_path),
            workspace_id=WORKSPACE_ALPHA,
            key_provider=provider,
            application_version=APPLICATION_VERSION,
        )
    assert not store_path.exists(), "fail-closed must happen before the store file is created"


def test_in_memory_test_provider_is_not_production_selectable() -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    assert provider.capabilities.production_selectable is False
    assert provider.capabilities.persistent is False
    assert provider.capabilities.protected_secret_storage is False


def test_store_refuses_a_newer_recorded_schema_version(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        store_path = store.store_path
    connection = sqlite3.connect(store_path)
    try:
        connection.execute(
            "UPDATE store_metadata SET value = '2' WHERE name = 'workspace_schema_version'"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(StoreVersionError):
        open_store(tmp_path)


def test_copied_store_is_unreadable_without_the_original_root_secret(tmp_path: Path) -> None:
    original = new_root_secret()
    with open_store(tmp_path, root_secret=original) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=binding_for(), payload=SENSITIVE_SYNTHETIC_PAYLOAD),)
        )
    with (
        open_store(tmp_path, root_secret=new_root_secret()) as wrong_key_store,
        pytest.raises(EnvelopeAuthenticationError),
    ):
        wrong_key_store.get_object(binding_for())


def test_associated_data_is_canonical_and_binds_every_component() -> None:
    binding = binding_for()
    canonical = binding.canonical_associated_data(key_version=1, encryption_format_version=1)
    document = json.loads(canonical)
    assert set(document) == {
        "domain",
        "encryption_format_version",
        "key_version",
        "object_id",
        "object_revision",
        "object_type",
        "workspace_id",
    }
    assert document["domain"] == "mesc-clinical-workspace-object-aad/1"
    variants = {
        binding.canonical_associated_data(key_version=version, encryption_format_version=1)
        for version in (1, 2, 3)
    }
    assert len(variants) == 3
    assert (
        binding_for(revision="rev-0002").canonical_associated_data(
            key_version=1, encryption_format_version=1
        )
        != canonical
    )
