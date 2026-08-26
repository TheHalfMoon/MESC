"""Fail-closed MESC training runtime-qualification evidence and receipt producer.

Runtime identity may be observed without smoke evidence, but platform qualification is
possible only from parser-validated canonical smoke-evidence bytes bound to the exact
runtime facts. This module performs no model loading, provider access, GPU work, network
access, or training.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Literal

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.modelkit.manifests import RunnerClass
from medscale.reproducibility import content_hash

RuntimeQualificationDisposition = Literal["BLOCKED", "OBSERVED", "PASS"]
SmokeDisposition = Literal["SKIPPED", "PASS", "FAIL"]
SmokeEvidenceDisposition = Literal["PASS", "FAIL"]

_PROGRAM_VERSION: Final = "MESC-TRAINING-RUNTIME-QUALIFICATION-V1"
_SMOKE_KIND: Final = "mesc.training_runtime_smoke.v1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_SMOKE_KEYS: Final = frozenset(
    {
        "dependency_lock_sha256",
        "disposition",
        "gpu_model",
        "kind",
        "network_accessed",
        "os_name",
        "probe_id",
        "probe_version",
        "python_version",
        "remote_code_allowed",
        "repository_sha",
        "repository_tree",
        "runner_class",
    }
)


class TrainingRuntimeQualificationError(ValueError):
    """Raised when runtime evidence or a qualification receipt is invalid."""


@dataclass(frozen=True, slots=True)
class TrainingRuntimeSmokeEvidence:
    """Canonical, content-addressed runtime smoke evidence parsed from exact bytes."""

    canonical_bytes: bytes = field(repr=False)
    disposition: SmokeEvidenceDisposition = field(init=False)
    runner_class: RunnerClass = field(init=False)
    python_version: str = field(init=False)
    os_name: str = field(init=False)
    gpu_model: str = field(init=False)
    dependency_lock_sha256: str = field(init=False)
    repository_sha: str = field(init=False)
    repository_tree: str = field(init=False)
    probe_id: str = field(init=False)
    probe_version: str = field(init=False)
    network_accessed: bool = field(init=False)
    remote_code_allowed: bool = field(init=False)

    def __post_init__(self) -> None:
        if type(self.canonical_bytes) is not bytes or not self.canonical_bytes:
            raise TrainingRuntimeQualificationError(
                "runtime smoke evidence must be non-empty exact bytes"
            )
        payload = _parse_smoke_payload(self.canonical_bytes)
        try:
            if canonical_json_bytes(payload) != self.canonical_bytes:
                raise TrainingRuntimeQualificationError(
                    "runtime smoke evidence bytes are not canonical JSON"
                )
        except TrainingRuntimeQualificationError:
            raise
        except (TypeError, ValueError, RecursionError) as exc:
            raise TrainingRuntimeQualificationError(
                "runtime smoke evidence cannot be canonicalized"
            ) from exc

        disposition = _require_exact_text(payload["disposition"], field="disposition")
        if disposition not in ("PASS", "FAIL"):
            raise TrainingRuntimeQualificationError(
                "runtime smoke disposition must be exactly PASS or FAIL"
            )
        runner_value = _require_exact_text(payload["runner_class"], field="runner_class")
        try:
            runner_class = RunnerClass(runner_value)
        except ValueError as exc:
            raise TrainingRuntimeQualificationError(
                "runtime smoke runner_class is invalid"
            ) from exc

        python_version = _require_exact_text(payload["python_version"], field="python_version")
        os_name = _require_exact_text(payload["os_name"], field="os_name")
        gpu_model = _require_exact_text(payload["gpu_model"], field="gpu_model")
        dependency_lock_sha256 = _require_sha256(
            payload["dependency_lock_sha256"], field="dependency_lock_sha256"
        )
        repository_sha = _require_git_sha(payload["repository_sha"], field="repository_sha")
        repository_tree = _require_git_sha(payload["repository_tree"], field="repository_tree")
        probe_id = _require_exact_text(payload["probe_id"], field="probe_id")
        probe_version = _require_exact_text(payload["probe_version"], field="probe_version")
        network_accessed = _require_exact_bool(
            payload["network_accessed"], field="network_accessed"
        )
        remote_code_allowed = _require_exact_bool(
            payload["remote_code_allowed"], field="remote_code_allowed"
        )

        object.__setattr__(self, "disposition", disposition)
        object.__setattr__(self, "runner_class", runner_class)
        object.__setattr__(self, "python_version", python_version)
        object.__setattr__(self, "os_name", os_name)
        object.__setattr__(self, "gpu_model", gpu_model)
        object.__setattr__(self, "dependency_lock_sha256", dependency_lock_sha256)
        object.__setattr__(self, "repository_sha", repository_sha)
        object.__setattr__(self, "repository_tree", repository_tree)
        object.__setattr__(self, "probe_id", probe_id)
        object.__setattr__(self, "probe_version", probe_version)
        object.__setattr__(self, "network_accessed", network_accessed)
        object.__setattr__(self, "remote_code_allowed", remote_code_allowed)

    @property
    def artifact_sha256(self) -> str:
        """Return SHA-256 over the exact canonical evidence bytes."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the validated semantic smoke payload."""
        return {
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "disposition": self.disposition,
            "gpu_model": self.gpu_model,
            "kind": _SMOKE_KIND,
            "network_accessed": self.network_accessed,
            "os_name": self.os_name,
            "probe_id": self.probe_id,
            "probe_version": self.probe_version,
            "python_version": self.python_version,
            "remote_code_allowed": self.remote_code_allowed,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "runner_class": self.runner_class.value,
        }


@dataclass(frozen=True, slots=True)
class TrainingRuntimeQualificationReceipt:
    """Content-addressed local runtime observation or validated qualification."""

    disposition: RuntimeQualificationDisposition
    runner_class: RunnerClass
    python_version: str
    os_name: str
    gpu_model: str
    dependency_lock_sha256: str
    repository_sha: str
    repository_tree: str
    probe_id: str
    probe_version: str
    network_accessed: bool
    remote_code_allowed: bool
    smoke_evidence: TrainingRuntimeSmokeEvidence | None
    blockers: tuple[str, ...]
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise TrainingRuntimeQualificationError(
                f"program_version must be exactly {_PROGRAM_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "OBSERVED", "PASS"):
            raise TrainingRuntimeQualificationError("disposition is invalid")
        if type(self.runner_class) is not RunnerClass:
            raise TrainingRuntimeQualificationError("runner_class must be an exact RunnerClass")
        for field_name, value in (
            ("python_version", self.python_version),
            ("os_name", self.os_name),
            ("gpu_model", self.gpu_model),
            ("probe_id", self.probe_id),
            ("probe_version", self.probe_version),
        ):
            _require_exact_text(value, field=field_name)
        _require_sha256(self.dependency_lock_sha256, field="dependency_lock_sha256")
        _require_git_sha(self.repository_sha, field="repository_sha")
        _require_git_sha(self.repository_tree, field="repository_tree")
        _require_exact_bool(self.network_accessed, field="network_accessed")
        _require_exact_bool(self.remote_code_allowed, field="remote_code_allowed")
        if (
            self.smoke_evidence is not None
            and type(self.smoke_evidence) is not TrainingRuntimeSmokeEvidence
        ):
            raise TrainingRuntimeQualificationError(
                "smoke_evidence must be an exact TrainingRuntimeSmokeEvidence"
            )
        if type(self.blockers) is not tuple:
            raise TrainingRuntimeQualificationError("blockers must be an exact tuple")
        if any(type(item) is not str or not item for item in self.blockers):
            raise TrainingRuntimeQualificationError(
                "blockers must contain exact non-empty strings only"
            )

        if self.disposition == "PASS":
            if self.blockers:
                raise TrainingRuntimeQualificationError("PASS receipts cannot retain blockers")
            if self.network_accessed or self.remote_code_allowed:
                raise TrainingRuntimeQualificationError(
                    "PASS receipts forbid network access and remote code"
                )
            if self.smoke_evidence is None or self.smoke_evidence.disposition != "PASS":
                raise TrainingRuntimeQualificationError(
                    "PASS requires validated PASS smoke evidence"
                )
            mismatch = _smoke_binding_mismatches(self, self.smoke_evidence)
            if mismatch:
                raise TrainingRuntimeQualificationError(
                    "PASS smoke evidence does not bind the exact runtime facts"
                )
            if self.smoke_evidence.network_accessed or self.smoke_evidence.remote_code_allowed:
                raise TrainingRuntimeQualificationError(
                    "PASS smoke evidence forbids network access and remote code"
                )
        elif self.disposition == "OBSERVED":
            if self.blockers:
                raise TrainingRuntimeQualificationError("OBSERVED receipts cannot retain blockers")
            if self.smoke_evidence is not None:
                raise TrainingRuntimeQualificationError("OBSERVED receipts forbid smoke evidence")
            if self.network_accessed or self.remote_code_allowed:
                raise TrainingRuntimeQualificationError(
                    "OBSERVED receipts forbid network access and remote code"
                )
        elif not self.blockers:
            raise TrainingRuntimeQualificationError("BLOCKED receipts must record blockers")

    @property
    def platform_qualified(self) -> bool:
        """Whether this receipt contains validated, exact-bound PASS smoke evidence."""
        return self.disposition == "PASS"

    @property
    def smoke_disposition(self) -> SmokeDisposition:
        if self.smoke_evidence is None:
            return "SKIPPED"
        return self.smoke_evidence.disposition

    @property
    def smoke_receipt_sha256(self) -> str | None:
        if self.smoke_evidence is None:
            return None
        return self.smoke_evidence.artifact_sha256

    @property
    def receipt_sha256(self) -> str:
        """Return the opaque digest bound into readiness/launch plans."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "blockers": list(self.blockers),
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "disposition": self.disposition,
            "gpu_model": self.gpu_model,
            "network_accessed": self.network_accessed,
            "os_name": self.os_name,
            "platform_qualified": self.platform_qualified,
            "probe_id": self.probe_id,
            "probe_version": self.probe_version,
            "program_version": self.program_version,
            "python_version": self.python_version,
            "remote_code_allowed": self.remote_code_allowed,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "runner_class": self.runner_class.value,
            "smoke_disposition": self.smoke_disposition,
            "smoke_receipt_sha256": self.smoke_receipt_sha256,
        }


def build_training_runtime_qualification_receipt(
    *,
    runner_class: RunnerClass,
    python_version: str,
    os_name: str,
    gpu_model: str,
    dependency_lock_sha256: str,
    repository_sha: str,
    repository_tree: str,
    probe_id: str,
    probe_version: str,
    network_accessed: bool = False,
    remote_code_allowed: bool = False,
    smoke_evidence: TrainingRuntimeSmokeEvidence | None = None,
) -> TrainingRuntimeQualificationReceipt:
    """Build one fail-closed receipt from observed facts and optional validated smoke evidence."""
    if type(runner_class) is not RunnerClass:
        raise TrainingRuntimeQualificationError("runner_class must be an exact RunnerClass")
    for field_name, value in (
        ("python_version", python_version),
        ("os_name", os_name),
        ("gpu_model", gpu_model),
        ("probe_id", probe_id),
        ("probe_version", probe_version),
    ):
        _require_exact_text(value, field=field_name)
    _require_sha256(dependency_lock_sha256, field="dependency_lock_sha256")
    _require_git_sha(repository_sha, field="repository_sha")
    _require_git_sha(repository_tree, field="repository_tree")
    _require_exact_bool(network_accessed, field="network_accessed")
    _require_exact_bool(remote_code_allowed, field="remote_code_allowed")
    if smoke_evidence is not None and type(smoke_evidence) is not TrainingRuntimeSmokeEvidence:
        raise TrainingRuntimeQualificationError(
            "smoke_evidence must be an exact TrainingRuntimeSmokeEvidence"
        )

    blockers: list[str] = []
    if network_accessed:
        blockers.append("network_accessed must be false")
    if remote_code_allowed:
        blockers.append("remote_code_allowed must be false")
    if smoke_evidence is not None:
        for field_name in _smoke_binding_mismatches_from_values(
            runner_class=runner_class,
            python_version=python_version,
            os_name=os_name,
            gpu_model=gpu_model,
            dependency_lock_sha256=dependency_lock_sha256,
            repository_sha=repository_sha,
            repository_tree=repository_tree,
            probe_id=probe_id,
            probe_version=probe_version,
            network_accessed=network_accessed,
            remote_code_allowed=remote_code_allowed,
            evidence=smoke_evidence,
        ):
            blockers.append(f"runtime smoke {field_name} does not match observed runtime")
        if smoke_evidence.disposition == "FAIL":
            blockers.append("runtime smoke qualification failed")
        if smoke_evidence.network_accessed:
            blockers.append("runtime smoke evidence accessed the network")
        if smoke_evidence.remote_code_allowed:
            blockers.append("runtime smoke evidence allowed remote code")

    if blockers:
        disposition: RuntimeQualificationDisposition = "BLOCKED"
    elif smoke_evidence is None:
        disposition = "OBSERVED"
    else:
        disposition = "PASS"

    return TrainingRuntimeQualificationReceipt(
        disposition=disposition,
        runner_class=runner_class,
        python_version=python_version.strip(),
        os_name=os_name.strip(),
        gpu_model=gpu_model.strip(),
        dependency_lock_sha256=dependency_lock_sha256,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        probe_id=probe_id.strip(),
        probe_version=probe_version.strip(),
        network_accessed=network_accessed,
        remote_code_allowed=remote_code_allowed,
        smoke_evidence=smoke_evidence,
        blockers=tuple(blockers),
    )


def _parse_smoke_payload(payload_bytes: bytes) -> dict[str, object]:
    try:
        text = payload_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TrainingRuntimeQualificationError(
            "runtime smoke evidence is not valid UTF-8"
        ) from exc
    try:
        value = json.loads(text, object_pairs_hook=_reject_duplicate_pairs)
    except TrainingRuntimeQualificationError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError, TypeError) as exc:
        raise TrainingRuntimeQualificationError("runtime smoke evidence is not valid JSON") from exc
    if type(value) is not dict:
        raise TrainingRuntimeQualificationError("runtime smoke evidence must be one JSON object")
    if set(value) != _SMOKE_KEYS:
        raise TrainingRuntimeQualificationError(
            "runtime smoke evidence must contain exactly the canonical field set"
        )
    if value.get("kind") != _SMOKE_KIND:
        raise TrainingRuntimeQualificationError(f"runtime smoke kind must be exactly {_SMOKE_KIND}")
    for key, item in value.items():
        if type(item) is float:
            raise TrainingRuntimeQualificationError(
                f"runtime smoke field {key} must not use JSON float encoding"
            )
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrainingRuntimeQualificationError(
                f"runtime smoke evidence contains duplicate key: {key}"
            )
        result[key] = value
    return result


def _smoke_binding_mismatches(
    receipt: TrainingRuntimeQualificationReceipt,
    evidence: TrainingRuntimeSmokeEvidence,
) -> tuple[str, ...]:
    return _smoke_binding_mismatches_from_values(
        runner_class=receipt.runner_class,
        python_version=receipt.python_version,
        os_name=receipt.os_name,
        gpu_model=receipt.gpu_model,
        dependency_lock_sha256=receipt.dependency_lock_sha256,
        repository_sha=receipt.repository_sha,
        repository_tree=receipt.repository_tree,
        probe_id=receipt.probe_id,
        probe_version=receipt.probe_version,
        network_accessed=receipt.network_accessed,
        remote_code_allowed=receipt.remote_code_allowed,
        evidence=evidence,
    )


def _smoke_binding_mismatches_from_values(
    *,
    runner_class: RunnerClass,
    python_version: str,
    os_name: str,
    gpu_model: str,
    dependency_lock_sha256: str,
    repository_sha: str,
    repository_tree: str,
    probe_id: str,
    probe_version: str,
    network_accessed: bool,
    remote_code_allowed: bool,
    evidence: TrainingRuntimeSmokeEvidence,
) -> tuple[str, ...]:
    comparisons: tuple[tuple[str, object, object], ...] = (
        ("runner_class", evidence.runner_class, runner_class),
        ("python_version", evidence.python_version, python_version.strip()),
        ("os_name", evidence.os_name, os_name.strip()),
        ("gpu_model", evidence.gpu_model, gpu_model.strip()),
        ("dependency_lock_sha256", evidence.dependency_lock_sha256, dependency_lock_sha256),
        ("repository_sha", evidence.repository_sha, repository_sha),
        ("repository_tree", evidence.repository_tree, repository_tree),
        ("probe_id", evidence.probe_id, probe_id.strip()),
        ("probe_version", evidence.probe_version, probe_version.strip()),
        ("network_accessed", evidence.network_accessed, network_accessed),
        ("remote_code_allowed", evidence.remote_code_allowed, remote_code_allowed),
    )
    return tuple(
        field_name for field_name, observed, expected in comparisons if observed != expected
    )


def _require_exact_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise TrainingRuntimeQualificationError(f"{field} must be exact non-empty NUL-free text")
    return value.strip()


def _require_exact_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise TrainingRuntimeQualificationError(f"{field} must be an exact bool")
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TrainingRuntimeQualificationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


def _require_git_sha(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise TrainingRuntimeQualificationError(
            f"{field} must be exactly 40 lowercase hex characters"
        )
    return value


__all__ = [
    "RuntimeQualificationDisposition",
    "SmokeDisposition",
    "SmokeEvidenceDisposition",
    "TrainingRuntimeQualificationError",
    "TrainingRuntimeQualificationReceipt",
    "TrainingRuntimeSmokeEvidence",
    "build_training_runtime_qualification_receipt",
]
