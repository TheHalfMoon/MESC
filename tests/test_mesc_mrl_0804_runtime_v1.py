"""Regression tests for the MRL-0804 hosted-runtime evidence producer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from medscale.mesc import _mrl_0804_runtime_v1 as runtime
from medscale.mesc._mrl_real_preflight_evidence_v1 import (
    MRLRealPreflightEvidenceError,
    admit_mrl_real_preflight_evidence,
    parse_mrl_real_preflight_evidence,
)

_ROOT = Path(__file__).resolve().parents[1]
_AUTH = _ROOT / "specs/mesc-experiment-0/mrl-0804-runtime-authorization-v1.json"
_PROBE = _ROOT / "scripts/mesc_mrl_0804_gpu_probe.py"


def _load_probe() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0804_gpu_probe_test", _PROBE)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load MRL-0804 GPU probe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeTensor:
    def __init__(self, values: list[int]) -> None:
        self.values = values

    def __mul__(self, value: int) -> _FakeTensor:
        return _FakeTensor([item * value for item in self.values])

    def __add__(self, value: int) -> _FakeTensor:
        return _FakeTensor([item + value for item in self.values])

    def cpu(self) -> _FakeTensor:
        return self

    def tolist(self) -> list[int]:
        return list(self.values)


class _FakeCuda:
    def __init__(self, *, available: bool = True, count: int = 1) -> None:
        self.available = available
        self.count = count
        self.synchronized = False

    def is_available(self) -> bool:
        return self.available

    def device_count(self) -> int:
        return self.count

    def get_device_name(self, index: int) -> str:
        assert index < self.count
        return "NVIDIA A10G"

    def get_device_properties(self, index: int) -> SimpleNamespace:
        assert index < self.count
        return SimpleNamespace(total_memory=24 * 1024**3)

    def synchronize(self) -> None:
        self.synchronized = True


class _FakeTorch:
    __version__ = "2.9.0+cu128"
    int64 = object()

    def __init__(self, *, available: bool = True, count: int = 1) -> None:
        self.cuda = _FakeCuda(available=available, count=count)
        self.version = SimpleNamespace(cuda="12.8")

    def arange(self, start: int, stop: int, *, dtype: object, device: str) -> _FakeTensor:
        assert dtype is self.int64
        assert device == "cuda"
        return _FakeTensor(list(range(start, stop)))


def _authorization() -> runtime.MRL0804RuntimeAuthorization:
    return runtime.parse_mrl_0804_runtime_authorization(_AUTH.read_bytes())


def _probe_bytes(
    *,
    provider: str = "HUGGING_FACE_JOBS",
    flavor: str = "zero-a10g",
    runner_class: str = "other",
    torch_module: Any | None = None,
) -> tuple[bytes, bytes, str]:
    authorization = _authorization()
    probe = _load_probe()
    probe_sha = hashlib.sha256(_PROBE.read_bytes()).hexdigest()
    observation, smoke = probe.build_probe_artifacts(
        torch_module=_FakeTorch() if torch_module is None else torch_module,
        provider=provider,
        provider_flavor=flavor,
        runner_class=runner_class,
        repository_sha=authorization.main_sha,
        repository_tree=authorization.main_tree,
        dependency_lock_sha256=authorization.dependency_lock_sha256,
        probe_source_sha256=probe_sha,
    )
    return observation, smoke, probe_sha


def _qualify() -> runtime.MRL0804RuntimeQualification:
    authorization = _authorization()
    observation, smoke, probe_sha = _probe_bytes()
    return runtime.qualify_mrl_0804_runtime(
        observation,
        smoke,
        authorization=authorization,
        repository_sha=authorization.main_sha,
        repository_tree=authorization.main_tree,
        dependency_lock_sha256=authorization.dependency_lock_sha256,
        probe_source_sha256=probe_sha,
    )


def _rewrite(raw: bytes, **updates: object) -> bytes:
    document = json.loads(raw)
    document.update(updates)
    probe = _load_probe()
    return probe.canonical_json_bytes(document)


def test_committed_authorization_is_exact_and_fail_closed() -> None:
    authorization = _authorization()
    assert authorization.authorization_sha256 == hashlib.sha256(_AUTH.read_bytes()).hexdigest()
    assert authorization.main_sha == "daa2e83774b7bc210014e4e160bcf1203e943a4e"
    assert authorization.main_tree == "dce64b8c75cb10773d21388b7c1cc83be4434b79"
    assert authorization.required_gpu_count == 1
    assert {(row.provider, row.provider_flavor) for row in authorization.providers} == {
        ("GOOGLE_COLAB", "DYNAMIC_ASSIGNED"),
        ("HUGGING_FACE_JOBS", "zero-a10g"),
    }
    hf = authorization.provider_for("HUGGING_FACE_JOBS", "zero-a10g")
    assert hf.requires_free_or_quota_backed is True


def test_hosted_gpu_probe_and_qualification_are_deterministic() -> None:
    first = _qualify()
    second = _qualify()
    assert first == second
    parsed = parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0804"
    assert parsed.subject_sha256 == first.runtime_identity_sha256
    assert first.smoke_receipt_sha256 == hashlib.sha256(first.smoke_receipt_bytes).hexdigest()
    with pytest.raises(MRLRealPreflightEvidenceError, match="not trusted"):
        admit_mrl_real_preflight_evidence(first.evidence_bytes, expected_task_id="MRL-0804")


def test_bundle_verifier_recomputes_exact_bytes_and_rejects_tampering() -> None:
    authorization = _authorization()
    observation, smoke, probe_sha = _probe_bytes()
    result = _qualify()
    verified = runtime.verify_mrl_0804_runtime_bundle(
        observation,
        smoke,
        authorization=authorization,
        repository_sha=authorization.main_sha,
        repository_tree=authorization.main_tree,
        dependency_lock_sha256=authorization.dependency_lock_sha256,
        probe_source_sha256=probe_sha,
        runtime_identity_bytes=result.runtime_identity_bytes,
        qualification_receipt_bytes=result.qualification_receipt_bytes,
        evidence_bytes=result.evidence_bytes,
    )
    assert verified == result
    with pytest.raises(runtime.MRL0804RuntimeError, match="supplied real-preflight evidence"):
        runtime.verify_mrl_0804_runtime_bundle(
            observation,
            smoke,
            authorization=authorization,
            repository_sha=authorization.main_sha,
            repository_tree=authorization.main_tree,
            dependency_lock_sha256=authorization.dependency_lock_sha256,
            probe_source_sha256=probe_sha,
            runtime_identity_bytes=result.runtime_identity_bytes,
            qualification_receipt_bytes=result.qualification_receipt_bytes,
            evidence_bytes=result.evidence_bytes.replace(b'"PASS"', b'"FAIL"', 1),
        )


def test_unauthorized_provider_flavor_fails_closed() -> None:
    authorization = _authorization()
    observation, smoke, probe_sha = _probe_bytes(flavor="a10g-small")
    with pytest.raises(runtime.MRL0804RuntimeError, match="not exactly authorized"):
        runtime.qualify_mrl_0804_runtime(
            observation,
            smoke,
            authorization=authorization,
            repository_sha=authorization.main_sha,
            repository_tree=authorization.main_tree,
            dependency_lock_sha256=authorization.dependency_lock_sha256,
            probe_source_sha256=probe_sha,
        )


def test_network_remote_code_and_source_drift_fail_closed() -> None:
    authorization = _authorization()
    observation, smoke, probe_sha = _probe_bytes()
    for field in ("network_accessed", "remote_code_allowed"):
        bad_observation = _rewrite(observation, **{field: True})
        with pytest.raises(runtime.MRL0804RuntimeError, match="must not"):
            runtime.qualify_mrl_0804_runtime(
                bad_observation,
                smoke,
                authorization=authorization,
                repository_sha=authorization.main_sha,
                repository_tree=authorization.main_tree,
                dependency_lock_sha256=authorization.dependency_lock_sha256,
                probe_source_sha256=probe_sha,
            )
    with pytest.raises(runtime.MRL0804RuntimeError, match="probe source"):
        runtime.qualify_mrl_0804_runtime(
            observation,
            smoke,
            authorization=authorization,
            repository_sha=authorization.main_sha,
            repository_tree=authorization.main_tree,
            dependency_lock_sha256=authorization.dependency_lock_sha256,
            probe_source_sha256="f" * 64,
        )


def test_gpu_count_and_cuda_unavailability_fail_at_probe_boundary() -> None:
    probe = _load_probe()
    authorization = _authorization()
    probe_sha = hashlib.sha256(_PROBE.read_bytes()).hexdigest()
    common = {
        "provider": "HUGGING_FACE_JOBS",
        "provider_flavor": "zero-a10g",
        "runner_class": "other",
        "repository_sha": authorization.main_sha,
        "repository_tree": authorization.main_tree,
        "dependency_lock_sha256": authorization.dependency_lock_sha256,
        "probe_source_sha256": probe_sha,
    }
    with pytest.raises(RuntimeError, match="CUDA is unavailable"):
        probe.build_probe_artifacts(torch_module=_FakeTorch(available=False), **common)
    with pytest.raises(RuntimeError, match="exactly one hosted GPU"):
        probe.build_probe_artifacts(torch_module=_FakeTorch(count=2), **common)


def test_probe_contains_no_model_loading_or_training_primitives() -> None:
    source = _PROBE.read_text(encoding="utf-8")
    for token in (
        "transformers",
        "from_pretrained",
        "AutoModel",
        "AutoTokenizer",
        "SFTTrainer",
        "optimizer.step",
        ".backward(",
        "unsloth",
    ):
        assert token not in source
