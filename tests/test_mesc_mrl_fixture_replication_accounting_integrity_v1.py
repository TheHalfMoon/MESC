"""Adversarial MRL-0205 tests for receipt-derived campaign accounting."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_replication_v1 import (
    FixtureReplicationError,
    apply_fixture_replication,
    assess_fixture_replication,
    request_fixture_replication,
    start_fixture_campaign,
)
from medscale.mesc._mrl_research_campaign_v1 import CampaignTierTotals
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from test_mesc_mrl_fixture_replication_v1 import _complete


def _apply_with_parent(parent):
    primary = _complete("primary-accounting")
    replica = _complete("replica-accounting")
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)
    return apply_fixture_replication(parent, primary, request, replica, outcome)


def test_underreported_parent_resource_accounting_fails_closed() -> None:
    primary = _complete("primary-accounting")
    campaign = start_fixture_campaign("fixture-accounting-campaign", primary)
    forged = replace(
        campaign,
        cumulative_resource_usage=replace(
            campaign.cumulative_resource_usage,
            storage_bytes=0,
            evaluator_invocations=0,
        ),
    )

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived initial campaign",
    ):
        _apply_with_parent(forged)


def test_underreported_parent_result_exposure_accounting_fails_closed() -> None:
    primary = _complete("primary-accounting")
    campaign = start_fixture_campaign("fixture-accounting-campaign", primary)
    forged = replace(
        campaign,
        cumulative_tier_usage=tuple(
            replace(item, result_exposures_used=0)
            if item.tier is EvaluationTier.DEVELOPMENT
            else item
            for item in campaign.cumulative_tier_usage
        ),
    )

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived initial campaign",
    ):
        _apply_with_parent(forged)


def test_parent_adaptive_query_accounting_cannot_diverge_from_receipts() -> None:
    primary = _complete("primary-accounting")
    campaign = start_fixture_campaign("fixture-accounting-campaign", primary)

    # Canonical MRL-0204 receipts are Tier 0 DEVELOPMENT only and hard-code
    # queries_used=0, so a negative under-report cannot be represented. The
    # adversarial case is therefore any caller-injected adaptive-query total.
    forged = replace(
        campaign,
        cumulative_tier_usage=tuple(
            sorted(
                (
                    *campaign.cumulative_tier_usage,
                    CampaignTierTotals(
                        tier=EvaluationTier.SEARCH,
                        queries_used=1,
                        result_exposures_used=0,
                    ),
                ),
                key=lambda item: int(item.tier),
            )
        ),
    )

    with pytest.raises(
        FixtureReplicationError,
        match="exact receipt-derived initial campaign",
    ):
        _apply_with_parent(forged)
