"""MRL-0203 tests for the fixture-only structured observation envelope."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_fixture_research_surface_v1 import FixtureEvaluation
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_structured_fixture_observation_v1 import (
    FixtureObservationDiagnostic,
    FixtureObservationError,
    FixtureObservationFailureClass,
    FixtureObservationResourceUse,
    FixtureObservationRunStatus,
    FixtureRawOutputArtifact,
    FixtureRawOutputStream,
    StructuredFixtureObservation,
)


def _evaluation() -> FixtureEvaluation:
    return FixtureEvaluation(
        surface_sha256="a" * 64,
        evaluator_sha256="b" * 64,
        candidate_sha256="c" * 64,
        metric_id="fixture-score",
        score=8,
        max_score=10,
    )


def _admission(
    *,
    classification: ResearchInputClassification,
    source_artifact_sha256: str,
    surfaces: tuple[ResearchLearningSurface, ...] = (ResearchLearningSurface.OBSERVATION,),
) -> ResearchInputAdmissionContract:
    permission = ResearchInputSourcePermission(
        permission_id=f"fixture-{classification.value.lower()}-permission",
        source_artifact_sha256=source_artifact_sha256,
        source_contract_sha256="d" * 64,
        classification=classification,
        allowed_learning_surfaces=surfaces,
    )
    return ResearchInputAdmissionContract(
        input_id="fixture-observation-input",
        classification_policy_sha256="e" * 64,
        classification=classification,
        source_artifact_sha256=source_artifact_sha256,
        source_contract_sha256="d" * 64,
        allowed_learning_surfaces=surfaces,
        source_permission=permission,
    )


def _success_observation() -> StructuredFixtureObservation:
    evaluation = _evaluation()
    return StructuredFixtureObservation(
        observation_id="fixture-observation-001",
        input_admission=_admission(
            classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
            source_artifact_sha256=evaluation.content_sha256,
        ),
        run_status=FixtureObservationRunStatus.SUCCEEDED,
        evaluation=evaluation,
        resource_use=FixtureObservationResourceUse(
            operation_count=3,
            evaluator_invocations=1,
            storage_bytes=128,
        ),
        failure_class=None,
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDOUT,
                artifact_sha256="f" * 64,
            ),
        ),
        diagnostics=(
            FixtureObservationDiagnostic(
                code="fixture-summary",
                detail="Structured fixture evaluation completed.",
            ),
        ),
    )


def test_observation_is_deterministic_and_content_addressed() -> None:
    first = _success_observation()
    second = _success_observation()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert b"content_sha256" not in first.semantic_bytes
    assert "content_sha256" not in first.semantic_dict()
    assert first.to_dict()["content_sha256"] == first.content_sha256


def test_success_observation_exposes_typed_fixture_summary() -> None:
    observation = _success_observation()
    payload = observation.semantic_dict()
    evaluation_sha256 = _evaluation().content_sha256

    assert payload["run_status"] == "SUCCEEDED"
    assert payload["failure_class"] is None
    assert payload["metric_artifacts"] == [
        {
            "metric_id": "fixture-score",
            "artifact_sha256": evaluation_sha256,
            "evaluator_sha256": "b" * 64,
            "tier": 0,
        }
    ]
    assert payload["selected_metric_values"] == [
        {
            "metric_id": "fixture-score",
            "artifact_sha256": evaluation_sha256,
            "score": 8,
            "max_score": 10,
        }
    ]
    assert payload["guardrail_outcomes"] == []
    assert payload["tier_accounting"] == {
        "tier": 0,
        "queries_used": 0,
        "result_exposures_used": 1,
        "exposed_result_fields": ["max_score", "score"],
    }


def test_raw_outputs_are_identity_only_and_never_trusted_control() -> None:
    payload = _success_observation().semantic_dict()
    raw = cast(list[dict[str, object]], payload["raw_output_artifacts"])

    assert raw == [
        {
            "stream": "STDOUT",
            "artifact_sha256": "f" * 64,
            "trusted_control": False,
        }
    ]
    assert payload["raw_output_trusted_control"] is False
    assert payload["diagnostics_trusted_control"] is False
    assert payload["trusted_control_input"] is False
    assert set(raw[0]) == {"stream", "artifact_sha256", "trusted_control"}


def test_observation_is_fixture_only_non_evidence_and_non_authoritative() -> None:
    payload = _success_observation().semantic_dict()

    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert payload["can_authorize_real_execution"] is False
    assert payload["can_authorize_training"] is False
    assert payload["can_authorize_model_promotion"] is False


def test_success_admission_must_bind_exact_fixture_evaluation() -> None:
    evaluation = _evaluation()
    wrong_admission = _admission(
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        source_artifact_sha256="9" * 64,
    )

    with pytest.raises(FixtureObservationError, match="bind the exact fixture evaluation"):
        replace(_success_observation(), input_admission=wrong_admission, evaluation=evaluation)


def test_observation_requires_observation_learning_surface() -> None:
    evaluation = _evaluation()
    admission = _admission(
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        source_artifact_sha256=evaluation.content_sha256,
        surfaces=(ResearchLearningSurface.CAMPAIGN_HISTORY,),
    )

    with pytest.raises(FixtureObservationError, match="OBSERVATION surface"):
        replace(_success_observation(), input_admission=admission, evaluation=evaluation)


def test_rejected_research_input_cannot_enter_observation() -> None:
    rejected = ResearchInputAdmissionContract(
        input_id="rejected-clinical-input",
        classification_policy_sha256="e" * 64,
        classification=ResearchInputClassification.PHI_OR_PATIENT_DATA,
        source_artifact_sha256=None,
        source_contract_sha256=None,
        allowed_learning_surfaces=(),
    )

    with pytest.raises(FixtureObservationError, match="structurally learning-admitted"):
        replace(_success_observation(), input_admission=rejected)


def test_failed_observation_uses_negative_result_admission_and_no_metric_claim() -> None:
    raw_sha256 = "7" * 64
    observation = StructuredFixtureObservation(
        observation_id="fixture-observation-failed",
        input_admission=_admission(
            classification=ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
            source_artifact_sha256=raw_sha256,
        ),
        run_status=FixtureObservationRunStatus.FAILED,
        evaluation=None,
        resource_use=FixtureObservationResourceUse(
            operation_count=2,
            evaluator_invocations=0,
            storage_bytes=64,
        ),
        failure_class=FixtureObservationFailureClass.EXECUTION_FAILED,
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDERR,
                artifact_sha256=raw_sha256,
            ),
        ),
        diagnostics=(),
    )
    payload = observation.semantic_dict()

    assert payload["run_status"] == "FAILED"
    assert payload["failure_class"] == "EXECUTION_FAILED"
    assert payload["metric_artifacts"] == []
    assert payload["selected_metric_values"] == []
    assert payload["tier_accounting"] == {
        "tier": 0,
        "queries_used": 0,
        "result_exposures_used": 0,
        "exposed_result_fields": [],
    }


def test_failed_observation_source_must_be_retained_by_identity() -> None:
    raw_sha256 = "7" * 64
    admission = _admission(
        classification=ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
        source_artifact_sha256=raw_sha256,
    )

    with pytest.raises(FixtureObservationError, match="retained as a raw-output artifact identity"):
        StructuredFixtureObservation(
            observation_id="fixture-observation-failed",
            input_admission=admission,
            run_status=FixtureObservationRunStatus.FAILED,
            evaluation=None,
            resource_use=FixtureObservationResourceUse(
                operation_count=2,
                evaluator_invocations=0,
                storage_bytes=64,
            ),
            failure_class=FixtureObservationFailureClass.EXECUTION_FAILED,
            raw_output_artifacts=(),
        )


def test_success_and_failure_fields_cannot_be_mixed() -> None:
    with pytest.raises(FixtureObservationError, match="cannot declare a failure class"):
        replace(
            _success_observation(),
            failure_class=FixtureObservationFailureClass.INVALID_RESULT,
        )

    with pytest.raises(FixtureObservationError, match="cannot claim a successful evaluation"):
        replace(
            _success_observation(),
            run_status=FixtureObservationRunStatus.FAILED,
            failure_class=FixtureObservationFailureClass.INVALID_RESULT,
        )


def test_raw_output_artifacts_are_unique_and_sorted() -> None:
    duplicate = FixtureRawOutputArtifact(
        stream=FixtureRawOutputStream.STDOUT,
        artifact_sha256="f" * 64,
    )

    with pytest.raises(FixtureObservationError, match="unique and strictly sorted"):
        replace(_success_observation(), raw_output_artifacts=(duplicate, duplicate))


def test_diagnostics_are_bounded_and_cannot_contain_control_characters() -> None:
    with pytest.raises(FixtureObservationError, match="bounded length"):
        FixtureObservationDiagnostic(code="too-long", detail="x" * 257)
    with pytest.raises(FixtureObservationError, match="control characters"):
        FixtureObservationDiagnostic(code="multiline", detail="first\nsecond")


def test_post_construction_tamper_fails_closed() -> None:
    observation = _success_observation()
    object.__setattr__(observation, "fixture_only", False)

    with pytest.raises(FixtureObservationError, match="fixture_only"):
        observation.semantic_dict()


def test_derived_observation_cannot_override_snapshot_dispatch() -> None:
    trusted = _success_observation()

    class DerivedObservation(StructuredFixtureObservation):
        def _validated_snapshot(self) -> StructuredFixtureObservation:
            return trusted

    derived = DerivedObservation(
        observation_id=trusted.observation_id,
        input_admission=trusted.input_admission,
        run_status=trusted.run_status,
        evaluation=trusted.evaluation,
        resource_use=trusted.resource_use,
        failure_class=trusted.failure_class,
        raw_output_artifacts=trusted.raw_output_artifacts,
        diagnostics=trusted.diagnostics,
    )

    with pytest.raises(FixtureObservationError, match="must be exact StructuredFixtureObservation"):
        derived.semantic_dict()


def test_derived_evaluation_is_rejected_before_snapshot_use() -> None:
    base = _evaluation()

    class DerivedEvaluation(FixtureEvaluation):
        pass

    derived = DerivedEvaluation(
        surface_sha256=base.surface_sha256,
        evaluator_sha256=base.evaluator_sha256,
        candidate_sha256=base.candidate_sha256,
        metric_id=base.metric_id,
        score=base.score,
        max_score=base.max_score,
    )

    with pytest.raises(FixtureObservationError, match="must be exact FixtureEvaluation"):
        replace(_success_observation(), evaluation=derived)


def test_derived_admission_is_rejected_before_snapshot_dispatch() -> None:
    trusted = _success_observation().input_admission

    class DerivedAdmission(ResearchInputAdmissionContract):
        def _validated_snapshot(self) -> ResearchInputAdmissionContract:
            return trusted

    derived = DerivedAdmission(
        input_id=trusted.input_id,
        classification_policy_sha256=trusted.classification_policy_sha256,
        classification=trusted.classification,
        source_artifact_sha256=trusted.source_artifact_sha256,
        source_contract_sha256=trusted.source_contract_sha256,
        allowed_learning_surfaces=trusted.allowed_learning_surfaces,
        source_permission=trusted.source_permission,
        transformation_kind=trusted.transformation_kind,
        parent_inputs=trusted.parent_inputs,
    )

    with pytest.raises(FixtureObservationError, match="must be exact ResearchInputAdmissionContract"):
        replace(_success_observation(), input_admission=derived)
