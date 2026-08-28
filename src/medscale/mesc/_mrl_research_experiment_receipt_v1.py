"""Immutable, content-addressed MRL V1 research experiment receipt.

The receipt binds one already-validated ``ExperimentManifestBinding`` to declarative
observations about the run: code/tree/patch identities, resource use, deterministic
metric artifacts, guardrail/subgroup outcomes, failure classification, lineage audit,
reproduction status, raw-output artifact identities, and exact evaluation-tier
accounting.

This module records evidence only. It performs no filesystem, Git, network, model,
dataset, GPU, inference, training, promotion, deployment, release, or clinical action
and grants no such authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Final, TypeVar, cast

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_experiment_manifest_binding_v1 import ExperimentManifestBinding
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    PlanFailureCondition,
    PlanTierAllowance,
    ResearchExperimentPlan,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    EvaluatorIdentity,
    EvidenceFloor,
    MetricContract,
    ResourceBudget,
)

__all__ = [
    "CodePatchIdentity",
    "ContaminationLineageAudit",
    "ContaminationLineageStatus",
    "EvidenceFloorResult",
    "MetricArtifactResult",
    "ObservedResourceUse",
    "ReproductionResult",
    "ReproductionStatus",
    "ResearchExperimentReceipt",
    "ResearchExperimentReceiptError",
    "TierAccounting",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")


class ResearchExperimentReceiptError(ValueError):
    """Fail-closed validation error for one MRL research experiment receipt."""


class ContaminationLineageStatus(enum.Enum):
    """Declarative status of the run's contamination/lineage audit."""

    NOT_EVALUATED = "NOT_EVALUATED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class ReproductionStatus(enum.Enum):
    """Declarative replay/reproduction status for the exact run artifacts."""

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    REPRODUCED = "REPRODUCED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class CodePatchIdentity:
    """Observed immutable code, Git-tree, and patch identities for the run."""

    code_sha: str
    tree_sha: str
    patch_sha256: str

    def __post_init__(self) -> None:
        _require_git_sha40(self.code_sha, "code_sha")
        _require_git_sha40(self.tree_sha, "tree_sha")
        _require_sha256(self.patch_sha256, "patch_sha256")

    def to_dict(self) -> dict[str, str]:
        return {
            "code_sha": self.code_sha,
            "tree_sha": self.tree_sha,
            "patch_sha256": self.patch_sha256,
        }


@dataclass(frozen=True, slots=True)
class ObservedResourceUse:
    """Observed resource accounting in the same integer units as ``ResourceBudget``."""

    wall_clock_seconds: int
    compute_seconds: int | None
    input_tokens: int | None
    generated_tokens: int | None
    storage_bytes: int
    monetary_cost_microunits: int | None
    retries: int
    known_failure_retries: int
    evaluator_invocations: int | None

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.wall_clock_seconds, "wall_clock_seconds")
        _require_optional_nonnegative_int(self.compute_seconds, "compute_seconds")
        _require_optional_nonnegative_int(self.input_tokens, "input_tokens")
        _require_optional_nonnegative_int(self.generated_tokens, "generated_tokens")
        _require_nonnegative_int(self.storage_bytes, "storage_bytes")
        _require_optional_nonnegative_int(
            self.monetary_cost_microunits,
            "monetary_cost_microunits",
        )
        _require_nonnegative_int(self.retries, "retries")
        _require_nonnegative_int(self.known_failure_retries, "known_failure_retries")
        _require_optional_nonnegative_int(
            self.evaluator_invocations,
            "evaluator_invocations",
        )
        if self.known_failure_retries > self.retries:
            raise ResearchExperimentReceiptError("known_failure_retries cannot exceed retries")

    def to_dict(self) -> dict[str, object]:
        return {
            "wall_clock_seconds": self.wall_clock_seconds,
            "compute_seconds": self.compute_seconds,
            "input_tokens": self.input_tokens,
            "generated_tokens": self.generated_tokens,
            "storage_bytes": self.storage_bytes,
            "monetary_cost_microunits": self.monetary_cost_microunits,
            "retries": self.retries,
            "known_failure_retries": self.known_failure_retries,
            "evaluator_invocations": self.evaluator_invocations,
        }


@dataclass(frozen=True, slots=True)
class MetricArtifactResult:
    """One deterministic metric artifact bound to its frozen evaluator and tier."""

    metric_id: str
    evaluator_id: str
    evaluator_artifact_sha256: str
    tier: EvaluationTier
    artifact_sha256: str

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        _require_sha256(
            self.evaluator_artifact_sha256,
            "evaluator_artifact_sha256",
        )
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_sha256(self.artifact_sha256, "artifact_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_artifact_sha256": self.evaluator_artifact_sha256,
            "tier": int(self.tier),
            "artifact_sha256": self.artifact_sha256,
        }


@dataclass(frozen=True, slots=True)
class EvidenceFloorResult:
    """Result for one frozen global guardrail or subgroup floor."""

    floor_id: str
    metric_artifact_sha256: str
    passed: bool

    def __post_init__(self) -> None:
        _require_token(self.floor_id, "floor_id")
        _require_sha256(
            self.metric_artifact_sha256,
            "metric_artifact_sha256",
        )
        if type(self.passed) is not bool:
            raise ResearchExperimentReceiptError("passed must be an exact bool")

    def to_dict(self) -> dict[str, object]:
        return {
            "floor_id": self.floor_id,
            "metric_artifact_sha256": self.metric_artifact_sha256,
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class ContaminationLineageAudit:
    """Identity-bearing contamination/lineage audit result, if one was performed."""

    status: ContaminationLineageStatus
    artifact_sha256: str | None

    def __post_init__(self) -> None:
        _require_exact_enum(
            self.status,
            ContaminationLineageStatus,
            "contamination lineage status",
        )
        if self.status is ContaminationLineageStatus.NOT_EVALUATED:
            if self.artifact_sha256 is not None:
                raise ResearchExperimentReceiptError(
                    "NOT_EVALUATED contamination audit cannot claim an artifact"
                )
            return
        if self.artifact_sha256 is None:
            raise ResearchExperimentReceiptError(
                "evaluated contamination audit requires artifact_sha256"
            )
        _require_sha256(self.artifact_sha256, "contamination audit artifact_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "artifact_sha256": self.artifact_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReproductionResult:
    """Identity-bearing replay/reproduction status, if replay was attempted."""

    status: ReproductionStatus
    artifact_sha256: str | None

    def __post_init__(self) -> None:
        _require_exact_enum(self.status, ReproductionStatus, "reproduction status")
        if self.status is ReproductionStatus.NOT_ATTEMPTED:
            if self.artifact_sha256 is not None:
                raise ResearchExperimentReceiptError(
                    "NOT_ATTEMPTED reproduction cannot claim an artifact"
                )
            return
        if self.artifact_sha256 is None:
            raise ResearchExperimentReceiptError("attempted reproduction requires artifact_sha256")
        _require_sha256(self.artifact_sha256, "reproduction artifact_sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "artifact_sha256": self.artifact_sha256,
        }


@dataclass(frozen=True, slots=True)
class TierAccounting:
    """Exact adaptive-query/result-exposure accounting for one plan tier."""

    tier: EvaluationTier
    queries_used: int
    result_exposures_used: int
    exposed_result_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(
            self.result_exposures_used,
            "result_exposures_used",
        )
        _require_sorted_unique_tokens(
            self.exposed_result_fields,
            "exposed_result_fields",
            allow_empty=True,
        )
        if self.result_exposures_used == 0 and self.exposed_result_fields:
            raise ResearchExperimentReceiptError(
                "zero result exposures cannot claim exposed result fields"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": int(self.tier),
            "queries_used": self.queries_used,
            "result_exposures_used": self.result_exposures_used,
            "exposed_result_fields": list(self.exposed_result_fields),
        }


@dataclass(frozen=True, slots=True)
class ResearchExperimentReceipt:
    """Content-addressed scientific receipt for one exact plan/manifest binding."""

    binding: ExperimentManifestBinding = field(repr=False)
    code_identity: CodePatchIdentity
    observed_resource_use: ObservedResourceUse
    metric_artifacts: tuple[MetricArtifactResult, ...]
    guardrail_results: tuple[EvidenceFloorResult, ...]
    subgroup_results: tuple[EvidenceFloorResult, ...]
    failure_classification: PlanFailureCondition | None
    contamination_lineage_audit: ContaminationLineageAudit
    reproduction: ReproductionResult
    raw_output_artifact_sha256s: tuple[str, ...]
    tier_accounting: tuple[TierAccounting, ...]

    def __post_init__(self) -> None:
        _validate_receipt(self)

    def _validated_snapshot(self) -> ResearchExperimentReceipt:
        """Rebuild all reachable nested values before every trust-bearing view."""
        _require_exact_instance(
            self,
            ResearchExperimentReceipt,
            "research_experiment_receipt",
        )
        return ResearchExperimentReceipt(
            binding=_snapshot_binding(self.binding),
            code_identity=_snapshot_code_identity(self.code_identity),
            observed_resource_use=_snapshot_resource_use(self.observed_resource_use),
            metric_artifacts=tuple(
                _snapshot_metric_artifact(result)
                for result in _require_exact_tuple_items(
                    self.metric_artifacts,
                    MetricArtifactResult,
                    "metric_artifacts",
                )
            ),
            guardrail_results=tuple(
                _snapshot_floor_result(result)
                for result in _require_exact_tuple_items(
                    self.guardrail_results,
                    EvidenceFloorResult,
                    "guardrail_results",
                )
            ),
            subgroup_results=tuple(
                _snapshot_floor_result(result)
                for result in _require_exact_tuple_items(
                    self.subgroup_results,
                    EvidenceFloorResult,
                    "subgroup_results",
                )
            ),
            failure_classification=self.failure_classification,
            contamination_lineage_audit=_snapshot_contamination_audit(
                self.contamination_lineage_audit
            ),
            reproduction=_snapshot_reproduction(self.reproduction),
            raw_output_artifact_sha256s=self.raw_output_artifact_sha256s,
            tier_accounting=tuple(
                _snapshot_tier_accounting(result)
                for result in _require_exact_tuple_items(
                    self.tier_accounting,
                    TierAccounting,
                    "tier_accounting",
                )
            ),
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        binding_semantics = self.binding.semantic_dict()
        return {
            "format": "MRL-RESEARCH-EXPERIMENT-RECEIPT-V1",
            "experiment_plan_sha256": binding_semantics["experiment_plan_sha256"],
            "experiment_manifest_sha256": binding_semantics["experiment_manifest_sha256"],
            "code_identity": self.code_identity.to_dict(),
            "observed_resource_use": self.observed_resource_use.to_dict(),
            "metric_artifacts": [result.to_dict() for result in self.metric_artifacts],
            "guardrail_results": [result.to_dict() for result in self.guardrail_results],
            "subgroup_results": [result.to_dict() for result in self.subgroup_results],
            "failure_classification": (
                None
                if self.failure_classification is None
                else self.failure_classification.value
            ),
            "contamination_lineage_audit": self.contamination_lineage_audit.to_dict(),
            "reproduction": self.reproduction.to_dict(),
            "raw_output_artifact_sha256s": list(self.raw_output_artifact_sha256s),
            "tier_accounting": [accounting.to_dict() for accounting in self.tier_accounting],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return one freshly revalidated canonical semantic payload."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical semantic bytes without self-referential identity."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive receipt identity outside its own semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived receipt identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _validate_receipt(receipt: ResearchExperimentReceipt) -> None:
    binding = _snapshot_binding(receipt.binding)
    plan = binding.plan

    code_identity = _snapshot_code_identity(receipt.code_identity)
    if code_identity.code_sha != binding.manifest.code_sha:
        raise ResearchExperimentReceiptError(
            "receipt code_sha does not match the bound ExperimentManifest"
        )
    if code_identity.code_sha != plan.expected_manifest.code_sha:
        raise ResearchExperimentReceiptError(
            "receipt code_sha does not match the frozen ResearchExperimentPlan"
        )

    resource_use = _snapshot_resource_use(receipt.observed_resource_use)
    resource_overrun = _resource_overrun_fields(
        resource_use,
        plan.resource_ceiling,
    )

    _require_failure_classification(
        receipt.failure_classification,
        plan,
    )

    metrics = tuple(
        _snapshot_metric_artifact(result)
        for result in _require_exact_tuple_items(
            receipt.metric_artifacts,
            MetricArtifactResult,
            "metric_artifacts",
        )
    )
    _require_strictly_sorted_ids(
        tuple(result.metric_id for result in metrics),
        "metric_artifacts",
    )
    expected_metrics = _applicable_metric_contracts(plan)
    expected_metric_ids = set(expected_metrics)
    actual_metric_ids = {result.metric_id for result in metrics}
    if receipt.failure_classification is None:
        if actual_metric_ids != expected_metric_ids:
            raise ResearchExperimentReceiptError(
                "successful receipt must bind exactly every metric for its plan tiers"
            )
    elif not actual_metric_ids.issubset(expected_metric_ids):
        raise ResearchExperimentReceiptError(
            "failed receipt contains a metric outside its frozen plan tiers"
        )

    evaluator_by_id = {identity.evaluator_id: identity for identity in plan.evaluator_identities}
    metric_by_id = {result.metric_id: result for result in metrics}
    for result in metrics:
        contract = expected_metrics[result.metric_id]
        _require_metric_binding(result, contract, evaluator_by_id)

    guardrails = tuple(
        _snapshot_floor_result(result)
        for result in _require_exact_tuple_items(
            receipt.guardrail_results,
            EvidenceFloorResult,
            "guardrail_results",
        )
    )
    subgroups = tuple(
        _snapshot_floor_result(result)
        for result in _require_exact_tuple_items(
            receipt.subgroup_results,
            EvidenceFloorResult,
            "subgroup_results",
        )
    )
    _require_floor_results(
        name="guardrail_results",
        results=guardrails,
        floors=plan.objective.hard_guardrails,
        metric_by_id=metric_by_id,
        complete=receipt.failure_classification is None,
    )
    _require_floor_results(
        name="subgroup_results",
        results=subgroups,
        floors=plan.objective.subgroup_floors,
        metric_by_id=metric_by_id,
        complete=receipt.failure_classification is None,
    )

    contamination = _snapshot_contamination_audit(receipt.contamination_lineage_audit)
    if (
        receipt.failure_classification
        is PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE
    ) != (contamination.status is ContaminationLineageStatus.FAILED):
        raise ResearchExperimentReceiptError(
            "contamination failure classification and audit status must agree"
        )

    _snapshot_reproduction(receipt.reproduction)
    _require_sorted_unique_sha256s(
        receipt.raw_output_artifact_sha256s,
        "raw_output_artifact_sha256s",
    )

    accounting = tuple(
        _snapshot_tier_accounting(result)
        for result in _require_exact_tuple_items(
            receipt.tier_accounting,
            TierAccounting,
            "tier_accounting",
        )
    )
    accounting_overruns = _require_tier_accounting(accounting, plan)

    _require_overrun_classification(
        failure=receipt.failure_classification,
        resource_overrun=resource_overrun,
        accounting_overruns=accounting_overruns,
    )


def _snapshot_binding(value: ExperimentManifestBinding) -> ExperimentManifestBinding:
    _require_exact_instance(value, ExperimentManifestBinding, "binding")
    try:
        return value._validated_snapshot()
    except (AttributeError, TypeError, ValueError) as exc:
        raise ResearchExperimentReceiptError("binding failed canonical revalidation") from exc


def _snapshot_code_identity(value: CodePatchIdentity) -> CodePatchIdentity:
    _require_exact_instance(value, CodePatchIdentity, "code_identity")
    return CodePatchIdentity(
        code_sha=value.code_sha,
        tree_sha=value.tree_sha,
        patch_sha256=value.patch_sha256,
    )


def _snapshot_resource_use(value: ObservedResourceUse) -> ObservedResourceUse:
    _require_exact_instance(
        value,
        ObservedResourceUse,
        "observed_resource_use",
    )
    return ObservedResourceUse(
        wall_clock_seconds=value.wall_clock_seconds,
        compute_seconds=value.compute_seconds,
        input_tokens=value.input_tokens,
        generated_tokens=value.generated_tokens,
        storage_bytes=value.storage_bytes,
        monetary_cost_microunits=value.monetary_cost_microunits,
        retries=value.retries,
        known_failure_retries=value.known_failure_retries,
        evaluator_invocations=value.evaluator_invocations,
    )


def _snapshot_metric_artifact(
    value: MetricArtifactResult,
) -> MetricArtifactResult:
    _require_exact_instance(value, MetricArtifactResult, "metric artifact")
    return MetricArtifactResult(
        metric_id=value.metric_id,
        evaluator_id=value.evaluator_id,
        evaluator_artifact_sha256=value.evaluator_artifact_sha256,
        tier=value.tier,
        artifact_sha256=value.artifact_sha256,
    )


def _snapshot_floor_result(value: EvidenceFloorResult) -> EvidenceFloorResult:
    _require_exact_instance(value, EvidenceFloorResult, "evidence floor result")
    return EvidenceFloorResult(
        floor_id=value.floor_id,
        metric_artifact_sha256=value.metric_artifact_sha256,
        passed=value.passed,
    )


def _snapshot_contamination_audit(
    value: ContaminationLineageAudit,
) -> ContaminationLineageAudit:
    _require_exact_instance(
        value,
        ContaminationLineageAudit,
        "contamination_lineage_audit",
    )
    return ContaminationLineageAudit(
        status=value.status,
        artifact_sha256=value.artifact_sha256,
    )


def _snapshot_reproduction(value: ReproductionResult) -> ReproductionResult:
    _require_exact_instance(value, ReproductionResult, "reproduction")
    return ReproductionResult(
        status=value.status,
        artifact_sha256=value.artifact_sha256,
    )


def _snapshot_tier_accounting(value: TierAccounting) -> TierAccounting:
    _require_exact_instance(value, TierAccounting, "tier accounting")
    return TierAccounting(
        tier=value.tier,
        queries_used=value.queries_used,
        result_exposures_used=value.result_exposures_used,
        exposed_result_fields=value.exposed_result_fields,
    )


def _applicable_metric_contracts(
    plan: ResearchExperimentPlan,
) -> dict[str, MetricContract]:
    tiers = set(plan.evaluation_tiers)
    contracts = tuple(plan.objective.search_metrics) + tuple(plan.objective.evaluation_metrics)
    return {contract.metric_id: contract for contract in contracts if contract.tier in tiers}


def _require_metric_binding(
    result: MetricArtifactResult,
    contract: MetricContract,
    evaluator_by_id: dict[str, EvaluatorIdentity],
) -> None:
    if result.evaluator_id != contract.evaluator_id:
        raise ResearchExperimentReceiptError(
            f"metric {result.metric_id!r} evaluator_id does not match the frozen contract"
        )
    if result.tier is not contract.tier:
        raise ResearchExperimentReceiptError(
            f"metric {result.metric_id!r} tier does not match the frozen contract"
        )
    evaluator = evaluator_by_id.get(result.evaluator_id)
    if evaluator is None:
        raise ResearchExperimentReceiptError(
            f"metric {result.metric_id!r} evaluator is not frozen in the plan"
        )
    if result.evaluator_artifact_sha256 != evaluator.artifact_sha256:
        raise ResearchExperimentReceiptError(
            f"metric {result.metric_id!r} evaluator artifact identity does not match the plan"
        )
    if result.tier not in evaluator.tiers:
        raise ResearchExperimentReceiptError(
            f"metric {result.metric_id!r} tier is not admitted by its evaluator identity"
        )


def _require_floor_results(
    *,
    name: str,
    results: tuple[EvidenceFloorResult, ...],
    floors: tuple[EvidenceFloor, ...],
    metric_by_id: dict[str, MetricArtifactResult],
    complete: bool,
) -> None:
    result_ids = tuple(result.floor_id for result in results)
    _require_strictly_sorted_ids(result_ids, name)
    floor_by_id = {floor.floor_id: floor for floor in floors if floor.metric_id in metric_by_id}
    actual_ids = set(result_ids)
    expected_ids = set(floor_by_id)
    if complete:
        if actual_ids != expected_ids:
            raise ResearchExperimentReceiptError(
                f"successful receipt must bind exactly every applicable {name}"
            )
    elif not actual_ids.issubset(expected_ids):
        raise ResearchExperimentReceiptError(
            f"failed receipt contains {name} outside available metric artifacts"
        )
    for result in results:
        floor = floor_by_id[result.floor_id]
        metric = metric_by_id[floor.metric_id]
        if result.metric_artifact_sha256 != metric.artifact_sha256:
            raise ResearchExperimentReceiptError(
                f"{name} {result.floor_id!r} does not bind its metric artifact"
            )


def _resource_overrun_fields(
    usage: ObservedResourceUse,
    ceiling: ResourceBudget,
) -> tuple[str, ...]:
    pairs = (
        ("wall_clock_seconds", usage.wall_clock_seconds, ceiling.wall_clock_seconds),
        ("compute_seconds", usage.compute_seconds, ceiling.compute_seconds),
        ("input_tokens", usage.input_tokens, ceiling.input_tokens),
        ("generated_tokens", usage.generated_tokens, ceiling.generated_tokens),
        ("storage_bytes", usage.storage_bytes, ceiling.storage_bytes),
        (
            "monetary_cost_microunits",
            usage.monetary_cost_microunits,
            ceiling.monetary_cost_microunits,
        ),
        ("retries", usage.retries, ceiling.retries),
        (
            "known_failure_retries",
            usage.known_failure_retries,
            ceiling.known_failure_retries,
        ),
        (
            "evaluator_invocations",
            usage.evaluator_invocations,
            ceiling.evaluator_invocations,
        ),
    )
    overruns: list[str] = []
    for name, observed, allowed in pairs:
        if allowed is None:
            if observed is not None:
                raise ResearchExperimentReceiptError(
                    f"observed resource {name} must be None when not applicable in the plan"
                )
            continue
        if observed is None:
            raise ResearchExperimentReceiptError(
                f"observed resource {name} cannot be None when bounded by the plan"
            )
        if observed > allowed:
            overruns.append(name)
    return tuple(overruns)


def _require_failure_classification(
    value: PlanFailureCondition | None,
    plan: ResearchExperimentPlan,
) -> None:
    if value is None:
        return
    _require_exact_enum(
        value,
        PlanFailureCondition,
        "failure_classification",
    )
    if value not in plan.failure_conditions:
        raise ResearchExperimentReceiptError(
            "failure_classification is not frozen in the ResearchExperimentPlan"
        )


def _require_tier_accounting(
    accounting: tuple[TierAccounting, ...],
    plan: ResearchExperimentPlan,
) -> tuple[PlanFailureCondition, ...]:
    tiers = tuple(item.tier for item in accounting)
    if tiers != plan.evaluation_tiers:
        raise ResearchExperimentReceiptError(
            "tier_accounting must define exactly every plan tier in ascending order"
        )
    allowance_by_tier: dict[EvaluationTier, PlanTierAllowance] = {
        allowance.tier: allowance for allowance in plan.tier_allowances
    }
    overruns: list[PlanFailureCondition] = []
    for item in accounting:
        allowance = allowance_by_tier[item.tier]
        if item.queries_used > allowance.max_queries:
            overruns.append(PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN)
        if item.result_exposures_used > allowance.max_result_exposures:
            overruns.append(PlanFailureCondition.RESULT_EXPOSURE_BUDGET_OVERRUN)
        if not set(item.exposed_result_fields).issubset(set(allowance.allowed_result_fields)):
            raise ResearchExperimentReceiptError(
                f"tier {int(item.tier)} exposes a result field outside the frozen allowance"
            )
    return tuple(sorted(set(overruns), key=lambda condition: condition.value))


def _require_overrun_classification(
    *,
    failure: PlanFailureCondition | None,
    resource_overrun: tuple[str, ...],
    accounting_overruns: tuple[PlanFailureCondition, ...],
) -> None:
    violations: list[PlanFailureCondition] = list(accounting_overruns)
    if resource_overrun:
        violations.append(PlanFailureCondition.RESOURCE_BUDGET_OVERRUN)
    unique = tuple(sorted(set(violations), key=lambda condition: condition.value))
    if not unique:
        if failure in (
            PlanFailureCondition.RESOURCE_BUDGET_OVERRUN,
            PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN,
            PlanFailureCondition.RESULT_EXPOSURE_BUDGET_OVERRUN,
        ):
            raise ResearchExperimentReceiptError(
                "overrun failure_classification requires matching observed accounting"
            )
        return
    if failure not in unique:
        names = ", ".join(condition.value for condition in unique)
        raise ResearchExperimentReceiptError(
            "observed accounting overrun must have one matching failure classification: "
            + names
        )


def _require_exact_instance(
    value: object,
    expected_type: type[object],
    name: str,
) -> None:
    if type(value) is not expected_type:
        raise ResearchExperimentReceiptError(
            f"{name} must be exact {expected_type.__name__}; subclasses/type substitution rejected"
        )


def _require_exact_enum(value: object, expected_type: type[enum.Enum], name: str) -> None:
    if type(value) is not expected_type:
        raise ResearchExperimentReceiptError(f"{name} must be exact {expected_type.__name__}")


_T = TypeVar("_T")


def _require_exact_tuple_items(
    value: object,
    item_type: type[_T],
    name: str,
) -> tuple[_T, ...]:
    if type(value) is not tuple:
        raise ResearchExperimentReceiptError(f"{name} must be an exact tuple")
    items = cast(tuple[object, ...], value)
    if any(type(item) is not item_type for item in items):
        raise ResearchExperimentReceiptError(f"{name} contains invalid item types")
    return cast(tuple[_T, ...], items)


def _require_token(value: object, name: str) -> None:
    if type(value) is not str or not value:
        raise ResearchExperimentReceiptError(f"{name} must be an exact non-empty string")
    if any(character.isspace() for character in value):
        raise ResearchExperimentReceiptError(f"{name} cannot contain whitespace")


def _require_sha256(value: object, name: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ResearchExperimentReceiptError(f"{name} must be an exact lowercase 64-hex SHA-256")


def _require_git_sha40(value: object, name: str) -> None:
    if type(value) is not str or _GIT_SHA40.fullmatch(value) is None:
        raise ResearchExperimentReceiptError(
            f"{name} must be an exact lowercase 40-hex Git identity"
        )


def _require_nonnegative_int(value: object, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ResearchExperimentReceiptError(f"{name} must be an exact non-negative integer")


def _require_optional_nonnegative_int(value: object, name: str) -> None:
    if value is None:
        return
    _require_nonnegative_int(value, name)


def _require_strictly_sorted_ids(values: tuple[str, ...], name: str) -> None:
    if values != tuple(sorted(set(values))):
        raise ResearchExperimentReceiptError(f"{name} must be unique and strictly sorted by id")


def _require_sorted_unique_tokens(
    value: object,
    name: str,
    *,
    allow_empty: bool,
) -> None:
    if type(value) is not tuple:
        raise ResearchExperimentReceiptError(f"{name} must be an exact tuple")
    items = value
    if not allow_empty and not items:
        raise ResearchExperimentReceiptError(f"{name} cannot be empty")
    for item in items:
        _require_token(item, f"{name} item")
    if items != tuple(sorted(set(items))):
        raise ResearchExperimentReceiptError(f"{name} must be unique and strictly sorted")


def _require_sorted_unique_sha256s(value: object, name: str) -> None:
    if type(value) is not tuple:
        raise ResearchExperimentReceiptError(f"{name} must be an exact tuple")
    for item in value:
        _require_sha256(item, f"{name} item")
    if value != tuple(sorted(set(value))):
        raise ResearchExperimentReceiptError(f"{name} must be unique and strictly sorted")
