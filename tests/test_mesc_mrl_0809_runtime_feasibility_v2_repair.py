from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0809_runtime_feasibility_v2_repair.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_runtime_feasibility_v2_repair_test",
        SCRIPT,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


REPAIR = _load()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preserved_v2_harness_is_sha_bound() -> None:
    assert _sha(ROOT / REPAIR.BASE_HARNESS) == REPAIR.BASE_HARNESS_SHA256
    assert REPAIR.BASE.HARNESS == REPAIR.REPAIR_HARNESS
    assert REPAIR.BASE.STATIC_MANIFEST == REPAIR.REPAIR_STATIC_MANIFEST


def test_repaired_worker_launch_mounts_worker_and_placement_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    payload = REPAIR.BASE.canonical_json_bytes({"ok": True})

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(argv, 0, stdout=payload, stderr=b"")

    monkeypatch.setattr(REPAIR.subprocess, "run", fake_run)
    monkeypatch.setattr(REPAIR.BASE, "_host_process_seccomp_program", lambda: b"seccomp")

    result = REPAIR._run_worker_repaired(
        candidate="Qwen/Qwen3-8B",
        prefix=["bwrap", "--chdir", "/mesc-run"],
        python_version="3.11.16",
    )

    assert result == {"ok": True}
    argv = captured["argv"]
    assert isinstance(argv, list)
    worker = str((ROOT / REPAIR.REPAIR_WORKER).resolve())
    placement = str((ROOT / REPAIR.PLACEMENT_AUDIT).resolve())
    assert [worker, "/mesc-run/worker.py"] == argv[
        argv.index(worker) : argv.index(worker) + 2
    ]
    assert [placement, "/mesc-run/placement_audit.py"] == argv[
        argv.index(placement) : argv.index(placement) + 2
    ]
    assert "PYTHONPATH" in argv
    assert "/mesc-run:/mesc-run/site-packages" in argv
    assert argv[-6:] == [
        "/mesc-run/python-base/bin/python3.11",
        "/mesc-run/worker.py",
        "--candidate",
        "Qwen/Qwen3-8B",
        "--snapshot",
        "/mesc-run/model-weights",
    ]


def test_direct_worker_entrypoint_is_forbidden() -> None:
    with pytest.raises(REPAIR.BASE.HarnessError, match="direct repair-harness"):
        REPAIR._direct_worker_forbidden("Qwen/Qwen3-8B", Path("snapshot"))
