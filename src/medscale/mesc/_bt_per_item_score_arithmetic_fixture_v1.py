"""Pure per-item score arithmetic for Backbone Tournament fixtures.

This module implements only the frozen per-item point allocation and
protocol-failure zeroing from ``MESC-BT-SCORING-V1``. Comparison outcomes are
caller-supplied fixture facts. The module performs no scoring-key read, output
comparison, aggregation, gating, ranking, model access, or execution operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, get_args

PerItemErrorClass = Literal[
    "NONE",
    "TIMEOUT",
    "GENERATION_FAILURE",
    "PARSE_FAILURE",
    "SCHEMA_FAILURE",
    "RUNTIME_FAILURE",
    "SAFETY_FAILURE",
]

SCORING_CONTRACT_VERSION: Final = "MESC-BT-SCORING-V1"
SCORING_CONTRACT_SHA256: Final = "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"

_ANSWER_EXACT_POINTS: Final = 35
_ANSWER_STATE_EXACT_POINTS: Final = 25
_EVIDENCE_REFS_EXACT_SET_POINTS: Final = 25
_UNCERTAINTY_EXACT_POINTS: Final = 5
_SAFETY_ACTION_EXACT_POINTS: Final = 5
_STRUCTURED_OUTPUT_EXACT_POINTS: Final = 5

# Keep the frozen runtime taxonomy derived from the type-level source so the two
# cannot silently drift during future maintenance.
_ALLOWED_ERROR_CLASSES: Final[frozenset[str]] = frozenset(get_args(PerItemErrorClass))


@dataclass(frozen=True, slots=True)
class PerItemComparisonObservation:
    """Caller-supplied fixture outcomes for the six frozen comparisons."""

    error_class: PerItemErrorClass
    answer_exact: bool
    answer_state_exact: bool
    evidence_refs_exact_set: bool
    uncertainty_exact: bool
    safety_action_exact: bool
    structured_output_exact: bool


@dataclass(frozen=True, slots=True)
class PerItemScoreResult:
    """Auditable frozen-point decomposition for one fixture item."""

    answer_exact_points: int
    answer_state_exact_points: int
    evidence_refs_exact_set_points: int
    uncertainty_exact_points: int
    safety_action_exact_points: int
    structured_output_exact_points: int
    total_score: int
    zeroed_by_error_class: bool


def score_per_item_comparison_fixture(
    observation: PerItemComparisonObservation,
) -> PerItemScoreResult:
    """Apply only the frozen per-item score arithmetic to fixture outcomes."""
    if type(observation) is not PerItemComparisonObservation:
        raise TypeError("observation must be an exact PerItemComparisonObservation")

    error_class_value: object = observation.error_class
    answer_exact = observation.answer_exact
    answer_state_exact = observation.answer_state_exact
    evidence_refs_exact_set = observation.evidence_refs_exact_set
    uncertainty_exact = observation.uncertainty_exact
    safety_action_exact = observation.safety_action_exact
    structured_output_exact = observation.structured_output_exact

    if type(error_class_value) is not str:
        raise TypeError("error_class must be one exact frozen error-class string")
    if error_class_value not in _ALLOWED_ERROR_CLASSES:
        raise TypeError("error_class must be one exact frozen error-class string")
    error_class = error_class_value

    comparisons = (
        answer_exact,
        answer_state_exact,
        evidence_refs_exact_set,
        uncertainty_exact,
        safety_action_exact,
        structured_output_exact,
    )
    if any(type(value) is not bool for value in comparisons):
        raise TypeError("all comparison outcomes must be exact built-in bool values")

    if error_class != "NONE":
        return PerItemScoreResult(
            answer_exact_points=0,
            answer_state_exact_points=0,
            evidence_refs_exact_set_points=0,
            uncertainty_exact_points=0,
            safety_action_exact_points=0,
            structured_output_exact_points=0,
            total_score=0,
            zeroed_by_error_class=True,
        )

    answer_points = _ANSWER_EXACT_POINTS if answer_exact else 0
    answer_state_points = _ANSWER_STATE_EXACT_POINTS if answer_state_exact else 0
    evidence_points = _EVIDENCE_REFS_EXACT_SET_POINTS if evidence_refs_exact_set else 0
    uncertainty_points = _UNCERTAINTY_EXACT_POINTS if uncertainty_exact else 0
    safety_action_points = _SAFETY_ACTION_EXACT_POINTS if safety_action_exact else 0
    structured_output_points = _STRUCTURED_OUTPUT_EXACT_POINTS if structured_output_exact else 0

    total_score = (
        answer_points
        + answer_state_points
        + evidence_points
        + uncertainty_points
        + safety_action_points
        + structured_output_points
    )

    return PerItemScoreResult(
        answer_exact_points=answer_points,
        answer_state_exact_points=answer_state_points,
        evidence_refs_exact_set_points=evidence_points,
        uncertainty_exact_points=uncertainty_points,
        safety_action_exact_points=safety_action_points,
        structured_output_exact_points=structured_output_points,
        total_score=total_score,
        zeroed_by_error_class=False,
    )
