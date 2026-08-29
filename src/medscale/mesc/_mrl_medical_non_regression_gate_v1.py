"""Hard medical non-regression gates for MESC Research Loop V1.

MRL-0306 evaluates the frozen global and subgroup evidence floors in one exact
``ResearchObjectiveContract`` against one independent Tier 3 sealed-evidence report.
Every frozen floor is mandatory: a single failed floor makes the report ineligible for
later Pareto/capability comparison. The result is deterministic evidence only and grants
no execution, training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    EvidenceFloor,
    FloorComparator,
    ResearchObjectiveContract,
)
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedEvaluationEvidenceReport,
    SealedMetricEvidence,
)

__all__ = [
    "MedicalFloorAssessment",
    "MedicalNonRegressionDisposition",
    "MedicalNonRegressionGateError",
    "MedicalNonRegressionGateReport",
    "evaluate_medical_non_regression_gates",
]


_TOKEN: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_CANONICAL_DECIMAL: Final = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")


class MedicalNonRegressionGateError(ValueError):
    """Fail-closed validation error for MRL-0306 hard-gate evaluation."""


class MedicalNonRegressionDisposition(enum.Enum):
    """Non-authoritative hard-gate disposition for later comparison control."""

    SATISFIED = "SATISFIED"
    REGRESSION_DETECTED = "REGRESSION_DETECTED"


@dataclass(frozen=True, slots=True)
class MedicalFloorAssessment:
    """One exact frozen floor evaluated against one sealed aggregate metric artifact."""

    floor_id: str
    metric_id: str
    comparator: FloorComparator
    threshold_decimal: str
    observed_value_decimal: str
    evidence_artifact_sha256: str
    subgroup: str | None
    passed: bool

    def __post_init__(self) -> None:
        if type(self.comparator) is not FloorComparator:
            raise MedicalNonRegressionGateError("comparator must be an exact FloorComparator")
        if type(self.passed) is not bool:
            raise MedicalNonRegressionGateError("passed must be an exact bool")
        _require_token(self.floor_id, "floor_id")
        _require_token(self.metric_id, "metric_id")
        _require_canonical_decimal(self.threshold_decimal, "threshold_decimal")
        _require_canonical_decimal(self.observed_value_decimal, "observed_value_decimal")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        if self.subgroup is not None:
            _require_text(self.subgroup, "subgroup")
        observed = Decimal(self.observed_value_decimal)
        threshold = Decimal(self.threshold_decimal)
        expected = (
            observed >= threshold
            if self.comparator is FloorComparator.GTE
            else observed <= threshold
        )
        if self.passed is not expected:
            raise MedicalNonRegressionGateError(
                "passed does not match the frozen comparator and observed value"
            )

    def to_dict(self) -> dict[str, object]:
        """Return deterministic floor-assessment semantics."""
        return {
            "comparator": self.comparator.value,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "floor_id": self.floor_id,
            "metric_id": self.metric_id,
            "observed_value_decimal": self.observed_value_decimal,
            "passed": self.passed,
            "subgroup": self.subgroup,
            "threshold_decimal": self.threshold_decimal,
        }


@dataclass(frozen=True, slots=True)
class MedicalNonRegressionGateReport:
    """Content-addressed hard-gate report bound to one objective and sealed report."""

    objective_sha256: str
    sealed_evidence_report_sha256: str
    assessments: tuple[MedicalFloorAssessment, ...]
    disposition: MedicalNonRegressionDisposition

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(
            self.sealed_evidence_report_sha256,
            "sealed_evidence_report_sha256",
        )
        if type(self.assessments) is not tuple or not self.assessments:
            raise MedicalNonRegressionGateError("assessments must be a non-empty exact tuple")
        if any(type(item) is not MedicalFloorAssessment for item in self.assessments):
            raise MedicalNonRegressionGateError("assessments contains an invalid item type")
        floor_ids = tuple(item.floor_id for item in self.assessments)
        if floor_ids != tuple(sorted(set(floor_ids))):
            raise MedicalNonRegressionGateError("assessments must be sorted and unique by floor_id")
        if type(self.disposition) is not MedicalNonRegressionDisposition:
            raise MedicalNonRegressionGateError(
                "disposition must be an exact MedicalNonRegressionDisposition"
            )
        expected = (
            MedicalNonRegressionDisposition.SATISFIED
            if all(item.passed for item in self.assessments)
            else MedicalNonRegressionDisposition.REGRESSION_DETECTED
        )
        if self.disposition is not expected:
            raise MedicalNonRegressionGateError(
                "disposition does not match the frozen floor assessments"
            )

    @property
    def comparison_eligible(self) -> bool:
        """Return whether later Pareto comparison may consider this evidence."""
        return self.disposition is MedicalNonRegressionDisposition.SATISFIED

    @property
    def can_authorize(self) -> bool:
        """Hard-gate evidence never grants execution or governance authority."""
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        """MRL V1 permanently defers model-promotion authority."""
        return False

    def semantic_dict(self) -> dict[str, object]:
        """Return deterministic non-authoritative gate semantics."""
        return {
            "assessments": [item.to_dict() for item in self.assessments],
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "comparison_eligible": self.comparison_eligible,
            "disposition": self.disposition.value,
            "format": "MRL-MEDICAL-NON-REGRESSION-GATE-V1",
            "objective_sha256": self.objective_sha256,
            "sealed_evidence_report_sha256": self.sealed_evidence_report_sha256,
        }

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic canonical bytes."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        """Return identity derived outside the semantic preimage."""
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        """Return gate semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def evaluate_medical_non_regression_gates(
    objective: ResearchObjectiveContract,
    sealed_report: SealedEvaluationEvidenceReport,
) -> MedicalNonRegressionGateReport:
    """Evaluate every frozen global/subgroup floor against exact sealed evidence."""
    if type(objective) is not ResearchObjectiveContract:
        raise MedicalNonRegressionGateError(
            "objective must be an exact ResearchObjectiveContract"
        )
    if type(sealed_report) is not SealedEvaluationEvidenceReport:
        raise MedicalNonRegressionGateError(
            "sealed_report must be an exact SealedEvaluationEvidenceReport"
        )

    objective.semantic_dict()
    report = _snapshot_sealed_report(sealed_report)
    if report.objective_sha256 != objective.content_sha256:
        raise MedicalNonRegressionGateError(
            "sealed evidence report does not bind the supplied objective"
        )
    _require_report_is_evidence_only(report)
    _require_sealed_evaluator_bindings(objective, report)

    evidence_by_key = _validated_evidence_index(objective, report)
    floors = tuple(sorted((*objective.hard_guardrails, *objective.subgroup_floors), key=_floor_id))
    assessments = tuple(_assess_floor(floor, evidence_by_key) for floor in floors)
    disposition = (
        MedicalNonRegressionDisposition.SATISFIED
        if all(item.passed for item in assessments)
        else MedicalNonRegressionDisposition.REGRESSION_DETECTED
    )
    return MedicalNonRegressionGateReport(
        objective_sha256=objective.content_sha256,
        sealed_evidence_report_sha256=report.content_sha256,
        assessments=assessments,
        disposition=disposition,
    )


def _snapshot_sealed_report(
    report: SealedEvaluationEvidenceReport,
) -> SealedEvaluationEvidenceReport:
    if any(type(item) is not SealedMetricEvidence for item in report.metric_evidence):
        raise MedicalNonRegressionGateError(
            "sealed report metric_evidence contains an invalid item type"
        )
    return SealedEvaluationEvidenceReport(
        objective_sha256=report.objective_sha256,
        tier_contract_sha256=report.tier_contract_sha256,
        request_sha256=report.request_sha256,
        handoff_sha256=report.handoff_sha256,
        sealed_evidence_ref_sha256=report.sealed_evidence_ref_sha256,
        evaluator_artifacts=tuple(report.evaluator_artifacts),
        metric_evidence=tuple(
            SealedMetricEvidence(
                metric_id=item.metric_id,
                evaluator_id=item.evaluator_id,
                value_decimal=item.value_decimal,
                evidence_artifact_sha256=item.evidence_artifact_sha256,
                subgroup=item.subgroup,
            )
            for item in report.metric_evidence
        ),
    )


def _require_report_is_evidence_only(report: SealedEvaluationEvidenceReport) -> None:
    payload = report.semantic_dict()
    if payload.get("adaptive_agent_visible") is not False:
        raise MedicalNonRegressionGateError("sealed report cannot be adaptive-agent visible")
    if payload.get("can_authorize") is not False:
        raise MedicalNonRegressionGateError("sealed report cannot authorize execution")
    if payload.get("can_authorize_model_promotion") is not False:
        raise MedicalNonRegressionGateError("sealed report cannot authorize model promotion")
    if payload.get("iterative_agent_result_stream") is not False:
        raise MedicalNonRegressionGateError(
            "sealed report cannot expose an iterative result stream"
        )
    if payload.get("sealed_item_level_content_included") is not False:
        raise MedicalNonRegressionGateError(
            "sealed report cannot include item-level sealed content"
        )


def _require_sealed_evaluator_bindings(
    objective: ResearchObjectiveContract,
    report: SealedEvaluationEvidenceReport,
) -> None:
    expected = tuple(
        (identity.evaluator_id, identity.artifact_sha256)
        for identity in objective.evaluator_identities
        if EvaluationTier.SEALED in identity.tiers
    )
    if report.evaluator_artifacts != expected:
        raise MedicalNonRegressionGateError(
            "sealed report evaluator artifacts do not match the frozen objective"
        )


def _validated_evidence_index(
    objective: ResearchObjectiveContract,
    report: SealedEvaluationEvidenceReport,
) -> dict[tuple[str, str | None], SealedMetricEvidence]:
    sealed_metrics = {
        metric.metric_id: metric
        for metric in objective.evaluation_metrics
        if metric.tier is EvaluationTier.SEALED
    }
    if not sealed_metrics:
        raise MedicalNonRegressionGateError("objective has no Tier 3 SEALED evaluation metric")

    index: dict[tuple[str, str | None], SealedMetricEvidence] = {}
    for evidence in report.metric_evidence:
        metric = sealed_metrics.get(evidence.metric_id)
        if metric is None:
            raise MedicalNonRegressionGateError(
                "sealed report contains evidence for an unfrozen Tier 3 metric"
            )
        if evidence.evaluator_id != metric.evaluator_id:
            raise MedicalNonRegressionGateError(
                "sealed metric evidence evaluator does not match the frozen metric"
            )
        key = (evidence.metric_id, evidence.subgroup)
        if key in index:
            raise MedicalNonRegressionGateError("sealed metric evidence key is duplicated")
        index[key] = evidence

    for floor in (*objective.hard_guardrails, *objective.subgroup_floors):
        metric = sealed_metrics.get(floor.metric_id)
        if metric is None:
            raise MedicalNonRegressionGateError(
                f"frozen floor {floor.floor_id!r} is not backed by a Tier 3 SEALED metric"
            )
        key = (floor.metric_id, floor.subgroup)
        if key not in index:
            raise MedicalNonRegressionGateError(
                f"sealed evidence is missing frozen floor {floor.floor_id!r}"
            )
    return index


def _assess_floor(
    floor: EvidenceFloor,
    evidence_by_key: dict[tuple[str, str | None], SealedMetricEvidence],
) -> MedicalFloorAssessment:
    evidence = evidence_by_key[(floor.metric_id, floor.subgroup)]
    observed = Decimal(evidence.value_decimal)
    threshold = Decimal(floor.threshold_decimal)
    if floor.comparator is FloorComparator.GTE:
        passed = observed >= threshold
    elif floor.comparator is FloorComparator.LTE:
        passed = observed <= threshold
    else:
        raise MedicalNonRegressionGateError("unsupported frozen floor comparator")
    return MedicalFloorAssessment(
        floor_id=floor.floor_id,
        metric_id=floor.metric_id,
        comparator=floor.comparator,
        threshold_decimal=floor.threshold_decimal,
        observed_value_decimal=evidence.value_decimal,
        evidence_artifact_sha256=evidence.evidence_artifact_sha256,
        subgroup=floor.subgroup,
        passed=passed,
    )


def _floor_id(floor: EvidenceFloor) -> str:
    return floor.floor_id


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise MedicalNonRegressionGateError(f"{label} must be canonical token text")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise MedicalNonRegressionGateError(f"{label} must be canonical text")
    if "\n" in value or "\r" in value:
        raise MedicalNonRegressionGateError(f"{label} must be one line")


def _require_canonical_decimal(value: object, label: str) -> None:
    if type(value) is not str or _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise MedicalNonRegressionGateError(f"{label} must be canonical decimal text")


def _require_sha256(value: object, label: str) -> None:
    invalid = (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    )
    if invalid:
        raise MedicalNonRegressionGateError(f"{label} must be 64 lowercase hex")
