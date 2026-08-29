"""Deterministic hard medical non-regression gates for MESC Research Loop V1.

MRL-0306 evaluates every frozen global and subgroup evidence floor against the aggregate
Tier 3 evidence admitted by MRL-0305. A satisfied aggregate metric cannot hide a failed
subgroup floor, and no scalar optimization result can override a violated hard gate.

This module evaluates evidence only. It grants no execution, training, promotion,
deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
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
    "HardMedicalGateResult",
    "HardMedicalNonRegressionError",
    "HardMedicalNonRegressionReport",
    "evaluate_hard_medical_non_regression",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_DECIMAL: Final = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")


class HardMedicalNonRegressionError(ValueError):
    """Fail-closed validation error for MRL-0306 hard-gate evaluation."""


@dataclass(frozen=True, slots=True)
class HardMedicalGateResult:
    """One frozen evidence floor evaluated against one bound aggregate metric artifact."""

    floor_id: str
    metric_id: str
    evaluator_id: str
    subgroup: str | None
    comparator: FloorComparator
    threshold_decimal: str
    observed_value_decimal: str
    evidence_artifact_sha256: str
    satisfied: bool

    def __post_init__(self) -> None:
        _require_token(self.floor_id, "floor_id")
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        if self.subgroup is not None:
            _require_text(self.subgroup, "subgroup")
        if type(self.comparator) is not FloorComparator:
            raise HardMedicalNonRegressionError("comparator must be an exact FloorComparator")
        _require_canonical_decimal(self.threshold_decimal, "threshold_decimal")
        _require_canonical_decimal(self.observed_value_decimal, "observed_value_decimal")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        if type(self.satisfied) is not bool:
            raise HardMedicalNonRegressionError("satisfied must be an exact bool")
        expected = _floor_satisfied(
            self.comparator,
            self.threshold_decimal,
            self.observed_value_decimal,
        )
        if self.satisfied is not expected:
            raise HardMedicalNonRegressionError(
                "satisfied must equal the deterministic floor comparison"
            )

    def to_dict(self) -> dict[str, object]:
        """Return deterministic hard-gate semantics."""
        return {
            "comparator": self.comparator.value,
            "evaluator_id": self.evaluator_id,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "floor_id": self.floor_id,
            "metric_id": self.metric_id,
            "observed_value_decimal": self.observed_value_decimal,
            "satisfied": self.satisfied,
            "subgroup": self.subgroup,
            "threshold_decimal": self.threshold_decimal,
        }


@dataclass(frozen=True, slots=True)
class HardMedicalNonRegressionReport:
    """Evidence-only result for every hard global and subgroup floor in one objective."""

    objective_sha256: str
    sealed_evidence_report_sha256: str
    gates: tuple[HardMedicalGateResult, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(self.sealed_evidence_report_sha256, "sealed_evidence_report_sha256")
        if type(self.gates) is not tuple or not self.gates:
            raise HardMedicalNonRegressionError("gates must be a non-empty exact tuple")
        if any(type(gate) is not HardMedicalGateResult for gate in self.gates):
            raise HardMedicalNonRegressionError("gates contains an invalid item type")
        floor_ids = tuple(gate.floor_id for gate in self.gates)
        if floor_ids != tuple(sorted(set(floor_ids))):
            raise HardMedicalNonRegressionError("gates must be unique and sorted by floor_id")

    @property
    def all_hard_gates_satisfied(self) -> bool:
        """Return whether every frozen hard floor is satisfied by the bound evidence."""
        return all(gate.satisfied for gate in self.gates)

    @property
    def violated_floor_ids(self) -> tuple[str, ...]:
        """Return deterministic identifiers for every violated global or subgroup floor."""
        return tuple(gate.floor_id for gate in self.gates if not gate.satisfied)

    @property
    def can_authorize(self) -> bool:
        """Hard-gate evidence never grants execution or governance authority."""
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        """MRL-0306 cannot make a model-promotion decision."""
        return False

    @property
    def content_sha256(self) -> str:
        """Return deterministic identity over the complete hard-gate result."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical evidence-only bytes."""
        return canonical_semantic_bytes(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return complete non-authoritative hard-gate semantics."""
        return {
            "all_hard_gates_satisfied": self.all_hard_gates_satisfied,
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "format": "MRL-HARD-MEDICAL-NON-REGRESSION-V1",
            "gates": [gate.to_dict() for gate in self.gates],
            "objective_sha256": self.objective_sha256,
            "sealed_evidence_report_sha256": self.sealed_evidence_report_sha256,
            "violated_floor_ids": list(self.violated_floor_ids),
        }

    def to_dict(self) -> dict[str, object]:
        """Return report semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def evaluate_hard_medical_non_regression(
    objective: ResearchObjectiveContract,
    sealed_report: SealedEvaluationEvidenceReport,
) -> HardMedicalNonRegressionReport:
    """Evaluate every frozen hard floor against one exact independent Tier 3 report."""
    if type(objective) is not ResearchObjectiveContract:
        raise HardMedicalNonRegressionError(
            "objective must be an exact ResearchObjectiveContract"
        )
    if type(sealed_report) is not SealedEvaluationEvidenceReport:
        raise HardMedicalNonRegressionError(
            "sealed_report must be an exact SealedEvaluationEvidenceReport"
        )

    try:
        objective.semantic_dict()
        objective_sha256 = objective.content_sha256
    except (AttributeError, TypeError, ValueError) as exc:
        raise HardMedicalNonRegressionError("objective failed semantic revalidation") from exc

    report = _snapshot_sealed_report(sealed_report)
    if report.objective_sha256 != objective_sha256:
        raise HardMedicalNonRegressionError(
            "sealed evidence report does not match the frozen objective"
        )

    evidence_by_key = _validate_report_against_objective(objective, report)
    floors = tuple(sorted((*objective.hard_guardrails, *objective.subgroup_floors), key=_floor_key))
    if not floors:
        raise HardMedicalNonRegressionError("objective has no hard evidence floors")

    metric_evaluator = {
        metric.metric_id: metric.evaluator_id
        for metric in objective.evaluation_metrics
        if metric.tier is EvaluationTier.SEALED
    }
    gates = tuple(
        _evaluate_floor(floor, evidence_by_key, metric_evaluator)
        for floor in floors
    )
    return HardMedicalNonRegressionReport(
        objective_sha256=objective_sha256,
        sealed_evidence_report_sha256=report.content_sha256,
        gates=gates,
    )


def _snapshot_sealed_report(
    report: SealedEvaluationEvidenceReport,
) -> SealedEvaluationEvidenceReport:
    if type(report.evaluator_artifacts) is not tuple:
        raise HardMedicalNonRegressionError("sealed evaluator_artifacts must remain an exact tuple")
    for item in report.evaluator_artifacts:
        if type(item) is not tuple or len(item) != 2:
            raise HardMedicalNonRegressionError("sealed evaluator_artifacts contains invalid entry")
    if type(report.metric_evidence) is not tuple:
        raise HardMedicalNonRegressionError("sealed metric_evidence must remain an exact tuple")
    if any(type(item) is not SealedMetricEvidence for item in report.metric_evidence):
        raise HardMedicalNonRegressionError("sealed metric_evidence contains invalid item type")

    try:
        metrics = tuple(
            SealedMetricEvidence(
                metric_id=item.metric_id,
                evaluator_id=item.evaluator_id,
                value_decimal=item.value_decimal,
                evidence_artifact_sha256=item.evidence_artifact_sha256,
                subgroup=item.subgroup,
            )
            for item in report.metric_evidence
        )
        return SealedEvaluationEvidenceReport(
            objective_sha256=report.objective_sha256,
            tier_contract_sha256=report.tier_contract_sha256,
            request_sha256=report.request_sha256,
            handoff_sha256=report.handoff_sha256,
            sealed_evidence_ref_sha256=report.sealed_evidence_ref_sha256,
            evaluator_artifacts=report.evaluator_artifacts,
            metric_evidence=metrics,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise HardMedicalNonRegressionError(
            "sealed evidence report failed semantic revalidation"
        ) from exc


def _validate_report_against_objective(
    objective: ResearchObjectiveContract,
    report: SealedEvaluationEvidenceReport,
) -> dict[tuple[str, str | None], SealedMetricEvidence]:
    sealed_metrics = tuple(
        metric for metric in objective.evaluation_metrics if metric.tier is EvaluationTier.SEALED
    )
    if not sealed_metrics:
        raise HardMedicalNonRegressionError("objective has no frozen Tier 3 evaluation metrics")

    expected_evaluator_artifacts = tuple(
        (identity.evaluator_id, identity.artifact_sha256)
        for identity in objective.evaluator_identities
        if EvaluationTier.SEALED in identity.tiers
    )
    if report.evaluator_artifacts != expected_evaluator_artifacts:
        raise HardMedicalNonRegressionError(
            "sealed evaluator artifacts do not match the frozen objective"
        )

    evaluator_by_metric = {metric.metric_id: metric.evaluator_id for metric in sealed_metrics}
    expected_keys: set[tuple[str, str, str | None]] = {
        (metric.metric_id, metric.evaluator_id, None) for metric in sealed_metrics
    }
    for floor in objective.subgroup_floors:
        evaluator_id = evaluator_by_metric.get(floor.metric_id)
        if evaluator_id is None:
            raise HardMedicalNonRegressionError(
                "subgroup hard floor references no frozen Tier 3 metric"
            )
        expected_keys.add((floor.metric_id, evaluator_id, floor.subgroup))
    for floor in objective.hard_guardrails:
        if floor.metric_id not in evaluator_by_metric:
            raise HardMedicalNonRegressionError(
                "global hard floor references no frozen Tier 3 metric"
            )

    observed_keys = {
        (item.metric_id, item.evaluator_id, item.subgroup) for item in report.metric_evidence
    }
    if observed_keys != expected_keys:
        raise HardMedicalNonRegressionError(
            "sealed metric evidence does not exactly match frozen Tier 3 evidence requirements"
        )

    return {(item.metric_id, item.subgroup): item for item in report.metric_evidence}


def _evaluate_floor(
    floor: EvidenceFloor,
    evidence_by_key: dict[tuple[str, str | None], SealedMetricEvidence],
    metric_evaluator: dict[str, str],
) -> HardMedicalGateResult:
    evidence = evidence_by_key.get((floor.metric_id, floor.subgroup))
    if evidence is None:
        raise HardMedicalNonRegressionError(
            f"missing sealed evidence for hard floor {floor.floor_id!r}"
        )
    expected_evaluator = metric_evaluator.get(floor.metric_id)
    if expected_evaluator is None or evidence.evaluator_id != expected_evaluator:
        raise HardMedicalNonRegressionError(
            f"hard floor {floor.floor_id!r} does not bind the frozen evaluator"
        )
    satisfied = _floor_satisfied(
        floor.comparator,
        floor.threshold_decimal,
        evidence.value_decimal,
    )
    return HardMedicalGateResult(
        floor_id=floor.floor_id,
        metric_id=floor.metric_id,
        evaluator_id=evidence.evaluator_id,
        subgroup=floor.subgroup,
        comparator=floor.comparator,
        threshold_decimal=floor.threshold_decimal,
        observed_value_decimal=evidence.value_decimal,
        evidence_artifact_sha256=evidence.evidence_artifact_sha256,
        satisfied=satisfied,
    )


def _floor_satisfied(
    comparator: FloorComparator,
    threshold_decimal: str,
    observed_value_decimal: str,
) -> bool:
    threshold = _parse_decimal(threshold_decimal, "threshold_decimal")
    observed = _parse_decimal(observed_value_decimal, "observed_value_decimal")
    if comparator is FloorComparator.GTE:
        return observed >= threshold
    if comparator is FloorComparator.LTE:
        return observed <= threshold
    raise HardMedicalNonRegressionError("unsupported hard-floor comparator")


def _floor_key(floor: EvidenceFloor) -> str:
    return floor.floor_id


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise HardMedicalNonRegressionError(f"{label} must be canonical text")
    if any(character.isspace() for character in value):
        raise HardMedicalNonRegressionError(f"{label} cannot contain whitespace")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise HardMedicalNonRegressionError(f"{label} must be canonical text")
    if "\n" in value or "\r" in value:
        raise HardMedicalNonRegressionError(f"{label} must be one line")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise HardMedicalNonRegressionError(f"{label} must be 64 lowercase hex")


def _require_canonical_decimal(value: object, label: str) -> None:
    if type(value) is not str or _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise HardMedicalNonRegressionError(f"{label} must be canonical decimal text")
    _parse_decimal(value, label)


def _parse_decimal(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise HardMedicalNonRegressionError(f"{label} must be a finite decimal") from exc
    if not parsed.is_finite():
        raise HardMedicalNonRegressionError(f"{label} must be a finite decimal")
    return parsed
