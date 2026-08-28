"""MRL-0211 adversarial proof for the frozen known-failure retry ceiling."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import (
    FixtureLoopResult,
    decide_fixture_experiment,
)
from medscale.mesc._mrl_fixture_replication_v1 import (
    FixtureReplicationError,
    apply_fixture_replication,
    assess_fixture_replication,
    request_fixture_replication,
    start_fixture_campaign,
)
from test_mesc_mrl_fixture_replication_v1 import _complete


def _with_known_failure_retry(result: FixtureLoopResult) -> FixtureLoopResult:
    plan = result.receipt.binding.plan
    objective = replace(
        plan.objective,
        resource_budget=replace(
            plan.objective.resource_budget,
            retries=2,
            known_failure_retries=1,
        ),
    )
    hypothesis = replace(
        plan.hypothesis,
        objective_sha256=objective.content_sha256,
    )
    bounded_plan = replace(
        plan,
        objective=objective,
        hypothesis=hypothesis,
        resource_ceiling=replace(
            plan.resource_ceiling,
            retries=1,
            known_failure_retries=1,
        ),
    )
    proposal = replace(
        result.proposal,
        experiment_plan_sha256=bounded_plan.content_sha256,
    )
    receipt = replace(
        result.receipt,
        binding=replace(result.receipt.binding, plan=bounded_plan),
        observed_resource_use=replace(
            result.receipt.observed_resource_use,
            retries=1,
            known_failure_retries=1,
        ),
    )
    decision = decide_fixture_experiment(proposal, result.observation, receipt)
    return FixtureLoopResult(
        proposal=proposal,
        observation=result.observation,
        receipt=receipt,
        decision=decision,
    )


def test_campaign_known_failure_retry_ceiling_cannot_be_exceeded() -> None:
    primary = _with_known_failure_retry(_complete("known-failure-primary"))
    replica = _with_known_failure_retry(_complete("known-failure-replica"))
    campaign = start_fixture_campaign("known-failure-campaign", primary)
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)

    assert campaign.cumulative_resource_usage.retries == 1
    assert campaign.cumulative_resource_usage.known_failure_retries == 1

    with pytest.raises(
        FixtureReplicationError,
        match="fixture campaign exceeds frozen known_failure_retries budget",
    ):
        apply_fixture_replication(campaign, primary, request, replica, outcome)
