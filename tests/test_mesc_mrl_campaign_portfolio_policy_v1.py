"""MRL-0501 tests for deterministic campaign frontier/portfolio policy."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioPolicy,
    CampaignPortfolioPolicyError,
    build_campaign_portfolio_frontier,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcome,
    CampaignBranchOutcomeKind,
    CampaignNode,
    CampaignNodeKind,
    CampaignReplicationRelation,
    CampaignResourceTotals,
    ResearchCampaign,
)

_OBJECTIVE_SHA = "a" * 64


def _node(
    node_id: str,
    kind: CampaignNodeKind,
    artifact: str,
    parents: tuple[str, ...] = (),
) -> CampaignNode:
    return CampaignNode(
        node_id=node_id,
        kind=kind,
        artifact_sha256=artifact,
        parent_node_ids=parents,
    )


def _nodes(*, shared_root: bool = False) -> tuple[CampaignNode, ...]:
    decision_b_parents = ("plan-a",) if shared_root else ("plan-b",)
    return tuple(
        sorted(
            (
                _node(
                    "decision-a",
                    CampaignNodeKind.DECISION,
                    "b" * 64,
                    ("plan-a",),
                ),
                _node(
                    "decision-b",
                    CampaignNodeKind.DECISION,
                    "c" * 64,
                    decision_b_parents,
                ),
                _node(
                    "hypothesis-a",
                    CampaignNodeKind.HYPOTHESIS,
                    "d" * 64,
                ),
                _node(
                    "hypothesis-b",
                    CampaignNodeKind.HYPOTHESIS,
                    "e" * 64,
                ),
                _node(
                    "plan-a",
                    CampaignNodeKind.EXPERIMENT_PLAN,
                    "f" * 64,
                    ("hypothesis-a",),
                ),
                _node(
                    "plan-b",
                    CampaignNodeKind.EXPERIMENT_PLAN,
                    "1" * 64,
                    ("hypothesis-b",),
                ),
            ),
            key=lambda item: item.node_id,
        )
    )


def _resources() -> CampaignResourceTotals:
    return CampaignResourceTotals(
        wall_clock_seconds=10,
        compute_seconds=8,
        input_tokens=100,
        generated_tokens=20,
        storage_bytes=1_000,
        monetary_cost_microunits=500,
        retries=0,
        known_failure_retries=0,
        evaluator_invocations=2,
    )


def _campaign(
    *,
    shared_root: bool = False,
    outcomes: tuple[CampaignBranchOutcome, ...] = (),
    retained: tuple[str, ...] = (),
    replications: tuple[CampaignReplicationRelation, ...] = (),
) -> ResearchCampaign:
    return ResearchCampaign(
        campaign_id="fixture-portfolio",
        objective_sha256=_OBJECTIVE_SHA,
        parent=None,
        nodes=_nodes(shared_root=shared_root),
        replications=replications,
        retained_alternative_node_ids=retained,
        branch_outcomes=outcomes,
        current_frontier_node_ids=("decision-a", "decision-b"),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=_resources(),
        cumulative_tier_usage=(),
    )


def _policy(
    *,
    max_frontier_size: int = 2,
    min_distinct_hypothesis_roots: int = 2,
    max_frontier_per_hypothesis_root: int = 1,
    max_retained_alternatives: int = 1,
    max_replication_relations: int = 1,
) -> CampaignPortfolioPolicy:
    return CampaignPortfolioPolicy(
        max_frontier_size=max_frontier_size,
        min_distinct_hypothesis_roots=min_distinct_hypothesis_roots,
        max_frontier_per_hypothesis_root=max_frontier_per_hypothesis_root,
        max_retained_alternatives=max_retained_alternatives,
        max_replication_relations=max_replication_relations,
    )


def test_frontier_is_deterministic_content_addressed_and_diverse() -> None:
    first = build_campaign_portfolio_frontier(_campaign(), _policy())
    second = build_campaign_portfolio_frontier(_campaign(), _policy())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert tuple(item.node_id for item in first.entries) == ("decision-a", "decision-b")
    assert first.semantic_dict()["distinct_hypothesis_root_node_ids"] == [
        "hypothesis-a",
        "hypothesis-b",
    ]
    assert first.expandable_node_ids == ("decision-a", "decision-b")


def test_terminal_negative_frontier_node_is_preserved_but_not_expandable() -> None:
    outcome = CampaignBranchOutcome(
        terminal_node_id="decision-a",
        outcome=CampaignBranchOutcomeKind.REJECTED,
        evidence_sha256s=("2" * 64,),
        reason="Fixture branch failed the frozen criterion.",
    )
    frontier = build_campaign_portfolio_frontier(
        _campaign(outcomes=(outcome,)),
        _policy(),
    )

    entry = frontier.entries[0]
    assert entry.node_id == "decision-a"
    assert entry.terminal_outcome is CampaignBranchOutcomeKind.REJECTED
    assert entry.expandable is False
    assert frontier.expandable_node_ids == ("decision-b",)


def test_frontier_size_limit_fails_closed() -> None:
    with pytest.raises(CampaignPortfolioPolicyError, match="max_frontier_size"):
        build_campaign_portfolio_frontier(
            _campaign(),
            _policy(
                max_frontier_size=1,
                min_distinct_hypothesis_roots=1,
                max_frontier_per_hypothesis_root=1,
            ),
        )


def test_hypothesis_root_diversity_fails_closed() -> None:
    with pytest.raises(CampaignPortfolioPolicyError, match="hypothesis-root diversity"):
        build_campaign_portfolio_frontier(
            _campaign(shared_root=True),
            _policy(),
        )


def test_per_root_concentration_limit_fails_closed() -> None:
    with pytest.raises(CampaignPortfolioPolicyError, match="concentration limit"):
        build_campaign_portfolio_frontier(
            _campaign(shared_root=True),
            _policy(
                min_distinct_hypothesis_roots=1,
                max_frontier_per_hypothesis_root=1,
            ),
        )


def test_retained_alternative_budget_is_frozen_by_policy() -> None:
    with pytest.raises(CampaignPortfolioPolicyError, match="retained alternatives"):
        build_campaign_portfolio_frontier(
            _campaign(retained=("decision-a", "decision-b")),
            _policy(),
        )


def test_replication_budget_is_frozen_by_policy() -> None:
    relations = (
        CampaignReplicationRelation(
            source_node_id="plan-a",
            replica_node_id="decision-a",
            evidence_sha256s=("3" * 64,),
        ),
        CampaignReplicationRelation(
            source_node_id="plan-b",
            replica_node_id="decision-b",
            evidence_sha256s=("4" * 64,),
        ),
    )
    with pytest.raises(CampaignPortfolioPolicyError, match="replication relations"):
        build_campaign_portfolio_frontier(
            _campaign(replications=relations),
            _policy(),
        )


def test_invalid_policy_bounds_fail_closed() -> None:
    with pytest.raises(CampaignPortfolioPolicyError, match="max_frontier_size"):
        _policy(max_frontier_size=0)

    with pytest.raises(
        CampaignPortfolioPolicyError,
        match="cannot exceed max_frontier_size",
    ):
        _policy(
            max_frontier_size=1,
            min_distinct_hypothesis_roots=2,
            max_frontier_per_hypothesis_root=1,
        )


def test_campaign_mutation_after_frontier_construction_fails_closed() -> None:
    campaign = _campaign()
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    object.__setattr__(
        campaign,
        "current_frontier_node_ids",
        ("decision-a",),
    )

    with pytest.raises(CampaignPortfolioPolicyError, match="exact canonical campaign frontier"):
        frontier.semantic_dict()


def test_policy_mutation_after_frontier_construction_fails_closed() -> None:
    policy = _policy()
    frontier = build_campaign_portfolio_frontier(_campaign(), policy)
    object.__setattr__(policy, "max_frontier_size", 3)

    with pytest.raises(CampaignPortfolioPolicyError, match="policy changed"):
        frontier.semantic_dict()


def test_frontier_entry_mutation_fails_closed() -> None:
    frontier = build_campaign_portfolio_frontier(_campaign(), _policy())
    object.__setattr__(frontier.entries[0], "artifact_sha256", "9" * 64)

    with pytest.raises(CampaignPortfolioPolicyError, match="entry changed"):
        frontier.semantic_dict()


def test_portfolio_frontier_grants_no_authority() -> None:
    frontier = build_campaign_portfolio_frontier(_campaign(), _policy())

    assert frontier.can_authorize_execution is False
    assert frontier.can_authorize_training is False
    assert frontier.can_authorize_promotion is False
    assert frontier.semantic_dict()["non_authoritative"] is True
