"""Tests for fail-closed MESC runtime qualification evidence."""

from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationError,
    TrainingRuntimeQualificationReceipt,
    TrainingRuntimeSmokeEvidence,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.manifests import RunnerClass

_LOCK = "a" * 64
_SHA = "b" * 40
_TREE = "c" * 40


def _smoke_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "dependency_lock_sha256": _LOCK,
        "disposition": "PASS",
        "gpu_model": "fixture-gpu",
        "kind": "mesc.training_runtime_smoke.v1",
        "network_accessed": False,
        "os_name": "linux",
        "probe_id": "fixture-probe",
        "probe_version": "v1",
        "python_version": "3.12.14",
        "remote_code_allowed": False,
        "repository_sha": _SHA,
        "repository_tree": _TREE,
        "runner_class": RunnerClass.LOCAL.value,
    }
    payload.update(overrides)
    return payload


def _smoke(**overrides: object) -> TrainingRuntimeSmokeEvidence:
    return TrainingRuntimeSmokeEvidence(canonical_json_bytes(_smoke_payload(**overrides)))


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
        "network_accessed": False,
        "remote_code_allowed": False,
        "smoke_evidence": None,
    }
    kwargs.update(overrides)
    return build_training_runtime_qualification_receipt(
        runner_class=cast(RunnerClass, kwargs["runner_class"]),
        python_version=cast(str, kwargs["python_version"]),
        os_name=cast(str, kwargs["os_name"]),
        gpu_model=cast(str, kwargs["gpu_model"]),
        dependency_lock_sha256=cast(str, kwargs["dependency_lock_sha256"]),
        repository_sha=cast(str, kwargs["repository_sha"]),
        repository_tree=cast(str, kwargs["repository_tree"]),
        probe_id=cast(str, kwargs["probe_id"]),
        probe_version=cast(str, kwargs["probe_version"]),
        network_accessed=cast(bool, kwargs["network_accessed"]),
        remote_code_allowed=cast(bool, kwargs["remote_code_allowed"]),
        smoke_evidence=cast(TrainingRuntimeSmokeEvidence | None, kwargs["smoke_evidence"]),
    )


def test_observation_without_smoke_never_qualifies_platform() -> None:
    receipt = _build()
    assert receipt.disposition == "OBSERVED"
    assert receipt.smoke_disposition == "SKIPPED"
    assert receipt.smoke_receipt_sha256 is None
    assert receipt.platform_qualified is False
    assert receipt.blockers == ()


def test_validated_exact_bound_smoke_can_qualify_platform() -> None:
    smoke = _smoke()
    receipt = _build(smoke_evidence=smoke)
    assert receipt.disposition == "PASS"
    assert receipt.platform_qualified is True
    assert receipt.smoke_disposition == "PASS"
    assert receipt.smoke_receipt_sha256 == smoke.artifact_sha256


def test_arbitrary_hash_is_not_an_authority_input() -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        build_training_runtime_qualification_receipt(  # type: ignore[call-arg]
            runner_class=RunnerClass.LOCAL,
            python_version="3.12.14",
            os_name="linux",
            gpu_model="fixture-gpu",
            dependency_lock_sha256=_LOCK,
            repository_sha=_SHA,
            repository_tree=_TREE,
            probe_id="fixture-probe",
            probe_version="v1",
            smoke_receipt_sha256="d" * 64,
        )


def test_smoke_binding_mismatch_blocks_instead_of_qualifying() -> None:
    receipt = _build(smoke_evidence=_smoke(gpu_model="different-gpu"))
    assert receipt.disposition == "BLOCKED"
    assert receipt.platform_qualified is False
    assert "runtime smoke gpu_model does not match observed runtime" in receipt.blockers


def test_smoke_fail_blocks() -> None:
    receipt = _build(smoke_evidence=_smoke(disposition="FAIL"))
    assert receipt.disposition == "BLOCKED"
    assert "runtime smoke qualification failed" in receipt.blockers


def test_noncanonical_and_duplicate_key_smoke_bytes_fail_closed() -> None:
    canonical = canonical_json_bytes(_smoke_payload())
    with pytest.raises(TrainingRuntimeQualificationError, match="not canonical JSON"):
        TrainingRuntimeSmokeEvidence(canonical.rstrip(b"\n"))

    duplicate = canonical.replace(
        b'"disposition":"PASS"',
        b'"disposition":"PASS","disposition":"FAIL"',
        1,
    )
    with pytest.raises(TrainingRuntimeQualificationError, match="duplicate key"):
        TrainingRuntimeSmokeEvidence(duplicate)


def test_network_or_remote_code_blocks() -> None:
    assert _build(network_accessed=True).disposition == "BLOCKED"
    assert _build(remote_code_allowed=True).disposition == "BLOCKED"


def test_receipt_identity_is_stable_and_blockers_are_immutable() -> None:
    left = _build(smoke_evidence=_smoke())
    right = _build(smoke_evidence=_smoke())
    assert left.receipt_sha256 == right.receipt_sha256

    with pytest.raises(TrainingRuntimeQualificationError, match="blockers must be an exact tuple"):
        TrainingRuntimeQualificationReceipt(
            disposition="BLOCKED",
            runner_class=RunnerClass.LOCAL,
            python_version="3.12.14",
            os_name="linux",
            gpu_model="fixture-gpu",
            dependency_lock_sha256=_LOCK,
            repository_sha=_SHA,
            repository_tree=_TREE,
            probe_id="fixture-probe",
            probe_version="v1",
            network_accessed=True,
            remote_code_allowed=False,
            smoke_evidence=None,
            blockers=cast(tuple[str, ...], ["mutable"]),
        )
