"""Fail-closed MESC training runtime-qualification receipt producer.

Observes or accepts injected local runtime facts and emits a content-addressed receipt
usable as ``runtime_qualification_sha256``. This module does not invent GPU identity,
does not authorize training, and does not treat package installation as PLATFORM_QUALIFIED.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.modelkit.manifests import RunnerClass
from medscale.reproducibility import content_hash

RuntimeQualificationDisposition = Literal["BLOCKED", "PASS"]
SmokeDisposition = Literal["SKIPPED", "PASS", "FAIL"]

_PROGRAM_VERSION: Final = "MESC-TRAINING-RUNTIME-QUALIFICATION-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)


class TrainingRuntimeQualificationError(ValueError):
    """Raised when a runtime-qualification receipt cannot be constructed fail-closed."""


@dataclass(frozen=True, slots=True)
class TrainingRuntimeQualificationReceipt:
    """Content-addressed local runtime observation for training launch binding."""

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
    smoke_disposition: SmokeDisposition
    smoke_receipt_sha256: str | None
    platform_qualified: bool
    blockers: tuple[str, ...]
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise TrainingRuntimeQualificationError(
                f"program_version must be exactly {_PROGRAM_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "PASS"):
            raise TrainingRuntimeQualificationError("disposition is invalid")
        if not isinstance(self.runner_class, RunnerClass):
            raise TrainingRuntimeQualificationError("runner_class must be a RunnerClass")
        for field, value in (
            ("python_version", self.python_version),
            ("os_name", self.os_name),
            ("gpu_model", self.gpu_model),
            ("probe_id", self.probe_id),
            ("probe_version", self.probe_version),
        ):
            if not isinstance(value, str) or not value.strip():
                raise TrainingRuntimeQualificationError(f"{field} must be a non-empty string")
        _require_sha256(self.dependency_lock_sha256, field="dependency_lock_sha256")
        _require_git_sha(self.repository_sha, field="repository_sha")
        _require_git_sha(self.repository_tree, field="repository_tree")
        if type(self.network_accessed) is not bool:
            raise TrainingRuntimeQualificationError("network_accessed must be a bool")
        if type(self.remote_code_allowed) is not bool:
            raise TrainingRuntimeQualificationError("remote_code_allowed must be a bool")
        if type(self.platform_qualified) is not bool:
            raise TrainingRuntimeQualificationError("platform_qualified must be a bool")
        if self.smoke_disposition not in ("SKIPPED", "PASS", "FAIL"):
            raise TrainingRuntimeQualificationError("smoke_disposition is invalid")
        if self.smoke_receipt_sha256 is not None:
            _require_sha256(self.smoke_receipt_sha256, field="smoke_receipt_sha256")
        if self.disposition == "PASS" and self.blockers:
            raise TrainingRuntimeQualificationError("PASS receipts cannot retain blockers")
        if self.disposition == "BLOCKED" and not self.blockers:
            raise TrainingRuntimeQualificationError("BLOCKED receipts must record blockers")
        if self.disposition == "PASS" and (self.network_accessed or self.remote_code_allowed):
            raise TrainingRuntimeQualificationError(
                "PASS receipts forbid network access and remote code"
            )
        if self.platform_qualified:
            if self.disposition != "PASS":
                raise TrainingRuntimeQualificationError(
                    "platform_qualified requires disposition PASS"
                )
            if self.smoke_disposition != "PASS":
                raise TrainingRuntimeQualificationError(
                    "platform_qualified requires smoke_disposition PASS"
                )
            if self.smoke_receipt_sha256 is None:
                raise TrainingRuntimeQualificationError(
                    "platform_qualified requires smoke_receipt_sha256"
                )
        if self.smoke_disposition == "PASS" and self.smoke_receipt_sha256 is None:
            raise TrainingRuntimeQualificationError(
                "smoke_disposition PASS requires smoke_receipt_sha256"
            )
        if self.smoke_disposition == "SKIPPED" and self.smoke_receipt_sha256 is not None:
            raise TrainingRuntimeQualificationError(
                "smoke_disposition SKIPPED forbids smoke_receipt_sha256"
            )

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
    smoke_disposition: SmokeDisposition = "SKIPPED",
    smoke_receipt_sha256: str | None = None,
) -> TrainingRuntimeQualificationReceipt:
    """Build one fail-closed runtime-qualification receipt from observed facts."""
    if not isinstance(runner_class, RunnerClass):
        raise TrainingRuntimeQualificationError("runner_class must be a RunnerClass")
    for field, value in (
        ("python_version", python_version),
        ("os_name", os_name),
        ("gpu_model", gpu_model),
        ("probe_id", probe_id),
        ("probe_version", probe_version),
    ):
        if not isinstance(value, str) or not value.strip():
            raise TrainingRuntimeQualificationError(f"{field} must be a non-empty string")
    _require_sha256(dependency_lock_sha256, field="dependency_lock_sha256")
    _require_git_sha(repository_sha, field="repository_sha")
    _require_git_sha(repository_tree, field="repository_tree")
    if smoke_disposition not in ("SKIPPED", "PASS", "FAIL"):
        raise TrainingRuntimeQualificationError("smoke_disposition is invalid")
    if smoke_receipt_sha256 is not None:
        _require_sha256(smoke_receipt_sha256, field="smoke_receipt_sha256")
    if smoke_disposition == "PASS" and smoke_receipt_sha256 is None:
        raise TrainingRuntimeQualificationError(
            "smoke_disposition PASS requires smoke_receipt_sha256"
        )
    if smoke_disposition == "SKIPPED" and smoke_receipt_sha256 is not None:
        raise TrainingRuntimeQualificationError(
            "smoke_disposition SKIPPED forbids smoke_receipt_sha256"
        )

    blockers: list[str] = []
    if network_accessed:
        blockers.append("network_accessed must be false")
    if remote_code_allowed:
        blockers.append("remote_code_allowed must be false")
    if smoke_disposition == "FAIL":
        blockers.append("runtime smoke qualification failed")

    disposition: RuntimeQualificationDisposition = "BLOCKED" if blockers else "PASS"
    platform_qualified = (
        disposition == "PASS" and smoke_disposition == "PASS" and smoke_receipt_sha256 is not None
    )
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
        smoke_disposition=smoke_disposition,
        smoke_receipt_sha256=smoke_receipt_sha256,
        platform_qualified=platform_qualified,
        blockers=tuple(blockers),
    )


def _require_sha256(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingRuntimeQualificationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )


def _require_git_sha(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
        raise TrainingRuntimeQualificationError(
            f"{field} must be exactly 40 lowercase hex characters"
        )


__all__ = [
    "RuntimeQualificationDisposition",
    "SmokeDisposition",
    "TrainingRuntimeQualificationError",
    "TrainingRuntimeQualificationReceipt",
    "build_training_runtime_qualification_receipt",
]
