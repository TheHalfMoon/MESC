"""Offline Kaggle contract/custody checks; no provider or model execution."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from medscale.mesc._kaggle_runtime_adapter_v1 import (
    CANDIDATES,
    DEPENDENCY_LOCK_SHA256,
    PACKAGES,
    KaggleAdapterError,
    OfflineCustodySession,
    require_scientific_execution,
    validate_environment_candidate,
)


def environment() -> dict[str, Any]:
    return {
        "schema_version": "MESC-KAGGLE-ENVIRONMENT-CANDIDATE-V1",
        "evidence_origin": "OFFLINE_SIMULATION",
        "provider": "KAGGLE",
        "run_id": "1" * 32,
        "source_revision": "2" * 40,
        "source_tree": "3" * 40,
        "source_manifest_sha256": "4" * 64,
        "dependency_lock_sha256": DEPENDENCY_LOCK_SHA256,
        "python_version": "3.11.15",
        "platform": "linux-x86_64",
        "packages": dict(PACKAGES),
        "cuda_available": True,
        "cuda_runtime": "12.8",
        "driver_version": "570.124.06",
        "devices": [
            {
                "index": 0,
                "name": "Tesla T4",
                "memory_bytes": 15 * 1024**3,
                "compute_capability": [7, 5],
            },
            {
                "index": 1,
                "name": "Tesla T4",
                "memory_bytes": 15 * 1024**3,
                "compute_capability": [7, 5],
            },
        ],
        "placement_policy": "SINGLE_CUDA0_SEQUENTIAL",
        "representation": "bitsandbytes-nf4-v1",
        "candidates": [{"model_id": model, "revision": revision} for model, revision in CANDIDATES],
        "input": "Write one short sentence about a blue triangle.",
        "input_class": "SYNTHETIC_ONLY",
        "cpu_offload": False,
        "disk_offload": False,
        "automatic_device_map": False,
        "training": False,
        "weight_mutation": False,
        "paid_compute": False,
        "quota_remaining_seconds": None,
        "max_session_seconds": 3600,
        "max_evidence_bytes": 65536,
    }


def validate(document: dict[str, Any]) -> bytes:
    return validate_environment_candidate(
        document,
        expected_revision="2" * 40,
        expected_tree="3" * 40,
        expected_manifest_sha256="4" * 64,
    )


def test_two_devices_are_separate_and_candidate_is_not_runtime_pass() -> None:
    candidate = json.loads(validate(environment()))
    assert candidate["per_device_memory_bytes"] == [15 * 1024**3, 15 * 1024**3]
    assert candidate["placement_policy"] == "SINGLE_CUDA0_SEQUENTIAL"
    assert candidate["scientific_execution_authorized"] is False
    assert candidate["runtime_feasibility_proven"] is False
    assert candidate["quota_state"] == "UNKNOWN"
    assert "pooled_memory_bytes" not in candidate


def test_single_device_supported_without_changing_protocol() -> None:
    document = environment()
    document["devices"] = document["devices"][:1]
    assert json.loads(validate(document))["per_device_memory_bytes"] == [15 * 1024**3]


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider", "GOOGLE_COLAB_FREE"),
        ("source_revision", "f" * 40),
        ("source_tree", "f" * 40),
        ("source_manifest_sha256", "f" * 64),
        ("dependency_lock_sha256", "f" * 64),
        ("python_version", "3.10.1"),
        ("python_version", "3.12.13"),
        ("python_version", "3.15.0"),
        ("python_version", "3.12"),
        ("python_version", "3.12.1; arbitrary"),
        ("platform", "windows-x86_64"),
        ("cuda_available", False),
        ("cuda_available", 1),
        ("cuda_runtime", "UNKNOWN"),
        ("driver_version", "UNKNOWN"),
        ("placement_policy", "AUTO"),
        ("representation", "fp16"),
        ("input_class", "PHI"),
        ("input", "arbitrary patient input"),
        ("cpu_offload", True),
        ("disk_offload", True),
        ("automatic_device_map", True),
        ("training", True),
        ("weight_mutation", True),
        ("paid_compute", True),
        ("paid_compute", 0),
        ("quota_remaining_seconds", -1),
        ("quota_remaining_seconds", True),
        ("max_session_seconds", 0),
        ("max_session_seconds", 14401),
        ("max_session_seconds", True),
        ("max_evidence_bytes", 1048577),
        ("evidence_origin", "TRUSTED_PASS"),
        ("run_id", "../other"),
    ],
)
def test_invalid_environment_fails_closed(field: str, value: object) -> None:
    document = environment()
    document[field] = value
    with pytest.raises(KaggleAdapterError):
        validate(document)


def test_unknown_fields_cannot_smuggle_credentials_or_authority() -> None:
    document = environment()
    document["token"] = "fixture-only"
    with pytest.raises(KaggleAdapterError):
        validate(document)


def test_missing_fields_fail_closed() -> None:
    document = environment()
    del document["paid_compute"]
    with pytest.raises(KaggleAdapterError):
        validate(document)


@pytest.mark.parametrize(
    "mutation", ["package", "revision", "gpu", "memory", "index", "capability", "three"]
)
def test_nested_identity_and_compatibility_rejection(mutation: str) -> None:
    document = environment()
    if mutation == "package":
        document["packages"]["torch"] = "2.12.0"
    elif mutation == "revision":
        document["candidates"][1]["revision"] = "f" * 40
    elif mutation == "gpu":
        document["devices"][0]["name"] = "P100"
    elif mutation == "memory":
        document["devices"][0]["memory_bytes"] = 8 * 1024**3
    elif mutation == "index":
        document["devices"][1]["index"] = 0
    elif mutation == "capability":
        document["devices"][0]["compute_capability"] = [8, 0]
    else:
        document["devices"].append(copy.deepcopy(document["devices"][1]))
    with pytest.raises(KaggleAdapterError):
        validate(document)


@pytest.mark.parametrize("origin", ["OFFLINE_SIMULATION", "HOSTED_OBSERVATION"])
def test_no_observation_or_caller_label_can_authorize_execution(origin: str) -> None:
    document = environment()
    document["evidence_origin"] = origin
    candidate = validate(document)
    with pytest.raises(KaggleAdapterError, match=r"separate.*authority"):
        require_scientific_execution(candidate)


def session(tmp_path: Path) -> OfflineCustodySession:
    return OfflineCustodySession(
        state_dir=tmp_path / "mock-state",
        custody=tmp_path / "custody",
        environment_candidate=validate(environment()),
    )


def test_continuous_local_hash_custody_deterministic_manifest_and_ack(tmp_path: Path) -> None:
    adapter = session(tmp_path)
    adapter.start()
    adapter.retain("qwen-result.json", b'{"result":"NULL","simulation":true}\n', elapsed_seconds=1)
    adapter.retain(
        "gemma-result.json", b'{"result":"NEGATIVE","simulation":true}\n', elapsed_seconds=2
    )
    manifest, ack = adapter.finish(elapsed_seconds=3)
    assert manifest == adapter.verify()
    assert json.loads(ack)["manifest_sha256"] == hashlib.sha256(manifest).hexdigest()
    assert json.loads(ack)["evidence_origin"] == "OFFLINE_SIMULATION"
    assert json.loads(ack)["scientific_execution_authorized"] is False
    assert (tmp_path / "mock-state" / ("1" * 32 + ".json")).is_file()
    assert all(
        row["sha256"]
        == hashlib.sha256((tmp_path / "custody" / row["path"]).read_bytes()).hexdigest()
        for row in json.loads(manifest)["artifacts"]
    )


def test_single_use_survives_new_custody_directory(tmp_path: Path) -> None:
    first = session(tmp_path)
    first.start()
    second = OfflineCustodySession(
        state_dir=tmp_path / "mock-state",
        custody=tmp_path / "different-custody",
        environment_candidate=validate(environment()),
    )
    with pytest.raises(KaggleAdapterError, match="consumed"):
        second.start()
    assert not (tmp_path / "different-custody").exists()


@pytest.mark.parametrize("failure", ["timeout", "interruption", "budget", "duplicate", "traversal"])
def test_failure_preserved_and_never_restarts(tmp_path: Path, failure: str) -> None:
    adapter = session(tmp_path)
    adapter.start()
    with pytest.raises(KaggleAdapterError):
        if failure == "timeout":
            adapter.retain("qwen-result.json", b"{}", elapsed_seconds=3601)
        elif failure == "interruption":
            adapter.interrupt()
        elif failure == "budget":
            adapter.retain("qwen-result.json", b"x" * 65537, elapsed_seconds=1)
        elif failure == "duplicate":
            adapter.retain("qwen-result.json", b"{}", elapsed_seconds=1)
            adapter.retain("qwen-result.json", b"{}", elapsed_seconds=2)
        else:
            adapter.retain("../outside.json", b"{}", elapsed_seconds=1)
    assert (tmp_path / "custody" / "failure.json").is_file()
    assert not (tmp_path / "custody" / "host-ack.json").exists()
    with pytest.raises(KaggleAdapterError):
        adapter.finish(elapsed_seconds=3)
    with pytest.raises(KaggleAdapterError):
        adapter.start()


def test_incomplete_bundle_cannot_ack(tmp_path: Path) -> None:
    adapter = session(tmp_path)
    adapter.start()
    with pytest.raises(KaggleAdapterError, match="incomplete"):
        adapter.finish(elapsed_seconds=1)
    assert not (tmp_path / "custody" / "host-ack.json").exists()


def test_tampering_prevents_host_ack(tmp_path: Path) -> None:
    adapter = session(tmp_path)
    adapter.start()
    adapter.retain("qwen-result.json", b"{}", elapsed_seconds=1)
    adapter.retain("gemma-result.json", b"{}", elapsed_seconds=2)
    (tmp_path / "custody" / "qwen-result.json").write_bytes(b"changed")
    with pytest.raises(KaggleAdapterError, match="hash"):
        adapter.finish(elapsed_seconds=3)
    assert not (tmp_path / "custody" / "host-ack.json").exists()


def test_hosted_candidate_cannot_enter_offline_simulator(tmp_path: Path) -> None:
    document = environment()
    document["evidence_origin"] = "HOSTED_OBSERVATION"
    with pytest.raises(KaggleAdapterError, match="offline"):
        OfflineCustodySession(
            state_dir=tmp_path / "mock-state",
            custody=tmp_path / "custody",
            environment_candidate=validate(document),
        )


def test_symlink_custody_is_rejected_without_mutating_target(tmp_path: Path) -> None:
    actual = tmp_path / "actual"
    actual.mkdir()
    link = tmp_path / "linked"
    try:
        link.symlink_to(actual, target_is_directory=True)
    except OSError:
        pytest.skip("OS account cannot create symlinks")
    with pytest.raises(KaggleAdapterError):
        OfflineCustodySession(
            state_dir=tmp_path / "mock-state",
            custody=link,
            environment_candidate=validate(environment()),
        )
    assert not list(actual.iterdir())


@pytest.mark.parametrize(
    "mutation", ["extra", "missing", "identity", "lock", "memory", "oversized"]
)
def test_forged_candidate_never_enters_custody(tmp_path: Path, mutation: str) -> None:
    value = json.loads(validate(environment()))
    if mutation == "extra":
        value["token"] = "fixture-only"
    elif mutation == "missing":
        del value["source_revision"]
    elif mutation == "identity":
        value["observation_sha256"] = "invalid"
    elif mutation == "lock":
        value["dependency_lock_sha256"] = "f" * 64
    elif mutation == "memory":
        value["per_device_memory_bytes"] = [True]
    else:
        value["token"] = "x" * 8192
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with pytest.raises(KaggleAdapterError):
        OfflineCustodySession(
            state_dir=tmp_path / "state", custody=tmp_path / "custody", environment_candidate=raw
        )
    assert not (tmp_path / "state").exists()
    assert not (tmp_path / "custody").exists()


def test_setup_failure_preserved_without_touching_existing_custody(tmp_path: Path) -> None:
    custody = tmp_path / "custody"
    custody.mkdir()
    marker = custody / "existing-user-file"
    marker.write_bytes(b"preserve")
    adapter = session(tmp_path)
    with pytest.raises(KaggleAdapterError, match="setup failed"):
        adapter.start()
    assert marker.read_bytes() == b"preserve"
    failure = tmp_path / "mock-state" / ("1" * 32 + ".setup-failure.json")
    assert json.loads(failure.read_bytes())["consumed"] is True
    assert json.loads(failure.read_bytes())["automatic_retry_authorized"] is False


def test_replaced_fifo_is_rejected_without_blocking(tmp_path: Path) -> None:
    mkfifo = getattr(os, "mkfifo", None)
    if mkfifo is None:
        pytest.skip("FIFO creation requires POSIX")
    adapter = session(tmp_path)
    adapter.start()
    adapter.retain("qwen-result.json", b"{}", elapsed_seconds=1)
    path = tmp_path / "custody" / "qwen-result.json"
    path.unlink()
    mkfifo(path)
    with pytest.raises(KaggleAdapterError, match="regular file"):
        adapter.verify()
    assert not (tmp_path / "custody" / "host-ack.json").exists()
