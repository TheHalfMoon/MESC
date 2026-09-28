"""CW-016 acceptance tests: read-only research workspace views."""

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
    AuditEventType,
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import research_view as view_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    ResearchViewInputError,
    ResearchViewRevisionError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    ReviewState,
    read_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ARTIFACT_ONE = UUID("2b3c4d5e-6f7a-8b9c-0d1e-2f3a4b5c6d7e")
ACTOR = "synthetic-operator"
T1 = "2026-09-28T10:00:00+03:00"
T2 = "2026-09-28T10:01:00+03:00"
EVIDENCE_DIGEST = "sha256:" + "ab12" * 16


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit_descriptor(**overrides: object) -> view_mod.ResearchArtifactDescriptor:
    arguments: dict[str, object] = {
        "artifact_id": ARTIFACT_ONE,
        "artifact_kind": view_mod.ArtifactKind.EVIDENCE_RECORD,
        "artifact_revision": "rev-00000001",
        "evidence_digest": EVIDENCE_DIGEST,
        "interface_name": "versioned-artifact-view",
        "interface_version": "1",
    }
    arguments.update(overrides)
    return view_mod.admit_research_descriptor(**arguments)


def test_descriptor_admission_is_versioned(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        descriptor = admit_descriptor()
        assert descriptor.artifact_kind is view_mod.ArtifactKind.EVIDENCE_RECORD
        binding = view_mod.store_research_view(store, trail, WORKSPACE_ALPHA, descriptor, ACTOR, T1)
        record = view_mod.read_research_view(store, binding.object_id)
        assert record.interface_version == "1"
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(artifact_kind="live-model-endpoint")
        with pytest.raises(ResearchViewRevisionError):
            admit_descriptor(interface_version="2")


def test_view_identity_is_deterministic(tmp_path: Path) -> None:
    first = view_mod.view_id_for(
        WORKSPACE_ALPHA,
        ARTIFACT_ONE,
        view_mod.ArtifactKind.BENCHMARK_RESULT,
        "rev-00000002",
        EVIDENCE_DIGEST,
        "versioned-artifact-view",
        "1",
    )
    second = view_mod.view_id_for(
        WORKSPACE_ALPHA,
        ARTIFACT_ONE,
        "benchmark-result",
        "rev-00000002",
        EVIDENCE_DIGEST,
        "versioned-artifact-view",
        "1",
    )
    assert first == second
    other = view_mod.view_id_for(
        WORKSPACE_ALPHA,
        ARTIFACT_ONE,
        view_mod.ArtifactKind.BENCHMARK_RESULT,
        "rev-00000003",
        EVIDENCE_DIGEST,
        "versioned-artifact-view",
        "1",
    )
    assert other != first


def test_view_displays_artifact_revision_evidence(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        assert record.artifact_id == ARTIFACT_ONE
        assert record.artifact_revision == "rev-00000001"
        assert record.evidence_digest == EVIDENCE_DIGEST
        document = record.to_document()
        assert document["artifact_id"] == str(ARTIFACT_ONE)
        assert document["artifact_revision"] == "rev-00000001"
        assert document["evidence_digest"] == EVIDENCE_DIGEST
        stored_provenance = read_provenance(store, binding)
        assert stored_provenance.review_state is ReviewState.IMPORTED
        stored_provenance.verify_payload(view_mod.view_payload_bytes(record))


def test_no_patient_context_can_be_supplied(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(TypeError):
            admit_descriptor(patient_id="patient-001")
        with pytest.raises(TypeError):
            admit_descriptor(session_id="session-001")
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        payload = json.dumps(record.to_document(), sort_keys=True)
        assert "patient" not in payload.lower()
        assert "session" not in payload.lower()
        assert ACTOR not in payload


def test_research_core_is_read_only_by_default(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        assert not hasattr(view_mod, "update_research_view")
        assert not hasattr(view_mod, "mutate_research_artifact")
        assert not hasattr(view_mod, "attach_patient_context")
        from medscale_workspace import nobackflow as guard_mod
        from medscale_workspace.binding import ObjectBinding
        from medscale_workspace.data_class import (
            DataClass,
            TrustDomain,
            classify,
        )
        from medscale_workspace.errors import ResearchBackflowError
        from medscale_workspace.identity import WorkspaceObjectType

        record = view_mod.read_research_view(store, binding.object_id)
        classified = guard_mod.classify_object(
            binding=ObjectBinding(
                workspace_id=WORKSPACE_ALPHA,
                object_id=binding.object_id,
                object_type=WorkspaceObjectType.WORKSPACE_RESEARCH_VIEW,
                object_revision=view_mod.VIEW_REVISION,
            ),
            classification=classify(DataClass.PUBLIC),
            payload=view_mod.view_payload_bytes(record),
        )
        evaluation = guard_mod.evaluate_object_flow(classified, TrustDomain.RESEARCH_CORE)
        assert evaluation.admitted is False
        with pytest.raises(ResearchBackflowError):
            guard_mod.guard_object_handoff(classified, TrustDomain.RESEARCH_CORE)


def test_no_mutation_or_export_events(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        events_before = list(trail.events())
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        fresh_events = list(trail.events())[len(events_before) :]
        kinds = [event.event_type for event in fresh_events]
        assert AuditEventType.OBJECT_CREATE in kinds
        assert AuditEventType.EXPORT not in kinds
        count_before = len(list(trail.events()))
        view_mod.read_research_view(store, binding.object_id)
        assert len(list(trail.events())) == count_before


def test_view_data_class_is_public_workspace_state(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        assert record.to_document()["data_class"] == view_mod.research_view_data_class_value()
        assert view_mod.research_view_data_class_value() == "PUBLIC"
