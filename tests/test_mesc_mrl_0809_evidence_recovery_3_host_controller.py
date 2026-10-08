from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/mesc_mrl_0809_evidence_recovery_3_host_controller.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_evidence_recovery_3_host_controller_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HOST = _load()


@pytest.fixture(autouse=True)
def _mock_effective_authority_for_synthetic_host_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Real launch authority is NOT_EFFECTIVE; tests never touch a provider.
    monkeypatch.setattr(HOST, "require_recovery_3_launch_effectiveness", lambda *_: None)


def _write_control_plane(evidence: Path, *, phase: str) -> None:
    evidence.mkdir(parents=True, exist_ok=True)
    active = phase == "AFTER_ALLOCATION"
    document = {
        "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-CONTROL-PLANE-V1",
        "phase": phase,
        "provider_class": "GOOGLE_COLAB_FREE",
        "paid_compute_units_balance": 0.0,
        "nominal_rate_hourly": 1.07 if active else 0.0,
        "account_assignments": int(active),
        "server_assignments": int(active),
        "session": {
            "name": "mesc-evidence-recovery-3",
            "accelerator": "T4",
            "variant": "GPU",
            "machine_shape": "STANDARD",
        }
        if active
        else None,
    }
    name = HOST._AFTER_CONTROL_PLANE if active else HOST._BEFORE_CONTROL_PLANE
    (evidence / name).write_bytes(HOST._canonical_json_bytes(document))


def _completed(args: tuple[str, ...], returncode: int = 0) -> object:
    import subprocess

    return subprocess.CompletedProcess(args, returncode, stdout="", stderr="")


def _write_valid_host_receipt(
    evidence: Path,
    *,
    session_name: str = "mesc-evidence-recovery-3",
    revision: str = "a" * 40,
) -> None:
    _write_control_plane(evidence, phase="AFTER_ALLOCATION")
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
                "schema_version": ("MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-LAUNCH-CONSUMPTION-V1"),
                "session_name": session_name,
            }
        )
    )
    (evidence / HOST._ALLOCATION_OUTCOME).write_bytes(
        HOST._canonical_json_bytes(
            {
                "host_launch_receipt_sha256": HOST._sha256(evidence / HOST._HOST_LAUNCH_RECEIPT),
                "returncode": 0,
                "session_name": session_name,
                "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-HOST-ALLOC-OUTCOME-V1",
            }
        )
    )


def test_allocate_persists_consumption_before_colab_new(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    seen: list[tuple[str, ...]] = []

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
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
        session_name="mesc-evidence-recovery-3",
        local_evidence_dir=evidence,
        canonical_revision="a" * 40,
        canonical_tree="b" * 40,
        authorization_sha256="c" * 64,
        decision_sha256="d" * 64,
    )
    assert seen == [("colab", "new", "--session", "mesc-evidence-recovery-3", "--gpu", "T4")]
    outcome = json.loads(
        (evidence / "evidence-recovery-3-colab-allocation-outcome.json").read_text(encoding="utf-8")
    )
    assert outcome["returncode"] == 0


def test_failed_allocation_remains_consumed_and_does_not_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    calls = 0

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        nonlocal calls
        calls += 1
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="launch consumption"):
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
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
        "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-AUTHORITY-RECEIPT-V1",
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

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        nonlocal upload_attempts
        if "upload" in args:
            assert timeout_seconds == 20.0
            upload_attempts += 1
            ack_path = Path(args[-2])
            assert ack_path.is_file()
            ack = json.loads(ack_path.read_text(encoding="utf-8"))
            assert ack["complete_local_evidence_verified"] is True
            assert (evidence / HOST._LOCAL_MANIFEST).is_file()
            upload_confirmed.set()
        if "exec" in args and not upload_confirmed.wait(timeout=5.0):
            return _completed(args, returncode=1)
        return _completed(args)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)

    HOST.run_with_continuous_retention(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-3",
        local_evidence_dir=evidence,
        remote_repository_root="/content/MESC",
        remote_custody="/content/mesc-evidence-recovery-3-custody",
        remote_python="/content/MESC/.venv/bin/python",
        expected_canonical_revision="a" * 40,
        poll_seconds=0.01,
    )

    assert upload_attempts == 1
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

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        if "stop" in args:
            return _completed(args)
        assert "exec" in args
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)

    with pytest.raises(HOST.EvidenceRecovery3HostError, match="remote Recovery-3 driver failed"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            remote_repository_root="/content/MESC",
            remote_custody="/content/mesc-evidence-recovery-3-custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
            poll_seconds=0.01,
        )

    assert set(forced) == set(HOST._REQUIRED_REMOTE_FILES)
    assert (evidence / last_artifact).read_bytes() == retained
    assert not (evidence / HOST._LOCAL_MANIFEST).exists()
    assert not (evidence / HOST._REMOTE_ACK).exists()
    outcome = json.loads(
        (evidence / "evidence-recovery-3-colab-exec-outcome.json").read_text(encoding="utf-8")
    )
    assert outcome["returncode"] == 1
    assert outcome["stdout"] == ""
    assert outcome["stderr"] == ""


def test_failed_driver_interrupts_watcher_scan_before_final_drain(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    _write_valid_host_receipt(evidence)
    first_download_started = threading.Event()
    initial_requests: list[str] = []

    def download(**kwargs: object) -> bool:
        if kwargs.get("force") is True:
            return False
        name = kwargs["name"]
        assert isinstance(name, str)
        initial_requests.append(name)
        first_download_started.set()
        time.sleep(0.1)
        return False

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        if "stop" in args:
            return _completed(args)
        assert "exec" in args
        assert first_download_started.wait(timeout=2.0)
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="remote Recovery-3 driver failed"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
            poll_seconds=0.01,
        )
    assert initial_requests == [HOST._REQUIRED_REMOTE_FILES[0]]
    assert not (evidence / HOST._REMOTE_ACK).exists()


def test_download_timeout_does_not_replace_existing_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "gemma-observation.json"
    target.write_bytes(b"prior-retained-evidence")

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        assert timeout_seconds == 20.0
        Path(args[-1]).write_bytes(b"partial-new-evidence")
        raise subprocess.TimeoutExpired(args, timeout_seconds)

    monkeypatch.setattr(HOST, "_run_colab", run)
    assert not HOST._download_once(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-3",
        remote_custody="/content/custody",
        local_dir=tmp_path,
        name="gemma-observation.json",
        force=True,
    )
    assert target.read_bytes() == b"prior-retained-evidence"
    assert not (tmp_path / ".partial" / "gemma-observation.json.partial").exists()


def test_force_refresh_replaces_early_partial_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    target = evidence / "gemma-observation.json"
    target.write_bytes(b"partial")

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        assert timeout_seconds == 20.0
        Path(args[-1]).write_bytes(b"complete-evidence")
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    assert HOST._download_once(
        colab_bin="colab",
        session_name="mesc-evidence-recovery-3",
        remote_custody="/content/custody",
        local_dir=evidence,
        name="gemma-observation.json",
        force=True,
    )
    assert target.read_bytes() == b"complete-evidence"
    journal = (evidence / HOST._COPY_JOURNAL).read_bytes()
    entry = json.loads(journal)
    assert entry == {
        "byte_count": len(b"complete-evidence"),
        "path": target.name,
        "sha256": hashlib.sha256(b"complete-evidence").hexdigest(),
        "state": "PROVISIONAL_COPY_ONLY",
    }
    assert journal == HOST._canonical_json_bytes(entry)


def test_run_rejects_host_receipt_for_different_session(tmp_path: Path) -> None:
    _write_valid_host_receipt(tmp_path, session_name="different-session")
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="session_name"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
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
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="local evidence mismatch"):
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
    with pytest.raises(HOST.EvidenceRecovery3HostError, match=error):
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
    with pytest.raises(HOST.EvidenceRecovery3HostError, match=error):
        HOST._verify_bundle_and_build_manifest(evidence)


def test_run_requires_host_launch_consumption(tmp_path: Path) -> None:
    _write_control_plane(tmp_path, phase="AFTER_ALLOCATION")
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="launch-consumption"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )


@pytest.mark.parametrize("outcome", ["missing", "failed", "wrong-session", "wrong-receipt", "bool"])
def test_run_requires_successful_bound_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    _write_valid_host_receipt(tmp_path)
    path = tmp_path / HOST._ALLOCATION_OUTCOME
    if outcome == "missing":
        path.unlink()
    else:
        document = json.loads(path.read_bytes())
        if outcome == "failed":
            document["returncode"] = 1
        elif outcome == "wrong-session":
            document["session_name"] = "other-session"
        elif outcome == "wrong-receipt":
            document["host_launch_receipt_sha256"] = "f" * 64
        else:
            document["returncode"] = False
        path.write_bytes(HOST._canonical_json_bytes(document))

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("allocation failure must prevent every Colab command")

    monkeypatch.setattr(HOST, "_run_colab", forbidden)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="allocation outcome"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )
    assert not (tmp_path / "evidence-recovery-3-colab-runner.py").exists()


@pytest.mark.parametrize("failure", ["watcher", "copy-out", "integrity", "ack"])
def test_terminal_retention_failure_stops_consumed_session_without_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _write_valid_host_receipt(tmp_path)
    remote = _remote_fixture()
    if failure == "integrity":
        remote["gemma-observation.json"] = b"corrupted-final-evidence"
    exec_started = threading.Event()
    session_stopped = threading.Event()
    commands: list[str] = []
    uploads = 0

    def download(**kwargs: object) -> bool:
        if session_stopped.is_set():
            return False
        assert exec_started.wait(timeout=2.0)
        if failure == "watcher":
            raise OSError("local evidence disk unavailable")
        if failure == "copy-out" and kwargs.get("force") is True:
            return False
        name = kwargs["name"]
        assert isinstance(name, str)
        (tmp_path / name).write_bytes(remote[name])
        return True

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        nonlocal uploads
        command = args[1]
        commands.append(command)
        if command == "exec":
            exec_started.set()
            assert session_stopped.wait(timeout=3.0), "remote execution was not stopped"
            return _completed(args, returncode=1)
        if command == "upload":
            uploads += 1
            return _completed(args, returncode=1)
        assert command == "stop"
        assert timeout_seconds == 20.0
        assert args[2:] == ("--session", "mesc-evidence-recovery-3")
        session_stopped.set()
        return _completed(args)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="watcher failed"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
            poll_seconds=0.01,
        )
    assert commands.count("exec") == 1
    assert commands.count("stop") == 1
    assert "new" not in commands
    assert uploads == (1 if failure == "ack" else 0)
    if failure != "ack":
        assert not (tmp_path / HOST._LOCAL_MANIFEST).exists()
        assert not (tmp_path / HOST._REMOTE_ACK).exists()
    stop_outcome = json.loads(
        (tmp_path / "evidence-recovery-3-colab-stop-outcome.json").read_bytes()
    )
    assert stop_outcome["returncode"] == 0


def test_immediate_watcher_failure_exposes_unproven_stop_before_exec(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_valid_host_receipt(tmp_path)
    commands: list[str] = []

    class FastFailureThread(threading.Thread):
        def start(self) -> None:
            super().start()
            self.join(timeout=2.0)

    def download(**kwargs: object) -> bool:
        raise OSError("immediate evidence-disk failure")

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        commands.append(args[1])
        assert args[1] == "stop"
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST.threading, "Thread", FastFailureThread)
    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="UNPROVEN; operator intervention"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )
    assert commands == ["stop"]


def test_provisional_copy_journal_preserves_each_copy_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copies = iter((b"early-partial", b"final-evidence"))

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        Path(args[-1]).write_bytes(next(copies))
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    for _ in range(2):
        assert HOST._download_once(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            remote_custody="/content/custody",
            local_dir=tmp_path,
            name="gemma-observation.json",
            force=True,
        )
    rows = [json.loads(line) for line in (tmp_path / HOST._COPY_JOURNAL).read_bytes().splitlines()]
    assert [row["sha256"] for row in rows] == [
        hashlib.sha256(raw).hexdigest() for raw in (b"early-partial", b"final-evidence")
    ]
    assert [row["byte_count"] for row in rows] == [len(b"early-partial"), len(b"final-evidence")]
    assert all(row["state"] == "PROVISIONAL_COPY_ONLY" for row in rows)
    assert not (tmp_path / HOST._LOCAL_MANIFEST).exists()


@pytest.mark.parametrize("failure", ["timeout", "launch", "nonzero"])
def test_failed_provider_stop_is_retained_and_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _write_valid_host_receipt(tmp_path)
    exec_started = threading.Event()
    stop_attempted = threading.Event()

    def download(**kwargs: object) -> bool:
        if stop_attempted.is_set():
            return False
        assert exec_started.wait(timeout=2.0)
        raise OSError("local-copy failure")

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        if args[1] == "exec":
            assert "--timeout" in args
            assert timeout_seconds == HOST._EXEC_WAIT_SECONDS + 20.0
            assert abort_event is not None
            exec_started.set()
            assert abort_event.wait(timeout=2.0)
            return _completed(args, returncode=1)
        assert args[1] == "stop"
        stop_attempted.set()
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 20.0, output=b"partial-stop", stderr=b"network")
        if failure == "launch":
            raise OSError("stop client unavailable")
        return _completed(args, returncode=1)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="UNPROVEN; operator intervention"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
            poll_seconds=0.01,
        )
    outcome = json.loads((tmp_path / "evidence-recovery-3-colab-stop-outcome.json").read_bytes())
    assert outcome["termination_state"] == "UNPROVEN"
    assert outcome["session_name"] == "mesc-evidence-recovery-3"
    if failure == "timeout":
        assert outcome["stdout"] == "partial-stop"
        assert outcome["stderr"] == "network"
        assert outcome["error_type"] == "TimeoutExpired"
    assert not (tmp_path / HOST._REMOTE_ACK).exists()


def test_supervised_local_client_cancels_without_waiting_for_remote_completion() -> None:
    abort = threading.Event()
    timer = threading.Timer(0.5, abort.set)
    timer.start()
    started = time.monotonic()
    try:
        result = HOST._run_colab(
            (sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"),
            timeout_seconds=10.0,
            abort_event=abort,
        )
    finally:
        timer.cancel()
    assert time.monotonic() - started < 8.0
    assert result.returncode != 0
    assert "started" in result.stdout


def test_supervised_local_client_timeout_preserves_captured_output() -> None:
    with pytest.raises(subprocess.TimeoutExpired) as raised:
        HOST._run_colab(
            (sys.executable, "-u", "-c", "import time; print('started'); time.sleep(30)"),
            timeout_seconds=0.5,
            abort_event=threading.Event(),
        )
    assert "started" in str(raised.value.stdout)


def test_exec_client_timeout_is_retained_and_stops_the_consumed_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_valid_host_receipt(tmp_path)
    commands: list[str] = []

    def download(**kwargs: object) -> bool:
        return False

    def run(
        args: tuple[str, ...],
        *,
        timeout_seconds: float | None = None,
        abort_event: threading.Event | None = None,
    ) -> object:
        commands.append(args[1])
        if args[1] == "exec":
            raise subprocess.TimeoutExpired(
                args, timeout_seconds or 1.0, output="early diagnostics"
            )
        assert args[1] == "stop"
        return _completed(args)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="launch consumed"):
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            remote_repository_root="/content/MESC",
            remote_custody="/content/custody",
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
            poll_seconds=0.01,
        )
    assert commands == ["exec", "stop"]
    outcome = json.loads((tmp_path / "evidence-recovery-3-colab-exec-outcome.json").read_bytes())
    assert outcome["error_type"] == "TimeoutExpired"
    assert outcome["stdout"] == "early diagnostics"
    assert outcome["returncode"] is None
    assert not (tmp_path / HOST._REMOTE_ACK).exists()
