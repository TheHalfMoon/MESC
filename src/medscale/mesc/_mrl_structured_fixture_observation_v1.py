"""Deterministic fixture-only structured observation envelope for MRL-0203.

The envelope turns already-typed fixture results into bounded observation data. Raw
stdout/stderr content is never accepted as an observation field; only content-addressed
raw-output artifact identities may be retained for human diagnosis. Diagnostics remain
bounded untrusted data and cannot become control instructions.

This module is declarative only. It performs no filesystem, network, subprocess, model,
data, GPU, inference, training, promotion, deployment, release, or clinical action and
grants no such authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final, TypeVar

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import FixtureEvaluation
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputDisposition,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier

__all__ = [
    "FixtureObservationDiagnostic",
    "FixtureObservationError",
    "FixtureObservationFailureClass",
    "FixtureObservationResourceUse",
    "FixtureObservationRunStatus",
    "FixtureRawOutputArtifact",
    "FixtureRawOutputStream",
    "StructuredFixtureObservation",
]

_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_MAX_DIAGNOSTICS: Final = 16
_MAX_DIAGNOSTIC_DETAIL_CHARS: Final = 256
_T = TypeVar("_T")


class FixtureObservationError(ValueError):
    """Fail-closed validation error for one fixture observation envelope."""


class FixtureObservationRunStatus(enum.Enum):
    """Typed fixture run status exposed to the research loop."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FixtureObservationFailureClass(enum.Enum):
    """Bounded failure classes for a fixture-only observation."""

    EXECUTION_FAILED = "EXECUTION_FAILED"
    INVALID_RESULT = "INVALID_RESULT"
    POLICY_REJECTED = "POLICY_REJECTED"
    RESOURCE_BLOCKED = "RESOURCE_BLOCKED"


class FixtureRawOutputStream(enum.Enum):
    """Raw stream identity retained only as a content-addressed artifact reference."""

    STDOUT = "STDOUT"
    STDERR = "STDERR"


@dataclass(frozen=True, slots=True)
class FixtureObservationResourceUse:
    """Deterministic fixture resource accounting with no real-runtime authority."""

    operation_count: int
    evaluator_invocations: int
    storage_bytes: int

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.operation_count, "operation_count")
        _require_nonnegative_int(self.evaluator_invocations, "evaluator_invocations")
        _require_nonnegative_int(self.storage_bytes, "storage_bytes")

    def to_dict(self) -> dict[str, int]:
        return {
            "operation_count": self.operation_count,
            "evaluator_invocations": self.evaluator_invocations,
            "storage_bytes": self.storage_bytes,
        }


@dataclass(frozen=True, slots=True)
class FixtureRawOutputArtifact:
    """Identity-only reference to raw stdout/stderr retained outside control input."""

    stream: FixtureRawOutputStream
    artifact_sha256: str

    def __post_init__(self) -> None:
        _require_exact_enum(self.stream, FixtureRawOutputStream, "stream")
        _require_sha256(self.artifact_sha256, "artifact_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "stream": self.stream.value,
            "artifact_sha256": self.artifact_sha256,
            "trusted_control": False,
        }


@dataclass(frozen=True, slots=True)
class FixtureObservationDiagnostic:
    """Bounded diagnostic data that is never interpreted as a control directive."""

    code: str
    detail: str

    def __post_init__(self) -> None:
        _require_token(self.code, "diagnostic code")
        if type(self.detail) is not str or not self.detail:
            raise FixtureObservationError("diagnostic detail must be a non-empty exact str")
        if len(self.detail) > _MAX_DIAGNOSTIC_DETAIL_CHARS:
            raise FixtureObservationError("diagnostic detail exceeds the bounded length")
        if any(ord(char) < 32 for char in self.detail):
            raise FixtureObservationError("diagnostic detail cannot contain control characters")

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "detail": self.detail,
            "trusted_control": False,
        }


@dataclass(frozen=True, slots=True)
class StructuredFixtureObservation:
    """Content-addressed, non-authoritative structured result view for MRL fixtures."""

    observation_id: str
    input_admission: ResearchInputAdmissionContract
    run_status: FixtureObservationRunStatus
    evaluation: FixtureEvaluation | None
    resource_use: FixtureObservationResourceUse
    failure_class: FixtureObservationFailureClass | None
    raw_output_artifacts: tuple[FixtureRawOutputArtifact, ...] = ()
    diagnostics: tuple[FixtureObservationDiagnostic, ...] = ()
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_observation(self)

    def _validated_snapshot(self) -> StructuredFixtureObservation:
        _require_exact_type(self, StructuredFixtureObservation, "structured_fixture_observation")
        return StructuredFixtureObservation(
            observation_id=self.observation_id,
            input_admission=_snapshot_admission(self.input_admission),
            run_status=self.run_status,
            evaluation=(None if self.evaluation is None else _snapshot_evaluation(self.evaluation)),
            resource_use=_snapshot_resource_use(self.resource_use),
            failure_class=self.failure_class,
            raw_output_artifacts=tuple(
                _snapshot_raw_output(item)
                for item in _require_exact_tuple_items(
                    self.raw_output_artifacts,
                    FixtureRawOutputArtifact,
                    "raw_output_artifacts",
                )
            ),
            diagnostics=tuple(
                _snapshot_diagnostic(item)
                for item in _require_exact_tuple_items(
                    self.diagnostics,
                    FixtureObservationDiagnostic,
                    "diagnostics",
                )
            ),
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        admission_semantics = ResearchInputAdmissionContract.semantic_dict(self.input_admission)
        admission_sha256 = derive_content_sha256(admission_semantics)
        evaluation_sha256 = None
        metric_artifacts: list[dict[str, object]] = []
        selected_metric_values: list[dict[str, object]] = []
        exposed_fields: list[str] = []
        if self.evaluation is not None:
            evaluation_semantics = FixtureEvaluation.semantic_dict(self.evaluation)
            evaluation_sha256 = derive_content_sha256(evaluation_semantics)
            metric_artifacts = [
                {
                    "metric_id": self.evaluation.metric_id,
                    "artifact_sha256": evaluation_sha256,
                    "evaluator_sha256": self.evaluation.evaluator_sha256,
                    "tier": int(EvaluationTier.DEVELOPMENT),
                }
            ]
            selected_metric_values = [
                {
                    "metric_id": self.evaluation.metric_id,
                    "artifact_sha256": evaluation_sha256,
                    "score": self.evaluation.score,
                    "max_score": self.evaluation.max_score,
                }
            ]
            exposed_fields = ["max_score", "score"]

        artifact_hashes = {item.artifact_sha256 for item in self.raw_output_artifacts}
        if self.input_admission.source_artifact_sha256 is not None:
            artifact_hashes.add(self.input_admission.source_artifact_sha256)
        if evaluation_sha256 is not None:
            artifact_hashes.add(evaluation_sha256)

        return {
            "format": "MRL-STRUCTURED-FIXTURE-OBSERVATION-V1",
            "observation_id": self.observation_id,
            "input_admission_sha256": admission_sha256,
            "input_classification": self.input_admission.classification.value,
            "run_status": self.run_status.value,
            "metric_artifacts": metric_artifacts,
            "selected_metric_values": selected_metric_values,
            "guardrail_outcomes": [],
            "resource_use": self.resource_use.to_dict(),
            "failure_class": None if self.failure_class is None else self.failure_class.value,
            "artifact_sha256s": sorted(artifact_hashes),
            "raw_output_artifacts": [item.to_dict() for item in self.raw_output_artifacts],
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "tier_accounting": {
                "tier": int(EvaluationTier.DEVELOPMENT),
                "queries_used": 0,
                "result_exposures_used": 1 if self.evaluation is not None else 0,
                "exposed_result_fields": exposed_fields,
            },
            "raw_output_trusted_control": False,
            "diagnostics_trusted_control": False,
            "trusted_control_input": False,
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, StructuredFixtureObservation, "structured_fixture_observation")
        snapshot = StructuredFixtureObservation._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, StructuredFixtureObservation, "structured_fixture_observation")
        return canonical_semantic_bytes(StructuredFixtureObservation.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, StructuredFixtureObservation, "structured_fixture_observation")
        return derive_content_sha256(StructuredFixtureObservation.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, StructuredFixtureObservation, "structured_fixture_observation")
        data = StructuredFixtureObservation.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _validate_observation(observation: StructuredFixtureObservation) -> None:
    _require_id(observation.observation_id, "observation_id")
    _require_exact_enum(observation.run_status, FixtureObservationRunStatus, "run_status")
    _require_true(observation.fixture_only, "fixture_only")
    _require_true(observation.non_evidence, "non_evidence")

    admission = _snapshot_admission(observation.input_admission)
    if admission.disposition is not ResearchInputDisposition.LEARNING_ADMITTED:
        raise FixtureObservationError("observation input must be structurally learning-admitted")
    if ResearchLearningSurface.OBSERVATION not in admission.allowed_learning_surfaces:
        raise FixtureObservationError(
            "observation input is not admitted to the OBSERVATION surface"
        )

    _snapshot_resource_use(observation.resource_use)
    raw_outputs = tuple(
        _snapshot_raw_output(item)
        for item in _require_exact_tuple_items(
            observation.raw_output_artifacts,
            FixtureRawOutputArtifact,
            "raw_output_artifacts",
        )
    )
    raw_keys = tuple((item.stream.value, item.artifact_sha256) for item in raw_outputs)
    if raw_keys != tuple(sorted(set(raw_keys))):
        raise FixtureObservationError("raw_output_artifacts must be unique and strictly sorted")

    diagnostics = tuple(
        _snapshot_diagnostic(item)
        for item in _require_exact_tuple_items(
            observation.diagnostics,
            FixtureObservationDiagnostic,
            "diagnostics",
        )
    )
    if len(diagnostics) > _MAX_DIAGNOSTICS:
        raise FixtureObservationError("diagnostics exceed the bounded item count")
    diagnostic_codes = tuple(item.code for item in diagnostics)
    if diagnostic_codes != tuple(sorted(set(diagnostic_codes))):
        raise FixtureObservationError("diagnostics must have unique, strictly sorted codes")

    if observation.run_status is FixtureObservationRunStatus.SUCCEEDED:
        if observation.failure_class is not None:
            raise FixtureObservationError("successful observation cannot declare a failure class")
        if admission.classification is not ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT:
            raise FixtureObservationError(
                "successful fixture observation requires DETERMINISTIC_FIXTURE_OUTPUT input"
            )
        evaluation = _snapshot_evaluation_required(observation.evaluation)
        if admission.source_artifact_sha256 != evaluation.content_sha256:
            raise FixtureObservationError(
                "successful observation admission must bind the exact fixture evaluation"
            )
        return

    _require_exact_enum(observation.failure_class, FixtureObservationFailureClass, "failure_class")
    if observation.evaluation is not None:
        raise FixtureObservationError("failed observation cannot claim a successful evaluation")
    if (
        admission.classification
        is not ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT
    ):
        raise FixtureObservationError(
            "failed fixture observation requires NEGATIVE_OR_INVALID_RESEARCH_RESULT input"
        )
    source_sha256 = admission.source_artifact_sha256
    if source_sha256 is None:
        raise FixtureObservationError("failed observation requires a source artifact identity")
    raw_hashes = {item.artifact_sha256 for item in raw_outputs}
    if source_sha256 not in raw_hashes:
        raise FixtureObservationError(
            "failed observation source artifact must be retained as a raw-output artifact identity"
        )


def _snapshot_admission(value: ResearchInputAdmissionContract) -> ResearchInputAdmissionContract:
    _require_exact_type(value, ResearchInputAdmissionContract, "input_admission")
    try:
        return ResearchInputAdmissionContract._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureObservationError("input_admission failed canonical revalidation") from exc


def _snapshot_evaluation(value: FixtureEvaluation) -> FixtureEvaluation:
    _require_exact_type(value, FixtureEvaluation, "evaluation")
    return FixtureEvaluation(
        surface_sha256=value.surface_sha256,
        evaluator_sha256=value.evaluator_sha256,
        candidate_sha256=value.candidate_sha256,
        metric_id=value.metric_id,
        score=value.score,
        max_score=value.max_score,
    )


def _snapshot_evaluation_required(value: FixtureEvaluation | None) -> FixtureEvaluation:
    if value is None:
        raise FixtureObservationError("successful observation requires a fixture evaluation")
    return _snapshot_evaluation(value)


def _snapshot_resource_use(value: FixtureObservationResourceUse) -> FixtureObservationResourceUse:
    _require_exact_type(value, FixtureObservationResourceUse, "resource_use")
    return FixtureObservationResourceUse(
        operation_count=value.operation_count,
        evaluator_invocations=value.evaluator_invocations,
        storage_bytes=value.storage_bytes,
    )


def _snapshot_raw_output(value: FixtureRawOutputArtifact) -> FixtureRawOutputArtifact:
    _require_exact_type(value, FixtureRawOutputArtifact, "raw output artifact")
    return FixtureRawOutputArtifact(stream=value.stream, artifact_sha256=value.artifact_sha256)


def _snapshot_diagnostic(value: FixtureObservationDiagnostic) -> FixtureObservationDiagnostic:
    _require_exact_type(value, FixtureObservationDiagnostic, "diagnostic")
    return FixtureObservationDiagnostic(code=value.code, detail=value.detail)


def _require_exact_tuple_items(
    values: tuple[_T, ...],
    expected: type[_T],
    label: str,
) -> tuple[_T, ...]:
    if type(values) is not tuple:
        raise FixtureObservationError(f"{label} must be an exact tuple")
    for value in values:
        _require_exact_type(value, expected, label)
    return values


def _require_id(value: str, label: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise FixtureObservationError(f"{label} must be lowercase kebab-case [a-z0-9-]")


def _require_token(value: str, label: str) -> None:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise FixtureObservationError(f"{label} must be a canonical token")


def _require_sha256(value: str, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise FixtureObservationError(f"{label} must be a lowercase 64-character SHA-256 digest")


def _require_nonnegative_int(value: int, label: str) -> None:
    if type(value) is not int or value < 0:
        raise FixtureObservationError(f"{label} must be a nonnegative exact int")


def _require_true(value: bool, label: str) -> None:
    if value is not True:
        raise FixtureObservationError(f"{label} must be exactly true")


def _require_exact_enum(value: object, enum_type: type[enum.Enum], label: str) -> None:
    if type(value) is not enum_type:
        raise FixtureObservationError(f"{label} must be exact {enum_type.__name__}")


def _require_exact_type(value: object, expected: type[object], label: str) -> None:
    if type(value) is not expected:
        raise FixtureObservationError(f"{label} must be exact {expected.__name__}")
