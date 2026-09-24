"""CW-009 focused acceptance tests for deterministic offline retrieval."""

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditEventType,
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import retrieval as retrieval_mod  # noqa: E402 runtime import
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

TEXT_ONE = "synthetic guideline: hydration monitoring for ward patients"
TEXT_TWO = "synthetic note: hydration protocol compliance audit"
TEXT_THREE = "synthetic memo: ward staffing rotation schedule"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit(store: WorkspaceStore, trail: AuditTrail, locator: str, text: str, date: str) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                CORPUS_KEY,
                locator,
                "Synthetic source",
                "rev-00000001",
                date,
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def stocked_store(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, UUID, UUID]:
    first = admit(store, trail, "synthetic-corpus/doc-001", TEXT_ONE, "2026-01-05")
    second = admit(store, trail, "synthetic-corpus/doc-002", TEXT_TWO, "2026-02-11")
    third = admit(store, trail, "synthetic-corpus/doc-003", TEXT_THREE, "2026-03-20")
    return first, second, third


def frozen_snapshot(store: WorkspaceStore, trail: AuditTrail, members: tuple[UUID, ...]) -> UUID:
    return UUID(
        str(
            retrieval_mod.admit_snapshot(
                store, trail, WORKSPACE_ALPHA, CORPUS_KEY, members, ACTOR, T1
            ).object_id
        )
    )


def test_snapshot_freezes_member_identities(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        members = stocked_store(store, trail)
        snapshot_id = frozen_snapshot(store, trail, members)
        manifest = retrieval_mod.read_snapshot(store, snapshot_id)
        assert [entry.source_id for entry in manifest.entries] == list(members)
        assert manifest.index_identity == retrieval_mod.INDEX_IDENTITY
        assert manifest.ranking_identity == retrieval_mod.RANKING_IDENTITY
        assert manifest.schema_version == retrieval_mod.SCHEMA_VERSION
        expected = retrieval_mod.snapshot_id_for(
            WORKSPACE_ALPHA, manifest.corpus_id, manifest.entries
        )
        assert snapshot_id == expected


def test_query_identity_is_deterministic(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        members = stocked_store(store, trail)
        snapshot_id = frozen_snapshot(store, trail, members)
        first = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        stored = retrieval_mod.read_result(store, first.object_id)
        query = retrieval_mod.read_query(store, stored.query_id)
        assert query.normalized_query == "hydration monitoring"
        second_id = retrieval_mod.query_id_for(
            WORKSPACE_ALPHA, snapshot_id, "hydration monitoring", 10, retrieval_mod.MatchMode.ANY
        )
        assert query.query_id == second_id


def test_same_snapshot_and_query_replay_identically(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        members = stocked_store(store, trail)
        snapshot_id = frozen_snapshot(store, trail, members)
        binding = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        result = retrieval_mod.read_result(store, binding.object_id)
        assert [hit.rank for hit in result.results] == [1, 2]
        assert result.results[0].score == 2
        assert result.results[1].score == 1
        assert result.results[0].source_date == "2026-01-05"
        replayed = retrieval_mod.replay_query(store, result.query_id)
        assert replayed.to_document() == result.to_document()


def test_different_parameters_change_query_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        members = stocked_store(store, trail)
        snapshot_id = frozen_snapshot(store, trail, members)
        wide = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        narrow = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            1,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        assert wide.object_id != narrow.object_id
        narrow_result = retrieval_mod.read_result(store, narrow.object_id)
        assert len(narrow_result.results) == 1
        strict = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ALL,
            ACTOR,
            T2,
        )
        strict_result = retrieval_mod.read_result(store, strict.object_id)
        assert [hit.source_id for hit in strict_result.results] == [
            hit.source_id for hit in retrieval_mod.read_result(store, wide.object_id).results[:1]
        ]


def test_deterministic_tie_breaking(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = admit(store, trail, "synthetic-corpus/tie-a", "shared token alpha", "2026-01-05")
        second = admit(store, trail, "synthetic-corpus/tie-b", "shared token beta", "2026-01-06")
        snapshot_id = frozen_snapshot(store, trail, (first, second))
        binding = retrieval_mod.execute_query(
            store, trail, snapshot_id, "shared token", 10, retrieval_mod.MatchMode.ANY, ACTOR, T2
        )
        result = retrieval_mod.read_result(store, binding.object_id)
        assert len(result.results) == 2
        assert result.results[0].score == result.results[1].score == 2
        assert str(result.results[0].source_id) < str(result.results[1].source_id)


def test_query_audit_records_evidence_query(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        members = stocked_store(store, trail)
        snapshot_id = frozen_snapshot(store, trail, members)
        retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        kinds = [event.event_type for event in trail.events()]
        assert AuditEventType.EVIDENCE_QUERY in kinds
