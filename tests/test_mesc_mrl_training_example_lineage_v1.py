"""MRL-0601 tests for the training-example lineage contract."""

from __future__ import annotations

from dataclasses import fields

import pytest

from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    TrainingExampleLineageError,
    build_training_example_lineage,
)
from medscale.mesc._training_example_contract_v1 import TrainingExampleV1, TrainingMessage


def _example(*, source_sha256: str = "a" * 64) -> TrainingExampleV1:
    return TrainingExampleV1(
        example_id="example-1",
        training_record_id="record-1",
        source_id="source-1",
        source_revision="revision-1",
        source_license="fixture-license",
        source_sha256=source_sha256,
        source_timestamp="2026-01-01T00:00:00Z",
        origin="synthetic",
        synthetic_provenance_sha256="b" * 64,
        evidence_refs=("evidence-1",),
        task_type="fixture-task",
        specialty="fixture-domain",
        patient_population="fixture-population",
        language="en",
        training_stage="evidence_sft",
        prompt=(TrainingMessage(role="user", content="Fixture input"),),
        completion=TrainingMessage(role="assistant", content="Fixture output"),
        uncertainty_class="SUPPORTED",
        abstention_target="ANSWER_SUPPORTED",
        contradiction_state="NONE",
        verification_state="VERIFIED",
        clinician_review_state="REVIEWED_PASS",
        contamination_state="CLEAR",
    )


def test_lineage_is_deterministic_and_binds_exact_training_example() -> None:
    example = _example()
    first = build_training_example_lineage(example)
    second = build_training_example_lineage(example)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.training_example_sha256 == example.example_sha256
    assert first.semantic_dict()["training_example_sha256"] == example.example_sha256
    assert first.semantic_dict()["source_sha256"] == example.source_sha256
    assert first.semantic_dict()["evidence_refs"] == ["evidence-1"]


def test_lineage_identity_changes_when_source_identity_changes() -> None:
    first = build_training_example_lineage(_example(source_sha256="a" * 64))
    second = build_training_example_lineage(_example(source_sha256="c" * 64))

    assert first.training_example_sha256 != second.training_example_sha256
    assert first.content_sha256 != second.content_sha256


def test_existing_lineage_rejects_valid_post_construction_example_identity_drift() -> None:
    lineage = build_training_example_lineage(_example())
    original_content_sha256 = lineage.content_sha256
    object.__setattr__(lineage.example, "source_sha256", "c" * 64)

    with pytest.raises(TrainingExampleLineageError, match="identity changed after construction"):
        lineage.semantic_dict()
    with pytest.raises(TrainingExampleLineageError, match="identity changed after construction"):
        _ = lineage.training_example_sha256
    with pytest.raises(TrainingExampleLineageError, match="identity changed after construction"):
        _ = lineage.content_sha256
    assert original_content_sha256


def test_lineage_construction_identity_is_not_reachable_as_mutable_state() -> None:
    lineage = build_training_example_lineage(_example())

    assert tuple(field.name for field in fields(TrainingExampleLineageContract)) == ("example",)
    with pytest.raises(AttributeError):
        object.__setattr__(lineage, "_bound_content_sha256", "a" * 64)


def test_lineage_is_metadata_only_and_non_authoritative() -> None:
    lineage = build_training_example_lineage(_example())

    assert lineage.can_access_source is False
    assert lineage.can_authorize_training is False
    assert lineage.can_authorize_model_promotion is False
    assert lineage.semantic_dict()["can_access_source"] is False
    assert lineage.semantic_dict()["can_authorize_training"] is False
    assert lineage.semantic_dict()["can_authorize_model_promotion"] is False
    assert b"PROMOTED" not in lineage.semantic_bytes


def test_mutated_training_example_fails_closed() -> None:
    example = _example()
    object.__setattr__(example, "source_sha256", "not-a-sha")

    with pytest.raises(TrainingExampleLineageError, match="canonical revalidation"):
        build_training_example_lineage(example)


def test_non_training_example_input_fails_closed() -> None:
    with pytest.raises(TrainingExampleLineageError, match="exact TrainingExampleV1"):
        build_training_example_lineage(object())  # type: ignore[arg-type]
