"""MRL-0403 tests for deterministic fixture-only procedure replay."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_procedure_replay_v1 import (
    ProcedureReplayDisposition,
    ProcedureReplayError,
    ProcedureReplayReceipt,
    replay_procedure_fixture,
)
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_research_procedure_v1 import _candidate_procedure


def test_fixture_replay_is_deterministic_and_binds_exact_evidence() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)

    first = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )
    second = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.disposition is ProcedureReplayDisposition.REPRODUCED
    assert first.procedure_admission_subject_sha256 == procedure.admission_subject_sha256
    assert first.procedure_content_sha256 == procedure.content_sha256
    assert first.surface_sha256 == surface.content_sha256
    assert first.evaluator_sha256 == evaluator.content_sha256
    assert first.observed_score == 1
    assert first.observed_max_score == 2


def test_replay_mismatch_remains_first_class_evidence() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)

    receipt = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=2,
        expected_max_score=2,
    )

    assert receipt.disposition is ProcedureReplayDisposition.MISMATCH
    assert receipt.expected_score == 2
    assert receipt.observed_score == 1
    assert receipt.content_sha256


def test_replay_receipt_cannot_advance_admission_or_authorize() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )

    assert receipt.fixture_only is True
    assert receipt.non_evidence_for_real_execution is True
    assert receipt.can_advance_admission is False
    assert receipt.can_authorize is False
    assert receipt.can_authorize_training is False
    assert receipt.can_authorize_model_promotion is False
    assert b"ADMITTED" not in receipt.semantic_bytes
    assert b"REVIEWED" not in receipt.semantic_bytes
    assert b"PROMOTED" not in receipt.semantic_bytes


def test_receipt_disposition_cannot_disagree_with_observed_evidence() -> None:
    with pytest.raises(ProcedureReplayError, match="does not match"):
        ProcedureReplayReceipt(
            procedure_admission_subject_sha256="a" * 64,
            procedure_content_sha256="b" * 64,
            surface_sha256="c" * 64,
            evaluator_sha256="d" * 64,
            candidate_sha256="e" * 64,
            evaluation_sha256="f" * 64,
            metric_id="fixture-metric",
            expected_score=2,
            expected_max_score=2,
            observed_score=1,
            observed_max_score=2,
            disposition=ProcedureReplayDisposition.REPRODUCED,
        )


def test_mutated_receipt_identity_fails_closed_on_semantic_and_hash_views() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )
    object.__setattr__(receipt, "evaluation_sha256", "invalid")

    with pytest.raises(ProcedureReplayError, match="64 lowercase hex"):
        receipt.semantic_dict()
    with pytest.raises(ProcedureReplayError, match="64 lowercase hex"):
        _ = receipt.content_sha256


def test_valid_receipt_identity_mutation_fails_closed() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )
    object.__setattr__(receipt, "candidate_sha256", "f" * 64)

    with pytest.raises(ProcedureReplayError, match="identity changed"):
        receipt.semantic_dict()
    with pytest.raises(ProcedureReplayError, match="identity changed"):
        _ = receipt.content_sha256


def test_mutated_receipt_disposition_fails_closed_on_semantic_and_hash_views() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = replay_procedure_fixture(
        procedure,
        surface,
        evaluator,
        _values(),
        expected_score=1,
        expected_max_score=2,
    )
    object.__setattr__(receipt, "disposition", ProcedureReplayDisposition.MISMATCH)

    with pytest.raises(ProcedureReplayError, match="does not match"):
        receipt.semantic_dict()
    with pytest.raises(ProcedureReplayError, match="does not match"):
        _ = receipt.content_sha256


def test_mutated_procedure_fails_closed_before_replay_evidence() -> None:
    procedure = _candidate_procedure()
    object.__setattr__(procedure, "procedure_id", "INVALID")
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(ProcedureReplayError, match="canonical fixture validation"):
        replay_procedure_fixture(
            procedure,
            surface,
            evaluator,
            _values(),
            expected_score=1,
            expected_max_score=2,
        )


def test_replay_rejects_wrong_types_and_invalid_expected_scores() -> None:
    procedure = _candidate_procedure()
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(ProcedureReplayError, match="exact ResearchProcedure"):
        replay_procedure_fixture(
            object(),  # type: ignore[arg-type]
            surface,
            evaluator,
            _values(),
            expected_score=1,
            expected_max_score=2,
        )
    with pytest.raises(ProcedureReplayError, match="expected scores"):
        replay_procedure_fixture(
            procedure,
            surface,
            evaluator,
            _values(),
            expected_score=3,
            expected_max_score=2,
        )
