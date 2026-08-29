"""MRL-0309 tests for fail-closed adaptive-budget exhaustion enforcement."""

from __future__ import annotations

from dataclasses import fields
from typing import cast

import pytest

from medscale.mesc._mrl_adaptive_budget_exhaustion_v1 import (
    AdaptiveBudgetBlockReason,
    AdaptiveBudgetExhaustionError,
    AdaptiveTierDisposition,
    AdaptiveTierUseState,
    build_adaptive_budget_disposition,
    require_adaptive_tier_available,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContract,
)
from test_mesc_mrl_adaptive_campaign_accounting_v1 import _campaign
from test_mesc_mrl_research_objective_v1 import _objective
from test_mesc_mrl_tier_evaluation_contract_v1 import _all_tier_objective


def test_available_adaptive_tiers_preserve_exact_remaining_capacity() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)
    first = build_adaptive_budget_disposition(objective, campaign)
    second = build_adaptive_budget_disposition(objective, campaign)
    search, replication = first.tiers

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.objective_sha256 == objective.content_sha256
    assert first.campaign_sha256 == campaign.content_sha256
    assert first.blocked_tiers == ()
    assert search.state is AdaptiveTierUseState.AVAILABLE
    assert search.reasons == ()
    assert (search.queries_remaining, search.result_exposures_remaining) == (2, 3)
    assert replication.state is AdaptiveTierUseState.AVAILABLE
    assert (replication.queries_remaining, replication.result_exposures_remaining) == (1, 1)


def test_query_budget_exhaustion_blocks_further_search_use() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5)
    report = build_adaptive_budget_disposition(objective, campaign)
    search = report.tiers[0]

    assert search.state is AdaptiveTierUseState.BLOCKED
    assert search.reasons == (AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED,)
    assert search.queries_remaining == 0
    assert report.blocked_tiers == (EvaluationTier.SEARCH,)
    with pytest.raises(AdaptiveBudgetExhaustionError, match="SEARCH is BLOCKED"):
        require_adaptive_tier_available(objective, campaign, EvaluationTier.SEARCH)


def test_result_exposure_exhaustion_blocks_further_search_use() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_exposures=5)
    search = build_adaptive_budget_disposition(objective, campaign).tiers[0]

    assert search.state is AdaptiveTierUseState.BLOCKED
    assert search.reasons == (AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED,)
    assert search.result_exposures_remaining == 0


def test_multiple_exhausted_ceilings_have_deterministic_block_reasons() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(
        objective,
        search_queries=5,
        search_exposures=5,
        replication_queries=2,
        replication_exposures=2,
    )
    report = build_adaptive_budget_disposition(objective, campaign)

    assert report.blocked_tiers == (
        EvaluationTier.SEARCH,
        EvaluationTier.REPLICATION,
    )
    for disposition in report.tiers:
        assert disposition.state is AdaptiveTierUseState.BLOCKED
        assert disposition.reasons == (
            AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED,
            AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED,
        )


def test_disallowed_adaptive_tier_is_blocked_without_fabricating_budget_exhaustion() -> None:
    objective = _objective()
    campaign = _campaign(objective, include_replication=False)
    report = build_adaptive_budget_disposition(objective, campaign)
    replication = report.tiers[1]

    assert replication.tier is EvaluationTier.REPLICATION
    assert replication.state is AdaptiveTierUseState.BLOCKED
    assert replication.reasons == (AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED,)
    assert replication.queries_remaining == 0
    assert replication.result_exposures_remaining == 0


def test_block_reasons_must_exactly_match_remaining_capacity() -> None:
    with pytest.raises(AdaptiveBudgetExhaustionError, match="exhausted adaptive capacities"):
        AdaptiveTierDisposition(
            tier=EvaluationTier.SEARCH,
            state=AdaptiveTierUseState.BLOCKED,
            reasons=(AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED,),
            queries_remaining=1,
            result_exposures_remaining=1,
        )
    with pytest.raises(AdaptiveBudgetExhaustionError, match="zero remaining adaptive capacity"):
        AdaptiveTierDisposition(
            tier=EvaluationTier.REPLICATION,
            state=AdaptiveTierUseState.BLOCKED,
            reasons=(AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED,),
            queries_remaining=1,
            result_exposures_remaining=0,
        )


def test_available_tier_guard_returns_exact_non_authoritative_disposition() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)

    search = require_adaptive_tier_available(objective, campaign, EvaluationTier.SEARCH)

    assert search.tier is EvaluationTier.SEARCH
    assert search.state is AdaptiveTierUseState.AVAILABLE


def test_usage_beyond_frozen_ceiling_fails_closed_before_disposition() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=6)

    with pytest.raises(AdaptiveBudgetExhaustionError, match="accounting failed closed"):
        build_adaptive_budget_disposition(objective, campaign)


def test_mutated_tier_disposition_fails_closed_before_report_views() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)
    report = build_adaptive_budget_disposition(objective, campaign)
    object.__setattr__(report.tiers[0], "queries_remaining", 0)

    with pytest.raises(AdaptiveBudgetExhaustionError, match="AVAILABLE tier must retain"):
        _ = report.blocked_tiers
    with pytest.raises(AdaptiveBudgetExhaustionError, match="AVAILABLE tier must retain"):
        _ = report.content_sha256


def test_mutated_block_reason_or_report_identity_fails_closed() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5)
    report = build_adaptive_budget_disposition(objective, campaign)
    object.__setattr__(report.tiers[0], "queries_remaining", 1)

    with pytest.raises(AdaptiveBudgetExhaustionError, match="exhausted adaptive capacities"):
        report.semantic_dict()

    fresh = build_adaptive_budget_disposition(objective, campaign)
    object.__setattr__(fresh, "accounting_sha256", "invalid")
    with pytest.raises(AdaptiveBudgetExhaustionError, match="64 lowercase hex"):
        _ = fresh.content_sha256


def test_disposition_cannot_expand_budget_or_request_additional_sealed_detail() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5)
    objective_sha256 = objective.content_sha256
    report = build_adaptive_budget_disposition(objective, campaign)
    payload = report.to_dict()

    assert tuple(field.name for field in fields(type(report))) == (
        "objective_sha256",
        "campaign_sha256",
        "accounting_sha256",
        "tiers",
    )
    assert objective.content_sha256 == objective_sha256
    assert report.can_authorize is False
    assert report.can_expand_budget is False
    assert report.can_request_additional_sealed_detail is False
    assert payload["can_authorize"] is False
    assert payload["can_expand_budget"] is False
    assert payload["can_request_additional_sealed_detail"] is False
    assert b"PROMOTED" not in report.semantic_bytes
    assert b'"can_request_additional_sealed_detail":false' in report.semantic_bytes


def test_exact_contract_and_tier_types_are_required() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)

    with pytest.raises(
        AdaptiveBudgetExhaustionError,
        match="exact ResearchObjectiveContract",
    ):
        build_adaptive_budget_disposition(
            cast(ResearchObjectiveContract, object()),
            campaign,
        )
    with pytest.raises(AdaptiveBudgetExhaustionError, match="exact ResearchCampaign"):
        build_adaptive_budget_disposition(
            objective,
            cast(ResearchCampaign, object()),
        )
    with pytest.raises(AdaptiveBudgetExhaustionError, match="SEARCH or REPLICATION"):
        require_adaptive_tier_available(
            objective,
            campaign,
            EvaluationTier.SEALED,
        )
