"""Deterministic MRL-0804 hosted-runtime qualification and evidence assembly.

This module validates externally produced runtime observation and GPU-smoke bytes. It performs
no provider access, network access, GPU work, model/tokenizer loading, inference, or training.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationError,
    TrainingRuntimeSmokeEvidence,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.manifests import RunnerClass

_AUTHORIZATION_SHA256: Final = "afef2cf4959e2f308f9422f8a6632f4ef0a16ec18056f25ae6aa58946403f277"
_AUTH_SCHEMA: Final = "MESC-MRL-0804-RUNTIME-AUTHORIZATION-V1"
_OBSERVATION_SCHEMA: Final = "MESC-MRL-0804-RUNTIME-OBSERVATION-V1"
_IDENTITY_SCHEMA: Final = "MESC-MRL-0804-RUNTIME-IDENTITY-V1"
_EXPECTED_TASK: Final = "MRL-0804"
_EXPECTED_KIND: Final = "mesc.mrl.real_preflight.runtime.v1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)


class MRL0804RuntimeError(ValueError):
    """Raised when MRL-0804 runtime material fails closed."""


@dataclass(frozen=True, slots=True)
class AuthorizedRuntimeProvider:
    """One provider/flavor/runner tuple authorized for runtime qualification."""

    provider: str
    provider_flavor: str
    runner_class: RunnerClass
    requires_free_or_quota_backed: bool


@dataclass(frozen=True, slots=True)
class MRL0804RuntimeAuthorization:
    """Exact committed MRL-0804 authorization bytes and validated semantics."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)
    main_sha: str = field(init=False)
    main_tree: str = field(init=False)
    dependency_lock_sha256: str = field(init=False)
    required_gpu_count: int = field(init=False)
    smoke_probe_id: str = field(init=False)
    smoke_probe_version: str = field(init=False)
    providers: tuple[AuthorizedRuntimeProvider, ...] = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="authorization")
        digest = hashlib.sha256(self.canonical_bytes).hexdigest()
        if digest != _AUTHORIZATION_SHA256:
            raise MRL0804RuntimeError("authorization bytes do not match the committed identity")
        _validate_authorization(document)

        base = _require_object(document["authorized_base"], label="authorized_base")
        runtime = _require_object(document["runtime_policy"], label="runtime_policy")
        provider_rows = _require_list(runtime["providers"], label="runtime_policy.providers")
        providers: list[AuthorizedRuntimeProvider] = []
        for index, row_value in enumerate(provider_rows):
            row = _require_object(row_value, label=f"runtime_policy.providers[{index}]")
            runner_text = _require_text(row["runner_class"], label="runner_class")
            try:
                runner = RunnerClass(runner_text)
            except ValueError as exc:
                raise MRL0804RuntimeError("authorization runner_class is invalid") from exc
            providers.append(
                AuthorizedRuntimeProvider(
                    provider=_require_text(row["provider"], label="provider"),
                    provider_flavor=_require_text(row["provider_flavor"], label="provider_flavor"),
                    runner_class=runner,
                    requires_free_or_quota_backed=_require_bool(
                        row["requires_free_or_quota_backed"],
                        label="requires_free_or_quota_backed",
                    ),
                )
            )

        object.__setattr__(self, "authorization_sha256", digest)
        object.__setattr__(self, "main_sha", _require_git_sha(base["main_sha"], "main_sha"))
        object.__setattr__(self, "main_tree", _require_git_sha(base["main_tree"], "main_tree"))
        object.__setattr__(
            self,
            "dependency_lock_sha256",
            _require_sha256(runtime["dependency_lock_sha256"], "dependency_lock_sha256"),
        )
        object.__setattr__(
            self,
            "required_gpu_count",
            _require_positive_int(runtime["required_gpu_count"], "required_gpu_count"),
        )
        object.__setattr__(
            self,
            "smoke_probe_id",
            _require_text(runtime["smoke_probe_id"], label="smoke_probe_id"),
        )
        object.__setattr__(
            self,
            "smoke_probe_version",
            _require_text(runtime["smoke_probe_version"], label="smoke_probe_version"),
        )
        object.__setattr__(self, "providers", tuple(providers))

    def provider_for(self, provider: str, flavor: str) -> AuthorizedRuntimeProvider:
        """Return the exact provider authorization or fail closed."""
        matches = [
            row
            for row in self.providers
            if row.provider == provider and row.provider_flavor == flavor
        ]
        if len(matches) != 1:
            raise MRL0804RuntimeError("runtime provider/flavor is not exactly authorized")
        return matches[0]


@dataclass(frozen=True, slots=True)
class MRL0804RuntimeObservation:
    """Parser-validated exact observation bytes emitted by the hosted GPU probe."""

    canonical_bytes: bytes = field(repr=False)
    provider: str = field(init=False)
    provider_flavor: str = field(init=False)
    runner_class: RunnerClass = field(init=False)
    python_version: str = field(init=False)
    os_name: str = field(init=False)
    torch_version: str = field(init=False)
    cuda_available: bool = field(init=False)
    cuda_version: str = field(init=False)
    gpu_count: int = field(init=False)
    gpu_models: tuple[str, ...] = field(init=False)
    gpu_total_memory_bytes: tuple[int, ...] = field(init=False)
    dependency_lock_sha256: str = field(init=False)
    repository_sha: str = field(init=False)
    repository_tree: str = field(init=False)
    probe_id: str = field(init=False)
    probe_version: str = field(init=False)
    probe_source_sha256: str = field(init=False)
    network_accessed: bool = field(init=False)
    remote_code_allowed: bool = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="runtime observation")
        _require_exact_keys(
            document,
            {
                "cuda_available",
                "cuda_version",
                "dependency_lock_sha256",
                "gpu_count",
                "gpu_models",
                "gpu_total_memory_bytes",
                "network_accessed",
                "os_name",
                "probe_id",
                "probe_source_sha256",
                "probe_version",
                "provider",
                "provider_flavor",
                "python_version",
                "remote_code_allowed",
                "repository_sha",
                "repository_tree",
                "runner_class",
                "schema_version",
                "torch_version",
            },
            label="runtime observation",
        )
        if document["schema_version"] != _OBSERVATION_SCHEMA:
            raise MRL0804RuntimeError("runtime observation schema_version is invalid")
        runner_text = _require_text(document["runner_class"], label="runner_class")
        try:
            runner = RunnerClass(runner_text)
        except ValueError as exc:
            raise MRL0804RuntimeError("runtime observation runner_class is invalid") from exc

        gpu_count = _require_positive_int(document["gpu_count"], "gpu_count")
        model_values = _require_list(document["gpu_models"], label="gpu_models")
        memory_values = _require_list(
            document["gpu_total_memory_bytes"], label="gpu_total_memory_bytes"
        )
        gpu_models = tuple(_require_text(value, label="gpu_models[]") for value in model_values)
        gpu_memory = tuple(
            _require_positive_int(value, "gpu_total_memory_bytes[]") for value in memory_values
        )
        if len(gpu_models) != gpu_count or len(gpu_memory) != gpu_count:
            raise MRL0804RuntimeError("runtime observation GPU vectors must match gpu_count")

        object.__setattr__(self, "provider", _require_text(document["provider"], label="provider"))
        object.__setattr__(
            self,
            "provider_flavor",
            _require_text(document["provider_flavor"], label="provider_flavor"),
        )
        object.__setattr__(self, "runner_class", runner)
        object.__setattr__(
            self,
            "python_version",
            _require_text(document["python_version"], label="python_version"),
        )
        object.__setattr__(self, "os_name", _require_text(document["os_name"], label="os_name"))
        object.__setattr__(
            self, "torch_version", _require_text(document["torch_version"], label="torch_version")
        )
        object.__setattr__(
            self,
            "cuda_available",
            _require_bool(document["cuda_available"], label="cuda_available"),
        )
        object.__setattr__(
            self, "cuda_version", _require_text(document["cuda_version"], label="cuda_version")
        )
        object.__setattr__(self, "gpu_count", gpu_count)
        object.__setattr__(self, "gpu_models", gpu_models)
        object.__setattr__(self, "gpu_total_memory_bytes", gpu_memory)
        object.__setattr__(
            self,
            "dependency_lock_sha256",
            _require_sha256(document["dependency_lock_sha256"], "dependency_lock_sha256"),
        )
        object.__setattr__(
            self, "repository_sha", _require_git_sha(document["repository_sha"], "repository_sha")
        )
        object.__setattr__(
            self,
            "repository_tree",
            _require_git_sha(document["repository_tree"], "repository_tree"),
        )
        object.__setattr__(self, "probe_id", _require_text(document["probe_id"], label="probe_id"))
        object.__setattr__(
            self, "probe_version", _require_text(document["probe_version"], label="probe_version")
        )
        object.__setattr__(
            self,
            "probe_source_sha256",
            _require_sha256(document["probe_source_sha256"], "probe_source_sha256"),
        )
        object.__setattr__(
            self,
            "network_accessed",
            _require_bool(document["network_accessed"], label="network_accessed"),
        )
        object.__setattr__(
            self,
            "remote_code_allowed",
            _require_bool(document["remote_code_allowed"], label="remote_code_allowed"),
        )

    @property
    def observation_sha256(self) -> str:
        return hashlib.sha256(self.canonical_bytes).hexdigest()


@dataclass(frozen=True, slots=True)
class MRL0804RuntimeQualification:
    """Deterministic MRL-0804 output bundle assembled from genuine external evidence."""

    observation_bytes: bytes = field(repr=False)
    smoke_receipt_bytes: bytes = field(repr=False)
    runtime_identity_bytes: bytes = field(repr=False)
    qualification_receipt_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    runtime_identity_sha256: str
    qualification_receipt_sha256: str
    smoke_receipt_sha256: str
    evidence_sha256: str


def parse_mrl_0804_runtime_authorization(raw: bytes) -> MRL0804RuntimeAuthorization:
    """Parse the exact committed authorization artifact."""
    return MRL0804RuntimeAuthorization(raw)


def parse_mrl_0804_runtime_observation(raw: bytes) -> MRL0804RuntimeObservation:
    """Parse exact canonical observation bytes without granting trust."""
    return MRL0804RuntimeObservation(raw)


def qualify_mrl_0804_runtime(
    observation_raw: bytes,
    smoke_raw: bytes,
    *,
    authorization: MRL0804RuntimeAuthorization,
    repository_sha: str,
    repository_tree: str,
    dependency_lock_sha256: str,
    probe_source_sha256: str,
) -> MRL0804RuntimeQualification:
    """Validate one hosted runtime and build an untrusted MRL-0804 evidence candidate."""
    if type(authorization) is not MRL0804RuntimeAuthorization:
        raise MRL0804RuntimeError("authorization must be an exact MRL0804RuntimeAuthorization")
    repository_sha = _require_git_sha(repository_sha, "repository_sha")
    repository_tree = _require_git_sha(repository_tree, "repository_tree")
    dependency_lock_sha256 = _require_sha256(dependency_lock_sha256, "dependency_lock_sha256")
    probe_source_sha256 = _require_sha256(probe_source_sha256, "probe_source_sha256")

    observation = MRL0804RuntimeObservation(observation_raw)
    provider = authorization.provider_for(observation.provider, observation.provider_flavor)
    if observation.runner_class is not provider.runner_class:
        raise MRL0804RuntimeError("runtime runner_class does not match provider authorization")
    if (
        observation.repository_sha != repository_sha
        or observation.repository_tree != repository_tree
    ):
        raise MRL0804RuntimeError("runtime observation does not bind the exact repository identity")
    if observation.dependency_lock_sha256 != dependency_lock_sha256:
        raise MRL0804RuntimeError("runtime observation dependency lock does not match exact source")
    if dependency_lock_sha256 != authorization.dependency_lock_sha256:
        raise MRL0804RuntimeError("exact source dependency lock is outside authorization")
    if observation.probe_source_sha256 != probe_source_sha256:
        raise MRL0804RuntimeError("runtime observation probe source does not match exact source")
    if observation.probe_id != authorization.smoke_probe_id:
        raise MRL0804RuntimeError("runtime observation probe_id is outside authorization")
    if observation.probe_version != authorization.smoke_probe_version:
        raise MRL0804RuntimeError("runtime observation probe_version is outside authorization")
    if observation.gpu_count != authorization.required_gpu_count:
        raise MRL0804RuntimeError("runtime GPU count does not match authorization")
    if not observation.cuda_available:
        raise MRL0804RuntimeError("runtime observation requires CUDA availability")
    if observation.network_accessed:
        raise MRL0804RuntimeError("runtime qualification smoke must not access the network")
    if observation.remote_code_allowed:
        raise MRL0804RuntimeError("runtime qualification smoke must not allow remote code")

    try:
        smoke = TrainingRuntimeSmokeEvidence(smoke_raw)
        receipt = build_training_runtime_qualification_receipt(
            runner_class=observation.runner_class,
            python_version=observation.python_version,
            os_name=observation.os_name,
            gpu_model=observation.gpu_models[0],
            dependency_lock_sha256=observation.dependency_lock_sha256,
            repository_sha=observation.repository_sha,
            repository_tree=observation.repository_tree,
            probe_id=observation.probe_id,
            probe_version=observation.probe_version,
            network_accessed=observation.network_accessed,
            remote_code_allowed=observation.remote_code_allowed,
            smoke_evidence=smoke,
        )
    except TrainingRuntimeQualificationError as exc:
        raise MRL0804RuntimeError("runtime smoke evidence is invalid") from exc
    if not receipt.platform_qualified:
        raise MRL0804RuntimeError("runtime qualification receipt did not reach PASS")

    smoke_sha256 = smoke.artifact_sha256
    runtime_identity_bytes = canonical_json_bytes(
        {
            "authorization_sha256": authorization.authorization_sha256,
            "cuda_available": observation.cuda_available,
            "cuda_version": observation.cuda_version,
            "dependency_lock_sha256": observation.dependency_lock_sha256,
            "gpu_count": observation.gpu_count,
            "gpu_models": list(observation.gpu_models),
            "gpu_total_memory_bytes": list(observation.gpu_total_memory_bytes),
            "network_accessed": observation.network_accessed,
            "observation_sha256": observation.observation_sha256,
            "os_name": observation.os_name,
            "probe_id": observation.probe_id,
            "probe_source_sha256": observation.probe_source_sha256,
            "probe_version": observation.probe_version,
            "provider": observation.provider,
            "provider_flavor": observation.provider_flavor,
            "python_version": observation.python_version,
            "remote_code_allowed": observation.remote_code_allowed,
            "repository_sha": observation.repository_sha,
            "repository_tree": observation.repository_tree,
            "runner_class": observation.runner_class.value,
            "schema_version": _IDENTITY_SCHEMA,
            "smoke_receipt_sha256": smoke_sha256,
            "torch_version": observation.torch_version,
        }
    )
    runtime_identity_sha256 = hashlib.sha256(runtime_identity_bytes).hexdigest()
    qualification_receipt_bytes = canonical_json_bytes(receipt.to_dict())
    qualification_receipt_sha256 = hashlib.sha256(qualification_receipt_bytes).hexdigest()
    evidence_bytes = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _EXPECTED_KIND,
            "payload": {
                "network_accessed": False,
                "platform_qualified": True,
                "remote_code_allowed": False,
                "runtime_identity_sha256": runtime_identity_sha256,
                "runtime_qualification_receipt_sha256": qualification_receipt_sha256,
                "smoke_receipt_sha256": smoke_sha256,
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": runtime_identity_sha256,
            "task_id": _EXPECTED_TASK,
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != _EXPECTED_TASK or parsed.subject_sha256 != runtime_identity_sha256:
        raise MRL0804RuntimeError("produced real-preflight evidence failed semantic self-check")
    return MRL0804RuntimeQualification(
        observation_bytes=observation.canonical_bytes,
        smoke_receipt_bytes=smoke.canonical_bytes,
        runtime_identity_bytes=runtime_identity_bytes,
        qualification_receipt_bytes=qualification_receipt_bytes,
        evidence_bytes=evidence_bytes,
        runtime_identity_sha256=runtime_identity_sha256,
        qualification_receipt_sha256=qualification_receipt_sha256,
        smoke_receipt_sha256=smoke_sha256,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )


def verify_mrl_0804_runtime_bundle(
    observation_raw: bytes,
    smoke_raw: bytes,
    *,
    authorization: MRL0804RuntimeAuthorization,
    repository_sha: str,
    repository_tree: str,
    dependency_lock_sha256: str,
    probe_source_sha256: str,
    runtime_identity_bytes: bytes,
    qualification_receipt_bytes: bytes,
    evidence_bytes: bytes,
) -> MRL0804RuntimeQualification:
    """Recompute the bundle and require byte-identical supplied artifacts."""
    expected = qualify_mrl_0804_runtime(
        observation_raw,
        smoke_raw,
        authorization=authorization,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        dependency_lock_sha256=dependency_lock_sha256,
        probe_source_sha256=probe_source_sha256,
    )
    supplied = (
        ("runtime identity", runtime_identity_bytes, expected.runtime_identity_bytes),
        (
            "qualification receipt",
            qualification_receipt_bytes,
            expected.qualification_receipt_bytes,
        ),
        ("real-preflight evidence", evidence_bytes, expected.evidence_bytes),
    )
    for label, actual, wanted in supplied:
        if type(actual) is not bytes or actual != wanted:
            raise MRL0804RuntimeError(f"supplied {label} does not match deterministic output")
    return expected


def _validate_authorization(document: dict[str, object]) -> None:
    _require_exact_keys(
        document,
        {
            "authorization_id",
            "authorization_state",
            "authorized_base",
            "experiment_id",
            "issue_number",
            "network_boundary",
            "policy",
            "runtime_policy",
            "schema_version",
            "scope",
            "task_id",
        },
        label="authorization",
    )
    if document["schema_version"] != _AUTH_SCHEMA:
        raise MRL0804RuntimeError("authorization schema_version is invalid")
    if document["authorization_state"] != "AUTHORIZED":
        raise MRL0804RuntimeError("authorization_state must be exactly AUTHORIZED")
    if document["task_id"] != _EXPECTED_TASK:
        raise MRL0804RuntimeError("authorization task_id is invalid")
    if document["issue_number"] != 410:
        raise MRL0804RuntimeError("authorization issue_number is invalid")
    if document["scope"] != "MRL-0804_RUNTIME_GPU_QUALIFICATION_ONLY":
        raise MRL0804RuntimeError("authorization scope is invalid")
    if document["experiment_id"] != "mesc-experiment-0-foundation-tournament":
        raise MRL0804RuntimeError("authorization experiment_id is invalid")

    base = _require_object(document["authorized_base"], label="authorized_base")
    _require_exact_keys(
        base,
        {
            "main_sha",
            "main_tree",
            "post_merge_ci_run",
            "post_merge_ci_success",
            "post_merge_codeql_run",
            "post_merge_codeql_success",
        },
        label="authorized_base",
    )
    _require_git_sha(base["main_sha"], "main_sha")
    _require_git_sha(base["main_tree"], "main_tree")
    _require_positive_int(base["post_merge_ci_run"], "post_merge_ci_run")
    _require_positive_int(base["post_merge_codeql_run"], "post_merge_codeql_run")
    if _require_bool(base["post_merge_ci_success"], label="post_merge_ci_success") is not True:
        raise MRL0804RuntimeError("post_merge_ci_success must be true")
    if (
        _require_bool(base["post_merge_codeql_success"], label="post_merge_codeql_success")
        is not True
    ):
        raise MRL0804RuntimeError("post_merge_codeql_success must be true")

    boundary = _require_object(document["network_boundary"], label="network_boundary")
    _require_exact_keys(
        boundary,
        {"remote_code_allowed", "setup_network_may_precede_smoke", "smoke_network_accessed"},
        label="network_boundary",
    )
    if _require_bool(boundary["remote_code_allowed"], label="remote_code_allowed"):
        raise MRL0804RuntimeError("authorization must forbid remote code")
    if not _require_bool(
        boundary["setup_network_may_precede_smoke"], label="setup_network_may_precede_smoke"
    ):
        raise MRL0804RuntimeError("authorization must explicitly separate setup network")
    if _require_bool(boundary["smoke_network_accessed"], label="smoke_network_accessed"):
        raise MRL0804RuntimeError("authorization must forbid smoke network access")

    policy = _require_object(document["policy"], label="policy")
    _require_exact_keys(
        policy,
        {
            "experiment_scientific_execution_authorized",
            "inference_authorized",
            "model_loading_authorized",
            "paid_hardware_fallback_authorized",
            "production_trust_registry_mutation_authorized",
            "tokenizer_loading_authorized",
            "training_authorized",
        },
        label="policy",
    )
    if any(_require_bool(value, label=f"policy.{key}") for key, value in policy.items()):
        raise MRL0804RuntimeError("MRL-0804 authorization policy must contain only false grants")

    runtime = _require_object(document["runtime_policy"], label="runtime_policy")
    _require_exact_keys(
        runtime,
        {
            "dependency_lock_sha256",
            "providers",
            "required_gpu_count",
            "smoke_probe_id",
            "smoke_probe_version",
        },
        label="runtime_policy",
    )
    _require_sha256(runtime["dependency_lock_sha256"], "dependency_lock_sha256")
    _require_positive_int(runtime["required_gpu_count"], "required_gpu_count")
    _require_text(runtime["smoke_probe_id"], label="smoke_probe_id")
    _require_text(runtime["smoke_probe_version"], label="smoke_probe_version")
    providers = _require_list(runtime["providers"], label="runtime_policy.providers")
    if not providers:
        raise MRL0804RuntimeError("runtime authorization requires at least one provider")
    seen: set[tuple[str, str]] = set()
    for index, row_value in enumerate(providers):
        row = _require_object(row_value, label=f"runtime_policy.providers[{index}]")
        _require_exact_keys(
            row,
            {"provider", "provider_flavor", "requires_free_or_quota_backed", "runner_class"},
            label=f"runtime_policy.providers[{index}]",
        )
        provider = _require_text(row["provider"], label="provider")
        flavor = _require_text(row["provider_flavor"], label="provider_flavor")
        _require_bool(row["requires_free_or_quota_backed"], label="requires_free_or_quota_backed")
        runner = _require_text(row["runner_class"], label="runner_class")
        try:
            RunnerClass(runner)
        except ValueError as exc:
            raise MRL0804RuntimeError("authorization provider runner_class is invalid") from exc
        identity = (provider, flavor)
        if identity in seen:
            raise MRL0804RuntimeError("authorization provider/flavor identities must be unique")
        seen.add(identity)


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0804RuntimeError(f"{label} must be non-empty exact bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, MRL0804RuntimeError):
            raise
        raise MRL0804RuntimeError(f"{label} is not valid strict JSON") from exc
    if type(value) is not dict:
        raise MRL0804RuntimeError(f"{label} must be one JSON object")
    document = cast(dict[str, object], value)
    try:
        canonical = canonical_json_bytes(document)
    except (TypeError, ValueError, RecursionError) as exc:
        raise MRL0804RuntimeError(f"{label} cannot be canonicalized") from exc
    if canonical != raw:
        raise MRL0804RuntimeError(f"{label} bytes are not canonical JSON")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0804RuntimeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise MRL0804RuntimeError(f"non-finite JSON constant is prohibited: {value}")


def _require_exact_keys(value: dict[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise MRL0804RuntimeError(f"{label} must contain the exact canonical key set")


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0804RuntimeError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _require_list(value: object, *, label: str) -> list[object]:
    if type(value) is not list:
        raise MRL0804RuntimeError(f"{label} must be a list")
    return cast(list[object], value)


def _require_text(value: object, *, label: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip():
        raise MRL0804RuntimeError(f"{label} must be exact non-empty text")
    return value


def _require_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise MRL0804RuntimeError(f"{label} must be an exact boolean")
    return value


def _require_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0804RuntimeError(f"{label} must be lowercase SHA-256")
    return value


def _require_git_sha(value: object, label: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0804RuntimeError(f"{label} must be lowercase 40-hex Git identity")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0804RuntimeError(f"{label} must be a positive integer")
    return value
