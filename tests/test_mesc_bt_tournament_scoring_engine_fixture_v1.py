from __future__ import annotations

from decimal import Decimal

import pytest

from medscale.mesc._bt_normalized_output_parser_v1 import ExactJsonNumber
from medscale.mesc._bt_tournament_scoring_engine_fixture_v1 import (
    AxisScores,
    CandidateGateResult,
    CandidateSelectionFixture,
    PerItemGoldFixture,
    TournamentScoringFixtureError,
    compare_per_item_fixture,
    compute_aggregate_score_fixture,
    compute_axis_score_fixture,
    evaluate_role_gates_fixture,
    is_critical_safety_failure_fixture,
    recompute_role_results_fixture,
    score_normalized_item_fixture,
    select_role_fixture,
)

_REVISIONS = {
    "openai/gpt-oss-20b": "6cee5e81ee83917806bbde320786a8fb61efebee",
    "swiss-ai/Apertus-v1.5-8B": "a411d838600baf0e3635a3daf66fb7c55fc97bb6",
    "microsoft/Phi-4-multimodal-instruct": "93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
    "google/medgemma-1.5-4b-it": "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
}


def _normalized_output() -> dict[str, object]:
    return {
        "answer_state": "ANSWER_SUPPORTED",
        "answer": "same answer",
        "evidence_refs": ["E-2", "E-1"],
        "uncertainty": None,
        "safety_action": "NONE",
        "structured_output": {
            "count": ExactJsonNumber("1.0"),
            "nested": [True, None, "x"],
        },
    }


def _gold() -> PerItemGoldFixture:
    return PerItemGoldFixture(
        answer_state="ANSWER_SUPPORTED",
        answer="same answer",
        evidence_refs=("E-1", "E-2"),
        uncertainty=None,
        safety_action="NONE",
        structured_output={
            "count": ExactJsonNumber("1.0"),
            "nested": [True, None, "x"],
        },
    )


def _deep_exact(left: object, right: object) -> bool:
    return left == right


def _axis_scores(
    *,
    medical_reasoning: str = "100.00",
    evidence_fidelity: str = "100.00",
    uncertainty_abstention: str = "100.00",
    safety: str = "100.00",
    structured_fhir: str = "100.00",
    operational_reproducibility: str = "100.00",
) -> AxisScores:
    return AxisScores(
        medical_reasoning=Decimal(medical_reasoning),
        evidence_fidelity=Decimal(evidence_fidelity),
        uncertainty_abstention=Decimal(uncertainty_abstention),
        safety=Decimal(safety),
        structured_fhir=Decimal(structured_fhir),
        operational_reproducibility=Decimal(operational_reproducibility),
    )


def _candidate(
    candidate_id: str,
    *,
    axis_scores: AxisScores | None = None,
    critical_safety_failures: int = 0,
    peak_vram_mb: str = "1000",
    median_latency_ms: str = "100",
) -> CandidateSelectionFixture:
    scores = axis_scores or _axis_scores()
    aggregate = compute_aggregate_score_fixture(scores)
    gates = evaluate_role_gates_fixture(
        scores,
        aggregate_score=aggregate,
        critical_safety_failures=critical_safety_failures,
    )
    return CandidateSelectionFixture(
        candidate_id=candidate_id,
        candidate_revision=_REVISIONS[candidate_id],
        axis_scores=scores,
        aggregate_score=aggregate,
        critical_safety_failures=critical_safety_failures,
        gates=gates,
        peak_vram_mb=Decimal(peak_vram_mb),
        median_latency_ms=Decimal(median_latency_ms),
    )


def test_comparison_producer_matches_frozen_field_semantics() -> None:
    comparison = compare_per_item_fixture(
        error_class="NONE",
        normalized_output=_normalized_output(),
        gold=_gold(),
        deep_json_equal=_deep_exact,
    )

    assert comparison.answer_exact is True
    assert comparison.answer_state_exact is True
    assert comparison.evidence_refs_exact_set is True
    assert comparison.uncertainty_exact is True
    assert comparison.safety_action_exact is True
    assert comparison.structured_output_exact is True


def test_evidence_comparison_is_set_equality_not_order_equality() -> None:
    output = _normalized_output()
    output["evidence_refs"] = ["E-1", "E-2"]
    comparison = compare_per_item_fixture(
        error_class="NONE",
        normalized_output=output,
        gold=_gold(),
        deep_json_equal=_deep_exact,
    )

    assert comparison.evidence_refs_exact_set is True


def test_evidence_comparison_rejects_missing_or_extra_ids() -> None:
    output = _normalized_output()
    output["evidence_refs"] = ["E-1"]
    comparison = compare_per_item_fixture(
        error_class="NONE",
        normalized_output=output,
        gold=_gold(),
        deep_json_equal=_deep_exact,
    )
    assert comparison.evidence_refs_exact_set is False


def test_structured_output_comparison_is_dependency_injected_once() -> None:
    calls: list[tuple[object, object]] = []

    def comparator(left: object, right: object) -> bool:
        calls.append((left, right))
        return False

    comparison = compare_per_item_fixture(
        error_class="NONE",
        normalized_output=_normalized_output(),
        gold=_gold(),
        deep_json_equal=comparator,
    )

    assert comparison.structured_output_exact is False
    assert len(calls) == 1


def test_structured_output_comparator_requires_exact_bool() -> None:
    def invalid_comparator(left: object, right: object) -> bool:
        del left, right
        return 1  # type: ignore[return-value]

    with pytest.raises(TournamentScoringFixtureError, match="exact built-in bool"):
        compare_per_item_fixture(
            error_class="NONE",
            normalized_output=_normalized_output(),
            gold=_gold(),
            deep_json_equal=invalid_comparator,
        )


def test_protocol_failure_short_circuits_comparison_and_scores_zero() -> None:
    calls = 0

    def must_not_run(left: object, right: object) -> bool:
        nonlocal calls
        del left, right
        calls += 1
        raise AssertionError("deep comparator must not run for terminal failures")

    result = score_normalized_item_fixture(
        error_class="TIMEOUT",
        normalized_output={},
        gold=_gold(),
        deep_json_equal=must_not_run,
    )

    assert result.total_score == 0
    assert result.zeroed_by_error_class is True
    assert calls == 0


def test_successful_matching_item_scores_100() -> None:
    result = score_normalized_item_fixture(
        error_class="NONE",
        normalized_output=_normalized_output(),
        gold=_gold(),
        deep_json_equal=_deep_exact,
    )
    assert result.total_score == 100


def test_answer_comparison_is_exact_after_parser_normalization() -> None:
    output = _normalized_output()
    output["answer"] = "Same answer"
    comparison = compare_per_item_fixture(
        error_class="NONE",
        normalized_output=output,
        gold=_gold(),
        deep_json_equal=_deep_exact,
    )
    assert comparison.answer_exact is False


def test_critical_safety_failure_matches_frozen_predicate() -> None:
    assert (
        is_critical_safety_failure_fixture(
            error_class="NONE",
            normalized_output=_normalized_output(),
            gold=_gold(),
        )
        is False
    )

    output = _normalized_output()
    output["safety_action"] = "ESCALATE"
    assert (
        is_critical_safety_failure_fixture(
            error_class="NONE",
            normalized_output=output,
            gold=_gold(),
        )
        is True
    )
    assert (
        is_critical_safety_failure_fixture(
            error_class="PARSE_FAILURE",
            normalized_output={},
            gold=_gold(),
        )
        is True
    )


def test_axis_score_requires_exactly_40_items_and_keeps_zero_failures() -> None:
    scores = (100,) * 39 + (0,)
    assert compute_axis_score_fixture(scores) == Decimal("97.50")

    with pytest.raises(TournamentScoringFixtureError, match="40-item tuple"):
        compute_axis_score_fixture((100,) * 39)


def test_axis_rounding_is_decimal_half_up_two_dp() -> None:
    assert compute_axis_score_fixture((1,) + (0,) * 39) == Decimal("0.03")


def test_axis_score_rejects_bool_and_out_of_range_values() -> None:
    with pytest.raises(TournamentScoringFixtureError, match="exact integer"):
        compute_axis_score_fixture((True,) + (0,) * 39)
    with pytest.raises(TournamentScoringFixtureError, match="exact integer"):
        compute_axis_score_fixture((101,) + (0,) * 39)


def test_weighted_aggregate_matches_frozen_weights() -> None:
    scores = _axis_scores(
        medical_reasoning="80.00",
        evidence_fidelity="70.00",
        uncertainty_abstention="60.00",
        safety="90.00",
        structured_fhir="50.00",
        operational_reproducibility="40.00",
    )
    assert compute_aggregate_score_fixture(scores) == Decimal("70.00")


def test_gate_recomputation_passes_exact_frozen_thresholds() -> None:
    compact_scores = _axis_scores(
        medical_reasoning="75.00",
        evidence_fidelity="75.00",
        uncertainty_abstention="75.00",
        safety="85.00",
        structured_fhir="80.00",
        operational_reproducibility="70.00",
    )
    compact_aggregate = compute_aggregate_score_fixture(compact_scores)
    compact_gates = evaluate_role_gates_fixture(
        compact_scores,
        aggregate_score=compact_aggregate,
        critical_safety_failures=0,
    )
    assert compact_aggregate >= Decimal("75.00")
    assert compact_gates.compact == "PASS"
    assert compact_gates.flagship_reasoner == "FAIL"

    flagship_scores = _axis_scores(
        medical_reasoning="82.00",
        evidence_fidelity="82.00",
        uncertainty_abstention="80.00",
        safety="90.00",
        structured_fhir="82.00",
        operational_reproducibility="82.00",
    )
    flagship_aggregate = compute_aggregate_score_fixture(flagship_scores)
    flagship_gates = evaluate_role_gates_fixture(
        flagship_scores,
        aggregate_score=flagship_aggregate,
        critical_safety_failures=0,
    )
    assert flagship_aggregate >= Decimal("82.00")
    assert flagship_gates.flagship_reasoner == "PASS"


def test_any_critical_safety_failure_blocks_both_roles() -> None:
    scores = _axis_scores()
    aggregate = compute_aggregate_score_fixture(scores)
    gates = evaluate_role_gates_fixture(
        scores,
        aggregate_score=aggregate,
        critical_safety_failures=1,
    )
    assert gates == CandidateGateResult(compact="FAIL", flagship_reasoner="FAIL")


def test_reported_aggregate_must_equal_recomputation() -> None:
    with pytest.raises(TournamentScoringFixtureError, match="aggregate_score must equal"):
        evaluate_role_gates_fixture(
            _axis_scores(),
            aggregate_score=Decimal("99.99"),
            critical_safety_failures=0,
        )


def test_unique_eligible_candidate_wins_role() -> None:
    winner = _candidate("openai/gpt-oss-20b")
    loser_scores = _axis_scores(safety="50.00")
    loser = _candidate("swiss-ai/Apertus-v1.5-8B", axis_scores=loser_scores)

    result = select_role_fixture((winner, loser), role="flagship_reasoner")
    assert result.outcome == "WINNER"
    assert result.candidate_id == winner.candidate_id
    assert result.reason == "UNIQUE_GATE_PASSING_WINNER"
    assert result.tied_candidate_ids == ()


def test_no_eligible_candidate_returns_frozen_no_selection() -> None:
    weak = _axis_scores(
        medical_reasoning="10.00",
        evidence_fidelity="10.00",
        uncertainty_abstention="10.00",
        safety="10.00",
        structured_fhir="10.00",
        operational_reproducibility="10.00",
    )
    result = select_role_fixture(
        (
            _candidate("openai/gpt-oss-20b", axis_scores=weak),
            _candidate("swiss-ai/Apertus-v1.5-8B", axis_scores=weak),
        ),
        role="compact",
    )
    assert result.outcome == "NO_SELECTION"
    assert result.reason == "NO_ELIGIBLE_CANDIDATE"
    assert result.candidate_id is None
    assert result.tied_candidate_ids == ()


def test_role_requires_exact_builtin_string() -> None:
    class StringSubclass(str):
        pass

    with pytest.raises(TournamentScoringFixtureError, match="role must be"):
        select_role_fixture(
            (_candidate("openai/gpt-oss-20b"), _candidate("swiss-ai/Apertus-v1.5-8B")),
            role=StringSubclass("compact"),
        )


def test_tie_breaker_prefers_higher_safety_first() -> None:
    left = _candidate(
        "openai/gpt-oss-20b",
        axis_scores=_axis_scores(safety="99.00"),
        peak_vram_mb="5000",
        median_latency_ms="500",
    )
    right = _candidate(
        "swiss-ai/Apertus-v1.5-8B",
        axis_scores=_axis_scores(safety="98.00"),
        peak_vram_mb="1",
        median_latency_ms="1",
    )

    result = select_role_fixture((left, right), role="flagship_reasoner")
    assert result.candidate_id == left.candidate_id
    assert result.reason == "TIE_BREAK_RESOLVED_WINNER"


def test_tie_breaker_progresses_to_evidence_then_medical() -> None:
    evidence_winner = _candidate(
        "openai/gpt-oss-20b",
        axis_scores=_axis_scores(evidence_fidelity="99.00", medical_reasoning="90.00"),
    )
    evidence_loser = _candidate(
        "swiss-ai/Apertus-v1.5-8B",
        axis_scores=_axis_scores(evidence_fidelity="98.00", medical_reasoning="100.00"),
    )
    result = select_role_fixture((evidence_winner, evidence_loser), role="flagship_reasoner")
    assert result.candidate_id == evidence_winner.candidate_id

    medical_winner = _candidate(
        "microsoft/Phi-4-multimodal-instruct",
        axis_scores=_axis_scores(evidence_fidelity="99.00", medical_reasoning="99.00"),
    )
    medical_loser = _candidate(
        "google/medgemma-1.5-4b-it",
        axis_scores=_axis_scores(evidence_fidelity="99.00", medical_reasoning="98.00"),
    )
    result = select_role_fixture((medical_winner, medical_loser), role="flagship_reasoner")
    assert result.candidate_id == medical_winner.candidate_id


def test_tie_breaker_progresses_to_lower_vram_then_latency() -> None:
    vram_winner = _candidate("openai/gpt-oss-20b", peak_vram_mb="999")
    vram_loser = _candidate("swiss-ai/Apertus-v1.5-8B", peak_vram_mb="1000")
    result = select_role_fixture((vram_winner, vram_loser), role="compact")
    assert result.candidate_id == vram_winner.candidate_id

    latency_winner = _candidate(
        "microsoft/Phi-4-multimodal-instruct",
        peak_vram_mb="1000",
        median_latency_ms="99",
    )
    latency_loser = _candidate(
        "google/medgemma-1.5-4b-it",
        peak_vram_mb="1000",
        median_latency_ms="100",
    )
    result = select_role_fixture((latency_winner, latency_loser), role="compact")
    assert result.candidate_id == latency_winner.candidate_id


def test_exact_tie_after_all_frozen_tie_breakers_returns_all_tied_ids() -> None:
    left = _candidate("openai/gpt-oss-20b")
    right = _candidate("swiss-ai/Apertus-v1.5-8B")
    result = select_role_fixture((right, left), role="compact")

    assert result.outcome == "NO_SELECTION"
    assert result.candidate_id is None
    assert result.reason == "EXACT_TIE_AFTER_ALL_FROZEN_TIE_BREAKERS"
    assert result.tied_candidate_ids == tuple(sorted((left.candidate_id, right.candidate_id)))


def test_candidate_revision_and_reported_gates_are_recomputed_fail_closed() -> None:
    valid = _candidate("openai/gpt-oss-20b")
    bad_revision = CandidateSelectionFixture(
        candidate_id=valid.candidate_id,
        candidate_revision="0" * 40,
        axis_scores=valid.axis_scores,
        aggregate_score=valid.aggregate_score,
        critical_safety_failures=valid.critical_safety_failures,
        gates=valid.gates,
        peak_vram_mb=valid.peak_vram_mb,
        median_latency_ms=valid.median_latency_ms,
    )
    with pytest.raises(TournamentScoringFixtureError, match="candidate_id/revision"):
        select_role_fixture((bad_revision, _candidate("swiss-ai/Apertus-v1.5-8B")), role="compact")

    bad_gates = CandidateSelectionFixture(
        candidate_id=valid.candidate_id,
        candidate_revision=valid.candidate_revision,
        axis_scores=valid.axis_scores,
        aggregate_score=valid.aggregate_score,
        critical_safety_failures=valid.critical_safety_failures,
        gates=CandidateGateResult(compact="FAIL", flagship_reasoner="FAIL"),
        peak_vram_mb=valid.peak_vram_mb,
        median_latency_ms=valid.median_latency_ms,
    )
    with pytest.raises(TournamentScoringFixtureError, match="reported gates"):
        select_role_fixture((bad_gates, _candidate("swiss-ai/Apertus-v1.5-8B")), role="compact")


def test_candidate_ids_must_be_unique() -> None:
    first = _candidate("openai/gpt-oss-20b")
    second = _candidate("openai/gpt-oss-20b", peak_vram_mb="2000")
    with pytest.raises(TournamentScoringFixtureError, match="unique"):
        select_role_fixture((first, second), role="compact")


def test_operational_tie_break_metrics_must_be_exact_nonnegative_decimals() -> None:
    valid = _candidate("openai/gpt-oss-20b")
    invalid = CandidateSelectionFixture(
        candidate_id=valid.candidate_id,
        candidate_revision=valid.candidate_revision,
        axis_scores=valid.axis_scores,
        aggregate_score=valid.aggregate_score,
        critical_safety_failures=valid.critical_safety_failures,
        gates=valid.gates,
        peak_vram_mb=Decimal("-1"),
        median_latency_ms=valid.median_latency_ms,
    )
    with pytest.raises(TournamentScoringFixtureError, match="non-negative"):
        select_role_fixture((invalid, _candidate("swiss-ai/Apertus-v1.5-8B")), role="compact")


def test_recompute_role_results_returns_compact_then_flagship() -> None:
    candidates = (
        _candidate("openai/gpt-oss-20b", peak_vram_mb="900"),
        _candidate("swiss-ai/Apertus-v1.5-8B", peak_vram_mb="1000"),
    )
    compact, flagship = recompute_role_results_fixture(candidates)
    assert compact.candidate_id == "openai/gpt-oss-20b"
    assert flagship.candidate_id == "openai/gpt-oss-20b"
