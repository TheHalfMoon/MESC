"""CW-017 acceptance tests: dataset collections and export staging."""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

import json
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
from medscale_workspace import dataset as dataset_mod  # noqa: E402 runtime import
from medscale_workspace import research_view as view_mod  # noqa: E402 runtime import
from medscale_workspace.binding import ObjectBinding  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    DatasetCollectionInputError,
    DatasetCollectionRevisionError,
    ExplicitExportRequestError,
    ExportStagingInputError,
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
    store_with_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ARTIFACT_ONE = UUID("2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e")
ARTIFACT_TWO = UUID("3c4d5e6f-7a8b-9c0d-1e2f-3a4b5c6d7e8f")
SOURCE_ONE = UUID("4d5e6f7a-8b9c-0d1e-2f3a-4b5c6d7e8f90")
ACTOR = "synthetic-operator"
T1 = "2026-09-28T10:00:00+03:00"
T2 = "2026-09-28T10:01:00+03:00"
EVIDENCE_DIGEST = "sha256:" + "ab12" * 16
PLANTED_IDENTIFIER = "PLANTED-IDENTIFIER-9Z84"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit_manifest_view(artifact_id: UUID) -> view_mod.ResearchArtifactDescriptor:
    return view_mod.admit_research_descriptor(
        artifact_id=artifact_id,
        artifact_kind=view_mod.ArtifactKind.DATASET_MANIFEST,
        artifact_revision="rev-00000001",
        evidence_digest=EVIDENCE_DIGEST,
        interface_name="versioned-artifact-view",
        interface_version="1",
    )


def store_manifest_view(
    store: WorkspaceStore, trail: AuditTrail, artifact_id: UUID
) -> ObjectBinding:
    return view_mod.store_research_view(
        store, trail, WORKSPACE_ALPHA, admit_manifest_view(artifact_id), ACTOR, T1
    )


def seed_source(
    store: WorkspaceStore,
    object_id: UUID,
    object_kind: WorkspaceObjectType,
    object_revision: str,
    text: str,
) -> ObjectBinding:
    binding = ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=object_id,
        object_type=object_kind,
        object_revision=object_revision,
    )
    payload = json.dumps(
        {"body": text}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=ProducerIdentity(
            kind=ProducerKind.HUMAN, identifier=ACTOR, version="cw017-test-v1"
        ),
        source_refs=(
            SourceRef(
                kind=SourceKind.IMPORT,
                source_id=str(SOURCE_ONE),
                source_revision="test-source-00000001",
                locator="dataset-test",
            ).validated(),
        ),
        review_state=ReviewState.IMPORTED,
    )
    store_with_provenance(store, record, payload)
    return binding


def admit_collection(
    name: str = "fixture-collection", view_ids: tuple[UUID, ...] = ()
) -> dataset_mod.DatasetCollectionDescriptor:
    return dataset_mod.admit_dataset_collection(
        collection_name=name,
        view_ids=view_ids,
        interface_version="1",
    )


def stage_manifest(
    store: WorkspaceStore,
    trail: AuditTrail,
    items: tuple[dataset_mod.ExportSourceDescriptor, ...],
    **overrides: object,
) -> ObjectBinding:
    arguments: dict[str, object] = {
        "target_path": "/quarantine/exports/manifest-00000001",
        "quarantine_root": "/quarantine",
        "research_core_roots": ("/research-core",),
        "consent_scope": "synthetic-only",
        "source_rights": "synthetic-fixture",
        "deidentification_method": "reference-only",
        "deidentification_version": "1",
        "explicit_export_request": True,
        "interface_version": "1",
        "actor_id": ACTOR,
        "occurred_at": T1,
    }
    arguments.update(overrides)
    return dataset_mod.stage_export_manifest(store, trail, WORKSPACE_ALPHA, items, **arguments)


def test_collection_admission_is_versioned(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = store_manifest_view(store, trail, ARTIFACT_ONE).object_id
        second = store_manifest_view(store, trail, ARTIFACT_TWO).object_id
        binding = dataset_mod.store_dataset_collection(
            store, trail, WORKSPACE_ALPHA, admit_collection(view_ids=(first, second)), ACTOR, T1
        )
        record = dataset_mod.read_dataset_collection(store, binding.object_id)
        assert record.interface_version == "1"
        assert set(record.view_ids) == {first, second}
        with pytest.raises(DatasetCollectionInputError):
            admit_collection(name="")
        with pytest.raises(DatasetCollectionRevisionError):
            dataset_mod.admit_dataset_collection(
                collection_name="fixture-collection", view_ids=(first,), interface_version="2"
            )


def test_collection_identity_is_deterministic(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = store_manifest_view(store, trail, ARTIFACT_ONE).object_id
        second = store_manifest_view(store, trail, ARTIFACT_TWO).object_id
        one = dataset_mod.collection_id_for(
            WORKSPACE_ALPHA, "fixture-collection", (first, second), "1"
        )
        same = dataset_mod.collection_id_for(
            WORKSPACE_ALPHA, "fixture-collection", (second, first), "1"
        )
        assert one == same
        other = dataset_mod.collection_id_for(
            WORKSPACE_ALPHA, "other-collection", (first, second), "1"
        )
        assert other != one


def test_research_mode_lists_pinned_manifests(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = store_manifest_view(store, trail, ARTIFACT_ONE).object_id
        second = store_manifest_view(store, trail, ARTIFACT_TWO).object_id
        binding = dataset_mod.store_dataset_collection(
            store, trail, WORKSPACE_ALPHA, admit_collection(view_ids=(first,)), ACTOR, T1
        )
        views = dataset_mod.list_collection_views(store, binding.object_id)
        assert len(views) == 1
        assert views[0].artifact_id == ARTIFACT_ONE
        assert views[0].artifact_kind is view_mod.ArtifactKind.DATASET_MANIFEST
        assert views[0].view_id != second
        assert not hasattr(dataset_mod, "update_dataset_collection")
        assert not hasattr(dataset_mod, "refresh_dataset_collection")
        assert not hasattr(dataset_mod, "attach_patient_context")


def test_export_staging_lands_in_domain_x(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source = seed_source(
            store,
            SOURCE_ONE,
            WorkspaceObjectType.LINKED_DOCUMENT,
            "linked-document-00000001",
            "synthetic dataset source",
        )
        item = dataset_mod.admit_export_source(
            object_id=source.object_id,
            object_kind=WorkspaceObjectType.LINKED_DOCUMENT,
            object_revision="linked-document-00000001",
        )
        binding = stage_manifest(store, trail, (item,))
        record = dataset_mod.read_export_manifest(store, binding.object_id)
        assert record.quarantine_target == "/quarantine/exports/manifest-00000001"
        assert record.to_document()["data_class"] == "EXPORT_QUARANTINE"
        assert record.consent_scope == "synthetic-only"
        assert record.source_rights == "synthetic-fixture"


def test_deidentification_is_reference_only(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source = seed_source(
            store,
            SOURCE_ONE,
            WorkspaceObjectType.LINKED_DOCUMENT,
            "linked-document-00000001",
            "synthetic note carrying " + PLANTED_IDENTIFIER + " for residual scan",
        )
        item = dataset_mod.admit_export_source(
            object_id=source.object_id,
            object_kind=WorkspaceObjectType.LINKED_DOCUMENT,
            object_revision="linked-document-00000001",
        )
        binding = stage_manifest(store, trail, (item,))
        record = dataset_mod.read_export_manifest(store, binding.object_id)
        assert record.deidentification_method == "reference-only"
        assert record.deidentification_version == "1"
        assert PLANTED_IDENTIFIER.encode("ascii") not in record.canonical_bytes()
        assert record.payload_digests[0].startswith("sha256:")


def test_consent_rights_manifest_recorded(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source = seed_source(
            store,
            SOURCE_ONE,
            WorkspaceObjectType.LINKED_TABLE,
            "linked-table-00000001",
            "synthetic table source",
        )
        item = dataset_mod.admit_export_source(
            object_id=source.object_id,
            object_kind="LinkedTable",
            object_revision="linked-table-00000001",
        )
        binding = stage_manifest(store, trail, (item,))
        document = dataset_mod.read_export_manifest(store, binding.object_id).to_document()
        assert document["consent_scope"] == "synthetic-only"
        assert document["source_rights"] == "synthetic-fixture"
        with pytest.raises(ExportStagingInputError):
            stage_manifest(store, trail, (item,), consent_scope="broad-consent")
        with pytest.raises(ExportStagingInputError):
            stage_manifest(store, trail, (item,), source_rights="unrestricted")


def test_explicit_request_required(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source = seed_source(
            store,
            SOURCE_ONE,
            WorkspaceObjectType.LINKED_DOCUMENT,
            "linked-document-00000001",
            "synthetic dataset source",
        )
        item = dataset_mod.admit_export_source(
            object_id=source.object_id,
            object_kind=WorkspaceObjectType.LINKED_DOCUMENT,
            object_revision="linked-document-00000001",
        )
        with pytest.raises(ExplicitExportRequestError):
            stage_manifest(store, trail, (item,), explicit_export_request=False)
        with pytest.raises(ExplicitExportRequestError):
            stage_manifest(store, trail, (item,), explicit_export_request="yes")
