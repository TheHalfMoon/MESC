"""MRL-0307 tests for hard-gate-first Pareto/multi-objective comparison."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_pareto_comparison_v1 import (
    MetricComparisonRelation,
    ParetoComparisonError,
    ParetoRelation,
    compare_pareto_evidence,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    MetricContract,
    MetricDirection,
    ResearchObjectiveContract,
)
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedEvaluationEvidenceReport,
    SealedMetricEvidence,
    build_sealed_evaluation_evidence_report,
)
from medscale.mesc._mrl_sealed_evaluation_interface_v1 import (
    build_sealed_evaluation_request,
    record_sealed_evidence_handoff,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract
from test_mesc_mrl_research_objective_v1 import _objective


def _multi_objective() -> ResearchObjectiveContract:
    base = _objective()
    return replace(
        base,
        evaluation_metrics=(
            MetricContract(
                metric_id="cost",
                evaluator_id="eval.sealed",
                tier=EvaluationTier.SEALED,
                direction=MetricDirection.MINIMIZE,
            ),
            base.evaluation_metrics[0],
        ),
    )


def _sealed_report(
    objective: ResearchObjectiveContract,
    *,
    candidate_marker: str,
    cost: str,
    safety: str,
    subgroup_safety: str,
) -> SealedEvaluationEvidenceReport:
    contract = TierEvaluationContract(objective=objective, tier=EvaluationTier.SEALED)
    request = build_sealed_evaluation_request(
        contract,
        candidate_sha256=candidate_marker * 64,
        source_receipt_sha256="c" * 64,
    )
    handoff = record_sealed_evidence_handoff(request, candidate_marker * 64)
    evidence = (
        SealedMetricEvidence(
            metric_id="cost",
            evaluator_id="eval.sealed",
            value_decimal=cost,
            evidence_artifact_sha256=candidate_marker + "1" * 63,
        ),
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal=safety,
            evidence_artifact_sha256=candidate_marker + "2" * 63,
        ),
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal=subgroup_safety,
            evidence_artifact_sha256=candidate_marker + "3" * 63,
            subgroup="critical-cohort",
        ),
    )
    return build_sealed_evaluation_evidence_report(contract, request, handoff, evidence)


def test_candidate_dominates_only_after_both_reports_pass_hard_gates() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.96",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.97",
        subgroup_safety="0.95",
    )

    report = compare_pareto_evidence(objective, reference, candidate)

    assert report.relation is ParetoRelation.CANDIDATE_DOMINATES
    assert tuple(metric.metric_id for metric in report.metrics) == ("cost", "safety")
    assert tuple(metric.relation for metric in report.metrics) == (
        MetricComparisonRelation.BETTER,
        MetricComparisonRelation.BETTER,
    )
    assert report.metrics[0].direction is MetricDirection.MINIMIZE
    assert report.metrics[1].direction is MetricDirection.MAXIMIZE


def test_incompatible_soft_improvements_are_preserved_as_tradeoff() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.97",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.96",
        subgroup_safety="0.95",
    )

    report = compare_pareto_evidence(objective, reference, candidate)

    assert report.relation is ParetoRelation.TRADEOFF
    assert tuple(metric.relation for metric in report.metrics) == (
        MetricComparisonRelation.BETTER,
        MetricComparisonRelation.WORSE,
    )


def test_reference_dominance_and_equivalence_are_deterministic() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.97",
        subgroup_safety="0.94",
    )
    worse = _sealed_report(
        objective,
        candidate_marker="b",
        cost="11",
        safety="0.96",
        subgroup_safety="0.94",
    )
    equal = _sealed_report(
        objective,
        candidate_marker="d",
        cost="10",
        safety="0.97",
        subgroup_safety="0.94",
    )

    assert (
        compare_pareto_evidence(objective, reference, worse).relation
        is ParetoRelation.REFERENCE_DOMINATES
    )
    assert (
        compare_pareto_evidence(objective, reference, equal).relation is ParetoRelation.EQUIVALENT
    )


def test_large_cost_gain_cannot_hide_critical_subgroup_regression() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="1000",
        safety="0.96",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="1",
        safety="0.99",
        subgroup_safety="0.89",
    )

    report = compare_pareto_evidence(objective, reference, candidate)

    assert report.relation is ParetoRelation.CANDIDATE_REJECTED_HARD_GATE
    assert report.metrics == ()
    assert b"1000" not in report.semantic_bytes
    assert b'"metrics":[]' in report.semantic_bytes


def test_hard_gate_failure_is_resolved_before_soft_comparison_for_either_side() -> None:
    objective = _multi_objective()
    failed_reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.94",
        subgroup_safety="0.89",
    )
    passed_candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="20",
        safety="0.96",
        subgroup_safety="0.94",
    )
    failed_candidate = _sealed_report(
        objective,
        candidate_marker="d",
        cost="1",
        safety="0.94",
        subgroup_safety="0.89",
    )

    reference_rejected = compare_pareto_evidence(objective, failed_reference, passed_candidate)
    both_rejected = compare_pareto_evidence(objective, failed_reference, failed_candidate)

    assert reference_rejected.relation is ParetoRelation.REFERENCE_REJECTED_HARD_GATE
    assert reference_rejected.metrics == ()
    assert both_rejected.relation is ParetoRelation.BOTH_REJECTED_HARD_GATE
    assert both_rejected.metrics == ()


def test_report_is_deterministic_content_addressed_and_non_authoritative() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.96",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.97",
        subgroup_safety="0.95",
    )

    first = compare_pareto_evidence(objective, reference, candidate)
    second = compare_pareto_evidence(objective, reference, candidate)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.objective_sha256 == objective.content_sha256
    assert first.reference_evidence_report_sha256 == reference.content_sha256
    assert first.candidate_evidence_report_sha256 == candidate.content_sha256
    assert first.can_authorize is False
    assert first.can_authorize_model_promotion is False
    assert first.to_dict()["can_authorize"] is False
    assert b"PROMOTED" not in first.semantic_bytes
    assert b"promotion_decision" not in first.semantic_bytes


def test_mutated_soft_metric_fails_closed_before_comparison() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.96",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.97",
        subgroup_safety="0.95",
    )
    object.__setattr__(candidate.metric_evidence[0], "value_decimal", "not-a-decimal")

    with pytest.raises(ParetoComparisonError, match="hard-gate revalidation"):
        compare_pareto_evidence(objective, reference, candidate)


def test_mutated_comparison_metric_or_report_fails_closed_on_hash_views() -> None:
    objective = _multi_objective()
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.96",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.97",
        subgroup_safety="0.95",
    )
    report = compare_pareto_evidence(objective, reference, candidate)
    object.__setattr__(report.metrics[0], "relation", MetricComparisonRelation.WORSE)

    with pytest.raises(ParetoComparisonError, match="deterministic directional comparison"):
        _ = report.content_sha256

    fresh = compare_pareto_evidence(objective, reference, candidate)
    object.__setattr__(fresh, "candidate_evidence_report_sha256", "invalid")
    with pytest.raises(ParetoComparisonError, match="64 lowercase hex"):
        fresh.semantic_dict()


def test_mismatched_objective_or_evidence_fails_closed() -> None:
    objective = _multi_objective()
    changed = replace(
        objective,
        hard_guardrails=(replace(objective.hard_guardrails[0], threshold_decimal="0.96"),),
    )
    reference = _sealed_report(
        objective,
        candidate_marker="a",
        cost="10",
        safety="0.97",
        subgroup_safety="0.94",
    )
    candidate = _sealed_report(
        objective,
        candidate_marker="b",
        cost="5",
        safety="0.98",
        subgroup_safety="0.95",
    )

    with pytest.raises(ParetoComparisonError, match="hard-gate revalidation"):
        compare_pareto_evidence(changed, reference, candidate)
