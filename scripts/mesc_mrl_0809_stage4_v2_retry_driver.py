#!/usr/bin/env python3
"""Authority-enforcing wrapper for the single accepted MRL-0809 Stage-4 retry."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Final

from medscale.mesc._mrl_0809_stage4_retry_gate_v1 import (
    Stage4RetryAuthorityIdentity,
    validate_stage4_retry_authority,
)
from mesc_mrl_0809_stage4_v2_repair_driver import run_stage4

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

    run_stage4(
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
