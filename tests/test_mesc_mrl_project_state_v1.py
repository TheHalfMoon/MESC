"""MRL-0703 tests for the non-authoritative project-state projection."""

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
            evidence_refs=("merge:d598b1df",),
        ),
        ProjectStateEntry(
            state_id="MRL-0702",
            lifecycle_state="CLOSED_CANONICAL",
            canonical_source_paths=(_TASKS_PATH,),
            dependency_ids=("MRL-0701",),
            evidence_refs=("merge:d683f205",),
        ),
    )


def _projection() -> ProjectStateProjection:
    return ProjectStateProjection(
        research_program_index=_research_projection(),
        capability_matrix=_capability_projection(),
        sources=(_source(),),
        entries=_entries(),
    )


def test_projection_is_deterministic_and_permanently_non_authoritative() -> None:
    first = _projection()
    second = _projection()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.semantic_bytes.endswith(b"\n")
    assert first.to_dict()["schema_version"] == "MRL-PROJECT-STATE-V1"
    assert first.to_dict()["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
    assert first.to_dict()["can_authorize"] is False
    assert first.can_authorize is False
    assert b"generated_at" not in first.semantic_bytes
    assert b"timestamp" not in first.semantic_bytes


def test_projection_binds_shared_repository_and_component_identities() -> None:
    projection = _projection()
    payload = projection.to_dict()
    components = cast(dict[str, object], payload["components"])

    assert payload["repository"] == {
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
    }
    assert components["research_program_index_sha256"] == canonical_sha256(
        _research_projection().to_dict()
    )
    assert components["capability_matrix_sha256"] == canonical_sha256(
        _capability_projection().to_dict()
    )


def test_component_repository_mismatch_fails_closed() -> None:
    capability = replace(
        _capability_projection(),
        repository=CapabilityRepositoryBinding(commit_sha="0" * 40, tree_sha="b" * 40),
    )
    with pytest.raises(ProjectStateProjectionError, match="different repository commits"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=capability,
            sources=(_source(),),
            entries=_entries(),
        )


def test_source_set_identity_changes_with_project_state_source_identity() -> None:
    original = _projection()
    changed = replace(
        original,
        sources=(replace(_source(), sha256="3" * 64),),
    )

    assert changed.source_set_sha256 != original.source_set_sha256
    assert changed.semantic_bytes != original.semantic_bytes


def test_closed_canonical_state_requires_evidence_reference() -> None:
    with pytest.raises(ProjectStateProjectionError, match="requires exact evidence_refs"):
        replace(_entries()[0], evidence_refs=())


def test_unknown_lifecycle_or_invalid_state_identity_fails_closed() -> None:
    with pytest.raises(ProjectStateProjectionError, match="lifecycle_state"):
        replace(_entries()[0], lifecycle_state="PROMOTED")
    with pytest.raises(ProjectStateProjectionError, match="state_id"):
        replace(_entries()[0], state_id="mrl-0701")


def test_dependencies_must_exist_and_cannot_be_self_referential() -> None:
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


def test_entry_sources_must_be_covered_by_component_or_project_sources() -> None:
    uncovered = replace(
        _entries()[0],
        canonical_source_paths=("docs/missing-state-source.md",),
    )
    with pytest.raises(ProjectStateProjectionError, match="omit referenced canonical source"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=(_source(),),
            entries=(uncovered, _entries()[1]),
        )


def test_unsorted_duplicate_and_mutable_collections_fail_closed() -> None:
    first, second = _entries()
    with pytest.raises(ProjectStateProjectionError, match="entries must be sorted"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=(_source(),),
            entries=(second, first),
        )

    with pytest.raises(ProjectStateProjectionError, match="sources must be an exact tuple"):
        ProjectStateProjection(
            research_program_index=_research_projection(),
            capability_matrix=_capability_projection(),
            sources=cast(tuple[ProjectStateSourceBinding, ...], [_source()]),
            entries=_entries(),
        )

    with pytest.raises(ProjectStateProjectionError, match="canonical_source_paths"):
        ProjectStateEntry(
            state_id="MRL-0703",
            lifecycle_state="PLANNED",
            canonical_source_paths=cast(tuple[str, ...], [_TASKS_PATH]),
        )


def test_project_state_projection_cannot_encode_authority() -> None:
    payload = _projection().to_dict()

    assert payload["can_authorize"] is False
    assert "authority_state" not in payload
    assert b"PROMOTED" not in _projection().semantic_bytes
