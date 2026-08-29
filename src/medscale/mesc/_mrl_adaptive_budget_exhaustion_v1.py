"""Fail-closed adaptive budget exhaustion enforcement for MRL-0309.

The view is derived from one exact frozen objective and one exact canonical campaign via
the MRL-0308 accounting primitive. Exhausted or disallowed adaptive tiers are ``BLOCKED``
for further use. This module cannot expand budgets, amend the objective, request additional
sealed detail, or grant execution, training, promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_adaptive_campaign_accounting_v1 import (
    AdaptiveTierAccounting,
    build_adaptive_campaign_accounting,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign
from medscale.mesc._mrl_research_objective_v1 import (
    BudgetExhaustionDisposition,
    EvaluationTier,
    ResearchObjectiveContract,
)

__all__ = [
    "AdaptiveBudgetBlockReason",
    "AdaptiveBudgetEnforcementError",
    "AdaptiveBudgetEnforcementReport",
    "AdaptiveTierDisposition",
    "AdaptiveTierEnforcement",
    "enforce_adaptive_budget_exhaustion",
]

_ADAPTIVE_TIERS: Final = (EvaluationTier.SEARCH, EvaluationTier.REPLICATION)


class AdaptiveBudgetEnforcementError(ValueError):
    """Fail-closed validation error for MRL-0309 budget enforcement."""


class AdaptiveTierDisposition(enum.Enum):
    """Per-tier availability after applying the frozen objective envelope."""

    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"


class AdaptiveBudgetBlockReason(enum.Enum):
    """Exact reason an adaptive tier cannot accept another adaptive use."""

    QUERY_BUDGET_EXHAUSTED = "QUERY_BUDGET_EXHAUSTED"
    RESULT_EXPOSURE_BUDGET_EXHAUSTED = "RESULT_EXPOSURE_BUDGET_EXHAUSTED"
    TIER_NOT_ALLOWED = "TIER_NOT_ALLOWED"


@dataclass(frozen=True, slots=True)
class AdaptiveTierEnforcement:
    """Immutable enforcement decision for one adaptive evaluation tier."""

    tier: EvaluationTier
    queries_remaining: int
    result_exposures_remaining: int
    disposition: AdaptiveTierDisposition
    block_reasons: tuple[AdaptiveBudgetBlockReason, ...]

    def __post_init__(self) -> None:
        if type(self.tier) is not EvaluationTier or self.tier not in _ADAPTIVE_TIERS:
            raise AdaptiveBudgetEnforcementError("tier must be SEARCH or REPLICATION")
        _require_nonnegative_int(self.queries_remaining, "queries_remaining")
        _require_nonnegative_int(
            self.result_exposures_remaining,
            "result_exposures_remaining",
        )
        if type(self.disposition) is not AdaptiveTierDisposition:
            raise AdaptiveBudgetEnforcementError("disposition has an invalid type")
        if type(self.block_reasons) is not tuple:
            raise AdaptiveBudgetEnforcementError("block_reasons must be an exact tuple")
        if any(
            type(reason) is not AdaptiveBudgetBlockReason
            for reason in self.block_reasons
        ):
            raise AdaptiveBudgetEnforcementError("block_reasons contains an invalid item")
        values = tuple(reason.value for reason in self.block_reasons)
        if values != tuple(sorted(set(values))):
            raise AdaptiveBudgetEnforcementError("block_reasons must be sorted and unique")
        if self.disposition is AdaptiveTierDisposition.AVAILABLE and self.block_reasons:
            raise AdaptiveBudgetEnforcementError("AVAILABLE tier cannot have block reasons")
        if self.disposition is AdaptiveTierDisposition.BLOCKED and not self.block_reasons:
            raise AdaptiveBudgetEnforcementError("BLOCKED tier requires a reason")

    @property
    def can_use_adaptive_tier(self) -> bool:
        """Return whether one additional bounded adaptive use is permitted."""
        return self.disposition is AdaptiveTierDisposition.AVAILABLE

    def to_dict(self) -> dict[str, object]:
        """Return deterministic per-tier enforcement semantics."""
        return {
            "block_reasons": [reason.value for reason in self.block_reasons],
            "can_use_adaptive_tier": self.can_use_adaptive_tier,
            "disposition": self.disposition.value,
            "queries_remaining": self.queries_remaining,
            "result_exposures_remaining": self.result_exposures_remaining,
            "tier": int(self.tier),
            "tier_name": self.tier.name,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveBudgetEnforcementReport:
    """Content-addressed non-authoritative enforcement view for one campaign."""

    objective_sha256: str
    campaign_sha256: str
    accounting_sha256: str
    tiers: tuple[AdaptiveTierEnforcement, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(self.campaign_sha256, "campaign_sha256")
        _require_sha256(self.accounting_sha256, "accounting_sha256")
        if type(self.tiers) is not tuple:
            raise AdaptiveBudgetEnforcementError("tiers must be an exact tuple")
        if any(type(item) is not AdaptiveTierEnforcement for item in self.tiers):
            raise AdaptiveBudgetEnforcementError("tiers contains an invalid item")
        if tuple(item.tier for item in self.tiers) != _ADAPTIVE_TIERS:
            raise AdaptiveBudgetEnforcementError(
                "tiers must contain SEARCH then REPLICATION"
            )

    @property
    def can_expand_budget(self) -> bool:
        return False

    @property
    def can_amend_objective(self) -> bool:
        return False

    @property
    def can_request_additional_sealed_detail(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def semantic_dict(self) -> dict[str, object]:
        """Return deterministic fail-closed enforcement semantics."""
        return {
            "accounting_sha256": self.accounting_sha256,
            "campaign_sha256": self.campaign_sha256,
            "can_amend_objective": False,
            "can_authorize": False,
            "can_expand_budget": False,
            "can_request_additional_sealed_detail": False,
            "format": "MRL-ADAPTIVE-BUDGET-ENFORCEMENT-V1",
            "objective_sha256": self.objective_sha256,
            "tiers": [item.to_dict() for item in self.tiers],
        }

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def enforce_adaptive_budget_exhaustion(
    objective: ResearchObjectiveContract,
    campaign: ResearchCampaign,
) -> AdaptiveBudgetEnforcementReport:
    """Derive exact per-tier BLOCKED/AVAILABLE state from frozen accounting."""
    if type(objective) is not ResearchObjectiveContract:
        raise AdaptiveBudgetEnforcementError(
            "objective must be an exact ResearchObjectiveContract"
        )
    if type(campaign) is not ResearchCampaign:
        raise AdaptiveBudgetEnforcementError("campaign must be an exact ResearchCampaign")
    if objective.budget_exhaustion_disposition is not BudgetExhaustionDisposition.BLOCKED:
        raise AdaptiveBudgetEnforcementError(
            "objective budget exhaustion disposition must be BLOCKED"
        )

    objective.semantic_dict()
    campaign.semantic_dict()
    accounting = build_adaptive_campaign_accounting(objective, campaign)
    rows = tuple(_enforce_tier(objective, row) for row in accounting.tiers)
    return AdaptiveBudgetEnforcementReport(
        objective_sha256=accounting.objective_sha256,
        campaign_sha256=accounting.campaign_sha256,
        accounting_sha256=accounting.content_sha256,
        tiers=rows,
    )


def _enforce_tier(
    objective: ResearchObjectiveContract,
    accounting: AdaptiveTierAccounting,
) -> AdaptiveTierEnforcement:
    reasons: list[AdaptiveBudgetBlockReason] = []
    if accounting.tier not in objective.evaluation_tier_policy.allowed_tiers:
        reasons.append(AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED)
    else:
        if accounting.queries_remaining == 0:
            reasons.append(AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED)
        if accounting.result_exposures_remaining == 0:
            reasons.append(AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED)

    ordered = tuple(sorted(reasons, key=lambda reason: reason.value))
    disposition = (
        AdaptiveTierDisposition.BLOCKED
        if ordered
        else AdaptiveTierDisposition.AVAILABLE
    )
    return AdaptiveTierEnforcement(
        tier=accounting.tier,
        queries_remaining=accounting.queries_remaining,
        result_exposures_remaining=accounting.result_exposures_remaining,
        disposition=disposition,
        block_reasons=ordered,
    )


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise AdaptiveBudgetEnforcementError(
            f"{label} must be a non-negative exact integer"
        )


def _require_sha256(value: object, label: str) -> None:
    invalid = (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    )
    if invalid:
        raise AdaptiveBudgetEnforcementError(f"{label} must be 64 lowercase hex")
