"""MRL-0703 tests for the frozen non-authoritative project-state schema."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._canonical_json_v1 import canonical_sha256
from medscale.mesc._mrl_capability_matrix_v1 import CapabilityRepositoryBinding
from medscale.mesc._mrl_project_state_v1 import (
    ProjectStateEntry,
    ProjectStateProjection,
    ProjectStateProjectionError,
    ProjectStateSourceBinding,
)
from test_mesc_mrl_capability_matrix_v1 import _projection as _capability_projection
from test_mesc_mrl_research_program_index_v1 import _projection as _research_projection

_TASKS_PATH = "specs/mesc-research-loop-v1/tasks.md"


def _source() -> ProjectStateSourceBinding:
    return ProjectStateSourceBinding(
        path=_TASKS_PATH,
        git_blob_sha="1" * 40,
        sha256="2" * 64,
    )


def _entries() -> tuple[ProjectStateEntry, ...]:
    return (
        ProjectStateEntry(
            state_id="MRL-0701",
            lifecycle_state="CLOSED_CANONICAL",
            canonical_source_paths=(_TASKS_PATH,),
            evidence_refs=(
                "canonical-merge:" + "3" * 40,
                "qualified-head:" + "4" * 40,
            ),
        ),
        ProjectStateEntry(
            state_id="MRL-0702",
            lifecycle_state="ELIGIBLE",
            canonical_source_paths=(_TASKS_PATH,),
            dependency_ids=("MRL-0701",),
        ),
    )


def _projection() -> ProjectStateProjection:
    return ProjectStateProjection(
        research_program_index=_research_projection(),
        capability_matrix=_capability_projection(),
        sources=(_source(),),
        entries=_entries(),
    )


def test_projection_matches_frozen_schema_shape_and_is_non_authoritative() -> None:
    projection = _projection()
    payload = projection.to_dict()

    assert set(payload) == {
        "can_authorize",
        "projection_kind",
        "repository",
        "schema_version",
        "source_set_sha256",
        "sources",
        "tasks",
    }
    assert payload["schema_version"] == "MRL-PROJECT-STATE-V1"
    assert payload["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
    assert payload["can_authorize"] is False
    assert payload["repository"] == {
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
    }
    assert "entries" not in payload
    assert "components" not in payload
    tasks = cast(list[dict[str, object]], payload["tasks"])
    assert tasks[0] == {
        "dependencies": [],
        "evidence_refs": [
            "canonical-merge:" + "3" * 40,
            "qualified-head:" + "4" * 40,
        ],
        "state": "CLOSED_CANONICAL",
        "task_id": "MRL-0701",
    }
    assert projection.semantic_bytes.endswith(b"\n")
    assert projection.can_authorize is False
    assert b"generated_at" not in projection.semantic_bytes
    assert b"PROMOTED" not in projection.semantic_bytes


def test_source_set_sha256_is_canonical_sources_array_only() -> None:
    projection = _projection()
    assert projection.source_set_sha256 == canonical_sha256([_source().to_dict()])
    changed = replace(
        projection,
        sources=(replace(_source(), sha256="3" * 64),),
    )
    assert changed.source_set_sha256 != projection.source_set_sha256


def test_component_repository_mismatch_fails_closed() -> None:
    capability = replace(
        _capability_projection(),
        repository=CapabilityRepositoryBinding(
            commit_sha="0" * 40,
            tree_sha="b" * 40,
        ),
    )
    with pytest.raises(
        ProjectStateProjectionError,
        match="different repository commits",
    ):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=capability,
            sources=(_source(),),
            entries=_entries(),
        )


def test_closed_state_requires_evidence_and_non_closed_state_rejects_it() -> None:
    with pytest.raises(
        ProjectStateProjectionError,
        match="requires exact evidence_refs",
    ):
        replace(_entries()[0], evidence_refs=())
    with pytest.raises(
        ProjectStateProjectionError,
        match="only CLOSED_CANONICAL",
    ):
        replace(_entries()[1], evidence_refs=("fabricated:evidence",))


def test_task_identity_state_dependencies_and_collections_fail_closed() -> None:
    with pytest.raises(ProjectStateProjectionError, match="lifecycle_state"):
        replace(_entries()[0], lifecycle_state="PROMOTED")
    with pytest.raises(ProjectStateProjectionError, match="state_id"):
        replace(_entries()[0], state_id="mrl-0701")
    with pytest.raises(ProjectStateProjectionError, match="cannot depend on itself"):
        replace(_entries()[0], dependency_ids=("MRL-0701",))

    missing = replace(_entries()[1], dependency_ids=("MRL-0999",))
    with pytest.raises(ProjectStateProjectionError, match="dependency is absent"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=(_source(),),
            entries=(_entries()[0], missing),
        )

    with pytest.raises(ProjectStateProjectionError, match="entries must be sorted"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=(_source(),),
            entries=tuple(reversed(_entries())),
        )

    with pytest.raises(
        ProjectStateProjectionError,
        match="sources must be a non-empty exact tuple",
    ):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=cast(tuple[ProjectStateSourceBinding, ...], [_source()]),
            entries=_entries(),
        )


def test_source_path_rejects_values_beyond_frozen_schema_limit() -> None:
    with pytest.raises(ProjectStateProjectionError, match="frozen schema limit"):
        ProjectStateSourceBinding(
            path="a" * 4097,
            git_blob_sha="1" * 40,
            sha256="2" * 64,
        )
