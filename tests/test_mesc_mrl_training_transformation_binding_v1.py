"""MRL-0603 tests for source/prompt/teacher transformation bindings."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_training_example_lineage_v1 import build_training_example_lineage
from medscale.mesc._mrl_training_transformation_binding_v1 import (
    TrainingTransformationBinding,
    TrainingTransformationBindingError,
    build_training_transformation_binding,
)
from test_mesc_mrl_training_example_lineage_v1 import _example


def test_binding_is_deterministic_and_uses_exact_lineage_source() -> None:
    lineage = build_training_example_lineage(_example())

    first = build_training_transformation_binding(
        lineage,
        transformation_kind="synthetic-generation",
        transformation_artifact_sha256="1" * 64,
        prompt_template_sha256="2" * 64,
        teacher_model_sha256="3" * 64,
        teacher_output_sha256="4" * 64,
    )
    second = build_training_transformation_binding(
        lineage,
        transformation_kind="synthetic-generation",
        transformation_artifact_sha256="1" * 64,
        prompt_template_sha256="2" * 64,
        teacher_model_sha256="3" * 64,
        teacher_output_sha256="4" * 64,
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.training_lineage_sha256 == lineage.content_sha256
    assert first.source_sha256 == lineage.example.source_sha256


def test_binding_cannot_invoke_sources_teachers_or_authorize_training() -> None:
    lineage = build_training_example_lineage(_example())
    binding = build_training_transformation_binding(
        lineage,
        transformation_kind="normalization",
        transformation_artifact_sha256="1" * 64,
    )

    assert binding.can_access_source is False
    assert binding.can_invoke_teacher is False
    assert binding.can_authorize_training is False
    assert binding.can_authorize_model_promotion is False
    assert b"PROMOTED" not in binding.semantic_bytes


def test_teacher_model_and_output_must_be_bound_together() -> None:
    with pytest.raises(TrainingTransformationBindingError, match="supplied together"):
        TrainingTransformationBinding(
            training_lineage_sha256="a" * 64,
            source_sha256="b" * 64,
            transformation_kind="teacher-generation",
            transformation_artifact_sha256="c" * 64,
            prompt_template_sha256=None,
            teacher_model_sha256="d" * 64,
            teacher_output_sha256=None,
        )


def test_transformation_identity_changes_with_prompt_or_teacher_evidence() -> None:
    lineage = build_training_example_lineage(_example())
    first = build_training_transformation_binding(
        lineage,
        transformation_kind="synthetic-generation",
        transformation_artifact_sha256="1" * 64,
        prompt_template_sha256="2" * 64,
    )
    second = build_training_transformation_binding(
        lineage,
        transformation_kind="synthetic-generation",
        transformation_artifact_sha256="1" * 64,
        prompt_template_sha256="5" * 64,
    )

    assert first.content_sha256 != second.content_sha256


def test_mutated_lineage_fails_closed() -> None:
    lineage = build_training_example_lineage(_example())
    object.__setattr__(lineage.example, "source_sha256", "invalid")

    with pytest.raises(TrainingTransformationBindingError, match="canonical revalidation"):
        build_training_transformation_binding(
            lineage,
            transformation_kind="normalization",
            transformation_artifact_sha256="1" * 64,
        )
