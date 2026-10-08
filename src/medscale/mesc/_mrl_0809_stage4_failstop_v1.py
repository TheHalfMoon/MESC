from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass


class Stage4DriverError(RuntimeError):
    pass


@dataclass(frozen=True)
class Stage4Step:
    name: str
    argv: tuple[str, ...]


def run_fail_stop(
    steps: Sequence[Stage4Step],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Execute each governed step once, in order, and stop on the first failure."""
    completed_names: list[str] = []
    for step in steps:
        completed = runner(
            list(step.argv),
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            raise Stage4DriverError(
                f"Stage-4 step failed and execution stopped: {step.name}; "
                f"returncode={completed.returncode}"
            )
        completed_names.append(step.name)
    return completed_names
