#!/usr/bin/env python3
"""Versioned MRL-0809 successor BMM portability repair harness.

Repository inclusion is repair work only. It does not authorize another hosted
Stage-4 attempt. The preserved repair-1 harness remains byte-identical.
"""

from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Final

import mesc_mrl_0809_runtime_feasibility_v2_repair as repair_module

BASE: Any = repair_module.BASE
BMM_HARNESS: Final = Path("scripts/mesc_mrl_0809_runtime_feasibility_v2_bmm_repair.py")
BMM_WORKER: Final = Path("scripts/mesc_mrl_0809_runtime_worker_v2_bmm_repair.py")
BMM_PREFLIGHT: Final = Path("scripts/mesc_mrl_0809_bmm_portability_preflight_v1.py")
BMM_GATE_MODULE: Final = "medscale.mesc._mrl_0809_successor_gate_v2_bmm_repair_1"
PREFLIGHT_SCHEMA: Final = "MESC-MRL-0809-BMM-PORTABILITY-PREFLIGHT-V1"


def _install_bmm_repair() -> None:
    repair_module.__dict__["REPAIR_WORKER"] = BMM_WORKER
    BASE.HARNESS = BMM_HARNESS

    def require_repository(root: Path) -> tuple[str, str]:
        head, tree = repair_module._require_repository_repaired(root)
        source_root = str((root.resolve(strict=True) / "src").resolve(strict=True))
        if source_root not in sys.path:
            sys.path.insert(0, source_root)
        gate: Any = importlib.import_module(BMM_GATE_MODULE)
        try:
            gate.validate_bmm_repair_static_prerequisites(root, head)
        except gate.MRL0809BMMRepairGateError as exc:
            raise BASE.HarnessError("BMM repair static prerequisite gate failed closed") from exc
        return head, tree

    BASE._require_repository = require_repository


def _compat_preflight(*, root: Path, python_executable: Path, receipt_out: Path) -> None:
    _install_bmm_repair()
    root = root.resolve(strict=True)
    BASE._require_repository(root)
    python_path = python_executable.absolute()
    if not python_path.is_file():
        raise BASE.HarnessError("BMM preflight Python executable is missing")
    bwrap_raw = shutil.which("bwrap")
    if bwrap_raw is None:
        raise BASE.HarnessError("bubblewrap is required before BMM preflight")
    bwrap = Path(bwrap_raw).resolve(strict=True)
    BASE._require_cuda_sandbox_support()
    base_prefix, site_packages, python_version = BASE._python_layout(python_path)
    BASE._package_versions()
    nodes = BASE._nvidia_nodes()
    preflight_source = (root / BMM_PREFLIGHT).resolve(strict=True)
    python_binary = f"/mesc-run/python-base/bin/python{'.'.join(python_version.split('.')[:2])}"

    with tempfile.TemporaryDirectory(prefix="mesc-mrl0809-bmm-empty-") as empty_raw:
        prefix = BASE._sandbox_prefix(
            bwrap=bwrap,
            harness=preflight_source,
            snapshot=Path(empty_raw),
            base_prefix=base_prefix,
            site_packages=site_packages,
            nvidia_nodes=nodes,
        )
        command = prefix.copy()
        environment = {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HOME": "/tmp/hf",
            "XDG_CACHE_HOME": "/tmp",
            "PYTHONPATH": "/mesc-run/site-packages",
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
            command.extend(
                ["--seccomp", str(seccomp.fileno()), python_binary, "/mesc-run/harness.py"]
            )
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                pass_fds=(seccomp.fileno(),),
            )
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")[-6000:]
        raise BASE.HarnessError(f"isolated BMM portability preflight failed: {stderr}")
    document = BASE.parse_canonical_object(completed.stdout, label="BMM portability preflight")
    expected = {
        "bmm_result_verified": True,
        "cuda_device_count": 1,
        "disabled_op_symbols": ["bmm"],
        "schema_version": PREFLIGHT_SCHEMA,
        "torch_version": "2.13.0",
    }
    if document != expected:
        raise BASE.HarnessError("BMM portability preflight receipt drifted")
    BASE.write_new(receipt_out, completed.stdout)


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "compat-preflight":
        parser = argparse.ArgumentParser()
        parser.add_argument("command", choices=("compat-preflight",))
        parser.add_argument("--repository-root", type=Path, required=True)
        parser.add_argument("--python-executable", type=Path, required=True)
        parser.add_argument("--receipt-out", type=Path, required=True)
        args = parser.parse_args()
        _compat_preflight(
            root=args.repository_root,
            python_executable=args.python_executable,
            receipt_out=args.receipt_out,
        )
        return
    _install_bmm_repair()
    repair_module.main()


if __name__ == "__main__":
    main()
