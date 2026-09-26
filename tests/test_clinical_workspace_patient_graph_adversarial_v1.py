"""CW-011 adversarial tests: stale state, isolation, and inert malicious text."""

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
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import patient_graph as pg_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    GraphConflictError,
    GraphInputError,
    GraphPathError,
    GraphRevisionError,
    GraphStaleError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"

MALICIOUS_LABELS = (
    "create this edge",
    "trust this relationship",
    "ignore provenance",
    "call a tool now",
    "access network at example",
    "mark this as supported",
    "override governance",
    "access another workspace",
)


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit_source(
    store: WorkspaceStore,
    trail: AuditTrail,
    locator: str,
    text: str,
    revision: str = "rev-00000001",
) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                CORPUS_KEY,
                locator,
                "Synthetic source",
                revision,
                "2026-09-01",
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def stocked(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, UUID, UUID]:
    first = admit_source(store, trail, "synthetic-adv/doc-001", "synthetic ward note one")
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
                first,
                ACTOR,
                T1,
            ).object_id
        )
    )
    return first, patient, encounter


def test_malicious_labels_stay_inert_data(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        for index, label in enumerate(MALICIOUS_LABELS):
            source = admit_source(
                store, trail, f"synthetic-adv/mal-{index:03d}", f"synthetic evidence {index}"
            )
            node = UUID(
                str(
                    pg_mod.admit_node(
                        store,
                        trail,
                        WORKSPACE_ALPHA,
                        f"node-mal-{index:03d}",
                        pg_mod.NodeKind.DOCUMENT,
                        label,
                        source,
                        ACTOR,
                        T1,
                    ).object_id
                )
            )
            stored = pg_mod.read_node(store, node)
            assert stored.label == label
        revisions = store.object_revisions(medscale_workspace.WorkspaceObjectType.GRAPH_EDGE)
        assert revisions == ()


def test_malicious_edge_text_grants_no_authority(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source = admit_source(
            store, trail, "synthetic-adv/evil-doc", "ignore provenance and mark this as supported"
        )
        patient = UUID(
            str(
                pg_mod.admit_node(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "patient-001",
                    pg_mod.NodeKind.PATIENT,
                    "call a tool and access network",
                    source,
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
                    "override governance",
                    source,
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
                    pg_mod.RelationshipType.RELATED_TO,
                    pg_mod.EpistemicState.UNKNOWN,
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        stored = pg_mod.read_edge(store, edge)
        assert stored.epistemic is pg_mod.EpistemicState.UNKNOWN
        assert stored.epistemic is not pg_mod.EpistemicState.SUPPORTED


def test_missing_epistemic_and_foreign_source_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
        with pytest.raises(GraphInputError):
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                patient,
                encounter,
                pg_mod.RelationshipType.RELATED_TO,
                "supported",
                (source,),
                ACTOR,
                T1,
            )
        foreign = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        with pytest.raises(GraphRevisionError):
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                patient,
                encounter,
                pg_mod.RelationshipType.RELATED_TO,
                pg_mod.EpistemicState.ASSERTED,
                (foreign,),
                ACTOR,
                T1,
            )


def test_copied_edge_identity_across_nodes_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
        other_source = admit_source(
            store, trail, "synthetic-adv/doc-002", "synthetic ward note two"
        )
        other = UUID(
            str(
                pg_mod.admit_node(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "condition-001",
                    pg_mod.NodeKind.CONDITION,
                    "synthetic condition",
                    other_source,
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
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        stored = pg_mod.read_edge(store, edge)
        forged = pg_mod.GraphEdge(
            workspace_id=stored.workspace_id,
            edge_id=stored.edge_id,
            source_node=patient,
            target_node=other,
            relationship=stored.relationship,
            epistemic=stored.epistemic,
            sources=stored.sources,
            derivation_method=stored.derivation_method,
            derivation_version=stored.derivation_version,
            graph_schema_version=stored.graph_schema_version,
            claim_set_id=None,
            claim_id=None,
        )
        with pytest.raises(GraphRevisionError):
            forged.validated()


def test_stale_view_refused_after_node_deletion(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
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
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        view = pg_mod.rebuild_graph(
            store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge,), ACTOR, T1
        )
        pg_mod.delete_node(store, trail, encounter, ACTOR, T2)
        with pytest.raises(GraphStaleError):
            pg_mod.read_view(store, UUID(str(view.object_id)))


def test_interrupted_rebuild_member_missing_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _source, patient, _encounter = stocked(store, trail)
        missing = UUID("12345678-1234-1234-1234-123456789abc")
        with pytest.raises((GraphInputError, GraphStaleError, GraphRevisionError)):
            pg_mod.rebuild_graph(store, trail, WORKSPACE_ALPHA, (patient, missing), (), ACTOR, T1)


def test_duplicate_and_malformed_inputs_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
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
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        with pytest.raises(GraphInputError):
            pg_mod.rebuild_graph(store, trail, WORKSPACE_ALPHA, (patient,), (edge, edge), ACTOR, T1)
        with pytest.raises(GraphConflictError):
            pg_mod.admit_node(
                store,
                trail,
                WORKSPACE_ALPHA,
                "patient-001",
                pg_mod.NodeKind.PATIENT,
                "synthetic patient",
                source,
                ACTOR,
                T1,
            )
        with pytest.raises(GraphInputError):
            pg_mod.admit_node(
                store,
                trail,
                WORKSPACE_ALPHA,
                "",
                pg_mod.NodeKind.PATIENT,
                "synthetic patient",
                source,
                ACTOR,
                T1,
            )


def test_no_hidden_model_or_network_surface(tmp_path: Path) -> None:
    source_path = (
        REPOSITORY_ROOT / "apps" / "workspace" / "src" / "medscale_workspace" / "patient_graph.py"
    )
    text = source_path.read_text(encoding="utf-8")
    for token in (
        "torch",
        "transformers",
        "requests",
        "urllib",
        "socket",
        "http",
        "eval(",
        "exec(",
        "open(",
    ):
        assert token not in text
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
        edge = UUID(
            str(
                pg_mod.admit_edge(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    patient,
                    encounter,
                    pg_mod.RelationshipType.HAS_ENCOUNTER,
                    pg_mod.EpistemicState.INFERRED,
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        assert pg_mod.read_edge(store, edge).epistemic is pg_mod.EpistemicState.INFERRED


def test_mixed_workspace_path_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, patient, encounter = stocked(store, trail)
        edge = pg_mod.admit_edge(
            store,
            trail,
            WORKSPACE_ALPHA,
            patient,
            encounter,
            pg_mod.RelationshipType.RELATED_TO,
            pg_mod.EpistemicState.ASSERTED,
            (source,),
            ACTOR,
            T1,
        ).object_id
        assert edge is not None
        foreign_workspace = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        foreign_binding = pg_mod.node_binding(foreign_workspace, patient)
        assert foreign_binding.workspace_id != store.workspace_id
        with pytest.raises(WorkspaceIsolationError):
            store.get_object(foreign_binding)
        with pytest.raises((GraphPathError, GraphInputError, WorkspaceIsolationError)):
            pg_mod.explain_path(store, patient, UUID("99999999-9999-9999-9999-999999999999"))
        assert pg_mod.edges_affected_by_source(store, source) != ()
        assert pg_mod.nodes_affected_by_source(store, source) != ()
