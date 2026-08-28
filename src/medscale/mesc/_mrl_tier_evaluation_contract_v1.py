"""Tier-aware evaluation contract for MESC Research Loop V1.

MRL-0301 binds one already-frozen ``ResearchObjectiveContract`` to one admitted
evaluation tier and derives the applicable evaluator, metric, adaptive-query, and
result-exposure semantics. Callers cannot provide replacement budgets or evaluator
identities through this contract; all such values are derived from the objective.

This module is deterministic and side-effect free. It grants no filesystem, network,
model, dataset, GPU, inference, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

import enum
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


@dataclass(frozen=True, slots=True)
class TierEvaluationContract:
    """A content-addressed view of one objective's exact policy for one tier."""

    objective: ResearchObjectiveContract
    tier: EvaluationTier

    def __post_init__(self) -> None:
        _validate_contract(self)

    @property
    def content_sha256(self) -> str:
        """Derive identity from a freshly revalidated semantic view."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic bytes from a freshly revalidated semantic view."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def can_authorize(self) -> bool:
        """MRL tier contracts are evidence policy only and never authority artifacts."""
        return False

    def semantic_dict(self) -> dict[str, object]:
        """Return complete tier semantics derived only from the frozen objective."""
        _validate_contract(self)
        exposure = _result_exposure(self.objective, self.tier)
        evaluators = _evaluator_identities(self.objective, self.tier)
        metrics = _metric_contracts(self.objective, self.tier)
        mode = _INTERACTION_MODE[self.tier]
        return {
            "format": "MRL-TIER-EVALUATION-CONTRACT-V1",
            "objective_sha256": self.objective.content_sha256,
            "tier": int(self.tier),
            "tier_name": self.tier.name,
            "interaction_mode": mode.value,
            "adaptive_query_ceiling": _adaptive_query_ceiling(self.objective, self.tier),
            "result_exposure": exposure.to_dict(),
            "evaluator_identities": [identity.to_dict() for identity in evaluators],
            "metric_contracts": [metric.to_dict() for metric in metrics],
            "iterative_agent_result_stream": self.tier
            not in (
                EvaluationTier.SEALED,
                EvaluationTier.EXTERNAL_ASSURANCE,
            ),
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


def _validate_contract(value: TierEvaluationContract) -> None:
    if type(value.objective) is not ResearchObjectiveContract:
        raise TierEvaluationContractError("objective must be an exact ResearchObjectiveContract")
    if type(value.tier) is not EvaluationTier:
        raise TierEvaluationContractError("tier must be an exact EvaluationTier")

    # Force the source objective through its complete fresh snapshot validation before
    # deriving any tier policy from its fields.
    value.objective.semantic_dict()
    if value.tier not in value.objective.evaluation_tier_policy.allowed_tiers:
        raise TierEvaluationContractError(
            f"tier {value.tier.name} is not admitted by the frozen objective"
        )

    exposure = _result_exposure(value.objective, value.tier)
    query_ceiling = _adaptive_query_ceiling(value.objective, value.tier)
    if value.tier not in (EvaluationTier.SEARCH, EvaluationTier.REPLICATION) and query_ceiling:
        raise TierEvaluationContractError(
            "only Tier 1 SEARCH and Tier 2 REPLICATION may consume adaptive queries"
        )
    if value.tier in (EvaluationTier.SEALED, EvaluationTier.EXTERNAL_ASSURANCE) and (
        exposure.max_exposures or exposure.allowed_result_fields
    ):
        raise TierEvaluationContractError(
            "Tier 3/4 cannot expose iterative agent-visible results"
        )


def _adaptive_query_ceiling(objective: ResearchObjectiveContract, tier: EvaluationTier) -> int:
    if tier is EvaluationTier.SEARCH:
        return objective.adaptive_query_budget.tier_1_queries
    if tier is EvaluationTier.REPLICATION:
        return objective.adaptive_query_budget.tier_2_queries
    return 0


def _result_exposure(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> TierResultExposure:
    matching = tuple(
        policy for policy in objective.tier_result_exposure_policy if policy.tier is tier
    )
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
    return tuple(
        EvaluatorIdentity(
            evaluator_id=identity.evaluator_id,
            artifact_sha256=identity.artifact_sha256,
            tiers=identity.tiers,
        )
        for identity in objective.evaluator_identities
        if tier in identity.tiers
    )


def _metric_contracts(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> tuple[MetricContract, ...]:
    candidates = (*objective.search_metrics, *objective.evaluation_metrics)
    return tuple(
        MetricContract(
            metric_id=metric.metric_id,
            evaluator_id=metric.evaluator_id,
            tier=metric.tier,
            direction=metric.direction,
        )
        for metric in candidates
        if metric.tier is tier
    )
