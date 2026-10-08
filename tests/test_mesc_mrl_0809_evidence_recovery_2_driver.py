from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._mrl_0809_evidence_recovery_2_gate_v1 import (
    EvidenceRecovery2AuthorityIdentity,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/mesc_mrl_0809_evidence_recovery_2_driver.py"


def _load() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_evidence_recovery_2_driver_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


DRIVER = _load()
REVISION = "a" * 40
TREE = "b" * 40


def _authority() -> EvidenceRecovery2AuthorityIdentity:
    return EvidenceRecovery2AuthorityIdentity(
        authorization_sha256="c" * 64,
        decision_sha256="d" * 64,
        static_manifest_sha256="e" * 64,
        predecessor_failure_sha256="f" * 64,
        predecessor_merge_sha="1" * 40,
        predecessor_merge_tree="2" * 40,
    )


def _patch_prelaunch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_tree", lambda _root: TREE)
    monkeypatch.setattr(DRIVER, "_require_clean", lambda _root: None)
    monkeypatch.setattr(DRIVER, "_live_origin_main", lambda _root: REVISION)
    monkeypatch.setattr(DRIVER, "_require_predecessor", lambda _root: None)
    monkeypatch.setattr(DRIVER, "_require_unconsumed", lambda _root: None)
    monkeypatch.setattr(DRIVER, "validate_evidence_recovery_2_authority", lambda *_: _authority())


def _populate_runtime_artifacts(custody: Path) -> None:
    for name in DRIVER._REQUIRED_BUNDLE_FILES:
        path = custody / name
        if path.exists():
            continue
        path.write_bytes(f"artifact:{name}\n".encode())


def test_success_is_held_until_host_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    python_executable = tmp_path / "python"
    python_executable.write_text("", encoding="utf-8")
    _patch_prelaunch(monkeypatch)
    calls: list[str] = []

    def runtime(**kwargs: object) -> None:
        target = kwargs["custody"]
        assert isinstance(target, Path)
        calls.append("runtime")
        _populate_runtime_artifacts(target)

    def hold(
        target: Path,
        *,
        bundle: bytes,
        timeout_seconds: float,
        poll_seconds: float,
    ) -> None:
        assert target == custody
        assert timeout_seconds == 1800.0
        assert poll_seconds == 1.0
        assert (custody / DRIVER._BUNDLE).read_bytes() == bundle
        ready = json.loads((custody / DRIVER._READY).read_text(encoding="utf-8"))
        assert ready["bundle_sha256"]
        calls.append("host-ack")

    monkeypatch.setattr(DRIVER, "_run_bmm_stage4", runtime)
    monkeypatch.setattr(DRIVER, "_wait_for_host_ack", hold)

    bundle = DRIVER.run_authorized_evidence_recovery_2(
        repository_root=root,
        custody=custody,
        python_executable=python_executable,
        expected_canonical_revision=REVISION,
    )

    assert calls == ["runtime", "host-ack"]
    assert (custody / DRIVER._BUNDLE).read_bytes() == bundle
    assert (custody / DRIVER._READY).is_file()
    assert (custody / DRIVER._LAUNCH_CONSUMPTION_RECEIPT).is_file()


def test_missing_ack_fails_closed_after_runtime_pass(
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

    monkeypatch.setattr(DRIVER, "_run_bmm_stage4", runtime)
    with pytest.raises(DRIVER.EvidenceRecovery2LaunchError, match="host copy-out acknowledgement"):
        DRIVER.run_authorized_evidence_recovery_2(
            repository_root=root,
            custody=custody,
            python_executable=python_executable,
            expected_canonical_revision=REVISION,
            ack_timeout_seconds=0.0,
        )

    assert (custody / DRIVER._BUNDLE).is_file()
    assert (custody / DRIVER._READY).is_file()


def test_ack_must_bind_bundle_and_verified_local_manifest(tmp_path: Path) -> None:
    custody = tmp_path / "custody"
    custody.mkdir()
    bundle = b'{"schema_version":"synthetic"}\n'
    ack = {
        "bundle_byte_count": len(bundle),
        "bundle_sha256": "0" * 64,
        "complete_local_evidence_verified": True,
        "local_manifest_sha256": "1" * 64,
        "schema_version": DRIVER._ACK_SCHEMA,
    }
    (custody / DRIVER._HOST_ACK).write_bytes(DRIVER._canonical_json_bytes(ack))
    with pytest.raises(DRIVER.EvidenceRecovery2LaunchError, match="bundle hash mismatch"):
        DRIVER._wait_for_host_ack(
            custody,
            bundle=bundle,
            timeout_seconds=0.1,
            poll_seconds=0.01,
        )


def test_partial_ack_is_retried_until_complete_and_verified(tmp_path: Path) -> None:
    custody = tmp_path / "custody"
    custody.mkdir()
    bundle = b'{"schema_version":"synthetic"}\n'
    ack_path = custody / DRIVER._HOST_ACK
    ack_path.write_bytes(b'{"incomplete":')
    valid_ack = DRIVER._canonical_json_bytes(
        {
            "bundle_byte_count": len(bundle),
            "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
            "complete_local_evidence_verified": True,
            "local_manifest_sha256": "1" * 64,
            "schema_version": DRIVER._ACK_SCHEMA,
        }
    )

    def complete_upload() -> None:
        time.sleep(0.04)
        ack_path.write_bytes(valid_ack)

    thread = threading.Thread(target=complete_upload)
    thread.start()
    try:
        DRIVER._wait_for_host_ack(custody, bundle=bundle, timeout_seconds=1.0, poll_seconds=0.01)
    finally:
        thread.join(timeout=2.0)
    assert not thread.is_alive()


def test_permanently_partial_ack_never_returns_success(tmp_path: Path) -> None:
    custody = tmp_path / "custody"
    custody.mkdir()
    (custody / DRIVER._HOST_ACK).write_bytes(b'{"incomplete":')
    with pytest.raises(DRIVER.EvidenceRecovery2LaunchError, match="timed out"):
        DRIVER._wait_for_host_ack(
            custody, bundle=b"synthetic", timeout_seconds=0.05, poll_seconds=0.01
        )


def test_existing_recovery_2_record_blocks_relaunch(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    consumed = root / DRIVER._CONSUMED_RECORDS[0]
    consumed.parent.mkdir(parents=True)
    consumed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(DRIVER.EvidenceRecovery2LaunchError, match="already consumed"):
        DRIVER._require_unconsumed(root)


def test_wrong_revision_fails_before_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setattr(DRIVER, "_head", lambda _root: REVISION)
    with pytest.raises(DRIVER.EvidenceRecovery2LaunchError, match="HEAD does not match"):
        DRIVER.run_authorized_evidence_recovery_2(
            repository_root=root,
            custody=tmp_path / "custody",
            python_executable=tmp_path / "python",
            expected_canonical_revision="0" * 40,
        )
