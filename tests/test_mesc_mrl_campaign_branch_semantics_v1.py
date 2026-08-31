"""MRL-0502..0504 tests for retained, replication, and failure-dedup semantics."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_campaign_branch_semantics_v1 import (
    CampaignBranchSemanticsError,
    build_campaign_branch_semantics,
)
from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioPolicy,
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


def _nodes() -> tuple[CampaignNode, ...]:
    return tuple(
        sorted(
            (
                _node("decision-a", CampaignNodeKind.DECISION, "b" * 64, ("plan-a",)),
                _node("decision-b", CampaignNodeKind.DECISION, "c" * 64, ("plan-b",)),
                _node("hypothesis-a", CampaignNodeKind.HYPOTHESIS, "d" * 64),
                _node("hypothesis-b", CampaignNodeKind.HYPOTHESIS, "e" * 64),
                _node("plan-a", CampaignNodeKind.EXPERIMENT_PLAN, "f" * 64, ("hypothesis-a",)),
                _node("plan-b", CampaignNodeKind.EXPERIMENT_PLAN, "1" * 64, ("hypothesis-b",)),
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
    retained: tuple[str, ...] = ("plan-b",),
    replications: tuple[CampaignReplicationRelation, ...] = (),
    outcomes: tuple[CampaignBranchOutcome, ...] = (),
) -> ResearchCampaign:
    return ResearchCampaign(
        campaign_id="fixture-branch-semantics",
        objective_sha256=_OBJECTIVE_SHA,
        parent=None,
        nodes=_nodes(),
        replications=replications,
        retained_alternative_node_ids=retained,
        branch_outcomes=outcomes,
        current_frontier_node_ids=("decision-a", "decision-b"),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=_resources(),
        cumulative_tier_usage=(),
    )


def _policy() -> CampaignPortfolioPolicy:
    return CampaignPortfolioPolicy(
        max_frontier_size=2,
        min_distinct_hypothesis_roots=2,
        max_frontier_per_hypothesis_root=1,
        max_retained_alternatives=2,
        max_replication_relations=2,
    )


def _view(campaign: ResearchCampaign):  # type: ignore[no-untyped-def]
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    return build_campaign_branch_semantics(campaign, frontier)


def test_retained_alternative_semantics_preserve_canonical_node() -> None:
    semantics = _view(_campaign())

    assert len(semantics.retained_alternatives) == 1
    retained = semantics.retained_alternatives[0]
    assert retained.node_id == "plan-b"
    assert retained.node_kind is CampaignNodeKind.EXPERIMENT_PLAN
    assert retained.hypothesis_root_node_ids == ("hypothesis-b",)
    assert retained.terminal_outcome is None
    assert retained.on_current_frontier is False
    assert retained.expandable is True


def test_terminal_retained_alternative_is_preserved_but_not_expandable() -> None:
    outcome = CampaignBranchOutcome(
        terminal_node_id="plan-b",
        outcome=CampaignBranchOutcomeKind.FAILED,
        evidence_sha256s=("2" * 64,),
        reason="Known fixture failure.",
    )
    semantics = _view(_campaign(outcomes=(outcome,)))

    retained = semantics.retained_alternatives[0]
    assert retained.terminal_outcome is CampaignBranchOutcomeKind.FAILED
    assert retained.expandable is False


def test_replication_semantics_bind_exact_campaign_relation() -> None:
    relation = CampaignReplicationRelation(
        source_node_id="plan-a",
        replica_node_id="decision-a",
        evidence_sha256s=("3" * 64,),
    )
    semantics = _view(_campaign(replications=(relation,)))

    replication = semantics.replications[0]
    assert replication.source_node_id == "plan-a"
    assert replication.replica_node_id == "decision-a"
    assert replication.evidence_sha256s == ("3" * 64,)
    assert replication.source_hypothesis_root_node_ids == ("hypothesis-a",)
    assert replication.replica_hypothesis_root_node_ids == ("hypothesis-a",)


def test_failure_signatures_deduplicate_without_deleting_occurrences() -> None:
    outcomes = tuple(
        sorted(
            (
                CampaignBranchOutcome(
                    terminal_node_id="decision-a",
                    outcome=CampaignBranchOutcomeKind.REJECTED,
                    evidence_sha256s=("4" * 64,),
                    reason="Repeated known failure.",
                ),
                CampaignBranchOutcome(
                    terminal_node_id="decision-b",
                    outcome=CampaignBranchOutcomeKind.REJECTED,
                    evidence_sha256s=("5" * 64,),
                    reason="  REPEATED   known failure. ",
                ),
            ),
            key=lambda item: item.terminal_node_id,
        )
    )
    semantics = _view(_campaign(outcomes=outcomes))

    assert len(semantics.failure_signatures) == 1
    group = semantics.failure_signatures[0]
    assert group.normalized_reason == "repeated known failure."
    assert group.occurrence_node_ids == ("decision-a", "decision-b")
    assert group.evidence_sha256s == ("4" * 64, "5" * 64)
    assert group.to_dict()["occurrence_count"] == 2
    assert group.to_dict()["duplicate_count"] == 1
    assert semantics.repeated_known_failure_count == 1
    payload = semantics.semantic_dict()
    assert payload["failure_occurrence_count"] == 2
    assert payload["unique_failure_signature_count"] == 1
    assert payload["repeated_known_failure_count"] == 1


def test_distinct_failure_reasons_remain_distinct_signatures() -> None:
    outcomes = tuple(
        sorted(
            (
                CampaignBranchOutcome(
                    terminal_node_id="decision-a",
                    outcome=CampaignBranchOutcomeKind.REJECTED,
                    evidence_sha256s=(),
                    reason="Failure alpha.",
                ),
                CampaignBranchOutcome(
                    terminal_node_id="decision-b",
                    outcome=CampaignBranchOutcomeKind.REJECTED,
                    evidence_sha256s=(),
                    reason="Failure beta.",
                ),
            ),
            key=lambda item: item.terminal_node_id,
        )
    )
    semantics = _view(_campaign(outcomes=outcomes))

    assert len(semantics.failure_signatures) == 2
    assert semantics.repeated_known_failure_count == 0


def test_campaign_mutation_invalidates_existing_branch_semantics() -> None:
    campaign = _campaign()
    semantics = _view(campaign)
    object.__setattr__(campaign, "retained_alternative_node_ids", ("plan-a",))

    with pytest.raises(CampaignBranchSemanticsError):
        semantics.semantic_dict()


def test_frontier_mutation_invalidates_existing_branch_semantics() -> None:
    campaign = _campaign()
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    semantics = build_campaign_branch_semantics(campaign, frontier)
    object.__setattr__(frontier.entries[0], "artifact_sha256", "9" * 64)

    with pytest.raises(CampaignBranchSemanticsError, match="portfolio frontier failed"):
        semantics.semantic_dict()


def test_retained_entry_mutation_fails_closed() -> None:
    semantics = _view(_campaign())
    object.__setattr__(semantics.retained_alternatives[0], "artifact_sha256", "8" * 64)

    with pytest.raises(CampaignBranchSemanticsError, match="retained alternative branch changed"):
        semantics.semantic_dict()


def test_replication_entry_mutation_fails_closed() -> None:
    relation = CampaignReplicationRelation(
        source_node_id="plan-a",
        replica_node_id="decision-a",
        evidence_sha256s=("3" * 64,),
    )
    semantics = _view(_campaign(replications=(relation,)))
    object.__setattr__(semantics.replications[0], "replica_node_id", "decision-b")

    with pytest.raises(CampaignBranchSemanticsError):
        semantics.semantic_dict()


def test_failure_group_mutation_fails_closed() -> None:
    outcome = CampaignBranchOutcome(
        terminal_node_id="decision-a",
        outcome=CampaignBranchOutcomeKind.REJECTED,
        evidence_sha256s=(),
        reason="Known failure.",
    )
    semantics = _view(_campaign(outcomes=(outcome,)))
    object.__setattr__(semantics.failure_signatures[0], "normalized_reason", "different")

    with pytest.raises(CampaignBranchSemanticsError):
        semantics.semantic_dict()


def test_branch_semantics_are_deterministic_and_non_authoritative() -> None:
    first = _view(_campaign())
    second = _view(_campaign())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.can_authorize_execution is False
    assert first.can_authorize_training is False
    assert first.can_authorize_promotion is False
    assert first.semantic_dict()["non_authoritative"] is True
