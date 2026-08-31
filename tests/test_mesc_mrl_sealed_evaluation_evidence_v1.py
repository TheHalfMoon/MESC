"""MRL-0305 tests for independent sealed-evaluation evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedEvaluationEvidenceError,
    SealedEvaluationEvidenceReport,
    SealedMetricEvidence,
    build_sealed_evaluation_evidence_report,
)
from medscale.mesc._mrl_sealed_evaluation_interface_v1 import (
    SealedEvaluationHandoff,
    SealedEvaluationRequest,
    build_sealed_evaluation_request,
    record_sealed_evidence_handoff,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract
from test_mesc_mrl_research_objective_v1 import _objective


def _contract() -> TierEvaluationContract:
    return TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEALED)


def _request() -> SealedEvaluationRequest:
    return build_sealed_evaluation_request(
        _contract(),
        candidate_sha256="a" * 64,
        source_receipt_sha256="c" * 64,
    )


def _handoff() -> SealedEvaluationHandoff:
    return record_sealed_evidence_handoff(_request(), "d" * 64)


def _metric(
    *,
    subgroup: str | None = None,
    value_decimal: str = "0.96",
    evidence_artifact_sha256: str = "e" * 64,
) -> SealedMetricEvidence:
    return SealedMetricEvidence(
        metric_id="safety",
        evaluator_id="eval.sealed",
        value_decimal=value_decimal,
        evidence_artifact_sha256=evidence_artifact_sha256,
        subgroup=subgroup,
    )


def _metrics() -> tuple[SealedMetricEvidence, ...]:
    return (
        _metric(),
        _metric(
            subgroup="critical-cohort",
            value_decimal="0.94",
            evidence_artifact_sha256="f" * 64,
        ),
    )


def _report() -> SealedEvaluationEvidenceReport:
    return build_sealed_evaluation_evidence_report(
        _contract(),
        _request(),
        _handoff(),
        _metrics(),
    )


def test_report_is_deterministic_and_binds_full_sealed_chain() -> None:
    first = _report()
    second = _report()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.objective_sha256 == _objective().content_sha256
    assert first.request_sha256 == _request().content_sha256
    assert first.handoff_sha256 == _handoff().content_sha256
    assert first.sealed_evidence_ref_sha256 == "d" * 64
    assert first.evaluator_artifacts == (("eval.sealed", "b" * 64),)
    assert tuple(item.subgroup for item in first.metric_evidence) == (
        None,
        "critical-cohort",
    )


def test_report_is_evidence_only_and_never_a_promotion_decision() -> None:
    report = _report()
    payload = report.to_dict()

    assert payload["adaptive_agent_visible"] is False
    assert payload["can_authorize"] is False
    assert payload["can_authorize_model_promotion"] is False
    assert payload["iterative_agent_result_stream"] is False
    assert payload["sealed_item_level_content_included"] is False
    assert b"PROMOTED" not in report.semantic_bytes
    assert b"promotion_decision" not in report.semantic_bytes
    assert b'"sealed_item_level_content_included":false' in report.semantic_bytes


def test_metric_evidence_must_cover_global_and_frozen_subgroup_metrics() -> None:
    wrong_metric = replace(_metrics()[0], metric_id="other")
    wrong_evaluator = replace(_metrics()[0], evaluator_id="eval.search")

    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (wrong_metric, _metrics()[1]),
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (_metrics()[1], wrong_evaluator),
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (_metrics()[0],),
        )
    unexpected_subgroup = _metric(
        subgroup="unfrozen-cohort",
        evidence_artifact_sha256="1" * 64,
    )
    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (*_metrics(), unexpected_subgroup),
        )


def test_request_and_handoff_chain_mismatches_fail_closed() -> None:
    other_request = build_sealed_evaluation_request(
        _contract(),
        candidate_sha256="f" * 64,
        source_receipt_sha256="c" * 64,
    )
    wrong_handoff = record_sealed_evidence_handoff(other_request, "d" * 64)

    with pytest.raises(SealedEvaluationEvidenceError, match="handoff does not match"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            wrong_handoff,
            _metrics(),
        )


def test_mutated_metric_evidence_fails_closed_on_report_semantic_and_hash_views() -> None:
    report = _report()
    object.__setattr__(report.metric_evidence[0], "value_decimal", "0.960")

    with pytest.raises(SealedEvaluationEvidenceError, match="value_decimal"):
        report.semantic_dict()
    with pytest.raises(SealedEvaluationEvidenceError, match="value_decimal"):
        _ = report.content_sha256


def test_valid_metric_identity_mutation_fails_closed() -> None:
    metric = _metric()
    object.__setattr__(metric, "evidence_artifact_sha256", "1" * 64)

    with pytest.raises(SealedEvaluationEvidenceError, match="identity changed"):
        metric.to_dict()


def test_builder_rejects_validly_mutated_sealed_request() -> None:
    request = _request()
    handoff = record_sealed_evidence_handoff(request, "d" * 64)
    object.__setattr__(request, "candidate_sha256", "f" * 64)

    with pytest.raises(SealedEvaluationEvidenceError, match="failed canonical revalidation"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            request,
            handoff,
            _metrics(),
        )


def test_mutated_report_identity_fails_closed_on_semantic_and_hash_views() -> None:
    report = _report()
    object.__setattr__(report, "objective_sha256", "invalid")

    with pytest.raises(SealedEvaluationEvidenceError, match="objective_sha256"):
        report.semantic_dict()
    with pytest.raises(SealedEvaluationEvidenceError, match="objective_sha256"):
        _ = report.content_sha256


def test_valid_report_identity_mutation_fails_closed() -> None:
    report = _report()
    object.__setattr__(report, "objective_sha256", "1" * 64)

    with pytest.raises(SealedEvaluationEvidenceError, match="identity changed"):
        report.semantic_dict()
    with pytest.raises(SealedEvaluationEvidenceError, match="identity changed"):
        _ = report.content_sha256


def test_mutated_evaluator_artifact_fails_closed_on_semantic_view() -> None:
    report = _report()
    object.__setattr__(report, "evaluator_artifacts", (("eval.sealed", "invalid"),))

    with pytest.raises(SealedEvaluationEvidenceError, match="evaluator artifact_sha256"):
        report.semantic_dict()


def test_non_sealed_and_fabricated_inputs_fail_closed() -> None:
    search = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)

    with pytest.raises(SealedEvaluationEvidenceError, match="requires Tier 3 SEALED"):
        build_sealed_evaluation_evidence_report(
            search,
            _request(),
            _handoff(),
            _metrics(),
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="request must be an exact"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            cast(SealedEvaluationRequest, object()),
            _handoff(),
            _metrics(),
        )


def test_metric_identity_decimal_artifact_and_subgroup_validation_fail_closed() -> None:
    with pytest.raises(SealedEvaluationEvidenceError, match="value_decimal"):
        _metric(value_decimal="0.960")
    with pytest.raises(SealedEvaluationEvidenceError, match="evidence_artifact_sha256"):
        _metric(evidence_artifact_sha256="E" * 64)
    with pytest.raises(SealedEvaluationEvidenceError, match="subgroup"):
        _metric(subgroup=" critical-cohort")
