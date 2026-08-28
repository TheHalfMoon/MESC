"""Adversarial MRL-0205 tests for exact replication-cycle accounting."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import FixtureLoopResult
from medscale.mesc._mrl_fixture_replication_v1 import (
    FixtureReplicationCycle,
    FixtureReplicationError,
    apply_fixture_replication,
    assess_fixture_replication,
    request_fixture_replication,
    start_fixture_campaign,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign
from medscale.mesc._mrl_research_decision_v1 import ResearchDecision
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from test_mesc_mrl_fixture_replication_v1 import _complete


def _valid_cycle_parts() -> tuple[
    FixtureLoopResult,
    ResearchDecision,
    FixtureLoopResult,
    ResearchDecision,
    ResearchCampaign,
]:
    primary = _complete("primary-cycle-accounting")
    replica = _complete("replica-cycle-accounting")
    initial = start_fixture_campaign("fixture-cycle-accounting", primary)
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)
    campaign = apply_fixture_replication(initial, primary, request, replica, outcome)
    return primary, request, replica, outcome, campaign


def test_direct_cycle_rejects_underreported_child_resource_accounting() -> None:
    primary, request, replica, outcome, campaign = _valid_cycle_parts()
    assert campaign.parent is not None
    forged = replace(
        campaign,
        cumulative_resource_usage=campaign.parent.cumulative_resource_usage,
    )

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived transition",
    ):
        FixtureReplicationCycle(
            primary=primary,
            replication_decision=request,
            replica=replica,
            retained_decision=outcome,
            campaign=forged,
        )


def test_direct_cycle_rejects_underreported_child_result_exposure() -> None:
    primary, request, replica, outcome, campaign = _valid_cycle_parts()
    assert campaign.parent is not None
    parent_tiers = {item.tier: item for item in campaign.parent.cumulative_tier_usage}
    forged = replace(
        campaign,
        cumulative_tier_usage=tuple(
            replace(
                item,
                result_exposures_used=parent_tiers[item.tier].result_exposures_used,
            )
            if item.tier is EvaluationTier.DEVELOPMENT
            else item
            for item in campaign.cumulative_tier_usage
        ),
    )

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived transition",
    ):
        FixtureReplicationCycle(
            primary=primary,
            replication_decision=request,
            replica=replica,
            retained_decision=outcome,
            campaign=forged,
        )


def test_cycle_to_dict_revalidates_exact_child_transition_after_mutation() -> None:
    primary, request, replica, outcome, campaign = _valid_cycle_parts()
    cycle = FixtureReplicationCycle(
        primary=primary,
        replication_decision=request,
        replica=replica,
        retained_decision=outcome,
        campaign=campaign,
    )
    assert campaign.parent is not None
    forged = replace(
        campaign,
        cumulative_resource_usage=campaign.parent.cumulative_resource_usage,
    )
    object.__setattr__(cycle, "campaign", forged)

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived transition",
    ):
        cycle.to_dict()
