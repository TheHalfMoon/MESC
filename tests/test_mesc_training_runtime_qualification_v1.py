"""Tests for MESC training runtime-qualification receipts."""

from __future__ import annotations

import pytest

from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationError,
    TrainingRuntimeQualificationReceipt,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.manifests import RunnerClass

_LOCK = "a" * 64
_SHA = "b" * 40
_TREE = "c" * 40
_SMOKE = "d" * 64


def _build(**overrides: object) -> TrainingRuntimeQualificationReceipt:
    kwargs: dict[str, object] = {
        "runner_class": RunnerClass.LOCAL,
        "python_version": "3.12.14",
        "os_name": "linux",
        "gpu_model": "fixture-gpu",
        "dependency_lock_sha256": _LOCK,
        "repository_sha": _SHA,
        "repository_tree": _TREE,
        "probe_id": "fixture-probe",
        "probe_version": "v1",
    }
    kwargs.update(overrides)
    return build_training_runtime_qualification_receipt(
        runner_class=kwargs["runner_class"],  # type: ignore[arg-type]
        python_version=str(kwargs["python_version"]),
        os_name=str(kwargs["os_name"]),
        gpu_model=str(kwargs["gpu_model"]),
        dependency_lock_sha256=str(kwargs["dependency_lock_sha256"]),
        repository_sha=str(kwargs["repository_sha"]),
        repository_tree=str(kwargs["repository_tree"]),
        probe_id=str(kwargs["probe_id"]),
        probe_version=str(kwargs["probe_version"]),
        network_accessed=bool(kwargs.get("network_accessed", False)),
        remote_code_allowed=bool(kwargs.get("remote_code_allowed", False)),
        smoke_disposition=kwargs.get("smoke_disposition", "SKIPPED"),  # type: ignore[arg-type]
        smoke_receipt_sha256=kwargs.get("smoke_receipt_sha256"),  # type: ignore[arg-type]
    )


def test_observed_without_smoke_is_not_platform_qualified() -> None:
    receipt = _build()
    assert receipt.disposition == "OBSERVED"
    assert receipt.smoke_disposition == "SKIPPED"
    assert receipt.platform_qualified is False
    assert len(receipt.receipt_sha256) == 64


def test_platform_qualified_requires_smoke_pass() -> None:
    receipt = _build(smoke_disposition="PASS", smoke_receipt_sha256=_SMOKE)
    assert receipt.disposition == "PASS"
    assert receipt.platform_qualified is True


def test_network_access_blocks() -> None:
    receipt = _build(network_accessed=True)
    assert receipt.disposition == "BLOCKED"
    assert "network_accessed must be false" in receipt.blockers
    assert receipt.platform_qualified is False


def test_smoke_fail_blocks() -> None:
    receipt = _build(smoke_disposition="FAIL")
    assert receipt.disposition == "BLOCKED"
    assert "runtime smoke qualification failed" in receipt.blockers


def test_direct_pass_with_failed_smoke_is_rejected() -> None:
    with pytest.raises(TrainingRuntimeQualificationError, match="PASS requires smoke"):
        TrainingRuntimeQualificationReceipt(
            disposition="PASS",
            runner_class=RunnerClass.LOCAL,
            python_version="3.12.14",
            os_name="linux",
            gpu_model="fixture-gpu",
            dependency_lock_sha256=_LOCK,
            repository_sha=_SHA,
            repository_tree=_TREE,
            probe_id="fixture-probe",
            probe_version="v1",
            network_accessed=False,
            remote_code_allowed=False,
            smoke_disposition="FAIL",
            smoke_receipt_sha256=None,
            platform_qualified=True,
            blockers=(),
        )


def test_refuses_invented_empty_gpu() -> None:
    with pytest.raises(TrainingRuntimeQualificationError, match="gpu_model"):
        _build(gpu_model=" ")


def test_deterministic_receipt_identity() -> None:
    left = _build()
    right = _build()
    assert left.receipt_sha256 == right.receipt_sha256
    changed = _build(gpu_model="other-gpu")
    assert changed.receipt_sha256 != left.receipt_sha256
