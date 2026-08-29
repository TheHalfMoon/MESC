"""MRL-0303 tests for the frozen Tier 2 replication-set policy."""

from __future__ import annotations

from dataclasses import fields, replace
from typing import cast

import pytest

from medscale.mesc._mrl_replication_set_policy_v1 import (
    ReplicationSetMember,
    ReplicationSetPolicy,
    ReplicationSetPolicyError,
    build_replication_set,
)
from medscale.mesc._mrl_research_objective_v1 import AdaptiveQueryBudget, TierResultExposure
from test_mesc_mrl_tier_evaluation_contract_v1 import _all_tier_objective


def _policy() -> ReplicationSetPolicy:
    return ReplicationSetPolicy(objective=_all_tier_objective())


def _members(count: int = 2) -> tuple[ReplicationSetMember, ...]:
    return tuple(
        ReplicationSetMember(
            member_id=f"replica-{index}",
            artifact_sha256=f"{index:064x}",
        )
        for index in range(1, count + 1)
    )


def test_policy_derives_frozen_tier2_bounds_and_never_authorizes() -> None:
    policy = _policy()

    assert policy.max_replication_queries == 2
    assert policy.replication_exposure.max_exposures == 2
    assert policy.replication_exposure.allowed_result_fields == ("aggregate_score",)
    assert set(policy.replication_exposure.allowed_result_fields).issubset(
        policy.search_exposure.allowed_result_fields,
    )
    assert policy.can_authorize is False
    assert policy.to_dict()["can_authorize"] is False


def test_replication_set_is_immutable_and_bounded_by_query_ceiling() -> None:
    policy = _policy()
    replication_set = build_replication_set(policy, _members())

    assert len(replication_set.members) == 2
    assert replication_set.max_replication_queries == 2
    assert replication_set.allowed_summary_fields == ("aggregate_score",)
    assert replication_set.max_summary_exposures == 2
    assert replication_set.to_dict()["can_authorize"] is False

    with pytest.raises(ReplicationSetPolicyError, match="exceeds the frozen Tier 2"):
        build_replication_set(policy, _members(3))


def test_tier2_cannot_expose_more_fields_than_tier1() -> None:
    objective = _all_tier_objective()
    policies = list(objective.tier_result_exposure_policy)
    policies[2] = TierResultExposure(
        tier=policies[2].tier,
        max_exposures=policies[2].max_exposures,
        allowed_result_fields=("aggregate_score", "sealed_detail"),
    )
    changed = replace(objective, tier_result_exposure_policy=tuple(policies))

    with pytest.raises(ReplicationSetPolicyError, match="subset of Tier 1"):
        ReplicationSetPolicy(objective=changed)


def test_tier2_exposure_ceiling_cannot_exceed_tier1() -> None:
    objective = _all_tier_objective()
    policies = list(objective.tier_result_exposure_policy)
    policies[2] = TierResultExposure(
        tier=policies[2].tier,
        max_exposures=6,
        allowed_result_fields=("aggregate_score",),
    )
    changed = replace(objective, tier_result_exposure_policy=tuple(policies))

    with pytest.raises(ReplicationSetPolicyError, match="cannot exceed Tier 1"):
        ReplicationSetPolicy(objective=changed)


def test_replication_members_must_be_distinct_sorted_and_exact() -> None:
    first, second = _members()

    with pytest.raises(ReplicationSetPolicyError, match="sorted and identity-unique"):
        build_replication_set(_policy(), (second, first))
    with pytest.raises(ReplicationSetPolicyError, match="distinct artifacts"):
        build_replication_set(
            _policy(),
            (first, replace(second, artifact_sha256=first.artifact_sha256)),
        )
    with pytest.raises(ReplicationSetPolicyError, match="members must be an exact tuple"):
        build_replication_set(_policy(), cast(tuple[ReplicationSetMember, ...], [first]))


def test_mutated_policy_objective_cannot_expand_frozen_replication_budget() -> None:
    policy = _policy()
    object.__setattr__(
        policy.objective,
        "adaptive_query_budget",
        AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=3),
    )

    with pytest.raises(ReplicationSetPolicyError, match="objective identity changed"):
        _ = policy.max_replication_queries
    with pytest.raises(ReplicationSetPolicyError, match="objective identity changed"):
        build_replication_set(policy, _members(3))


def test_policy_construction_identity_is_not_reachable_as_mutable_state() -> None:
    policy = _policy()

    assert tuple(field.name for field in fields(ReplicationSetPolicy)) == ("objective",)
    with pytest.raises(AttributeError):
        object.__setattr__(policy, "_bound_objective_sha256", "a" * 64)


def test_mutated_member_fails_closed_before_replication_set_serialization() -> None:
    members = _members()
    replication_set = build_replication_set(_policy(), members)
    object.__setattr__(members[0], "artifact_sha256", "invalid")

    with pytest.raises(ReplicationSetPolicyError, match="artifact_sha256"):
        replication_set.to_dict()


def test_invalid_member_and_objective_types_fail_closed() -> None:
    with pytest.raises(ReplicationSetPolicyError, match="member_id"):
        ReplicationSetMember(member_id="Replica-1", artifact_sha256="a" * 64)
    with pytest.raises(ReplicationSetPolicyError, match="artifact_sha256"):
        ReplicationSetMember(member_id="replica-1", artifact_sha256="A" * 64)
    with pytest.raises(ReplicationSetPolicyError, match="exact ResearchObjectiveContract"):
        ReplicationSetPolicy(objective=object())  # type: ignore[arg-type]


def test_policy_identity_tracks_frozen_objective() -> None:
    policy = _policy()

    assert policy.to_dict()["objective_sha256"] == _all_tier_objective().content_sha256
    assert (
        policy.to_dict()["search_tier_contract_sha256"]
        != policy.to_dict()["replication_tier_contract_sha256"]
    )
