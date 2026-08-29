"""MRL-0306 tests for hard medical non-regression gates."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_medical_non_regression_gate_v1 import (
    MedicalFloorAssessment,
    MedicalNonRegressionDisposition,
    MedicalNonRegressionGateError,
    evaluate_medical_non_regression_gates,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    FloorComparator,
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


def _sealed_report(
    objective: ResearchObjectiveContract,
    *,
    global_value: str = "0.96",
    subgroup_value: str = "0.94",
) -> SealedEvaluationEvidenceReport:
    contract = TierEvaluationContract(objective=objective, tier=EvaluationTier.SEALED)
    request = build_sealed_evaluation_request(
        contract,
        candidate_sha256="a" * 64,
        source_receipt_sha256="c" * 64,
    )
    handoff = record_sealed_evidence_handoff(request, "d" * 64)
    evidence = (
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal=global_value,
            evidence_artifact_sha256="e" * 64,
        ),
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal=subgroup_value,
            evidence_artifact_sha256="f" * 64,
            subgroup="critical-cohort",
        ),
    )
    return build_sealed_evaluation_evidence_report(
        contract,
        request,
        handoff,
        evidence,
    )


def test_gate_is_deterministic_evidence_only_and_comparison_eligible_when_all_floors_hold() -> None:
    first = evaluate_medical_non_regression_gates(
        _objective(),
        _sealed_report(_objective()),
    )
    second = evaluate_medical_non_regression_gates(
        _objective(),
        _sealed_report(_objective()),
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.disposition is MedicalNonRegressionDisposition.SATISFIED
    assert first.comparison_eligible is True
    assert first.can_authorize is False
    assert first.can_authorize_model_promotion is False
    assert tuple(item.floor_id for item in first.assessments) == (
        "global-safety",
        "subgroup-safety",
    )
    assert all(item.passed for item in first.assessments)
    assert b"PROMOTED" not in first.semantic_bytes
    assert first.to_dict()["content_sha256"] == first.content_sha256


def test_global_hard_guardrail_failure_blocks_later_comparison() -> None:
    report = evaluate_medical_non_regression_gates(
        _objective(),
        _sealed_report(_objective(), global_value="0.94"),
    )

    assert report.disposition is MedicalNonRegressionDisposition.REGRESSION_DETECTED
    assert report.comparison_eligible is False
    assert report.assessments[0].floor_id == "global-safety"
    assert report.assessments[0].passed is False
    assert report.assessments[1].passed is True


def test_critical_subgroup_regression_cannot_be_hidden_by_global_gain() -> None:
    report = evaluate_medical_non_regression_gates(
        _objective(),
        _sealed_report(_objective(), global_value="1", subgroup_value="0.89"),
    )

    assert report.disposition is MedicalNonRegressionDisposition.REGRESSION_DETECTED
    assert report.comparison_eligible is False
    assert report.assessments[0].passed is True
    assert report.assessments[1].floor_id == "subgroup-safety"
    assert report.assessments[1].subgroup == "critical-cohort"
    assert report.assessments[1].passed is False


def test_lte_floor_comparator_is_evaluated_exactly() -> None:
    objective = replace(
        _objective(),
        hard_guardrails=(
            replace(
                _objective().hard_guardrails[0],
                comparator=FloorComparator.LTE,
                threshold_decimal="0.97",
            ),
        ),
    )
    report = evaluate_medical_non_regression_gates(
        objective,
        _sealed_report(objective, global_value="0.96"),
    )

    assert report.disposition is MedicalNonRegressionDisposition.SATISFIED
    assert report.assessments[0].comparator is FloorComparator.LTE
    assert report.assessments[0].passed is True


def test_material_sealed_value_change_changes_gate_identity() -> None:
    objective = _objective()
    first = evaluate_medical_non_regression_gates(
        objective,
        _sealed_report(objective, global_value="0.96"),
    )
    second = evaluate_medical_non_regression_gates(
        objective,
        _sealed_report(objective, global_value="0.97"),
    )

    assert first.content_sha256 != second.content_sha256
    assert first.semantic_bytes != second.semantic_bytes


def test_objective_identity_mismatch_fails_closed() -> None:
    changed = replace(
        _objective(),
        hard_guardrails=(
            replace(
                _objective().hard_guardrails[0],
                threshold_decimal="0.96",
            ),
        ),
    )

    with pytest.raises(MedicalNonRegressionGateError, match="does not bind"):
        evaluate_medical_non_regression_gates(_objective(), _sealed_report(changed))


def test_fabricated_report_missing_frozen_subgroup_evidence_fails_closed() -> None:
    original = _sealed_report(_objective())
    fabricated = replace(original, metric_evidence=(original.metric_evidence[0],))

    with pytest.raises(MedicalNonRegressionGateError, match="missing frozen floor"):
        evaluate_medical_non_regression_gates(_objective(), fabricated)


def test_fabricated_evaluator_artifact_or_metric_binding_fails_closed() -> None:
    original = _sealed_report(_objective())
    wrong_artifact = replace(
        original,
        evaluator_artifacts=(("eval.sealed", "1" * 64),),
    )
    wrong_metric = replace(
        original.metric_evidence[0],
        evaluator_id="eval.search",
    )
    wrong_metric_report = replace(
        original,
        metric_evidence=(wrong_metric, original.metric_evidence[1]),
    )

    with pytest.raises(MedicalNonRegressionGateError, match="evaluator artifacts"):
        evaluate_medical_non_regression_gates(_objective(), wrong_artifact)
    with pytest.raises(MedicalNonRegressionGateError, match="evaluator does not match"):
        evaluate_medical_non_regression_gates(_objective(), wrong_metric_report)


def test_exact_contract_types_are_required() -> None:
    with pytest.raises(
        MedicalNonRegressionGateError,
        match="exact ResearchObjectiveContract",
    ):
        evaluate_medical_non_regression_gates(
            cast(ResearchObjectiveContract, object()),
            _sealed_report(_objective()),
        )
    with pytest.raises(
        MedicalNonRegressionGateError,
        match="exact SealedEvaluationEvidenceReport",
    ):
        evaluate_medical_non_regression_gates(
            _objective(),
            cast(SealedEvaluationEvidenceReport, object()),
        )


def test_assessment_rejects_inconsistent_or_noncanonical_direct_construction() -> None:
    with pytest.raises(MedicalNonRegressionGateError, match="passed does not match"):
        MedicalFloorAssessment(
            floor_id="global-safety",
            metric_id="safety",
            comparator=FloorComparator.GTE,
            threshold_decimal="0.95",
            observed_value_decimal="0.96",
            evidence_artifact_sha256="e" * 64,
            subgroup=None,
            passed=False,
        )
    with pytest.raises(MedicalNonRegressionGateError, match="canonical decimal"):
        MedicalFloorAssessment(
            floor_id="global-safety",
            metric_id="safety",
            comparator=FloorComparator.GTE,
            threshold_decimal="0.950",
            observed_value_decimal="0.96",
            evidence_artifact_sha256="e" * 64,
            subgroup=None,
            passed=True,
        )
