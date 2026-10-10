"""Official SDK read-only calls mocked; no auth or network in tests."""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_kaggle_readonly.py"
SPEC = importlib.util.spec_from_file_location("mesc_kaggle_readonly_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
observe = cast(Callable[[object], dict[str, object]], MODULE.observe)


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def authenticate(self) -> None:
        self.calls.append("authenticate")

    def kernels_list(self, *, mine: bool, page_size: int, page: int) -> list[object]:
        assert mine is True and page_size == 5 and page == 1
        self.calls.append("personal_list")
        return [object()]

    def quota_view(self) -> SimpleNamespace:
        self.calls.append("quota_read")
        return SimpleNamespace(
            gpu_quota=SimpleNamespace(
                total_time_allowed=timedelta(hours=30), time_used=timedelta(hours=12)
            )
        )


def test_supported_readonly_quota_is_observed_without_allocation() -> None:
    api = FakeApi()
    result = observe(api)
    assert api.calls == ["authenticate", "personal_list", "quota_read"]
    assert result["gpu_remaining_seconds"] == 18 * 3600
    assert result["quota_state"] == "OBSERVED_NOT_CAPACITY_GUARANTEE"
    assert result["gpu_capacity_state"] == "UNKNOWN"
    assert result["allocation_performed"] is False
    assert result["scientific_execution_authorized"] is False
    assert "username" not in result and "token" not in result


@pytest.mark.parametrize("case", ["absent", "empty", "error", "invalid", "negative"])
def test_unknown_quota_is_honest_and_exception_text_is_private(case: str) -> None:
    api = FakeApi()
    if case == "absent":
        replacement = SimpleNamespace(authenticate=api.authenticate, kernels_list=api.kernels_list)
    elif case == "empty":
        replacement = SimpleNamespace(
            authenticate=api.authenticate,
            kernels_list=api.kernels_list,
            quota_view=lambda: SimpleNamespace(gpu_quota=None),
        )
    elif case == "error":

        def unavailable() -> None:
            raise RuntimeError("fixture-only-private-token-never-log")

        replacement = SimpleNamespace(
            authenticate=api.authenticate, kernels_list=api.kernels_list, quota_view=unavailable
        )
    else:
        replacement = SimpleNamespace(
            authenticate=api.authenticate,
            kernels_list=api.kernels_list,
            quota_view=lambda: SimpleNamespace(
                gpu_quota=SimpleNamespace(
                    total_time_allowed=timedelta(seconds=1),
                    time_used=timedelta(seconds=2 if case == "invalid" else -0.5),
                )
            ),
        )
    result = observe(replacement)
    assert result["quota_state"] == "UNKNOWN"
    assert "gpu_remaining_seconds" not in result
    assert "fixture-only-private-token" not in str(result)


def test_fractional_provider_usage_kept_exact_and_remaining_seconds_conservative() -> None:
    api = FakeApi()
    replacement = SimpleNamespace(
        authenticate=api.authenticate,
        kernels_list=api.kernels_list,
        quota_view=lambda: SimpleNamespace(
            gpu_quota=SimpleNamespace(
                total_time_allowed=timedelta(seconds=10), time_used=timedelta(seconds=0.5)
            )
        ),
    )
    result = observe(replacement)
    assert result["gpu_used_microseconds"] == 500000
    assert result["gpu_remaining_seconds"] == 9


def test_remote_personal_list_failure_does_not_claim_authentication() -> None:
    def denied(**_kwargs: object) -> None:
        raise PermissionError("fixture-only")

    api = SimpleNamespace(authenticate=lambda: None, kernels_list=denied)
    with pytest.raises(PermissionError):
        observe(api)
