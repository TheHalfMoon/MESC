#!/usr/bin/env python3
"""Authority-enforcing wrapper for the single accepted MRL-0809 Stage-4 retry-2."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Final

from mesc_mrl_0809_stage4_v2_bmm_repair_driver import run_stage4 as _run_bmm_stage4

from medscale.mesc._mrl_0809_stage4_retry_2_gate_v1 import (
    Stage4Retry2AuthorityIdentity,
    validate_stage4_retry_2_authority,
)

_AUTHORITY_RECEIPT: Final = "stage4-retry-2-authority.json"
_LAUNCH_CONSUMPTION_RECEIPT: Final = "stage4-retry-2-launch-consumption.json"
_CONSUMED_RECORDS: Final = (
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-stage4-retry-2-failure-record.json"),
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-stage4-retry-2-result.json"),
)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)


class Stage4Retry2LaunchError(RuntimeError):
    """The accepted retry-2 launch cannot proceed under the current repository state."""


def _head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def _live_origin_main(root: Path) -> str:
    try:
        output = subprocess.check_output(
            ["git", "-C", str(root), "ls-remote", "--exit-code", "origin", "refs/heads/main"],
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Stage4Retry2LaunchError("live origin/main identity is unavailable") from exc
    fields = output.split()
    if (
        len(fields) != 2
        or _SHA40.fullmatch(fields[0]) is None
        or fields[1] != "refs/heads/main"
    ):
        raise Stage4Retry2LaunchError("live origin/main identity is malformed")
    return fields[0]


def _require_canonical_main(root: Path, revision: str) -> None:
    if _live_origin_main(root) != revision:
        raise Stage4Retry2LaunchError(
            "runtime revision is not the exact current live origin/main revision"
        )


def _require_clean(root: Path) -> None:
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
        encoding="utf-8",
    )
    if status:
        raise Stage4Retry2LaunchError("repository has tracked working-tree changes")


def _require_unconsumed(root: Path) -> None:
    if any((root / path).is_file() for path in _CONSUMED_RECORDS):
        raise Stage4Retry2LaunchError(
            "accepted Stage-4 retry-2 is already consumed; no additional launch is authorized"
        )


def _write_json(path: Path, document: dict[str, object]) -> None:
    raw = json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_text(raw, encoding="utf-8", newline="\n")


def _write_authority_receipt(
    custody: Path,
    *,
    revision: str,
    authority: Stage4Retry2AuthorityIdentity,
) -> None:
    _write_json(
        custody / _AUTHORITY_RECEIPT,
        {
            "authorization_sha256": authority.authorization_sha256,
            "bmm_repair_merge_sha": authority.bmm_repair_merge_sha,
            "bmm_repair_merge_tree": authority.bmm_repair_merge_tree,
            "canonical_revision": revision,
            "decision_sha256": authority.decision_sha256,
            "schema_version": "MESC-MRL-0809-STAGE4-RETRY-2-AUTHORITY-RECEIPT-V1",
            "static_manifest_sha256": authority.static_manifest_sha256,
        },
    )


def _write_launch_consumption_receipt(
    custody: Path,
    *,
    revision: str,
    authority: Stage4Retry2AuthorityIdentity,
) -> None:
    _write_json(
        custody / _LAUNCH_CONSUMPTION_RECEIPT,
        {
            "authorization_sha256": authority.authorization_sha256,
            "automatic_relaunch_authorized": False,
            "automatic_retry_authorized": False,
            "canonical_revision": revision,
            "launch_authorization_consumed": True,
            "preflight_failure_exhausts_launch": True,
            "provider_or_session_failure_exhausts_launch": True,
            "schema_version": "MESC-MRL-0809-STAGE4-RETRY-2-LAUNCH-CONSUMPTION-V1",
        },
    )


def run_authorized_stage4_retry_2(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    expected_canonical_revision: str,
) -> None:
    """Consume the single launch authorization, then run the BMM fail-stop sequence."""

    root = repository_root.resolve(strict=True)
    current_head = _head(root)
    if current_head != expected_canonical_revision:
        raise Stage4Retry2LaunchError(
            "repository HEAD does not match the fresh-main-qualified canonical revision"
        )
    _require_clean(root)
    _require_canonical_main(root, current_head)
    _require_unconsumed(root)

    if custody.exists():
        raise Stage4Retry2LaunchError("custody path must not already exist")

    authority = validate_stage4_retry_2_authority(root, current_head)
    custody.mkdir(parents=True, exist_ok=False)
    _write_authority_receipt(custody, revision=current_head, authority=authority)

    # The decision consumes retry-2 on hosted launch invocation, even when the
    # BMM preflight fails before probe-start. Persist that fact before runtime.
    _write_launch_consumption_receipt(custody, revision=current_head, authority=authority)

    _run_bmm_stage4(
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
    run_authorized_stage4_retry_2(
        repository_root=args.repository_root,
        custody=args.custody,
        python_executable=args.python_executable,
        expected_canonical_revision=args.expected_canonical_revision,
    )


if __name__ == "__main__":
    main()
