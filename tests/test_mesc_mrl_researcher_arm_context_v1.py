"""MRL-0506..0509 tests for context-bound researcher benchmark arms."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_campaign_branch_semantics_v1 import (
    build_campaign_branch_semantics,
)
from medscale.mesc._mrl_campaign_history_projection_v1 import (
    build_campaign_history_projection,
)
from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioPolicy,
    build_campaign_portfolio_frontier,
)
from medscale.mesc._mrl_procedure_registry_v1 import (
    ProcedureRegistry,
    register_procedure_admission,
)
from medscale.mesc._mrl_procedure_search_index_v1 import build_procedure_search_index
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignNode,
    CampaignNodeKind,
    CampaignResourceTotals,
    ResearchCampaign,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_researcher_arm_context_v1 import (
    ResearcherArmContext,
    ResearcherArmContextError,
    build_history_only_researcher_context,
    build_portfolio_tree_search_researcher_context,
    build_procedure_memory_researcher_context,
    build_stateless_researcher_context,
)
from medscale.mesc._mrl_researcher_benchmark_v1 import (
    ResearcherBenchmarkArm,
    ResearcherBenchmarkRun,
    build_researcher_benchmark_run,
)
from test_mesc_mrl_procedure_registry_v1 import _gate_result

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


def _campaign() -> ResearchCampaign:
    nodes = tuple(
        sorted(
            (
                _node("decision-a", CampaignNodeKind.DECISION, "1" * 64, ("receipt-a",)),
                _node("hypothesis-a", CampaignNodeKind.HYPOTHESIS, "2" * 64),
                _node(
                    "plan-a",
                    CampaignNodeKind.EXPERIMENT_PLAN,
                    "3" * 64,
                    ("hypothesis-a",),
                ),
                _node(
                    "receipt-a",
                    CampaignNodeKind.RECEIPT,
                    "4" * 64,
                    ("plan-a",),
                ),
            ),
            key=lambda item: item.node_id,
        )
    )
    return ResearchCampaign(
        campaign_id="fixture-arm-context",
        objective_sha256=_OBJECTIVE_SHA,
        parent=None,
        nodes=nodes,
        replications=(),
        retained_alternative_node_ids=("decision-a",),
        branch_outcomes=(),
        current_frontier_node_ids=("decision-a",),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=CampaignResourceTotals(
            wall_clock_seconds=5,
            compute_seconds=4,
            input_tokens=10,
            generated_tokens=5,
            storage_bytes=100,
            monetary_cost_microunits=1,
            retries=0,
            known_failure_retries=0,
            evaluator_invocations=1,
        ),
        cumulative_tier_usage=(),
    )


def _policy() -> CampaignPortfolioPolicy:
    return CampaignPortfolioPolicy(
        max_frontier_size=1,
        min_distinct_hypothesis_roots=1,
        max_frontier_per_hypothesis_root=1,
        max_retained_alternatives=1,
        max_replication_relations=0,
    )


def _run(arm: ResearcherBenchmarkArm) -> ResearcherBenchmarkRun:
    campaign = _campaign()
    frontier = build_campaign_portfolio_frontier(campaign, _policy())
    semantics = build_campaign_branch_semantics(campaign, frontier)
    return build_researcher_benchmark_run(arm, campaign, frontier, semantics)


def _allow_index_fixture_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    def fixture_gate(
        self: ResearchInputAdmissionContract,
        surface: ResearchLearningSurface,
    ) -> None:
        assert surface is ResearchLearningSurface.RESEARCH_SEARCH_INDEX
        assert surface in self.allowed_learning_surfaces

    monkeypatch.setattr(
        ResearchInputAdmissionContract,
        "require_learning_admission",
        fixture_gate,
    )


def _procedure_index(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("arm-context")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    procedure = result.admitted_procedure
    assert procedure is not None
    source_sha256 = procedure.content_sha256
    permission = ResearchInputSourcePermission(
        permission_id="arm-context-search-index",
        source_artifact_sha256=source_sha256,
        source_contract_sha256="b" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.RESEARCH_SEARCH_INDEX,),
    )
    admission = ResearchInputAdmissionContract(
        input_id="arm-context-search-index-input",
        classification_policy_sha256="c" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256=source_sha256,
        source_contract_sha256="b" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.RESEARCH_SEARCH_INDEX,),
        source_permission=permission,
    )
    return build_procedure_search_index(registry, (admission,))


def test_stateless_context_exposes_no_research_memory() -> None:
    context = build_stateless_researcher_context(_run(ResearcherBenchmarkArm.STATELESS))

    payload = context.semantic_dict()
    assert payload["researcher_visible_context"] == []
    assert payload["history_projection_sha256"] is None
    assert payload["procedure_search_index_sha256"] is None
    assert payload["portfolio_frontier_sha256"] is None
    assert payload["branch_semantics_sha256"] is None


def test_history_only_context_binds_exact_campaign_history() -> None:
    run = _run(ResearcherBenchmarkArm.HISTORY_ONLY)
    history = build_campaign_history_projection(run.campaign)
    context = build_history_only_researcher_context(run, history)

    payload = context.semantic_dict()
    assert payload["researcher_visible_context"] == ["CAMPAIGN_HISTORY"]
    assert payload["history_projection_sha256"] == history.content_sha256


def test_procedure_memory_context_requires_real_nonempty_admitted_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = _run(ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY)
    index = _procedure_index(monkeypatch)
    context = build_procedure_memory_researcher_context(run, index)

    payload = context.semantic_dict()
    assert payload["researcher_visible_context"] == ["ADMITTED_PROCEDURE_INDEX"]
    assert payload["procedure_search_index_sha256"] == index.content_sha256


def test_portfolio_context_binds_exact_benchmark_frontier_and_semantics() -> None:
    run = _run(ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH)
    context = build_portfolio_tree_search_researcher_context(
        run,
        run.portfolio_frontier,
        run.branch_semantics,
    )

    payload = context.semantic_dict()
    assert payload["researcher_visible_context"] == [
        "PORTFOLIO_FRONTIER",
        "BRANCH_SEMANTICS",
    ]
    assert payload["portfolio_frontier_sha256"] == run.portfolio_frontier.content_sha256
    assert payload["branch_semantics_sha256"] == run.branch_semantics.content_sha256


def test_arm_label_cannot_be_used_with_stronger_context() -> None:
    stateless = _run(ResearcherBenchmarkArm.STATELESS)
    history = build_campaign_history_projection(stateless.campaign)

    with pytest.raises(ResearcherArmContextError):
        ResearcherArmContext(
            benchmark_run=stateless,
            history_projection=history,
        )


def test_history_context_from_different_campaign_fails_closed() -> None:
    run = _run(ResearcherBenchmarkArm.HISTORY_ONLY)
    other = _campaign()
    object.__setattr__(other, "campaign_id", "other-fixture-arm-context")

    with pytest.raises(ResearcherArmContextError):
        build_history_only_researcher_context(
            run,
            build_campaign_history_projection(other),
        )


def test_context_mutation_after_construction_fails_closed() -> None:
    run = _run(ResearcherBenchmarkArm.HISTORY_ONLY)
    history = build_campaign_history_projection(run.campaign)
    context = build_history_only_researcher_context(run, history)
    object.__setattr__(context, "history_projection", None)

    with pytest.raises(ResearcherArmContextError):
        context.semantic_dict()


def test_all_contexts_are_deterministic_and_non_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stateless = build_stateless_researcher_context(_run(ResearcherBenchmarkArm.STATELESS))
    history_run = _run(ResearcherBenchmarkArm.HISTORY_ONLY)
    history = build_history_only_researcher_context(
        history_run,
        build_campaign_history_projection(history_run.campaign),
    )
    procedure = build_procedure_memory_researcher_context(
        _run(ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY),
        _procedure_index(monkeypatch),
    )
    portfolio_run = _run(ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH)
    portfolio = build_portfolio_tree_search_researcher_context(
        portfolio_run,
        portfolio_run.portfolio_frontier,
        portfolio_run.branch_semantics,
    )

    contexts = (stateless, history, procedure, portfolio)
    assert len({item.content_sha256 for item in contexts}) == 4
    for context in contexts:
        assert context.can_execute_agent is False
        assert context.can_authorize_real_execution is False
        assert context.can_authorize_training is False
        assert context.can_authorize_promotion is False
        assert context.semantic_dict()["fixture_only"] is True
        assert context.semantic_dict()["non_evidence"] is True
