#!/usr/bin/env python3
"""Authority-enforcing wrapper for the single accepted MRL-0809 Stage-4 retry."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

from mesc_mrl_0809_stage4_v2_repair_driver import (
    GEMMA,
    HARNESS,
    QWEN,
    _run,
)

from medscale.mesc._mrl_0809_stage4_retry_gate_v1 import (
    Stage4RetryAuthorityIdentity,
    validate_stage4_retry_authority,
)

_AUTHORITY_RECEIPT: Final = "stage4-retry-authority.json"


class Stage4RetryLaunchError(RuntimeError):
    """The single retry cannot launch under the current repository state."""


def _head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def _require_clean(root: Path) -> None:
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
        encoding="utf-8",
    )
    if status:
        raise Stage4RetryLaunchError("repository has tracked working-tree changes")


def _write_authority_receipt(
    custody: Path,
    *,
    revision: str,
    authority: Stage4RetryAuthorityIdentity,
) -> None:
    document = {
        "authorization_sha256": authority.authorization_sha256,
        "canonical_revision": revision,
        "decision_sha256": authority.decision_sha256,
        "repair_merge_sha": authority.repair_merge_sha,
        "repair_merge_tree": authority.repair_merge_tree,
        "schema_version": "MESC-MRL-0809-STAGE4-RETRY-AUTHORITY-RECEIPT-V1",
    }
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    (custody / _AUTHORITY_RECEIPT).write_text(raw, encoding="utf-8", newline="\n")


def _python_launch_path(python_executable: Path) -> Path:
    """Return an absolute executable path without dereferencing a venv symlink."""

    path = python_executable.absolute()
    if not path.is_file():
        raise Stage4RetryLaunchError("python executable is missing")
    return path


def _run_retry_stage4(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    remove_tree: Callable[..., None] = shutil.rmtree,
) -> None:
    """Run the preserved fail-stop sequence while retaining venv executable identity."""

    root = repository_root.resolve(strict=True)
    python_path = _python_launch_path(python_executable)
    harness = (root / HARNESS).resolve(strict=True)
    custody = custody.resolve(strict=False)
    custody.mkdir(parents=True, exist_ok=True)
    custody = custody.resolve(strict=True)

    qwen_snapshot = custody / "qwen-snapshot"
    gemma_snapshot = custody / "gemma-snapshot"
    qwen_stage = custody / "qwen-stage.json"
    gemma_stage = custody / "gemma-stage.json"
    qwen_observation = custody / "qwen-observation.json"
    gemma_observation = custody / "gemma-observation.json"
    common = [str(python_path), str(harness)]

    _run(
        [
            *common,
            "stage",
            "--repository-root",
            str(root),
            "--candidate",
            QWEN,
            "--destination",
            str(qwen_snapshot),
            "--receipt-out",
            str(qwen_stage),
        ],
        runner=runner,
    )
    _run(
        [
            *common,
            "probe",
            "--repository-root",
            str(root),
            "--candidate",
            QWEN,
            "--snapshot",
            str(qwen_snapshot),
            "--stage-receipt",
            str(qwen_stage),
            "--observation-out",
            str(qwen_observation),
            "--python-executable",
            str(python_path),
        ],
        runner=runner,
    )
    remove_tree(qwen_snapshot, ignore_errors=False)

    _run(
        [
            *common,
            "stage",
            "--repository-root",
            str(root),
            "--candidate",
            GEMMA,
            "--destination",
            str(gemma_snapshot),
            "--receipt-out",
            str(gemma_stage),
        ],
        runner=runner,
    )
    _run(
        [
            *common,
            "probe",
            "--repository-root",
            str(root),
            "--candidate",
            GEMMA,
            "--snapshot",
            str(gemma_snapshot),
            "--stage-receipt",
            str(gemma_stage),
            "--observation-out",
            str(gemma_observation),
            "--python-executable",
            str(python_path),
        ],
        runner=runner,
    )
    remove_tree(gemma_snapshot, ignore_errors=False)

    _run(
        [
            *common,
            "assemble",
            "--repository-root",
            str(root),
            "--observation",
            str(qwen_observation),
            "--observation",
            str(gemma_observation),
            "--receipt-out",
            str(custody / "runtime-feasibility-v2-repair-1.json"),
        ],
        runner=runner,
    )


def run_authorized_stage4(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    expected_canonical_revision: str,
) -> None:
    """Validate authority and canonical identity before invoking the preserved driver."""

    root = repository_root.resolve(strict=True)
    current_head = _head(root)
    if current_head != expected_canonical_revision:
        raise Stage4RetryLaunchError(
            "repository HEAD does not match the fresh-main-qualified canonical revision"
        )
    _require_clean(root)

    if custody.exists():
        raise Stage4RetryLaunchError("custody path must not already exist")

    authority = validate_stage4_retry_authority(root, current_head)
    custody.mkdir(parents=True, exist_ok=False)
    _write_authority_receipt(custody, revision=current_head, authority=authority)

    _run_retry_stage4(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--python-executable", type=Path, required=True)
    parser.add_argument("--expected-canonical-revision", required=True)
    args = parser.parse_args()
    run_authorized_stage4(
        repository_root=args.repository_root,
        custody=args.custody,
        python_executable=args.python_executable,
        expected_canonical_revision=args.expected_canonical_revision,
    )


if __name__ == "__main__":
    main()
