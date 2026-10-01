from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_stage4_v2_repair_driver.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_stage4_v2_repair_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "repo"
    harness = root / DRIVER.HARNESS
    harness.parent.mkdir(parents=True)
    harness.write_text("# harness\n", encoding="utf-8")
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    custody = tmp_path / "custody"
    custody.mkdir()
    return root, python_executable, custody


def test_first_probe_failure_prevents_gemma_and_assemble(tmp_path: Path) -> None:
    root, python_executable, custody = _fixture(tmp_path)
    calls: list[list[str]] = []
    removed: list[Path] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        subcommand = argv[2]
        return subprocess.CompletedProcess(argv, 1 if subcommand == "probe" else 0)

    def remove_tree(path: Path, **_: object) -> None:
        removed.append(path)

    with pytest.raises(DRIVER.Stage4ExecutionError, match="probe"):
        DRIVER.run_stage4(
            repository_root=root,
            custody=custody,
            python_executable=python_executable,
            runner=runner,
            remove_tree=remove_tree,
        )

    assert [call[2] for call in calls] == ["stage", "probe"]
    assert DRIVER.QWEN in calls[0]
    assert DRIVER.QWEN in calls[1]
    assert DRIVER.GEMMA not in {item for call in calls for item in call}
    assert removed == []


def test_success_path_is_exact_and_non_retrying(tmp_path: Path) -> None:
    root, python_executable, custody = _fixture(tmp_path)
    calls: list[list[str]] = []
    removed: list[Path] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    def remove_tree(path: Path, **_: object) -> None:
        removed.append(path)

    DRIVER.run_stage4(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
        runner=runner,
        remove_tree=remove_tree,
    )

    assert [call[2] for call in calls] == ["stage", "probe", "stage", "probe", "assemble"]
    assert calls[0].count(DRIVER.QWEN) == 1
    assert calls[1].count(DRIVER.QWEN) == 1
    assert calls[2].count(DRIVER.GEMMA) == 1
    assert calls[3].count(DRIVER.GEMMA) == 1
    assert removed == [custody / "qwen-snapshot", custody / "gemma-snapshot"]


def test_cleanup_failure_stops_before_second_candidate(tmp_path: Path) -> None:
    root, python_executable, custody = _fixture(tmp_path)
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0)

    def remove_tree(path: Path, **_: object) -> None:
        raise OSError(f"cannot remove {path}")

    with pytest.raises(OSError, match="cannot remove"):
        DRIVER.run_stage4(
            repository_root=root,
            custody=custody,
            python_executable=python_executable,
            runner=runner,
            remove_tree=remove_tree,
        )

    assert [call[2] for call in calls] == ["stage", "probe"]
