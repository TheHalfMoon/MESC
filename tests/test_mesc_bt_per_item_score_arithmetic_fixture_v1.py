"""Qualification for Backbone Tournament fixture per-item score arithmetic."""

from __future__ import annotations

import pytest

from medscale.mesc._bt_per_item_score_arithmetic_fixture_v1 import (
    PerItemComparisonObservation,
    PerItemScoreResult,
    score_per_item_comparison_fixture,
)


def _all_match() -> PerItemComparisonObservation:
    return PerItemComparisonObservation(
        error_class="NONE",
        answer_exact=True,
        answer_state_exact=True,
        evidence_refs_exact_set=True,
        uncertainty_exact=True,
        safety_action_exact=True,
        structured_output_exact=True,
    )


def _mutate_fixture_field(
    observation: PerItemComparisonObservation,
    field: str,
    value: object,
) -> PerItemComparisonObservation:
    object.__setattr__(observation, field, value)
    return observation


def test_all_matches_score_exactly_100() -> None:
    result = score_per_item_comparison_fixture(_all_match())

    assert result == PerItemScoreResult(
        answer_exact_points=35,
        answer_state_exact_points=25,
        evidence_refs_exact_set_points=25,
        uncertainty_exact_points=5,
        safety_action_exact_points=5,
        structured_output_exact_points=5,
        total_score=100,
        zeroed_by_error_class=False,
    )


@pytest.mark.parametrize(
    ("field", "expected_total", "expected_component"),
    [
        ("answer_exact", 65, 0),
        ("answer_state_exact", 75, 0),
        ("evidence_refs_exact_set", 75, 0),
        ("uncertainty_exact", 95, 0),
        ("safety_action_exact", 95, 0),
        ("structured_output_exact", 95, 0),
    ],
)
def test_each_frozen_field_weight_is_applied_exactly(
    field: str,
    expected_total: int,
    expected_component: int,
) -> None:
    observation = _mutate_fixture_field(_all_match(), field, False)
    result = score_per_item_comparison_fixture(observation)

    assert result.total_score == expected_total
    assert getattr(result, f"{field}_points") == expected_component
    assert result.zeroed_by_error_class is False


def test_all_non_error_comparisons_false_score_zero_without_failure_zeroing() -> None:
    result = score_per_item_comparison_fixture(
        PerItemComparisonObservation(
            error_class="NONE",
            answer_exact=False,
            answer_state_exact=False,
            evidence_refs_exact_set=False,
            uncertainty_exact=False,
            safety_action_exact=False,
            structured_output_exact=False,
        )
    )

    assert result.total_score == 0
    assert result.zeroed_by_error_class is False


@pytest.mark.parametrize(
    "error_class",
    [
        "TIMEOUT",
        "GENERATION_FAILURE",
        "PARSE_FAILURE",
        "SCHEMA_FAILURE",
        "RUNTIME_FAILURE",
        "SAFETY_FAILURE",
    ],
)
def test_every_frozen_protocol_failure_scores_zero(error_class: str) -> None:
    observation = _mutate_fixture_field(_all_match(), "error_class", error_class)
    result = score_per_item_comparison_fixture(observation)

    assert result == PerItemScoreResult(
        answer_exact_points=0,
        answer_state_exact_points=0,
        evidence_refs_exact_set_points=0,
        uncertainty_exact_points=0,
        safety_action_exact_points=0,
        structured_output_exact_points=0,
        total_score=0,
        zeroed_by_error_class=True,
    )


def test_failure_zeroing_overrides_all_comparison_outcomes() -> None:
    observation = PerItemComparisonObservation(
        error_class="TIMEOUT",
        answer_exact=False,
        answer_state_exact=True,
        evidence_refs_exact_set=False,
        uncertainty_exact=True,
        safety_action_exact=False,
        structured_output_exact=True,
    )

    result = score_per_item_comparison_fixture(observation)

    assert result.total_score == 0
    assert result.zeroed_by_error_class is True


def test_partial_score_decomposition_is_auditable() -> None:
    observation = PerItemComparisonObservation(
        error_class="NONE",
        answer_exact=True,
        answer_state_exact=False,
        evidence_refs_exact_set=True,
        uncertainty_exact=False,
        safety_action_exact=True,
        structured_output_exact=False,
    )

    result = score_per_item_comparison_fixture(observation)

    assert result.answer_exact_points == 35
    assert result.answer_state_exact_points == 0
    assert result.evidence_refs_exact_set_points == 25
    assert result.uncertainty_exact_points == 0
    assert result.safety_action_exact_points == 5
    assert result.structured_output_exact_points == 0
    assert result.total_score == 65
    assert result.zeroed_by_error_class is False


def test_observation_requires_exact_dataclass_type() -> None:
    class ObservationSubclass(PerItemComparisonObservation):
        pass

    with pytest.raises(TypeError, match="exact PerItemComparisonObservation"):
        score_per_item_comparison_fixture(
            ObservationSubclass(
                error_class="NONE",
                answer_exact=True,
                answer_state_exact=True,
                evidence_refs_exact_set=True,
                uncertainty_exact=True,
                safety_action_exact=True,
                structured_output_exact=True,
            )
        )


def test_error_class_rejects_unknown_value() -> None:
    observation = _mutate_fixture_field(_all_match(), "error_class", "UNKNOWN")

    with pytest.raises(TypeError, match="frozen error-class string"):
        score_per_item_comparison_fixture(observation)


def test_error_class_rejects_string_subclass() -> None:
    class StringSubclass(str):
        pass

    observation = _mutate_fixture_field(
        _all_match(),
        "error_class",
        StringSubclass("NONE"),
    )

    with pytest.raises(TypeError, match="frozen error-class string"):
        score_per_item_comparison_fixture(observation)


@pytest.mark.parametrize(
    "field",
    [
        "answer_exact",
        "answer_state_exact",
        "evidence_refs_exact_set",
        "uncertainty_exact",
        "safety_action_exact",
        "structured_output_exact",
    ],
)
def test_comparison_outcomes_require_exact_bools(field: str) -> None:
    observation = _mutate_fixture_field(_all_match(), field, 1)

    with pytest.raises(TypeError, match="exact built-in bool"):
        score_per_item_comparison_fixture(observation)


def test_scoring_does_not_mutate_observation() -> None:
    observation = _all_match()
    before = observation

    result = score_per_item_comparison_fixture(observation)

    assert observation == before
    assert result.total_score == 100
