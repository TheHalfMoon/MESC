from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/mesc_mrl_0809_evidence_recovery_2_host_controller.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_evidence_recovery_2_host_controller_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HOST = _load()


def _completed(args: tuple[str, ...], returncode: int = 0) -> object:
    import subprocess

    return subprocess.CompletedProcess(args, returncode, stdout="", stderr="")


def test_allocate_persists_consumption_before_colab_new(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    seen: list[tuple[str, ...]] = []

    def run(args: tuple[str, ...]) -> object:
        receipt = evidence / HOST._HOST_LAUNCH_RECEIPT
        assert receipt.is_file()
        document = json.loads(receipt.read_text(encoding="utf-8"))
        assert document["launch_authorization_consumed"] is True
        assert document["automatic_retry_authorized"] is False
        assert document["automatic_relaunch_authorized"] is False
        seen.append(args)
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    HOST.allocate_single_t4_session(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-2",
        local_evidence_dir=evidence,
        canonical_revision="a" * 40,
        canonical_tree="b" * 40,
        authorization_sha256="c" * 64,
        decision_sha256="d" * 64,
    )
    assert seen == [("colab", "new", "--session", "mesc-evidence-recovery-2", "--gpu", "T4")]


def test_failed_allocation_remains_consumed_and_does_not_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    calls = 0

    def run(args: tuple[str, ...]) -> object:
        nonlocal calls
        calls += 1
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery2HostError, match="launch consumption"):
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-2",
            local_evidence_dir=evidence,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )
    assert calls == 1
    assert (evidence / HOST._HOST_LAUNCH_RECEIPT).is_file()


def _remote_fixture() -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    individual = set(HOST._REQUIRED_REMOTE_FILES) - {HOST._REMOTE_BUNDLE, HOST._REMOTE_READY}
    for name in sorted(individual):
        payloads[name] = f"artifact:{name}\n".encode()
    rows = [
        {
            "byte_count": len(payloads[name]),
            "path": name,
            "sha256": hashlib.sha256(payloads[name]).hexdigest(),
        }
        for name in sorted(individual)
    ]
    bundle = HOST._canonical_json_bytes(
        {
            "artifacts": rows,
            "canonical_revision": "a" * 40,
            "canonical_tree": "b" * 40,
            "purpose": "EVIDENCE_RECOVERY_ONLY",
            "schema_version": HOST._BUNDLE_SCHEMA,
        }
    )
    payloads[HOST._REMOTE_BUNDLE] = bundle
    payloads[HOST._REMOTE_READY] = HOST._canonical_json_bytes(
        {
            "bundle_byte_count": len(bundle),
            "bundle_path": HOST._REMOTE_BUNDLE,
            "bundle_sha256": hashlib.sha256(bundle).hexdigest(),
            "required_artifact_count": len(individual),
            "schema_version": HOST._READY_SCHEMA,
        }
    )
    return payloads


def test_continuous_retention_verifies_bytes_before_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / HOST._HOST_LAUNCH_RECEIPT).write_text("{}\n", encoding="utf-8")
    remote = _remote_fixture()
    uploads: list[Path] = []

    def download(**kwargs: object) -> bool:
        name = kwargs["name"]
        local_dir = kwargs["local_dir"]
        assert isinstance(name, str)
        assert isinstance(local_dir, Path)
        path = local_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(remote[name])
        return True

    def run(args: tuple[str, ...]) -> object:
        if "upload" in args:
            ack_path = Path(args[-2])
            assert ack_path.is_file()
            ack = json.loads(ack_path.read_text(encoding="utf-8"))
            assert ack["complete_local_evidence_verified"] is True
            assert (evidence / HOST._LOCAL_MANIFEST).is_file()
            uploads.append(ack_path)
        return _completed(args)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)

    HOST.run_with_continuous_retention(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-2",
        local_evidence_dir=evidence,
        remote_repository_root="/content/MESC",
        remote_custody="/content/mesc-evidence-recovery-2-custody",
        remote_python="/content/MESC/.venv/bin/python",
        expected_canonical_revision="a" * 40,
        poll_seconds=0.01,
    )

    assert len(uploads) == 1
    assert all((evidence / name).is_file() for name in HOST._REQUIRED_REMOTE_FILES)
    manifest = json.loads((evidence / HOST._LOCAL_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["complete_local_evidence_verified"] is True


def test_corrupted_local_artifact_prevents_ack(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / HOST._HOST_LAUNCH_RECEIPT).write_text("{}\n", encoding="utf-8")
    remote = _remote_fixture()
    for name, raw in remote.items():
        (evidence / name).write_bytes(raw)
    target = evidence / "gemma-observation.json"
    target.write_bytes(b"corrupted\n")
    with pytest.raises(HOST.EvidenceRecovery2HostError, match="local evidence mismatch"):
        HOST._verify_bundle_and_build_manifest(evidence)


def test_run_requires_host_launch_consumption(tmp_path: Path) -> None:
    with pytest.raises(HOST.EvidenceRecovery2HostError, match="launch-consumption"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-2",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )
