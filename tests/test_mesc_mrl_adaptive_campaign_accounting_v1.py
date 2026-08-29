"""MRL-0308 tests for frozen adaptive-query and exposure accounting."""

from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._mrl_adaptive_campaign_accounting_v1 import (
    AdaptiveCampaignAccountingError,
    build_adaptive_campaign_accounting,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignResourceTotals,
    CampaignTierTotals,
    ResearchCampaign,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContract,
)
from test_mesc_mrl_research_objective_v1 import _objective
from test_mesc_mrl_tier_evaluation_contract_v1 import _all_tier_objective


def _resources() -> CampaignResourceTotals:
    return CampaignResourceTotals(
        wall_clock_seconds=0,
        compute_seconds=0,
        input_tokens=0,
        generated_tokens=0,
        storage_bytes=0,
        monetary_cost_microunits=0,
        retries=0,
        known_failure_retries=0,
        evaluator_invocations=0,
    )


def _campaign(
    objective: ResearchObjectiveContract,
    *,
    search_queries: int = 3,
    search_exposures: int = 2,
    replication_queries: int = 1,
    replication_exposures: int = 1,
    include_replication: bool = True,
) -> ResearchCampaign:
    tier_usage = [
        CampaignTierTotals(
            tier=EvaluationTier.SEARCH,
            queries_used=search_queries,
            result_exposures_used=search_exposures,
        )
    ]
    if include_replication:
        tier_usage.append(
            CampaignTierTotals(
                tier=EvaluationTier.REPLICATION,
                queries_used=replication_queries,
                result_exposures_used=replication_exposures,
            )
        )
    return ResearchCampaign(
        campaign_id="adaptive-accounting-campaign",
        objective_sha256=objective.content_sha256,
        parent=None,
        nodes=(),
        replications=(),
        retained_alternative_node_ids=(),
        branch_outcomes=(),
        current_frontier_node_ids=(),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=_resources(),
        cumulative_tier_usage=tuple(tier_usage),
    )


def test_accounting_binds_exact_campaign_objective_and_frozen_tier_ceilings() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)
    accounting = build_adaptive_campaign_accounting(objective, campaign)
    search, replication = accounting.tiers

    assert accounting.objective_sha256 == objective.content_sha256
    assert accounting.campaign_sha256 == campaign.content_sha256
    assert (search.tier, replication.tier) == (
        EvaluationTier.SEARCH,
        EvaluationTier.REPLICATION,
    )
    assert (search.queries_used, search.query_ceiling, search.queries_remaining) == (3, 5, 2)
    assert (
        search.result_exposures_used,
        search.result_exposure_ceiling,
        search.result_exposures_remaining,
    ) == (2, 5, 3)
    assert (
        replication.queries_used,
        replication.query_ceiling,
        replication.queries_remaining,
    ) == (1, 2, 1)
    assert (
        replication.result_exposures_used,
        replication.result_exposure_ceiling,
        replication.result_exposures_remaining,
    ) == (1, 2, 1)


def test_accounting_is_deterministic_non_authoritative_and_does_not_block() -> None:
    objective = _all_tier_objective()
    campaign = _campaign(objective)
    first = build_adaptive_campaign_accounting(objective, campaign)
    second = build_adaptive_campaign_accounting(objective, campaign)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.to_dict()["content_sha256"] == first.content_sha256
    assert first.can_authorize is False
    assert first.can_expand_budget is False
    assert b"PROMOTED" not in first.semantic_bytes
    assert b"BLOCKED" not in first.semantic_bytes


def test_missing_disallowed_replication_usage_accounts_as_zero() -> None:
    objective = _objective()
    campaign = _campaign(
        objective,
        search_queries=2,
        search_exposures=1,
        include_replication=False,
    )
    accounting = build_adaptive_campaign_accounting(objective, campaign)
    replication = accounting.tiers[1]

    assert replication.tier is EvaluationTier.REPLICATION
    assert replication.queries_used == 0
    assert replication.query_ceiling == 0
    assert replication.result_exposures_used == 0
    assert replication.result_exposure_ceiling == 0


@pytest.mark.parametrize(
    (
        "search_queries",
        "search_exposures",
        "replication_queries",
        "replication_exposures",
        "error",
    ),
    (
        (6, 2, 1, 1, "adaptive query usage exceeds"),
        (3, 6, 1, 1, "result exposure usage exceeds"),
        (3, 2, 3, 1, "adaptive query usage exceeds"),
        (3, 2, 1, 3, "result exposure usage exceeds"),
    ),
)
def test_usage_beyond_frozen_ceiling_fails_closed(
    search_queries: int,
    search_exposures: int,
    replication_queries: int,
    replication_exposures: int,
    error: str,
) -> None:
    objective = _all_tier_objective()
    campaign = _campaign(
        objective,
        search_queries=search_queries,
        search_exposures=search_exposures,
        replication_queries=replication_queries,
        replication_exposures=replication_exposures,
    )

    with pytest.raises(AdaptiveCampaignAccountingError, match=error):
        build_adaptive_campaign_accounting(objective, campaign)


def test_objective_identity_mismatch_and_fabricated_types_fail_closed() -> None:
    objective = _all_tier_objective()
    mismatched = ResearchCampaign(
        campaign_id="adaptive-accounting-campaign",
        objective_sha256="a" * 64,
        parent=None,
        nodes=(),
        replications=(),
        retained_alternative_node_ids=(),
        branch_outcomes=(),
        current_frontier_node_ids=(),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=_resources(),
        cumulative_tier_usage=(),
    )

    with pytest.raises(AdaptiveCampaignAccountingError, match="objective identity"):
        build_adaptive_campaign_accounting(objective, mismatched)
    with pytest.raises(AdaptiveCampaignAccountingError, match="objective must be an exact"):
        build_adaptive_campaign_accounting(
            cast(ResearchObjectiveContract, object()),
            _campaign(objective),
        )
    with pytest.raises(AdaptiveCampaignAccountingError, match="campaign must be an exact"):
        build_adaptive_campaign_accounting(
            objective,
            cast(ResearchCampaign, object()),
        )
