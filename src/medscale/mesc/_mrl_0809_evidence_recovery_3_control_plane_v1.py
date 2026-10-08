"""Strict, zero-paid-unit control-plane preflight for Recovery-3.

A positive *nominal* hourly consumption rate is not proof of a charge.
This validator never allocates, retries, or executes a hosted workload.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal, cast

_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-CONTROL-PLANE-V1"
Phase = Literal["BEFORE_ALLOCATION", "AFTER_ALLOCATION"]


class Recovery3PreflightError(ValueError):
    """A required zero-cost or frozen-provider fact is absent or contradicted."""


@dataclass(frozen=True, slots=True)
class Recovery3PreflightVerdict:
    phase: Phase
    nominal_rate_hourly: float
    balance_paid_compute_units: float
    assignment_count: int
    evidence_kind: str = "CONTROL_PLANE_ONLY_NOT_MONETARY_RECEIPT"


def _nonnegative_number(value: object, *, name: str) -> float:
    if type(value) not in (int, float):
        raise Recovery3PreflightError(f"{name} must be a finite numeric measurement")
    number = float(cast(int | float, value))
    if not math.isfinite(number) or number < 0:
        raise Recovery3PreflightError(f"{name} must be finite and nonnegative")
    return number


def validate_recovery_3_control_plane(
    observation: dict[str, object], *, phase: Phase, session_name: str
) -> Recovery3PreflightVerdict:
    """Fail closed on paid-unit balance, unexpected assignments or GPU drift.

    The provider's reported nominal rate is retained as telemetry. It is
    deliberately *not* constrained to zero: Recovery-2 failed on that
    unjustified assertion before a frozen runtime could be attempted.
    """
    fields = {
        "schema_version",
        "phase",
        "provider_class",
        "paid_compute_units_balance",
        "nominal_rate_hourly",
        "account_assignments",
        "server_assignments",
        "session",
    }
    if set(observation) != fields:
        raise Recovery3PreflightError("control-plane field envelope drifted")
    if observation["schema_version"] != _SCHEMA or observation["phase"] != phase:
        raise Recovery3PreflightError("control-plane schema or phase drifted")
    if observation["provider_class"] != "GOOGLE_COLAB_FREE":
        raise Recovery3PreflightError("only Google Colab Free is permitted")

    balance = _nonnegative_number(
        observation["paid_compute_units_balance"], name="paid_compute_units_balance"
    )
    if balance != 0:
        raise Recovery3PreflightError("positive paid compute-unit balance is not permitted")
    rate = _nonnegative_number(observation["nominal_rate_hourly"], name="nominal_rate_hourly")
    count = observation["account_assignments"]
    server_count = observation["server_assignments"]
    if type(count) is not int or type(server_count) is not int:
        raise Recovery3PreflightError("assignment counts must be integers")
    if count != server_count:
        raise Recovery3PreflightError("account/server assignments disagree")
    session = observation["session"]

    if phase == "BEFORE_ALLOCATION":
        if count != 0 or session is not None:
            raise Recovery3PreflightError("pre-allocation account must have no sessions")
    elif phase == "AFTER_ALLOCATION":
        if count != 1 or type(session) is not dict:
            raise Recovery3PreflightError("one bounded allocated session is required")
        item = cast(dict[str, object], session)
        if item != {
            "name": session_name,
            "accelerator": "T4",
            "variant": "GPU",
            "machine_shape": "STANDARD",
        }:
            raise Recovery3PreflightError("session/provider/GPU/shape identity drifted")
    else:
        raise Recovery3PreflightError("unsupported allocation phase")

    return Recovery3PreflightVerdict(
        phase=phase,
        nominal_rate_hourly=rate,
        balance_paid_compute_units=balance,
        assignment_count=count,
    )
