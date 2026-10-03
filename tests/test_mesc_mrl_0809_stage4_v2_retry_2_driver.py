from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._mrl_0809_stage4_retry_2_gate_v1 import Stage4Retry2AuthorityIdentity

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_stage4_v2_retry_2_driver.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_stage4_v2_retry_2_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()
REVISION = "a" * 40


def _authority() -> Stage4Retry2AuthorityIdentity:
    return Stage4Retry2AuthorityIdentity(
        authorization_sha256="b" * 64,
        decision_sha256="c" * 64,
        static_manifest_sha256="d" * 64,
        bmm_repair_merge_sha="e" * 40,
        bmm_repair_merge_tree="f" * 40,
    )


def test_launch_consumption_receipt_is_written_before_bmm_sequence(
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

    def validate(root_arg: Path, revision: str) -> Stage4Retry2AuthorityIdentity:
        assert root_arg == root.resolve()
        assert revision == REVISION
        calls.append("authority")
        return _authority()

    def runtime(**kwargs: object) -> None:
        assert kwargs["repository_root"] == root.resolve()
        assert kwargs["custody"] == custody
        assert kwargs["python_executable"] == python_executable
        assert (custody / DRIVER._AUTHORITY_RECEIPT).is_file()
        assert (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).is_file()
        calls.append("runtime")

    monkeypatch.setattr(DRIVER, "validate_stage4_retry_2_authority", validate)
    monkeypatch.setattr(DRIVER, "_run_bmm_stage4", runtime)

    DRIVER.run_authorized_stage4_retry_2(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
        expected_canonical_revision=REVISION,
    )

    assert calls == ["clean", "authority", "runtime"]
    receipt = json.loads(
        (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).read_text(encoding="utf-8")
    )
    assert receipt["launch_authorization_consumed"] is True
    assert receipt["automatic_relaunch_authorized"] is False
    assert receipt["preflight_failure_exhausts_launch"] is True


def test_wrong_revision_fails_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)

    with pytest.raises(DRIVER.Stage4Retry2LaunchError, match="HEAD does not match"):
        DRIVER.run_authorized_stage4_retry_2(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=tmp_path / "python",
            expected_canonical_revision="0" * 40,
        )


def test_existing_retry_2_record_blocks_relaunch_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    consumed = root / DRIVER._CONSUMED_RECORDS[0]
    consumed.parent.mkdir(parents=True)
    consumed.write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: calls.append("clean"))
    monkeypatch.setattr(
        DRIVER,
        "validate_stage4_retry_2_authority",
        lambda *_args, **_kwargs: calls.append("authority"),
    )

    with pytest.raises(DRIVER.Stage4Retry2LaunchError, match="already consumed"):
        DRIVER.run_authorized_stage4_retry_2(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=tmp_path / "python",
            expected_canonical_revision=REVISION,
        )

    assert calls == ["clean"]


def test_existing_custody_fails_before_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    custody.mkdir()

    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: None)
    monkeypatch.setattr(DRIVER, "validate_stage4_retry_2_authority", lambda *_: _authority())

    with pytest.raises(DRIVER.Stage4Retry2LaunchError, match="must not already exist"):
        DRIVER.run_authorized_stage4_retry_2(
            repository_root=root,
            custody=custody,
            python_executable=tmp_path / "python",
            expected_canonical_revision=REVISION,
        )
