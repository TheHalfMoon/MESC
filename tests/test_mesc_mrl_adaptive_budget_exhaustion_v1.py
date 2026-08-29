"""MRL-0309 tests for fail-closed adaptive-budget exhaustion enforcement."""

from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._mrl_adaptive_budget_exhaustion_v1 import (
    AdaptiveBudgetBlockReason,
    AdaptiveBudgetEnforcementError,
    AdaptiveBudgetEnforcementReport,
    AdaptiveTierDisposition,
    enforce_adaptive_budget_exhaustion,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign
from medscale.mesc._mrl_research_objective_v1 import ResearchObjectiveContract
from test_mesc_mrl_adaptive_campaign_accounting_v1 import _campaign
from test_mesc_mrl_research_objective_v1 import _objective
from test_mesc_mrl_tier_evaluation_contract_v1 import _all_tier_objective


def test_available_adaptive_tiers_preserve_frozen_remaining_capacity() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)
    report = enforce_adaptive_budget_exhaustion(objective, campaign)
    search, replication = report.tiers

    assert search.disposition is AdaptiveTierDisposition.AVAILABLE
    assert search.can_use_adaptive_tier is True
    assert search.queries_remaining == 2
    assert search.result_exposures_remaining == 3
    assert search.block_reasons == ()
    assert replication.disposition is AdaptiveTierDisposition.AVAILABLE
    assert replication.can_use_adaptive_tier is True
    assert replication.queries_remaining == 1
    assert replication.result_exposures_remaining == 1


def test_exhausted_query_budget_blocks_further_tier_use() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5)
    report = enforce_adaptive_budget_exhaustion(objective, campaign)
    search = report.tiers[0]

    assert search.disposition is AdaptiveTierDisposition.BLOCKED
    assert search.can_use_adaptive_tier is False
    assert search.queries_remaining == 0
    assert search.block_reasons == (
        AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED,
    )


def test_exhausted_result_exposure_budget_blocks_further_tier_use() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, replication_exposures=2)
    report = enforce_adaptive_budget_exhaustion(objective, campaign)
    replication = report.tiers[1]

    assert replication.disposition is AdaptiveTierDisposition.BLOCKED
    assert replication.can_use_adaptive_tier is False
    assert replication.result_exposures_remaining == 0
    assert replication.block_reasons == (
        AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED,
    )


def test_both_exhausted_budgets_are_preserved_as_sorted_block_reasons() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5, search_exposures=5)
    search = enforce_adaptive_budget_exhaustion(objective, campaign).tiers[0]

    assert search.disposition is AdaptiveTierDisposition.BLOCKED
    assert search.block_reasons == (
        AdaptiveBudgetBlockReason.QUERY_BUDGET_EXHAUSTED,
        AdaptiveBudgetBlockReason.RESULT_EXPOSURE_BUDGET_EXHAUSTED,
    )


def test_disallowed_adaptive_tier_is_blocked_without_reinterpreting_zero_budget() -> None:
    objective = _objective()
    campaign = _campaign(
        objective,
        search_queries=1,
        search_exposures=1,
        include_replication=False,
    )
    replication = enforce_adaptive_budget_exhaustion(objective, campaign).tiers[1]

    assert replication.disposition is AdaptiveTierDisposition.BLOCKED
    assert replication.can_use_adaptive_tier is False
    assert replication.queries_remaining == 0
    assert replication.result_exposures_remaining == 0
    assert replication.block_reasons == (
        AdaptiveBudgetBlockReason.TIER_NOT_ALLOWED,
    )


def test_report_is_deterministic_non_authoritative_and_cannot_expand_or_escape() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=5)
    first = enforce_adaptive_budget_exhaustion(objective, campaign)
    second = enforce_adaptive_budget_exhaustion(objective, campaign)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.to_dict()["content_sha256"] == first.content_sha256
    assert first.can_authorize is False
    assert first.can_expand_budget is False
    assert first.can_amend_objective is False
    assert first.can_request_additional_sealed_detail is False
    assert b'"can_expand_budget":false' in first.semantic_bytes
    assert b'"can_request_additional_sealed_detail":false' in first.semantic_bytes
    assert b"PROMOTED" not in first.semantic_bytes


def test_material_campaign_usage_change_changes_enforcement_identity() -> None:
    objective = _all_tier_objective()
    first = enforce_adaptive_budget_exhaustion(
        objective,
        _campaign(objective, search_queries=3),
    )
    second = enforce_adaptive_budget_exhaustion(
        objective,
        _campaign(objective, search_queries=4),
    )

    assert first.content_sha256 != second.content_sha256
    assert first.accounting_sha256 != second.accounting_sha256


def test_usage_beyond_ceiling_fails_closed_through_mrl_0308_accounting() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective, search_queries=6)

    with pytest.raises(ValueError, match="adaptive query usage exceeds frozen ceiling"):
        enforce_adaptive_budget_exhaustion(objective, campaign)


def test_exact_objective_and_campaign_types_are_required() -> None:
    objective = _all_tier_objective()

    with pytest.raises(
        AdaptiveBudgetEnforcementError,
        match="exact ResearchObjectiveContract",
    ):
        enforce_adaptive_budget_exhaustion(
            cast(ResearchObjectiveContract, object()),
            _campaign(objective),
        )
    with pytest.raises(AdaptiveBudgetEnforcementError, match="exact ResearchCampaign"):
        enforce_adaptive_budget_exhaustion(
            objective,
            cast(ResearchCampaign, object()),
        )


def test_direct_report_construction_requires_exact_adaptive_tier_order() -> None:
    objective = _all_tier_objective()
    report = enforce_adaptive_budget_exhaustion(objective, _campaign(objective))

    with pytest.raises(AdaptiveBudgetEnforcementError, match="SEARCH then REPLICATION"):
        AdaptiveBudgetEnforcementReport(
            objective_sha256=report.objective_sha256,
            campaign_sha256=report.campaign_sha256,
            accounting_sha256=report.accounting_sha256,
            tiers=tuple(reversed(report.tiers)),
        )
