from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import threading
import time
from dataclasses import replace
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._mrl_0809_evidence_recovery_3_effectiveness_v1 import (
    Recovery3EffectiveIdentity,
)
from medscale.mesc._mrl_0809_evidence_recovery_3_gate_v1 import (
    EvidenceRecovery3AuthorityIdentity,
)

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
_REAL_OBSERVE_TERMINATION = HOST._observe_session_terminated
_REAL_HOST_STATE_ROOT = HOST._host_state_root


def _effective_identity() -> Recovery3EffectiveIdentity:
    return Recovery3EffectiveIdentity(
        canonical_revision="a" * 40,
        canonical_tree="b" * 40,
        approved_implementation_sha="3" * 40,
        implementation_merge_sha="4" * 40,
        approval_comment_id=123,
        approval_body_sha256="5" * 64,
        authority=EvidenceRecovery3AuthorityIdentity(
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
            static_manifest_sha256="e" * 64,
            predecessor_failure_sha256="f" * 64,
            predecessor_merge_sha="1" * 40,
            predecessor_merge_tree="2" * 40,
        ),
    )


@pytest.fixture(autouse=True)
def _mock_effective_authority_for_synthetic_host_tests(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Real launch authority is NOT_EFFECTIVE; tests never touch a provider.
    monkeypatch.setattr(
        HOST, "require_recovery_3_launch_effectiveness", lambda *_: _effective_identity()
    )
    monkeypatch.setattr(HOST, "_host_state_root", lambda: tmp_path / "account-state")
    monkeypatch.setattr(HOST, "_observe_session_terminated", lambda **_: True)


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
    identity = _effective_identity()
    binding = {
        "approved_implementation_sha": identity.approved_implementation_sha,
        "implementation_merge_sha": identity.implementation_merge_sha,
        "approval_comment_id": identity.approval_comment_id,
        "approval_body_sha256": identity.approval_body_sha256,
        "canonical_revision": revision,
        "canonical_tree": "b" * 40,
        "authorization_sha256": "c" * 64,
        "decision_sha256": "d" * 64,
    }
    global_path = HOST._host_state_root() / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3.json"
    global_path.parent.mkdir(parents=True, exist_ok=True)
    global_path.write_bytes(
        HOST._canonical_json_bytes(
            {
                **binding,
                "session_name": session_name,
                "launch_authorization_consumed": True,
                "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-GLOBAL-CONSUMPTION-V1",
            }
        )
    )
    (evidence / HOST._HOST_LAUNCH_RECEIPT).write_bytes(
        HOST._canonical_json_bytes(
            {
                **binding,
                "global_consumption_sha256": HOST._sha256(global_path),
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
    assert calls == 2  # Exactly one allocation and one bounded stop.
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

    monkeypatch.setattr(HOST, "_observe_session_terminated", lambda **_: False)
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
    monkeypatch.setattr(HOST, "_observe_session_terminated", lambda **_: False)
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


def _run_retention(evidence: Path) -> None:
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


@pytest.mark.parametrize("failure", ["timeout", "launch", "outcome-write"])
def test_allocation_client_failure_is_consumed_retained_and_stopped_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _write_control_plane(tmp_path, phase="BEFORE_ALLOCATION")
    commands: list[str] = []
    original_write = HOST._write_new_fsync

    def write(path: Path, raw: bytes) -> None:
        if failure == "outcome-write" and path.name == HOST._ALLOCATION_OUTCOME:
            raise OSError("outcome disk unavailable")
        original_write(path, raw)

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        if args[1] == "new":
            assert kwargs["timeout_seconds"] == HOST._ALLOCATION_WAIT_SECONDS
            assert (tmp_path / HOST._HOST_LAUNCH_RECEIPT).is_file()
            if failure == "timeout":
                raise subprocess.TimeoutExpired(
                    args, HOST._ALLOCATION_WAIT_SECONDS, output=b"allocated?", stderr=b"network"
                )
            if failure == "launch":
                raise OSError("allocation client unavailable")
        else:
            assert args[1] == "stop"
            assert kwargs["timeout_seconds"] == 20.0
        return _completed(args)

    monkeypatch.setattr(HOST, "_write_new_fsync", write)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="launch consumption"):
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )
    assert commands == ["new", "stop"]
    assert (tmp_path / HOST._HOST_LAUNCH_RECEIPT).is_file()
    if failure != "outcome-write":
        outcome = json.loads((tmp_path / HOST._ALLOCATION_OUTCOME).read_bytes())
        assert outcome["returncode"] is None
        assert outcome["error_type"] == ("TimeoutExpired" if failure == "timeout" else "OSError")
        if failure == "timeout":
            assert outcome["stdout"] == "allocated?"
            assert outcome["stderr"] == "network"
    # A repeated invocation using this custody must not allocate or stop again.
    with pytest.raises(FileExistsError):
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )
    assert commands == ["new", "stop"]


@pytest.mark.parametrize("failure", ["preflight", "authority", "runner", "thread-start"])
def test_post_allocation_setup_failure_stops_owned_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    _write_valid_host_receipt(tmp_path)
    commands: list[str] = []

    def broken(*args: object, **kwargs: object) -> None:
        raise OSError(failure)

    if failure == "preflight":
        (tmp_path / HOST._AFTER_CONTROL_PLANE).write_bytes(b"invalid")
    elif failure == "authority":
        monkeypatch.setattr(HOST, "require_recovery_3_launch_effectiveness", broken)
    elif failure == "runner":
        monkeypatch.setattr(HOST, "_write_runner", broken)
    else:
        monkeypatch.setattr(HOST.threading.Thread, "start", broken)

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "stop"
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises((HOST.EvidenceRecovery3HostError, OSError)):
        _run_retention(tmp_path)
    assert commands == ["stop"]


def test_driver_failure_requests_stop_before_final_drain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_valid_host_receipt(tmp_path)
    commands: list[str] = []

    def download(**kwargs: object) -> bool:
        if kwargs.get("force") is True:
            assert commands == ["exec", "stop"]
        return False

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] in ("exec", "stop")
        return _completed(args, returncode=1 if args[1] == "exec" else 0)

    monkeypatch.setattr(HOST, "_download_once", download)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="driver failed"):
        _run_retention(tmp_path)
    assert commands == ["exec", "stop"]


@pytest.mark.parametrize("verified", [True, False])
def test_success_requires_exactly_one_stop_and_independent_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verified: bool
) -> None:
    _write_valid_host_receipt(tmp_path)
    commands: list[str] = []
    observations: list[str] = []

    def completed_runtime(**kwargs: object) -> None:
        assert callable(kwargs["stop_session"])

    def observe(**kwargs: object) -> bool:
        observations.append(str(kwargs["session_name"]))
        return verified

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "stop"
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_with_continuous_retention", completed_runtime)
    monkeypatch.setattr(HOST, "_observe_session_terminated", observe)
    monkeypatch.setattr(HOST, "_run_colab", run)
    if verified:
        _run_retention(tmp_path)
    else:
        with pytest.raises(HOST.EvidenceRecovery3HostError, match="termination UNPROVEN"):
            _run_retention(tmp_path)
    assert commands == ["stop"]
    assert observations == ["mesc-evidence-recovery-3"]
    outcome = json.loads((tmp_path / "evidence-recovery-3-colab-stop-outcome.json").read_bytes())
    assert outcome["independent_zero_assignments_verified"] is verified
    assert outcome["termination_state"] == ("VERIFIED_UNASSIGNED" if verified else "UNPROVEN")


@pytest.mark.parametrize("state", ["zero", "active", "unavailable", "timeout"])
def test_independent_observer_requires_bounded_zero_assignments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    def run(args: tuple[str, ...], **kwargs: object) -> object:
        assert args[0] == sys.executable
        assert args[1].endswith("mesc_mrl_0809_evidence_recovery_3_control_plane.py")
        assert kwargs["timeout_seconds"] == 20.0
        assert args[2:6] == (
            "--phase",
            "BEFORE_ALLOCATION",
            "--session",
            "mesc-evidence-recovery-3",
        )
        if state == "timeout":
            raise subprocess.TimeoutExpired(args, 20.0)
        if state == "unavailable":
            return _completed(args, returncode=1)
        _write_control_plane(tmp_path, phase="BEFORE_ALLOCATION")
        raw = (tmp_path / HOST._BEFORE_CONTROL_PLANE).read_bytes()
        if state == "active":
            document = json.loads(raw)
            document["account_assignments"] = 1
            document["server_assignments"] = 1
            raw = HOST._canonical_json_bytes(document)
        Path(args[-1]).write_bytes(raw)
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    assert _REAL_OBSERVE_TERMINATION(
        session_name="mesc-evidence-recovery-3", local_dir=tmp_path
    ) is (state == "zero")


def test_global_receipt_blocks_second_allocation_with_fresh_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for evidence in (first, second):
        _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    commands: list[str] = []
    identity = _effective_identity()
    global_path = HOST._host_state_root() / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3.json"

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "new"
        assert global_path.is_file()
        global_receipt = json.loads(global_path.read_bytes())
        local_receipt = json.loads((first / HOST._HOST_LAUNCH_RECEIPT).read_bytes())
        assert global_receipt["approval_comment_id"] == identity.approval_comment_id
        assert local_receipt["global_consumption_sha256"] == HOST._sha256(global_path)
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)

    def allocate(evidence: Path) -> None:
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )

    allocate(first)
    original_global = global_path.read_bytes()
    with pytest.raises(FileExistsError):
        allocate(second)
    assert commands == ["new"]  # Duplicate rejection must not stop the first session.
    assert global_path.read_bytes() == original_global
    assert not (second / HOST._HOST_LAUNCH_RECEIPT).exists()


@pytest.mark.parametrize(
    "field", ["canonical_revision", "canonical_tree", "authorization_sha256", "decision_sha256"]
)
@pytest.mark.parametrize("bad", ["wrong", True])
def test_allocation_arguments_must_match_verified_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, bad: object
) -> None:
    _write_control_plane(tmp_path, phase="BEFORE_ALLOCATION")
    args: dict[str, object] = {
        "colab_bin": "colab",
        "session_name": "mesc-evidence-recovery-3",
        "local_evidence_dir": tmp_path,
        "canonical_revision": "a" * 40,
        "canonical_tree": "b" * 40,
        "authorization_sha256": "c" * 64,
        "decision_sha256": "d" * 64,
    }
    args[field] = bad

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("unbound authority must not invoke the provider")

    monkeypatch.setattr(HOST, "_run_colab", forbidden)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match=f"binding mismatch: {field}"):
        HOST.allocate_single_t4_session(**args)
    assert not (tmp_path / HOST._HOST_LAUNCH_RECEIPT).exists()
    assert not (HOST._host_state_root()).exists()


@pytest.mark.parametrize(
    "bad_identity",
    [
        {"approval_comment_id": True},
        {"approval_comment_id": 0},
        {"approved_implementation_sha": "../unsafe"},
        {"approval_body_sha256": "bad"},
    ],
)
def test_malformed_effective_identity_cannot_create_global_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_identity: dict[str, object]
) -> None:
    identity = _effective_identity()
    if "approval_comment_id" in bad_identity:
        value = bad_identity["approval_comment_id"]
        assert isinstance(value, int)  # bool is deliberately included as hostile input.
        identity = replace(identity, approval_comment_id=value)
    elif "approved_implementation_sha" in bad_identity:
        value = bad_identity["approved_implementation_sha"]
        assert isinstance(value, str)
        identity = replace(identity, approved_implementation_sha=value)
    else:
        value = bad_identity["approval_body_sha256"]
        assert isinstance(value, str)
        identity = replace(identity, approval_body_sha256=value)
    monkeypatch.setattr(HOST, "require_recovery_3_launch_effectiveness", lambda *_: identity)
    _write_control_plane(tmp_path, phase="BEFORE_ALLOCATION")
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="effective identity is malformed"):
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=tmp_path,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )
    assert not (HOST._host_state_root()).exists()


def test_changed_approval_binding_fails_run_and_stops_owned_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_valid_host_receipt(tmp_path)
    changed = replace(_effective_identity(), approval_body_sha256="6" * 64)
    monkeypatch.setattr(HOST, "require_recovery_3_launch_effectiveness", lambda *_: changed)
    commands: list[str] = []

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "stop"
        return _completed(args)

    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="approval_body_sha256"):
        _run_retention(tmp_path)
    assert commands == ["stop"]


def test_global_consumption_survives_local_receipt_disk_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for evidence in (first, second):
        _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    original_write = HOST._write_new_fsync

    def write(path: Path, raw: bytes) -> None:
        if path.name == HOST._HOST_LAUNCH_RECEIPT:
            raise OSError("local receipt disk unavailable")
        original_write(path, raw)

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("receipt failure or duplicate rejection must not invoke or stop the provider")

    monkeypatch.setattr(HOST, "_write_new_fsync", write)
    monkeypatch.setattr(HOST, "_run_colab", forbidden)

    def allocate(evidence: Path) -> None:
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )

    with pytest.raises(OSError, match="local receipt disk"):
        allocate(first)
    global_path = HOST._host_state_root() / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3.json"
    original_global = global_path.read_bytes()
    with pytest.raises(FileExistsError):
        allocate(second)
    assert global_path.read_bytes() == original_global


def test_environment_home_change_cannot_create_new_consumption_namespace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    os_account_directory = tmp_path / "actual-account-state"
    monkeypatch.setattr(HOST, "_account_state_directory", lambda: str(os_account_directory))
    monkeypatch.setattr(HOST, "_host_state_root", _REAL_HOST_STATE_ROOT)
    first, second = tmp_path / "first", tmp_path / "second"
    for evidence in (first, second):
        _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    commands: list[str] = []

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "new"
        return _completed(args)

    def allocate(evidence: Path) -> None:
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )

    monkeypatch.setattr(HOST, "_run_colab", run)
    before = HOST._global_receipt_path()
    allocate(first)
    for key in ("HOME", "USERPROFILE", "LOCALAPPDATA"):
        monkeypatch.setenv(key, str(tmp_path / "caller-selected-home"))
    assert HOST._global_receipt_path() == before
    assert before.parent == os_account_directory.resolve() / "mesc/evidence-recovery-3"
    with pytest.raises(FileExistsError):
        allocate(second)
    assert commands == ["new"]


@pytest.mark.parametrize("failure", ["lookup-error", "relative-path"])
def test_os_account_lookup_failure_cannot_fall_back_to_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    def account_directory() -> str:
        if failure == "lookup-error":
            raise OSError("OS account unavailable")
        return "relative-account-path"

    monkeypatch.setattr(HOST, "_account_state_directory", account_directory)
    with pytest.raises(HOST.EvidenceRecovery3HostError, match="OS account state directory"):
        _REAL_HOST_STATE_ROOT()


def test_new_implementation_approval_cannot_reconsume_same_fixed_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for evidence in (first, second):
        _write_control_plane(evidence, phase="BEFORE_ALLOCATION")
    commands: list[str] = []

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "new"
        return _completed(args)

    def allocate(evidence: Path) -> None:
        HOST.allocate_single_t4_session(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            canonical_revision="a" * 40,
            canonical_tree="b" * 40,
            authorization_sha256="c" * 64,
            decision_sha256="d" * 64,
        )

    monkeypatch.setattr(HOST, "_run_colab", run)
    allocate(first)
    anchor = HOST._global_receipt_path()
    original_global = anchor.read_bytes()
    changed_identity = replace(
        _effective_identity(), approved_implementation_sha="7" * 40, approval_comment_id=456
    )
    monkeypatch.setattr(
        HOST, "require_recovery_3_launch_effectiveness", lambda *_: changed_identity
    )
    assert HOST._global_receipt_path() == anchor
    with pytest.raises(FileExistsError):
        allocate(second)
    assert anchor.read_bytes() == original_global
    assert commands == ["new"]


def test_copied_receipts_and_fresh_custody_cannot_repeat_host_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _write_valid_host_receipt(first)
    second.mkdir()
    for path in first.iterdir():
        if path.is_file():
            (second / path.name).write_bytes(path.read_bytes())
    executions: list[str] = []
    stops: list[str] = []

    def runtime(**kwargs: object) -> None:
        anchor = (
            HOST._host_state_root()
            / "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3-host-execution.json"
        )
        start = json.loads(anchor.read_bytes())
        assert start["remote_custody"] == "/content/first-custody"
        assert start["approval_body_sha256"] == _effective_identity().approval_body_sha256
        assert start["host_execution_authorization_consumed"] is True
        executions.append(str(kwargs["remote_custody"]))

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        stops.append(args[1])
        assert args[1] == "stop"
        return _completed(args)

    def retain(evidence: Path, custody: str) -> None:
        HOST.run_with_continuous_retention(
            colab_bin="colab",
            session_name="mesc-evidence-recovery-3",
            local_evidence_dir=evidence,
            remote_repository_root="/content/MESC",
            remote_custody=custody,
            remote_python="/content/MESC/.venv/bin/python",
            expected_canonical_revision="a" * 40,
        )

    monkeypatch.setattr(HOST, "_run_with_continuous_retention", runtime)
    monkeypatch.setattr(HOST, "_run_colab", run)
    retain(first, "/content/first-custody")
    with pytest.raises(FileExistsError):
        retain(second, "/content/fresh-second-custody")
    assert executions == ["/content/first-custody"]
    assert stops == ["stop"]


def test_host_execution_start_disk_failure_stops_owned_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_valid_host_receipt(tmp_path)
    original_write = HOST._write_new_fsync
    commands: list[str] = []

    def write(path: Path, raw: bytes) -> None:
        if path.name.endswith("-host-execution.json"):
            raise OSError("execution anchor disk unavailable")
        original_write(path, raw)

    def run(args: tuple[str, ...], **kwargs: object) -> object:
        commands.append(args[1])
        assert args[1] == "stop"
        return _completed(args)

    monkeypatch.setattr(HOST, "_write_new_fsync", write)
    monkeypatch.setattr(HOST, "_run_colab", run)
    with pytest.raises(OSError, match="execution anchor disk"):
        _run_retention(tmp_path)
    assert commands == ["stop"]


@pytest.mark.parametrize("termination", ["abort", "timeout"])
def test_local_client_tree_cleanup_closes_descendant_inherited_output(
    tmp_path: Path, termination: str
) -> None:
    child_started = tmp_path / "child-started"
    child_script = (
        "import pathlib,sys,time; "
        "pathlib.Path(sys.argv[1]).write_text('started'); "
        "print('child-output',flush=True); time.sleep(30)"
    )
    parent_script = (
        "import subprocess,sys; "
        f"child=subprocess.Popen([sys.executable,'-u','-c',{child_script!r},sys.argv[1]]); "
        "child.wait()"
    )
    abort = threading.Event()

    def signal_when_child_ready() -> None:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not child_started.is_file():
            time.sleep(0.01)
        if termination == "abort":
            abort.set()

    signal_thread = threading.Thread(target=signal_when_child_ready)
    signal_thread.start()
    started = time.monotonic()
    try:
        argv = (sys.executable, "-u", "-c", parent_script, str(child_started))
        if termination == "timeout":
            with pytest.raises(subprocess.TimeoutExpired) as raised:
                HOST._run_colab(argv, timeout_seconds=1.0)
            output = str(raised.value.stdout)
        else:
            result = HOST._run_colab(argv, timeout_seconds=10.0, abort_event=abort)
            assert result.returncode != 0
            output = result.stdout
    finally:
        signal_thread.join(timeout=6.0)
    assert not signal_thread.is_alive()
    assert child_started.is_file()
    assert "child-output" in output
    assert time.monotonic() - started < 8.0
