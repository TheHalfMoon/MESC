"""Bounded Tier 1 result exposure for MESC Research Loop V1.

MRL-0302 enforces the query and result-exposure ceilings already frozen in a
``TierEvaluationContract`` for Tier 1 SEARCH. It is pure, deterministic, and grants
no execution, budget-expansion, training, promotion, deployment, or clinical authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._mrl_research_objective_v1 import EvaluationTier, TierResultExposure
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract

__all__ = [
    "Tier1ExposureError",
    "Tier1ExposurePolicy",
    "Tier1ExposureUsage",
    "consume_tier1_query",
    "record_tier1_exposure",
]


class Tier1ExposureError(ValueError):
    """Fail-closed error for bounded Tier 1 adaptive-result exposure."""


@dataclass(frozen=True, slots=True)
class Tier1ExposureUsage:
    """Immutable usage counters for one frozen Tier 1 policy."""

    queries_used: int = 0
    exposures_used: int = 0

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(self.exposures_used, "exposures_used")


@dataclass(frozen=True, slots=True)
class Tier1ExposurePolicy:
    """Exact Tier 1 ceilings and aggregate fields derived from a frozen objective."""

    tier_contract: TierEvaluationContract

    def __post_init__(self) -> None:
        if type(self.tier_contract) is not TierEvaluationContract:
            raise Tier1ExposureError("tier_contract must be an exact TierEvaluationContract")
        if self.tier_contract.tier is not EvaluationTier.SEARCH:
            raise Tier1ExposureError("Tier 1 exposure policy requires SEARCH tier")
        self.tier_contract.semantic_dict()

    @property
    def query_ceiling(self) -> int:
        """Return the frozen Tier 1 adaptive-query ceiling."""
        return self.tier_contract.objective.adaptive_query_budget.tier_1_queries

    @property
    def exposure_contract(self) -> TierResultExposure:
        """Return a fresh immutable snapshot of the frozen Tier 1 exposure contract."""
        matches = [
            policy
            for policy in self.tier_contract.objective.tier_result_exposure_policy
            if policy.tier is EvaluationTier.SEARCH
        ]
        if len(matches) != 1:
            raise Tier1ExposureError("objective must define exactly one SEARCH exposure policy")
        policy = matches[0]
        return TierResultExposure(
            tier=policy.tier,
            max_exposures=policy.max_exposures,
            allowed_result_fields=policy.allowed_result_fields,
        )

    @property
    def max_exposures(self) -> int:
        """Return the frozen Tier 1 result-exposure ceiling."""
        return self.exposure_contract.max_exposures

    @property
    def allowed_result_fields(self) -> tuple[str, ...]:
        """Return the exact aggregate result fields visible to adaptive search."""
        return self.exposure_contract.allowed_result_fields

    @property
    def can_expand_budget(self) -> bool:
        """Tier 1 policy can never expand its own frozen budget."""
        return False

    def to_dict(self) -> dict[str, object]:
        """Return deterministic policy semantics without authority amplification."""
        return {
            "allowed_result_fields": list(self.allowed_result_fields),
            "can_authorize": False,
            "can_expand_budget": False,
            "max_exposures": self.max_exposures,
            "query_ceiling": self.query_ceiling,
            "tier": int(EvaluationTier.SEARCH),
            "tier_contract_sha256": self.tier_contract.content_sha256,
        }


def consume_tier1_query(
    policy: Tier1ExposurePolicy,
    usage: Tier1ExposureUsage,
) -> Tier1ExposureUsage:
    """Consume one adaptive Tier 1 query or fail closed at the frozen ceiling."""
    _validate_policy_and_usage(policy, usage)
    if usage.queries_used >= policy.query_ceiling:
        raise Tier1ExposureError("Tier 1 adaptive-query budget is exhausted")
    return Tier1ExposureUsage(
        queries_used=usage.queries_used + 1,
        exposures_used=usage.exposures_used,
    )


def record_tier1_exposure(
    policy: Tier1ExposurePolicy,
    usage: Tier1ExposureUsage,
    result_fields: tuple[str, ...],
) -> Tier1ExposureUsage:
    """Record one aggregate-result exposure if fields and budget remain admissible."""
    _validate_policy_and_usage(policy, usage)
    _require_sorted_unique_fields(result_fields)
    if not set(result_fields).issubset(policy.allowed_result_fields):
        raise Tier1ExposureError("Tier 1 result contains a field outside the frozen allow-list")
    if usage.exposures_used >= policy.max_exposures:
        raise Tier1ExposureError("Tier 1 result-exposure budget is exhausted")
    return Tier1ExposureUsage(
        queries_used=usage.queries_used,
        exposures_used=usage.exposures_used + 1,
    )


def _validate_policy_and_usage(policy: Tier1ExposurePolicy, usage: Tier1ExposureUsage) -> None:
    if type(policy) is not Tier1ExposurePolicy:
        raise Tier1ExposureError("policy must be an exact Tier1ExposurePolicy")
    if type(usage) is not Tier1ExposureUsage:
        raise Tier1ExposureError("usage must be an exact Tier1ExposureUsage")
    policy.tier_contract.semantic_dict()
    _require_nonnegative_int(usage.queries_used, "queries_used")
    _require_nonnegative_int(usage.exposures_used, "exposures_used")
    if usage.queries_used > policy.query_ceiling:
        raise Tier1ExposureError("Tier 1 query usage exceeds the frozen ceiling")
    if usage.exposures_used > policy.max_exposures:
        raise Tier1ExposureError("Tier 1 exposure usage exceeds the frozen ceiling")


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise Tier1ExposureError(f"{label} must be a non-negative exact integer")


def _require_sorted_unique_fields(values: tuple[str, ...]) -> None:
    if type(values) is not tuple:
        raise Tier1ExposureError("result_fields must be an exact tuple")
    if not values:
        raise Tier1ExposureError("result_fields cannot be empty")
    if any(type(value) is not str or not value or value.strip() != value for value in values):
        raise Tier1ExposureError("result_fields must contain canonical exact strings")
    if values != tuple(sorted(set(values))):
        raise Tier1ExposureError("result_fields must be sorted and unique")
