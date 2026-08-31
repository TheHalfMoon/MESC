"""MRL-0510 tests for the deterministic researcher comparison report."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_campaign_history_projection_v1 import (
    build_campaign_history_projection,
)
from medscale.mesc._mrl_researcher_arm_context_v1 import (
    ResearcherArmContext,
    build_history_only_researcher_context,
    build_portfolio_tree_search_researcher_context,
    build_procedure_memory_researcher_context,
    build_stateless_researcher_context,
)
from medscale.mesc._mrl_researcher_benchmark_v1 import ResearcherBenchmarkArm
from medscale.mesc._mrl_researcher_comparison_report_v1 import (
    ResearcherComparisonReportError,
    build_researcher_comparison_report,
)
from test_mesc_mrl_researcher_arm_context_v1 import _procedure_index, _run


def _contexts(monkeypatch: pytest.MonkeyPatch) -> tuple[ResearcherArmContext, ...]:
    stateless_run = _run(ResearcherBenchmarkArm.STATELESS)
    history_run = _run(ResearcherBenchmarkArm.HISTORY_ONLY)
    procedure_run = _run(ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY)
    portfolio_run = _run(ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH)

    return (
        build_stateless_researcher_context(stateless_run),
        build_history_only_researcher_context(
            history_run,
            build_campaign_history_projection(history_run.campaign),
        ),
        build_procedure_memory_researcher_context(
            procedure_run,
            _procedure_index(monkeypatch),
        ),
        build_portfolio_tree_search_researcher_context(
            portfolio_run,
            portfolio_run.portfolio_frontier,
            portfolio_run.branch_semantics,
        ),
    )


def test_report_requires_and_canonicalizes_all_four_arms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contexts = _contexts(monkeypatch)
    report = build_researcher_comparison_report(tuple(reversed(contexts)))

    assert tuple(item.benchmark_run.arm for item in report.contexts) == (
        ResearcherBenchmarkArm.STATELESS,
        ResearcherBenchmarkArm.HISTORY_ONLY,
        ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY,
        ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
    )

    with pytest.raises(
        ResearcherComparisonReportError,
        match="exactly one context for each required researcher arm",
    ):
        build_researcher_comparison_report(contexts[:-1])


def test_metrics_are_derived_and_unrepresented_dimensions_are_explicitly_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = build_researcher_comparison_report(_contexts(monkeypatch))
    payload = report.semantic_dict()
    metrics = payload["metrics"]
    assert isinstance(metrics, dict)
    stateless = metrics[ResearcherBenchmarkArm.STATELESS.value]
    assert isinstance(stateless, list)

    by_name = {item["metric"]: item for item in stateless}
    assert by_name["validated_gain_per_compute_unit"]["availability"] == "AVAILABLE"
    assert by_name["validated_gain_per_compute_unit"]["numerator"] == 0
    assert by_name["validated_gain_per_compute_unit"]["denominator"] == 4
    assert (
        by_name["false_evidence_candidate_rate"]["availability"]
        == "NOT_AVAILABLE_FROM_FIXTURE_CONTRACT"
    )
    assert (
        by_name["human_correction_count"]["availability"] == "NOT_AVAILABLE_FROM_FIXTURE_CONTRACT"
    )
    assert (
        by_name["wasted_compute_on_known_failures"]["availability"]
        == "NOT_AVAILABLE_FROM_FIXTURE_CONTRACT"
    )


def test_equal_fixture_arms_all_remain_on_pareto_frontier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = build_researcher_comparison_report(_contexts(monkeypatch))

    assert report.pareto_frontier_arms == (
        ResearcherBenchmarkArm.STATELESS,
        ResearcherBenchmarkArm.HISTORY_ONLY,
        ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY,
        ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
    )


def test_markdown_is_deterministic_and_declares_fixture_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = build_researcher_comparison_report(_contexts(monkeypatch))
    second = build_researcher_comparison_report(_contexts(monkeypatch))

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.render_markdown() == second.render_markdown()

    markdown = first.render_markdown()
    assert markdown.startswith("# MRL Researcher Comparison Report V1\n")
    assert "N/A" in markdown
    assert "fixture-only" in markdown
    assert "hidden agent cognition" in markdown
    assert first.content_sha256 in markdown


def test_report_fails_closed_on_context_drift_after_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contexts = _contexts(monkeypatch)
    report = build_researcher_comparison_report(contexts)
    object.__setattr__(contexts[0], "fixture_only", False)

    with pytest.raises(ResearcherComparisonReportError):
        report.semantic_dict()


def test_report_is_non_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = build_researcher_comparison_report(_contexts(monkeypatch))

    assert report.can_execute_agent is False
    assert report.can_authorize_real_execution is False
    assert report.can_authorize_training is False
    assert report.can_authorize_promotion is False
    payload = report.semantic_dict()
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
