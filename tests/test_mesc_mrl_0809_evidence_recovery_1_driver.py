from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._mrl_0809_evidence_recovery_1_gate_v1 import (
    EvidenceRecovery1AuthorityIdentity,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_evidence_recovery_1_driver.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_evidence_recovery_1_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()
REVISION = "a" * 40
TREE = "b" * 40


def _authority() -> EvidenceRecovery1AuthorityIdentity:
    return EvidenceRecovery1AuthorityIdentity(
        authorization_sha256="c" * 64,
        decision_sha256="d" * 64,
        static_manifest_sha256="e" * 64,
        predecessor_result_sha256="f" * 64,
        predecessor_merge_sha="1" * 40,
        predecessor_merge_tree="2" * 40,
    )


def _patch_prelaunch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_tree", lambda _root: TREE)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: None)
    monkeypatch.setattr(DRIVER, "_require_canonical_main", lambda _root, _revision: None)
    monkeypatch.setattr(DRIVER, "_require_predecessor", lambda _root: None)
    monkeypatch.setattr(DRIVER, "_require_recovery_unconsumed", lambda _root: None)
    monkeypatch.setattr(DRIVER, "validate_evidence_recovery_1_authority", lambda *_: _authority())


def _populate_runtime_artifacts(custody: Path) -> None:
    for name in DRIVER._REQUIRED_BUNDLE_FILES:
        path = custody / name
        if path.exists():
            continue
        path.write_bytes((f"artifact:{name}\n").encode())


def test_recovery_consumes_launch_before_runtime_and_emits_full_byte_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    calls: list[str] = []
    _patch_prelaunch(monkeypatch)

    def runtime(**kwargs: object) -> None:
        assert kwargs["repository_root"] == root.resolve()
        assert kwargs["custody"] == custody
        assert kwargs["python_executable"] == python_executable
        assert (custody / DRIVER._AUTHORITY_RECEIPT).is_file()
        assert (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).is_file()
        calls.append("runtime")
        _populate_runtime_artifacts(custody)

    monkeypatch.setattr(DRIVER, "_run_bmm_stage4", runtime)
    bundle_raw = DRIVER.run_authorized_evidence_recovery_1(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
        expected_canonical_revision=REVISION,
    )

    assert calls == ["runtime"]
    assert (custody / DRIVER._BUNDLE).read_bytes() == bundle_raw
    bundle = json.loads(bundle_raw)
    assert bundle["schema_version"] == DRIVER._BUNDLE_SCHEMA
    assert bundle["canonical_revision"] == REVISION
    assert bundle["canonical_tree"] == TREE
    rows = bundle["artifacts"]
    assert [row["path"] for row in rows] == list(DRIVER._REQUIRED_BUNDLE_FILES)
    for row in rows:
        raw = base64.b64decode(row["base64"], validate=True)
        assert raw == (custody / row["path"]).read_bytes()
        assert row["byte_count"] == len(raw)

    output = capsys.readouterr().out.strip()
    assert output.startswith(DRIVER._BUNDLE_STDOUT_PREFIX)
    stdout_bundle = base64.b64decode(
        output.removeprefix(DRIVER._BUNDLE_STDOUT_PREFIX), validate=True
    )
    assert stdout_bundle == bundle_raw

    consumption = json.loads(
        (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).read_text(encoding="utf-8")
    )
    assert consumption["launch_authorization_consumed"] is True
    assert consumption["automatic_retry_authorized"] is False
    assert consumption["automatic_relaunch_authorized"] is False
    assert consumption["purpose"] == "EVIDENCE_RECOVERY_ONLY"


def test_missing_runtime_artifact_fails_after_launch_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    _patch_prelaunch(monkeypatch)

    def runtime(**kwargs: object) -> None:
        target = kwargs["custody"]
        assert isinstance(target, Path)
        _populate_runtime_artifacts(target)
        (target / "gemma-observation.json").unlink()

    monkeypatch.setattr(DRIVER, "_run_bmm_stage4", runtime)
    with pytest.raises(DRIVER.EvidenceRecovery1LaunchError, match=r"gemma-observation\.json"):
        DRIVER.run_authorized_evidence_recovery_1(
            repository_root=root,
            custody=custody,
            python_executable=python_executable,
            expected_canonical_revision=REVISION,
        )

    assert (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).is_file()
    assert not (custody / DRIVER._BUNDLE).exists()


def test_wrong_revision_fails_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    with pytest.raises(DRIVER.EvidenceRecovery1LaunchError, match="HEAD does not match"):
        DRIVER.run_authorized_evidence_recovery_1(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=tmp_path / "python",
            expected_canonical_revision="0" * 40,
        )


def test_existing_recovery_record_blocks_relaunch(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    consumed = root / DRIVER._CONSUMED_RECORDS[1]
    consumed.parent.mkdir(parents=True)
    consumed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(DRIVER.EvidenceRecovery1LaunchError, match="already consumed"):
        DRIVER._require_recovery_unconsumed(root)


def test_missing_predecessor_blocks_recovery(tmp_path: Path) -> None:
    with pytest.raises(DRIVER.EvidenceRecovery1LaunchError, match="Retry-2 outcome"):
        DRIVER._require_predecessor(tmp_path)


def test_existing_custody_fails_before_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    custody.mkdir()
    _patch_prelaunch(monkeypatch)
    with pytest.raises(DRIVER.EvidenceRecovery1LaunchError, match="must not already exist"):
        DRIVER.run_authorized_evidence_recovery_1(
            repository_root=root,
            custody=custody,
            python_executable=tmp_path / "python",
            expected_canonical_revision=REVISION,
        )
