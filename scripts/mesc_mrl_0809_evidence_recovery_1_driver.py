#!/usr/bin/env python3
"""Authority-enforcing driver for MRL-0809 successor-v2 evidence recovery 1."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Final

from mesc_mrl_0809_stage4_v2_bmm_repair_driver import run_stage4 as _run_bmm_stage4

from medscale.mesc._mrl_0809_evidence_recovery_1_gate_v1 import (
    EvidenceRecovery1AuthorityIdentity,
    validate_evidence_recovery_1_authority,
)

_AUTHORITY_RECEIPT: Final = "evidence-recovery-1-authority.json"
_LAUNCH_CONSUMPTION_RECEIPT: Final = "evidence-recovery-1-launch-consumption.json"
_BUNDLE: Final = "evidence-recovery-1-bundle.json"
_BUNDLE_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-BUNDLE-V1"
_BUNDLE_STDOUT_PREFIX: Final = "MESC_EVIDENCE_RECOVERY_BUNDLE_V1_BASE64="
_PREDECESSOR_RESULT: Final = Path(
    "specs/mesc-experiment-0/mrl-0809-successor-v2-stage4-retry-2-result.json"
)
_CONSUMED_RECORDS: Final = (
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-1-failure-record.json"),
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-1-result.json"),
)
_REQUIRED_BUNDLE_FILES: Final = (
    "bmm-portability-preflight.json",
    _AUTHORITY_RECEIPT,
    _LAUNCH_CONSUMPTION_RECEIPT,
    "gemma-observation.json",
    "gemma-observation.json.probe-start.json",
    "gemma-stage.json",
    "qwen-observation.json",
    "qwen-observation.json.probe-start.json",
    "qwen-stage.json",
    "runtime-feasibility-v2-bmm-repair-1.json",
)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)


class EvidenceRecovery1LaunchError(RuntimeError):
    """The accepted evidence-recovery launch cannot proceed under the current state."""


def _head(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def _tree(root: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD^{tree}"],
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
        raise EvidenceRecovery1LaunchError("live origin/main identity is unavailable") from exc
    fields = output.split()
    if len(fields) != 2 or _SHA40.fullmatch(fields[0]) is None or fields[1] != "refs/heads/main":
        raise EvidenceRecovery1LaunchError("live origin/main identity is malformed")
    return fields[0]


def _require_canonical_main(root: Path, revision: str) -> None:
    if _live_origin_main(root) != revision:
        raise EvidenceRecovery1LaunchError(
            "runtime revision is not the exact current live origin/main revision"
        )


def _require_clean(root: Path) -> None:
    status = subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        text=True,
        encoding="utf-8",
    )
    if status:
        raise EvidenceRecovery1LaunchError("repository has tracked working-tree changes")


def _require_recovery_unconsumed(root: Path) -> None:
    if any((root / path).is_file() for path in _CONSUMED_RECORDS):
        raise EvidenceRecovery1LaunchError(
            "evidence-recovery-1 is already consumed; no additional launch is authorized"
        )


def _require_predecessor(root: Path) -> None:
    if not (root / _PREDECESSOR_RESULT).is_file():
        raise EvidenceRecovery1LaunchError("canonical consumed Retry-2 outcome record is missing")


def _canonical_json_bytes(document: dict[str, object]) -> bytes:
    return (
        json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, document: dict[str, object]) -> None:
    _write_new(path, _canonical_json_bytes(document))


def _write_authority_receipt(
    custody: Path,
    *,
    revision: str,
    tree: str,
    authority: EvidenceRecovery1AuthorityIdentity,
) -> None:
    _write_json(
        custody / _AUTHORITY_RECEIPT,
        {
            "authorization_sha256": authority.authorization_sha256,
            "canonical_revision": revision,
            "canonical_tree": tree,
            "decision_sha256": authority.decision_sha256,
            "predecessor_merge_sha": authority.predecessor_merge_sha,
            "predecessor_merge_tree": authority.predecessor_merge_tree,
            "predecessor_result_sha256": authority.predecessor_result_sha256,
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-1-AUTHORITY-RECEIPT-V1",
            "static_manifest_sha256": authority.static_manifest_sha256,
        },
    )


def _write_launch_consumption_receipt(
    custody: Path,
    *,
    revision: str,
    authority: EvidenceRecovery1AuthorityIdentity,
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
            "purpose": "EVIDENCE_RECOVERY_ONLY",
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-1-LAUNCH-CONSUMPTION-V1",
        },
    )


def _build_recovery_bundle(custody: Path, *, revision: str, tree: str) -> bytes:
    artifacts: list[dict[str, object]] = []
    for name in _REQUIRED_BUNDLE_FILES:
        path = custody / name
        if not path.is_file():
            raise EvidenceRecovery1LaunchError(f"required recovery artifact is missing: {name}")
        raw = path.read_bytes()
        if not raw:
            raise EvidenceRecovery1LaunchError(f"required recovery artifact is empty: {name}")
        artifacts.append(
            {
                "base64": base64.b64encode(raw).decode("ascii"),
                "byte_count": len(raw),
                "path": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return _canonical_json_bytes(
        {
            "artifacts": artifacts,
            "canonical_revision": revision,
            "canonical_tree": tree,
            "purpose": "EVIDENCE_RECOVERY_ONLY",
            "schema_version": _BUNDLE_SCHEMA,
        }
    )


def run_authorized_evidence_recovery_1(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    expected_canonical_revision: str,
) -> bytes:
    """Consume the recovery launch, run the frozen BMM sequence, and emit retained bytes."""

    root = repository_root.resolve(strict=True)
    current_head = _head(root)
    if current_head != expected_canonical_revision:
        raise EvidenceRecovery1LaunchError(
            "repository HEAD does not match the fresh-main-qualified canonical revision"
        )
    _require_clean(root)
    _require_canonical_main(root, current_head)
    _require_predecessor(root)
    _require_recovery_unconsumed(root)

    if custody.exists():
        raise EvidenceRecovery1LaunchError("custody path must not already exist")

    authority = validate_evidence_recovery_1_authority(root, current_head)
    current_tree = _tree(root)
    custody.mkdir(parents=True, exist_ok=False)
    _write_authority_receipt(
        custody,
        revision=current_head,
        tree=current_tree,
        authority=authority,
    )

    # The Founder decision exhausts the one recovery launch on hosted invocation,
    # including provider/session or BMM-preflight failure. Persist before runtime.
    _write_launch_consumption_receipt(
        custody,
        revision=current_head,
        authority=authority,
    )

    _run_bmm_stage4(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
    )

    bundle = _build_recovery_bundle(custody, revision=current_head, tree=current_tree)
    _write_new(custody / _BUNDLE, bundle)

    # The stdout copy is a mandatory second retention path captured by Colab CLI
    # execution history if the hosted filesystem is pruned before copy-out.
    encoded = base64.b64encode(bundle).decode("ascii")
    print(_BUNDLE_STDOUT_PREFIX + encoded, flush=True)
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--python-executable", type=Path, required=True)
    parser.add_argument("--expected-canonical-revision", required=True)
    args = parser.parse_args()
    run_authorized_evidence_recovery_1(
        repository_root=args.repository_root,
        custody=args.custody,
        python_executable=args.python_executable,
        expected_canonical_revision=args.expected_canonical_revision,
    )


if __name__ == "__main__":
    main()
