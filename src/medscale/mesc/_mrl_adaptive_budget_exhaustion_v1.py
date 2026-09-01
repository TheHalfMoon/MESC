"""Fail-closed adaptive-budget exhaustion enforcement for MESC Research Loop V1.

MRL-0309 converts the immutable MRL-0308 accounting view into an enforceable per-tier
adaptive-use disposition. Exhausted or disallowed adaptive tiers are ``BLOCKED`` and no
caller can use this contract to expand a frozen objective budget or request additional
sealed detail.

This module grants no model, data, network, GPU, training, promotion, deployment, release,
or clinical authority.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
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
    "AdaptiveBudgetDispositionReport",
    "AdaptiveBudgetExhaustionError",
    "AdaptiveTierDisposition",
    "AdaptiveTierUseState",
    "build_adaptive_budget_disposition",
    "require_adaptive_tier_available",
]

_ADAPTIVE_TIERS: Final = (EvaluationTier.SEARCH, EvaluationTier.REPLICATION)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class AdaptiveBudgetExhaustionError(ValueError):
    """Fail-closed error for MRL-0309 adaptive-use enforcement."""


class AdaptiveTierUseState(enum.Enum):
    """Whether further adaptive use of one tier remains available."""

    AVAILABLE = "AVAILABLE"
    BLOCKED = "BLOCKED"


class AdaptiveBudgetBlockReason(enum.Enum):
    """Canonical reasons why one adaptive tier is blocked."""

    QUERY_BUDGET_EXHAUSTED = "ADAPTIVE_QUERY_BUDGET_EXHAUSTED"
    RESULT_EXPOSURE_BUDGET_EXHAUSTED = "RESULT_EXPOSURE_BUDGET_EXHAUSTED"
    TIER_NOT_ALLOWED = "TIER_NOT_ALLOWED"


def _make_tier_identity_registry() -> tuple[
    Callable[[AdaptiveTierDisposition, str], None],
    Callable[[AdaptiveTierDisposition], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: AdaptiveTierDisposition, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise AdaptiveBudgetExhaustionError(
                "adaptive tier disposition construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: AdaptiveTierDisposition) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise AdaptiveBudgetExhaustionError(
                "adaptive tier disposition construction identity is missing"
            )
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[AdaptiveBudgetDispositionReport, str], None],
    Callable[[AdaptiveBudgetDispositionReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: AdaptiveBudgetDispositionReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise AdaptiveBudgetExhaustionError(
                "adaptive budget report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: AdaptiveBudgetDispositionReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise AdaptiveBudgetExhaustionError(
                "adaptive budget report construction identity is missing"
            )
        return identity

    return store, load


_store_tier_identity, _load_tier_identity = _make_tier_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class AdaptiveTierDisposition:
    """Deterministic adaptive-use disposition for one frozen evaluation tier."""

    tier: EvaluationTier
    state: AdaptiveTierUseState
    reasons: tuple[AdaptiveBudgetBlockReason, ...]
    queries_remaining: int
    result_exposures_remaining: int

    def __post_init__(self) -> None:
        if type(self.tier) is not EvaluationTier or self.tier not in _ADAPTIVE_TIERS:
            raise AdaptiveBudgetExhaustionError("tier must be SEARCH or REPLICATION")
        if type(self.state) is not AdaptiveTierUseState:
            raise AdaptiveBudgetExhaustionError("state must be an exact AdaptiveTierUseState")
        if type(self.reasons) is not tuple:
            raise AdaptiveBudgetExhaustionError("reasons must be an exact tuple")
        if any(type(reason) is not AdaptiveBudgetBlockReason for reason in self.reasons):
            raise AdaptiveBudgetExhaustionError("reasons contains an invalid item type")
        reason_values = tuple(reason.value for reason in self.reasons)
        if reason_values != tuple(sorted(set(reason_values))):
            raise AdaptiveBudgetExhaustionError("reasons must be unique and sorted")
        _require_nonnegative_int(self.queries_remaining, "queries_remaining")
        _require_nonnegative_int(
            self.result_exposures_remaining,
            "result_exposures_remaining",
        )

        if self.state is AdaptiveTierUseState.AVAILABLE:
            if self.reasons:
                raise AdaptiveBudgetExhaustionError("AVAILABLE tier cannot carry block reasons")
            if self.queries_remaining == 0 or self.result_exposures_remaining == 0:
                raise AdaptiveBudgetExhaustionError(
                    "AVAILABLE tier must retain query and exposure capacity"
                )
        else:
            if not self.reasons:
                raise AdaptiveBudgetExhaustionError("BLOCKED tier requires at least one reason")
            if AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED in self.reasons:
                if self.reasons != (AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED,):
                    raise AdaptiveBudgetExhaustionError(
                        "TIER_NOT_ALLOWED cannot be combined with budget exhaustion reasons"
                    )
                if self.queries_remaining != 0 or self.result_exposures_remaining != 0:
                    raise AdaptiveBudgetExhaustionError(
                        "TIER_NOT_ALLOWED tier must expose zero remaining adaptive capacity"
                    )
            else:
                expected_reasons: list[AdaptiveBudgetBlockReason] = []
                if self.queries_remaining == 0:
                    expected_reasons.append(AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED)
                if self.result_exposures_remaining == 0:
                    expected_reasons.append(
                        AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED
                    )
                expected = tuple(sorted(expected_reasons, key=lambda reason: reason.value))
                if not expected:
                    raise AdaptiveBudgetExhaustionError(
                        "BLOCKED allowed tier must have at least one exhausted capacity"
                    )
                if self.reasons != expected:
                    raise AdaptiveBudgetExhaustionError(
                        "BLOCKED reasons must exactly match exhausted adaptive capacities"
                    )
        _store_tier_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> AdaptiveTierDisposition:
        if type(self) is not AdaptiveTierDisposition:
            raise AdaptiveBudgetExhaustionError(
                "tier disposition must be an exact AdaptiveTierDisposition"
            )
        bound_content_sha256 = _load_tier_identity(self)
        _require_sha256(bound_content_sha256, "bound tier disposition content_sha256")
        snapshot = AdaptiveTierDisposition(
            tier=self.tier,
            state=self.state,
            reasons=self.reasons,
            queries_remaining=self.queries_remaining,
            result_exposures_remaining=self.result_exposures_remaining,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise AdaptiveBudgetExhaustionError(
                "adaptive tier disposition identity changed after construction"
            )
        return snapshot

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "queries_remaining": self.queries_remaining,
            "reasons": [reason.value for reason in self.reasons],
            "result_exposures_remaining": self.result_exposures_remaining,
            "state": self.state.value,
            "tier": int(self.tier),
            "tier_name": self.tier.name,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated per-tier disposition semantics."""
        snapshot = AdaptiveTierDisposition._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class AdaptiveBudgetDispositionReport:
    """Content-addressed MRL-0309 enforcement result for one exact campaign."""

    objective_sha256: str
    campaign_sha256: str
    accounting_sha256: str
    tiers: tuple[AdaptiveTierDisposition, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_sha256(self.campaign_sha256, "campaign_sha256")
        _require_sha256(self.accounting_sha256, "accounting_sha256")
        if type(self.tiers) is not tuple:
            raise AdaptiveBudgetExhaustionError("tiers must be an exact tuple")
        if any(type(item) is not AdaptiveTierDisposition for item in self.tiers):
            raise AdaptiveBudgetExhaustionError("tiers contains an invalid item type")
        snapshots = tuple(AdaptiveTierDisposition._validated_snapshot(item) for item in self.tiers)
        if tuple(item.tier for item in snapshots) != _ADAPTIVE_TIERS:
            raise AdaptiveBudgetExhaustionError("tiers must contain SEARCH then REPLICATION")
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> AdaptiveBudgetDispositionReport:
        if type(self) is not AdaptiveBudgetDispositionReport:
            raise AdaptiveBudgetExhaustionError(
                "report must be an exact AdaptiveBudgetDispositionReport"
            )
        if type(self.tiers) is not tuple:
            raise AdaptiveBudgetExhaustionError("tiers must be an exact tuple")
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound report content_sha256")
        snapshot = AdaptiveBudgetDispositionReport(
            objective_sha256=self.objective_sha256,
            campaign_sha256=self.campaign_sha256,
            accounting_sha256=self.accounting_sha256,
            tiers=tuple(AdaptiveTierDisposition._validated_snapshot(item) for item in self.tiers),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise AdaptiveBudgetExhaustionError(
                "adaptive budget report identity changed after construction"
            )
        return snapshot

    def _blocked_tiers_validated(self) -> tuple[EvaluationTier, ...]:
        return tuple(item.tier for item in self.tiers if item.state is AdaptiveTierUseState.BLOCKED)

    @property
    def blocked_tiers(self) -> tuple[EvaluationTier, ...]:
        """Return every freshly validated adaptive tier that cannot be used further."""
        snapshot = AdaptiveBudgetDispositionReport._validated_snapshot(self)
        return snapshot._blocked_tiers_validated()

    @property
    def can_authorize(self) -> bool:
        """Budget disposition never grants execution authority."""
        return False

    @property
    def can_expand_budget(self) -> bool:
        """The campaign cannot amend its externally frozen budget."""
        return False

    @property
    def can_request_additional_sealed_detail(self) -> bool:
        """Budget exhaustion cannot unlock additional Tier 3 detail."""
        return False

    @property
    def content_sha256(self) -> str:
        """Return deterministic identity over freshly validated disposition semantics."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical fail-closed disposition bytes after revalidation."""
        return canonical_semantic_bytes(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "accounting_sha256": self.accounting_sha256,
            "blocked_tiers": [int(tier) for tier in self._blocked_tiers_validated()],
            "campaign_sha256": self.campaign_sha256,
            "can_authorize": False,
            "can_expand_budget": False,
            "can_request_additional_sealed_detail": False,
            "format": "MRL-ADAPTIVE-BUDGET-DISPOSITION-V1",
            "objective_sha256": self.objective_sha256,
            "tiers": [item._to_dict_validated() for item in self.tiers],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly validated disposition snapshot."""
        snapshot = AdaptiveBudgetDispositionReport._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return report semantics plus derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_adaptive_budget_disposition(
    objective: ResearchObjectiveContract,
    campaign: ResearchCampaign,
) -> AdaptiveBudgetDispositionReport:
    """Derive fail-closed adaptive-use state from exact frozen campaign accounting."""
    if type(objective) is not ResearchObjectiveContract:
        raise AdaptiveBudgetExhaustionError("objective must be an exact ResearchObjectiveContract")
    if type(campaign) is not ResearchCampaign:
        raise AdaptiveBudgetExhaustionError("campaign must be an exact ResearchCampaign")

    try:
        accounting = build_adaptive_campaign_accounting(objective, campaign)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AdaptiveBudgetExhaustionError("adaptive campaign accounting failed closed") from exc

    if objective.budget_exhaustion_disposition is not BudgetExhaustionDisposition.BLOCKED:
        raise AdaptiveBudgetExhaustionError(
            "frozen objective budget exhaustion disposition must be BLOCKED"
        )

    allowed_tiers = set(objective.evaluation_tier_policy.allowed_tiers)
    dispositions = tuple(_derive_tier_disposition(item, allowed_tiers) for item in accounting.tiers)
    return AdaptiveBudgetDispositionReport(
        objective_sha256=accounting.objective_sha256,
        campaign_sha256=accounting.campaign_sha256,
        accounting_sha256=accounting.content_sha256,
        tiers=dispositions,
    )


def require_adaptive_tier_available(
    objective: ResearchObjectiveContract,
    campaign: ResearchCampaign,
    tier: EvaluationTier,
) -> AdaptiveTierDisposition:
    """Return an available tier snapshot or reject further use when it is blocked."""
    if type(tier) is not EvaluationTier or tier not in _ADAPTIVE_TIERS:
        raise AdaptiveBudgetExhaustionError("tier must be SEARCH or REPLICATION")
    report = build_adaptive_budget_disposition(objective, campaign)._validated_snapshot()
    disposition = next(item for item in report.tiers if item.tier is tier)
    if disposition.state is AdaptiveTierUseState.BLOCKED:
        reasons = ",".join(reason.value for reason in disposition.reasons)
        raise AdaptiveBudgetExhaustionError(f"adaptive tier {tier.name} is BLOCKED: {reasons}")
    return AdaptiveTierDisposition._validated_snapshot(disposition)


def _derive_tier_disposition(
    accounting: AdaptiveTierAccounting,
    allowed_tiers: set[EvaluationTier],
) -> AdaptiveTierDisposition:
    if type(accounting) is not AdaptiveTierAccounting:
        raise AdaptiveBudgetExhaustionError(
            "accounting row must be an exact AdaptiveTierAccounting"
        )
    try:
        snapshot = AdaptiveTierAccounting._validated_snapshot(accounting)
    except (AttributeError, TypeError, ValueError) as exc:
        raise AdaptiveBudgetExhaustionError(
            "adaptive tier accounting failed canonical revalidation"
        ) from exc

    queries_remaining = snapshot.queries_remaining
    result_exposures_remaining = snapshot.result_exposures_remaining
    reasons: list[AdaptiveBudgetBlockReason] = []
    if snapshot.tier not in allowed_tiers:
        queries_remaining = 0
        result_exposures_remaining = 0
        reasons.append(AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED)
    else:
        if queries_remaining == 0:
            reasons.append(AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED)
        if result_exposures_remaining == 0:
            reasons.append(AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED)
    reasons.sort(key=lambda reason: reason.value)
    state = AdaptiveTierUseState.BLOCKED if reasons else AdaptiveTierUseState.AVAILABLE
    return AdaptiveTierDisposition(
        tier=snapshot.tier,
        state=state,
        reasons=tuple(reasons),
        queries_remaining=queries_remaining,
        result_exposures_remaining=result_exposures_remaining,
    )


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise AdaptiveBudgetExhaustionError(f"{label} must be a non-negative exact integer")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise AdaptiveBudgetExhaustionError(f"{label} must be 64 lowercase hex")
