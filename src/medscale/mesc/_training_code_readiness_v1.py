"""Final repository training-code readiness audit for MESC.

This gate decides whether the repository-side training stack is complete enough to
declare ``TRAINING_CODE_READY``. It does not authorize real training, invent receipts,
download models, or claim MedScale Spec 012 admission readiness.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from medscale.mesc._training_orchestrator_v1 import hash_dependency_lock
from medscale.reproducibility import content_hash

TrainingCodeReadinessDisposition = Literal["BLOCKED", "TRAINING_CODE_READY"]

_AUDIT_VERSION: Final = "MESC-TRAINING-CODE-READINESS-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REQUIRED_MODULES: Final = (
    "medscale.mesc._training_readiness_v1",
    "medscale.mesc._training_launch_plan_v1",
    "medscale.mesc._training_dataset_qualification_v1",
    "medscale.mesc._training_example_contract_v1",
    "medscale.mesc._training_corpus_binding_v1",
    "medscale.mesc._training_local_asset_attestation_v1",
    "medscale.mesc._training_hf_safetensors_identity_v1",
    "medscale.mesc._training_executor_v1",
    "medscale.mesc._training_hf_local_sft_backend_v1",
    "medscale.mesc._training_orchestrator_v1",
    "medscale.mesc._training_runtime_qualification_v1",
    "medscale.mesc._training_authorization_receipt_v1",
)
_REQUIRED_SPECS: Final = (
    "specs/mesc-training-readiness-v1/README.md",
    "specs/mesc-training-launch-plan-v1/README.md",
    "specs/mesc-training-dataset-qualification-v1/README.md",
    "specs/mesc-training-example-contract-v1/README.md",
    "specs/mesc-training-corpus-binding-v1/README.md",
    "specs/mesc-training-local-asset-attestation-v1/README.md",
    "specs/mesc-hf-safetensors-weight-identity-v1/README.md",
    "specs/mesc-training-executor-v1/README.md",
    "specs/mesc-hf-local-sft-backend-v1/README.md",
    "specs/mesc-hf-sft-dependency-lock-v1/README.md",
    "specs/mesc-training-orchestrator-v1/README.md",
    "specs/mesc-training-runtime-qualification-v1/README.md",
    "specs/mesc-training-authorization-receipt-v1/README.md",
)
_EXPECTED_TRAINING_PINS: Final = (
    "accelerate==1.14.0",
    "bitsandbytes==0.50.1",
    "datasets==5.0.1",
    "peft==0.20.0",
    "torch==2.13.0",
    "transformers==5.15.1",
    "trl==1.10.0",
)


class TrainingCodeReadinessError(ValueError):
    """Raised when the audit cannot be constructed fail-closed."""


@dataclass(frozen=True, slots=True)
class TrainingCodeReadinessReport:
    """Deterministic repository-side training-code readiness audit."""

    disposition: TrainingCodeReadinessDisposition
    repository_root: str
    dependency_lock_sha256: str | None
    training_extra_pins: tuple[str, ...]
    present_modules: tuple[str, ...]
    missing_modules: tuple[str, ...]
    present_specs: tuple[str, ...]
    missing_specs: tuple[str, ...]
    blockers: tuple[str, ...]
    real_training_authorized: bool
    medscale_spec_012_admission_readiness: str
    audit_version: str = _AUDIT_VERSION

    def __post_init__(self) -> None:
        if self.audit_version != _AUDIT_VERSION:
            raise TrainingCodeReadinessError(f"audit_version must be exactly {_AUDIT_VERSION}")
        if self.disposition not in ("BLOCKED", "TRAINING_CODE_READY"):
            raise TrainingCodeReadinessError("disposition is invalid")
        if not self.repository_root.strip():
            raise TrainingCodeReadinessError("repository_root must be non-empty")
        if self.dependency_lock_sha256 is not None and (
            not isinstance(self.dependency_lock_sha256, str)
            or _SHA256.fullmatch(self.dependency_lock_sha256) is None
        ):
            raise TrainingCodeReadinessError(
                "dependency_lock_sha256 must be exactly 64 lowercase hex characters"
            )
        if type(self.real_training_authorized) is not bool:
            raise TrainingCodeReadinessError("real_training_authorized must be a bool")
        if self.medscale_spec_012_admission_readiness != "NOT_READY":
            raise TrainingCodeReadinessError(
                "medscale_spec_012_admission_readiness must remain NOT_READY in V1"
            )
        if self.disposition == "TRAINING_CODE_READY":
            if self.blockers:
                raise TrainingCodeReadinessError("TRAINING_CODE_READY cannot retain blockers")
            if self.missing_modules or self.missing_specs:
                raise TrainingCodeReadinessError(
                    "TRAINING_CODE_READY cannot retain missing modules or specs"
                )
            if self.present_modules != _REQUIRED_MODULES:
                raise TrainingCodeReadinessError(
                    "TRAINING_CODE_READY must present the exact required module set"
                )
            if self.present_specs != _REQUIRED_SPECS:
                raise TrainingCodeReadinessError(
                    "TRAINING_CODE_READY must present the exact required spec set"
                )
            if self.training_extra_pins != _EXPECTED_TRAINING_PINS:
                raise TrainingCodeReadinessError(
                    "TRAINING_CODE_READY must bind the exact training-hf-sft pins"
                )
            if self.dependency_lock_sha256 is None:
                raise TrainingCodeReadinessError(
                    "TRAINING_CODE_READY requires an observed dependency_lock_sha256"
                )
        if self.disposition == "BLOCKED" and not self.blockers:
            raise TrainingCodeReadinessError("BLOCKED audits must record blockers")
        if self.real_training_authorized:
            raise TrainingCodeReadinessError("V1 audit must not authorize real training")

    @property
    def audit_sha256(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "audit_version": self.audit_version,
            "blockers": list(self.blockers),
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "disposition": self.disposition,
            "medscale_spec_012_admission_readiness": self.medscale_spec_012_admission_readiness,
            "missing_modules": list(self.missing_modules),
            "missing_specs": list(self.missing_specs),
            "present_modules": list(self.present_modules),
            "present_specs": list(self.present_specs),
            "real_training_authorized": self.real_training_authorized,
            "repository_root": self.repository_root,
            "training_extra_pins": list(self.training_extra_pins),
        }


def audit_training_code_readiness(*, repository_root: Path) -> TrainingCodeReadinessReport:
    """Audit whether the repository training stack is TRAINING_CODE_READY."""
    if not isinstance(repository_root, Path):
        raise TrainingCodeReadinessError("repository_root must be an exact pathlib.Path")
    if not repository_root.is_dir():
        raise TrainingCodeReadinessError("repository_root must be an existing directory")

    blockers: list[str] = []
    present_modules: list[str] = []
    missing_modules: list[str] = []
    for module_name in _REQUIRED_MODULES:
        module_path = _module_source_path(repository_root, module_name)
        if module_path.is_file() and not module_path.is_symlink():
            present_modules.append(module_name)
        else:
            missing_modules.append(module_name)
            blockers.append(f"missing module: {module_name}")

    present_specs: list[str] = []
    missing_specs: list[str] = []
    for relative in _REQUIRED_SPECS:
        path = repository_root / relative
        if path.is_file() and not path.is_symlink():
            present_specs.append(relative)
        else:
            missing_specs.append(relative)
            blockers.append(f"missing spec: {relative}")

    training_pins: tuple[str, ...] = ()
    try:
        training_pins = _read_training_extra_pins(repository_root / "pyproject.toml")
        if training_pins != _EXPECTED_TRAINING_PINS:
            blockers.append("training-hf-sft pins do not match the canonical lock gate")
    except TrainingCodeReadinessError as exc:
        blockers.append(str(exc))

    dependency_lock_sha256: str | None = None
    try:
        dependency_lock_sha256 = hash_dependency_lock(repository_root / "uv.lock")
    except Exception as exc:
        blockers.append(f"dependency lock observation failed: {exc}")

    disposition: TrainingCodeReadinessDisposition = "BLOCKED" if blockers else "TRAINING_CODE_READY"
    return TrainingCodeReadinessReport(
        disposition=disposition,
        repository_root=repository_root.as_posix(),
        dependency_lock_sha256=dependency_lock_sha256,
        training_extra_pins=training_pins,
        present_modules=tuple(present_modules),
        missing_modules=tuple(missing_modules),
        present_specs=tuple(present_specs),
        missing_specs=tuple(missing_specs),
        blockers=tuple(blockers),
        real_training_authorized=False,
        medscale_spec_012_admission_readiness="NOT_READY",
    )


def _module_source_path(repository_root: Path, module_name: str) -> Path:
    relative = Path("src", *module_name.split(".")).with_suffix(".py")
    return repository_root / relative


def _read_training_extra_pins(pyproject_path: Path) -> tuple[str, ...]:
    try:
        if pyproject_path.is_symlink() or not pyproject_path.is_file():
            raise TrainingCodeReadinessError("pyproject.toml must be a regular file")
        with pyproject_path.open("rb") as handle:
            document = cast(dict[str, object], tomllib.load(handle))
        project = cast(dict[str, object], document["project"])
        dependencies = cast(list[object], project.get("dependencies", []))
        if dependencies:
            raise TrainingCodeReadinessError("default project.dependencies must remain empty")
        optional = cast(dict[str, object], project.get("optional-dependencies", {}))
        training = cast(list[str], optional.get("training-hf-sft", []))
        if not training:
            raise TrainingCodeReadinessError("training-hf-sft optional extra is missing")
        return tuple(training)
    except TrainingCodeReadinessError:
        raise
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, AttributeError) as exc:
        raise TrainingCodeReadinessError("pyproject.toml is invalid") from exc


__all__ = [
    "TrainingCodeReadinessDisposition",
    "TrainingCodeReadinessError",
    "TrainingCodeReadinessReport",
    "audit_training_code_readiness",
]
