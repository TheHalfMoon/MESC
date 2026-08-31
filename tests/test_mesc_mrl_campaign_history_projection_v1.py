"""MRL-0401 tests for the append-only campaign-history projection."""

from __future__ import annotations

import pytest

import medscale.mesc._mrl_campaign_history_projection_v1 as history_module
from medscale.mesc._mrl_campaign_history_projection_v1 import (
    CampaignHistoryProjectionError,
    build_campaign_history_projection,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign
from test_mesc_mrl_research_campaign_v1 import _campaign, _resources, _tier_usage


def test_single_snapshot_projection_is_deterministic_and_non_authoritative() -> None:
    campaign = _campaign()

    first = build_campaign_history_projection(campaign)
    second = build_campaign_history_projection(campaign)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.latest_campaign_sha256 == campaign.content_sha256
    assert first.entries[0].parent_campaign_sha256 is None
    assert first.entries[0].campaign_sha256 == campaign.content_sha256
    assert first.can_authorize is False
    assert first.semantic_dict()["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
    assert first.semantic_dict()["can_authorize"] is False


def test_child_projection_preserves_parent_projection_as_exact_prefix() -> None:
    parent = _campaign()
    child = _campaign(
        parent=parent,
        resources=_resources(wall_clock_seconds=11),
        tier_usage=_tier_usage(search_queries=3),
    )

    parent_projection = build_campaign_history_projection(parent)
    child_projection = build_campaign_history_projection(child)

    assert child_projection.entries[:-1] == parent_projection.entries
    assert child_projection.entries[-1].sequence_index == 1
    assert child_projection.entries[-1].parent_campaign_sha256 == parent.content_sha256
    assert child_projection.entries[-1].campaign_sha256 == child.content_sha256
    assert child_projection.latest_campaign_sha256 == child.content_sha256


def test_projection_preserves_negative_history_and_current_navigation_fields() -> None:
    campaign = _campaign()

    projection = build_campaign_history_projection(campaign)
    entry = projection.entries[0]

    assert entry.branch_outcome_node_ids == ("decision-a",)
    assert entry.current_frontier_node_ids == ("decision-a",)
    assert entry.node_ids == (
        "decision-a",
        "hypothesis-a",
        "plan-a",
        "receipt-a",
    )
    assert entry.procedure_candidate_node_ids == ()


def test_projection_content_identity_changes_when_history_appends() -> None:
    parent = _campaign()
    child = _campaign(
        parent=parent,
        resources=_resources(wall_clock_seconds=12),
        tier_usage=_tier_usage(search_queries=4),
    )

    parent_projection = build_campaign_history_projection(parent)
    child_projection = build_campaign_history_projection(child)

    assert child_projection.content_sha256 != parent_projection.content_sha256
    assert len(child_projection.entries) == len(parent_projection.entries) + 1


def test_projection_uses_one_campaign_snapshot_if_live_campaign_drifts_mid_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = _campaign()
    original_campaign_sha256 = campaign.content_sha256
    original_chain = history_module._oldest_first_chain
    mutation_performed = False

    def mutate_live_campaign_then_walk_snapshot(
        snapshot: ResearchCampaign,
    ) -> tuple[ResearchCampaign, ...]:
        nonlocal mutation_performed
        if not mutation_performed:
            mutation_performed = True
            object.__setattr__(
                campaign.cumulative_resource_usage,
                "wall_clock_seconds",
                campaign.cumulative_resource_usage.wall_clock_seconds + 1,
            )
        return original_chain(snapshot)

    monkeypatch.setattr(
        history_module,
        "_oldest_first_chain",
        mutate_live_campaign_then_walk_snapshot,
    )

    projection = build_campaign_history_projection(campaign)

    assert mutation_performed is True
    assert projection.latest_campaign_sha256 == original_campaign_sha256
    assert campaign.content_sha256 != original_campaign_sha256


def test_mutated_history_entry_fails_closed_on_latest_and_hash_views() -> None:
    projection = build_campaign_history_projection(_campaign())
    object.__setattr__(projection.entries[0], "campaign_sha256", "invalid")

    with pytest.raises(CampaignHistoryProjectionError, match="64 lowercase hex"):
        _ = projection.latest_campaign_sha256
    with pytest.raises(CampaignHistoryProjectionError, match="64 lowercase hex"):
        _ = projection.content_sha256


def test_valid_history_entry_identity_mutation_fails_closed() -> None:
    projection = build_campaign_history_projection(_campaign())
    object.__setattr__(projection.entries[0], "campaign_sha256", "f" * 64)

    with pytest.raises(CampaignHistoryProjectionError, match="identity changed"):
        projection.entries[0].to_dict()
    with pytest.raises(CampaignHistoryProjectionError, match="identity changed"):
        _ = projection.content_sha256


def test_mutated_projection_identity_fails_closed_on_semantic_and_hash_views() -> None:
    projection = build_campaign_history_projection(_campaign())
    object.__setattr__(projection, "objective_sha256", "invalid")

    with pytest.raises(CampaignHistoryProjectionError, match="64 lowercase hex"):
        projection.semantic_dict()
    with pytest.raises(CampaignHistoryProjectionError, match="64 lowercase hex"):
        _ = projection.content_sha256


def test_valid_projection_identity_mutation_fails_closed() -> None:
    projection = build_campaign_history_projection(_campaign())
    object.__setattr__(projection, "objective_sha256", "f" * 64)

    with pytest.raises(CampaignHistoryProjectionError, match="identity changed"):
        projection.semantic_dict()
    with pytest.raises(CampaignHistoryProjectionError, match="identity changed"):
        _ = projection.content_sha256


def test_corrupted_campaign_chain_fails_closed() -> None:
    parent = _campaign()
    child = _campaign(
        parent=parent,
        resources=_resources(wall_clock_seconds=11),
        tier_usage=_tier_usage(search_queries=3),
    )
    object.__setattr__(child, "campaign_id", "corrupted-campaign")

    with pytest.raises(CampaignHistoryProjectionError, match="canonical revalidation"):
        build_campaign_history_projection(child)


def test_non_campaign_input_fails_closed() -> None:
    with pytest.raises(CampaignHistoryProjectionError, match="exact ResearchCampaign"):
        build_campaign_history_projection(object())  # type: ignore[arg-type]
