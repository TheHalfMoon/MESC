"""MRL-0404 tests for representative procedure transfer evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_procedure_replay_v1 import replay_procedure_fixture
from medscale.mesc._mrl_procedure_transfer_test_v1 import (
    ProcedureTransferCaseEvidence,
    ProcedureTransferTestError,
    build_procedure_transfer_test_report,
)
from medscale.mesc._mrl_research_procedure_v1 import ProcedureApplicabilityBounds
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_research_procedure_v1 import _bounds, _candidate_procedure


def _case_bounds(label: str) -> ProcedureApplicabilityBounds:
    base = _bounds()
    return ProcedureApplicabilityBounds(
        research_program_refs=base.research_program_refs,
        task_types=base.task_types,
        model_classes=base.model_classes,
        data_classes=base.data_classes,
        evaluation_tiers=base.evaluation_tiers,
        constraints=tuple(sorted((*base.constraints, label))),
    )


def _cases() -> tuple[ProcedureTransferCaseEvidence, ProcedureTransferCaseEvidence]:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    first_replay = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )
    second_replay = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(beta=10),
        expected_score=2,
        expected_max_score=2,
    )
    return (
        ProcedureTransferCaseEvidence(
            case_id="case-a",
            applicability_bounds=_case_bounds("Representative transfer case A."),
            replay_receipt=first_replay,
            evidence_artifact_sha256="1" * 64,
        ),
        ProcedureTransferCaseEvidence(
            case_id="case-b",
            applicability_bounds=_case_bounds("Representative transfer case B."),
            replay_receipt=second_replay,
            evidence_artifact_sha256="2" * 64,
        ),
    )


def test_representative_transfer_report_is_deterministic_and_reproduced() -> None:
    procedure = _candidate_procedure()
    cases = _cases()

    first = build_procedure_transfer_test_report(procedure, cases)
    second = build_procedure_transfer_test_report(procedure, cases)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.procedure_sha256 == procedure.admission_subject_sha256
    assert first.all_cases_reproduced is True
    assert first.can_advance_admission is False
    assert first.can_authorize is False


def test_transfer_report_preserves_replay_mismatch_as_failure_evidence() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    cases = list(_cases())
    mismatched = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(beta=10),
        expected_score=1,
        expected_max_score=2,
    )
    cases[1] = replace(cases[1], replay_receipt=mismatched)

    report = build_procedure_transfer_test_report(procedure, tuple(cases))

    assert report.all_cases_reproduced is False


def test_transfer_requires_at_least_two_distinct_cases() -> None:
    procedure = _candidate_procedure()
    case = _cases()[0]

    with pytest.raises(ProcedureTransferTestError, match="at least two"):
        build_procedure_transfer_test_report(procedure, (case,))


def test_transfer_rejects_duplicate_replay_evidence_under_distinct_case_ids() -> None:
    procedure = _candidate_procedure()
    cases = list(_cases())
    cases[1] = replace(cases[1], replay_receipt=cases[0].replay_receipt)

    with pytest.raises(ProcedureTransferTestError, match="distinct replay evidence"):
        build_procedure_transfer_test_report(procedure, tuple(cases))


def test_transfer_rejects_same_candidate_with_distinct_replay_metadata() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    cases = list(_cases())
    same_candidate_new_replay = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=0,
        expected_max_score=2,
    )
    assert same_candidate_new_replay.content_sha256 != cases[0].replay_receipt.content_sha256
    assert same_candidate_new_replay.candidate_sha256 == cases[0].replay_receipt.candidate_sha256
    cases[1] = replace(cases[1], replay_receipt=same_candidate_new_replay)

    with pytest.raises(ProcedureTransferTestError, match="distinct fixture candidate"):
        build_procedure_transfer_test_report(procedure, tuple(cases))


def test_transfer_case_cannot_escape_procedure_applicability() -> None:
    procedure = _candidate_procedure()
    cases = list(_cases())
    escaped = ProcedureApplicabilityBounds(
        research_program_refs=("MRL-RQ1",),
        task_types=("fixture-research",),
        model_classes=("fixture-model",),
        data_classes=("synthetic-fixture",),
        evaluation_tiers=_bounds().evaluation_tiers,
        constraints=_bounds().constraints,
    )
    cases[1] = replace(cases[1], applicability_bounds=escaped)

    with pytest.raises(ProcedureTransferTestError, match="within procedure applicability"):
        build_procedure_transfer_test_report(procedure, tuple(cases))


def test_mutated_replay_receipt_fails_closed() -> None:
    procedure = _candidate_procedure()
    cases = list(_cases())
    object.__setattr__(cases[0].replay_receipt, "evaluation_sha256", "invalid")

    with pytest.raises(ProcedureTransferTestError, match="canonical revalidation"):
        build_procedure_transfer_test_report(procedure, tuple(cases))


def test_mutated_nested_case_fails_closed_on_report_public_views() -> None:
    procedure = _candidate_procedure()
    cases = _cases()
    report = build_procedure_transfer_test_report(procedure, cases)
    object.__setattr__(cases[0], "evidence_artifact_sha256", "invalid")

    with pytest.raises(ProcedureTransferTestError, match="64 lowercase hex"):
        _ = report.all_cases_reproduced
    with pytest.raises(ProcedureTransferTestError, match="64 lowercase hex"):
        _ = report.content_sha256
