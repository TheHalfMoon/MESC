"""Synthetic and adversarial tests: no Colab API/network calls."""

from __future__ import annotations

import copy

import pytest

from medscale.mesc._mrl_0809_evidence_recovery_3_control_plane_v1 import (
    Recovery3PreflightError,
    validate_recovery_3_control_plane,
)

SCHEMA = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-CONTROL-PLANE-V1"
SESSION = "mesc-evidence-recovery-3"


def observation(phase: str, *, rate: float = 0.0) -> dict[str, object]:
    active = phase == "AFTER_ALLOCATION"
    return {
        "schema_version": SCHEMA,
        "phase": phase,
        "provider_class": "GOOGLE_COLAB_FREE",
        "paid_compute_units_balance": 0.0,
        "nominal_rate_hourly": rate,
        "account_assignments": 1 if active else 0,
        "server_assignments": 1 if active else 0,
        "session": {
            "name": SESSION,
            "accelerator": "T4",
            "variant": "GPU",
            "machine_shape": "STANDARD",
        }
        if active
        else None,
    }


def test_idle_free_account_passes_before_allocation() -> None:
    verdict = validate_recovery_3_control_plane(
        observation("BEFORE_ALLOCATION"),
        phase="BEFORE_ALLOCATION",
        session_name=SESSION,
    )
    assert verdict.balance_paid_compute_units == 0.0
    assert verdict.assignment_count == 0


def test_nominal_positive_rate_is_not_a_monetary_charge() -> None:
    verdict = validate_recovery_3_control_plane(
        observation("AFTER_ALLOCATION", rate=1.07),
        phase="AFTER_ALLOCATION",
        session_name=SESSION,
    )
    assert verdict.nominal_rate_hourly == 1.07
    assert verdict.assignment_count == 1
    assert verdict.evidence_kind == "CONTROL_PLANE_ONLY_NOT_MONETARY_RECEIPT"


@pytest.mark.parametrize(
    ("field", "bad", "expected"),
    [
        ("provider_class", "GOOGLE_COLAB_PAID", "only Google Colab Free"),
        ("paid_compute_units_balance", 1.0, "positive paid compute-unit"),
        ("paid_compute_units_balance", -0.01, "finite and nonnegative"),
        ("paid_compute_units_balance", float("nan"), "finite and nonnegative"),
        ("paid_compute_units_balance", "0.00", "finite numeric"),
        ("nominal_rate_hourly", float("inf"), "finite and nonnegative"),
        ("account_assignments", True, "counts must be integers"),
        ("account_assignments", 2, "assignments disagree"),
        ("server_assignments", 2, "assignments disagree"),
        ("phase", "BEFORE_ALLOCATION", "schema or phase"),
        ("schema_version", "WRONG", "schema or phase"),
        ("session", None, "one bounded allocated session"),
    ],
)
def test_active_adversarial_observations_fail_closed(
    field: str, bad: object, expected: str
) -> None:
    case = observation("AFTER_ALLOCATION", rate=1.07)
    case[field] = bad
    with pytest.raises(Recovery3PreflightError, match=expected):
        validate_recovery_3_control_plane(case, phase="AFTER_ALLOCATION", session_name=SESSION)


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("name", "other-attempt"),
        ("accelerator", "A100"),
        ("variant", "TPU"),
        ("machine_shape", "HIGHMEM"),
    ],
)
def test_wrong_allocated_session_fails_closed(field: str, bad: str) -> None:
    case = observation("AFTER_ALLOCATION", rate=1.07)
    item = copy.deepcopy(case["session"])
    assert type(item) is dict
    item[field] = bad
    case["session"] = item
    with pytest.raises(Recovery3PreflightError, match="identity drifted"):
        validate_recovery_3_control_plane(case, phase="AFTER_ALLOCATION", session_name=SESSION)


def test_existing_preallocation_assignment_fails_closed() -> None:
    case = observation("BEFORE_ALLOCATION")
    case["account_assignments"] = 1
    case["server_assignments"] = 1
    with pytest.raises(Recovery3PreflightError, match="no sessions"):
        validate_recovery_3_control_plane(case, phase="BEFORE_ALLOCATION", session_name=SESSION)


def test_unknown_fields_or_endpoint_leakage_fail_closed() -> None:
    case = observation("AFTER_ALLOCATION")
    case["provider_endpoint"] = "PRIVATE_ENDPOINT_MUST_NEVER_BE_SERIALIZED"
    with pytest.raises(Recovery3PreflightError, match="field envelope drifted"):
        validate_recovery_3_control_plane(case, phase="AFTER_ALLOCATION", session_name=SESSION)
