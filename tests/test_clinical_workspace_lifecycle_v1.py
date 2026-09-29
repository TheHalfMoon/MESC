"""CW-018 acceptance tests: backup, restore, deletion, key rotation, and migration."""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import dataset as dataset_mod  # noqa: E402 runtime import
from medscale_workspace import lifecycle as lc  # noqa: E402 runtime import
from medscale_workspace import patient_graph as pg_mod  # noqa: E402 runtime import
from medscale_workspace import research_view as view_mod  # noqa: E402 runtime import
from medscale_workspace.audit import AuditEventType  # noqa: E402 runtime import
from medscale_workspace.binding import ObjectBinding  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    KeyStateError,
    MigrationValidationError,
    RestoreConflictError,
    StoreMigrationRequiredError,
    StoreRoleError,
    StoreVersionError,
)
from medscale_workspace.identity import WorkspaceObjectType  # noqa: E402 runtime import
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    SourceKind,
    SourceRef,
    describe_revision,
    provenance_binding_for,
    store_with_provenance,
)
from medscale_workspace.storage import (  # noqa: E402 runtime import
    JournalState,
    KeyState,
    ObjectWrite,
    StoreRole,
    TombstoneReason,
)
from medscale_workspace.versions import (  # noqa: E402 runtime import
    SCHEMA_V2_MIGRATION_ID,
    SCHEMA_V3_MIGRATION_ID,
    SUPPORTED_DOWNGRADE_TARGETS,
    WORKSPACE_SCHEMA_VERSION,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ACTOR = "synthetic-operator"
T1 = "2026-09-29T10:00:00+03:00"
T2 = "2026-09-29T10:01:00+03:00"
T3 = "2026-09-29T10:02:00+03:00"
PLANTED_MARKER = b"PLANTED-SYNTHETIC-MARKER-7Q41"
PATIENT_IDS = (
    UUID("10000000-0000-4000-8000-000000000001"),
    UUID("10000000-0000-4000-8000-000000000002"),
    UUID("10000000-0000-4000-8000-000000000003"),
    UUID("10000000-0000-4000-8000-000000000004"),
)
PLENTY_OF_SPACE = 1 << 40
MIGRATION_ID = "cw-018-fixture-patient-representation-v2"
SECTION_5_MANIFEST_FIELDS = {
    "migration_id",
    "migration_class",
    "source_app_version",
    "target_app_version",
    "source_workspace_schema_version",
    "target_workspace_schema_version",
    "source_policy_version",
    "target_policy_version",
    "source_encryption_format_version",
    "target_encryption_format_version",
    "required_key_versions",
    "affected_object_types",
    "affected_projection_types",
    "preconditions",
    "expected_object_counts",
    "pre_migration_snapshot_identity",
    "steps",
    "postconditions",
    "rollback_strategy",
    "irreversible_operations",
    "external_side_effects",
    "tool_version",
    "started_at",
    "completed_at",
    "result",
}


class Roots:
    """Separate explicit store roots for the live, quarantine and recovery stores."""

    def __init__(self, tmp_path: Path) -> None:
        self.live = tmp_path / "live"
        self.quarantine = tmp_path / "quarantine"
        self.recovery = tmp_path / "recovery"
        for root in (self.live, self.quarantine, self.recovery):
            root.mkdir()


def open_live(root: Path, provider: InMemoryTestKeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    )


def open_quarantine(root: Path, provider: InMemoryTestKeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
        role=StoreRole.QUARANTINE,
    )


def open_maintenance(root: Path, provider: InMemoryTestKeyProvider) -> WorkspaceStore:
    return WorkspaceStore.open_for_maintenance(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    )


def patient_binding(object_id: UUID, revision: str = "rev-00000001") -> ObjectBinding:
    return ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=object_id,
        object_type=WorkspaceObjectType.PATIENT,
        object_revision=revision,
    )


def patient_payload(index: int) -> bytes:
    return json.dumps(
        {"given_name": f"synthetic-{index}", "note": PLANTED_MARKER.decode("ascii")},
        sort_keys=True,
    ).encode("ascii")


def seed_patients(store: WorkspaceStore, count: int = 3) -> tuple[ObjectBinding, ...]:
    trail = AuditTrail(store)
    bindings: list[ObjectBinding] = []
    for index in range(count):
        binding = patient_binding(PATIENT_IDS[index])
        payload = patient_payload(index)
        store.put_objects_atomic((ObjectWrite(binding=binding, payload=payload),))
        trail.record_object_write(binding=binding, payload=payload, actor_id=ACTOR, occurred_at=T1)
        bindings.append(binding)
    return tuple(bindings)


def content_of(store: WorkspaceStore) -> dict[tuple[str, str, str], bytes]:
    return {
        (
            item.binding.object_type.value,
            str(item.binding.object_id),
            item.binding.object_revision,
        ): item.payload
        for item in store.export_snapshot().objects
    }


def non_audit(content: dict[tuple[str, str, str], bytes]) -> dict[tuple[str, str, str], bytes]:
    return {key: value for key, value in content.items() if key[0] != "AuditEvent"}


def audit_events(store: WorkspaceStore) -> list[tuple[str, dict[str, str]]]:
    return [(event.event_type.value, dict(event.metadata)) for event in AuditTrail(store).events()]


def make_legacy_schema_1_store(root: Path, provider: InMemoryTestKeyProvider) -> None:
    """Reproduce the exact CW-002 (schema 1) layout, holding synthetic objects."""

    with open_live(root, provider) as store:
        seed_patients(store, 2)
        path = store.store_path
    connection = sqlite3.connect(path)
    try:
        connection.execute("DROP TABLE deletion_tombstones")
        connection.execute("DROP TABLE migration_journal")
        connection.execute("DELETE FROM store_metadata WHERE name = 'store_role'")
        connection.execute(
            "DELETE FROM store_metadata WHERE name IN ('seal_salt', 'integrity_seal')"
        )
        for name in (
            "workspace_schema_version",
            "minimum_readable_workspace_schema",
            "maximum_readable_workspace_schema",
        ):
            connection.execute("UPDATE store_metadata SET value = '1' WHERE name = ?", (name,))
        connection.execute("UPDATE migration_log SET target_workspace_schema_version = 1")
        connection.commit()
    finally:
        connection.close()


class RepresentationV2(lc.SemanticTransform):  # type: ignore[misc]
    """Synthetic M2 fixture: nest ``given_name`` under ``name`` and mark version 2."""

    def __init__(self, *, fail_after: int | None = None, reject: bool = False) -> None:
        self.calls = 0
        self.fail_after = fail_after
        self.reject = reject

    def transform(self, binding: ObjectBinding, payload: bytes) -> bytes:
        if self.fail_after is not None and self.calls >= self.fail_after:
            raise RuntimeError("simulated power loss during the semantic migration")
        self.calls += 1
        document = json.loads(payload.decode("ascii"))
        migrated = {
            "name": {"given": document["given_name"]},
            "note": document["note"],
            "representation": 2,
        }
        return json.dumps(migrated, sort_keys=True).encode("ascii")

    def validate(self, binding: ObjectBinding, payload: bytes) -> bool:
        if self.reject:
            return False
        document = json.loads(payload.decode("ascii"))
        return document.get("representation") == 2 and "given_name" not in document


def semantic_manifest(
    store: WorkspaceStore,
    snapshot_id: UUID | None,
    strategy: lc.RollbackStrategy = lc.RollbackStrategy.SNAPSHOT_ROLLBACK,
) -> lc.MigrationManifest:
    versions = store.versions
    return lc.MigrationManifest(
        migration_id=MIGRATION_ID,
        migration_class=lc.MigrationClass.M2,
        workspace_id=store.workspace_id,
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
        preconditions=("synthetic patient fixtures at representation 1",),
        expected_object_counts=lc.expected_object_counts(store, (WorkspaceObjectType.PATIENT,)),
        pre_migration_snapshot_identity=snapshot_id,
        steps=("rewrite each patient revision into representation 2",),
        postconditions=("patient count reconciled", "every revision validates"),
        rollback_strategy=strategy,
        irreversible_operations=(),
        external_side_effects=(),
        tool_version=lc.LIFECYCLE_TOOL_VERSION,
        started_at=T2,
    )


# --- encrypted backup and integrity manifest ------------------------------------------


def test_backup_is_encrypted_and_carries_a_versioned_integrity_manifest(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        store.delete_object(patient_binding(PATIENT_IDS[2]))
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        events = audit_events(store)
    manifest = lc.read_backup_manifest(data)
    assert data.startswith(lc.BACKUP_MAGIC)
    assert manifest.backup_format_version == 1
    assert manifest.workspace_id == WORKSPACE_ALPHA
    assert manifest.workspace_schema_version == WORKSPACE_SCHEMA_VERSION
    assert manifest.included_data_classes == ("SYNTHETIC",)
    assert manifest.included_object_types == ("AuditEvent", "Patient")
    assert len(manifest.objects) == 5
    assert manifest.audit_event_count == 3
    assert [item.reason for item in manifest.tombstones] == [TombstoneReason.USER_DELETION]
    assert all(entry.content_digest.startswith("sha256:") for entry in manifest.objects)
    assert PLANTED_MARKER not in data
    assert b"synthetic-0" not in data
    assert events[-1][0] == AuditEventType.BACKUP.value
    assert events[-1][1]["backup_id"] == str(manifest.backup_id)
    assert events[-1][1]["object_count"] == "5"
    verified = lc.open_backup(data, provider, workspace_id=WORKSPACE_ALPHA)
    assert verified.manifest == manifest
    assert {item.payload for item in verified.objects} >= {patient_payload(0), patient_payload(1)}


def test_backup_key_is_separate_from_every_store_key(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    provider = InMemoryTestKeyProvider(root_secret)
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        path = store.store_path
        first = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        second = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T3)
    connection = sqlite3.connect(path)
    try:
        salt = bytes(connection.execute("SELECT salt FROM key_versions").fetchone()[0])
    finally:
        connection.close()
    store_key = provider.key_for_version(workspace_id=WORKSPACE_ALPHA, key_version=1, salt=salt)
    backup_keys = []
    for data in (first, second):
        manifest = lc.read_backup_manifest(data)
        key = provider.backup_key(
            workspace_id=WORKSPACE_ALPHA,
            backup_id=manifest.backup_id,
            salt=bytes.fromhex(manifest.key_salt_hex),
        )
        backup_keys.append(key)
        for secret in (root_secret, store_key, key):
            assert secret not in data
            assert secret.hex().encode("ascii") not in data
    assert backup_keys[0] != backup_keys[1]
    assert store_key not in backup_keys
    assert (
        lc.read_backup_manifest(first).key_salt_hex != lc.read_backup_manifest(second).key_salt_hex
    )


# --- quarantine restore, promotion, and no silent overwrite ---------------------------


def test_restore_lands_in_quarantine_that_normal_mode_refuses(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
    report = lc.restore_backup_to_quarantine(
        data,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(roots.quarantine),
        application_version=APPLICATION_VERSION,
    )
    assert report.object_count == 6
    assert report.audit_events_verified == 3
    assert report.type_counts == (("AuditEvent", 3), ("Patient", 3))
    with pytest.raises(StoreRoleError):
        open_live(roots.quarantine, provider)
    with open_quarantine(roots.quarantine, provider) as quarantine:
        assert quarantine.restored_backup_id == report.backup_id
        with pytest.raises(StoreRoleError):
            quarantine.put_objects_atomic(
                (ObjectWrite(binding=patient_binding(PATIENT_IDS[3]), payload=b"x"),)
            )
        restored = non_audit(content_of(quarantine))
    assert set(restored.values()) == {patient_payload(0), patient_payload(1), patient_payload(2)}


def test_promotion_into_an_empty_store_recovers_the_workspace(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        store.delete_object(patient_binding(PATIENT_IDS[1]))
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        original = content_of(store)
    lc.restore_backup_to_quarantine(
        data,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(roots.quarantine),
        application_version=APPLICATION_VERSION,
    )
    with (
        open_live(roots.recovery, provider) as recovered,
        open_quarantine(roots.quarantine, provider) as quarantine,
    ):
        report = lc.promote_quarantine(recovered, quarantine, actor_id=ACTOR, occurred_at=T3)
        recovered_content = content_of(recovered)
        tombstones = recovered.tombstones()
        events = audit_events(recovered)
    assert report.restored_objects == 5
    assert report.recorded_tombstones == 1
    assert non_audit(recovered_content) == non_audit(original)
    assert [(item.object_id, item.reason) for item in tombstones] == [
        (PATIENT_IDS[1], TombstoneReason.USER_DELETION)
    ]
    assert events[-1][0] == AuditEventType.RESTORE.value
    assert events[-1][1]["mode"] == "promote"
    assert events[-1][1]["restored_objects"] == "5"


def test_promotion_never_overwrites_newer_live_state(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store, 2)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        newer = patient_binding(PATIENT_IDS[3])
        store.put_objects_atomic((ObjectWrite(binding=newer, payload=b"newer synthetic state"),))
        before = content_of(store)
        lc.restore_backup_to_quarantine(
            data,
            provider,
            workspace_id=WORKSPACE_ALPHA,
            quarantine_root=str(roots.quarantine),
            application_version=APPLICATION_VERSION,
        )
        with (
            open_quarantine(roots.quarantine, provider) as quarantine,
            pytest.raises(RestoreConflictError, match="newer or divergent"),
        ):
            lc.promote_quarantine(store, quarantine, actor_id=ACTOR, occurred_at=T3)
        assert content_of(store) == before


def test_promotion_skips_revisions_the_live_store_deleted(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store, 2)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
    lc.restore_backup_to_quarantine(
        data,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(roots.quarantine),
        application_version=APPLICATION_VERSION,
    )
    # A live store that lost recent writes (only its first object) but recorded a
    # deletion of the second revision must not get that revision back.
    with open_live(roots.recovery, provider) as recovered:
        with open_quarantine(roots.quarantine, provider) as quarantine:
            source = quarantine.export_snapshot()
        first_event = next(
            item
            for item in source.objects
            if item.binding.object_type is WorkspaceObjectType.AUDIT_EVENT
            and b'"sequence":1' in item.payload
        )
        first_patient = next(
            item for item in source.objects if item.binding.object_id == PATIENT_IDS[0]
        )
        second_patient = next(
            item for item in source.objects if item.binding.object_id == PATIENT_IDS[1]
        )
        recovered.put_objects_atomic(
            (
                ObjectWrite(binding=first_patient.binding, payload=first_patient.payload),
                ObjectWrite(binding=first_event.binding, payload=first_event.payload),
                ObjectWrite(binding=second_patient.binding, payload=second_patient.payload),
            )
        )
        recovered.delete_object(second_patient.binding)
        with open_quarantine(roots.quarantine, provider) as quarantine:
            report = lc.promote_quarantine(recovered, quarantine, actor_id=ACTOR, occurred_at=T3)
        ids = {key[1] for key in non_audit(content_of(recovered))}
    assert report.skipped_deleted == 1
    assert str(PATIENT_IDS[1]) not in ids
    assert str(PATIENT_IDS[0]) in ids


# --- rollback exercise and deletion across backups ------------------------------------


def test_rollback_discards_newer_state_and_keeps_user_deletions(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        trail = AuditTrail(store)
        trail.record_object_deletion(
            binding=patient_binding(PATIENT_IDS[0]), actor_id=ACTOR, occurred_at=T2
        )
        newer = patient_binding(PATIENT_IDS[3])
        store.put_objects_atomic((ObjectWrite(binding=newer, payload=b"post-snapshot state"),))
        events_before = len(AuditTrail(store).events())
        lc.restore_backup_to_quarantine(
            data,
            provider,
            workspace_id=WORKSPACE_ALPHA,
            quarantine_root=str(roots.quarantine),
            application_version=APPLICATION_VERSION,
        )
        with open_quarantine(roots.quarantine, provider) as quarantine:
            report = lc.rollback_to_quarantine(store, quarantine, actor_id=ACTOR, occurred_at=T3)
        remaining = {key[1] for key in non_audit(content_of(store))}
        reasons = {item.object_id: item.reason for item in store.tombstones()}
        events = audit_events(store)
    assert report.discarded_objects == 1
    assert report.kept_deleted == 1
    assert remaining == {str(PATIENT_IDS[1]), str(PATIENT_IDS[2])}
    assert reasons == {
        PATIENT_IDS[0]: TombstoneReason.USER_DELETION,
        PATIENT_IDS[3]: TombstoneReason.ROLLBACK_DISCARDED,
    }
    assert len(events) == events_before + 1
    assert events[-1][0] == AuditEventType.RESTORE.value
    assert events[-1][1]["mode"] == "rollback"


def test_every_deletion_path_records_a_tombstone(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        store.delete_object(patient_binding(PATIENT_IDS[0]))
        AuditTrail(store).record_object_deletion(
            binding=patient_binding(PATIENT_IDS[1]), actor_id=ACTOR, occurred_at=T2
        )
        assert {item.object_id for item in store.tombstones()} == {
            PATIENT_IDS[0],
            PATIENT_IDS[1],
        }
        store.put_objects_atomic(
            (ObjectWrite(binding=patient_binding(PATIENT_IDS[0]), payload=patient_payload(0)),)
        )
        assert {item.object_id for item in store.tombstones()} == {PATIENT_IDS[1]}


# --- M1 additive schema migration, preflight and downgrade refusal --------------------


def test_legacy_schema_1_store_is_migrated_forward_by_the_m1_migration(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    make_legacy_schema_1_store(tmp_path, provider)
    with pytest.raises(StoreMigrationRequiredError):
        open_live(tmp_path, provider)
    with open_maintenance(tmp_path, provider) as legacy:
        assert legacy.versions.workspace_schema_version == 1
        with pytest.raises(StoreMigrationRequiredError):
            legacy.put_objects_atomic(
                (ObjectWrite(binding=patient_binding(PATIENT_IDS[3]), payload=b"x"),)
            )
        legacy_content = content_of_legacy(legacy)
    report = lc.migrate_schema_to_current(
        store_root=str(tmp_path),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        source_application_version=APPLICATION_VERSION,
        target_application_version=APPLICATION_VERSION,
        available_bytes=PLENTY_OF_SPACE,
        actor_id=ACTOR,
        occurred_at=T2,
    )
    assert report.state is JournalState.COMPLETED
    with open_live(tmp_path, provider) as store:
        assert store.versions.workspace_schema_version == 3
        assert store.role is StoreRole.LIVE
        log = store.migration_log()
        journal = store.journal_entries()
        migrated_content = content_of(store)
        events = audit_events(store)
    # CW-019 (Issue #523): the migration chains 1 -> 2 -> 3, one M1 step per schema.
    assert log == (
        ("cw-002-store-initialization", "M1", 0, 1, "COMPLETED"),
        (SCHEMA_V2_MIGRATION_ID, "M1", 1, 2, "COMPLETED"),
        (SCHEMA_V3_MIGRATION_ID, "M1", 2, 3, "COMPLETED"),
    )
    assert [(entry.migration_id, entry.state) for entry in journal] == [
        (SCHEMA_V2_MIGRATION_ID, JournalState.COMPLETED),
        (SCHEMA_V3_MIGRATION_ID, JournalState.COMPLETED),
    ]
    manifest = json.loads(journal[0].manifest)["manifest"]
    assert set(manifest) >= SECTION_5_MANIFEST_FIELDS
    assert manifest["workspace_id"] == str(WORKSPACE_ALPHA)
    assert manifest["rollback_strategy"] == "forward_repair"
    assert manifest["external_side_effects"] == []
    assert non_audit(migrated_content) == non_audit(legacy_content)
    assert [meta["migration_id"] for kind, meta in events if kind == "migration"] == [
        SCHEMA_V2_MIGRATION_ID,
        SCHEMA_V3_MIGRATION_ID,
    ]


def content_of_legacy(store: WorkspaceStore) -> dict[tuple[str, str, str], bytes]:
    result: dict[tuple[str, str, str], bytes] = {}
    for object_type in (WorkspaceObjectType.PATIENT, WorkspaceObjectType.AUDIT_EVENT):
        for object_id, revision in store.object_revisions(object_type):
            binding = ObjectBinding(
                workspace_id=WORKSPACE_ALPHA,
                object_id=object_id,
                object_type=object_type,
                object_revision=revision,
            )
            result[(object_type.value, str(object_id), revision)] = store.get_object(binding)
    return result


def test_supported_upgrade_and_downgrade_refusal_semantics(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    assert SUPPORTED_DOWNGRADE_TARGETS == ()
    with open_live(tmp_path, provider) as store:
        path = store.store_path
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "UPDATE store_metadata SET value = '4' WHERE name = 'workspace_schema_version'"
        )
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(StoreVersionError, match="downgrade is refused"):
        open_live(tmp_path, provider)
    with pytest.raises(StoreVersionError, match="downgrade is refused"):
        open_maintenance(tmp_path, provider)


# --- M2 semantic migration: evidence, checkpoint resume, rollback ---------------------


def test_semantic_migration_records_object_by_object_digest_evidence(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        snapshot = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T1)
        snapshot_id = lc.read_backup_manifest(snapshot).backup_id
        report = lc.begin_semantic_migration(
            store,
            semantic_manifest(store, snapshot_id),
            RepresentationV2(),
            provider,
            available_bytes=PLENTY_OF_SPACE,
            snapshot=snapshot,
            actor_id=ACTOR,
            occurred_at=T2,
        )
        patients = store.object_revisions(WorkspaceObjectType.PATIENT)
        tombstones = store.tombstones()
        journal = store.journal_entries()
        log = store.migration_log()
        phases = [meta.get("phase") for kind, meta in audit_events(store) if kind == "migration"]
    assert report.state is JournalState.COMPLETED
    assert report.migrated_objects == 3
    assert {revision for _, revision in patients} == {f"rev-00000001+{MIGRATION_ID}"}
    assert {item.reason for item in tombstones} == {TombstoneReason.MIGRATION_SUPERSEDED}
    for old_id, old_revision, old_digest, new_revision, new_digest in report.evidence:
        assert old_revision == "rev-00000001"
        assert new_revision == f"rev-00000001+{MIGRATION_ID}"
        assert old_digest != new_digest
        assert UUID(old_id) in PATIENT_IDS
    assert journal[-1].state is JournalState.COMPLETED
    assert (MIGRATION_ID, "M2", 3, 3, "COMPLETED") in log
    assert phases == ["PREPARED", "COMPLETED"]


def test_interrupted_semantic_migration_resumes_deterministically(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        snapshot = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T1)
        snapshot_id = lc.read_backup_manifest(snapshot).backup_id
        with pytest.raises(RuntimeError, match="simulated power loss"):
            lc.begin_semantic_migration(
                store,
                semantic_manifest(store, snapshot_id),
                RepresentationV2(fail_after=1),
                provider,
                available_bytes=PLENTY_OF_SPACE,
                snapshot=snapshot,
                actor_id=ACTOR,
                occurred_at=T2,
            )
    with pytest.raises(StoreMigrationRequiredError):
        open_live(tmp_path, provider)
    with open_maintenance(tmp_path, provider) as store:
        (entry,) = store.journal_entries()
        assert entry.state is JournalState.MUTATING
        assert entry.checkpoint == 1
        report = lc.resume_semantic_migration(
            store, MIGRATION_ID, RepresentationV2(), actor_id=ACTOR, occurred_at=T3
        )
    assert report.state is JournalState.COMPLETED
    assert report.migrated_objects == 3
    with open_live(tmp_path, provider) as store:
        payloads = sorted(non_audit(content_of(store)).values())
    expected = sorted(
        RepresentationV2().transform(patient_binding(PATIENT_IDS[i]), patient_payload(i))
        for i in range(3)
    )
    assert payloads == expected


def test_failed_validation_is_rolled_back_from_the_protected_snapshot(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        before = non_audit(content_of(store))
        snapshot = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T1)
        snapshot_id = lc.read_backup_manifest(snapshot).backup_id
        with pytest.raises(MigrationValidationError):
            lc.begin_semantic_migration(
                store,
                semantic_manifest(store, snapshot_id),
                RepresentationV2(reject=True),
                provider,
                available_bytes=PLENTY_OF_SPACE,
                snapshot=snapshot,
                actor_id=ACTOR,
                occurred_at=T2,
            )
    with pytest.raises(StoreMigrationRequiredError):
        open_live(roots.live, provider)
    lc.restore_backup_to_quarantine(
        snapshot,
        provider,
        workspace_id=WORKSPACE_ALPHA,
        quarantine_root=str(roots.quarantine),
        application_version=APPLICATION_VERSION,
    )
    with (
        open_maintenance(roots.live, provider) as store,
        open_quarantine(roots.quarantine, provider) as quarantine,
    ):
        assert store.journal_entries()[-1].state is JournalState.FAILED_REQUIRES_INTERVENTION
        report = lc.rollback_to_quarantine(
            store,
            quarantine,
            actor_id=ACTOR,
            occurred_at=T3,
            journal_migration_id=MIGRATION_ID,
        )
    assert report.discarded_objects == 3
    assert report.returned_objects == 3
    with open_live(roots.live, provider) as store:
        assert non_audit(content_of(store)) == before
        assert store.journal_entries()[-1].state is JournalState.ROLLED_BACK
        assert {item.reason for item in store.tombstones()} == {TombstoneReason.ROLLBACK_DISCARDED}
        AuditTrail(store).verify()


# --- key rotation crash tests ---------------------------------------------------------


def test_key_rotation_resumes_after_a_crash_at_every_state_boundary(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store, 4)
        store.begin_key_rotation(2)
        store.rotate_pending(max_objects=2)
    with open_live(tmp_path, provider) as store:
        assert dict(store.key_states()) == {1: KeyState.ROTATING, 2: KeyState.ACTIVE}
        assert patient_payload(0) in set(non_audit(content_of(store)).values())
        report = lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=3, actor_id=ACTOR, occurred_at=T2
        )
        assert report.resumed is True
        assert report.retired_key_versions == (1,)
    with open_live(tmp_path, provider) as store:
        store.begin_key_rotation(3)
        while store.rotate_pending(max_objects=5):
            pass
        store.finalize_key_rotation()
    with open_live(tmp_path, provider) as store:
        assert dict(store.key_states())[2] is KeyState.RETIRING
        report = lc.rotate_workspace_key(
            store, new_key_version=3, batch_size=5, actor_id=ACTOR, occurred_at=T3
        )
        assert report.retired_key_versions == (2,)
        assert dict(store.key_states()) == {
            1: KeyState.RETIRED,
            2: KeyState.RETIRED,
            3: KeyState.ACTIVE,
        }
        assert store.object_key_versions() == (3,)
        with pytest.raises(KeyStateError):
            store.verify_key_availability((1,))
        payloads = non_audit(content_of(store))
        rotation_phases = [
            meta.get("phase") for kind, meta in audit_events(store) if kind == "key_rotation"
        ]
    assert len(payloads) == 4
    assert rotation_phases == ["completed", "completed"]


def test_uninterrupted_key_rotation_is_audited(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        report = lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=1, actor_id=ACTOR, occurred_at=T2
        )
        events = [meta for kind, meta in audit_events(store) if kind == "key_rotation"]
    assert report.resumed is False
    assert report.rotated_objects == 6
    assert [meta["phase"] for meta in events] == ["begin", "completed"]
    assert events[0]["previous_key_version"] == "1"


# --- deletion reconciliation across graph, views, datasets and exports ----------------


def admit_source(store: WorkspaceStore, trail: AuditTrail, locator: str, text: str) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                "synthetic-evidence-v1",
                locator,
                "Synthetic source",
                "rev-00000001",
                "2026-09-01",
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def test_deletion_reconciliation_removes_stale_graph_state_and_rebuilds(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        trail = AuditTrail(store)
        first = admit_source(store, trail, "synthetic-graph/doc-001", "synthetic ward note one")
        second = admit_source(store, trail, "synthetic-graph/doc-002", "synthetic ward note two")
        patient = UUID(
            str(
                pg_mod.admit_node(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "patient-001",
                    pg_mod.NodeKind.PATIENT,
                    "synthetic patient",
                    first,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        encounter = UUID(
            str(
                pg_mod.admit_node(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "encounter-001",
                    pg_mod.NodeKind.ENCOUNTER,
                    "synthetic encounter",
                    second,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        edge = UUID(
            str(
                pg_mod.admit_edge(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    patient,
                    encounter,
                    pg_mod.RelationshipType.HAS_ENCOUNTER,
                    pg_mod.EpistemicState.DERIVED,
                    (second,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        view = UUID(
            str(
                pg_mod.rebuild_graph(
                    store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge,), ACTOR, T1
                ).object_id
            )
        )
        survivor_view = UUID(
            str(
                pg_mod.rebuild_graph(
                    store, trail, WORKSPACE_ALPHA, (patient,), (), ACTOR, T1
                ).object_id
            )
        )
        assert lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T2) == (
            lc.DeletionReconciliationReport((), (), (), (), ())
        )
        trail.record_object_deletion(
            binding=corpus_mod.source_binding(WORKSPACE_ALPHA, second),
            actor_id=ACTOR,
            occurred_at=T2,
        )
        report = lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T3)
        assert report.removed_edges == (edge,)
        assert report.removed_nodes == (encounter,)
        assert report.removed_views == (view,)
        assert store.object_revisions(WorkspaceObjectType.GRAPH_EDGE) == ()
        assert pg_mod.read_view(store, survivor_view).node_ids == (patient,)
        rebuilt = pg_mod.rebuild_graph(store, trail, WORKSPACE_ALPHA, (patient,), (), ACTOR, T3)
        assert UUID(str(rebuilt.object_id)) == survivor_view
        assert lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T3) == (
            lc.DeletionReconciliationReport((), (), (), (), ())
        )
        deletions = [kind for kind, _ in audit_events(store) if kind == "object_delete"]
        AuditTrail(store).verify()
    assert len(deletions) >= 5


def test_deletion_reconciliation_removes_stale_dataset_collections(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        trail = AuditTrail(store)
        view_ids = []
        for artifact in (UUID(int=11), UUID(int=12)):
            descriptor = view_mod.admit_research_descriptor(
                artifact_id=artifact,
                artifact_kind=view_mod.ArtifactKind.DATASET_MANIFEST,
                artifact_revision="rev-00000001",
                evidence_digest="sha256:" + "ab12" * 16,
                interface_name="versioned-artifact-view",
                interface_version="1",
            )
            binding = view_mod.store_research_view(
                store, trail, WORKSPACE_ALPHA, descriptor, ACTOR, T1
            )
            view_ids.append(binding.object_id)
        collection = dataset_mod.admit_dataset_collection(
            "synthetic-collection", tuple(view_ids), "1"
        )
        stored = dataset_mod.store_dataset_collection(
            store, trail, WORKSPACE_ALPHA, collection, ACTOR, T1
        )
        collection_id = UUID(str(stored.object_id))
        view_mod.delete_research_view(store, trail, view_ids[0], ACTOR, T2)
        report = lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T3)
        assert report.removed_collections == (collection_id,)
        assert store.object_revisions(WorkspaceObjectType.WORKSPACE_DATASET_COLLECTION) == ()


# --- policy, audit coverage and runbook -----------------------------------------------


def test_deletion_policy_declares_every_required_scope() -> None:
    scopes = " ".join(entry.scope for entry in lc.DELETION_POLICY)
    for required in (
        "object revisions",
        "audit",
        "graph",
        "views",
        "indexes",
        "embeddings",
        "caches",
        "temporary files",
        "backups",
        "external",
        "cryptographic erasure",
    ):
        assert required in scopes


def test_lifecycle_audit_events_carry_no_payload_content(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        lc.rotate_workspace_key(
            store, new_key_version=2, batch_size=4, actor_id=ACTOR, occurred_at=T2
        )
        lc.restore_backup_to_quarantine(
            data,
            provider,
            workspace_id=WORKSPACE_ALPHA,
            quarantine_root=str(roots.quarantine),
            application_version=APPLICATION_VERSION,
        )
        with open_quarantine(roots.quarantine, provider) as quarantine:
            lc.rollback_to_quarantine(store, quarantine, actor_id=ACTOR, occurred_at=T3)
        kinds = {event.event_type.value for event in AuditTrail(store).events()}
        raw_events = [event.canonical_bytes() for event in AuditTrail(store).events()]
    assert {"backup", "key_rotation", "restore"} <= kinds
    for raw in raw_events:
        assert PLANTED_MARKER not in raw
        assert b"synthetic-0" not in raw


def test_recovery_runbook_names_existing_entry_points() -> None:
    runbook = (
        REPOSITORY_ROOT / "specs" / "medscale-clinical-workspace-v1" / "recovery_runbook.md"
    ).read_text(encoding="utf-8")
    for name in (
        "create_backup",
        "restore_backup_to_quarantine",
        "promote_quarantine",
        "rollback_to_quarantine",
        "migrate_schema_to_current",
        "begin_semantic_migration",
        "resume_semantic_migration",
        "rotate_workspace_key",
        "reconcile_deletions",
        "open_for_maintenance",
    ):
        assert f"`{name}`" in runbook or f"`{name}(" in runbook or f".{name}(" in runbook
        assert hasattr(lc, name) or hasattr(WorkspaceStore, name)
    assert "root secret" in runbook
    assert "FAILED_REQUIRES_INTERVENTION" in runbook


def test_deletion_reconciliation_removes_stale_export_manifests(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    source_id = UUID("30000000-0000-4000-8000-000000000001")
    with open_live(tmp_path, provider) as store:
        trail = AuditTrail(store)
        binding = ObjectBinding(
            workspace_id=WORKSPACE_ALPHA,
            object_id=source_id,
            object_type=WorkspaceObjectType.LINKED_DOCUMENT,
            object_revision="linked-document-00000001",
        )
        payload = b'{"body":"synthetic export source"}'
        record = describe_revision(
            binding=binding,
            payload=payload,
            producer=ProducerIdentity(
                kind=ProducerKind.HUMAN, identifier=ACTOR, version="cw018-test-v1"
            ),
            source_refs=(
                SourceRef(
                    kind=SourceKind.IMPORT,
                    source_id=str(source_id),
                    source_revision="test-source-00000001",
                    locator="lifecycle-test",
                ).validated(),
            ),
            review_state=ReviewState.IMPORTED,
        )
        store_with_provenance(store, record, payload)
        staged = dataset_mod.stage_export_manifest(
            store,
            trail,
            WORKSPACE_ALPHA,
            (
                dataset_mod.admit_export_source(
                    object_id=source_id,
                    object_kind=WorkspaceObjectType.LINKED_DOCUMENT,
                    object_revision="linked-document-00000001",
                ),
            ),
            target_path="/quarantine/exports/manifest-00000001",
            quarantine_root="/quarantine",
            research_core_roots=("/research-core",),
            consent_scope="synthetic-only",
            source_rights="synthetic-fixture",
            deidentification_method="reference-only",
            deidentification_version="1",
            explicit_export_request=True,
            interface_version="1",
            actor_id=ACTOR,
            occurred_at=T1,
        )
        for doomed in (binding, provenance_binding_for(binding)):
            trail.record_object_deletion(binding=doomed, actor_id=ACTOR, occurred_at=T2)
        report = lc.reconcile_deletions(store, actor_id=ACTOR, occurred_at=T3)
        assert report.removed_exports == (UUID(str(staged.object_id)),)
        assert store.object_revisions(WorkspaceObjectType.WORKSPACE_EXPORT_MANIFEST) == ()


def test_preflight_report_lists_every_section_6_check(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(tmp_path, provider) as store:
        seed_patients(store)
        snapshot = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T1)
        manifest = semantic_manifest(store, lc.read_backup_manifest(snapshot).backup_id)
        report = lc.preflight(
            store, manifest, provider, available_bytes=PLENTY_OF_SPACE, snapshot=snapshot
        )
        forward = lc.preflight(
            store,
            semantic_manifest(store, None, lc.RollbackStrategy.FORWARD_REPAIR),
            provider,
            available_bytes=PLENTY_OF_SPACE,
        )
        assert store.journal_entries() == ()
        stored = store.stored_envelope_bytes()
    assert [name for name, _ in report.checks] == [
        "exclusive_migration_lock",
        "workspace_identity",
        "source_versions",
        "database_and_audit_integrity",
        "key_availability",
        "sufficient_space",
        "no_active_capture",
        "snapshot_integrity",
        "object_inventory",
        "external_side_effects_classified",
        "fail_before_mutation",
    ]
    assert dict(report.checks)["snapshot_integrity"] == "PASS"
    assert dict(forward.checks)["snapshot_integrity"] == "NOT_REQUIRED_BY_ROLLBACK_CLASS"
    assert report.required_bytes == 2 * stored


def test_lifecycle_reports_bind_to_the_audit_chain_head(tmp_path: Path) -> None:
    roots = Roots(tmp_path)
    provider = InMemoryTestKeyProvider(new_root_secret())
    with open_live(roots.live, provider) as store:
        seed_patients(store)
        data = lc.create_backup(store, provider, actor_id=ACTOR, occurred_at=T2)
        report = lc.restore_backup_to_quarantine(
            data,
            provider,
            workspace_id=WORKSPACE_ALPHA,
            quarantine_root=str(roots.quarantine),
            application_version=APPLICATION_VERSION,
        )
        assert report.tombstone_count == 0
        with open_quarantine(roots.quarantine, provider) as quarantine:
            rollback = lc.rollback_to_quarantine(store, quarantine, actor_id=ACTOR, occurred_at=T3)
        assert rollback.journal_migration_id is None
        assert rollback.audit_event_digest == AuditTrail(store).verify().head_event_digest
    with (
        open_live(roots.recovery, provider) as recovered,
        open_quarantine(roots.quarantine, provider) as quarantine,
    ):
        promotion = lc.promote_quarantine(recovered, quarantine, actor_id=ACTOR, occurred_at=T3)
        assert promotion.audit_event_digest == AuditTrail(recovered).verify().head_event_digest
