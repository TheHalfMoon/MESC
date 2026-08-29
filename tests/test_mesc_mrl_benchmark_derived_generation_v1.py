"""MRL-0604 tests for benchmark-derived generation flags."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_benchmark_derived_generation_v1 import (
    BenchmarkDerivedGenerationClassification,
    BenchmarkDerivedGenerationError,
    BenchmarkDerivedGenerationFlags,
    build_benchmark_derived_generation_flags,
)
from medscale.mesc._mrl_contamination_interfaces_v1 import (
    ContaminationEvidenceReport,
    build_contamination_evidence_report,
)
from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    build_training_example_lineage,
)
from medscale.mesc._mrl_training_transformation_binding_v1 import (
    TrainingTransformationBinding,
    build_training_transformation_binding,
)
from test_mesc_mrl_contamination_interfaces_v1 import _checks
from test_mesc_mrl_training_example_lineage_v1 import _example


def _bound_inputs() -> tuple[
    TrainingExampleLineageContract,
    ContaminationEvidenceReport,
    TrainingTransformationBinding,
]:
    lineage = build_training_example_lineage(_example())
    contamination = build_contamination_evidence_report(lineage, _checks())
    transformation = build_training_transformation_binding(
        lineage,
        transformation_kind="normalization",
        transformation_artifact_sha256="7" * 64,
    )
    return lineage, contamination, transformation


def test_not_derived_flags_are_deterministic_and_exactly_bound() -> None:
    lineage, contamination, transformation = _bound_inputs()

    first = build_benchmark_derived_generation_flags(
        lineage,
        contamination,
        transformation,
        assessment_artifact_sha256="8" * 64,
        classification=BenchmarkDerivedGenerationClassification.NOT_BENCHMARK_DERIVED,
    )
    second = build_benchmark_derived_generation_flags(
        lineage,
        contamination,
        transformation,
        assessment_artifact_sha256="8" * 64,
        classification=BenchmarkDerivedGenerationClassification.NOT_BENCHMARK_DERIVED,
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.training_lineage_sha256 == lineage.content_sha256
    assert first.contamination_report_sha256 == contamination.content_sha256
    assert first.transformation_binding_sha256 == transformation.content_sha256
    assert first.benchmark_derived_flag is False


def test_benchmark_derived_classification_requires_benchmark_artifact() -> None:
    with pytest.raises(BenchmarkDerivedGenerationError, match="requires"):
        BenchmarkDerivedGenerationFlags(
            training_lineage_sha256="a" * 64,
            contamination_report_sha256="b" * 64,
            transformation_binding_sha256="c" * 64,
            assessment_artifact_sha256="d" * 64,
            classification=BenchmarkDerivedGenerationClassification.BENCHMARK_DERIVED,
        )


def test_benchmark_derived_flag_binds_exact_benchmark_identity() -> None:
    lineage, contamination, transformation = _bound_inputs()
    flags = build_benchmark_derived_generation_flags(
        lineage,
        contamination,
        transformation,
        assessment_artifact_sha256="8" * 64,
        classification=BenchmarkDerivedGenerationClassification.BENCHMARK_DERIVED,
        benchmark_artifact_sha256="9" * 64,
    )

    assert flags.benchmark_derived_flag is True
    assert flags.benchmark_artifact_sha256 == "9" * 64


def test_not_derived_classification_cannot_claim_benchmark_source() -> None:
    with pytest.raises(BenchmarkDerivedGenerationError, match="cannot claim"):
        BenchmarkDerivedGenerationFlags(
            training_lineage_sha256="a" * 64,
            contamination_report_sha256="b" * 64,
            transformation_binding_sha256="c" * 64,
            assessment_artifact_sha256="d" * 64,
            classification=BenchmarkDerivedGenerationClassification.NOT_BENCHMARK_DERIVED,
            benchmark_artifact_sha256="e" * 64,
        )


def test_contamination_report_from_another_lineage_fails_closed() -> None:
    lineage, _, transformation = _bound_inputs()
    other_lineage = build_training_example_lineage(_example(source_sha256="c" * 64))
    other_contamination = build_contamination_evidence_report(other_lineage, _checks())

    with pytest.raises(
        BenchmarkDerivedGenerationError,
        match="contamination report does not bind",
    ):
        build_benchmark_derived_generation_flags(
            lineage,
            other_contamination,
            transformation,
            assessment_artifact_sha256="8" * 64,
            classification=BenchmarkDerivedGenerationClassification.INDETERMINATE,
        )


def test_transformation_from_another_lineage_fails_closed() -> None:
    lineage, contamination, _ = _bound_inputs()
    other_lineage = build_training_example_lineage(_example(source_sha256="c" * 64))
    other_transformation = build_training_transformation_binding(
        other_lineage,
        transformation_kind="normalization",
        transformation_artifact_sha256="7" * 64,
    )

    with pytest.raises(
        BenchmarkDerivedGenerationError,
        match="transformation binding does not bind",
    ):
        build_benchmark_derived_generation_flags(
            lineage,
            contamination,
            other_transformation,
            assessment_artifact_sha256="8" * 64,
            classification=BenchmarkDerivedGenerationClassification.INDETERMINATE,
        )


def test_mutated_contamination_evidence_fails_closed() -> None:
    lineage, contamination, transformation = _bound_inputs()
    object.__setattr__(contamination.checks[0], "detector_artifact_sha256", "invalid")

    with pytest.raises(ValueError, match="64 lowercase hex"):
        build_benchmark_derived_generation_flags(
            lineage,
            contamination,
            transformation,
            assessment_artifact_sha256="8" * 64,
            classification=BenchmarkDerivedGenerationClassification.INDETERMINATE,
        )


def test_flags_cannot_generate_access_or_authorize_training() -> None:
    lineage, contamination, transformation = _bound_inputs()
    flags = build_benchmark_derived_generation_flags(
        lineage,
        contamination,
        transformation,
        assessment_artifact_sha256="8" * 64,
        classification=BenchmarkDerivedGenerationClassification.INDETERMINATE,
    )

    assert flags.benchmark_derived_flag is None
    assert flags.can_generate_examples is False
    assert flags.can_access_benchmark is False
    assert flags.can_authorize_training is False
    assert flags.can_authorize_model_promotion is False
    assert b"PROMOTED" not in flags.semantic_bytes
