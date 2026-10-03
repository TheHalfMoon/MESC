#!/usr/bin/env python3
"""Fail-stop driver for a future separately authorized MRL-0809 BMM repair attempt.

Repository inclusion is not runtime authority. A hosted execution requires a new
Founder decision bound to the exact canonical repair revision.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

from mesc_mrl_0809_stage4_v2_repair_driver import GEMMA, QWEN, _run

HARNESS: Final = Path("scripts/mesc_mrl_0809_runtime_feasibility_v2_bmm_repair.py")


class Stage4BMMRepairError(RuntimeError):
    """The future BMM-repaired Stage-4 sequence cannot continue."""


def _python_launch_path(python_executable: Path) -> Path:
    path = python_executable.absolute()
    if not path.is_file():
        raise Stage4BMMRepairError("python executable is missing")
    return path


def run_stage4(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    remove_tree: Callable[..., None] = shutil.rmtree,
) -> None:
    """Run preflight then the exact dual-candidate sequence, stopping on first failure."""

    root = repository_root.resolve(strict=True)
    python_path = _python_launch_path(python_executable)
    harness = (root / HARNESS).resolve(strict=True)
    custody = custody.resolve(strict=False)
    custody.mkdir(parents=True, exist_ok=True)
    custody = custody.resolve(strict=True)
    common = [str(python_path), str(harness)]

    qwen_snapshot = custody / "qwen-snapshot"
    gemma_snapshot = custody / "gemma-snapshot"
    qwen_stage = custody / "qwen-stage.json"
    gemma_stage = custody / "gemma-stage.json"
    qwen_observation = custody / "qwen-observation.json"
    gemma_observation = custody / "gemma-observation.json"

    _run(
        [
            *common,
            "compat-preflight",
            "--repository-root",
            str(root),
            "--python-executable",
            str(python_path),
            "--receipt-out",
            str(custody / "bmm-portability-preflight.json"),
        ],
        runner=runner,
    )
    _run(
        [*common, "stage", "--repository-root", str(root), "--candidate", QWEN,
         "--destination", str(qwen_snapshot), "--receipt-out", str(qwen_stage)],
        runner=runner,
    )
    _run(
        [*common, "probe", "--repository-root", str(root), "--candidate", QWEN,
         "--snapshot", str(qwen_snapshot), "--stage-receipt", str(qwen_stage),
         "--observation-out", str(qwen_observation), "--python-executable", str(python_path)],
        runner=runner,
    )
    remove_tree(qwen_snapshot, ignore_errors=False)
    _run(
        [*common, "stage", "--repository-root", str(root), "--candidate", GEMMA,
         "--destination", str(gemma_snapshot), "--receipt-out", str(gemma_stage)],
        runner=runner,
    )
    _run(
        [*common, "probe", "--repository-root", str(root), "--candidate", GEMMA,
         "--snapshot", str(gemma_snapshot), "--stage-receipt", str(gemma_stage),
         "--observation-out", str(gemma_observation), "--python-executable", str(python_path)],
        runner=runner,
    )
    remove_tree(gemma_snapshot, ignore_errors=False)
    _run(
        [*common, "assemble", "--repository-root", str(root),
         "--observation", str(qwen_observation), "--observation", str(gemma_observation),
         "--receipt-out", str(custody / "runtime-feasibility-v2-bmm-repair-1.json")],
        runner=runner,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--python-executable", type=Path, required=True)
    args = parser.parse_args()
    run_stage4(
        repository_root=args.repository_root,
        custody=args.custody,
        python_executable=args.python_executable,
    )


if __name__ == "__main__":
    main()
