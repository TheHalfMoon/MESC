"""MRL-0405 tests for procedure negative and failure-control evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_procedure_negative_control_v1 import (
    NegativeControlDisposition,
    ProcedureNegativeControlCase,
    ProcedureNegativeControlError,
    build_procedure_negative_control_report,
)
from test_mesc_mrl_research_procedure_v1 import _candidate_procedure


def _passing_case() -> ProcedureNegativeControlCase:
    return ProcedureNegativeControlCase(
        control_id="budget-control",
        expected_failure_mode="budget-exhaustion",
        observed_failure_mode="budget-exhaustion",
        evidence_artifact_sha256="1" * 64,
    )


def test_negative_control_report_is_deterministic_and_complete() -> None:
    procedure = _candidate_procedure()

    first = build_procedure_negative_control_report(procedure, (_passing_case(),))
    second = build_procedure_negative_control_report(procedure, (_passing_case(),))

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.procedure_sha256 == procedure.admission_subject_sha256
    assert first.coverage_complete is True
    assert first.all_controls_pass is True
    assert first.can_advance_admission is False
    assert first.can_authorize is False


def test_unexpected_success_remains_first_class_failure_evidence() -> None:
    procedure = _candidate_procedure()
    case = replace(_passing_case(), observed_failure_mode=None)

    report = build_procedure_negative_control_report(procedure, (case,))

    assert case.disposition is NegativeControlDisposition.UNEXPECTED_SUCCESS
    assert report.coverage_complete is True
    assert report.all_controls_pass is False


def test_wrong_failure_mode_remains_first_class_failure_evidence() -> None:
    procedure = _candidate_procedure()
    case = replace(_passing_case(), observed_failure_mode="different-failure")

    report = build_procedure_negative_control_report(procedure, (case,))

    assert case.disposition is NegativeControlDisposition.WRONG_FAILURE_MODE
    assert report.all_controls_pass is False


def test_incomplete_failure_mode_coverage_is_visible_not_silently_accepted() -> None:
    procedure = replace(
        _candidate_procedure(),
        known_failure_modes=("budget-exhaustion", "verification-failure"),
    )

    report = build_procedure_negative_control_report(procedure, (_passing_case(),))

    assert report.coverage_complete is False
    assert report.all_controls_pass is False


def test_undeclared_failure_control_fails_closed() -> None:
    procedure = _candidate_procedure()
    case = replace(
        _passing_case(),
        expected_failure_mode="undeclared-failure",
        observed_failure_mode="undeclared-failure",
    )

    with pytest.raises(ProcedureNegativeControlError, match="undeclared"):
        build_procedure_negative_control_report(procedure, (case,))


def test_duplicate_control_evidence_fails_closed() -> None:
    procedure = replace(
        _candidate_procedure(),
        known_failure_modes=("budget-exhaustion", "verification-failure"),
    )
    first = _passing_case()
    second = ProcedureNegativeControlCase(
        control_id="verification-control",
        expected_failure_mode="verification-failure",
        observed_failure_mode="verification-failure",
        evidence_artifact_sha256="1" * 64,
    )

    with pytest.raises(ProcedureNegativeControlError, match="distinct evidence"):
        build_procedure_negative_control_report(procedure, (first, second))


def test_mutated_nested_control_fails_closed_on_report_public_views() -> None:
    procedure = _candidate_procedure()
    case = _passing_case()
    report = build_procedure_negative_control_report(procedure, (case,))
    object.__setattr__(case, "evidence_artifact_sha256", "invalid")

    with pytest.raises(ProcedureNegativeControlError, match="64 lowercase hex"):
        _ = report.all_controls_pass
    with pytest.raises(ProcedureNegativeControlError, match="64 lowercase hex"):
        _ = report.content_sha256


def test_valid_procedure_identity_mutation_fails_closed() -> None:
    procedure = _candidate_procedure()
    report = build_procedure_negative_control_report(procedure, (_passing_case(),))
    object.__setattr__(report, "procedure_sha256", "f" * 64)

    with pytest.raises(ProcedureNegativeControlError, match="identity changed"):
        _ = report.coverage_complete
    with pytest.raises(ProcedureNegativeControlError, match="identity changed"):
        _ = report.content_sha256


def test_mutated_control_failure_mode_fails_closed_on_disposition() -> None:
    case = _passing_case()
    object.__setattr__(case, "expected_failure_mode", "")

    with pytest.raises(ProcedureNegativeControlError, match="canonical non-empty text"):
        _ = case.disposition
