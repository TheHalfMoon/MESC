from __future__ import annotations

from decimal import ROUND_DOWN, Decimal, Inexact, Rounded, localcontext

from medscale.mesc._bt_tournament_scoring_engine_fixture_v1 import (
    AxisScores,
    compute_aggregate_score_fixture,
    compute_axis_score_fixture,
    evaluate_role_gates_fixture,
)


def _hostile_axis_scores() -> AxisScores:
    return AxisScores(
        medical_reasoning=Decimal("83.33"),
        evidence_fidelity=Decimal("82.22"),
        uncertainty_abstention=Decimal("81.11"),
        safety=Decimal("90.00"),
        structured_fhir=Decimal("80.00"),
        operational_reproducibility=Decimal("70.00"),
    )


def test_axis_rounding_ignores_hostile_caller_decimal_context() -> None:
    with localcontext() as caller:
        caller.prec = 2
        caller.rounding = ROUND_DOWN
        caller.traps[Inexact] = True
        caller.traps[Rounded] = True

        assert compute_axis_score_fixture((1,) + (0,) * 39) == Decimal("0.03")

        assert caller.prec == 2
        assert caller.rounding == ROUND_DOWN
        assert caller.traps[Inexact] is True
        assert caller.traps[Rounded] is True


def test_aggregate_and_gate_recomputation_ignore_hostile_decimal_context() -> None:
    scores = _hostile_axis_scores()

    with localcontext() as caller:
        caller.prec = 2
        caller.rounding = ROUND_DOWN
        caller.traps[Inexact] = True
        caller.traps[Rounded] = True

        aggregate = compute_aggregate_score_fixture(scores)
        gates = evaluate_role_gates_fixture(
            scores,
            aggregate_score=aggregate,
            critical_safety_failures=0,
        )

        assert aggregate == Decimal("82.44")
        assert gates.compact == "PASS"
        assert gates.flagship_reasoner == "PASS"
        assert caller.prec == 2
        assert caller.rounding == ROUND_DOWN
        assert caller.traps[Inexact] is True
        assert caller.traps[Rounded] is True
