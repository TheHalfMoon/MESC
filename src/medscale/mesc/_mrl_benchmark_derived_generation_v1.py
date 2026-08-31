"""Benchmark-derived generation flags for MESC Research Loop V1.

MRL-0604 binds one exact training lineage, contamination assessment, and transformation
provenance record to an explicit benchmark-derivation classification. It records supplied
provenance evidence only; it does not generate data, inspect benchmarks, execute detectors,
or authorize training or model promotion.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_contamination_interfaces_v1 import (
    ContaminationEvidenceReport,
    ContaminationInterfaceError,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    TrainingExampleLineageError,
)
from medscale.mesc._mrl_training_transformation_binding_v1 import (
    TrainingTransformationBinding,
    TrainingTransformationBindingError,
)

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


def _make_flags_identity_registry() -> tuple[
    Callable[[BenchmarkDerivedGenerationFlags, str], None],
    Callable[[BenchmarkDerivedGenerationFlags], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: BenchmarkDerivedGenerationFlags, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise BenchmarkDerivedGenerationError(
                "benchmark flags construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: BenchmarkDerivedGenerationFlags) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise BenchmarkDerivedGenerationError(
                "benchmark flags construction identity is missing"
            )
        return identity

    return store, load


_store_flags_identity, _load_flags_identity = _make_flags_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
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
        _store_flags_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> BenchmarkDerivedGenerationFlags:
        if type(self) is not BenchmarkDerivedGenerationFlags:
            raise BenchmarkDerivedGenerationError(
                "flags must be an exact BenchmarkDerivedGenerationFlags"
            )
        bound_content_sha256 = _load_flags_identity(self)
        _require_sha256(bound_content_sha256, "bound benchmark flags content_sha256")
        snapshot = BenchmarkDerivedGenerationFlags(
            training_lineage_sha256=self.training_lineage_sha256,
            contamination_report_sha256=self.contamination_report_sha256,
            transformation_binding_sha256=self.transformation_binding_sha256,
            assessment_artifact_sha256=self.assessment_artifact_sha256,
            classification=self.classification,
            benchmark_artifact_sha256=self.benchmark_artifact_sha256,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise BenchmarkDerivedGenerationError(
                "benchmark flags identity changed after construction"
            )
        return snapshot

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
    """Bind supplied benchmark evidence to construction-bound MRL-0601/0602/0603 inputs."""
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
        example_snapshot, lineage_sha256 = lineage._validated_example()
        contamination_snapshot = contamination_report._validated_snapshot()
        transformation_snapshot = transformation_binding._validated_snapshot()
    except (
        TrainingExampleLineageError,
        ContaminationInterfaceError,
        TrainingTransformationBindingError,
    ) as exc:
        raise BenchmarkDerivedGenerationError(
            "benchmark derivation evidence failed canonical revalidation"
        ) from exc

    if contamination_snapshot.training_lineage_sha256 != lineage_sha256:
        raise BenchmarkDerivedGenerationError(
            "contamination report does not bind the supplied training lineage"
        )
    if transformation_snapshot.training_lineage_sha256 != lineage_sha256:
        raise BenchmarkDerivedGenerationError(
            "transformation binding does not bind the supplied training lineage"
        )
    if transformation_snapshot.source_sha256 != example_snapshot.source_sha256:
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


def _require_optional_sha256(value: object, label: str) -> None:
    if value is not None:
        _require_sha256(value, label)


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise BenchmarkDerivedGenerationError(f"{label} must be 64 lowercase hex")
