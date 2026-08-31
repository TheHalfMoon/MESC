"""MRL-0505 tests for the deterministic fixture-only researcher benchmark harness."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_campaign_branch_semantics_v1 import (
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
from medscale.mesc._mrl_researcher_benchmark_v1 import (
    ResearcherBenchmarkArm,
    ResearcherBenchmarkHarnessError,
    ResearcherBenchmarkRun,
    build_researcher_benchmark_run,
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
                _node("decision-a", CampaignNodeKind.DECISION, "1" * 64, ("receipt-a",)),
                _node("decision-b", CampaignNodeKind.DECISION, "2" * 64, ("receipt-b",)),
                _node("hypothesis-a", CampaignNodeKind.HYPOTHESIS, "3" * 64),
                _node("hypothesis-b", CampaignNodeKind.HYPOTHESIS, "4" * 64),
                _node(
                    "plan-a",
                    CampaignNodeKind.EXPERIMENT_PLAN,
                    "5" * 64,
                    ("hypothesis-a",),
                ),
                _node(
                    "plan-b",
                    CampaignNodeKind.EXPERIMENT_PLAN,
                    "6" * 64,
                    ("hypothesis-b",),
                ),
                _node(
                    "receipt-a",
                    CampaignNodeKind.RECEIPT,
                    "7" * 64,
                    ("plan-a",),
                ),
                _node(
                    "receipt-b",
                    CampaignNodeKind.RECEIPT,
                    "8" * 64,
                    ("plan-b",),
                ),
            ),
            key=lambda item: item.node_id,
        )
    )


def _resources(*, known_failure_retries: int = 0) -> CampaignResourceTotals:
    return CampaignResourceTotals(
        wall_clock_seconds=10,
        compute_seconds=8,
        input_tokens=100,
        generated_tokens=20,
        storage_bytes=1_000,
        monetary_cost_microunits=500,
        retries=known_failure_retries,
        known_failure_retries=known_failure_retries,
        evaluator_invocations=2,
    )


def _campaign(
    *,
    outcomes: tuple[CampaignBranchOutcome, ...] = (),
    retained: tuple[str, ...] = ("decision-a", "decision-b"),
    replications: tuple[CampaignReplicationRelation, ...] | None = None,
    known_failure_retries: int = 0,
) -> ResearchCampaign:
    if replications is None:
        replications = (
            CampaignReplicationRelation(
                source_node_id="decision-a",
                replica_node_id="decision-b",
                evidence_sha256s=("9" * 64,),
            ),
        )
    return ResearchCampaign(
        campaign_id="fixture-researcher-benchmark",
        objective_sha256=_OBJECTIVE_SHA,
        parent=None,
        nodes=_nodes(),
        replications=replications,
        retained_alternative_node_ids=retained,
        branch_outcomes=outcomes,
        current_frontier_node_ids=("decision-a", "decision-b"),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=_resources(
            known_failure_retries=known_failure_retries,
        ),
        cumulative_tier_usage=(),
    )


def _policy() -> CampaignPortfolioPolicy:
    return CampaignPortfolioPolicy(
        max_frontier_size=2,
        min_distinct_hypothesis_roots=2,
        max_frontier_per_hypothesis_root=1,
        max_retained_alternatives=2,
        max_replication_relations=1,
    )


def _run(
    campaign: ResearchCampaign,
    arm: ResearcherBenchmarkArm = ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
) -> ResearcherBenchmarkRun:
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    semantics = build_campaign_branch_semantics(campaign, frontier)
    return build_researcher_benchmark_run(
        arm,
        campaign,
        frontier,
        semantics,
    )


def test_benchmark_metrics_are_derived_from_exact_campaign_state() -> None:
    run = _run(_campaign())
    metrics = run.metrics

    assert metrics.experiment_count == 2
    assert metrics.hypothesis_count == 2
    assert metrics.frontier_hypothesis_root_count == 2
    assert metrics.replication_count == 1
    assert metrics.validated_replicated_gain_count == 1
    assert metrics.experiments_to_first_replicated_gain == 2
    assert metrics.semantic_dict()["validated_gain_per_compute_unit"] == {
        "numerator": 1,
        "denominator": 8,
    }
    assert metrics.evaluator_invocation_count == 2
    assert metrics.storage_bytes == 1_000


def test_repeated_known_failure_and_retry_counts_remain_visible() -> None:
    outcomes = (
        CampaignBranchOutcome(
            terminal_node_id="decision-a",
            outcome=CampaignBranchOutcomeKind.REJECTED,
            evidence_sha256s=("b" * 64,),
            reason="Repeated fixture failure.",
        ),
        CampaignBranchOutcome(
            terminal_node_id="decision-b",
            outcome=CampaignBranchOutcomeKind.REJECTED,
            evidence_sha256s=("c" * 64,),
            reason="REPEATED fixture failure.",
        ),
    )
    run = _run(
        _campaign(
            outcomes=outcomes,
            retained=(),
            replications=(),
            known_failure_retries=2,
        )
    )

    metrics = run.metrics
    assert metrics.validated_replicated_gain_count == 0
    assert metrics.experiments_to_first_replicated_gain is None
    assert metrics.terminal_failure_outcome_count == 2
    assert metrics.repeated_known_failure_count == 1
    assert metrics.known_failure_retry_count == 2


def test_invalid_outcomes_are_counted_separately() -> None:
    outcome = CampaignBranchOutcome(
        terminal_node_id="decision-a",
        outcome=CampaignBranchOutcomeKind.INVALID,
        evidence_sha256s=("d" * 64,),
        reason="Fixture experiment was invalid.",
    )
    run = _run(
        _campaign(
            outcomes=(outcome,),
            retained=(),
            replications=(),
        )
    )

    metrics = run.metrics
    assert metrics.invalid_outcome_count == 1
    assert metrics.terminal_failure_outcome_count == 1


def test_all_four_required_researcher_arms_are_supported() -> None:
    campaign = _campaign()
    hashes = {arm: _run(campaign, arm).content_sha256 for arm in ResearcherBenchmarkArm}

    assert set(hashes) == {
        ResearcherBenchmarkArm.STATELESS,
        ResearcherBenchmarkArm.HISTORY_ONLY,
        ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY,
        ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
    }
    assert len(set(hashes.values())) == 4


def test_campaign_mutation_after_run_construction_fails_closed() -> None:
    campaign = _campaign()
    run = _run(campaign)
    object.__setattr__(
        campaign,
        "retained_alternative_node_ids",
        ("decision-a",),
    )

    with pytest.raises(ResearcherBenchmarkHarnessError):
        run.semantic_dict()


def test_metric_mutation_after_run_construction_fails_closed() -> None:
    run = _run(_campaign())
    object.__setattr__(run.metrics, "experiment_count", 999)

    with pytest.raises(ResearcherBenchmarkHarnessError):
        run.semantic_dict()


def test_branch_semantics_must_bind_exact_frontier() -> None:
    campaign = _campaign()
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    other_campaign = _campaign(retained=("decision-a",))
    other_frontier = build_campaign_portfolio_frontier(other_campaign, _policy())
    other_semantics = build_campaign_branch_semantics(other_campaign, other_frontier)

    with pytest.raises(
        ResearcherBenchmarkHarnessError,
        match="branch semantics do not bind the exact benchmark campaign",
    ):
        build_researcher_benchmark_run(
            ResearcherBenchmarkArm.STATELESS,
            campaign,
            frontier,
            other_semantics,
        )


def test_run_is_deterministic_content_addressed_and_non_authoritative() -> None:
    first = _run(_campaign(), ResearcherBenchmarkArm.STATELESS)
    second = _run(_campaign(), ResearcherBenchmarkArm.STATELESS)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.can_execute_agent is False
    assert first.can_authorize_real_execution is False
    assert first.can_authorize_training is False
    assert first.can_authorize_promotion is False
    payload = first.semantic_dict()
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
