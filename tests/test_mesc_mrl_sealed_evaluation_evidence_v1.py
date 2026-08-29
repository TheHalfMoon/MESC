"""MRL-0305 tests for independent sealed-evaluation evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedEvaluationEvidenceError,
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


def _metric() -> SealedMetricEvidence:
    return SealedMetricEvidence(
        metric_id="safety",
        evaluator_id="eval.sealed",
        value_decimal="0.96",
        evidence_artifact_sha256="e" * 64,
    )


def _report():
    return build_sealed_evaluation_evidence_report(
        _contract(),
        _request(),
        _handoff(),
        (_metric(),),
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
    assert b"item_level" not in report.semantic_bytes


def test_metric_evidence_must_exactly_cover_frozen_sealed_metrics() -> None:
    wrong_metric = replace(_metric(), metric_id="other")
    wrong_evaluator = replace(_metric(), evaluator_id="eval.search")

    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (wrong_metric,),
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="exactly cover"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            _request(),
            _handoff(),
            (wrong_evaluator,),
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
            (_metric(),),
        )


def test_non_sealed_and_fabricated_inputs_fail_closed() -> None:
    search = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)

    with pytest.raises(SealedEvaluationEvidenceError, match="requires Tier 3 SEALED"):
        build_sealed_evaluation_evidence_report(
            search,
            _request(),
            _handoff(),
            (_metric(),),
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="request must be an exact"):
        build_sealed_evaluation_evidence_report(
            _contract(),
            cast(SealedEvaluationRequest, object()),
            _handoff(),
            (_metric(),),
        )


def test_metric_identity_decimal_and_artifact_validation_fail_closed() -> None:
    with pytest.raises(SealedEvaluationEvidenceError, match="value_decimal"):
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal="0.960",
            evidence_artifact_sha256="e" * 64,
        )
    with pytest.raises(SealedEvaluationEvidenceError, match="evidence_artifact_sha256"):
        SealedMetricEvidence(
            metric_id="safety",
            evaluator_id="eval.sealed",
            value_decimal="0.96",
            evidence_artifact_sha256="E" * 64,
        )
