"""MRL-0407 tests for append-only governed procedure-registry history."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_procedure_admission_gate_v1 import (
    ProcedureAdmissionGateResult,
    evaluate_procedure_admission,
)
from medscale.mesc._mrl_procedure_negative_control_v1 import (
    build_procedure_negative_control_report,
)
from medscale.mesc._mrl_procedure_registry_v1 import (
    ProcedureRegistry,
    ProcedureRegistryDisposition,
    ProcedureRegistryError,
    invalidate_admitted_procedure,
    register_procedure_admission,
    supersede_admitted_procedure,
)
from medscale.mesc._mrl_procedure_replay_v1 import replay_procedure_fixture
from medscale.mesc._mrl_procedure_transfer_test_v1 import (
    ProcedureTransferCaseEvidence,
    build_procedure_transfer_test_report,
)
from medscale.mesc._mrl_research_procedure_v1 import ProcedureAdmissionDecision
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_procedure_admission_gate_v1 import _review_receipt, _trusted_receipt
from test_mesc_mrl_procedure_negative_control_v1 import _passing_case
from test_mesc_mrl_procedure_transfer_test_v1 import _case_bounds
from test_mesc_mrl_research_procedure_v1 import _candidate_procedure


def _gate_result(
    label: str,
    *,
    decision: ProcedureAdmissionDecision = ProcedureAdmissionDecision.ADMIT,
) -> ProcedureAdmissionGateResult:
    procedure = replace(_candidate_procedure(), procedure_id=f"registry-{label}")
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
    transfer = build_procedure_transfer_test_report(
        procedure,
        (
            ProcedureTransferCaseEvidence(
                case_id=f"{label}-case-a",
                applicability_bounds=_case_bounds("Representative transfer case A."),
                replay_receipt=first_replay,
                evidence_artifact_sha256="1" * 64,
            ),
            ProcedureTransferCaseEvidence(
                case_id=f"{label}-case-b",
                applicability_bounds=_case_bounds("Representative transfer case B."),
                replay_receipt=second_replay,
                evidence_artifact_sha256="2" * 64,
            ),
        ),
    )
    negative = build_procedure_negative_control_report(
        procedure,
        (_passing_case(),),
    )
    receipt = _review_receipt(
        procedure,
        transfer,
        negative,
        decision=decision,
    )
    with _trusted_receipt(receipt) as registry_sha256:
        return evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=registry_sha256,
        )


def test_registry_records_admitted_and_rejected_gate_results_deterministically() -> None:
    admitted = _gate_result("admitted")
    rejected = _gate_result("rejected", decision=ProcedureAdmissionDecision.REJECT)

    first = register_procedure_admission(ProcedureRegistry(), admitted)
    first = register_procedure_admission(first, rejected)
    second = register_procedure_admission(ProcedureRegistry(), admitted)
    second = register_procedure_admission(second, rejected)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.current_event(admitted.procedure_sha256).disposition is (
        ProcedureRegistryDisposition.ADMITTED
    )
    assert first.current_event(rejected.procedure_sha256).disposition is (
        ProcedureRegistryDisposition.REJECTED
    )
    assert first.active_admitted_procedure_sha256s == (admitted.procedure_sha256,)
    assert first.can_authorize_model_promotion is False


def test_invalidation_preserves_original_admission_evidence_append_only() -> None:
    admitted = _gate_result("invalidate")
    registry = register_procedure_admission(ProcedureRegistry(), admitted)
    admission_event_sha256 = registry.events[0].content_sha256
    gate_result_sha256 = admitted.content_sha256

    invalidated = invalidate_admitted_procedure(
        registry,
        admitted.procedure_sha256,
        evidence_sha256s=("a" * 64,),
        reason="A later known boundary violation invalidated reuse.",
    )

    assert len(invalidated.events) == 2
    assert invalidated.events[0].content_sha256 == admission_event_sha256
    assert invalidated.events[0].admission_result.content_sha256 == gate_result_sha256
    assert invalidated.events[1].admission_result.content_sha256 == gate_result_sha256
    assert invalidated.events[1].previous_event_sha256 == admission_event_sha256
    assert invalidated.current_event(admitted.procedure_sha256).disposition is (
        ProcedureRegistryDisposition.INVALIDATED
    )
    assert invalidated.active_admitted_procedure_sha256s == ()


def test_supersession_requires_replacement_to_be_independently_admitted_first() -> None:
    original = _gate_result("original")
    replacement = _gate_result("replacement")
    registry = register_procedure_admission(ProcedureRegistry(), original)

    with pytest.raises(
        ProcedureRegistryError,
        match="not present in the registry",
    ):
        supersede_admitted_procedure(
            registry,
            original.procedure_sha256,
            replacement_procedure_sha256=replacement.procedure_sha256,
            evidence_sha256s=("b" * 64,),
            reason="Replacement was not independently admitted yet.",
        )

    registry = register_procedure_admission(registry, replacement)
    superseded = supersede_admitted_procedure(
        registry,
        original.procedure_sha256,
        replacement_procedure_sha256=replacement.procedure_sha256,
        evidence_sha256s=("b" * 64,),
        reason="Independent evidence established the replacement procedure.",
    )

    assert len(superseded.events) == 3
    assert superseded.current_event(original.procedure_sha256).disposition is (
        ProcedureRegistryDisposition.SUPERSEDED
    )
    assert superseded.current_event(original.procedure_sha256).replacement_procedure_sha256 == (
        replacement.procedure_sha256
    )
    assert superseded.current_event(replacement.procedure_sha256).disposition is (
        ProcedureRegistryDisposition.ADMITTED
    )
    assert superseded.active_admitted_procedure_sha256s == (replacement.procedure_sha256,)


def test_rejected_or_terminal_history_cannot_be_rewritten() -> None:
    rejected = _gate_result("terminal-reject", decision=ProcedureAdmissionDecision.REJECT)
    rejected_registry = register_procedure_admission(ProcedureRegistry(), rejected)
    with pytest.raises(ProcedureRegistryError, match="only an active admitted"):
        invalidate_admitted_procedure(
            rejected_registry,
            rejected.procedure_sha256,
            evidence_sha256s=("c" * 64,),
            reason="Rejected history must remain terminal.",
        )

    admitted = _gate_result("terminal-admit")
    invalidated = invalidate_admitted_procedure(
        register_procedure_admission(ProcedureRegistry(), admitted),
        admitted.procedure_sha256,
        evidence_sha256s=("d" * 64,),
        reason="Known failure invalidated the admitted procedure.",
    )
    with pytest.raises(ProcedureRegistryError, match="only an active admitted"):
        invalidate_admitted_procedure(
            invalidated,
            admitted.procedure_sha256,
            evidence_sha256s=("e" * 64,),
            reason="Terminal invalidation cannot be rewritten.",
        )


def test_registry_rejects_duplicate_first_history_for_same_procedure() -> None:
    admitted = _gate_result("duplicate")
    registry = register_procedure_admission(ProcedureRegistry(), admitted)

    with pytest.raises(ProcedureRegistryError, match="already has registry history"):
        register_procedure_admission(registry, admitted)


def test_registry_fails_closed_if_original_admission_evidence_mutates() -> None:
    admitted = _gate_result("mutation")
    registry = register_procedure_admission(ProcedureRegistry(), admitted)
    object.__setattr__(
        admitted.review_receipt,
        "reason",
        "A different but syntactically valid review reason.",
    )

    with pytest.raises(
        ProcedureRegistryError,
        match="admission result failed canonical revalidation",
    ):
        _ = registry.content_sha256


def test_registry_fails_closed_if_append_only_event_chain_is_mutated() -> None:
    admitted = _gate_result("chain")
    registry = register_procedure_admission(ProcedureRegistry(), admitted)
    registry = invalidate_admitted_procedure(
        registry,
        admitted.procedure_sha256,
        evidence_sha256s=("f" * 64,),
        reason="Known boundary failure.",
    )
    object.__setattr__(registry.events[1], "previous_event_sha256", "0" * 64)

    with pytest.raises(ProcedureRegistryError):
        _ = registry.semantic_dict()
