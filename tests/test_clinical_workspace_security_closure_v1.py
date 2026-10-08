"""CW-019 security and privacy closure: attacks across the canonical review lanes.

Every case here attacks the synthetic/local implementation as it exists on canonical
main. A protection is claimed only where a case below proves it; the residual risks
that remain are asserted as residual (for example whole-store rollback), not hidden.
"""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

import ast
import importlib.metadata
import json
import shutil
import socket
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_MODULES = WORKSPACE_SRC / "medscale_workspace"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import data_class as data_class_mod  # noqa: E402 runtime import
from medscale_workspace import lifecycle as lc  # noqa: E402 runtime import
from medscale_workspace import nobackflow as nobackflow_mod  # noqa: E402 runtime import
from medscale_workspace.binding import ObjectBinding  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    BackflowError,
    KeyMaterialUnavailableError,
    StoreMigrationRequiredError,
    StoreSealError,
    WorkspaceStoreError,
)
from medscale_workspace.identity import WorkspaceObjectType  # noqa: E402 runtime import
from medscale_workspace.keyderive import (  # noqa: E402 runtime import
    derive_backup_key,
    derive_seal_key,
    derive_workspace_key,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    KeyProvider,
    new_root_secret,
)
from medscale_workspace.storage import (  # noqa: E402 runtime import
    KeyState,
    ObjectWrite,
    StoreRole,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ACTOR = "synthetic-security-operator"
T1 = "2026-09-30T10:00:00+03:00"
T2 = "2026-09-30T10:01:00+03:00"
T3 = "2026-09-30T10:02:00+03:00"
MARKER = b"PLANTED-SYNTHETIC-SECURITY-MARKER-Z19"
PATIENTS = tuple(UUID(f"40000000-0000-4000-8000-00000000000{index}") for index in range(1, 7))
PLENTY = 1 << 40


def open_live(root: Path, provider: KeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    )


def open_quarantine(root: Path, provider: KeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
        role=StoreRole.QUARANTINE,
    )


def open_maintenance(root: Path, provider: KeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open_for_maintenance(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    )


def binding(index: int, revision: str = "rev-00000001") -> ObjectBinding:
    return ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=PATIENTS[index],
        object_type=WorkspaceObjectType.PATIENT,
        object_revision=revision,
    )


def payload(index: int) -> bytes:
    return json.dumps(
        {"given_name": f"synthetic-{index}", "note": MARKER.decode("ascii")}, sort_keys=True
    ).encode("ascii")


def seeded(root: Path, provider: KeyProvider, count: int = 3) -> str:
    with open_live(root, provider) as store:
        trail = AuditTrail(store)
        for index in range(count):
            store.put_objects_atomic((ObjectWrite(binding=binding(index), payload=payload(index)),))
            trail.record_object_write(
                binding=binding(index), payload=payload(index), actor_id=ACTOR, occurred_at=T1
            )
        return str(store.store_path)


def raw(store_path: str, *statements: tuple[str, tuple[object, ...]]) -> None:
    connection = sqlite3.connect(store_path)
    try:
        for statement, parameters in statements:
            connection.execute(statement, parameters)
        connection.commit()
    finally:
        connection.close()


# ---------------------------------------------------------------------------
# Lane: local storage / key management -- the CW-019 integrity seal
# ---------------------------------------------------------------------------

TAMPERING = {
    "retired_key_reactivated": (
        ("UPDATE key_versions SET state = 'RETIRING' WHERE key_version = 2", ()),
        ("UPDATE key_versions SET state = 'ACTIVE' WHERE key_version = 1", ()),
    ),
    "key_salt_swapped": (
        ("UPDATE key_versions SET salt = zeroblob(16) WHERE key_version = 2", ()),
    ),
    "store_role_flipped": (
        ("UPDATE store_metadata SET value = 'QUARANTINE' WHERE name = 'store_role'", ()),
    ),
    "policy_version_edited": (
        ("UPDATE store_metadata SET value = 'production/1' WHERE name = 'policy_version'", ()),
    ),
    "journal_row_forged": (
        (
            "INSERT INTO migration_journal VALUES ('forged', 'M2', 'COMPLETED', 0, '{}')",
            (),
        ),
    ),
    "migration_log_edited": (("UPDATE migration_log SET result = 'FAILED'", ()),),
    "tombstone_removed": (("DELETE FROM deletion_tombstones", ()),),
    "tombstone_reason_weakened": (
        ("UPDATE deletion_tombstones SET reason = 'MIGRATION_SUPERSEDED'", ()),
    ),
    "object_row_deleted": (("DELETE FROM objects WHERE object_type = 'Patient'", ()),),
    "audit_tail_truncated": (
        (
            "DELETE FROM objects WHERE object_type = 'AuditEvent' AND object_revision = "
            "(SELECT MAX(object_revision) FROM objects WHERE object_type = 'AuditEvent')",
            (),
        ),
    ),
    "envelope_byte_flipped": (
        (
            "UPDATE objects SET envelope = CAST(zeroblob(64) AS BLOB) "
            "WHERE object_type = 'Patient'",
            (),
        ),
    ),
    "row_key_version_edited": (("UPDATE objects SET key_version = 1", ()),),
    "seal_row_deleted": (("DELETE FROM store_metadata WHERE name = 'integrity_seal'", ()),),
    "seal_salt_replaced": (
        (
            "UPDATE store_metadata SET value = '00000000000000000000000000000000' "
            "WHERE name = 'seal_salt'",
            (),
        ),
    ),
}


def rotated_store_with_deletion(root: Path, provider: KeyProvider) -> str:
    path = seeded(root, provider, 3)
    with open_live(root, provider) as store:
        store.delete_object(binding(2))
        lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=10, actor_id=ACTOR, occurred_at=T2
        )
    return path


@pytest.mark.parametrize("attack", sorted(TAMPERING))
def test_the_integrity_seal_refuses_every_raw_tampering_class(tmp_path: Path, attack: str) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    path = rotated_store_with_deletion(tmp_path, provider)
    raw(path, *TAMPERING[attack])
    with pytest.raises(StoreSealError):
        open_live(tmp_path, provider)
    with pytest.raises(StoreSealError):
        open_maintenance(tmp_path, provider)


def test_a_retired_key_cannot_be_made_to_write_again_by_editing_key_state(
    tmp_path: Path,
) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    path = rotated_store_with_deletion(tmp_path, provider)
    with open_live(tmp_path, provider) as store:
        assert dict(store.key_states()) == {1: KeyState.RETIRED, 2: KeyState.ACTIVE}
    raw(path, *TAMPERING["retired_key_reactivated"])
    with pytest.raises(StoreSealError):
        open_live(tmp_path, provider)


def test_the_wrong_root_secret_is_refused_before_any_envelope_is_read(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    seeded(tmp_path, provider)
    with pytest.raises(StoreSealError):
        open_live(tmp_path, InMemoryTestKeyProvider(new_root_secret()))


def test_the_seal_key_is_separated_from_data_and_backup_keys() -> None:
    root_secret = new_root_secret()
    salt = bytes(range(16))
    seal = derive_seal_key(root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, salt=salt)
    data = derive_workspace_key(
        root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, salt=salt, key_version=1
    )
    backup = derive_backup_key(
        root_secret=root_secret, workspace_id=WORKSPACE_ALPHA, backup_id=UUID(int=1), salt=salt
    )
    other_workspace = derive_seal_key(root_secret=root_secret, workspace_id=UUID(int=9), salt=salt)
    assert len({seal, data, backup, other_workspace}) == 4
    assert len(seal) == 32


def test_a_short_seal_key_is_refused_before_any_store_is_sealed(tmp_path: Path) -> None:
    class ShortSealProvider(InMemoryTestKeyProvider):  # type: ignore[misc]
        def seal_key(self, *, workspace_id: UUID, salt: bytes) -> bytes:
            del workspace_id, salt
            return b"\x00" * 8

    with pytest.raises(KeyMaterialUnavailableError):
        open_live(tmp_path, ShortSealProvider(new_root_secret()))


def test_the_seal_is_rewritten_by_every_mutating_api_path(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    live, quarantine, recovery = tmp_path / "live", tmp_path / "quarantine", tmp_path / "recovery"
    for root in (live, quarantine, recovery):
        root.mkdir()
    seeded(live, provider, 3)

    def reopen(root: Path, role: StoreRole = StoreRole.LIVE) -> None:
        opener = open_quarantine if role is StoreRole.QUARANTINE else open_live
        with opener(root, provider) as store:
            assert store.object_count() >= 0

    with open_live(live, provider) as store:
        store.delete_object(binding(0))
    reopen(live)
    with open_live(live, provider) as store:
        AuditTrail(store).record_object_deletion(binding=binding(1), actor_id=ACTOR, occurred_at=T2)
    reopen(live)
    with open_live(live, provider) as store:
        store.begin_key_rotation(2)
    reopen(live)
    with open_live(live, provider) as store:
        store.rotate_pending(max_objects=2)
    reopen(live)
    with open_live(live, provider) as store:
        lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=10, actor_id=ACTOR, occurred_at=T2
        )
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
    reopen(live)
    lc.restore_backup_to_quarantine(
        data,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(quarantine),
        application_version=APPLICATION_VERSION,
    )
    reopen(quarantine, StoreRole.QUARANTINE)
    with open_live(recovery, provider) as fresh, open_quarantine(quarantine, provider) as source:
        lc.promote_quarantine(fresh, source, actor_id=ACTOR, occurred_at=T3)
    reopen(recovery)
    with open_live(live, provider) as store, open_quarantine(quarantine, provider) as source:
        lc.rollback_to_quarantine(store, source, actor_id=ACTOR, occurred_at=T3)
        lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T3)
    reopen(live)


def test_tampering_while_the_store_is_open_is_not_blessed_by_the_next_write(
    tmp_path: Path,
) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    path = rotated_store_with_deletion(tmp_path, provider)
    with open_live(tmp_path, provider) as store:
        raw(path, *TAMPERING["tombstone_removed"])
        with pytest.raises(StoreSealError):
            store.put_objects_atomic((ObjectWrite(binding=binding(5), payload=b"later write"),))
        with pytest.raises(StoreSealError):
            lc.rotate_workspace_key(
                store, new_key_version=3, batch_size=10, actor_id=ACTOR, occurred_at=T3
            )
    with pytest.raises(StoreSealError):
        open_live(tmp_path, provider)


def test_a_backup_is_never_taken_from_state_tampered_while_open(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    path = rotated_store_with_deletion(tmp_path, provider)
    with open_live(tmp_path, provider) as store:
        raw(path, *TAMPERING["object_row_deleted"])
        with pytest.raises(StoreSealError):
            store.export_snapshot()
        with pytest.raises(StoreSealError):
            lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T3)


def test_an_unsealed_legacy_store_is_not_sealed_without_explicit_acknowledgement(
    tmp_path: Path,
) -> None:
    """A sealed store stripped back to "schema 2" and tampered is not silently re-sealed."""

    provider = InMemoryTestKeyProvider(new_root_secret())
    path = rotated_store_with_deletion(tmp_path, provider)
    raw(
        path,
        ("DELETE FROM store_metadata WHERE name IN ('seal_salt', 'integrity_seal')", ()),
        (
            "UPDATE store_metadata SET value = '2' WHERE name IN ('workspace_schema_version', "
            "'minimum_readable_workspace_schema', 'maximum_readable_workspace_schema')",
            (),
        ),
        ("DELETE FROM deletion_tombstones", ()),
    )
    with pytest.raises(StoreMigrationRequiredError):
        open_live(tmp_path, provider)
    with pytest.raises(lc.MigrationError, match="acknowledge_unsealed_legacy_state"):
        lc.migrate_schema_to_current(
            store_root=str(tmp_path),
            workspace_id=WORKSPACE_ALPHA,
            key_provider=provider,
            source_application_version=APPLICATION_VERSION,
            target_application_version=APPLICATION_VERSION,
            available_bytes=PLENTY,
            actor_id=ACTOR,
            occurred_at=T3,
        )
    with open_maintenance(tmp_path, provider) as store:
        assert store.versions.workspace_schema_version == 2
        with pytest.raises(StoreMigrationRequiredError):
            store.put_objects_atomic((ObjectWrite(binding=binding(5), payload=b"x"),))


def test_whole_store_rollback_remains_undetected_by_the_seal(tmp_path: Path) -> None:
    """Residual risk (ADR-0039 A1.5): an older, internally consistent copy still opens."""

    provider = InMemoryTestKeyProvider(new_root_secret())
    path = Path(seeded(tmp_path, provider, 1))
    archive = tmp_path / "older-copy.sqlite3"
    shutil.copyfile(path, archive)
    with open_live(tmp_path, provider) as store:
        store.put_objects_atomic((ObjectWrite(binding=binding(4), payload=b"newer state"),))
        newer = store.object_count()
    shutil.copyfile(archive, path)
    with open_live(tmp_path, provider) as store:
        assert store.object_count() == newer - 1


def test_schema_2_stores_are_migrated_and_sealed_but_never_opened_normally(
    tmp_path: Path,
) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    path = seeded(tmp_path, provider, 2)
    raw(
        path,
        ("DELETE FROM store_metadata WHERE name IN ('seal_salt', 'integrity_seal')", ()),
        (
            "UPDATE store_metadata SET value = '2' WHERE name IN ('workspace_schema_version', "
            "'minimum_readable_workspace_schema', 'maximum_readable_workspace_schema')",
            (),
        ),
    )
    with pytest.raises(StoreMigrationRequiredError):
        open_live(tmp_path, provider)
    lc.migrate_schema_to_current(
        store_root=str(tmp_path),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        source_application_version=APPLICATION_VERSION,
        target_application_version=APPLICATION_VERSION,
        available_bytes=PLENTY,
        actor_id=ACTOR,
        occurred_at=T2,
        acknowledge_unsealed_legacy_state=True,
    )
    with open_live(tmp_path, provider) as store:
        assert store.versions.workspace_schema_version == 3
        assert store.get_object(binding(0)) == payload(0)
    raw(path, ("UPDATE store_metadata SET value = 'QUARANTINE' WHERE name = 'store_role'", ()))
    with pytest.raises(StoreSealError):
        open_live(tmp_path, provider)


# ---------------------------------------------------------------------------
# Lane: privacy / data flow -- no hidden egress, no Research Core backflow
# ---------------------------------------------------------------------------


class EgressAttemptError(AssertionError):
    pass


def _forbid(*_args: object, **_kwargs: object) -> None:
    raise EgressAttemptError("hidden network, process or remote access was attempted")


def test_no_hidden_egress_across_the_full_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(socket, "socket", _forbid)
    monkeypatch.setattr(socket, "create_connection", _forbid)
    monkeypatch.setattr(socket, "getaddrinfo", _forbid)
    monkeypatch.setattr(subprocess, "Popen", _forbid)
    monkeypatch.setattr(urllib.request, "urlopen", _forbid)
    provider = InMemoryTestKeyProvider(new_root_secret())
    live, quarantine, recovery = tmp_path / "live", tmp_path / "quarantine", tmp_path / "recovery"
    for root in (live, quarantine, recovery):
        root.mkdir()
    seeded(live, provider, 3)
    with open_live(live, provider) as store:
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=2, actor_id=ACTOR, occurred_at=T2
        )
        lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T2)
    lc.restore_backup_to_quarantine(
        data,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(quarantine),
        application_version=APPLICATION_VERSION,
    )
    with open_live(recovery, provider) as fresh, open_quarantine(quarantine, provider) as source:
        lc.promote_quarantine(fresh, source, actor_id=ACTOR, occurred_at=T3)
        AuditTrail(fresh).verify()


def test_the_workspace_package_imports_no_network_process_or_dynamic_import_module() -> None:
    forbidden = {
        "socket",
        "http",
        "urllib",
        "urllib3",
        "requests",
        "httpx",
        "aiohttp",
        "ftplib",
        "smtplib",
        "subprocess",
        "multiprocessing",
        "ctypes",
        "importlib",
        "os",
    }
    offenders = []
    for module in sorted(WORKSPACE_MODULES.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                if name.split(".")[0] in forbidden:
                    offenders.append(f"{module.name}:{name}")
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in {
                "__import__",
                "eval",
                "exec",
                "compile",
            }:
                offenders.append(f"{module.name}:{node.func.id}")  # type: ignore[attr-defined]
    assert offenders == []


def test_no_workspace_data_class_can_flow_into_research_core() -> None:
    research_core = data_class_mod.admit_trust_domain("ResearchCore")
    refused = 0
    for member in data_class_mod.DATA_CLASS_ADMISSIONS:
        classification = data_class_mod.classify(member.data_class)
        for explicit in (False, True):
            with pytest.raises(BackflowError):
                nobackflow_mod.admit_flow(
                    classification, research_core, explicit_user_request=explicit
                )
            refused += 1
    assert refused == 2 * len(data_class_mod.DATA_CLASS_ADMISSIONS)


# ---------------------------------------------------------------------------
# Lane: application security -- exception text never carries payload or keys
# ---------------------------------------------------------------------------


def _chain_text(error: BaseException) -> str:
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(f"{type(current).__name__}: {current!s} {current!r}")
        current = current.__cause__ or current.__context__
    return "\n".join(parts)


def test_failure_messages_never_carry_payload_or_key_material(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    provider = InMemoryTestKeyProvider(root_secret)
    live, quarantine = tmp_path / "live", tmp_path / "quarantine"
    live.mkdir()
    quarantine.mkdir()
    path = seeded(live, provider, 2)
    with open_live(live, provider) as store:
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
    manifest = lc.read_backup_manifest(data)
    backup_key = provider.backup_key(
        workspace_id=WORKSPACE_ALPHA,
        backup_id=manifest.backup_id,
        salt=bytes.fromhex(manifest.key_salt_hex),
    )
    failures: list[BaseException] = []

    def capture(action: object) -> None:
        try:
            action()  # type: ignore[operator]
        except (WorkspaceStoreError, ValueError, AssertionError) as error:
            failures.append(error)

    capture(lambda: lc.open_backup(data[:-3], provider, workspace_id=WORKSPACE_ALPHA))
    capture(
        lambda: lc.open_backup(
            data, InMemoryTestKeyProvider(new_root_secret()), workspace_id=WORKSPACE_ALPHA
        )
    )
    capture(lambda: open_live(live, InMemoryTestKeyProvider(new_root_secret())))
    with open_live(live, provider) as store:
        capture(
            lambda: store.put_objects_atomic((ObjectWrite(binding=binding(0), payload=payload(0)),))
        )
        capture(lambda: store.get_object(binding(5)))
    raw(path, ("UPDATE objects SET envelope = zeroblob(40) WHERE object_type = 'Patient'", ()))
    capture(lambda: open_live(live, provider))
    capture(
        lambda: lc.restore_backup_to_quarantine(
            data,
            provider,
            workspace_id=UUID(int=3),
            quarantine_root=str(quarantine),
            application_version=APPLICATION_VERSION,
        )
    )
    assert len(failures) == 7
    forbidden = (
        MARKER,
        root_secret,
        backup_key,
        root_secret.hex().encode("ascii"),
        backup_key.hex().encode("ascii"),
    )
    for failure in failures:
        text = _chain_text(failure).encode("utf-8", "backslashreplace")
        for secret in forbidden:
            assert secret not in text


# ---------------------------------------------------------------------------
# Lanes: supply chain and license / provenance
# ---------------------------------------------------------------------------


def test_the_admitted_runtime_dependency_surface_is_pinned_and_permissive() -> None:
    guard = (REPOSITORY_ROOT / "scripts" / "check_clinical_workspace_boundary.py").read_text(
        encoding="utf-8"
    )
    assert '"cryptography.hazmat.primitives.ciphers.aead",' in guard
    workflow = (REPOSITORY_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert '"cryptography==50.0.1"' in workflow
    distribution = importlib.metadata.distribution("cryptography")
    assert distribution.version == "50.0.1"
    metadata = distribution.metadata
    license_text = " ".join(
        [
            *metadata.get_all("License", []),
            *metadata.get_all("License-Expression", []),
            *metadata.get_all("Classifier", []),
        ]
    )
    assert "Apache" in license_text
    assert "BSD" in license_text
    workspace_imports = set()
    for module in WORKSPACE_MODULES.glob("*.py"):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                workspace_imports.add(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                workspace_imports.update(alias.name.split(".")[0] for alias in node.names)
    third_party = workspace_imports - set(sys.stdlib_module_names) - {"medscale_workspace"}
    assert third_party <= {"cryptography", "torch", "transformers"}


# ---------------------------------------------------------------------------
# Lane: backup / delete -- the recovery runbook exercised end to end
# ---------------------------------------------------------------------------


class Nest(lc.SemanticTransform):  # type: ignore[misc]
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject

    def transform(self, binding: ObjectBinding, payload: bytes) -> bytes:
        document = json.loads(payload.decode("ascii"))
        return json.dumps(
            {"name": {"given": document["given_name"]}, "representation": 2}, sort_keys=True
        ).encode("ascii")

    def validate(self, binding: ObjectBinding, payload: bytes) -> bool:
        return not self.reject and json.loads(payload.decode("ascii"))["representation"] == 2


def test_the_recovery_runbook_exercises_pass_end_to_end(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    live, quarantine, recovery = tmp_path / "live", tmp_path / "quarantine", tmp_path / "recovery"
    for root in (live, quarantine, recovery):
        root.mkdir()
    path = Path(seeded(live, provider, 3))
    with open_live(live, provider) as store:
        snapshot = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        before = {
            str(item.binding.object_id): item.payload
            for item in store.export_snapshot().objects
            if item.binding.object_type is WorkspaceObjectType.PATIENT
        }
        versions = store.versions
        manifest = lc.MigrationManifest(
            migration_id="cw-019-runbook-exercise",
            migration_class=lc.MigrationClass.M2,
            workspace_id=WORKSPACE_ALPHA,
            source_app_version=versions.application_version,
            target_app_version=versions.application_version,
            source_workspace_schema_version=versions.workspace_schema_version,
            target_workspace_schema_version=versions.workspace_schema_version,
            source_policy_version=versions.policy_version,
            target_policy_version=versions.policy_version,
            source_encryption_format_version=versions.encryption_format_version,
            target_encryption_format_version=versions.encryption_format_version,
            required_key_versions=(store.active_key_version,),
            affected_object_types=(WorkspaceObjectType.PATIENT,),
            affected_projection_types=(),
            preconditions=("synthetic fixtures",),
            expected_object_counts=lc.expected_object_counts(store, (WorkspaceObjectType.PATIENT,)),
            pre_migration_snapshot_identity=lc.read_backup_manifest(snapshot).backup_id,
            steps=("nest given names",),
            postconditions=("validates",),
            rollback_strategy=lc.RollbackStrategy.SNAPSHOT_ROLLBACK,
            irreversible_operations=(),
            external_side_effects=(),
            tool_version=lc.LIFECYCLE_TOOL_VERSION,
            started_at=T2,
        )
        with pytest.raises(lc.MigrationValidationError):
            lc.begin_semantic_migration(
                store,
                manifest,
                Nest(reject=True),
                provider,
                available_bytes=PLENTY,
                snapshot=snapshot,
                actor_id=ACTOR,
                occurred_at=T2,
            )
    # Runbook 4 + 5.2: a failed migration is rolled back from the protected snapshot.
    lc.restore_backup_to_quarantine(
        snapshot,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(quarantine),
        application_version=APPLICATION_VERSION,
    )
    with open_maintenance(live, provider) as store, open_quarantine(quarantine, provider) as source:
        lc.rollback_to_quarantine(
            store,
            source,
            actor_id=ACTOR,
            occurred_at=T3,
            journal_migration_id="cw-019-runbook-exercise",
        )
    with open_live(live, provider) as store:
        after = {
            str(item.binding.object_id): item.payload
            for item in store.export_snapshot().objects
            if item.binding.object_type is WorkspaceObjectType.PATIENT
        }
        # Runbook 6: rotation after recovery.
        lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=2, actor_id=ACTOR, occurred_at=T3
        )
        final_backup = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T3)
    assert after == before
    # Runbook 3: disaster recovery -- the live store is lost; recover into a fresh store.
    path.unlink()
    second_quarantine = tmp_path / "second-quarantine"
    second_quarantine.mkdir()
    lc.restore_backup_to_quarantine(
        final_backup,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(second_quarantine),
        application_version=APPLICATION_VERSION,
    )
    with (
        open_live(recovery, provider) as fresh,
        open_quarantine(second_quarantine, provider) as source,
    ):
        lc.promote_quarantine(fresh, source, actor_id=ACTOR, occurred_at=T3)
        recovered = {
            str(item.binding.object_id): item.payload
            for item in fresh.export_snapshot().objects
            if item.binding.object_type is WorkspaceObjectType.PATIENT
        }
        AuditTrail(fresh).verify()
    assert recovered == before
