#!/usr/bin/env python3
"""Versioned MRL-0809 successor repair harness.

This wrapper preserves the consumed v2 harness bytes and delegates the existing
stage/observation/receipt logic to that historical module while replacing only
the isolated worker launch. The repaired worker is separately manifest-bound.
"""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Final

BASE_HARNESS: Final = Path("scripts/mesc_mrl_0809_runtime_feasibility_v2.py")
BASE_HARNESS_SHA256: Final = (
    "1516f2eb2b269a2a63db21413e365e2b1b39fc53fd012a94767bca7e1ae65579"
)
REPAIR_HARNESS: Final = Path(
    "scripts/mesc_mrl_0809_runtime_feasibility_v2_repair.py"
)
REPAIR_WORKER: Final = Path(
    "scripts/mesc_mrl_0809_runtime_worker_v2_repair.py"
)
PLACEMENT_AUDIT: Final = Path(
    "src/medscale/mesc/_mrl_0809_device_placement_audit_v1.py"
)
REPAIR_STATIC_MANIFEST: Final = Path(
    "specs/mesc-experiment-0/mrl-0809-static-prerequisites-v2-repair-1.json"
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_base() -> ModuleType:
    root = Path(__file__).resolve().parents[1]
    base_path = root / BASE_HARNESS
    if _sha256_file(base_path) != BASE_HARNESS_SHA256:
        raise RuntimeError("historical v2 harness bytes drifted")
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_runtime_feasibility_v2_preserved",
        base_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load preserved v2 harness")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


BASE = _load_base()
BASE.HARNESS = REPAIR_HARNESS
BASE.STATIC_MANIFEST = REPAIR_STATIC_MANIFEST


def _run_worker_repaired(
    *,
    candidate: str,
    prefix: list[str],
    python_version: str,
) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    worker_source = (root / REPAIR_WORKER).resolve(strict=True)
    placement_source = (root / PLACEMENT_AUDIT).resolve(strict=True)
    python_binary = (
        f"/mesc-run/python-base/bin/python{'.'.join(python_version.split('.')[:2])}"
    )
    command = prefix.copy()
    command.extend(
        [
            "--ro-bind",
            str(worker_source),
            "/mesc-run/worker.py",
            "--ro-bind",
            str(placement_source),
            "/mesc-run/placement_audit.py",
        ]
    )
    environment = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HOME": "/tmp/hf",
        "XDG_CACHE_HOME": "/tmp",
        "PYTHONPATH": "/mesc-run:/mesc-run/site-packages",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LD_LIBRARY_PATH": BASE.CUDA_DRIVER_LIBRARY_PATH,
        "NVIDIA_VISIBLE_DEVICES": BASE.NVIDIA_VISIBLE_DEVICES_VALUE,
        "NVIDIA_DRIVER_CAPABILITIES": BASE.NVIDIA_DRIVER_CAPABILITIES_VALUE,
    }
    for key, value in environment.items():
        command.extend(["--setenv", key, value])

    with tempfile.TemporaryFile(mode="w+b") as seccomp:
        seccomp.write(BASE._host_process_seccomp_program())
        seccomp.flush()
        seccomp.seek(0)
        command.extend(["--seccomp", str(seccomp.fileno())])
        command.extend(
            [
                python_binary,
                "/mesc-run/worker.py",
                "--candidate",
                candidate,
                "--snapshot",
                "/mesc-run/model-weights",
            ]
        )
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            pass_fds=(seccomp.fileno(),),
        )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")[-6000:]
        raise BASE.HarnessError(f"isolated candidate probe failed: {stderr}")
    return BASE.parse_canonical_object(
        completed.stdout,
        label="isolated repaired worker observation",
    )


def _direct_worker_forbidden(candidate: str, snapshot: Path) -> None:
    del candidate, snapshot
    raise BASE.HarnessError(
        "direct repair-harness _worker execution is prohibited; "
        "the worker must be launched through the repaired sandbox path"
    )


BASE._run_worker = _run_worker_repaired
BASE._worker = _direct_worker_forbidden


def main() -> None:
    BASE.main()


if __name__ == "__main__":
    main()
