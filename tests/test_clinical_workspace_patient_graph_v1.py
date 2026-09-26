"""CW-011 acceptance tests: derived longitudinal graph with provenance."""

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
from medscale_workspace import evidence_strength as es_mod  # noqa: E402 runtime import
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
WORKSPACE_BETA = UUID("7dd9e9f4-1c3b-40b4-b10f-5b16db71b00f")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"


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
    date: str = "2026-09-01",
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
                date,
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def admit_node(
    store: WorkspaceStore,
    trail: AuditTrail,
    key: str,
    kind: pg_mod.NodeKind,
    label: str,
    source_id: UUID,
) -> UUID:
    return UUID(
        str(
            pg_mod.admit_node(
                store,
                trail,
                WORKSPACE_ALPHA,
                key,
                kind,
                label,
                source_id,
                ACTOR,
                T1,
            ).object_id
        )
    )


def admit_edge(
    store: WorkspaceStore,
    trail: AuditTrail,
    source_node: UUID,
    target_node: UUID,
    relationship: pg_mod.RelationshipType,
    epistemic: pg_mod.EpistemicState,
    sources: tuple[UUID, ...],
) -> UUID:
    return UUID(
        str(
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                source_node,
                target_node,
                relationship,
                epistemic,
                sources,
                ACTOR,
                T1,
            ).object_id
        )
    )


def stocked_two_nodes(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, UUID, UUID, UUID]:
    first = admit_source(store, trail, "synthetic-graph/doc-001", "synthetic ward note one")
    second = admit_source(store, trail, "synthetic-graph/doc-002", "synthetic ward note two")
    patient = admit_node(
        store, trail, "patient-001", pg_mod.NodeKind.PATIENT, "synthetic patient alpha", first
    )
    encounter = admit_node(
        store, trail, "encounter-001", pg_mod.NodeKind.ENCOUNTER, "synthetic encounter one", second
    )
    return first, second, patient, encounter


def test_node_identity_deterministic_and_provenance_bound(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-graph/n-001", "synthetic note alpha")
        node_id = admit_node(
            store,
            trail,
            "patient-001",
            pg_mod.NodeKind.PATIENT,
            "synthetic patient alpha",
            source_id,
        )
        node = pg_mod.read_node(store, node_id)
        assert node.node_key == "patient-001"
        assert node.node_kind is pg_mod.NodeKind.PATIENT
        assert node.source_id == source_id
        assert node.node_id == pg_mod.node_id_for(
            WORKSPACE_ALPHA, "patient-001", pg_mod.NodeKind.PATIENT, "rev-00000001"
        )
        with pytest.raises(GraphConflictError):
            admit_node(
                store,
                trail,
                "patient-001",
                pg_mod.NodeKind.PATIENT,
                "synthetic patient alpha",
                source_id,
            )
        other = admit_node(
            store,
            trail,
            "patient-002",
            pg_mod.NodeKind.PATIENT,
            "synthetic patient beta",
            source_id,
        )
        assert other != node_id


def test_edge_requires_epistemic_and_source_refs(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        edge_id = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        edge = pg_mod.read_edge(store, edge_id)
        assert edge.source_node == patient
        assert edge.target_node == encounter
        assert edge.epistemic is pg_mod.EpistemicState.DERIVED
        assert len(edge.sources) == 1
        assert edge.derivation_method == pg_mod.DERIVATION_METHOD
        assert edge.graph_schema_version == pg_mod.GRAPH_SCHEMA_VERSION
        with pytest.raises(GraphInputError):
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                patient,
                encounter,
                pg_mod.RelationshipType.HAS_ENCOUNTER,
                pg_mod.EpistemicState.DERIVED,
                (),
                ACTOR,
                T1,
            )
        with pytest.raises(GraphInputError):
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                patient,
                patient,
                pg_mod.RelationshipType.RELATED_TO,
                pg_mod.EpistemicState.ASSERTED,
                (second,),
                ACTOR,
                T1,
            )


def test_epistemic_states_stay_distinct(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        derived = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        assert pg_mod.read_edge(store, derived).epistemic is not pg_mod.EpistemicState.SUPPORTED
        unknown = pg_mod.admit_edge(
            store,
            trail,
            WORKSPACE_ALPHA,
            patient,
            encounter,
            pg_mod.RelationshipType.RELATED_TO,
            pg_mod.EpistemicState.UNKNOWN,
            (second,),
            ACTOR,
            T2,
        ).object_id
        assert (
            pg_mod.read_edge(store, UUID(str(unknown))).epistemic is pg_mod.EpistemicState.UNKNOWN
        )


def test_rebuild_empty_identical_reordered(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        empty = pg_mod.rebuild_graph(store, trail, WORKSPACE_ALPHA, (), (), ACTOR, T1)
        assert pg_mod.read_view(store, UUID(str(empty.object_id))).node_ids == ()
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        edge_id = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        first_build = pg_mod.rebuild_graph(
            store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge_id,), ACTOR, T1
        )
        second_build = pg_mod.rebuild_graph(
            store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge_id,), ACTOR, T2
        )
        assert first_build.object_id == second_build.object_id
        reordered = pg_mod.rebuild_graph(
            store, trail, WORKSPACE_ALPHA, (encounter, patient), (edge_id,), ACTOR, T2
        )
        assert reordered.object_id == first_build.object_id
        with pytest.raises(GraphInputError):
            pg_mod.rebuild_graph(
                store, trail, WORKSPACE_ALPHA, (patient, patient), (edge_id,), ACTOR, T1
            )


def test_changed_source_revision_yields_new_identities(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        old_source = admit_source(
            store, trail, "synthetic-graph/rev-doc", "synthetic note version one", "rev-00000001"
        )
        node_old = admit_node(
            store, trail, "patient-001", pg_mod.NodeKind.PATIENT, "synthetic patient", old_source
        )
        new_source = admit_source(
            store, trail, "synthetic-graph/rev-doc", "synthetic note version two", "rev-00000002"
        )
        assert new_source != old_source
        node_new = admit_node(
            store, trail, "patient-001", pg_mod.NodeKind.PATIENT, "synthetic patient", new_source
        )
        assert node_new != node_old


def test_deleted_source_makes_edge_stale(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        edge_id = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        pg_mod.read_edge(store, edge_id)
        trail.record_object_deletion(
            binding=corpus_mod.source_binding(WORKSPACE_ALPHA, second),
            actor_id=ACTOR,
            occurred_at=T2,
        )
        with pytest.raises((GraphInputError, GraphStaleError)):
            pg_mod.read_edge(store, edge_id)
        with pytest.raises((GraphInputError, GraphStaleError)):
            pg_mod.rebuild_graph(
                store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge_id,), ACTOR, T2
            )


def test_path_explain_returns_provenance(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        third_source = admit_source(
            store, trail, "synthetic-graph/doc-003", "synthetic ward note three"
        )
        condition = admit_node(
            store,
            trail,
            "condition-001",
            pg_mod.NodeKind.CONDITION,
            "synthetic condition",
            third_source,
        )
        first_edge = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        second_edge = admit_edge(
            store,
            trail,
            encounter,
            condition,
            pg_mod.RelationshipType.HAS_CONDITION,
            pg_mod.EpistemicState.EXTRACTED,
            (third_source,),
        )
        explanation = pg_mod.explain_path(store, patient, condition)
        assert explanation.source_node == patient
        assert explanation.target_node == condition
        assert len(explanation.steps) == 2
        assert explanation.steps[0].edge_id == first_edge
        assert explanation.steps[1].edge_id == second_edge
        assert explanation.steps[0].epistemic is pg_mod.EpistemicState.DERIVED
        assert explanation.steps[0].provenance_digest.startswith("sha256:")
        assert explanation.steps[0].derivation_method == pg_mod.DERIVATION_METHOD
        view = pg_mod.rebuild_graph(
            store,
            trail,
            WORKSPACE_ALPHA,
            (patient, encounter, condition),
            (first_edge, second_edge),
            ACTOR,
            T1,
        )
        scoped = pg_mod.explain_path(store, patient, condition, view_id=UUID(str(view.object_id)))
        assert len(scoped.steps) == 2
        with pytest.raises(GraphPathError):
            pg_mod.explain_path(store, condition, patient)


def test_cross_workspace_traversal_fails(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, _second, patient, _encounter = stocked_two_nodes(store, trail)
        foreign_node = UUID("11111111-2222-3333-4444-555555555555")
        with pytest.raises((GraphRevisionError, GraphInputError, WorkspaceIsolationError)):
            pg_mod.admit_edge(
                store,
                trail,
                WORKSPACE_ALPHA,
                patient,
                foreign_node,
                pg_mod.RelationshipType.RELATED_TO,
                pg_mod.EpistemicState.ASSERTED,
                (_first,),
                ACTOR,
                T1,
            )
        with pytest.raises(WorkspaceIsolationError):
            pg_mod.admit_node(
                store,
                trail,
                WORKSPACE_BETA,
                "patient-x",
                pg_mod.NodeKind.PATIENT,
                "synthetic patient x",
                _first,
                ACTOR,
                T1,
            )
        with pytest.raises((GraphPathError, WorkspaceIsolationError)):
            pg_mod.explain_path(store, patient, foreign_node)


def test_deletion_removes_node_and_incident_edges(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        edge_id = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        removed = pg_mod.delete_node(store, trail, encounter, ACTOR, T2)
        assert removed >= 2
        with pytest.raises(GraphInputError):
            pg_mod.read_node(store, encounter)
        with pytest.raises(GraphInputError):
            pg_mod.read_edge(store, edge_id)
        with pytest.raises((GraphInputError, GraphStaleError)):
            pg_mod.rebuild_graph(
                store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge_id,), ACTOR, T2
            )


def test_timeline_is_deterministic_projection(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _first, second, patient, encounter = stocked_two_nodes(store, trail)
        edge_id = admit_edge(
            store,
            trail,
            patient,
            encounter,
            pg_mod.RelationshipType.HAS_ENCOUNTER,
            pg_mod.EpistemicState.DERIVED,
            (second,),
        )
        view = pg_mod.rebuild_graph(
            store, trail, WORKSPACE_ALPHA, (patient, encounter), (edge_id,), ACTOR, T1
        )
        nodes_a, edges_a = pg_mod.timeline_for_view(store, UUID(str(view.object_id)))
        nodes_b, edges_b = pg_mod.timeline_for_view(store, UUID(str(view.object_id)))
        assert nodes_a == nodes_b
        assert edges_a == edges_b
        assert set(nodes_a) == {patient, encounter}


def test_edge_claim_reference_when_applicable(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = admit_source(store, trail, "synthetic-graph/claim-doc", "synthetic claim evidence")
        patient = admit_node(
            store, trail, "patient-001", pg_mod.NodeKind.PATIENT, "synthetic patient", first
        )
        encounter = admit_node(
            store, trail, "encounter-001", pg_mod.NodeKind.ENCOUNTER, "synthetic encounter", first
        )
        set_id = UUID(
            str(
                es_mod.admit_claim_set(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "answer: synthetic ward protocol",
                    ("synthetic claim one",),
                    (("cite-one",),),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        claim_set = es_mod.read_claim_set(store, set_id)
        claim_id = claim_set.claims[0].claim_id
        edge_id = UUID(
            str(
                pg_mod.admit_edge(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    patient,
                    encounter,
                    pg_mod.RelationshipType.EVIDENCE_FOR,
                    pg_mod.EpistemicState.SUPPORTED,
                    (first,),
                    ACTOR,
                    T1,
                    claim_set_id=set_id,
                    claim_id=claim_id,
                ).object_id
            )
        )
        assert pg_mod.read_edge(store, edge_id).claim_id == claim_id
