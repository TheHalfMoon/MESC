"""MRL-0107 tests for the immutable ResearchCampaign DAG."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcome,
    CampaignBranchOutcomeKind,
    CampaignNode,
    CampaignNodeKind,
    CampaignReplicationRelation,
    CampaignResourceTotals,
    CampaignTierTotals,
    ResearchCampaign,
    ResearchCampaignError,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier

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


def _base_nodes() -> tuple[CampaignNode, ...]:
    return (
        _node("decision-a", CampaignNodeKind.DECISION, "e" * 64, ("receipt-a",)),
        _node("hypothesis-a", CampaignNodeKind.HYPOTHESIS, "b" * 64),
        _node("plan-a", CampaignNodeKind.EXPERIMENT_PLAN, "c" * 64, ("hypothesis-a",)),
        _node("receipt-a", CampaignNodeKind.RECEIPT, "d" * 64, ("plan-a",)),
    )


def _resources(*, wall_clock_seconds: int = 10) -> CampaignResourceTotals:
    return CampaignResourceTotals(
        wall_clock_seconds=wall_clock_seconds,
        compute_seconds=8,
        input_tokens=100,
        generated_tokens=20,
        storage_bytes=1_000,
        monetary_cost_microunits=500,
        retries=1,
        known_failure_retries=0,
        evaluator_invocations=2,
    )


def _tier_usage(
    *,
    search_queries: int = 2,
    search_exposures: int = 1,
) -> tuple[CampaignTierTotals, ...]:
    return (
        CampaignTierTotals(
            tier=EvaluationTier.SEARCH,
            queries_used=search_queries,
            result_exposures_used=search_exposures,
        ),
        CampaignTierTotals(
            tier=EvaluationTier.SEALED,
            queries_used=0,
            result_exposures_used=0,
        ),
    )


def _outcome() -> CampaignBranchOutcome:
    return CampaignBranchOutcome(
        terminal_node_id="decision-a",
        outcome=CampaignBranchOutcomeKind.REJECTED,
        evidence_sha256s=("f" * 64,),
        reason="The branch failed the frozen acceptance criteria.",
    )


def _campaign(
    *,
    parent: ResearchCampaign | None = None,
    nodes: tuple[CampaignNode, ...] | None = None,
    replications: tuple[CampaignReplicationRelation, ...] = (),
    retained: tuple[str, ...] = (),
    outcomes: tuple[CampaignBranchOutcome, ...] | None = None,
    frontier: tuple[str, ...] = ("decision-a",),
    procedure_candidates: tuple[str, ...] = (),
    resources: CampaignResourceTotals | None = None,
    tier_usage: tuple[CampaignTierTotals, ...] | None = None,
) -> ResearchCampaign:
    return ResearchCampaign(
        campaign_id="fixture-campaign",
        objective_sha256=_OBJECTIVE_SHA,
        parent=parent,
        nodes=_base_nodes() if nodes is None else nodes,
        replications=replications,
        retained_alternative_node_ids=retained,
        branch_outcomes=(_outcome(),) if outcomes is None else outcomes,
        current_frontier_node_ids=frontier,
        procedure_candidate_node_ids=procedure_candidates,
        cumulative_resource_usage=_resources() if resources is None else resources,
        cumulative_tier_usage=_tier_usage() if tier_usage is None else tier_usage,
    )


def test_campaign_identity_is_deterministic_and_parent_bound() -> None:
    first = _campaign()
    second = _campaign()
    child = _campaign(
        parent=first,
        resources=_resources(wall_clock_seconds=11),
        tier_usage=_tier_usage(search_queries=3),
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert child.semantic_dict()["parent_campaign_sha256"] == first.content_sha256
    assert child.content_sha256 != first.content_sha256


def test_content_sha256_is_outside_campaign_semantic_preimage() -> None:
    campaign = _campaign()

    assert "content_sha256" not in campaign.semantic_dict()
    assert campaign.to_dict()["content_sha256"] == campaign.content_sha256


def test_unknown_parent_node_reference_fails_closed() -> None:
    nodes = list(_base_nodes())
    nodes[0] = replace(nodes[0], parent_node_ids=("missing-node",))

    with pytest.raises(ResearchCampaignError, match="unknown parent node"):
        _campaign(nodes=tuple(nodes))


def test_campaign_node_graph_cycle_fails_closed() -> None:
    nodes = (
        _node("node-a", CampaignNodeKind.HYPOTHESIS, "b" * 64, ("node-b",)),
        _node("node-b", CampaignNodeKind.EXPERIMENT_PLAN, "c" * 64, ("node-a",)),
    )

    with pytest.raises(ResearchCampaignError, match="acyclic"):
        _campaign(nodes=nodes, outcomes=(), frontier=())


def test_frontier_retained_and_replication_references_must_exist() -> None:
    with pytest.raises(ResearchCampaignError, match="current_frontier_node_ids"):
        _campaign(frontier=("missing",))

    with pytest.raises(ResearchCampaignError, match="retained_alternative_node_ids"):
        _campaign(retained=("missing",))

    relation = CampaignReplicationRelation(
        source_node_id="decision-a",
        replica_node_id="missing",
        evidence_sha256s=(),
    )
    with pytest.raises(ResearchCampaignError, match="replication relationship"):
        _campaign(replications=(relation,))


def test_procedure_candidate_reference_requires_procedure_candidate_node() -> None:
    with pytest.raises(ResearchCampaignError, match="PROCEDURE_CANDIDATE"):
        _campaign(procedure_candidates=("decision-a",))


def test_failed_null_invalid_and_rejected_outcomes_are_first_class() -> None:
    outcomes = tuple(
        CampaignBranchOutcome(
            terminal_node_id=node_id,
            outcome=outcome,
            evidence_sha256s=(),
            reason=f"Canonical {outcome.value.lower()} branch outcome.",
        )
        for node_id, outcome in (
            ("decision-a", CampaignBranchOutcomeKind.FAILED),
            ("hypothesis-a", CampaignBranchOutcomeKind.INVALID),
            ("plan-a", CampaignBranchOutcomeKind.NULL),
            ("receipt-a", CampaignBranchOutcomeKind.REJECTED),
        )
    )
    outcomes = tuple(sorted(outcomes, key=lambda item: item.terminal_node_id))
    campaign = _campaign(outcomes=outcomes)

    assert tuple(item.outcome for item in campaign.branch_outcomes) == (
        CampaignBranchOutcomeKind.FAILED,
        CampaignBranchOutcomeKind.INVALID,
        CampaignBranchOutcomeKind.NULL,
        CampaignBranchOutcomeKind.REJECTED,
    )


def test_child_campaign_cannot_delete_prior_node() -> None:
    parent = _campaign()
    child_nodes = tuple(node for node in _base_nodes() if node.node_id == "hypothesis-a")

    with pytest.raises(ResearchCampaignError, match="cannot delete a prior node"):
        _campaign(parent=parent, nodes=child_nodes, outcomes=(), frontier=())


def test_child_campaign_cannot_rewrite_prior_node() -> None:
    parent = _campaign()
    nodes = list(_base_nodes())
    nodes[0] = replace(nodes[0], artifact_sha256="1" * 64)

    with pytest.raises(ResearchCampaignError, match="cannot rewrite a prior node"):
        _campaign(parent=parent, nodes=tuple(nodes))


def test_child_campaign_cannot_delete_or_rewrite_prior_negative_outcome() -> None:
    parent = _campaign()

    with pytest.raises(ResearchCampaignError, match="cannot delete a prior branch outcome"):
        _campaign(parent=parent, outcomes=())

    rewritten = replace(_outcome(), reason="A different later explanation.")
    with pytest.raises(ResearchCampaignError, match="cannot rewrite a prior branch outcome"):
        _campaign(parent=parent, outcomes=(rewritten,))


def test_child_campaign_cannot_delete_prior_replication_relation() -> None:
    relation = CampaignReplicationRelation(
        source_node_id="plan-a",
        replica_node_id="receipt-a",
        evidence_sha256s=("1" * 64,),
    )
    parent = _campaign(replications=(relation,))

    with pytest.raises(ResearchCampaignError, match="prior replication relationship"):
        _campaign(parent=parent, replications=())


def test_cumulative_resource_accounting_cannot_move_backward() -> None:
    parent = _campaign()

    with pytest.raises(ResearchCampaignError, match="wall_clock_seconds cannot move backward"):
        _campaign(parent=parent, resources=_resources(wall_clock_seconds=9))

    child = _campaign(parent=parent, resources=_resources(wall_clock_seconds=11))
    assert child.cumulative_resource_usage.wall_clock_seconds == 11


def test_cumulative_query_and_exposure_accounting_cannot_move_backward() -> None:
    parent = _campaign()

    with pytest.raises(ResearchCampaignError, match="query accounting cannot move backward"):
        _campaign(parent=parent, tier_usage=_tier_usage(search_queries=1))

    with pytest.raises(
        ResearchCampaignError,
        match="result-exposure accounting cannot move backward",
    ):
        _campaign(parent=parent, tier_usage=_tier_usage(search_exposures=0))


def test_cumulative_tier_accounting_cannot_drop_prior_tier() -> None:
    parent = _campaign()
    search_only = (_tier_usage()[0],)

    with pytest.raises(ResearchCampaignError, match="cannot delete a prior tier"):
        _campaign(parent=parent, tier_usage=search_only)


def test_parent_campaign_identity_and_objective_must_match() -> None:
    parent = _campaign()

    with pytest.raises(ResearchCampaignError, match="campaign_id"):
        ResearchCampaign(
            campaign_id="different-campaign",
            objective_sha256=_OBJECTIVE_SHA,
            parent=parent,
            nodes=_base_nodes(),
            replications=(),
            retained_alternative_node_ids=(),
            branch_outcomes=(_outcome(),),
            current_frontier_node_ids=("decision-a",),
            procedure_candidate_node_ids=(),
            cumulative_resource_usage=_resources(),
            cumulative_tier_usage=_tier_usage(),
        )

    altered_parent = replace(parent, objective_sha256="9" * 64)
    with pytest.raises(ResearchCampaignError, match="objective identity"):
        _campaign(parent=altered_parent)


def test_parent_chain_cycle_created_by_tampering_fails_on_trust_view() -> None:
    campaign = _campaign()
    object.__setattr__(campaign, "parent", campaign)

    with pytest.raises(ResearchCampaignError, match="parent chain cannot contain a cycle"):
        _ = campaign.content_sha256


def test_post_construction_nested_tampering_fails_on_next_trust_view() -> None:
    campaign = _campaign()
    object.__setattr__(campaign.nodes[0], "artifact_sha256", "not-a-sha")

    with pytest.raises(ResearchCampaignError, match="64 lowercase hex"):
        _ = campaign.semantic_dict()


def test_campaign_subclass_fails_closed_during_construction() -> None:
    class CampaignSubclass(ResearchCampaign):
        pass

    base = _campaign()
    with pytest.raises(
        ResearchCampaignError,
        match="campaign parent chain contains an invalid type",
    ):
        CampaignSubclass(
            campaign_id=base.campaign_id,
            objective_sha256=base.objective_sha256,
            parent=base.parent,
            nodes=base.nodes,
            replications=base.replications,
            retained_alternative_node_ids=base.retained_alternative_node_ids,
            branch_outcomes=base.branch_outcomes,
            current_frontier_node_ids=base.current_frontier_node_ids,
            procedure_candidate_node_ids=base.procedure_candidate_node_ids,
            cumulative_resource_usage=base.cumulative_resource_usage,
            cumulative_tier_usage=base.cumulative_tier_usage,
        )
