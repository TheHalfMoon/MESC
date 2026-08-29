"""MRL-0306 tests for deterministic hard medical non-regression gates."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_hard_medical_non_regression_v1 import (
    HardMedicalNonRegressionError,
    evaluate_hard_medical_non_regression,
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
    return build_sealed_evaluation_evidence_report(contract, request, handoff, evidence)


def test_report_is_deterministic_binds_exact_evidence_and_satisfies_all_frozen_floors() -> None:
    objective = _objective()
    sealed = _sealed_report(objective)
    first = evaluate_hard_medical_non_regression(objective, sealed)
    second = evaluate_hard_medical_non_regression(objective, sealed)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.objective_sha256 == objective.content_sha256
    assert first.sealed_evidence_report_sha256 == sealed.content_sha256
    assert first.all_hard_gates_satisfied is True
    assert first.violated_floor_ids == ()
    assert tuple(gate.floor_id for gate in first.gates) == (
        "global-safety",
        "subgroup-safety",
    )
    assert tuple(gate.satisfied for gate in first.gates) == (True, True)


def test_global_floor_violation_is_preserved_as_a_hard_gate_failure() -> None:
    objective = _objective()
    report = evaluate_hard_medical_non_regression(
        objective,
        _sealed_report(objective, global_value="0.94"),
    )

    assert report.all_hard_gates_satisfied is False
    assert report.violated_floor_ids == ("global-safety",)
    assert report.gates[0].threshold_decimal == "0.95"
    assert report.gates[0].observed_value_decimal == "0.94"
    assert report.gates[0].evidence_artifact_sha256 == "e" * 64


def test_subgroup_regression_cannot_be_hidden_by_a_strong_global_metric() -> None:
    objective = _objective()
    report = evaluate_hard_medical_non_regression(
        objective,
        _sealed_report(objective, global_value="0.99", subgroup_value="0.89"),
    )

    assert report.all_hard_gates_satisfied is False
    assert report.violated_floor_ids == ("subgroup-safety",)
    assert report.gates[0].satisfied is True
    assert report.gates[1].subgroup == "critical-cohort"
    assert report.gates[1].satisfied is False


def test_lte_floor_comparator_is_evaluated_exactly_from_frozen_semantics() -> None:
    original = _objective()
    lte_floor = replace(
        original.hard_guardrails[0],
        comparator=FloorComparator.LTE,
        threshold_decimal="0.1",
    )
    objective = replace(original, hard_guardrails=(lte_floor,))

    satisfied = evaluate_hard_medical_non_regression(
        objective,
        _sealed_report(objective, global_value="0.09"),
    )
    violated = evaluate_hard_medical_non_regression(
        objective,
        _sealed_report(objective, global_value="0.11"),
    )

    assert satisfied.gates[0].comparator is FloorComparator.LTE
    assert satisfied.gates[0].satisfied is True
    assert violated.gates[0].satisfied is False
    assert violated.violated_floor_ids == ("global-safety",)


def test_objective_and_sealed_report_identity_mismatch_fails_closed() -> None:
    original = _objective()
    changed = replace(
        original,
        hard_guardrails=(
            replace(original.hard_guardrails[0], threshold_decimal="0.96"),
        ),
    )

    with pytest.raises(HardMedicalNonRegressionError, match="does not match"):
        evaluate_hard_medical_non_regression(changed, _sealed_report(original))


def test_fabricated_evaluator_or_metric_binding_fails_closed() -> None:
    objective = _objective()
    sealed = _sealed_report(objective)
    wrong_artifact = replace(
        sealed,
        evaluator_artifacts=(("eval.sealed", "1" * 64),),
    )
    wrong_global_metric = replace(
        sealed.metric_evidence[0],
        evaluator_id="eval.search",
    )
    wrong_metric_report = replace(
        sealed,
        metric_evidence=(wrong_global_metric, sealed.metric_evidence[1]),
    )

    with pytest.raises(HardMedicalNonRegressionError, match="evaluator artifacts"):
        evaluate_hard_medical_non_regression(objective, wrong_artifact)
    with pytest.raises(HardMedicalNonRegressionError, match="does not exactly match"):
        evaluate_hard_medical_non_regression(objective, wrong_metric_report)


def test_report_remains_evidence_only_and_cannot_encode_promotion_authority() -> None:
    objective = _objective()
    report = evaluate_hard_medical_non_regression(objective, _sealed_report(objective))
    payload = report.to_dict()

    assert report.can_authorize is False
    assert report.can_authorize_model_promotion is False
    assert payload["can_authorize"] is False
    assert payload["can_authorize_model_promotion"] is False
    assert b"PROMOTED" not in report.semantic_bytes
    assert b"promotion_decision" not in report.semantic_bytes


def test_exact_contract_types_are_required() -> None:
    objective = _objective()
    sealed = _sealed_report(objective)

    with pytest.raises(HardMedicalNonRegressionError, match="exact ResearchObjectiveContract"):
        evaluate_hard_medical_non_regression(
            cast(ResearchObjectiveContract, object()),
            sealed,
        )
    with pytest.raises(
        HardMedicalNonRegressionError,
        match="exact SealedEvaluationEvidenceReport",
    ):
        evaluate_hard_medical_non_regression(
            objective,
            cast(SealedEvaluationEvidenceReport, object()),
        )
