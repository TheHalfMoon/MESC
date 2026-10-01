from __future__ import annotations

import subprocess

import pytest

from medscale.mesc._mrl_0809_stage4_failstop_v1 import (
    Stage4DriverError,
    Stage4Step,
    run_fail_stop,
)


def _completed(argv: list[str], returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout="", stderr="")


def test_fail_stop_prevents_later_steps_after_first_probe_failure() -> None:
    steps = (
        Stage4Step("stage-qwen", ("stage-qwen",)),
        Stage4Step("probe-qwen", ("probe-qwen",)),
        Stage4Step("stage-gemma", ("stage-gemma",)),
        Stage4Step("probe-gemma", ("probe-gemma",)),
    )
    calls: list[str] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv[0])
        return _completed(argv, 1 if argv[0] == "probe-qwen" else 0)

    with pytest.raises(Stage4DriverError, match="probe-qwen"):
        run_fail_stop(steps, runner=runner)

    assert calls == ["stage-qwen", "probe-qwen"]


def test_fail_stop_executes_each_step_exactly_once_on_success() -> None:
    steps = (
        Stage4Step("a", ("a",)),
        Stage4Step("b", ("b",)),
    )
    calls: list[str] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv[0])
        return _completed(argv, 0)

    assert run_fail_stop(steps, runner=runner) == ["a", "b"]
    assert calls == ["a", "b"]
