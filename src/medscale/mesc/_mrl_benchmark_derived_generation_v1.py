"""Benchmark-derived generation flags for MESC Research Loop V1.

MRL-0604 binds one exact training lineage, contamination assessment, and transformation
provenance record to an explicit benchmark-derivation classification. It records supplied
provenance evidence only; it does not generate data, inspect benchmarks, execute detectors,
or authorize training or model promotion.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass

from medscale.mesc._mrl_contamination_interfaces_v1 import (
    ContaminationCheckEvidence,
    ContaminationEvidenceReport,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    TrainingExampleLineageError,
    build_training_example_lineage,
)
from medscale.mesc._mrl_training_transformation_binding_v1 import TrainingTransformationBinding

__all__ = [
    "BenchmarkDerivedGenerationClassification",
    "BenchmarkDerivedGenerationError",
    "BenchmarkDerivedGenerationFlags",
    "build_benchmark_derived_generation_flags",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BenchmarkDerivedGenerationError(ValueError):
    """Fail-closed validation error for benchmark-derived generation metadata."""


class BenchmarkDerivedGenerationClassification(enum.Enum):
    """Closed benchmark-derivation classifications for one training example."""

    NOT_BENCHMARK_DERIVED = "NOT_BENCHMARK_DERIVED"
    BENCHMARK_DERIVED = "BENCHMARK_DERIVED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class BenchmarkDerivedGenerationFlags:
    """Immutable benchmark-derivation metadata bound to exact contamination lineage."""

    training_lineage_sha256: str
    contamination_report_sha256: str
    transformation_binding_sha256: str
    assessment_artifact_sha256: str
    classification: BenchmarkDerivedGenerationClassification
    benchmark_artifact_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(self.training_lineage_sha256, "training_lineage_sha256")
        _require_sha256(self.contamination_report_sha256, "contamination_report_sha256")
        _require_sha256(self.transformation_binding_sha256, "transformation_binding_sha256")
        _require_sha256(self.assessment_artifact_sha256, "assessment_artifact_sha256")
        if type(self.classification) is not BenchmarkDerivedGenerationClassification:
            raise BenchmarkDerivedGenerationError(
                "classification must be an exact BenchmarkDerivedGenerationClassification"
            )
        _require_optional_sha256(self.benchmark_artifact_sha256, "benchmark_artifact_sha256")
        if self.classification is BenchmarkDerivedGenerationClassification.BENCHMARK_DERIVED:
            if self.benchmark_artifact_sha256 is None:
                raise BenchmarkDerivedGenerationError(
                    "benchmark-derived classification requires an exact benchmark artifact identity"
                )
        elif (
            self.classification is BenchmarkDerivedGenerationClassification.NOT_BENCHMARK_DERIVED
            and self.benchmark_artifact_sha256 is not None
        ):
            raise BenchmarkDerivedGenerationError(
                "not-benchmark-derived classification cannot claim a benchmark source artifact"
            )

    def _validated_snapshot(self) -> BenchmarkDerivedGenerationFlags:
        if type(self) is not BenchmarkDerivedGenerationFlags:
            raise BenchmarkDerivedGenerationError(
                "flags must be an exact BenchmarkDerivedGenerationFlags"
            )
        return BenchmarkDerivedGenerationFlags(
            training_lineage_sha256=self.training_lineage_sha256,
            contamination_report_sha256=self.contamination_report_sha256,
            transformation_binding_sha256=self.transformation_binding_sha256,
            assessment_artifact_sha256=self.assessment_artifact_sha256,
            classification=self.classification,
            benchmark_artifact_sha256=self.benchmark_artifact_sha256,
        )

    def _benchmark_derived_flag_validated(self) -> bool | None:
        if self.classification is BenchmarkDerivedGenerationClassification.BENCHMARK_DERIVED:
            return True
        if self.classification is BenchmarkDerivedGenerationClassification.NOT_BENCHMARK_DERIVED:
            return False
        return None

    @property
    def benchmark_derived_flag(self) -> bool | None:
        snapshot = BenchmarkDerivedGenerationFlags._validated_snapshot(self)
        return snapshot._benchmark_derived_flag_validated()

    @property
    def can_generate_examples(self) -> bool:
        return False

    @property
    def can_access_benchmark(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "assessment_artifact_sha256": self.assessment_artifact_sha256,
            "benchmark_artifact_sha256": self.benchmark_artifact_sha256,
            "benchmark_derived_flag": self._benchmark_derived_flag_validated(),
            "can_access_benchmark": False,
            "can_authorize_model_promotion": False,
            "can_authorize_training": False,
            "can_generate_examples": False,
            "classification": self.classification.value,
            "contamination_report_sha256": self.contamination_report_sha256,
            "format": "MRL-BENCHMARK-DERIVED-GENERATION-FLAGS-V1",
            "training_lineage_sha256": self.training_lineage_sha256,
            "transformation_binding_sha256": self.transformation_binding_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = BenchmarkDerivedGenerationFlags._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_benchmark_derived_generation_flags(
    lineage: TrainingExampleLineageContract,
    contamination_report: ContaminationEvidenceReport,
    transformation_binding: TrainingTransformationBinding,
    *,
    assessment_artifact_sha256: str,
    classification: BenchmarkDerivedGenerationClassification,
    benchmark_artifact_sha256: str | None = None,
) -> BenchmarkDerivedGenerationFlags:
    """Bind supplied benchmark-derivation evidence to exact MRL-0601/0602/0603 identities."""
    if type(lineage) is not TrainingExampleLineageContract:
        raise BenchmarkDerivedGenerationError(
            "lineage must be an exact TrainingExampleLineageContract"
        )
    if type(contamination_report) is not ContaminationEvidenceReport:
        raise BenchmarkDerivedGenerationError(
            "contamination_report must be an exact ContaminationEvidenceReport"
        )
    if type(transformation_binding) is not TrainingTransformationBinding:
        raise BenchmarkDerivedGenerationError(
            "transformation_binding must be an exact TrainingTransformationBinding"
        )

    try:
        lineage_snapshot = build_training_example_lineage(lineage.example)
    except TrainingExampleLineageError as exc:
        raise BenchmarkDerivedGenerationError(
            "training lineage failed canonical revalidation"
        ) from exc
    if lineage_snapshot.content_sha256 != lineage.content_sha256:
        raise BenchmarkDerivedGenerationError(
            "training lineage identity changed after construction"
        )

    contamination_snapshot = _snapshot_contamination_report(contamination_report)
    transformation_snapshot = _snapshot_transformation_binding(transformation_binding)
    lineage_sha256 = lineage_snapshot.content_sha256
    if contamination_snapshot.training_lineage_sha256 != lineage_sha256:
        raise BenchmarkDerivedGenerationError(
            "contamination report does not bind the supplied training lineage"
        )
    if transformation_snapshot.training_lineage_sha256 != lineage_sha256:
        raise BenchmarkDerivedGenerationError(
            "transformation binding does not bind the supplied training lineage"
        )
    if transformation_snapshot.source_sha256 != lineage_snapshot.example.source_sha256:
        raise BenchmarkDerivedGenerationError(
            "transformation source identity does not match the canonical lineage source"
        )

    return BenchmarkDerivedGenerationFlags(
        training_lineage_sha256=lineage_sha256,
        contamination_report_sha256=contamination_snapshot.content_sha256,
        transformation_binding_sha256=transformation_snapshot.content_sha256,
        assessment_artifact_sha256=assessment_artifact_sha256,
        classification=classification,
        benchmark_artifact_sha256=benchmark_artifact_sha256,
    )


def _snapshot_contamination_report(
    report: ContaminationEvidenceReport,
) -> ContaminationEvidenceReport:
    if type(report.checks) is not tuple:
        raise BenchmarkDerivedGenerationError(
            "contamination report checks must remain an exact tuple"
        )
    if any(type(item) is not ContaminationCheckEvidence for item in report.checks):
        raise BenchmarkDerivedGenerationError(
            "contamination report checks contains an invalid item type"
        )
    checks = tuple(
        ContaminationCheckEvidence(
            kind=item.kind,
            detector_id=item.detector_id,
            detector_artifact_sha256=item.detector_artifact_sha256,
            evidence_artifact_sha256=item.evidence_artifact_sha256,
            disposition=item.disposition,
            similarity_decimal=item.similarity_decimal,
            threshold_decimal=item.threshold_decimal,
        )
        for item in report.checks
    )
    return ContaminationEvidenceReport(
        training_lineage_sha256=report.training_lineage_sha256,
        checks=checks,
    )


def _snapshot_transformation_binding(
    binding: TrainingTransformationBinding,
) -> TrainingTransformationBinding:
    return TrainingTransformationBinding(
        training_lineage_sha256=binding.training_lineage_sha256,
        source_sha256=binding.source_sha256,
        transformation_kind=binding.transformation_kind,
        transformation_artifact_sha256=binding.transformation_artifact_sha256,
        prompt_template_sha256=binding.prompt_template_sha256,
        teacher_model_sha256=binding.teacher_model_sha256,
        teacher_output_sha256=binding.teacher_output_sha256,
    )


def _require_optional_sha256(value: object, label: str) -> None:
    if value is not None:
        _require_sha256(value, label)


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise BenchmarkDerivedGenerationError(f"{label} must be 64 lowercase hex")
