from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import threading
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


def _write_valid_host_receipt(
    evidence: Path,
    *,
    session_name: str = "mesc-evidence-recovery-2",
    revision: str = "a" * 40,
) -> None:
    (evidence / HOST._HOST_LAUNCH_RECEIPT).write_bytes(
        HOST._canonical_json_bytes(
            {
                "authorization_sha256": "c" * 64,
                "automatic_relaunch_authorized": False,
                "automatic_retry_authorized": False,
                "canonical_revision": revision,
                "canonical_tree": "b" * 40,
                "decision_sha256": "d" * 64,
                "gpu_class": "STANDARD_T4",
                "launch_authorization_consumed": True,
                "monetary_cost_microunits": 0,
                "provider_class": "GOOGLE_COLAB_FREE",
                "purpose": "EVIDENCE_RECOVERY_ONLY",
                "schema_version": ("MESC-MRL-0809-EVIDENCE-RECOVERY-2-HOST-LAUNCH-CONSUMPTION-V1"),
                "session_name": session_name,
            }
        )
    )


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


def _remote_fixture(*, authority_override: tuple[str, str] | None = None) -> dict[str, bytes]:
    payloads: dict[str, bytes] = {}
    individual = set(HOST._REQUIRED_REMOTE_FILES) - {HOST._REMOTE_BUNDLE, HOST._REMOTE_READY}
    for name in sorted(individual):
        payloads[name] = f"artifact:{name}\n".encode()
    authority = {
        "authorization_sha256": "c" * 64,
        "decision_sha256": "d" * 64,
        "canonical_revision": "a" * 40,
        "canonical_tree": "b" * 40,
        "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-2-AUTHORITY-RECEIPT-V1",
    }
    if authority_override is not None:
        field, value = authority_override
        authority[field] = value
    payloads[HOST._REMOTE_AUTHORITY] = HOST._canonical_json_bytes(authority)
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
    _write_valid_host_receipt(evidence)
    remote = _remote_fixture()
    upload_attempts = 0
    upload_confirmed = threading.Event()

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
        nonlocal upload_attempts
        if "upload" in args:
            upload_attempts += 1
            ack_path = Path(args[-2])
            assert ack_path.is_file()
            ack = json.loads(ack_path.read_text(encoding="utf-8"))
            assert ack["complete_local_evidence_verified"] is True
            assert (evidence / HOST._LOCAL_MANIFEST).is_file()
            if upload_attempts == 1:
                return _completed(args, returncode=1)
            upload_confirmed.set()
        if "exec" in args and not upload_confirmed.wait(timeout=5.0):
            return _completed(args, returncode=1)
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

    assert upload_attempts == 2
    assert all((evidence / name).is_file() for name in HOST._REQUIRED_REMOTE_FILES)
    manifest = json.loads((evidence / HOST._LOCAL_MANIFEST).read_text(encoding="utf-8"))
    assert manifest["complete_local_evidence_verified"] is True


def test_failed_remote_driver_drains_last_evidence_without_ack(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    _write_valid_host_receipt(evidence)
    last_artifact = "runtime-feasibility-v2-bmm-repair-1.json"
    retained = b"last-runtime-evidence-after-final-poll\n"
    forced: list[str] = []

    def download(**kwargs: object) -> bool:
        if kwargs.get("force") is not True:
            return False
        name = kwargs["name"]
        local_dir = kwargs["local_dir"]
        assert isinstance(name, str)
        assert isinstance(local_dir, Path)
        forced.append(name)
        if name == last_artifact:
            (local_dir / name).write_bytes(retained)
            return True
        return False

    def run(args: tuple[str, ...]) -> object:
        assert "exec" in args
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)

    with pytest.raises(HOST.EvidenceRecovery2HostError, match="remote Recovery-2 driver failed"):
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

    assert set(forced) == set(HOST._REQUIRED_REMOTE_FILES)
    assert (evidence / last_artifact).read_bytes() == retained
    assert not (evidence / HOST._LOCAL_MANIFEST).exists()
    assert not (evidence / HOST._REMOTE_ACK).exists()


def test_force_refresh_replaces_early_partial_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    target = evidence / "gemma-observation.json"
    target.write_bytes(b"partial")

    def run(args: tuple[str, ...]) -> object:
        Path(args[-1]).write_bytes(b"complete-evidence")
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    assert HOST._download_once(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-2",
        remote_custody="/content/custody",
        local_dir=evidence,
        name="gemma-observation.json",
        force=True,
    )
    assert target.read_bytes() == b"complete-evidence"


def test_run_rejects_host_receipt_for_different_session(tmp_path: Path) -> None:
    _write_valid_host_receipt(tmp_path, session_name="different-session")
    with pytest.raises(HOST.EvidenceRecovery2HostError, match="session_name"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-2",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )


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


@pytest.mark.parametrize(
    ("source", "field", "value", "error"),
    [
        ("bundle", "canonical_revision", "f" * 40, "canonical identity mismatch"),
        ("bundle", "canonical_tree", "f" * 40, "canonical identity mismatch"),
        ("bundle", "purpose", "UNAUTHORIZED", "bundle purpose drifted"),
        ("ready", "bundle_path", "other.json", "bundle path mismatch"),
        ("ready", "required_artifact_count", 0, "artifact count mismatch"),
    ],
)
def test_remote_metadata_tampering_prevents_ack(
    tmp_path: Path,
    source: str,
    field: str,
    value: str | int,
    error: str,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    _write_valid_host_receipt(evidence)
    remote = _remote_fixture()
    name = HOST._REMOTE_BUNDLE if source == "bundle" else HOST._REMOTE_READY
    document = json.loads(remote[name].decode("utf-8"))
    document[field] = value
    remote[name] = HOST._canonical_json_bytes(document)
    if source == "bundle":
        ready = json.loads(remote[HOST._REMOTE_READY].decode("utf-8"))
        ready["bundle_sha256"] = hashlib.sha256(remote[name]).hexdigest()
        ready["bundle_byte_count"] = len(remote[name])
        remote[HOST._REMOTE_READY] = HOST._canonical_json_bytes(ready)
    for artifact, raw in remote.items():
        (evidence / artifact).write_bytes(raw)
    with pytest.raises(HOST.EvidenceRecovery2HostError, match=error):
        HOST._verify_bundle_and_build_manifest(evidence)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("authorization_sha256", "f" * 64),
        ("decision_sha256", "f" * 64),
        ("canonical_revision", "f" * 40),
        ("canonical_tree", "f" * 40),
        ("schema_version", "UNAUTHORIZED"),
    ],
)
def test_remote_authority_drift_prevents_ack(tmp_path: Path, field: str, value: str) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    _write_valid_host_receipt(evidence)
    remote = _remote_fixture(authority_override=(field, value))
    for name, raw in remote.items():
        (evidence / name).write_bytes(raw)
    error = "schema drifted" if field == "schema_version" else f"mismatch: {field}"
    with pytest.raises(HOST.EvidenceRecovery2HostError, match=error):
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
