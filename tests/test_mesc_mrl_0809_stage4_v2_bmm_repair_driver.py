from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_stage4_v2_bmm_repair_driver.py"
)


def _load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_stage4_v2_bmm_repair_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()


def test_compat_preflight_is_first_and_fail_stops_before_stage(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    harness = root / DRIVER.HARNESS
    harness.parent.mkdir(parents=True)
    harness.write_text("# harness\n", encoding="utf-8")
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1)

    with pytest.raises(RuntimeError, match="execution stopped without retry"):
        DRIVER.run_stage4(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=python_executable,
            runner=runner,
        )

    assert len(calls) == 1
    assert calls[0][2] == "compat-preflight"


def test_successful_preflight_precedes_qwen_stage(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    harness = root / DRIVER.HARNESS
    harness.parent.mkdir(parents=True)
    harness.write_text("# harness\n", encoding="utf-8")
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1 if len(calls) == 2 else 0)

    with pytest.raises(RuntimeError, match="execution stopped without retry"):
        DRIVER.run_stage4(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=python_executable,
            runner=runner,
        )

    assert [call[2] for call in calls] == ["compat-preflight", "stage"]
    assert DRIVER.QWEN in calls[1]
