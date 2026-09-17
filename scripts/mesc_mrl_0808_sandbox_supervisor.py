#!/usr/bin/env python3
"""Supervise the synthetic MRL-0808 probe and enforce bounded output collection."""

from __future__ import annotations

import argparse
import contextlib
import errno
import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Final, Never, cast

OUTPUT_ROOT: Final = Path("/mesc-run/output")
PROBE: Final = Path("/mesc-run/repository/scripts/mesc_mrl_0808_sandbox_probe.py")
OBSERVATION_NAME: Final = "sandbox-observation.json"
CONTROL_NAME: Final = "sandbox-control-evidence.json"
MAXIMUM_TOTAL_BYTES: Final = 67_108_864
_COLLECTION_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-COLLECTION-V1"
_CONTROL_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-CONTROL-EVIDENCE-V1"


class SupervisorError(RuntimeError):
    """Fail-closed sandbox-supervisor error."""


def _reject_constant(token: str) -> Never:
    raise SupervisorError(f"non-standard JSON constant prohibited: {token}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise SupervisorError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def canonical_json_bytes(value: object) -> bytes:
    """Serialize the MESC canonical JSON subset with one terminal LF."""
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("utf-8") + b"\n"
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise SupervisorError("value cannot be canonically serialized") from exc


def parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse one exact canonical JSON object."""
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except SupervisorError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise SupervisorError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict:
        raise SupervisorError(f"{label} must be one object")
    document = cast(dict[str, object], value)
    if canonical_json_bytes(document) != raw:
        raise SupervisorError(f"{label} is not exact canonical JSON")
    return document


def write_new(path: Path, raw: bytes) -> None:
    """Create one output file without overwrite."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SupervisorError(f"refusing overwrite: {path}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def output_mount() -> tuple[str, int]:
    """Return the output mount type and reported capacity without relying on procfs."""
    if OUTPUT_ROOT.stat().st_dev == OUTPUT_ROOT.parent.stat().st_dev:
        raise SupervisorError("sandbox output root is not a distinct mount")
    completed = subprocess.run(
        ["/usr/bin/stat", "-f", "-c", "%T", str(OUTPUT_ROOT)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    mount_type = completed.stdout.strip()
    if completed.returncode != 0 or not mount_type:
        raise SupervisorError("cannot resolve sandbox output filesystem type")
    statvfs = getattr(os, "statvfs", None)
    if statvfs is None:
        raise SupervisorError("sandbox output filesystem capacity is unavailable")
    stats = statvfs(OUTPUT_ROOT)
    capacity = stats.f_frsize * stats.f_blocks
    return mount_type, capacity


def validate_output_set() -> tuple[dict[str, bytes], int]:
    """Require exactly the declared output classes within the frozen budget."""
    allowed = {
        OBSERVATION_NAME: "qualification-observation",
        CONTROL_NAME: "sandbox-control-evidence",
    }
    entries = {path.name: path for path in OUTPUT_ROOT.iterdir()}
    if set(entries) != set(allowed):
        extra = sorted(set(entries) - set(allowed))
        missing = sorted(set(allowed) - set(entries))
        raise SupervisorError(f"output artifact class mismatch: extra={extra} missing={missing}")
    payloads: dict[str, bytes] = {}
    total = 0
    for name, path in entries.items():
        if path.is_symlink() or not path.is_file():
            raise SupervisorError(f"output artifact is not a regular file: {name}")
        raw = path.read_bytes()
        total += len(raw)
        payloads[name] = raw
    if total > MAXIMUM_TOTAL_BYTES:
        raise SupervisorError("output artifact budget exceeded")
    return payloads, total


def denied_write(path: Path) -> bool:
    """Return whether a filesystem write is denied at one forbidden path."""
    try:
        path.write_bytes(b"forbidden")
    except OSError:
        return True
    else:
        with contextlib.suppress(OSError):
            path.unlink()
        return False


def gpu_observation() -> str:
    """Prove the launcher's exact NVIDIA device set remains visible inside the sandbox."""
    expected_gpu = os.environ.get("MESC_MRL0808_GPU_OBSERVATION", "").strip()
    raw_nodes = os.environ.get("MESC_MRL0808_NVIDIA_DEVICE_NODES", "")
    if not expected_gpu or not raw_nodes:
        raise SupervisorError("sandbox GPU identity environment is incomplete")
    try:
        parsed_nodes = json.loads(raw_nodes)
    except (TypeError, ValueError) as exc:
        raise SupervisorError("sandbox NVIDIA device-node identity is invalid") from exc
    if type(parsed_nodes) is not list or not parsed_nodes:
        raise SupervisorError("sandbox NVIDIA device-node identity must be a non-empty list")
    expected_nodes = [str(value) for value in parsed_nodes]
    if expected_nodes != sorted(set(expected_nodes)) or any(
        not value.startswith("/dev/nvidia") for value in expected_nodes
    ):
        raise SupervisorError("sandbox NVIDIA device-node identity escaped frozen scope")
    actual_nodes: list[str] = []
    for candidate in sorted(Path("/dev").glob("nvidia*")):
        candidates = candidate.rglob("*") if candidate.is_dir() else (candidate,)
        for path in candidates:
            try:
                mode = path.stat().st_mode
            except OSError:
                continue
            if stat.S_ISCHR(mode):
                actual_nodes.append(str(path))
    if sorted(set(actual_nodes)) != expected_nodes:
        raise SupervisorError("sandbox NVIDIA device-node set drifted")
    return expected_gpu


def normal() -> int:
    """Run the real control probe, validate outputs, and emit a collection envelope."""
    mount_type, capacity = output_mount()
    if mount_type != "tmpfs" or capacity > MAXIMUM_TOTAL_BYTES:
        raise SupervisorError("sandbox output tmpfs budget is not enforced")
    probe = subprocess.run(
        [sys.executable, str(PROBE)],
        check=False,
        capture_output=True,
    )
    if probe.returncode != 0:
        raise SupervisorError("sandbox control probe failed")
    observation = parse_canonical_object(probe.stdout, label="sandbox observation")
    observation_raw = canonical_json_bytes(observation)
    write_new(OUTPUT_ROOT / OBSERVATION_NAME, observation_raw)
    gpu = gpu_observation()
    forbidden_host_roots = ("/content", "/home", "/mnt", "/root", "/run", "/var")
    if any(Path(path).exists() for path in forbidden_host_roots):
        raise SupervisorError("undeclared host-data root is visible inside the sandbox")
    if not Path("/usr").is_dir() or not Path("/sys").is_dir():
        raise SupervisorError("required read-only runtime support root is missing")
    if not denied_write(Path("/dev/.mrl0808-write-probe")):
        raise SupervisorError("/dev directory accepted an undeclared filesystem write")
    if not denied_write(Path("/proc/.mrl0808-write-probe")):
        raise SupervisorError("/proc accepted an undeclared filesystem write")
    control = {
        "allowed_artifact_names": [OBSERVATION_NAME, CONTROL_NAME],
        "challenge": observation["challenge"],
        "gpu_observation": gpu,
        "dev_directory_write_denied": True,
        "forbidden_host_data_roots_absent": True,
        "gpu_visible_inside_sandbox": True,
        "maximum_total_bytes": MAXIMUM_TOTAL_BYTES,
        "output_filesystem_type": mount_type,
        "output_mount_capacity_bytes": capacity,
        "output_root": str(OUTPUT_ROOT),
        "output_root_capacity_enforced": True,
        "proc_write_denied": True,
        "runtime_context_sha256": observation["runtime_context_sha256"],
        "runtime_support_roots_present": True,
        "schema_version": _CONTROL_SCHEMA,
        "undeclared_artifact_present": False,
    }
    control_raw = canonical_json_bytes(control)
    write_new(OUTPUT_ROOT / CONTROL_NAME, control_raw)
    payloads, total = validate_output_set()
    artifacts = []
    classes = {
        OBSERVATION_NAME: "qualification-observation",
        CONTROL_NAME: "sandbox-control-evidence",
    }
    for name in (OBSERVATION_NAME, CONTROL_NAME):
        raw = payloads[name]
        artifacts.append(
            {
                "class": classes[name],
                "document": parse_canonical_object(raw, label=name),
                "name": name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    envelope = {
        "artifacts": artifacts,
        "maximum_total_bytes": MAXIMUM_TOTAL_BYTES,
        "schema_version": _COLLECTION_SCHEMA,
        "total_bytes": total,
    }
    sys.stdout.buffer.write(canonical_json_bytes(envelope))
    return 0


def undeclared_output_challenge() -> int:
    """Prove the class validator rejects an extra undeclared output artifact."""
    write_new(OUTPUT_ROOT / OBSERVATION_NAME, b"{}\n")
    write_new(OUTPUT_ROOT / CONTROL_NAME, b"{}\n")
    write_new(OUTPUT_ROOT / "undeclared-output.bin", b"undeclared\n")
    try:
        validate_output_set()
    except SupervisorError:
        print("MRL0808_UNDECLARED_OUTPUT_BLOCKED", file=sys.stderr)
        return 43
    raise SupervisorError("undeclared output artifact was not blocked")


def output_budget_challenge() -> int:
    """Prove the output tmpfs cannot exceed the frozen byte budget."""
    target = OUTPUT_ROOT / OBSERVATION_NAME
    chunk = b"0" * (1024 * 1024)
    try:
        with target.open("xb") as stream:
            for _ in range((MAXIMUM_TOTAL_BYTES // len(chunk)) + 2):
                stream.write(chunk)
                stream.flush()
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            print("MRL0808_OUTPUT_BUDGET_BLOCKED", file=sys.stderr)
            return 42
        raise
    raise SupervisorError("output tmpfs accepted bytes beyond the frozen budget")


def main() -> int:
    """Dispatch one deterministic sandbox-control mode."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("normal", "undeclared-output", "output-budget"),
        default="normal",
    )
    args = parser.parse_args()
    if args.mode == "normal":
        return normal()
    if args.mode == "undeclared-output":
        return undeclared_output_challenge()
    return output_budget_challenge()


if __name__ == "__main__":
    raise SystemExit(main())
