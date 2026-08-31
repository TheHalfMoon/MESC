"""Independent sealed-evaluation evidence report for MESC Research Loop V1.

MRL-0305 records aggregate Tier 3 evidence produced behind the sealed boundary. The
report binds one frozen SEALED tier contract, its identity-only request, the opaque
handoff, and aggregate metric evidence. It never carries sealed item-level content or an
iterative agent-consumable result stream.

The report is evidence only. It cannot encode model promotion, deployment, release, or
clinical authority; ADR-0033 remains controlling for any later promotion decision.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier, MetricContract
from medscale.mesc._mrl_sealed_evaluation_interface_v1 import (
    SealedEvaluationHandoff,
    SealedEvaluationRequest,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract

__all__ = [
    "SealedEvaluationEvidenceError",
    "SealedEvaluationEvidenceReport",
    "SealedMetricEvidence",
    "build_sealed_evaluation_evidence_report",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_DECIMAL: Final = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")


class SealedEvaluationEvidenceError(ValueError):
    """Fail-closed validation error for independent Tier 3 evidence."""


def _make_metric_identity_registry() -> tuple[
    Callable[[SealedMetricEvidence, str], None],
    Callable[[SealedMetricEvidence], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: SealedMetricEvidence, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise SealedEvaluationEvidenceError(
                "sealed metric construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: SealedMetricEvidence) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise SealedEvaluationEvidenceError("sealed metric construction identity is missing")
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[SealedEvaluationEvidenceReport, str], None],
    Callable[[SealedEvaluationEvidenceReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: SealedEvaluationEvidenceReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise SealedEvaluationEvidenceError(
                "sealed evidence report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: SealedEvaluationEvidenceReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise SealedEvaluationEvidenceError(
                "sealed evidence report construction identity is missing"
            )
        return identity

    return store, load


_store_metric_identity, _load_metric_identity = _make_metric_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class SealedMetricEvidence:
    """One aggregate metric result with immutable evidence-artifact identity."""

    metric_id: str
    evaluator_id: str
    value_decimal: str
    evidence_artifact_sha256: str
    subgroup: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        _require_canonical_decimal(self.value_decimal, "value_decimal")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        if self.subgroup is not None:
            _require_text(self.subgroup, "subgroup")
        _store_metric_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> SealedMetricEvidence:
        if type(self) is not SealedMetricEvidence:
            raise SealedEvaluationEvidenceError(
                "metric evidence must be an exact SealedMetricEvidence"
            )
        bound_content_sha256 = _load_metric_identity(self)
        _require_sha256(bound_content_sha256, "bound metric content_sha256")
        snapshot = SealedMetricEvidence(
            metric_id=self.metric_id,
            evaluator_id=self.evaluator_id,
            value_decimal=self.value_decimal,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
            subgroup=self.subgroup,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise SealedEvaluationEvidenceError("sealed metric identity changed after construction")
        return snapshot

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "evaluator_id": self.evaluator_id,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "metric_id": self.metric_id,
            "subgroup": self.subgroup,
            "value_decimal": self.value_decimal,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated deterministic aggregate evidence semantics."""
        snapshot = SealedMetricEvidence._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class SealedEvaluationEvidenceReport:
    """Immutable evidence-only report for one independent Tier 3 evaluation."""

    objective_sha256: str
    tier_contract_sha256: str
    request_sha256: str
    handoff_sha256: str
    sealed_evidence_ref_sha256: str
    evaluator_artifacts: tuple[tuple[str, str], ...]
    metric_evidence: tuple[SealedMetricEvidence, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(self.tier_contract_sha256, "tier_contract_sha256")
        _require_sha256(self.request_sha256, "request_sha256")
        _require_sha256(self.handoff_sha256, "handoff_sha256")
        _require_sha256(self.sealed_evidence_ref_sha256, "sealed_evidence_ref_sha256")
        _require_evaluator_artifacts(self.evaluator_artifacts)
        _require_metric_evidence(self.metric_evidence)
        for item in self.metric_evidence:
            SealedMetricEvidence._validated_snapshot(item)
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> SealedEvaluationEvidenceReport:
        if type(self) is not SealedEvaluationEvidenceReport:
            raise SealedEvaluationEvidenceError(
                "report must be an exact SealedEvaluationEvidenceReport"
            )
        if type(self.evaluator_artifacts) is not tuple:
            raise SealedEvaluationEvidenceError("evaluator_artifacts must be a non-empty tuple")
        if type(self.metric_evidence) is not tuple:
            raise SealedEvaluationEvidenceError("metric_evidence must be a non-empty exact tuple")
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound report content_sha256")
        evaluator_artifacts = tuple(
            (evaluator_id, artifact_sha256)
            for evaluator_id, artifact_sha256 in self.evaluator_artifacts
        )
        metrics = tuple(
            SealedMetricEvidence._validated_snapshot(item) for item in self.metric_evidence
        )
        snapshot = SealedEvaluationEvidenceReport(
            objective_sha256=self.objective_sha256,
            tier_contract_sha256=self.tier_contract_sha256,
            request_sha256=self.request_sha256,
            handoff_sha256=self.handoff_sha256,
            sealed_evidence_ref_sha256=self.sealed_evidence_ref_sha256,
            evaluator_artifacts=evaluator_artifacts,
            metric_evidence=metrics,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise SealedEvaluationEvidenceError(
                "sealed evidence report identity changed after construction"
            )
        return snapshot

    @property
    def content_sha256(self) -> str:
        """Return identity derived from freshly revalidated report semantics."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic report bytes without authority amplification."""
        return canonical_semantic_bytes(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "adaptive_agent_visible": False,
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "evaluator_artifacts": [
                {"artifact_sha256": artifact_sha256, "evaluator_id": evaluator_id}
                for evaluator_id, artifact_sha256 in self.evaluator_artifacts
            ],
            "format": "MRL-SEALED-EVALUATION-EVIDENCE-V1",
            "handoff_sha256": self.handoff_sha256,
            "iterative_agent_result_stream": False,
            "metric_evidence": [item._to_dict_validated() for item in self.metric_evidence],
            "objective_sha256": self.objective_sha256,
            "request_sha256": self.request_sha256,
            "sealed_evidence_ref_sha256": self.sealed_evidence_ref_sha256,
            "sealed_item_level_content_included": False,
            "tier": int(EvaluationTier.SEALED),
            "tier_contract_sha256": self.tier_contract_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return freshly revalidated evidence-only semantics."""
        snapshot = SealedEvaluationEvidenceReport._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return report semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_sealed_evaluation_evidence_report(
    tier_contract: TierEvaluationContract,
    request: SealedEvaluationRequest,
    handoff: SealedEvaluationHandoff,
    metric_evidence: tuple[SealedMetricEvidence, ...],
) -> SealedEvaluationEvidenceReport:
    """Build one evidence report from an exact sealed request/handoff chain."""
    if type(tier_contract) is not TierEvaluationContract:
        raise SealedEvaluationEvidenceError("tier_contract must be an exact TierEvaluationContract")
    if tier_contract.tier is not EvaluationTier.SEALED:
        raise SealedEvaluationEvidenceError("evidence report requires Tier 3 SEALED")
    if type(request) is not SealedEvaluationRequest:
        raise SealedEvaluationEvidenceError("request must be an exact SealedEvaluationRequest")
    if type(handoff) is not SealedEvaluationHandoff:
        raise SealedEvaluationEvidenceError("handoff must be an exact SealedEvaluationHandoff")
    if type(metric_evidence) is not tuple:
        raise SealedEvaluationEvidenceError("metric_evidence must be an exact tuple")

    tier_contract.semantic_dict()
    try:
        request_snapshot = request._validated_snapshot()
        handoff_snapshot = handoff._validated_snapshot()
        metrics = tuple(SealedMetricEvidence._validated_snapshot(item) for item in metric_evidence)
    except (AttributeError, TypeError, ValueError) as exc:
        raise SealedEvaluationEvidenceError(
            "sealed request, handoff, or metric evidence failed canonical revalidation"
        ) from exc

    if request_snapshot.tier_contract_sha256 != tier_contract.content_sha256:
        raise SealedEvaluationEvidenceError("request does not match the sealed tier contract")
    if handoff_snapshot.request_sha256 != request_snapshot.content_sha256:
        raise SealedEvaluationEvidenceError("handoff does not match the sealed request")

    evaluator_artifacts = _sealed_evaluator_artifacts(tier_contract)
    expected_evaluator_ids = tuple(item[0] for item in evaluator_artifacts)
    if request_snapshot.evaluator_ids != expected_evaluator_ids:
        raise SealedEvaluationEvidenceError("request evaluator identities do not match objective")

    expected_metrics = _sealed_metric_contracts(tier_contract)
    _validate_metric_evidence(tier_contract, metrics, expected_metrics)

    return SealedEvaluationEvidenceReport(
        objective_sha256=tier_contract.objective.content_sha256,
        tier_contract_sha256=tier_contract.content_sha256,
        request_sha256=request_snapshot.content_sha256,
        handoff_sha256=handoff_snapshot.content_sha256,
        sealed_evidence_ref_sha256=handoff_snapshot.sealed_evidence_ref_sha256,
        evaluator_artifacts=evaluator_artifacts,
        metric_evidence=metrics,
    )


def _sealed_evaluator_artifacts(
    tier_contract: TierEvaluationContract,
) -> tuple[tuple[str, str], ...]:
    items = tuple(
        (identity.evaluator_id, identity.artifact_sha256)
        for identity in tier_contract.objective.evaluator_identities
        if EvaluationTier.SEALED in identity.tiers
    )
    if not items:
        raise SealedEvaluationEvidenceError("sealed objective has no evaluator identity")
    if items != tuple(sorted(set(items))):
        raise SealedEvaluationEvidenceError("sealed evaluator identities must be canonical")
    return items


def _sealed_metric_contracts(
    tier_contract: TierEvaluationContract,
) -> tuple[MetricContract, ...]:
    items = tuple(
        metric
        for metric in tier_contract.objective.evaluation_metrics
        if metric.tier is EvaluationTier.SEALED
    )
    if not items:
        raise SealedEvaluationEvidenceError("sealed objective has no evaluation metrics")
    return items


def _validate_metric_evidence(
    tier_contract: TierEvaluationContract,
    evidence: tuple[SealedMetricEvidence, ...],
    expected_metrics: tuple[MetricContract, ...],
) -> None:
    _require_metric_evidence(evidence)
    evaluator_by_metric = {metric.metric_id: metric.evaluator_id for metric in expected_metrics}
    expected: set[tuple[str, str, str | None]] = {
        (metric.metric_id, metric.evaluator_id, None) for metric in expected_metrics
    }
    for floor in tier_contract.objective.subgroup_floors:
        evaluator_id = evaluator_by_metric.get(floor.metric_id)
        if evaluator_id is None:
            raise SealedEvaluationEvidenceError("subgroup floor references no frozen Tier 3 metric")
        if floor.subgroup is None:
            raise SealedEvaluationEvidenceError("subgroup_floors must bind an explicit subgroup")
        expected.add((floor.metric_id, evaluator_id, floor.subgroup))

    observed = {(item.metric_id, item.evaluator_id, item.subgroup) for item in evidence}
    if observed != expected:
        raise SealedEvaluationEvidenceError(
            "metric_evidence must exactly cover frozen Tier 3 global and subgroup metrics"
        )


def _require_metric_evidence(values: tuple[SealedMetricEvidence, ...]) -> None:
    if type(values) is not tuple or not values:
        raise SealedEvaluationEvidenceError("metric_evidence must be a non-empty exact tuple")
    if any(type(value) is not SealedMetricEvidence for value in values):
        raise SealedEvaluationEvidenceError("metric_evidence contains an invalid item type")
    for value in values:
        SealedMetricEvidence._validated_snapshot(value)
    keys = tuple((value.metric_id, value.evaluator_id, value.subgroup or "") for value in values)
    if keys != tuple(sorted(set(keys))):
        raise SealedEvaluationEvidenceError("metric_evidence must be sorted and unique")


def _require_evaluator_artifacts(values: tuple[tuple[str, str], ...]) -> None:
    if type(values) is not tuple or not values:
        raise SealedEvaluationEvidenceError("evaluator_artifacts must be a non-empty tuple")
    for value in values:
        if type(value) is not tuple or len(value) != 2:
            raise SealedEvaluationEvidenceError("evaluator_artifacts contains invalid entry")
        evaluator_id, artifact_sha256 = value
        _require_token(evaluator_id, "evaluator_id")
        _require_sha256(artifact_sha256, "evaluator artifact_sha256")
    if values != tuple(sorted(set(values))):
        raise SealedEvaluationEvidenceError("evaluator_artifacts must be sorted and unique")


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise SealedEvaluationEvidenceError(f"{label} must be canonical text")
    if any(character.isspace() for character in value):
        raise SealedEvaluationEvidenceError(f"{label} cannot contain whitespace")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise SealedEvaluationEvidenceError(f"{label} must be canonical text")
    if "\n" in value or "\r" in value:
        raise SealedEvaluationEvidenceError(f"{label} must be one line")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SealedEvaluationEvidenceError(f"{label} must be 64 lowercase hex")


def _require_canonical_decimal(value: object, label: str) -> None:
    if type(value) is not str or _CANONICAL_DECIMAL.fullmatch(value) is None:
        raise SealedEvaluationEvidenceError(f"{label} must be canonical decimal text")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SealedEvaluationEvidenceError(f"{label} must be a finite decimal") from exc
    if not parsed.is_finite():
        raise SealedEvaluationEvidenceError(f"{label} must be a finite decimal")
