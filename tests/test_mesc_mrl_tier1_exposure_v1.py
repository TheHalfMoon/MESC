"""MRL-0302 tests for bounded Tier 1 result exposure."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_research_objective_v1 import AdaptiveQueryBudget, EvaluationTier
from medscale.mesc._mrl_tier1_exposure_v1 import (
    Tier1ExposureError,
    Tier1ExposurePolicy,
    Tier1ExposureUsage,
    consume_tier1_query,
    record_tier1_exposure,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract
from test_mesc_mrl_research_objective_v1 import _objective


def _policy() -> Tier1ExposurePolicy:
    return Tier1ExposurePolicy(
        tier_contract=TierEvaluationContract(
            objective=_objective(),
            tier=EvaluationTier.SEARCH,
        ),
    )


def test_policy_derives_exact_frozen_search_limits_and_never_authorizes() -> None:
    policy = _policy()

    assert policy.query_ceiling == 5
    assert policy.max_exposures == 5
    assert policy.allowed_result_fields == ("aggregate_score", "cost_microunits")
    assert policy.can_expand_budget is False
    assert policy.to_dict()["can_authorize"] is False
    assert policy.to_dict()["can_expand_budget"] is False


def test_query_consumption_stops_exactly_at_frozen_ceiling() -> None:
    policy = _policy()
    usage = Tier1ExposureUsage()

    for expected in range(1, 6):
        usage = consume_tier1_query(policy, usage)
        assert usage.queries_used == expected

    with pytest.raises(Tier1ExposureError, match="query budget is exhausted"):
        consume_tier1_query(policy, usage)


def test_result_exposure_accepts_only_frozen_aggregate_fields() -> None:
    policy = _policy()
    usage = record_tier1_exposure(
        policy,
        Tier1ExposureUsage(),
        ("aggregate_score", "cost_microunits"),
    )

    assert usage.exposures_used == 1
    with pytest.raises(Tier1ExposureError, match="outside the frozen allow-list"):
        record_tier1_exposure(policy, usage, ("item_level_result",))


def test_result_exposure_stops_exactly_at_frozen_ceiling() -> None:
    policy = _policy()
    usage = Tier1ExposureUsage()

    for expected in range(1, 6):
        usage = record_tier1_exposure(policy, usage, ("aggregate_score",))
        assert usage.exposures_used == expected

    with pytest.raises(Tier1ExposureError, match="exposure budget is exhausted"):
        record_tier1_exposure(policy, usage, ("aggregate_score",))


def test_policy_identity_tracks_material_objective_budget_changes() -> None:
    original = _policy()
    changed_objective = replace(
        _objective(),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=4, tier_2_queries=0),
    )
    changed = Tier1ExposurePolicy(
        tier_contract=TierEvaluationContract(
            objective=changed_objective,
            tier=EvaluationTier.SEARCH,
        ),
    )

    assert original.query_ceiling == 5
    assert changed.query_ceiling == 4
    assert original.to_dict()["tier_contract_sha256"] != changed.to_dict()["tier_contract_sha256"]


def test_post_construction_objective_mutation_cannot_expand_bound_tier1_budget() -> None:
    policy = _policy()
    object.__setattr__(
        policy.tier_contract.objective.adaptive_query_budget,
        "tier_1_queries",
        50,
    )

    with pytest.raises(Tier1ExposureError, match="identity changed after policy creation"):
        _ = policy.query_ceiling
    with pytest.raises(Tier1ExposureError, match="identity changed after policy creation"):
        consume_tier1_query(policy, Tier1ExposureUsage())


def test_non_search_contract_and_fabricated_usage_fail_closed() -> None:
    with pytest.raises(Tier1ExposureError, match="requires SEARCH tier"):
        Tier1ExposurePolicy(
            tier_contract=TierEvaluationContract(
                objective=_objective(),
                tier=EvaluationTier.SEALED,
            ),
        )

    with pytest.raises(Tier1ExposureError, match="usage must be an exact"):
        consume_tier1_query(_policy(), cast(Tier1ExposureUsage, object()))


def test_mutated_negative_usage_cannot_create_extra_query_or_exposure_capacity() -> None:
    policy = _policy()
    query_usage = Tier1ExposureUsage(queries_used=5)
    object.__setattr__(query_usage, "queries_used", -1)

    with pytest.raises(Tier1ExposureError, match="queries_used must be a non-negative"):
        consume_tier1_query(policy, query_usage)

    exposure_usage = Tier1ExposureUsage(exposures_used=5)
    object.__setattr__(exposure_usage, "exposures_used", -1)

    with pytest.raises(Tier1ExposureError, match="exposures_used must be a non-negative"):
        record_tier1_exposure(policy, exposure_usage, ("aggregate_score",))


def test_usage_cannot_start_beyond_frozen_limits_or_use_mutable_field_collection() -> None:
    policy = _policy()

    with pytest.raises(Tier1ExposureError, match="query usage exceeds"):
        consume_tier1_query(policy, Tier1ExposureUsage(queries_used=6))
    with pytest.raises(Tier1ExposureError, match="exposure usage exceeds"):
        record_tier1_exposure(
            policy,
            Tier1ExposureUsage(exposures_used=6),
            ("aggregate_score",),
        )
    with pytest.raises(Tier1ExposureError, match="result_fields must be an exact tuple"):
        record_tier1_exposure(
            policy,
            Tier1ExposureUsage(),
            cast(tuple[str, ...], ["aggregate_score"]),
        )
