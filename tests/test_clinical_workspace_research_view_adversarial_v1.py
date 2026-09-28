"""CW-016 adversarial tests: view isolation, forgery, and boundary attacks."""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

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
from medscale_workspace import research_view as view_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    ResearchViewConflictError,
    ResearchViewInputError,
    ResearchViewRevisionError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7dd9e9f4-1c3b-40b4-b10f-5b16db71b00f")
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


def test_unknown_artifact_kind_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(ResearchViewInputError):
            view_mod.store_research_view(
                store,
                trail,
                WORKSPACE_ALPHA,
                admit_descriptor(artifact_kind="live-query"),
                ACTOR,
                T1,
            )
        with pytest.raises(ResearchViewInputError):
            view_mod.store_research_view(
                store, trail, WORKSPACE_ALPHA, admit_descriptor(artifact_kind=""), ACTOR, T1
            )


def test_malformed_revision_and_digest_refused(tmp_path: Path) -> None:
    with open_store(tmp_path):
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(artifact_revision="")
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(artifact_revision="rev with space")
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(evidence_digest="not-a-digest")
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(evidence_digest="sha256:" + "zz12" * 16)
        with pytest.raises(ResearchViewRevisionError):
            admit_descriptor(interface_version="latest")


def test_replay_collides_instead_of_overwriting(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        with pytest.raises(ResearchViewConflictError):
            view_mod.store_research_view(
                store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T2
            )
        record = view_mod.read_research_view(store, first.object_id)
        assert record.artifact_revision == "rev-00000001"


def test_cross_workspace_store_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        with pytest.raises(WorkspaceIsolationError):
            view_mod.store_research_view(
                store, trail, WORKSPACE_BETA, admit_descriptor(), ACTOR, T1
            )
        beta_root = tmp_path / "beta"
        beta_root.mkdir(parents=True, exist_ok=True)
        with (
            open_store(beta_root, WORKSPACE_BETA) as foreign,
            pytest.raises((ResearchViewInputError, WorkspaceIsolationError)),
        ):
            view_mod.read_research_view(foreign, binding.object_id)


def test_forged_view_documents_fail_closed(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        document = record.to_document()
        tampered_revision = dict(document)
        tampered_revision["artifact_revision"] = "rev-99999999"
        with pytest.raises(ResearchViewRevisionError):
            view_mod.ResearchViewRecord.from_document(tampered_revision)
        tampered_class = dict(document)
        tampered_class["data_class"] = "RESEARCH_ARTIFACT"
        with pytest.raises(ResearchViewInputError):
            view_mod.ResearchViewRecord.from_document(tampered_class)
        tampered_patient = dict(document)
        tampered_patient["patient_id"] = "patient-001"
        with pytest.raises(ResearchViewInputError):
            view_mod.ResearchViewRecord.from_document(tampered_patient)


def test_oversized_inputs_refused(tmp_path: Path) -> None:
    with open_store(tmp_path):
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(artifact_revision="r" * 65)
        with pytest.raises(ResearchViewInputError):
            admit_descriptor(interface_name="i" * 65)


def test_malicious_text_grants_no_capability(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        for hostile in (
            "rev-00000001;DROP TABLE views",
            "rev-00000001\nEXPORT",
        ):
            with pytest.raises(ResearchViewInputError):
                admit_descriptor(artifact_revision=hostile)
        inert = "__import__('socket')"
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(artifact_revision=inert), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        assert record.artifact_revision == inert


def test_stale_view_after_deletion(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        binding = view_mod.store_research_view(
            store, trail, WORKSPACE_ALPHA, admit_descriptor(), ACTOR, T1
        )
        record = view_mod.read_research_view(store, binding.object_id)
        assert record.artifact_id == ARTIFACT_ONE
        view_mod.delete_research_view(store, trail, binding.object_id, ACTOR, T2)
        with pytest.raises(ResearchViewInputError):
            view_mod.read_research_view(store, binding.object_id)
