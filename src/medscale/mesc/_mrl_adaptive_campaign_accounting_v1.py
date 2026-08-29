"""Deterministic adaptive-query and exposure accounting for MRL campaigns.

MRL-0308 reconciles cumulative campaign Tier 1/Tier 2 usage against the exact ceilings
already frozen in one ``ResearchObjectiveContract``. It is an accounting view only: it
cannot enlarge budgets, authorize execution, or decide the MRL-0309 blocked disposition.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import CampaignTierTotals, ResearchCampaign
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContract,
)

__all__ = [
    "AdaptiveCampaignAccounting",
    "AdaptiveCampaignAccountingError",
    "AdaptiveTierAccounting",
    "build_adaptive_campaign_accounting",
]

_ADAPTIVE_TIERS: Final = (EvaluationTier.SEARCH, EvaluationTier.REPLICATION)


class AdaptiveCampaignAccountingError(ValueError):
    """Fail-closed validation error for MRL-0308 accounting."""


def _make_tier_identity_registry() -> tuple[
    Callable[[AdaptiveTierAccounting, str], None],
    Callable[[AdaptiveTierAccounting], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: AdaptiveTierAccounting, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise AdaptiveCampaignAccountingError(
                "adaptive tier accounting construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: AdaptiveTierAccounting) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise AdaptiveCampaignAccountingError(
                "adaptive tier accounting construction identity is missing"
            )
        return identity

    return store, load


def _make_accounting_identity_registry() -> tuple[
    Callable[[AdaptiveCampaignAccounting, str], None],
    Callable[[AdaptiveCampaignAccounting], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: AdaptiveCampaignAccounting, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise AdaptiveCampaignAccountingError(
                "adaptive accounting construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: AdaptiveCampaignAccounting) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise AdaptiveCampaignAccountingError(
                "adaptive accounting construction identity is missing"
            )
        return identity

    return store, load


_store_tier_identity, _load_tier_identity = _make_tier_identity_registry()
_store_accounting_identity, _load_accounting_identity = _make_accounting_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class AdaptiveTierAccounting:
    """Immutable cumulative usage and frozen ceilings for one adaptive tier."""

    tier: EvaluationTier
    queries_used: int
    query_ceiling: int
    result_exposures_used: int
    result_exposure_ceiling: int

    def __post_init__(self) -> None:
        if type(self.tier) is not EvaluationTier or self.tier not in _ADAPTIVE_TIERS:
            raise AdaptiveCampaignAccountingError("tier must be SEARCH or REPLICATION")
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(self.query_ceiling, "query_ceiling")
        _require_nonnegative_int(self.result_exposures_used, "result_exposures_used")
        _require_nonnegative_int(self.result_exposure_ceiling, "result_exposure_ceiling")
        if self.queries_used > self.query_ceiling:
            raise AdaptiveCampaignAccountingError("adaptive query usage exceeds frozen ceiling")
        if self.result_exposures_used > self.result_exposure_ceiling:
            raise AdaptiveCampaignAccountingError("result exposure usage exceeds frozen ceiling")
        _store_tier_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> AdaptiveTierAccounting:
        if type(self) is not AdaptiveTierAccounting:
            raise AdaptiveCampaignAccountingError(
                "tier accounting must be an exact AdaptiveTierAccounting"
            )
        bound_content_sha256 = _load_tier_identity(self)
        _require_sha256(bound_content_sha256, "bound tier content_sha256")
        snapshot = AdaptiveTierAccounting(
            tier=self.tier,
            queries_used=self.queries_used,
            query_ceiling=self.query_ceiling,
            result_exposures_used=self.result_exposures_used,
            result_exposure_ceiling=self.result_exposure_ceiling,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise AdaptiveCampaignAccountingError(
                "adaptive tier accounting identity changed after construction"
            )
        return snapshot

    def _queries_remaining_validated(self) -> int:
        return self.query_ceiling - self.queries_used

    def _result_exposures_remaining_validated(self) -> int:
        return self.result_exposure_ceiling - self.result_exposures_used

    @property
    def queries_remaining(self) -> int:
        """Return unused query capacity from a freshly validated accounting row."""
        snapshot = AdaptiveTierAccounting._validated_snapshot(self)
        return snapshot._queries_remaining_validated()

    @property
    def result_exposures_remaining(self) -> int:
        """Return unused exposure capacity from a freshly validated accounting row."""
        snapshot = AdaptiveTierAccounting._validated_snapshot(self)
        return snapshot._result_exposures_remaining_validated()

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "queries_remaining": self._queries_remaining_validated(),
            "queries_used": self.queries_used,
            "query_ceiling": self.query_ceiling,
            "result_exposure_ceiling": self.result_exposure_ceiling,
            "result_exposures_remaining": self._result_exposures_remaining_validated(),
            "result_exposures_used": self.result_exposures_used,
            "tier": int(self.tier),
            "tier_name": self.tier.name,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated accounting semantics for one adaptive tier."""
        snapshot = AdaptiveTierAccounting._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class AdaptiveCampaignAccounting:
    """Content-addressed accounting view for one exact campaign/objective pair."""

    objective_sha256: str
    campaign_sha256: str
    tiers: tuple[AdaptiveTierAccounting, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(self.campaign_sha256, "campaign_sha256")
        if type(self.tiers) is not tuple:
            raise AdaptiveCampaignAccountingError("tiers must be an exact tuple")
        if any(type(item) is not AdaptiveTierAccounting for item in self.tiers):
            raise AdaptiveCampaignAccountingError("tiers contains an invalid item type")
        snapshots = tuple(AdaptiveTierAccounting._validated_snapshot(item) for item in self.tiers)
        tier_ids = tuple(int(item.tier) for item in snapshots)
        expected = tuple(int(tier) for tier in _ADAPTIVE_TIERS)
        if tier_ids != expected:
            raise AdaptiveCampaignAccountingError("tiers must contain SEARCH then REPLICATION")
        _store_accounting_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> AdaptiveCampaignAccounting:
        if type(self) is not AdaptiveCampaignAccounting:
            raise AdaptiveCampaignAccountingError(
                "accounting must be an exact AdaptiveCampaignAccounting"
            )
        if type(self.tiers) is not tuple:
            raise AdaptiveCampaignAccountingError("tiers must be an exact tuple")
        bound_content_sha256 = _load_accounting_identity(self)
        _require_sha256(bound_content_sha256, "bound accounting content_sha256")
        snapshot = AdaptiveCampaignAccounting(
            objective_sha256=self.objective_sha256,
            campaign_sha256=self.campaign_sha256,
            tiers=tuple(AdaptiveTierAccounting._validated_snapshot(item) for item in self.tiers),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise AdaptiveCampaignAccountingError(
                "adaptive accounting identity changed after construction"
            )
        return snapshot

    @property
    def can_authorize(self) -> bool:
        """Accounting views never grant execution or scientific authority."""
        return False

    @property
    def can_expand_budget(self) -> bool:
        """Accounting views cannot alter externally frozen budgets."""
        return False

    @property
    def content_sha256(self) -> str:
        """Return deterministic identity over freshly validated accounting semantics."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic canonical accounting bytes after revalidation."""
        return canonical_semantic_bytes(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "campaign_sha256": self.campaign_sha256,
            "can_authorize": False,
            "can_expand_budget": False,
            "format": "MRL-ADAPTIVE-CAMPAIGN-ACCOUNTING-V1",
            "objective_sha256": self.objective_sha256,
            "tiers": [item._to_dict_validated() for item in self.tiers],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return non-authoritative semantics from one freshly validated snapshot."""
        snapshot = AdaptiveCampaignAccounting._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return accounting semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_adaptive_campaign_accounting(
    objective: ResearchObjectiveContract,
    campaign: ResearchCampaign,
) -> AdaptiveCampaignAccounting:
    """Reconcile exact cumulative campaign usage against frozen adaptive ceilings."""
    if type(objective) is not ResearchObjectiveContract:
        raise AdaptiveCampaignAccountingError(
            "objective must be an exact ResearchObjectiveContract"
        )
    if type(campaign) is not ResearchCampaign:
        raise AdaptiveCampaignAccountingError("campaign must be an exact ResearchCampaign")

    objective.semantic_dict()
    campaign.semantic_dict()
    if campaign.objective_sha256 != objective.content_sha256:
        raise AdaptiveCampaignAccountingError(
            "campaign objective identity does not match objective"
        )

    usage_by_tier = {item.tier: item for item in campaign.cumulative_tier_usage}
    rows = tuple(
        _build_tier_accounting(objective, usage_by_tier, tier) for tier in _ADAPTIVE_TIERS
    )
    return AdaptiveCampaignAccounting(
        objective_sha256=objective.content_sha256,
        campaign_sha256=campaign.content_sha256,
        tiers=rows,
    )


def _build_tier_accounting(
    objective: ResearchObjectiveContract,
    usage_by_tier: dict[EvaluationTier, CampaignTierTotals],
    tier: EvaluationTier,
) -> AdaptiveTierAccounting:
    usage = usage_by_tier.get(tier)
    queries_used = 0 if usage is None else usage.queries_used
    result_exposures_used = 0 if usage is None else usage.result_exposures_used

    query_ceiling = (
        objective.adaptive_query_budget.tier_1_queries
        if tier is EvaluationTier.SEARCH
        else objective.adaptive_query_budget.tier_2_queries
    )
    exposure_matches = tuple(
        policy for policy in objective.tier_result_exposure_policy if policy.tier is tier
    )
    if tier in objective.evaluation_tier_policy.allowed_tiers:
        if len(exposure_matches) != 1:
            raise AdaptiveCampaignAccountingError(
                "allowed adaptive tier must have exactly one frozen exposure policy"
            )
        exposure_ceiling = exposure_matches[0].max_exposures
    else:
        if exposure_matches:
            raise AdaptiveCampaignAccountingError(
                "disallowed adaptive tier cannot have a frozen exposure policy"
            )
        exposure_ceiling = 0
        if query_ceiling != 0:
            raise AdaptiveCampaignAccountingError(
                "disallowed adaptive tier cannot have a nonzero query ceiling"
            )

    return AdaptiveTierAccounting(
        tier=tier,
        queries_used=queries_used,
        query_ceiling=query_ceiling,
        result_exposures_used=result_exposures_used,
        result_exposure_ceiling=exposure_ceiling,
    )


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise AdaptiveCampaignAccountingError(f"{label} must be a non-negative exact integer")


def _require_sha256(value: object, label: str) -> None:
    invalid = (
        type(value) is not str
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    )
    if invalid:
        raise AdaptiveCampaignAccountingError(f"{label} must be 64 lowercase hex")
