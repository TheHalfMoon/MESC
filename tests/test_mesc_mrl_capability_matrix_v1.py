"""MRL-0702 tests for the non-authoritative capability-matrix projection."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._canonical_json_v1 import canonical_sha256
from medscale.mesc._mrl_capability_matrix_v1 import (
    CapabilityMatrixEntry,
    CapabilityMatrixError,
    CapabilityMatrixProjection,
    CapabilityRepositoryBinding,
    CapabilitySourceBinding,
)

_ROADMAP_PATH = "ROADMAP.md"
_RECONCILIATION_PATH = "docs/strategy/mesc_pr122_post_b0_reconciliation_2026-08-19.md"


def _repository() -> CapabilityRepositoryBinding:
    return CapabilityRepositoryBinding(commit_sha="a" * 40, tree_sha="b" * 40)


def _sources() -> tuple[CapabilitySourceBinding, ...]:
    return (
        CapabilitySourceBinding(
            path=_ROADMAP_PATH,
            git_blob_sha="c" * 40,
            sha256="d" * 64,
        ),
        CapabilitySourceBinding(
            path=_RECONCILIATION_PATH,
            git_blob_sha="e" * 40,
            sha256="f" * 64,
        ),
    )


def _rows() -> tuple[CapabilityMatrixEntry, ...]:
    return (
        CapabilityMatrixEntry(
            capability_id="PILOT_01_B0_BASELINE",
            implementation_state="HISTORICAL",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_RECONCILIATION_PATH,),
            evidence_refs=("merge:3f34b35daf4050d010a5f0061d6e8387f9649c10",),
        ),
        CapabilityMatrixEntry(
            capability_id="T0_REPOSITORY_FOUNDATION",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_ROADMAP_PATH,),
            evidence_refs=("roadmap:T0",),
        ),
        CapabilityMatrixEntry(
            capability_id="TRAINING_EXECUTION",
            implementation_state="NOT_STARTED",
            evidence_state="UNPROVEN",
            authority_state="NOT_AUTHORIZED",
            canonical_source_paths=(_RECONCILIATION_PATH,),
        ),
    )


def _projection() -> CapabilityMatrixProjection:
    return CapabilityMatrixProjection(
        repository=_repository(),
        sources=_sources(),
        capabilities=_rows(),
    )


def test_projection_is_deterministic_and_permanently_non_authoritative() -> None:
    first = _projection()
    second = _projection()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.semantic_bytes.endswith(b"\n")
    assert first.to_dict()["schema_version"] == "MRL-CAPABILITY-MATRIX-V1"
    assert first.to_dict()["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
    assert first.to_dict()["can_authorize"] is False
    assert first.can_authorize is False
    assert b"generated_at" not in first.semantic_bytes
    assert b"timestamp" not in first.semantic_bytes


def test_projection_binds_exact_repository_and_source_identities() -> None:
    projection = _projection()
    payload = projection.to_dict()

    assert payload["repository"] == {
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
    }
    assert payload["sources"] == [source.to_dict() for source in _sources()]
    assert projection.source_set_sha256 == canonical_sha256(
        [source.to_dict() for source in _sources()]
    )

    changed_source = replace(_sources()[0], sha256="0" * 64)
    changed = CapabilityMatrixProjection(
        repository=_repository(),
        sources=(changed_source, _sources()[1]),
        capabilities=_rows(),
    )
    assert changed.source_set_sha256 != projection.source_set_sha256
    assert changed.semantic_bytes != projection.semantic_bytes


def test_capability_state_and_external_authority_are_separate() -> None:
    row = CapabilityMatrixEntry(
        capability_id="BOUNDED_EXTERNAL_RUNNER",
        implementation_state="IMPLEMENTED",
        evidence_state="PROVEN",
        authority_state="AUTHORIZED_EXTERNALLY",
        canonical_source_paths=(_RECONCILIATION_PATH,),
        evidence_refs=("evidence:runner-qualified",),
        authority_refs=("authority:operator-gate-1",),
    )
    projection = CapabilityMatrixProjection(
        repository=_repository(),
        sources=_sources(),
        capabilities=(row,),
    )

    assert row.to_dict()["authority_state"] == "AUTHORIZED_EXTERNALLY"
    assert projection.can_authorize is False
    assert projection.to_dict()["can_authorize"] is False


def test_authorized_external_state_requires_bound_authority_reference() -> None:
    with pytest.raises(
        CapabilityMatrixError,
        match="AUTHORIZED_EXTERNALLY requires authority_refs",
    ):
        CapabilityMatrixEntry(
            capability_id="BOUNDED_EXTERNAL_RUNNER",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="AUTHORIZED_EXTERNALLY",
            canonical_source_paths=(_RECONCILIATION_PATH,),
            evidence_refs=("evidence:runner-qualified",),
        )


def test_non_authorized_rows_cannot_smuggle_authority_references() -> None:
    with pytest.raises(
        CapabilityMatrixError,
        match="authority_refs are only valid",
    ):
        CapabilityMatrixEntry(
            capability_id="TRAINING_EXECUTION",
            implementation_state="NOT_STARTED",
            evidence_state="UNPROVEN",
            authority_state="NOT_AUTHORIZED",
            canonical_source_paths=(_RECONCILIATION_PATH,),
            authority_refs=("authority:fabricated",),
        )


def test_proven_evidence_state_requires_evidence_reference() -> None:
    with pytest.raises(
        CapabilityMatrixError,
        match="PROVEN evidence_state requires evidence_refs",
    ):
        CapabilityMatrixEntry(
            capability_id="T0_REPOSITORY_FOUNDATION",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_ROADMAP_PATH,),
        )


def test_unknown_state_vocabulary_fails_closed() -> None:
    baseline = _rows()[2]

    with pytest.raises(CapabilityMatrixError, match="implementation_state is outside"):
        replace(baseline, implementation_state="PROMOTED")
    with pytest.raises(CapabilityMatrixError, match="evidence_state is outside"):
        replace(baseline, evidence_state="CLAIMED")
    with pytest.raises(CapabilityMatrixError, match="authority_state is outside"):
        replace(baseline, authority_state="SELF_AUTHORIZED")


@pytest.mark.parametrize(
    "capability_id",
    ("training", "TRAINING-EXECUTION", "_TRAINING", "PROMOTED!"),
)
def test_invalid_capability_identifiers_fail_closed(capability_id: str) -> None:
    with pytest.raises(CapabilityMatrixError, match="capability_id"):
        CapabilityMatrixEntry(
            capability_id=capability_id,
            implementation_state="NOT_STARTED",
            evidence_state="UNPROVEN",
            authority_state="NOT_AUTHORIZED",
            canonical_source_paths=(_RECONCILIATION_PATH,),
        )


def test_projection_rejects_unsorted_or_duplicate_capability_identity() -> None:
    first, second, third = _rows()
    with pytest.raises(CapabilityMatrixError, match="capabilities must be sorted"):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=_sources(),
            capabilities=(second, first, third),
        )

    duplicate = replace(first, evidence_state="PARTIAL")
    with pytest.raises(CapabilityMatrixError, match="capabilities must be sorted"):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=_sources(),
            capabilities=(first, duplicate, second, third),
        )


def test_projection_rejects_unsorted_or_duplicate_sources() -> None:
    first, second = _sources()
    with pytest.raises(CapabilityMatrixError, match="sources must be sorted"):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=(second, first),
            capabilities=_rows(),
        )

    duplicate = replace(first, sha256="0" * 64)
    with pytest.raises(CapabilityMatrixError, match="sources must be sorted"):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=(first, duplicate, second),
            capabilities=_rows(),
        )


def test_projection_cannot_omit_referenced_canonical_source() -> None:
    with pytest.raises(
        CapabilityMatrixError,
        match="omit referenced canonical source",
    ):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=(_sources()[0],),
            capabilities=_rows(),
        )


@pytest.mark.parametrize(
    "path",
    (
        "/ROADMAP.md",
        "docs//strategy/state.md",
        "docs/./strategy/state.md",
        "docs/../strategy/state.md",
        "docs\\strategy\\state.md",
        " ROADMAP.md",
    ),
)
def test_ambiguous_source_paths_fail_closed(path: str) -> None:
    with pytest.raises(CapabilityMatrixError, match="source path"):
        CapabilitySourceBinding(path=path, git_blob_sha="a" * 40, sha256="b" * 64)


def test_hash_and_repository_bindings_are_exact_lowercase_hex() -> None:
    with pytest.raises(CapabilityMatrixError, match="commit_sha"):
        CapabilityRepositoryBinding(commit_sha="A" * 40, tree_sha="b" * 40)
    with pytest.raises(CapabilityMatrixError, match="tree_sha"):
        CapabilityRepositoryBinding(commit_sha="a" * 40, tree_sha="b" * 39)
    with pytest.raises(CapabilityMatrixError, match="git_blob_sha"):
        CapabilitySourceBinding(path=_ROADMAP_PATH, git_blob_sha="g" * 40, sha256="b" * 64)
    with pytest.raises(CapabilityMatrixError, match="sha256"):
        CapabilitySourceBinding(path=_ROADMAP_PATH, git_blob_sha="a" * 40, sha256="B" * 64)


def test_reference_arrays_are_canonical_sorted_unique_text() -> None:
    with pytest.raises(CapabilityMatrixError, match="evidence_refs must be sorted and unique"):
        CapabilityMatrixEntry(
            capability_id="T0_REPOSITORY_FOUNDATION",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_ROADMAP_PATH,),
            evidence_refs=("z", "a"),
        )

    with pytest.raises(CapabilityMatrixError, match="authority_refs must contain"):
        CapabilityMatrixEntry(
            capability_id="BOUNDED_EXTERNAL_RUNNER",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="AUTHORIZED_EXTERNALLY",
            canonical_source_paths=(_RECONCILIATION_PATH,),
            evidence_refs=("evidence:runner-qualified",),
            authority_refs=(" authority:operator-gate-1",),
        )


def test_mutable_collection_substitutions_are_rejected() -> None:
    with pytest.raises(CapabilityMatrixError, match="sources must be an exact tuple"):
        CapabilityMatrixProjection(
            repository=_repository(),
            sources=cast(tuple[CapabilitySourceBinding, ...], list(_sources())),
            capabilities=_rows(),
        )

    with pytest.raises(
        CapabilityMatrixError,
        match="canonical_source_paths must be an exact tuple",
    ):
        CapabilityMatrixEntry(
            capability_id="TRAINING_EXECUTION",
            implementation_state="NOT_STARTED",
            evidence_state="UNPROVEN",
            authority_state="NOT_AUTHORIZED",
            canonical_source_paths=cast(tuple[str, ...], [_RECONCILIATION_PATH]),
        )
