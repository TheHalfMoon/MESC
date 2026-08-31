"""Bounded Tier 1 result exposure for MESC Research Loop V1.

MRL-0302 enforces the query and result-exposure ceilings already frozen in a
``TierEvaluationContract`` for Tier 1 SEARCH. It is pure, deterministic, and grants
no execution, budget-expansion, training, promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
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


def _make_policy_identity_registry() -> tuple[
    Callable[[Tier1ExposurePolicy, str], None],
    Callable[[Tier1ExposurePolicy], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: Tier1ExposurePolicy, tier_contract_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise Tier1ExposureError("Tier 1 policy construction identity already exists")
        identities[key] = tier_contract_sha256
        weakref.finalize(value, remove, key)

    def load(value: Tier1ExposurePolicy) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise Tier1ExposureError("Tier 1 policy construction identity is missing")
        return identity

    return store, load


def _make_usage_identity_registry() -> tuple[
    Callable[[Tier1ExposureUsage, tuple[int, int]], None],
    Callable[[Tier1ExposureUsage], tuple[int, int]],
]:
    identities: dict[int, tuple[int, int]] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: Tier1ExposureUsage, counters: tuple[int, int]) -> None:
        key = id(value)
        if key in identities:
            raise Tier1ExposureError("Tier 1 usage construction identity already exists")
        identities[key] = counters
        weakref.finalize(value, remove, key)

    def load(value: Tier1ExposureUsage) -> tuple[int, int]:
        identity = identities.get(id(value))
        if identity is None:
            raise Tier1ExposureError("Tier 1 usage construction identity is missing")
        return identity

    return store, load


_store_policy_identity, _load_policy_identity = _make_policy_identity_registry()
_store_usage_identity, _load_usage_identity = _make_usage_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Tier1ExposureUsage:
    """Immutable usage counters for one frozen Tier 1 policy."""

    queries_used: int = 0
    exposures_used: int = 0

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(self.exposures_used, "exposures_used")
        if type(self) is Tier1ExposureUsage:
            _store_usage_identity(
                self,
                (self.queries_used, self.exposures_used),
            )

    def _validated_snapshot(self) -> Tier1ExposureUsage:
        if type(self) is not Tier1ExposureUsage:
            raise Tier1ExposureError("usage must be an exact Tier1ExposureUsage")
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(self.exposures_used, "exposures_used")
        bound_counters = _load_usage_identity(self)
        if (self.queries_used, self.exposures_used) != bound_counters:
            raise Tier1ExposureError("Tier 1 usage counters changed after construction")
        return Tier1ExposureUsage(
            queries_used=self.queries_used,
            exposures_used=self.exposures_used,
        )


@dataclass(frozen=True, slots=True, weakref_slot=True)
class Tier1ExposurePolicy:
    """Exact Tier 1 ceilings and aggregate fields bound to one frozen tier contract."""

    tier_contract: TierEvaluationContract

    def __post_init__(self) -> None:
        if type(self) is not Tier1ExposurePolicy:
            return
        contract = _validate_tier_contract(self.tier_contract)
        _store_policy_identity(self, contract.content_sha256)

    def _validated_contract(self) -> tuple[TierEvaluationContract, str]:
        if type(self) is not Tier1ExposurePolicy:
            raise Tier1ExposureError("policy must be an exact Tier1ExposurePolicy")
        bound_tier_contract_sha256 = _load_policy_identity(self)
        _require_sha256(
            bound_tier_contract_sha256,
            "bound tier_contract_sha256",
        )
        contract = _validate_tier_contract(self.tier_contract)
        if contract.content_sha256 != bound_tier_contract_sha256:
            raise Tier1ExposureError("tier contract identity changed after policy creation")
        return contract, bound_tier_contract_sha256

    @property
    def query_ceiling(self) -> int:
        """Return the originally bound Tier 1 adaptive-query ceiling."""
        contract, _ = self._validated_contract()
        return contract.objective.adaptive_query_budget.tier_1_queries

    @property
    def exposure_contract(self) -> TierResultExposure:
        """Return a fresh snapshot of the originally bound Tier 1 exposure contract."""
        contract, _ = self._validated_contract()
        matches = [
            policy
            for policy in contract.objective.tier_result_exposure_policy
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
        """Return the originally bound Tier 1 result-exposure ceiling."""
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
        contract, tier_contract_sha256 = self._validated_contract()
        exposure = self.exposure_contract
        return {
            "allowed_result_fields": list(exposure.allowed_result_fields),
            "can_authorize": False,
            "can_expand_budget": False,
            "max_exposures": exposure.max_exposures,
            "query_ceiling": contract.objective.adaptive_query_budget.tier_1_queries,
            "tier": int(EvaluationTier.SEARCH),
            "tier_contract_sha256": tier_contract_sha256,
        }


def consume_tier1_query(
    policy: Tier1ExposurePolicy,
    usage: Tier1ExposureUsage,
) -> Tier1ExposureUsage:
    """Consume one adaptive Tier 1 query or fail closed at the frozen ceiling."""
    usage_snapshot = _validate_policy_and_usage(policy, usage)
    if usage_snapshot.queries_used >= policy.query_ceiling:
        raise Tier1ExposureError("Tier 1 adaptive-query budget is exhausted")
    return Tier1ExposureUsage(
        queries_used=usage_snapshot.queries_used + 1,
        exposures_used=usage_snapshot.exposures_used,
    )


def record_tier1_exposure(
    policy: Tier1ExposurePolicy,
    usage: Tier1ExposureUsage,
    result_fields: tuple[str, ...],
) -> Tier1ExposureUsage:
    """Record one aggregate-result exposure if fields and budget remain admissible."""
    usage_snapshot = _validate_policy_and_usage(policy, usage)
    _require_sorted_unique_fields(result_fields)
    if not set(result_fields).issubset(policy.allowed_result_fields):
        raise Tier1ExposureError("Tier 1 result contains a field outside the frozen allow-list")
    if usage_snapshot.exposures_used >= policy.max_exposures:
        raise Tier1ExposureError("Tier 1 result-exposure budget is exhausted")
    return Tier1ExposureUsage(
        queries_used=usage_snapshot.queries_used,
        exposures_used=usage_snapshot.exposures_used + 1,
    )


def _validate_policy_and_usage(
    policy: Tier1ExposurePolicy,
    usage: Tier1ExposureUsage,
) -> Tier1ExposureUsage:
    if type(policy) is not Tier1ExposurePolicy:
        raise Tier1ExposureError("policy must be an exact Tier1ExposurePolicy")
    if type(usage) is not Tier1ExposureUsage:
        raise Tier1ExposureError("usage must be an exact Tier1ExposureUsage")
    policy._validated_contract()
    usage_snapshot = usage._validated_snapshot()
    if usage_snapshot.queries_used > policy.query_ceiling:
        raise Tier1ExposureError("Tier 1 query usage exceeds the frozen ceiling")
    if usage_snapshot.exposures_used > policy.max_exposures:
        raise Tier1ExposureError("Tier 1 exposure usage exceeds the frozen ceiling")
    return usage_snapshot


def _validate_tier_contract(contract: TierEvaluationContract) -> TierEvaluationContract:
    if type(contract) is not TierEvaluationContract:
        raise Tier1ExposureError("tier_contract must be an exact TierEvaluationContract")
    if contract.tier is not EvaluationTier.SEARCH:
        raise Tier1ExposureError("Tier 1 exposure policy requires SEARCH tier")
    try:
        contract.semantic_dict()
        _ = contract.content_sha256
    except (AttributeError, TypeError, ValueError) as exc:
        raise Tier1ExposureError("tier contract failed canonical revalidation") from exc
    return contract


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise Tier1ExposureError(f"{label} must be a non-negative exact integer")


def _require_sha256(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise Tier1ExposureError(f"{label} must be 64 lowercase hex")


def _require_sorted_unique_fields(values: tuple[str, ...]) -> None:
    if type(values) is not tuple:
        raise Tier1ExposureError("result_fields must be an exact tuple")
    if not values:
        raise Tier1ExposureError("result_fields cannot be empty")
    if any(type(value) is not str or not value or value.strip() != value for value in values):
        raise Tier1ExposureError("result_fields must contain canonical exact strings")
    if values != tuple(sorted(set(values))):
        raise Tier1ExposureError("result_fields must be sorted and unique")
