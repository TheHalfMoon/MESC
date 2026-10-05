#!/usr/bin/env python3
"""Host-side continuous-retention controller for MRL-0809 Recovery-2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

_HOST_LAUNCH_RECEIPT: Final = "evidence-recovery-2-host-launch-consumption.json"
_REMOTE_AUTHORITY: Final = "evidence-recovery-2-authority.json"
_REMOTE_LAUNCH: Final = "evidence-recovery-2-launch-consumption.json"
_REMOTE_BUNDLE: Final = "evidence-recovery-2-bundle.json"
_REMOTE_READY: Final = "evidence-recovery-2-copyout-ready.json"
_REMOTE_ACK: Final = "evidence-recovery-2-host-ack.json"
_LOCAL_MANIFEST: Final = "evidence-recovery-2-local-evidence-manifest.json"
_ACK_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-HOST-ACK-V1"
_READY_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-COPYOUT-READY-V1"
_BUNDLE_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-BUNDLE-V1"
_LOCAL_MANIFEST_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-LOCAL-MANIFEST-V1"
_REQUIRED_REMOTE_FILES: Final = (
    "bmm-portability-preflight.json",
    _REMOTE_AUTHORITY,
    _REMOTE_LAUNCH,
    "gemma-observation.json",
    "gemma-observation.json.probe-start.json",
    "gemma-stage.json",
    "qwen-observation.json",
    "qwen-observation.json.probe-start.json",
    "qwen-stage.json",
    "runtime-feasibility-v2-bmm-repair-1.json",
    _REMOTE_BUNDLE,
    _REMOTE_READY,
)


class EvidenceRecovery2HostError(RuntimeError):
    """Host-side Recovery-2 retention failed closed."""


@dataclass(frozen=True, slots=True)
class LocalArtifact:
    path: str
    byte_count: int
    sha256: str


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


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new_fsync(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _replace_fsync(temp_path: Path, final_path: Path) -> None:
    with temp_path.open("rb+") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    temp_path.replace(final_path)
    _fsync_directory(final_path.parent)


def _run_colab(args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        tuple(args),
        check=False,
        text=True,
        encoding="utf-8",
        capture_output=True,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_canonical_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceRecovery2HostError(f"{label} is unreadable") from exc
    if type(value) is not dict:
        raise EvidenceRecovery2HostError(f"{label} must be a JSON object")
    document = cast(dict[str, object], value)
    if _canonical_json_bytes(document) != raw:
        raise EvidenceRecovery2HostError(f"{label} is not canonical JSON")
    return document


def _validate_host_launch_receipt(
    local_dir: Path,
    *,
    session_name: str,
    expected_canonical_revision: str,
) -> None:
    receipt = _load_canonical_object(
        local_dir / _HOST_LAUNCH_RECEIPT,
        label="host launch-consumption receipt",
    )
    expected = {
        "automatic_relaunch_authorized": False,
        "automatic_retry_authorized": False,
        "canonical_revision": expected_canonical_revision,
        "gpu_class": "STANDARD_T4",
        "launch_authorization_consumed": True,
        "monetary_cost_microunits": 0,
        "provider_class": "GOOGLE_COLAB_FREE",
        "purpose": "EVIDENCE_RECOVERY_ONLY",
        "schema_version": (
            "MESC-MRL-0809-EVIDENCE-RECOVERY-2-HOST-LAUNCH-CONSUMPTION-V1"
        ),
        "session_name": session_name,
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise EvidenceRecovery2HostError(
                f"host launch-consumption receipt binding mismatch: {key}"
            )


def allocate_single_t4_session(
    *,
    colab_bin: str,
    session_name: str,
    local_evidence_dir: Path,
    canonical_revision: str,
    canonical_tree: str,
    authorization_sha256: str,
    decision_sha256: str,
) -> subprocess.CompletedProcess[str]:
    """Persist local consumption evidence, then invoke colab new exactly once."""

    evidence_dir = local_evidence_dir.resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    receipt = evidence_dir / _HOST_LAUNCH_RECEIPT
    _write_new_fsync(
        receipt,
        _canonical_json_bytes(
            {
                "authorization_sha256": authorization_sha256,
                "automatic_relaunch_authorized": False,
                "automatic_retry_authorized": False,
                "canonical_revision": canonical_revision,
                "canonical_tree": canonical_tree,
                "decision_sha256": decision_sha256,
                "gpu_class": "STANDARD_T4",
                "launch_authorization_consumed": True,
                "monetary_cost_microunits": 0,
                "provider_class": "GOOGLE_COLAB_FREE",
                "purpose": "EVIDENCE_RECOVERY_ONLY",
                "schema_version": ("MESC-MRL-0809-EVIDENCE-RECOVERY-2-HOST-LAUNCH-CONSUMPTION-V1"),
                "session_name": session_name,
            }
        ),
    )
    result = _run_colab((colab_bin, "new", "--session", session_name, "--gpu", "T4"))
    if result.returncode != 0:
        raise EvidenceRecovery2HostError(
            "single authorized Colab allocation failed after launch consumption"
        )
    return result


def _download_once(
    *,
    colab_bin: str,
    session_name: str,
    remote_custody: str,
    local_dir: Path,
    name: str,
    force: bool = False,
) -> bool:
    final_path = local_dir / name
    if final_path.is_file() and not force:
        return True
    partial_dir = local_dir / ".partial"
    partial_dir.mkdir(parents=True, exist_ok=True)
    temp_path = partial_dir / f"{name}.partial"
    temp_path.unlink(missing_ok=True)
    remote_path = f"{remote_custody.rstrip('/')}/{name}"
    result = _run_colab(
        (
            colab_bin,
            "download",
            "--session",
            session_name,
            remote_path,
            str(temp_path),
        )
    )
    if result.returncode != 0 or not temp_path.is_file():
        temp_path.unlink(missing_ok=True)
        return False
    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        return False
    _replace_fsync(temp_path, final_path)
    return True


def _verify_bundle_and_build_manifest(local_dir: Path) -> bytes:
    bundle_path = local_dir / _REMOTE_BUNDLE
    ready_path = local_dir / _REMOTE_READY
    if not bundle_path.is_file() or not ready_path.is_file():
        raise EvidenceRecovery2HostError("bundle/ready marker is not retained locally")

    bundle_raw = bundle_path.read_bytes()
    bundle = _load_canonical_object(bundle_path, label="Recovery-2 bundle")
    if bundle.get("schema_version") != _BUNDLE_SCHEMA:
        raise EvidenceRecovery2HostError("Recovery-2 bundle schema drifted")
    artifacts_value = bundle.get("artifacts")
    if type(artifacts_value) is not list:
        raise EvidenceRecovery2HostError("Recovery-2 bundle artifacts are malformed")
    rows = cast(list[object], artifacts_value)
    expected_names = set(_REQUIRED_REMOTE_FILES) - {_REMOTE_BUNDLE, _REMOTE_READY}
    seen: set[str] = set()
    local_rows: list[dict[str, object]] = []
    for item in rows:
        if type(item) is not dict:
            raise EvidenceRecovery2HostError("Recovery-2 bundle artifact row is malformed")
        row = cast(dict[str, object], item)
        name = row.get("path")
        if type(name) is not str or name not in expected_names or name in seen:
            raise EvidenceRecovery2HostError("Recovery-2 bundle artifact path drifted")
        path = local_dir / name
        if not path.is_file():
            raise EvidenceRecovery2HostError(f"required local evidence is missing: {name}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if row.get("byte_count") != len(raw) or row.get("sha256") != digest:
            raise EvidenceRecovery2HostError(f"local evidence mismatch: {name}")
        seen.add(name)
        local_rows.append({"byte_count": len(raw), "path": name, "sha256": digest})
    if seen != expected_names:
        raise EvidenceRecovery2HostError("Recovery-2 bundle did not bind the complete evidence set")

    ready = _load_canonical_object(ready_path, label="Recovery-2 ready marker")
    if ready.get("schema_version") != _READY_SCHEMA:
        raise EvidenceRecovery2HostError("Recovery-2 ready-marker schema drifted")
    bundle_sha = hashlib.sha256(bundle_raw).hexdigest()
    if ready.get("bundle_sha256") != bundle_sha:
        raise EvidenceRecovery2HostError("ready marker bundle hash mismatch")
    if ready.get("bundle_byte_count") != len(bundle_raw):
        raise EvidenceRecovery2HostError("ready marker bundle size mismatch")

    host_receipt = local_dir / _HOST_LAUNCH_RECEIPT
    if not host_receipt.is_file():
        raise EvidenceRecovery2HostError("host launch-consumption receipt is missing")
    local_rows.extend(
        [
            {
                "byte_count": host_receipt.stat().st_size,
                "path": _HOST_LAUNCH_RECEIPT,
                "sha256": _sha256(host_receipt),
            },
            {
                "byte_count": len(bundle_raw),
                "path": _REMOTE_BUNDLE,
                "sha256": bundle_sha,
            },
            {
                "byte_count": ready_path.stat().st_size,
                "path": _REMOTE_READY,
                "sha256": _sha256(ready_path),
            },
        ]
    )
    local_rows.sort(key=lambda row: cast(str, row["path"]))
    return _canonical_json_bytes(
        {
            "artifacts": local_rows,
            "complete_local_evidence_verified": True,
            "schema_version": _LOCAL_MANIFEST_SCHEMA,
        }
    )


def _write_ack(local_dir: Path, manifest_raw: bytes) -> Path:
    manifest_path = local_dir / _LOCAL_MANIFEST
    _write_new_fsync(manifest_path, manifest_raw)
    bundle_path = local_dir / _REMOTE_BUNDLE
    bundle_raw = bundle_path.read_bytes()
    ack_path = local_dir / _REMOTE_ACK
    _write_new_fsync(
        ack_path,
        _canonical_json_bytes(
            {
                "bundle_byte_count": len(bundle_raw),
                "bundle_sha256": hashlib.sha256(bundle_raw).hexdigest(),
                "complete_local_evidence_verified": True,
                "local_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
                "schema_version": _ACK_SCHEMA,
            }
        ),
    )
    return ack_path


def _upload_ack(
    *,
    colab_bin: str,
    session_name: str,
    remote_custody: str,
    ack_path: Path,
) -> bool:
    remote_path = f"{remote_custody.rstrip('/')}/{_REMOTE_ACK}"
    result = _run_colab(
        (
            colab_bin,
            "upload",
            "--session",
            session_name,
            str(ack_path),
            remote_path,
        )
    )
    return result.returncode == 0


def _write_runner(
    path: Path,
    *,
    remote_repository_root: str,
    remote_custody: str,
    remote_python: str,
    expected_canonical_revision: str,
) -> None:
    driver = (
        f"{remote_repository_root.rstrip('/')}/scripts/mesc_mrl_0809_evidence_recovery_2_driver.py"
    )
    argv = [
        remote_python,
        driver,
        "--repository-root",
        remote_repository_root,
        "--custody",
        remote_custody,
        "--python-executable",
        remote_python,
        "--expected-canonical-revision",
        expected_canonical_revision,
    ]
    source = (f"import subprocess\nraise SystemExit(subprocess.call({argv!r}))\n").encode()
    _write_new_fsync(path, source)


def run_with_continuous_retention(
    *,
    colab_bin: str,
    session_name: str,
    local_evidence_dir: Path,
    remote_repository_root: str,
    remote_custody: str,
    remote_python: str,
    expected_canonical_revision: str,
    poll_seconds: float = 1.0,
) -> None:
    """Start watcher first, invoke remote driver, and ACK only complete local evidence."""

    local_dir = local_evidence_dir.resolve()
    _validate_host_launch_receipt(
        local_dir,
        session_name=session_name,
        expected_canonical_revision=expected_canonical_revision,
    )

    stop = threading.Event()
    ack_complete = threading.Event()
    watcher_error: list[BaseException] = []

    def watcher() -> None:
        ack_path: Path | None = None
        try:
            while not stop.is_set():
                for name in _REQUIRED_REMOTE_FILES:
                    _download_once(
                        colab_bin=colab_bin,
                        session_name=session_name,
                        remote_custody=remote_custody,
                        local_dir=local_dir,
                        name=name,
                    )

                if (local_dir / _REMOTE_READY).is_file():
                    refresh_complete = True
                    for name in _REQUIRED_REMOTE_FILES:
                        if not _download_once(
                            colab_bin=colab_bin,
                            session_name=session_name,
                            remote_custody=remote_custody,
                            local_dir=local_dir,
                            name=name,
                            force=True,
                        ):
                            refresh_complete = False
                    if refresh_complete:
                        try:
                            manifest_raw = _verify_bundle_and_build_manifest(local_dir)
                        except EvidenceRecovery2HostError:
                            stop.wait(poll_seconds)
                            continue
                        if ack_path is None:
                            ack_path = _write_ack(local_dir, manifest_raw)
                        if _upload_ack(
                            colab_bin=colab_bin,
                            session_name=session_name,
                            remote_custody=remote_custody,
                            ack_path=ack_path,
                        ):
                            ack_complete.set()
                            return
                stop.wait(poll_seconds)
        except BaseException as exc:
            watcher_error.append(exc)
            stop.set()

    thread = threading.Thread(target=watcher, name="mesc-recovery2-retention", daemon=True)
    thread.start()
    if not thread.is_alive():
        raise EvidenceRecovery2HostError("continuous-retention watcher did not start")

    runner_path = local_dir / "evidence-recovery-2-colab-runner.py"
    _write_runner(
        runner_path,
        remote_repository_root=remote_repository_root,
        remote_custody=remote_custody,
        remote_python=remote_python,
        expected_canonical_revision=expected_canonical_revision,
    )
    try:
        result = _run_colab((colab_bin, "exec", "--session", session_name, "-f", str(runner_path)))
    finally:
        stop.set()
        thread.join(timeout=10.0)

    if watcher_error:
        raise EvidenceRecovery2HostError("continuous-retention watcher failed") from watcher_error[
            0
        ]
    if result.returncode != 0:
        raise EvidenceRecovery2HostError(
            "remote Recovery-2 driver failed; launch is consumed and no retry is authorized"
        )
    if not ack_complete.is_set():
        raise EvidenceRecovery2HostError(
            "remote driver returned without complete locally verified evidence"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    allocate = subparsers.add_parser("allocate")
    allocate.add_argument("--colab-bin", default="colab")
    allocate.add_argument("--session", required=True)
    allocate.add_argument("--local-evidence-dir", type=Path, required=True)
    allocate.add_argument("--canonical-revision", required=True)
    allocate.add_argument("--canonical-tree", required=True)
    allocate.add_argument("--authorization-sha256", required=True)
    allocate.add_argument("--decision-sha256", required=True)

    run = subparsers.add_parser("run")
    run.add_argument("--colab-bin", default="colab")
    run.add_argument("--session", required=True)
    run.add_argument("--local-evidence-dir", type=Path, required=True)
    run.add_argument("--remote-repository-root", required=True)
    run.add_argument("--remote-custody", required=True)
    run.add_argument("--remote-python", required=True)
    run.add_argument("--expected-canonical-revision", required=True)

    args = parser.parse_args()
    if args.command == "allocate":
        allocate_single_t4_session(
            colab_bin=args.colab_bin,
            session_name=args.session,
            local_evidence_dir=args.local_evidence_dir,
            canonical_revision=args.canonical_revision,
            canonical_tree=args.canonical_tree,
            authorization_sha256=args.authorization_sha256,
            decision_sha256=args.decision_sha256,
        )
    else:
        run_with_continuous_retention(
            colab_bin=args.colab_bin,
            session_name=args.session,
            local_evidence_dir=args.local_evidence_dir,
            remote_repository_root=args.remote_repository_root,
            remote_custody=args.remote_custody,
            remote_python=args.remote_python,
            expected_canonical_revision=args.expected_canonical_revision,
        )


if __name__ == "__main__":
    main()
