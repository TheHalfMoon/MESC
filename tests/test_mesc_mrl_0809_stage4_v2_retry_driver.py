from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._mrl_0809_stage4_retry_gate_v1 import Stage4RetryAuthorityIdentity

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_stage4_v2_retry_driver.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_stage4_v2_retry_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()
REVISION = "a" * 40


def _authority() -> Stage4RetryAuthorityIdentity:
    return Stage4RetryAuthorityIdentity(
        authorization_sha256="b" * 64,
        decision_sha256="c" * 64,
        repair_merge_sha="d" * 40,
        repair_merge_tree="e" * 40,
    )


def test_authority_is_checked_before_retry_sequence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: calls.append("clean"))

    def validate(root_arg: Path, revision: str) -> Stage4RetryAuthorityIdentity:
        assert root_arg == root.resolve()
        assert revision == REVISION
        calls.append("authority")
        return _authority()

    def retry_sequence(**kwargs: object) -> None:
        assert kwargs["repository_root"] == root.resolve()
        assert kwargs["custody"] == custody
        assert kwargs["python_executable"] == python_executable
        calls.append("driver")

    monkeypatch.setattr(DRIVER, "validate_stage4_retry_authority", validate)
    monkeypatch.setattr(DRIVER, "_run_retry_stage4", retry_sequence)

    DRIVER.run_authorized_stage4(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
        expected_canonical_revision=REVISION,
    )

    assert calls == ["clean", "authority", "driver"]
    receipt = json.loads((custody / DRIVER._AUTHORITY_RECEIPT).read_text(encoding="utf-8"))
    assert receipt["canonical_revision"] == REVISION
    assert receipt["authorization_sha256"] == "b" * 64


def test_wrong_revision_fails_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)

    with pytest.raises(DRIVER.Stage4RetryLaunchError, match="HEAD does not match"):
        DRIVER.run_authorized_stage4(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=python_executable,
            expected_canonical_revision="f" * 40,
        )


def test_existing_custody_fails_before_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    custody.mkdir()
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: None)

    with pytest.raises(DRIVER.Stage4RetryLaunchError, match="must not already exist"):
        DRIVER.run_authorized_stage4(
            repository_root=root,
            custody=custody,
            python_executable=python_executable,
            expected_canonical_revision=REVISION,
        )


def test_python_launch_path_preserves_venv_symlink(tmp_path: Path) -> None:
    target = tmp_path / "base-python"
    target.write_text("", encoding="utf-8")
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python_link = venv_bin / "python"
    try:
        python_link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    launch_path = DRIVER._python_launch_path(python_link)

    assert launch_path == python_link.absolute()
    assert launch_path != python_link.resolve()


def test_retry_sequence_uses_venv_symlink_and_stops_before_gemma(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    harness = root / DRIVER.HARNESS
    harness.parent.mkdir(parents=True)
    harness.write_text("# harness\n", encoding="utf-8")
    target = tmp_path / "base-python"
    target.write_text("", encoding="utf-8")
    venv_bin = tmp_path / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    python_link = venv_bin / "python"
    try:
        python_link.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    custody = tmp_path / "custody"
    calls: list[list[str]] = []

    def runner(argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 1 if argv[2] == "probe" else 0)

    with pytest.raises(RuntimeError, match="execution stopped without retry"):
        DRIVER._run_retry_stage4(
            repository_root=root,
            custody=custody,
            python_executable=python_link,
            runner=runner,
            remove_tree=lambda *_args, **_kwargs: None,
        )

    assert [call[2] for call in calls] == ["stage", "probe"]
    assert calls[0][0] == str(python_link.absolute())
    assert calls[0][0] != str(python_link.resolve())
    assert DRIVER.QWEN in calls[0]
    assert DRIVER.GEMMA not in {item for call in calls for item in call}
