"""Tier-aware evaluation contract for MESC Research Loop V1.

MRL-0301 binds one already-frozen ``ResearchObjectiveContract`` to one admitted
evaluation tier and derives evaluator, metric, adaptive-query, and result-exposure
semantics from that objective.

This module is deterministic and side-effect free. It grants no filesystem, network,
model, dataset, GPU, inference, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

import enum
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    EvaluatorIdentity,
    MetricContract,
    ResearchObjectiveContract,
    TierResultExposure,
)

__all__ = [
    "TierEvaluationContract",
    "TierEvaluationContractError",
    "TierInteractionMode",
]


class TierEvaluationContractError(ValueError):
    """Fail-closed validation error for MRL-0301 tier semantics."""


class TierInteractionMode(enum.Enum):
    """Permanent high-level interaction semantics for each canonical MRL tier."""

    FIXTURE_DEVELOPMENT = "FIXTURE_DEVELOPMENT"
    ADAPTIVE_SEARCH = "ADAPTIVE_SEARCH"
    BOUNDED_REPLICATION = "BOUNDED_REPLICATION"
    SEALED_INDEPENDENT_EVIDENCE = "SEALED_INDEPENDENT_EVIDENCE"
    EXTERNAL_ASSURANCE = "EXTERNAL_ASSURANCE"


_INTERACTION_MODE: Final[dict[EvaluationTier, TierInteractionMode]] = {
    EvaluationTier.DEVELOPMENT: TierInteractionMode.FIXTURE_DEVELOPMENT,
    EvaluationTier.SEARCH: TierInteractionMode.ADAPTIVE_SEARCH,
    EvaluationTier.REPLICATION: TierInteractionMode.BOUNDED_REPLICATION,
    EvaluationTier.SEALED: TierInteractionMode.SEALED_INDEPENDENT_EVIDENCE,
    EvaluationTier.EXTERNAL_ASSURANCE: TierInteractionMode.EXTERNAL_ASSURANCE,
}
_ADAPTIVE_TIERS: Final = (EvaluationTier.SEARCH, EvaluationTier.REPLICATION)
_NON_ITERATIVE_TIERS: Final = (EvaluationTier.SEALED, EvaluationTier.EXTERNAL_ASSURANCE)


def _make_construction_identity_registry() -> tuple[
    Callable[[TierEvaluationContract, str], None],
    Callable[[TierEvaluationContract], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: TierEvaluationContract, objective_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise TierEvaluationContractError("tier contract construction identity already exists")
        identities[key] = objective_sha256
        weakref.finalize(value, remove, key)

    def load(value: TierEvaluationContract) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise TierEvaluationContractError("tier contract construction identity is missing")
        return identity

    return store, load


(
    _store_construction_identity,
    _load_construction_identity,
) = _make_construction_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TierEvaluationContract:
    """A content-addressed view of one exact frozen objective policy for one tier."""

    objective: ResearchObjectiveContract
    tier: EvaluationTier

    def __post_init__(self) -> None:
        if type(self) is not TierEvaluationContract:
            return
        if type(self.tier) is not EvaluationTier:
            raise TierEvaluationContractError("tier must be an exact EvaluationTier")
        objective = _snapshot_objective(self.objective)
        _validate_objective_tier_semantics(objective, self.tier)
        _store_construction_identity(self, objective.content_sha256)

    def _validated_objective(self) -> tuple[ResearchObjectiveContract, str]:
        if type(self) is not TierEvaluationContract:
            raise TierEvaluationContractError("contract must be an exact TierEvaluationContract")
        if type(self.tier) is not EvaluationTier:
            raise TierEvaluationContractError("tier must be an exact EvaluationTier")
        bound_objective_sha256 = _load_construction_identity(self)
        _require_sha256(bound_objective_sha256, "bound objective_sha256")
        objective = _snapshot_objective(self.objective)
        _validate_objective_tier_semantics(objective, self.tier)
        current_sha256 = objective.content_sha256
        if current_sha256 != bound_objective_sha256:
            raise TierEvaluationContractError(
                "objective identity changed after tier contract creation"
            )
        return objective, bound_objective_sha256

    @property
    def content_sha256(self) -> str:
        """Derive identity only from the originally bound frozen objective."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic bytes only after frozen-objective identity validation."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def can_authorize(self) -> bool:
        """MRL tier contracts are evidence policy only and never authority artifacts."""
        return False

    def semantic_dict(self) -> dict[str, object]:
        """Return complete tier semantics from one construction-bound objective snapshot."""
        objective, objective_sha256 = self._validated_objective()
        exposure = _result_exposure(objective, self.tier)
        evaluators = _evaluator_identities(objective, self.tier)
        metrics = _metric_contracts(objective, self.tier)
        mode = _INTERACTION_MODE[self.tier]
        iterative_stream = self.tier not in _NON_ITERATIVE_TIERS
        return {
            "format": "MRL-TIER-EVALUATION-CONTRACT-V1",
            "objective_sha256": objective_sha256,
            "tier": int(self.tier),
            "tier_name": self.tier.name,
            "interaction_mode": mode.value,
            "adaptive_query_ceiling": _adaptive_query_ceiling(objective, self.tier),
            "result_exposure": exposure.to_dict(),
            "evaluator_identities": [identity.to_dict() for identity in evaluators],
            "metric_contracts": [metric.to_dict() for metric in metrics],
            "iterative_agent_result_stream": iterative_stream,
            "sealed_item_level_search_context": False,
            "can_expand_budget": False,
            "can_replace_evaluator": False,
            "can_authorize": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def to_dict(self) -> dict[str, object]:
        """Return semantic data plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _snapshot_objective(value: ResearchObjectiveContract) -> ResearchObjectiveContract:
    if type(value) is not ResearchObjectiveContract:
        raise TierEvaluationContractError("objective must be an exact ResearchObjectiveContract")
    try:
        return value._validated_snapshot()
    except (AttributeError, TypeError, ValueError) as exc:
        raise TierEvaluationContractError(
            "objective failed canonical snapshot revalidation"
        ) from exc


def _validate_objective_tier_semantics(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> None:
    if tier not in objective.evaluation_tier_policy.allowed_tiers:
        raise TierEvaluationContractError(
            f"tier {tier.name} is not admitted by the frozen objective"
        )

    exposure = _result_exposure(objective, tier)
    query_ceiling = _adaptive_query_ceiling(objective, tier)
    if tier not in _ADAPTIVE_TIERS and query_ceiling:
        raise TierEvaluationContractError(
            "only Tier 1 SEARCH and Tier 2 REPLICATION may consume adaptive queries"
        )
    if tier in _NON_ITERATIVE_TIERS and (exposure.max_exposures or exposure.allowed_result_fields):
        raise TierEvaluationContractError("Tier 3/4 cannot expose iterative agent-visible results")


def _adaptive_query_ceiling(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> int:
    if tier is EvaluationTier.SEARCH:
        return objective.adaptive_query_budget.tier_1_queries
    if tier is EvaluationTier.REPLICATION:
        return objective.adaptive_query_budget.tier_2_queries
    return 0


def _result_exposure(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> TierResultExposure:
    matching: list[TierResultExposure] = []
    for policy in objective.tier_result_exposure_policy:
        if policy.tier is tier:
            matching.append(policy)
    if len(matching) != 1:
        raise TierEvaluationContractError(
            "frozen objective must define exactly one result-exposure policy for the tier"
        )
    policy = matching[0]
    return TierResultExposure(
        tier=policy.tier,
        max_exposures=policy.max_exposures,
        allowed_result_fields=policy.allowed_result_fields,
    )


def _evaluator_identities(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> tuple[EvaluatorIdentity, ...]:
    result: list[EvaluatorIdentity] = []
    for identity in objective.evaluator_identities:
        if tier in identity.tiers:
            result.append(
                EvaluatorIdentity(
                    evaluator_id=identity.evaluator_id,
                    artifact_sha256=identity.artifact_sha256,
                    tiers=identity.tiers,
                )
            )
    return tuple(result)


def _metric_contracts(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> tuple[MetricContract, ...]:
    result: list[MetricContract] = []
    candidates = (*objective.search_metrics, *objective.evaluation_metrics)
    for metric in candidates:
        if metric.tier is tier:
            result.append(
                MetricContract(
                    metric_id=metric.metric_id,
                    evaluator_id=metric.evaluator_id,
                    tier=metric.tier,
                    direction=metric.direction,
                )
            )
    return tuple(result)


def _require_sha256(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TierEvaluationContractError(f"{label} must be 64 lowercase hex")
