"""Immutable, content-addressed MRL V1 research experiment plan.

A plan narrows one canonical objective/hypothesis into a single bounded experiment
attempt. It freezes mutation scope, expected ExperimentManifest-compatible identities,
resource ceilings, evaluator/tier use, adaptive query/result exposure allowances, and
stop/failure conditions before execution. It is declarative only and grants no filesystem,
network, model, data, GPU, inference, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_hypothesis_v1 import (
    ResearchHypothesis,
    ResearchHypothesisError,
)
from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveInvalidationRule,
    AdaptiveStoppingRule,
    EvaluationTier,
    EvaluatorIdentity,
    ResearchObjectiveContract,
    ResearchObjectiveContractError,
    ResourceBudget,
    TierResultExposure,
)

__all__ = [
    "ExpectedDatasetBinding",
    "ExpectedExperimentManifestBinding",
    "ExpectedModelBinding",
    "PlanFailureCondition",
    "PlanStopCondition",
    "PlanTierAllowance",
    "ResearchExperimentPlan",
    "ResearchExperimentPlanError",
]

_PLAN_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EXPERIMENT_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_RQ_REF: Final = re.compile(r"^RQ[1-9][0-9]?$")
_SAFE_RESULT_ROOTS: Final[tuple[str, ...]] = (
    "experiments/",
    "research/experiments/",
    "tests/fixtures/mrl/",
)


class ResearchExperimentPlanError(ValueError):
    """Fail-closed validation error for one MRL research experiment plan."""


class PlanStopCondition(enum.Enum):
    """Canonical conditions that stop further work for this exact plan."""

    RESOURCE_CEILING_REACHED = "RESOURCE_CEILING_REACHED"
    ADAPTIVE_QUERY_ALLOWANCE_EXHAUSTED = "ADAPTIVE_QUERY_ALLOWANCE_EXHAUSTED"
    RESULT_EXPOSURE_ALLOWANCE_EXHAUSTED = "RESULT_EXPOSURE_ALLOWANCE_EXHAUSTED"
    EXTERNAL_GOVERNANCE_STOP = "EXTERNAL_GOVERNANCE_STOP"
    OBJECTIVE_INVALIDATED = "OBJECTIVE_INVALIDATED"
    EVALUATOR_IDENTITY_CHANGED = "EVALUATOR_IDENTITY_CHANGED"
    FAILURE_CONDITION_TRIGGERED = "FAILURE_CONDITION_TRIGGERED"


class PlanFailureCondition(enum.Enum):
    """Canonical fail-closed invalidation/failure conditions for one plan."""

    MUTATION_SCOPE_VIOLATION = "MUTATION_SCOPE_VIOLATION"
    MANIFEST_BINDING_MISMATCH = "MANIFEST_BINDING_MISMATCH"
    EVALUATOR_IDENTITY_MISMATCH = "EVALUATOR_IDENTITY_MISMATCH"
    RESOURCE_BUDGET_OVERRUN = "RESOURCE_BUDGET_OVERRUN"
    ADAPTIVE_QUERY_BUDGET_OVERRUN = "ADAPTIVE_QUERY_BUDGET_OVERRUN"
    RESULT_EXPOSURE_BUDGET_OVERRUN = "RESULT_EXPOSURE_BUDGET_OVERRUN"
    SEALED_BOUNDARY_BREACH = "SEALED_BOUNDARY_BREACH"
    CONTAMINATION_OR_LINEAGE_FAILURE = "CONTAMINATION_OR_LINEAGE_FAILURE"
    OBJECTIVE_SEMANTICS_CHANGED = "OBJECTIVE_SEMANTICS_CHANGED"
    EXECUTION_ERROR = "EXECUTION_ERROR"


_OBJECTIVE_STOP_CONDITION_MAP: Final[dict[AdaptiveStoppingRule, PlanStopCondition]] = {
    AdaptiveStoppingRule.ADAPTIVE_QUERY_BUDGET_EXHAUSTED: (
        PlanStopCondition.ADAPTIVE_QUERY_ALLOWANCE_EXHAUSTED
    ),
    AdaptiveStoppingRule.EXTERNAL_GOVERNANCE_STOP: (PlanStopCondition.EXTERNAL_GOVERNANCE_STOP),
    AdaptiveStoppingRule.OBJECTIVE_INVALIDATED: (PlanStopCondition.OBJECTIVE_INVALIDATED),
    AdaptiveStoppingRule.RESOURCE_BUDGET_EXHAUSTED: (PlanStopCondition.RESOURCE_CEILING_REACHED),
    AdaptiveStoppingRule.RESULT_EXPOSURE_BUDGET_EXHAUSTED: (
        PlanStopCondition.RESULT_EXPOSURE_ALLOWANCE_EXHAUSTED
    ),
}
_OBJECTIVE_FAILURE_CONDITION_MAP: Final[dict[AdaptiveInvalidationRule, PlanFailureCondition]] = {
    AdaptiveInvalidationRule.EVALUATOR_IDENTITY_CHANGED: (
        PlanFailureCondition.EVALUATOR_IDENTITY_MISMATCH
    ),
    AdaptiveInvalidationRule.LINEAGE_OR_CONTAMINATION_FAILURE: (
        PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE
    ),
    AdaptiveInvalidationRule.OBJECTIVE_SEMANTICS_CHANGED: (
        PlanFailureCondition.OBJECTIVE_SEMANTICS_CHANGED
    ),
    AdaptiveInvalidationRule.PROTECTED_SURFACE_MUTATION_ATTEMPT: (
        PlanFailureCondition.MUTATION_SCOPE_VIOLATION
    ),
    AdaptiveInvalidationRule.SEALED_BOUNDARY_BREACH: (PlanFailureCondition.SEALED_BOUNDARY_BREACH),
}


@dataclass(frozen=True, slots=True)
class ExpectedDatasetBinding:
    """Exact dataset identity expected in the later canonical ExperimentManifest."""

    name: str
    version: str
    content_sha256: str

    def __post_init__(self) -> None:
        _require_token(self.name, "dataset name")
        _require_text(self.version, "dataset version")
        _require_sha256(self.content_sha256, "dataset content_sha256")

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "version": self.version,
            "content_sha256": self.content_sha256,
        }


@dataclass(frozen=True, slots=True)
class ExpectedModelBinding:
    """Exact model identity expected in the later canonical ExperimentManifest."""

    model_id: str
    revision: str
    quantization: str
    backend: str

    def __post_init__(self) -> None:
        _require_text(self.model_id, "model_id")
        _require_text(self.revision, "model revision")
        _require_text(self.quantization, "model quantization")
        _require_text(self.backend, "model backend")

    def to_dict(self) -> dict[str, str]:
        return {
            "model_id": self.model_id,
            "revision": self.revision,
            "quantization": self.quantization,
            "backend": self.backend,
        }


@dataclass(frozen=True, slots=True)
class ExpectedExperimentManifestBinding:
    """Plan-time subset that MRL-0104 must bind to the existing ExperimentManifest."""

    experiment_id: str
    rq_refs: tuple[str, ...]
    configuration_sha256: str
    datasets: tuple[ExpectedDatasetBinding, ...]
    model: ExpectedModelBinding
    model_tier: int
    code_sha: str
    seeds: tuple[int, ...]
    results_paths: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_kebab_id(self.experiment_id, "experiment_id", pattern=_EXPERIMENT_ID)
        _require_rq_refs(self.rq_refs)
        _require_sha256(self.configuration_sha256, "configuration_sha256")
        _require_exact_instances(self.datasets, ExpectedDatasetBinding, "datasets")
        if not self.datasets:
            raise ResearchExperimentPlanError("expected manifest requires at least one dataset")
        dataset_keys = tuple((dataset.name, dataset.version) for dataset in self.datasets)
        if dataset_keys != tuple(sorted(set(dataset_keys))):
            raise ResearchExperimentPlanError(
                "expected manifest datasets must be unique and strictly sorted by name/version"
            )
        _require_exact_instance(self.model, ExpectedModelBinding, "model")
        _require_positive_int(self.model_tier, "model_tier")
        if self.model_tier not in (1, 2):
            raise ResearchExperimentPlanError("model_tier must be 1 or 2")
        _require_git_sha40(self.code_sha, "code_sha")
        _require_seed_plan(self.seeds)
        _require_result_paths(self.results_paths)

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment_id": self.experiment_id,
            "rq_refs": list(self.rq_refs),
            "configuration_sha256": self.configuration_sha256,
            "datasets": [dataset.to_dict() for dataset in self.datasets],
            "model": self.model.to_dict(),
            "model_tier": self.model_tier,
            "code_sha": self.code_sha,
            "seeds": list(self.seeds),
            "results_paths": list(self.results_paths),
        }


@dataclass(frozen=True, slots=True)
class PlanTierAllowance:
    """Per-run adaptive-query and result-exposure allowance for one evaluation tier."""

    tier: EvaluationTier
    max_queries: int
    max_result_exposures: int
    allowed_result_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_nonnegative_int(self.max_queries, "max_queries")
        _require_nonnegative_int(self.max_result_exposures, "max_result_exposures")
        _require_sorted_unique_text(
            self.allowed_result_fields,
            "allowed_result_fields",
            allow_empty=True,
        )
        if (
            self.tier not in (EvaluationTier.SEARCH, EvaluationTier.REPLICATION)
            and self.max_queries
        ):
            raise ResearchExperimentPlanError(
                "only Tier 1 SEARCH and Tier 2 REPLICATION may consume adaptive queries"
            )
        if self.tier in (
            EvaluationTier.SEALED,
            EvaluationTier.EXTERNAL_ASSURANCE,
        ) and (self.max_result_exposures or self.allowed_result_fields):
            raise ResearchExperimentPlanError(
                "Tier 3/4 cannot expose iterative agent-visible results"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": int(self.tier),
            "max_queries": self.max_queries,
            "max_result_exposures": self.max_result_exposures,
            "allowed_result_fields": list(self.allowed_result_fields),
        }


@dataclass(frozen=True, slots=True)
class ResearchExperimentPlan:
    """One frozen, content-addressed experiment plan bounded by a canonical objective."""

    experiment_plan_id: str
    objective: ResearchObjectiveContract = field(repr=False)
    hypothesis: ResearchHypothesis = field(repr=False)
    mutation_surfaces: tuple[str, ...]
    expected_manifest: ExpectedExperimentManifestBinding
    resource_ceiling: ResourceBudget
    evaluator_identities: tuple[EvaluatorIdentity, ...]
    evaluation_tiers: tuple[EvaluationTier, ...]
    tier_allowances: tuple[PlanTierAllowance, ...]
    stop_conditions: tuple[PlanStopCondition, ...]
    failure_conditions: tuple[PlanFailureCondition, ...]
    _bound_resource_ceiling: tuple[int | None, ...] = field(init=False, repr=False, compare=False)
    _bound_tier_allowances: tuple[tuple[int, int, int, tuple[str, ...]], ...] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        _validate_plan(self)
        object.__setattr__(
            self,
            "_bound_resource_ceiling",
            _resource_ceiling_freeze_binding(self.resource_ceiling),
        )
        object.__setattr__(
            self,
            "_bound_tier_allowances",
            _tier_allowance_freeze_binding(self.tier_allowances),
        )

    def _validated_snapshot(self) -> ResearchExperimentPlan:
        """Rebuild all mutable-reachable nested values before every public semantic view."""
        _require_exact_instance(
            self,
            ResearchExperimentPlan,
            "research_experiment_plan",
        )
        _require_original_plan_budget_bindings(self)
        objective = _snapshot_objective(self.objective)
        hypothesis = _snapshot_hypothesis(self.hypothesis)
        expected_manifest = _snapshot_expected_manifest(self.expected_manifest)
        resource_ceiling = _snapshot_resource_budget(self.resource_ceiling)
        evaluator_identities = tuple(
            _snapshot_evaluator_identity(identity) for identity in self.evaluator_identities
        )
        _require_exact_instances(
            self.tier_allowances,
            PlanTierAllowance,
            "tier_allowances",
        )
        tier_allowances = tuple(
            PlanTierAllowance(
                tier=allowance.tier,
                max_queries=allowance.max_queries,
                max_result_exposures=allowance.max_result_exposures,
                allowed_result_fields=allowance.allowed_result_fields,
            )
            for allowance in self.tier_allowances
        )
        return ResearchExperimentPlan(
            experiment_plan_id=self.experiment_plan_id,
            objective=objective,
            hypothesis=hypothesis,
            mutation_surfaces=self.mutation_surfaces,
            expected_manifest=expected_manifest,
            resource_ceiling=resource_ceiling,
            evaluator_identities=evaluator_identities,
            evaluation_tiers=self.evaluation_tiers,
            tier_allowances=tier_allowances,
            stop_conditions=self.stop_conditions,
            failure_conditions=self.failure_conditions,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-EXPERIMENT-PLAN-V1",
            "experiment_plan_id": self.experiment_plan_id,
            "objective_sha256": self.objective.content_sha256,
            "hypothesis_sha256": self.hypothesis.content_sha256,
            "mutation_surfaces": list(self.mutation_surfaces),
            "expected_manifest": self.expected_manifest.to_dict(),
            "resource_ceiling": self.resource_ceiling.to_dict(),
            "evaluator_identities": [identity.to_dict() for identity in self.evaluator_identities],
            "evaluation_tiers": [int(tier) for tier in self.evaluation_tiers],
            "tier_allowances": [allowance.to_dict() for allowance in self.tier_allowances],
            "stop_conditions": [condition.value for condition in self.stop_conditions],
            "failure_conditions": [condition.value for condition in self.failure_conditions],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete plan semantics from one freshly revalidated snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 semantic bytes without self-referential identity."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive the plan identity outside its semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived plan content identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _resource_ceiling_freeze_binding(value: ResourceBudget) -> tuple[int | None, ...]:
    _require_exact_instance(value, ResourceBudget, "resource_ceiling")
    return (
        value.wall_clock_seconds,
        value.compute_seconds,
        value.input_tokens,
        value.generated_tokens,
        value.storage_bytes,
        value.monetary_cost_microunits,
        value.max_experiments,
        value.retries,
        value.known_failure_retries,
        value.evaluator_invocations,
    )


def _tier_allowance_freeze_binding(
    values: tuple[PlanTierAllowance, ...],
) -> tuple[tuple[int, int, int, tuple[str, ...]], ...]:
    _require_exact_instances(values, PlanTierAllowance, "tier_allowances")
    return tuple(
        (
            int(value.tier),
            value.max_queries,
            value.max_result_exposures,
            value.allowed_result_fields,
        )
        for value in values
    )


def _require_original_plan_budget_bindings(plan: ResearchExperimentPlan) -> None:
    try:
        bound_resource_ceiling = plan._bound_resource_ceiling
        bound_tier_allowances = plan._bound_tier_allowances
    except AttributeError as exc:
        raise ResearchExperimentPlanError(
            "research experiment plan is missing its original frozen budget bindings"
        ) from exc

    if bound_resource_ceiling != _resource_ceiling_freeze_binding(plan.resource_ceiling):
        raise ResearchExperimentPlanError(
            "resource_ceiling changed after the research experiment plan was frozen"
        )
    if bound_tier_allowances != _tier_allowance_freeze_binding(plan.tier_allowances):
        raise ResearchExperimentPlanError(
            "tier_allowances changed after the research experiment plan was frozen"
        )


def _validate_plan(plan: ResearchExperimentPlan) -> None:
    _require_kebab_id(
        plan.experiment_plan_id,
        "experiment_plan_id",
        pattern=_PLAN_ID,
    )
    objective = _snapshot_objective(plan.objective)
    hypothesis = _snapshot_hypothesis(plan.hypothesis)
    objective_sha256 = objective.content_sha256
    if hypothesis.objective_sha256 != objective_sha256:
        raise ResearchExperimentPlanError(
            "hypothesis objective_sha256 does not bind the supplied canonical objective"
        )

    _require_sorted_unique_text(
        plan.mutation_surfaces,
        "mutation_surfaces",
        allow_empty=True,
    )
    for surface in plan.mutation_surfaces:
        _require_plan_mutation_surface(
            surface,
            objective.allowed_mutation_surfaces,
            objective.forbidden_mutation_surfaces,
        )

    expected_manifest = _snapshot_expected_manifest(plan.expected_manifest)
    if not set(expected_manifest.rq_refs).issubset(set(objective.research_program_refs)):
        raise ResearchExperimentPlanError(
            "expected manifest research-question refs must be within the objective envelope"
        )
    _require_result_destinations_outside_forbidden_surfaces(
        expected_manifest.results_paths,
        objective.forbidden_mutation_surfaces,
    )

    resource_ceiling = _snapshot_resource_budget(plan.resource_ceiling)
    if resource_ceiling.max_experiments != 1:
        raise ResearchExperimentPlanError(
            "one ResearchExperimentPlan must freeze exactly one experiment attempt"
        )
    _require_resource_subset(resource_ceiling, objective.resource_budget)

    _require_exact_instances(
        plan.evaluator_identities,
        EvaluatorIdentity,
        "evaluator_identities",
    )
    evaluator_ids = tuple(identity.evaluator_id for identity in plan.evaluator_identities)
    if not evaluator_ids:
        raise ResearchExperimentPlanError("evaluator_identities cannot be empty")
    if evaluator_ids != tuple(sorted(set(evaluator_ids))):
        raise ResearchExperimentPlanError(
            "evaluator_identities must be unique and strictly sorted by evaluator_id"
        )
    objective_evaluators = {
        identity.evaluator_id: identity for identity in objective.evaluator_identities
    }
    for identity in plan.evaluator_identities:
        matched = objective_evaluators.get(identity.evaluator_id)
        if matched is None or identity.to_dict() != matched.to_dict():
            raise ResearchExperimentPlanError(
                f"evaluator {identity.evaluator_id!r} does not exactly match the frozen objective"
            )

    _require_evaluation_tiers(plan.evaluation_tiers)
    objective_tiers = set(objective.evaluation_tier_policy.allowed_tiers)
    if not set(plan.evaluation_tiers).issubset(objective_tiers):
        raise ResearchExperimentPlanError(
            "plan evaluation tiers must be a subset of the frozen objective policy"
        )
    for tier in plan.evaluation_tiers:
        if not any(tier in identity.tiers for identity in plan.evaluator_identities):
            raise ResearchExperimentPlanError(
                f"plan tier {int(tier)} has no exact frozen evaluator identity"
            )

    _require_exact_instances(
        plan.tier_allowances,
        PlanTierAllowance,
        "tier_allowances",
    )
    allowance_tiers = tuple(allowance.tier for allowance in plan.tier_allowances)
    if allowance_tiers != plan.evaluation_tiers:
        raise ResearchExperimentPlanError(
            "tier_allowances must define exactly every plan evaluation tier in ascending order"
        )
    objective_exposure = {policy.tier: policy for policy in objective.tier_result_exposure_policy}
    for allowance in plan.tier_allowances:
        _require_tier_allowance_within_objective(
            allowance,
            objective,
            objective_exposure,
        )

    _require_sorted_unique_enum_members(
        plan.stop_conditions,
        PlanStopCondition,
        "stop_conditions",
    )
    _require_sorted_unique_enum_members(
        plan.failure_conditions,
        PlanFailureCondition,
        "failure_conditions",
    )
    if not plan.stop_conditions:
        raise ResearchExperimentPlanError("stop_conditions cannot be empty")
    if not plan.failure_conditions:
        raise ResearchExperimentPlanError("failure_conditions cannot be empty")
    _require_objective_control_conditions(plan, objective)


def _require_objective_control_conditions(
    plan: ResearchExperimentPlan,
    objective: ResearchObjectiveContract,
) -> None:
    controls = objective.adaptive_evaluation_controls
    try:
        required_stops = {_OBJECTIVE_STOP_CONDITION_MAP[rule] for rule in controls.stopping_rules}
        required_failures = {
            _OBJECTIVE_FAILURE_CONDITION_MAP[rule] for rule in controls.invalidation_rules
        }
    except KeyError as exc:
        raise ResearchExperimentPlanError(
            "objective contains an unsupported adaptive control rule"
        ) from exc

    missing_stops = tuple(
        sorted(condition.value for condition in required_stops.difference(plan.stop_conditions))
    )
    if missing_stops:
        raise ResearchExperimentPlanError(
            "stop_conditions omit frozen objective requirements: " + ", ".join(missing_stops)
        )

    missing_failures = tuple(
        sorted(
            condition.value for condition in required_failures.difference(plan.failure_conditions)
        )
    )
    if missing_failures:
        raise ResearchExperimentPlanError(
            "failure_conditions omit frozen objective requirements: " + ", ".join(missing_failures)
        )

    if (
        controls.invalidation_rules
        and PlanStopCondition.FAILURE_CONDITION_TRIGGERED not in plan.stop_conditions
    ):
        raise ResearchExperimentPlanError(
            "stop_conditions must include FAILURE_CONDITION_TRIGGERED when the frozen "
            "objective defines invalidation_rules"
        )


def _snapshot_objective(
    value: ResearchObjectiveContract,
) -> ResearchObjectiveContract:
    _require_exact_instance(value, ResearchObjectiveContract, "objective")
    try:
        return value._validated_snapshot()
    except ResearchObjectiveContractError as exc:
        raise ResearchExperimentPlanError("objective failed canonical revalidation") from exc


def _snapshot_hypothesis(value: ResearchHypothesis) -> ResearchHypothesis:
    _require_exact_instance(value, ResearchHypothesis, "hypothesis")
    try:
        return value._validated_snapshot()
    except ResearchHypothesisError as exc:
        raise ResearchExperimentPlanError("hypothesis failed canonical revalidation") from exc


def _snapshot_expected_manifest(
    value: ExpectedExperimentManifestBinding,
) -> ExpectedExperimentManifestBinding:
    _require_exact_instance(
        value,
        ExpectedExperimentManifestBinding,
        "expected_manifest",
    )
    _require_exact_instances(value.datasets, ExpectedDatasetBinding, "datasets")
    _require_exact_instance(value.model, ExpectedModelBinding, "model")
    return ExpectedExperimentManifestBinding(
        experiment_id=value.experiment_id,
        rq_refs=value.rq_refs,
        configuration_sha256=value.configuration_sha256,
        datasets=tuple(
            ExpectedDatasetBinding(
                name=dataset.name,
                version=dataset.version,
                content_sha256=dataset.content_sha256,
            )
            for dataset in value.datasets
        ),
        model=ExpectedModelBinding(
            model_id=value.model.model_id,
            revision=value.model.revision,
            quantization=value.model.quantization,
            backend=value.model.backend,
        ),
        model_tier=value.model_tier,
        code_sha=value.code_sha,
        seeds=value.seeds,
        results_paths=value.results_paths,
    )


def _snapshot_resource_budget(value: ResourceBudget) -> ResourceBudget:
    _require_exact_instance(value, ResourceBudget, "resource_ceiling")
    try:
        return ResourceBudget(
            wall_clock_seconds=value.wall_clock_seconds,
            compute_seconds=value.compute_seconds,
            input_tokens=value.input_tokens,
            generated_tokens=value.generated_tokens,
            storage_bytes=value.storage_bytes,
            monetary_cost_microunits=value.monetary_cost_microunits,
            max_experiments=value.max_experiments,
            retries=value.retries,
            known_failure_retries=value.known_failure_retries,
            evaluator_invocations=value.evaluator_invocations,
        )
    except ResearchObjectiveContractError as exc:
        raise ResearchExperimentPlanError("resource_ceiling failed canonical revalidation") from exc


def _snapshot_evaluator_identity(value: EvaluatorIdentity) -> EvaluatorIdentity:
    _require_exact_instance(value, EvaluatorIdentity, "evaluator_identity")
    try:
        return EvaluatorIdentity(
            evaluator_id=value.evaluator_id,
            artifact_sha256=value.artifact_sha256,
            tiers=value.tiers,
        )
    except ResearchObjectiveContractError as exc:
        raise ResearchExperimentPlanError(
            "evaluator identity failed canonical revalidation"
        ) from exc


def _require_resource_subset(
    plan: ResourceBudget,
    objective: ResourceBudget,
) -> None:
    fields = (
        "wall_clock_seconds",
        "compute_seconds",
        "input_tokens",
        "generated_tokens",
        "storage_bytes",
        "monetary_cost_microunits",
        "max_experiments",
        "retries",
        "known_failure_retries",
        "evaluator_invocations",
    )
    for name in fields:
        planned = getattr(plan, name)
        allowed = getattr(objective, name)
        if allowed is None:
            if planned is not None:
                raise ResearchExperimentPlanError(
                    f"resource_ceiling {name} is not applicable in the frozen objective"
                )
            continue
        if planned is None:
            raise ResearchExperimentPlanError(
                f"resource_ceiling {name} cannot be not applicable when the frozen "
                "objective defines a numeric ceiling"
            )
        if planned > allowed:
            raise ResearchExperimentPlanError(
                f"resource_ceiling {name} exceeds the frozen objective envelope"
            )


def _require_tier_allowance_within_objective(
    allowance: PlanTierAllowance,
    objective: ResearchObjectiveContract,
    exposure_by_tier: dict[EvaluationTier, TierResultExposure],
) -> None:
    if allowance.tier is EvaluationTier.SEARCH:
        max_queries = objective.adaptive_query_budget.tier_1_queries
    elif allowance.tier is EvaluationTier.REPLICATION:
        max_queries = objective.adaptive_query_budget.tier_2_queries
    else:
        max_queries = 0
    if allowance.max_queries > max_queries:
        raise ResearchExperimentPlanError(
            f"tier {int(allowance.tier)} query allowance exceeds the frozen objective"
        )

    exposure = exposure_by_tier.get(allowance.tier)
    if exposure is None:
        raise ResearchExperimentPlanError(
            f"tier {int(allowance.tier)} has no frozen objective exposure policy"
        )
    if allowance.max_result_exposures > exposure.max_exposures:
        raise ResearchExperimentPlanError(
            f"tier {int(allowance.tier)} result exposure exceeds the frozen objective"
        )
    if not set(allowance.allowed_result_fields).issubset(set(exposure.allowed_result_fields)):
        raise ResearchExperimentPlanError(
            f"tier {int(allowance.tier)} exposes result fields outside the frozen objective"
        )


def _require_plan_mutation_surface(
    surface: str,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    _require_canonical_relative_path(surface, "mutation_surfaces")
    if any(_paths_overlap(surface, blocked) for blocked in forbidden):
        raise ResearchExperimentPlanError(
            f"mutation surface {surface!r} overlaps a frozen forbidden surface"
        )
    for envelope in allowed:
        if _path_contains(envelope, surface):
            return
    raise ResearchExperimentPlanError(
        f"mutation surface {surface!r} is outside the frozen objective allow-list"
    )


def _require_result_destinations_outside_forbidden_surfaces(
    values: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    for value in values:
        if any(_paths_overlap(value, blocked) for blocked in forbidden):
            raise ResearchExperimentPlanError(
                f"result destination {value!r} overlaps a frozen forbidden surface"
            )


def _paths_overlap(left: str, right: str) -> bool:
    return _path_contains(left, right) or _path_contains(right, left)


def _path_contains(envelope: str, candidate: str) -> bool:
    return envelope == candidate or candidate.startswith(f"{envelope}/")


def _require_result_paths(values: tuple[str, ...]) -> None:
    _require_sorted_unique_text(values, "results_paths", allow_empty=False)
    for value in values:
        _require_canonical_relative_path(value, "results_paths")
        if not any(value.startswith(root) for root in _SAFE_RESULT_ROOTS):
            raise ResearchExperimentPlanError(
                f"result destination {value!r} is outside governed experiment roots"
            )


def _require_canonical_relative_path(value: str, label: str) -> None:
    _require_text(value, label)
    parts = value.split("/")
    if (
        value.startswith("/")
        or "\\" in value
        or "//" in value
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise ResearchExperimentPlanError(f"{label} contains non-canonical relative path {value!r}")


def _require_rq_refs(values: tuple[str, ...]) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError("rq_refs must be an exact tuple")
    if not values:
        raise ResearchExperimentPlanError("rq_refs cannot be empty")
    for value in values:
        _require_text(value, "rq_refs")
        if not _RQ_REF.fullmatch(value):
            raise ResearchExperimentPlanError("rq_refs must use canonical RQn references")
    if values != tuple(sorted(set(values))):
        raise ResearchExperimentPlanError("rq_refs must be unique and strictly sorted")


def _require_seed_plan(values: tuple[int, ...]) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError("seeds must be an exact tuple")
    if not values:
        raise ResearchExperimentPlanError("seeds cannot be empty")
    for value in values:
        _require_nonnegative_int(value, "seed")
    if values != tuple(sorted(set(values))):
        raise ResearchExperimentPlanError("seeds must be unique and strictly ascending")


def _require_evaluation_tiers(values: tuple[EvaluationTier, ...]) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError("evaluation_tiers must be an exact tuple")
    if not values:
        raise ResearchExperimentPlanError("evaluation_tiers cannot be empty")
    for value in values:
        _require_exact_enum(value, EvaluationTier, "evaluation_tiers")
    numeric = tuple(int(value) for value in values)
    if numeric != tuple(sorted(set(numeric))):
        raise ResearchExperimentPlanError("evaluation_tiers must be unique and strictly ascending")


def _require_sorted_unique_enum_members(
    values: tuple[enum.Enum, ...],
    enum_type: type[enum.Enum],
    label: str,
) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError(f"{label} must be an exact tuple")
    for value in values:
        if type(value) is not enum_type:
            raise ResearchExperimentPlanError(
                f"{label} members must be exact {enum_type.__name__} values"
            )
    names = tuple(value.value for value in values)
    if names != tuple(sorted(set(names))):
        raise ResearchExperimentPlanError(f"{label} must be unique and strictly sorted")


def _require_sorted_unique_text(
    values: tuple[str, ...],
    label: str,
    *,
    allow_empty: bool,
) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError(f"{label} must be an exact tuple")
    if not values and not allow_empty:
        raise ResearchExperimentPlanError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchExperimentPlanError(f"{label} must be unique and strictly sorted")


def _require_exact_instances(
    values: tuple[object, ...],
    expected: type[object],
    label: str,
) -> None:
    if type(values) is not tuple:
        raise ResearchExperimentPlanError(f"{label} must be an exact tuple")
    for value in values:
        _require_exact_instance(value, expected, label)


def _require_exact_instance(
    value: object,
    expected: type[object],
    label: str,
) -> None:
    if type(value) is not expected:
        raise ResearchExperimentPlanError(f"{label} must be an exact {expected.__name__} instance")


def _require_exact_enum(
    value: enum.Enum,
    expected: type[enum.Enum],
    label: str,
) -> None:
    if type(value) is not expected:
        raise ResearchExperimentPlanError(f"{label} must be an exact {expected.__name__} value")


def _require_kebab_id(
    value: str,
    label: str,
    *,
    pattern: re.Pattern[str],
) -> None:
    _require_text(value, label)
    if not pattern.fullmatch(value):
        raise ResearchExperimentPlanError(f"{label} must use lowercase kebab-case semantics")


def _require_token(value: str, label: str) -> None:
    _require_text(value, label)
    if not _TOKEN_ID.fullmatch(value):
        raise ResearchExperimentPlanError(f"{label} must be a canonical token")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchExperimentPlanError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise ResearchExperimentPlanError(f"{label} must be non-empty canonical text")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchExperimentPlanError(f"{label} must be 64 lowercase hex")


def _require_git_sha40(value: str, label: str) -> None:
    _require_text(value, label)
    if not _GIT_SHA40.fullmatch(value):
        raise ResearchExperimentPlanError(f"{label} must be an exact 40-character git SHA")


def _require_positive_int(value: int, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise ResearchExperimentPlanError(f"{label} must be a positive exact integer")


def _require_nonnegative_int(value: int, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ResearchExperimentPlanError(f"{label} must be a non-negative exact integer")
