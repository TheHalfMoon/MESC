#!/usr/bin/env python3
"""Remote fail-closed driver for MRL-0809 Evidence-Recovery-2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Final, cast

from mesc_mrl_0809_stage4_v2_bmm_repair_driver import run_stage4 as _run_bmm_stage4

from medscale.mesc._mrl_0809_evidence_recovery_2_gate_v1 import (
    EvidenceRecovery2AuthorityIdentity,
    validate_evidence_recovery_2_authority,
)

_AUTHORITY_RECEIPT: Final = "evidence-recovery-2-authority.json"
_LAUNCH_CONSUMPTION_RECEIPT: Final = "evidence-recovery-2-launch-consumption.json"
_BUNDLE: Final = "evidence-recovery-2-bundle.json"
_READY: Final = "evidence-recovery-2-copyout-ready.json"
_HOST_ACK: Final = "evidence-recovery-2-host-ack.json"
_BUNDLE_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-BUNDLE-V1"
_READY_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-COPYOUT-READY-V1"
_ACK_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-HOST-ACK-V1"
_PREDECESSOR_FAILURE: Final = Path(
    "specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-1-failure-record.json"
)
_CONSUMED_RECORDS: Final = (
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-2-failure-record.json"),
    Path("specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-2-result.json"),
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
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


class EvidenceRecovery2LaunchError(RuntimeError):
    """The accepted Recovery-2 launch cannot proceed or finish safely."""


def _head(root: Path) -> str:
    return subprocess.check_output(
        ("git", "-C", str(root), "rev-parse", "HEAD"),
        text=True,
        encoding="utf-8",
    ).strip()


def _tree(root: Path) -> str:
    return subprocess.check_output(
        ("git", "-C", str(root), "rev-parse", "HEAD^{tree}"),
        text=True,
        encoding="utf-8",
    ).strip()


def _live_origin_main(root: Path) -> str:
    try:
        output = subprocess.check_output(
            ("git", "-C", str(root), "ls-remote", "--exit-code", "origin", "refs/heads/main"),
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidenceRecovery2LaunchError("live origin/main identity is unavailable") from exc
    fields = output.split()
    if len(fields) != 2 or _SHA40.fullmatch(fields[0]) is None:
        raise EvidenceRecovery2LaunchError("live origin/main identity is malformed")
    if fields[1] != "refs/heads/main":
        raise EvidenceRecovery2LaunchError("live origin/main ref is malformed")
    return fields[0]


def _require_clean(root: Path) -> None:
    status = subprocess.check_output(
        ("git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"),
        text=True,
        encoding="utf-8",
    )
    if status:
        raise EvidenceRecovery2LaunchError("repository has tracked working-tree changes")


def _require_predecessor(root: Path) -> None:
    if not (root / _PREDECESSOR_FAILURE).is_file():
        raise EvidenceRecovery2LaunchError("canonical Recovery-1 failure record is missing")


def _require_unconsumed(root: Path) -> None:
    if any((root / path).is_file() for path in _CONSUMED_RECORDS):
        raise EvidenceRecovery2LaunchError(
            "Evidence-Recovery-2 is already consumed; no additional launch is authorized"
        )


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
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
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
    authority: EvidenceRecovery2AuthorityIdentity,
) -> None:
    _write_json(
        custody / _AUTHORITY_RECEIPT,
        {
            "authorization_sha256": authority.authorization_sha256,
            "canonical_revision": revision,
            "canonical_tree": tree,
            "decision_sha256": authority.decision_sha256,
            "predecessor_failure_sha256": authority.predecessor_failure_sha256,
            "predecessor_merge_sha": authority.predecessor_merge_sha,
            "predecessor_merge_tree": authority.predecessor_merge_tree,
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-2-AUTHORITY-RECEIPT-V1",
            "static_manifest_sha256": authority.static_manifest_sha256,
        },
    )


def _write_launch_consumption_receipt(
    custody: Path,
    *,
    revision: str,
    authority: EvidenceRecovery2AuthorityIdentity,
) -> None:
    _write_json(
        custody / _LAUNCH_CONSUMPTION_RECEIPT,
        {
            "authorization_sha256": authority.authorization_sha256,
            "automatic_relaunch_authorized": False,
            "automatic_retry_authorized": False,
            "canonical_revision": revision,
            "host_continuous_retention_required": True,
            "launch_authorization_consumed": True,
            "preflight_failure_exhausts_launch": True,
            "provider_or_session_failure_exhausts_launch": True,
            "purpose": "EVIDENCE_RECOVERY_ONLY",
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-2-LAUNCH-CONSUMPTION-V1",
        },
    )


def _build_bundle(custody: Path, *, revision: str, tree: str) -> bytes:
    artifacts: list[dict[str, object]] = []
    for name in _REQUIRED_BUNDLE_FILES:
        path = custody / name
        if not path.is_file():
            raise EvidenceRecovery2LaunchError(f"required Recovery-2 artifact is missing: {name}")
        raw = path.read_bytes()
        if not raw:
            raise EvidenceRecovery2LaunchError(f"required Recovery-2 artifact is empty: {name}")
        artifacts.append(
            {
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


def _write_ready(custody: Path, bundle: bytes) -> None:
    _write_json(
        custody / _READY,
        {
            "bundle_byte_count": len(bundle),
            "bundle_path": _BUNDLE,
            "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
            "required_artifact_count": len(_REQUIRED_BUNDLE_FILES),
            "schema_version": _READY_SCHEMA,
        },
    )


def _load_ack(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceRecovery2LaunchError("host acknowledgement is unreadable") from exc
    if type(value) is not dict:
        raise EvidenceRecovery2LaunchError("host acknowledgement must be an object")
    document = cast(dict[str, object], value)
    if _canonical_json_bytes(document) != raw:
        raise EvidenceRecovery2LaunchError("host acknowledgement is not canonical JSON")
    return document


def _wait_for_host_ack(
    custody: Path,
    *,
    bundle: bytes,
    timeout_seconds: float,
    poll_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    expected_sha = hashlib.sha256(bundle).hexdigest()
    while time.monotonic() < deadline:
        ack_path = custody / _HOST_ACK
        if ack_path.is_file():
            try:
                ack = _load_ack(ack_path)
            except EvidenceRecovery2LaunchError as exc:
                # An upload may be visible before its final bytes land. Retry
                # only transient read/canonicalization failures until deadline.
                if str(exc) not in (
                    "host acknowledgement is unreadable",
                    "host acknowledgement is not canonical JSON",
                ):
                    raise
                time.sleep(poll_seconds)
                continue
            if ack.get("schema_version") != _ACK_SCHEMA:
                raise EvidenceRecovery2LaunchError("host acknowledgement schema drifted")
            if ack.get("bundle_sha256") != expected_sha:
                raise EvidenceRecovery2LaunchError("host acknowledgement bundle hash mismatch")
            if ack.get("bundle_byte_count") != len(bundle):
                raise EvidenceRecovery2LaunchError("host acknowledgement bundle size mismatch")
            manifest_sha = ack.get("local_manifest_sha256")
            if type(manifest_sha) is not str or _SHA256.fullmatch(manifest_sha) is None:
                raise EvidenceRecovery2LaunchError(
                    "host acknowledgement manifest hash is malformed"
                )
            if ack.get("complete_local_evidence_verified") is not True:
                raise EvidenceRecovery2LaunchError(
                    "host acknowledgement did not verify complete evidence"
                )
            return
        time.sleep(poll_seconds)
    raise EvidenceRecovery2LaunchError("timed out waiting for host copy-out acknowledgement")


def run_authorized_evidence_recovery_2(
    *,
    repository_root: Path,
    custody: Path,
    python_executable: Path,
    expected_canonical_revision: str,
    ack_timeout_seconds: float = 1800.0,
    ack_poll_seconds: float = 1.0,
) -> bytes:
    """Run the frozen BMM sequence and hold success until host copy-out is verified."""

    root = repository_root.resolve(strict=True)
    current_head = _head(root)
    if current_head != expected_canonical_revision:
        raise EvidenceRecovery2LaunchError(
            "repository HEAD does not match the fresh-main-qualified canonical revision"
        )
    _require_clean(root)
    if _live_origin_main(root) != current_head:
        raise EvidenceRecovery2LaunchError("runtime revision is not exact live origin/main")
    _require_predecessor(root)
    _require_unconsumed(root)
    if custody.exists():
        raise EvidenceRecovery2LaunchError("custody path must not already exist")

    authority = validate_evidence_recovery_2_authority(root, current_head)
    current_tree = _tree(root)
    custody.mkdir(parents=True, exist_ok=False)
    _write_authority_receipt(
        custody,
        revision=current_head,
        tree=current_tree,
        authority=authority,
    )
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

    bundle = _build_bundle(custody, revision=current_head, tree=current_tree)
    _write_new(custody / _BUNDLE, bundle)
    _write_ready(custody, bundle)
    _wait_for_host_ack(
        custody,
        bundle=bundle,
        timeout_seconds=ack_timeout_seconds,
        poll_seconds=ack_poll_seconds,
    )
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--custody", type=Path, required=True)
    parser.add_argument("--python-executable", type=Path, required=True)
    parser.add_argument("--expected-canonical-revision", required=True)
    parser.add_argument("--ack-timeout-seconds", type=float, default=1800.0)
    args = parser.parse_args()
    run_authorized_evidence_recovery_2(
        repository_root=args.repository_root,
        custody=args.custody,
        python_executable=args.python_executable,
        expected_canonical_revision=args.expected_canonical_revision,
        ack_timeout_seconds=args.ack_timeout_seconds,
    )


if __name__ == "__main__":
    main()
