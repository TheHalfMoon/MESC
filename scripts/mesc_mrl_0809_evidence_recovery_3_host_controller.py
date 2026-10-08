#!/usr/bin/env python3
"""Host-side continuous-retention controller for MRL-0809 Recovery-3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from medscale.mesc._mrl_0809_evidence_recovery_3_control_plane_v1 import (
    Phase,
    Recovery3PreflightError,
    validate_recovery_3_control_plane,
)
from medscale.mesc._mrl_0809_evidence_recovery_3_gate_v1 import (
    require_recovery_3_launch_effectiveness,
)

if TYPE_CHECKING:
    from medscale.mesc._mrl_0809_evidence_recovery_3_effectiveness_v1 import (
        Recovery3EffectiveIdentity,
    )

_GLOBAL_CONSUMPTION_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-GLOBAL-CONSUMPTION-V1"

_HOST_LAUNCH_RECEIPT: Final = "evidence-recovery-3-host-launch-consumption.json"
_ALLOCATION_OUTCOME: Final = "evidence-recovery-3-colab-allocation-outcome.json"
_BEFORE_CONTROL_PLANE: Final = "evidence-recovery-3-control-plane-before.json"
_AFTER_CONTROL_PLANE: Final = "evidence-recovery-3-control-plane-after.json"
_COPY_JOURNAL: Final = "evidence-recovery-3-local-copy-journal.jsonl"
_EXEC_WAIT_SECONDS: Final = 14400.0
_ALLOCATION_WAIT_SECONDS: Final = 60.0
_TERMINATION_OBSERVATION: Final = "evidence-recovery-3-control-plane-terminated.json"
_REMOTE_AUTHORITY: Final = "evidence-recovery-3-authority.json"
_REMOTE_LAUNCH: Final = "evidence-recovery-3-launch-consumption.json"
_REMOTE_BUNDLE: Final = "evidence-recovery-3-bundle.json"
_REMOTE_READY: Final = "evidence-recovery-3-copyout-ready.json"
_REMOTE_ACK: Final = "evidence-recovery-3-host-ack.json"
_LOCAL_MANIFEST: Final = "evidence-recovery-3-local-evidence-manifest.json"
_ACK_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-ACK-V1"
_READY_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-COPYOUT-READY-V1"
_BUNDLE_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-BUNDLE-V1"
_LOCAL_MANIFEST_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-LOCAL-MANIFEST-V1"
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


class EvidenceRecovery3HostError(RuntimeError):
    """Host-side Recovery-3 retention failed closed."""


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


def _record_provisional_copy(path: Path) -> None:
    raw = path.read_bytes()
    entry = _canonical_json_bytes(
        {
            "byte_count": len(raw),
            "path": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "state": "PROVISIONAL_COPY_ONLY",
        }
    )
    descriptor = os.open(path.parent / _COPY_JOURNAL, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "ab") as handle:
        handle.write(entry)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_directory(path.parent)


def _kill_local_client_tree(process: subprocess.Popen[str]) -> None:
    """Kill only this newly spawned client and descendants, never provider work."""
    if sys.platform == "win32":
        try:
            # A venv launcher owns a child Python process that inherits pipes.
            # Killing the launcher first loses the process-tree relationship.
            subprocess.run(
                ("taskkill", "/PID", str(process.pid), "/T", "/F"),
                check=False,
                capture_output=True,
                timeout=2.0,
            )
        except (OSError, subprocess.SubprocessError):
            if process.poll() is None:
                process.kill()
    else:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)


def _run_colab(
    args: Sequence[str],
    *,
    timeout_seconds: float | None = None,
    abort_event: threading.Event | None = None,
) -> subprocess.CompletedProcess[str]:
    if abort_event is not None and timeout_seconds is None:
        raise ValueError("supervised execution requires a finite client timeout")
    if timeout_seconds is None:
        return subprocess.run(
            tuple(args),
            check=False,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
    deadline = time.monotonic() + timeout_seconds
    process = subprocess.Popen(
        tuple(args),
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=sys.platform != "win32",
    )
    # Avoid Popen's context-manager pipe close on an unresponsive descendant:
    # that close can block despite a communicate timeout on Windows.
    try:
        while True:
            try:
                stdout, stderr = process.communicate(timeout=0.2)
                return subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired as exc:
                expired = time.monotonic() >= deadline
                aborted = abort_event is not None and abort_event.is_set()
                if not aborted and not expired:
                    continue
                # Provider shutdown is separate; client cancellation proves
                # only local process-tree cleanup, never remote termination.
                _kill_local_client_tree(process)
                try:
                    stdout, stderr = process.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    if process.poll() is None:
                        process.kill()
                    raise
                if expired:
                    raise subprocess.TimeoutExpired(args, timeout_seconds, stdout, stderr) from exc
                return subprocess.CompletedProcess(args, process.returncode or 1, stdout, stderr)
    finally:
        if process.poll() is None:
            _kill_local_client_tree(process)
            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2.0)


def _diagnostic_text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""


def _observe_session_terminated(*, session_name: str, local_dir: Path) -> bool:
    """Read the provider independently; stop success alone is insufficient."""
    observation_path = local_dir / _TERMINATION_OBSERVATION
    observer = Path(__file__).with_name("mesc_mrl_0809_evidence_recovery_3_control_plane.py")
    try:
        result = _run_colab(
            (
                sys.executable,
                str(observer),
                "--phase",
                "BEFORE_ALLOCATION",
                "--session",
                session_name,
                "--output",
                str(observation_path),
            ),
            timeout_seconds=20.0,
        )
        if result.returncode != 0:
            return False
        observation = _load_canonical_object(
            observation_path, label="independent termination observation"
        )
        validate_recovery_3_control_plane(
            observation, phase="BEFORE_ALLOCATION", session_name=session_name
        )
        return True
    except (
        OSError,
        subprocess.SubprocessError,
        Recovery3PreflightError,
        EvidenceRecovery3HostError,
    ):
        return False


def _stop_failed_session(*, colab_bin: str, session_name: str, local_dir: Path) -> bool:
    document: dict[str, object] = {
        "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-STOP-OUTCOME-V1",
        "session_name": session_name,
    }
    try:
        result = _run_colab((colab_bin, "stop", "--session", session_name), timeout_seconds=20.0)
        document.update(returncode=result.returncode, stdout=result.stdout, stderr=result.stderr)
        succeeded = result.returncode == 0
    except (OSError, subprocess.SubprocessError) as exc:
        document.update(returncode=None, error_type=type(exc).__name__, error=str(exc))
        if isinstance(exc, subprocess.TimeoutExpired):
            document.update(
                stdout=_diagnostic_text(exc.stdout), stderr=_diagnostic_text(exc.stderr)
            )
        succeeded = False
    document["stop_command_succeeded"] = succeeded
    verified = _observe_session_terminated(session_name=session_name, local_dir=local_dir)
    document["independent_zero_assignments_verified"] = verified
    document["termination_state"] = "VERIFIED_UNASSIGNED" if verified else "UNPROVEN"
    _write_new_fsync(
        local_dir / "evidence-recovery-3-colab-stop-outcome.json", _canonical_json_bytes(document)
    )
    return verified


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_canonical_object(path: Path, *, label: str) -> dict[str, object]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceRecovery3HostError(f"{label} is unreadable") from exc
    if type(value) is not dict:
        raise EvidenceRecovery3HostError(f"{label} must be a JSON object")
    document = cast(dict[str, object], value)
    if _canonical_json_bytes(document) != raw:
        raise EvidenceRecovery3HostError(f"{label} is not canonical JSON")
    return document


def _validate_control_plane(local_dir: Path, *, session_name: str, phase: str) -> None:
    name = _BEFORE_CONTROL_PLANE if phase == "BEFORE_ALLOCATION" else _AFTER_CONTROL_PLANE
    document = _load_canonical_object(local_dir / name, label="Recovery-3 control plane")
    try:
        validate_recovery_3_control_plane(
            document, phase=cast(Phase, phase), session_name=session_name
        )
    except Recovery3PreflightError as exc:
        raise EvidenceRecovery3HostError("Recovery-3 zero-paid-unit control plane failed") from exc


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
        "schema_version": ("MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-LAUNCH-CONSUMPTION-V1"),
        "session_name": session_name,
    }
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise EvidenceRecovery3HostError(
                f"host launch-consumption receipt binding mismatch: {key}"
            )
    outcome = _load_canonical_object(
        local_dir / _ALLOCATION_OUTCOME, label="host allocation outcome"
    )
    if (
        outcome.get("schema_version") != "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-ALLOC-OUTCOME-V1"
        or type(outcome.get("returncode")) is not int
        or outcome.get("returncode") != 0
        or outcome.get("session_name") != session_name
        or outcome.get("host_launch_receipt_sha256") != _sha256(local_dir / _HOST_LAUNCH_RECEIPT)
    ):
        raise EvidenceRecovery3HostError("successful bound host allocation outcome is required")


def _effective_host_binding(identity: Recovery3EffectiveIdentity) -> dict[str, object]:
    binding: dict[str, object] = {
        "canonical_revision": identity.canonical_revision,
        "canonical_tree": identity.canonical_tree,
        "approved_implementation_sha": identity.approved_implementation_sha,
        "implementation_merge_sha": identity.implementation_merge_sha,
        "approval_comment_id": identity.approval_comment_id,
        "approval_body_sha256": identity.approval_body_sha256,
        "authorization_sha256": identity.authority.authorization_sha256,
        "decision_sha256": identity.authority.decision_sha256,
    }
    for field, value in binding.items():
        if field == "approval_comment_id":
            valid = type(value) is int and value > 0
        else:
            length = 64 if field.endswith("sha256") else 40
            valid = (
                type(value) is str
                and re.fullmatch(rf"[0-9a-f]{{{length}}}", value, flags=re.ASCII) is not None
            )
        if not valid:
            raise EvidenceRecovery3HostError(f"effective identity is malformed: {field}")
    return binding


def _account_state_directory() -> str:
    """Resolve the actual OS account; environment-selected homes are forbidden."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        shell = ctypes.WinDLL("shell32", use_last_error=True)
        getter = shell.SHGetFolderPathW
        getter.argtypes = (
            wintypes.HWND,
            ctypes.c_int,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
        )
        getter.restype = ctypes.c_long
        buffer = ctypes.create_unicode_buffer(32768)
        # CSIDL_LOCAL_APPDATA for the current process user, current location.
        if getter(None, 28, None, 0, buffer) != 0 or not buffer.value:
            raise EvidenceRecovery3HostError("OS account state directory is unavailable")
        return buffer.value
    else:
        import pwd

        return str(Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local" / "state")


def _host_state_root() -> Path:
    try:
        account_path = Path(_account_state_directory())
        if not account_path.is_absolute():
            raise EvidenceRecovery3HostError("OS account state directory must be absolute")
        return account_path.resolve() / "mesc" / "evidence-recovery-3"
    except (OSError, KeyError) as exc:
        raise EvidenceRecovery3HostError("OS account state directory is unavailable") from exc


def _global_receipt_path() -> Path:
    # One fixed grant across all implementation revisions and approval comments.
    return _host_state_root() / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3.json"


def _consume_host_execution(
    *,
    local_dir: Path,
    session_name: str,
    remote_repository_root: str,
    remote_custody: str,
    remote_python: str,
) -> None:
    receipt = _load_canonical_object(local_dir / _HOST_LAUNCH_RECEIPT, label="host launch receipt")
    binding = {
        field: receipt.get(field)
        for field in (
            "canonical_revision",
            "canonical_tree",
            "approved_implementation_sha",
            "implementation_merge_sha",
            "approval_comment_id",
            "approval_body_sha256",
            "authorization_sha256",
            "decision_sha256",
            "global_consumption_sha256",
        )
    }
    _write_new_fsync(
        _host_state_root() / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3-host-execution.json",
        _canonical_json_bytes(
            {
                **binding,
                "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-EXECUTION-START-V1",
                "host_execution_authorization_consumed": True,
                "host_launch_receipt_sha256": _sha256(local_dir / _HOST_LAUNCH_RECEIPT),
                "session_name": session_name,
                "remote_repository_root": remote_repository_root,
                "remote_custody": remote_custody,
                "remote_python": remote_python,
            }
        ),
    )


def _validate_effective_host_receipt(
    local_dir: Path, *, identity: Recovery3EffectiveIdentity, session_name: str
) -> None:
    binding = _effective_host_binding(identity)
    receipt = _load_canonical_object(local_dir / _HOST_LAUNCH_RECEIPT, label="host launch receipt")
    global_path = _global_receipt_path()
    global_receipt = _load_canonical_object(global_path, label="global launch-consumption receipt")
    for document in (receipt, global_receipt):
        for field, value in binding.items():
            if type(document.get(field)) is not type(value) or document.get(field) != value:
                raise EvidenceRecovery3HostError(
                    f"effective host receipt binding mismatch: {field}"
                )
    if (
        global_receipt.get("schema_version") != _GLOBAL_CONSUMPTION_SCHEMA
        or global_receipt.get("launch_authorization_consumed") is not True
        or global_receipt.get("session_name") != session_name
        or receipt.get("global_consumption_sha256") != _sha256(global_path)
    ):
        raise EvidenceRecovery3HostError("global launch-consumption receipt binding mismatch")


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

    identity = require_recovery_3_launch_effectiveness(
        Path(__file__).resolve().parents[1], canonical_revision
    )
    binding = _effective_host_binding(identity)
    for field, value in (
        ("canonical_revision", canonical_revision),
        ("canonical_tree", canonical_tree),
        ("authorization_sha256", authorization_sha256),
        ("decision_sha256", decision_sha256),
    ):
        if type(value) is not str or binding[field] != value:
            raise EvidenceRecovery3HostError(f"allocation authority binding mismatch: {field}")
    evidence_dir = local_evidence_dir.resolve()
    _validate_control_plane(evidence_dir, session_name=session_name, phase="BEFORE_ALLOCATION")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    global_path = _global_receipt_path()
    # Exclusive fsync precedes the local receipt and every provider command.
    # Never unlink this anchor, including on a failed local write or allocation.
    _write_new_fsync(
        global_path,
        _canonical_json_bytes(
            {
                **binding,
                "schema_version": _GLOBAL_CONSUMPTION_SCHEMA,
                "session_name": session_name,
                "launch_authorization_consumed": True,
            }
        ),
    )
    receipt = evidence_dir / _HOST_LAUNCH_RECEIPT
    _write_new_fsync(
        receipt,
        _canonical_json_bytes(
            {
                **binding,
                "global_consumption_sha256": _sha256(global_path),
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
                "schema_version": ("MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-LAUNCH-CONSUMPTION-V1"),
                "session_name": session_name,
            }
        ),
    )
    result: subprocess.CompletedProcess[str] | None = None
    try:
        result = _run_colab(
            (colab_bin, "new", "--session", session_name, "--gpu", "T4"),
            timeout_seconds=_ALLOCATION_WAIT_SECONDS,
        )
        _write_new_fsync(
            evidence_dir / _ALLOCATION_OUTCOME,
            _canonical_json_bytes(
                {
                    "host_launch_receipt_sha256": _sha256(receipt),
                    "returncode": result.returncode,
                    "session_name": session_name,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-ALLOC-OUTCOME-V1",
                }
            ),
        )
        if result.returncode != 0:
            raise EvidenceRecovery3HostError(
                "single authorized Colab allocation failed after launch consumption"
            )
        return result
    except BaseException as exc:
        # An ambiguous allocation still exhausts the grant. Never repeat new.
        document: dict[str, object] = {
            "returncode": None if result is None else result.returncode,
            "session_name": session_name,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-ALLOC-OUTCOME-V1",
        }
        if isinstance(exc, subprocess.TimeoutExpired):
            document.update(
                stdout=_diagnostic_text(exc.stdout), stderr=_diagnostic_text(exc.stderr)
            )
        with suppress(OSError):
            document["host_launch_receipt_sha256"] = _sha256(receipt)
            _write_new_fsync(evidence_dir / _ALLOCATION_OUTCOME, _canonical_json_bytes(document))
        verified = False
        with suppress(OSError, subprocess.SubprocessError):
            verified = _stop_failed_session(
                colab_bin=colab_bin, session_name=session_name, local_dir=evidence_dir
            )
        message = "single authorized Colab allocation failed after launch consumption"
        if not verified:
            message += (
                "; remote termination UNPROVEN; operator intervention required for this session"
            )
        raise EvidenceRecovery3HostError(message) from exc


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
    try:
        result = _run_colab(
            (
                colab_bin,
                "download",
                "--session",
                session_name,
                remote_path,
                str(temp_path),
            ),
            timeout_seconds=20.0,
        )
    except subprocess.TimeoutExpired:
        temp_path.unlink(missing_ok=True)
        return False
    if result.returncode != 0 or not temp_path.is_file():
        temp_path.unlink(missing_ok=True)
        return False
    if temp_path.stat().st_size == 0:
        temp_path.unlink(missing_ok=True)
        return False
    _replace_fsync(temp_path, final_path)
    _record_provisional_copy(final_path)
    return True


def _verify_bundle_and_build_manifest(local_dir: Path) -> bytes:
    bundle_path = local_dir / _REMOTE_BUNDLE
    ready_path = local_dir / _REMOTE_READY
    if not bundle_path.is_file() or not ready_path.is_file():
        raise EvidenceRecovery3HostError("bundle/ready marker is not retained locally")

    bundle_raw = bundle_path.read_bytes()
    bundle = _load_canonical_object(bundle_path, label="Recovery-3 bundle")
    if bundle.get("schema_version") != _BUNDLE_SCHEMA:
        raise EvidenceRecovery3HostError("Recovery-3 bundle schema drifted")
    if bundle.get("purpose") != "EVIDENCE_RECOVERY_ONLY":
        raise EvidenceRecovery3HostError("Recovery-3 bundle purpose drifted")
    artifacts_value = bundle.get("artifacts")
    if type(artifacts_value) is not list:
        raise EvidenceRecovery3HostError("Recovery-3 bundle artifacts are malformed")
    rows = cast(list[object], artifacts_value)
    expected_names = set(_REQUIRED_REMOTE_FILES) - {_REMOTE_BUNDLE, _REMOTE_READY}
    seen: set[str] = set()
    local_rows: list[dict[str, object]] = []
    for item in rows:
        if type(item) is not dict:
            raise EvidenceRecovery3HostError("Recovery-3 bundle artifact row is malformed")
        row = cast(dict[str, object], item)
        name = row.get("path")
        if type(name) is not str or name not in expected_names or name in seen:
            raise EvidenceRecovery3HostError("Recovery-3 bundle artifact path drifted")
        path = local_dir / name
        if not path.is_file():
            raise EvidenceRecovery3HostError(f"required local evidence is missing: {name}")
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if row.get("byte_count") != len(raw) or row.get("sha256") != digest:
            raise EvidenceRecovery3HostError(f"local evidence mismatch: {name}")
        seen.add(name)
        local_rows.append({"byte_count": len(raw), "path": name, "sha256": digest})
    if seen != expected_names:
        raise EvidenceRecovery3HostError("Recovery-3 bundle did not bind the complete evidence set")

    ready = _load_canonical_object(ready_path, label="Recovery-3 ready marker")
    if ready.get("schema_version") != _READY_SCHEMA:
        raise EvidenceRecovery3HostError("Recovery-3 ready-marker schema drifted")
    bundle_sha = hashlib.sha256(bundle_raw).hexdigest()
    if ready.get("bundle_sha256") != bundle_sha:
        raise EvidenceRecovery3HostError("ready marker bundle hash mismatch")
    if ready.get("bundle_byte_count") != len(bundle_raw):
        raise EvidenceRecovery3HostError("ready marker bundle size mismatch")
    if ready.get("bundle_path") != _REMOTE_BUNDLE:
        raise EvidenceRecovery3HostError("ready marker bundle path mismatch")
    if ready.get("required_artifact_count") != len(expected_names):
        raise EvidenceRecovery3HostError("ready marker artifact count mismatch")

    host_receipt = local_dir / _HOST_LAUNCH_RECEIPT
    if not host_receipt.is_file():
        raise EvidenceRecovery3HostError("host launch-consumption receipt is missing")
    host_identity = _load_canonical_object(host_receipt, label="host launch-consumption receipt")
    if (bundle.get("canonical_revision"), bundle.get("canonical_tree")) != (
        host_identity.get("canonical_revision"),
        host_identity.get("canonical_tree"),
    ):
        raise EvidenceRecovery3HostError("Recovery-3 bundle canonical identity mismatch")
    authority = _load_canonical_object(
        local_dir / _REMOTE_AUTHORITY, label="Recovery-3 remote authority receipt"
    )
    if authority.get("schema_version") != (
        "MESC-MRL-0809-EVIDENCE-RECOVERY-3-AUTHORITY-RECEIPT-V1"
    ):
        raise EvidenceRecovery3HostError("Recovery-3 authority receipt schema drifted")
    for field in (
        "authorization_sha256",
        "decision_sha256",
        "canonical_revision",
        "canonical_tree",
    ):
        if authority.get(field) != host_identity.get(field):
            raise EvidenceRecovery3HostError(f"Recovery-3 authority receipt mismatch: {field}")
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
    try:
        result = _run_colab(
            (
                colab_bin,
                "upload",
                "--session",
                session_name,
                str(ack_path),
                remote_path,
            ),
            timeout_seconds=20.0,
        )
    except subprocess.TimeoutExpired:
        return False
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
        f"{remote_repository_root.rstrip('/')}/scripts/mesc_mrl_0809_evidence_recovery_3_driver.py"
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


def _run_with_continuous_retention(
    *,
    colab_bin: str,
    session_name: str,
    local_evidence_dir: Path,
    remote_repository_root: str,
    remote_custody: str,
    remote_python: str,
    expected_canonical_revision: str,
    poll_seconds: float = 1.0,
    stop_session: Callable[[], bool],
) -> None:
    """Start watcher first, invoke remote driver, and ACK only complete local evidence."""

    identity = require_recovery_3_launch_effectiveness(
        Path(__file__).resolve().parents[1], expected_canonical_revision
    )
    _validate_effective_host_receipt(
        local_evidence_dir.resolve(), identity=identity, session_name=session_name
    )
    local_dir = local_evidence_dir.resolve()
    _validate_control_plane(local_dir, session_name=session_name, phase="AFTER_ALLOCATION")
    _validate_host_launch_receipt(
        local_dir,
        session_name=session_name,
        expected_canonical_revision=expected_canonical_revision,
    )

    stop = threading.Event()
    ack_complete = threading.Event()
    watcher_error: list[BaseException] = []
    termination_unproven = threading.Event()
    stop_requested = threading.Event()
    stop_lock = threading.Lock()

    def request_session_stop() -> None:
        with stop_lock:
            if stop_requested.is_set():
                return
            stop_requested.set()
        try:
            if not stop_session():
                termination_unproven.set()
        except (OSError, subprocess.SubprocessError):
            termination_unproven.set()

    def failure_message(message: str) -> str:
        if termination_unproven.is_set():
            message += (
                "; remote termination UNPROVEN; operator intervention required for this session"
            )
        return message

    def watcher() -> None:
        try:
            while not stop.is_set():
                for name in _REQUIRED_REMOTE_FILES:
                    if stop.is_set():
                        return
                    _download_once(
                        colab_bin=colab_bin,
                        session_name=session_name,
                        remote_custody=remote_custody,
                        local_dir=local_dir,
                        name=name,
                    )

                if stop.is_set():
                    return
                if (local_dir / _REMOTE_READY).is_file():
                    for name in _REQUIRED_REMOTE_FILES:
                        if stop.is_set():
                            return
                        if not _download_once(
                            colab_bin=colab_bin,
                            session_name=session_name,
                            remote_custody=remote_custody,
                            local_dir=local_dir,
                            name=name,
                            force=True,
                        ):
                            raise EvidenceRecovery3HostError(
                                f"final evidence copy-out failed: {name}"
                            )
                    manifest_raw = _verify_bundle_and_build_manifest(local_dir)
                    ack_path = _write_ack(local_dir, manifest_raw)
                    if not _upload_ack(
                        colab_bin=colab_bin,
                        session_name=session_name,
                        remote_custody=remote_custody,
                        ack_path=ack_path,
                    ):
                        raise EvidenceRecovery3HostError("host acknowledgement upload failed")
                    ack_complete.set()
                    return
                stop.wait(poll_seconds)
        except BaseException as exc:
            watcher_error.append(exc)
            stop.set()
            # Killing the local exec client does not stop remote model work.
            # Stop this consumed session at the provider, without a relaunch.
            request_session_stop()

    runner_path = local_dir / "evidence-recovery-3-colab-runner.py"
    _write_runner(
        runner_path,
        remote_repository_root=remote_repository_root,
        remote_custody=remote_custody,
        remote_python=remote_python,
        expected_canonical_revision=expected_canonical_revision,
    )
    thread = threading.Thread(target=watcher, name="mesc-recovery3-retention", daemon=True)
    thread.start()
    execution_error: BaseException | None = None
    try:
        if not thread.is_alive():
            raise EvidenceRecovery3HostError("continuous-retention watcher did not start")
        if stop.is_set():
            raise EvidenceRecovery3HostError("continuous-retention watcher failed before execution")
        result = _run_colab(
            (
                colab_bin,
                "exec",
                "--session",
                session_name,
                "-f",
                str(runner_path),
                "--timeout",
                str(_EXEC_WAIT_SECONDS),
            ),
            timeout_seconds=_EXEC_WAIT_SECONDS + 20.0,
            abort_event=stop,
        )
        # Preserve early driver errors locally even when custody does not exist.
        # This receipt is diagnostic only, never a verified-evidence manifest.
        _write_new_fsync(
            local_dir / "evidence-recovery-3-colab-exec-outcome.json",
            _canonical_json_bytes(
                {
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-EXEC-OUTCOME-V1",
                }
            ),
        )
    except BaseException as exc:
        execution_error = exc
        stop.set()
        request_session_stop()
        # Keep client-level failure diagnostics when the evidence disk permits.
        document: dict[str, object] = {
            "returncode": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-EXEC-OUTCOME-V1",
        }
        if isinstance(exc, subprocess.TimeoutExpired):
            document.update(
                stdout=_diagnostic_text(exc.stdout), stderr=_diagnostic_text(exc.stderr)
            )
        # Disk failure cannot be repaired by a second runtime invocation.
        with suppress(OSError):
            _write_new_fsync(
                local_dir / "evidence-recovery-3-colab-exec-outcome.json",
                _canonical_json_bytes(document),
            )
    finally:
        stop.set()
        request_session_stop()
        thread.join(timeout=25.0)
        # A failing remote driver may have produced its last evidence after the
        # watcher's final poll. Preserve the bytes without granting success.
        if not ack_complete.is_set() and not thread.is_alive():
            for name in _REQUIRED_REMOTE_FILES:
                try:
                    _download_once(
                        colab_bin=colab_bin,
                        session_name=session_name,
                        remote_custody=remote_custody,
                        local_dir=local_dir,
                        name=name,
                        force=True,
                    )
                except (OSError, subprocess.SubprocessError):
                    # This is best-effort failure evidence, never an ACK path.
                    continue

    if thread.is_alive():
        termination_unproven.set()
        request_session_stop()
        raise EvidenceRecovery3HostError(
            failure_message("continuous-retention watcher did not stop")
        )
    if execution_error is not None:
        raise EvidenceRecovery3HostError(
            failure_message("remote execution or local outcome retention failed; launch consumed")
        ) from execution_error
    if watcher_error or result.returncode != 0 or not ack_complete.is_set():
        request_session_stop()
    if watcher_error:
        raise EvidenceRecovery3HostError(
            failure_message("continuous-retention watcher failed")
        ) from watcher_error[0]
    if result.returncode != 0:
        raise EvidenceRecovery3HostError(
            failure_message(
                "remote Recovery-3 driver failed; launch is consumed and no retry is authorized"
            )
        )
    if not ack_complete.is_set():
        raise EvidenceRecovery3HostError(
            failure_message("remote driver returned without complete locally verified evidence")
        )


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
    """Clean up every exit after validating ownership of the allocated session."""
    local_dir = local_evidence_dir.resolve()
    # Invalid receipts must never stop another session. After ownership is
    # established, preflight, disk and thread-start failures all need cleanup.
    _validate_host_launch_receipt(
        local_dir,
        session_name=session_name,
        expected_canonical_revision=expected_canonical_revision,
    )
    stop_lock = threading.Lock()
    stop_attempted = False
    termination_verified = False

    def stop_session() -> bool:
        nonlocal stop_attempted, termination_verified
        with stop_lock:
            if not stop_attempted:
                stop_attempted = True
                try:
                    termination_verified = _stop_failed_session(
                        colab_bin=colab_bin, session_name=session_name, local_dir=local_dir
                    )
                except (OSError, subprocess.SubprocessError):
                    termination_verified = False
            return termination_verified

    try:
        _consume_host_execution(
            local_dir=local_dir,
            session_name=session_name,
            remote_repository_root=remote_repository_root,
            remote_custody=remote_custody,
            remote_python=remote_python,
        )
    except FileExistsError:
        # A duplicate must not stop or otherwise affect the first invocation.
        raise
    except BaseException as exc:
        if not stop_session():
            raise EvidenceRecovery3HostError(
                f"{exc}; remote termination UNPROVEN; "
                "operator intervention required for this session"
            ) from exc
        raise

    try:
        _run_with_continuous_retention(
            colab_bin=colab_bin,
            session_name=session_name,
            local_evidence_dir=local_dir,
            remote_repository_root=remote_repository_root,
            remote_custody=remote_custody,
            remote_python=remote_python,
            expected_canonical_revision=expected_canonical_revision,
            poll_seconds=poll_seconds,
            stop_session=stop_session,
        )
    except BaseException as exc:
        if not stop_session() and "termination UNPROVEN" not in str(exc):
            raise EvidenceRecovery3HostError(
                f"{exc}; remote termination UNPROVEN; "
                "operator intervention required for this session"
            ) from exc
        raise
    else:
        if not stop_session():
            raise EvidenceRecovery3HostError(
                "evidence retained but remote termination UNPROVEN; "
                "operator intervention required for this session"
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
