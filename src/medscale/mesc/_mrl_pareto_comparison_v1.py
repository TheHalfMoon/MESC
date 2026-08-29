"""Pareto/multi-objective comparison for MESC Research Loop V1.

MRL-0307 applies hard medical admissibility before any multi-objective comparison. A
candidate that violates a frozen hard gate is rejected from Pareto comparison even when
one or more aggregate optimization metrics improve.

This module evaluates evidence only. It grants no execution, training, promotion,
deployment, release, or clinical authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_hard_medical_non_regression_v1 import (
    HardMedicalNonRegressionReport,
    evaluate_hard_medical_non_regression,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    MetricContract,
    MetricDirection,
    ResearchObjectiveContract,
)
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedEvaluationEvidenceReport,
    SealedMetricEvidence,
)

__all__ = [
    "MetricComparisonRelation",
    "ParetoComparisonError",
    "ParetoComparisonReport",
    "ParetoMetricComparison",
    "ParetoRelation",
    "compare_pareto_evidence",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_DECIMAL: Final = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")


class ParetoComparisonError(ValueError):
    """Fail-closed validation error for MRL-0307 comparison semantics."""


class MetricComparisonRelation(enum.Enum):
    BETTER = "BETTER"
    EQUAL = "EQUAL"
    WORSE = "WORSE"


class ParetoRelation(enum.Enum):
    BOTH_REJECTED_HARD_GATE = "BOTH_REJECTED_HARD_GATE"
    CANDIDATE_REJECTED_HARD_GATE = "CANDIDATE_REJECTED_HARD_GATE"
    REFERENCE_REJECTED_HARD_GATE = "REFERENCE_REJECTED_HARD_GATE"
    CANDIDATE_DOMINATES = "CANDIDATE_DOMINATES"
    REFERENCE_DOMINATES = "REFERENCE_DOMINATES"
    EQUIVALENT = "EQUIVALENT"
    TRADEOFF = "TRADEOFF"


@dataclass(frozen=True, slots=True)
class ParetoMetricComparison:
    """One frozen Tier 3 optimization metric compared in its declared direction."""

    metric_id: str
    evaluator_id: str
    direction: MetricDirection
    reference_value_decimal: str
    candidate_value_decimal: str
    reference_evidence_artifact_sha256: str
    candidate_evidence_artifact_sha256: str
    relation: MetricComparisonRelation

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        if type(self.direction) is not MetricDirection:
            raise ParetoComparisonError("direction must be an exact MetricDirection")
        _require_canonical_decimal(self.reference_value_decimal, "reference_value_decimal")
        _require_canonical_decimal(self.candidate_value_decimal, "candidate_value_decimal")
        _require_sha256(
            self.reference_evidence_artifact_sha256,
            "reference_evidence_artifact_sha256",
        )
        _require_sha256(
            self.candidate_evidence_artifact_sha256,
            "candidate_evidence_artifact_sha256",
        )
        if type(self.relation) is not MetricComparisonRelation:
            raise ParetoComparisonError("relation must be an exact MetricComparisonRelation")
        expected = _metric_relation(
            self.direction,
            self.reference_value_decimal,
            self.candidate_value_decimal,
        )
        if self.relation is not expected:
            raise ParetoComparisonError(
                "relation must equal the deterministic directional comparison"
            )

    def _validated_snapshot(self) -> ParetoMetricComparison:
        if type(self) is not ParetoMetricComparison:
            raise ParetoComparisonError("metric must be an exact ParetoMetricComparison")
        return ParetoMetricComparison(
            metric_id=self.metric_id,
            evaluator_id=self.evaluator_id,
            direction=self.direction,
            reference_value_decimal=self.reference_value_decimal,
            candidate_value_decimal=self.candidate_value_decimal,
            reference_evidence_artifact_sha256=self.reference_evidence_artifact_sha256,
            candidate_evidence_artifact_sha256=self.candidate_evidence_artifact_sha256,
            relation=self.relation,
        )

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "candidate_evidence_artifact_sha256": self.candidate_evidence_artifact_sha256,
            "candidate_value_decimal": self.candidate_value_decimal,
            "direction": self.direction.value,
            "evaluator_id": self.evaluator_id,
            "metric_id": self.metric_id,
            "reference_evidence_artifact_sha256": self.reference_evidence_artifact_sha256,
            "reference_value_decimal": self.reference_value_decimal,
            "relation": self.relation.value,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated metric-comparison semantics."""
        snapshot = ParetoMetricComparison._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True)
class ParetoComparisonReport:
    """Evidence-only hard-gate-first relation between two sealed evaluation reports."""

    objective_sha256: str
    reference_evidence_report_sha256: str
    candidate_evidence_report_sha256: str
    reference_hard_gate_report_sha256: str
    candidate_hard_gate_report_sha256: str
    relation: ParetoRelation
    metrics: tuple[ParetoMetricComparison, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(
            self.reference_evidence_report_sha256,
            "reference_evidence_report_sha256",
        )
        _require_sha256(
            self.candidate_evidence_report_sha256,
            "candidate_evidence_report_sha256",
        )
        _require_sha256(
            self.reference_hard_gate_report_sha256,
            "reference_hard_gate_report_sha256",
        )
        _require_sha256(
            self.candidate_hard_gate_report_sha256,
            "candidate_hard_gate_report_sha256",
        )
        if type(self.relation) is not ParetoRelation:
            raise ParetoComparisonError("relation must be an exact ParetoRelation")
        if type(self.metrics) is not tuple:
            raise ParetoComparisonError("metrics must be an exact tuple")
        if any(type(metric) is not ParetoMetricComparison for metric in self.metrics):
            raise ParetoComparisonError("metrics contains an invalid item type")
        snapshots = tuple(ParetoMetricComparison._validated_snapshot(metric) for metric in self.metrics)
        metric_ids = tuple(metric.metric_id for metric in snapshots)
        if metric_ids != tuple(sorted(set(metric_ids))):
            raise ParetoComparisonError("metrics must be unique and sorted by metric_id")

        hard_gate_relation = self.relation in {
            ParetoRelation.BOTH_REJECTED_HARD_GATE,
            ParetoRelation.CANDIDATE_REJECTED_HARD_GATE,
            ParetoRelation.REFERENCE_REJECTED_HARD_GATE,
        }
        if hard_gate_relation and snapshots:
            raise ParetoComparisonError(
                "optimization metrics must remain unevaluated when a hard gate fails"
            )
        if not hard_gate_relation and not snapshots:
            raise ParetoComparisonError(
                "admissible Pareto comparison requires at least one frozen metric"
            )
        if snapshots and self.relation is not _pareto_relation(snapshots):
            raise ParetoComparisonError("relation must equal the deterministic Pareto relation")

    def _validated_snapshot(self) -> ParetoComparisonReport:
        if type(self) is not ParetoComparisonReport:
            raise ParetoComparisonError("report must be an exact ParetoComparisonReport")
        if type(self.metrics) is not tuple:
            raise ParetoComparisonError("metrics must be an exact tuple")
        return ParetoComparisonReport(
            objective_sha256=self.objective_sha256,
            reference_evidence_report_sha256=self.reference_evidence_report_sha256,
            candidate_evidence_report_sha256=self.candidate_evidence_report_sha256,
            reference_hard_gate_report_sha256=self.reference_hard_gate_report_sha256,
            candidate_hard_gate_report_sha256=self.candidate_hard_gate_report_sha256,
            relation=self.relation,
            metrics=tuple(ParetoMetricComparison._validated_snapshot(metric) for metric in self.metrics),
        )

    @property
    def can_authorize(self) -> bool:
        """Pareto evidence cannot grant execution or governance authority."""
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        """MRL-0307 cannot make a model-promotion decision."""
        return False

    @property
    def content_sha256(self) -> str:
        """Return identity derived from freshly validated comparison semantics."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical evidence-only bytes after complete revalidation."""
        return canonical_semantic_bytes(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "candidate_evidence_report_sha256": self.candidate_evidence_report_sha256,
            "candidate_hard_gate_report_sha256": self.candidate_hard_gate_report_sha256,
            "format": "MRL-PARETO-COMPARISON-V1",
            "metrics": [metric._to_dict_validated() for metric in self.metrics],
            "objective_sha256": self.objective_sha256,
            "reference_evidence_report_sha256": self.reference_evidence_report_sha256,
            "reference_hard_gate_report_sha256": self.reference_hard_gate_report_sha256,
            "relation": self.relation.value,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly validated comparison snapshot."""
        snapshot = ParetoComparisonReport._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return report semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def compare_pareto_evidence(
    objective: ResearchObjectiveContract,
    reference_report: SealedEvaluationEvidenceReport,
    candidate_report: SealedEvaluationEvidenceReport,
) -> ParetoComparisonReport:
    """Compare two exact sealed reports after mandatory hard-gate evaluation."""
    if type(objective) is not ResearchObjectiveContract:
        raise ParetoComparisonError("objective must be an exact ResearchObjectiveContract")
    if type(reference_report) is not SealedEvaluationEvidenceReport:
        raise ParetoComparisonError(
            "reference_report must be an exact SealedEvaluationEvidenceReport"
        )
    if type(candidate_report) is not SealedEvaluationEvidenceReport:
        raise ParetoComparisonError(
            "candidate_report must be an exact SealedEvaluationEvidenceReport"
        )

    try:
        objective.semantic_dict()
        objective_sha256 = objective.content_sha256
        reference_snapshot = _snapshot_sealed_report(reference_report)
        candidate_snapshot = _snapshot_sealed_report(candidate_report)
        reference_hard_gates = evaluate_hard_medical_non_regression(
            objective,
            reference_snapshot,
        )
        candidate_hard_gates = evaluate_hard_medical_non_regression(
            objective,
            candidate_snapshot,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ParetoComparisonError(
            "objective or sealed evidence failed hard-gate revalidation"
        ) from exc

    hard_relation = _hard_gate_relation(reference_hard_gates, candidate_hard_gates)
    if hard_relation is not None:
        return ParetoComparisonReport(
            objective_sha256=objective_sha256,
            reference_evidence_report_sha256=reference_snapshot.content_sha256,
            candidate_evidence_report_sha256=candidate_snapshot.content_sha256,
            reference_hard_gate_report_sha256=reference_hard_gates.content_sha256,
            candidate_hard_gate_report_sha256=candidate_hard_gates.content_sha256,
            relation=hard_relation,
            metrics=(),
        )

    metric_contracts = tuple(
        metric for metric in objective.evaluation_metrics if metric.tier is EvaluationTier.SEALED
    )
    if not metric_contracts:
        raise ParetoComparisonError("objective has no frozen Tier 3 metrics for Pareto comparison")

    reference_metrics = _global_metric_evidence(reference_snapshot)
    candidate_metrics = _global_metric_evidence(candidate_snapshot)
    metrics = tuple(
        _compare_metric(contract, reference_metrics, candidate_metrics)
        for contract in metric_contracts
    )
    return ParetoComparisonReport(
        objective_sha256=objective_sha256,
        reference_evidence_report_sha256=reference_snapshot.content_sha256,
        candidate_evidence_report_sha256=candidate_snapshot.content_sha256,
        reference_hard_gate_report_sha256=reference_hard_gates.content_sha256,
        candidate_hard_gate_report_sha256=candidate_hard_gates.content_sha256,
        relation=_pareto_relation(metrics),
        metrics=metrics,
    )


def _snapshot_sealed_report(
    report: SealedEvaluationEvidenceReport,
) -> SealedEvaluationEvidenceReport:
    if type(report) is not SealedEvaluationEvidenceReport:
        raise ParetoComparisonError(
            "sealed report must be an exact SealedEvaluationEvidenceReport"
        )
    if type(report.evaluator_artifacts) is not tuple:
        raise ParetoComparisonError("sealed evaluator_artifacts must remain an exact tuple")
    for item in report.evaluator_artifacts:
        if type(item) is not tuple or len(item) != 2:
            raise ParetoComparisonError("sealed evaluator_artifacts contains invalid entry")
    if type(report.metric_evidence) is not tuple:
        raise ParetoComparisonError("sealed metric_evidence must remain an exact tuple")
    if any(type(item) is not SealedMetricEvidence for item in report.metric_evidence):
        raise ParetoComparisonError("sealed metric_evidence contains invalid item type")

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
        raise ParetoComparisonError(
            "sealed evidence report failed canonical revalidation"
        ) from exc


def _hard_gate_relation(
    reference: HardMedicalNonRegressionReport,
    candidate: HardMedicalNonRegressionReport,
) -> ParetoRelation | None:
    reference_ok = reference.all_hard_gates_satisfied
    candidate_ok = candidate.all_hard_gates_satisfied
    if not reference_ok and not candidate_ok:
        return ParetoRelation.BOTH_REJECTED_HARD_GATE
    if not candidate_ok:
        return ParetoRelation.CANDIDATE_REJECTED_HARD_GATE
    if not reference_ok:
        return ParetoRelation.REFERENCE_REJECTED_HARD_GATE
    return None


def _global_metric_evidence(
    report: SealedEvaluationEvidenceReport,
) -> dict[str, SealedMetricEvidence]:
    values = {item.metric_id: item for item in report.metric_evidence if item.subgroup is None}
    if len(values) != sum(item.subgroup is None for item in report.metric_evidence):
        raise ParetoComparisonError("global metric evidence contains duplicate metric ids")
    return values


def _compare_metric(
    contract: MetricContract,
    reference: dict[str, SealedMetricEvidence],
    candidate: dict[str, SealedMetricEvidence],
) -> ParetoMetricComparison:
    reference_item = reference.get(contract.metric_id)
    candidate_item = candidate.get(contract.metric_id)
    if reference_item is None or candidate_item is None:
        raise ParetoComparisonError(
            f"missing global sealed evidence for metric {contract.metric_id!r}"
        )
    if (
        reference_item.evaluator_id != contract.evaluator_id
        or candidate_item.evaluator_id != contract.evaluator_id
    ):
        raise ParetoComparisonError(
            f"metric {contract.metric_id!r} does not bind the frozen evaluator"
        )
    relation = _metric_relation(
        contract.direction,
        reference_item.value_decimal,
        candidate_item.value_decimal,
    )
    return ParetoMetricComparison(
        metric_id=contract.metric_id,
        evaluator_id=contract.evaluator_id,
        direction=contract.direction,
        reference_value_decimal=reference_item.value_decimal,
        candidate_value_decimal=candidate_item.value_decimal,
        reference_evidence_artifact_sha256=reference_item.evidence_artifact_sha256,
        candidate_evidence_artifact_sha256=candidate_item.evidence_artifact_sha256,
        relation=relation,
    )


def _metric_relation(
    direction: MetricDirection,
    reference_value_decimal: str,
    candidate_value_decimal: str,
) -> MetricComparisonRelation:
    reference = _parse_decimal(reference_value_decimal, "reference_value_decimal")
    candidate = _parse_decimal(candidate_value_decimal, "candidate_value_decimal")
    if candidate == reference:
        return MetricComparisonRelation.EQUAL
    if direction is MetricDirection.MAXIMIZE:
        return (
            MetricComparisonRelation.BETTER
            if candidate > reference
            else MetricComparisonRelation.WORSE
        )
    if direction is MetricDirection.MINIMIZE:
        return (
            MetricComparisonRelation.BETTER
            if candidate < reference
            else MetricComparisonRelation.WORSE
        )
    raise ParetoComparisonError("unsupported metric direction")


def _pareto_relation(metrics: tuple[ParetoMetricComparison, ...]) -> ParetoRelation:
    has_better = any(metric.relation is MetricComparisonRelation.BETTER for metric in metrics)
    has_worse = any(metric.relation is MetricComparisonRelation.WORSE for metric in metrics)
    if not has_better and not has_worse:
        return ParetoRelation.EQUIVALENT
    if has_better and not has_worse:
        return ParetoRelation.CANDIDATE_DOMINATES
    if has_worse and not has_better:
        return ParetoRelation.REFERENCE_DOMINATES
    return ParetoRelation.TRADEOFF


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ParetoComparisonError(f"{label} must be canonical text")
    if any(character.isspace() for character in value):
        raise ParetoComparisonError(f"{label} cannot contain whitespace")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ParetoComparisonError(f"{label} must be 64 lowercase hex")


def _require_canonical_decimal(value: object, label: str) -> None:
    if type(value) is not str or _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise ParetoComparisonError(f"{label} must be canonical decimal text")
    _parse_decimal(value, label)


def _parse_decimal(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ParetoComparisonError(f"{label} must be a finite decimal") from exc
    if not parsed.is_finite():
        raise ParetoComparisonError(f"{label} must be a finite decimal")
    return parsed
