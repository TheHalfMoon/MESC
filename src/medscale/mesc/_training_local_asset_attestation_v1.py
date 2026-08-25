"""Fail-closed attestation of already-local MESC training assets.

The corpus is verified directly. Model-weight verification is delegated to an explicitly
injected local verifier because the canonical ``weights_sha256`` contract does not define
a new filesystem-tree hashing algorithm. This module performs no network, model loading,
inference, or training.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Protocol

from medscale.mesc._training_corpus_binding_v1 import TrainingCorpusBindingReport
from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlan,
    TrainingRole,
    TrainingRunPlan,
)
from medscale.reproducibility import content_hash

LocalAssetDisposition = Literal["BLOCKED", "PASS"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_ATTESTATION_VERSION: Final = "MESC-TRAINING-LOCAL-ASSET-ATTESTATION-V1"
_CHUNK_SIZE: Final = 1024 * 1024


class TrainingLocalAssetAttestationError(ValueError):
    """Fail-closed local-asset attestation error."""


@dataclass(frozen=True, slots=True)
class LocalModelAssetObservation:
    """Identity receipt returned by one explicitly injected local model verifier."""

    role: TrainingRole
    model_id: str
    revision: str
    weights_sha256: str
    verifier_id: str
    verifier_version: str
    verifier_receipt_sha256: str
    network_accessed: bool
    remote_code_allowed: bool
    gated_terms_accepted: bool

    def __post_init__(self) -> None:
        if self.role not in ("compact", "reasoner"):
            raise TrainingLocalAssetAttestationError("role must be compact or reasoner")
        _require_text(self.model_id, field="model_id")
        if _GIT_SHA.fullmatch(self.revision) is None:
            raise TrainingLocalAssetAttestationError(
                "revision must be exactly 40 lowercase hex characters"
            )
        _require_sha256(self.weights_sha256, field="weights_sha256")
        _require_text(self.verifier_id, field="verifier_id")
        _require_text(self.verifier_version, field="verifier_version")
        _require_sha256(self.verifier_receipt_sha256, field="verifier_receipt_sha256")
        for bool_name, bool_value in (
            ("network_accessed", self.network_accessed),
            ("remote_code_allowed", self.remote_code_allowed),
            ("gated_terms_accepted", self.gated_terms_accepted),
        ):
            if type(bool_value) is not bool:
                raise TrainingLocalAssetAttestationError(f"{bool_name} must be a bool")


class LocalModelAssetVerifier(Protocol):
    """Backend-specific boundary for verification of already-local model assets."""

    def verify(
        self,
        *,
        role: TrainingRole,
        model_root: Path,
        run_plan: TrainingRunPlan,
    ) -> LocalModelAssetObservation: ...


@dataclass(frozen=True, slots=True)
class TrainingLocalAssetAttestationReport:
    """Deterministic proof that local assets match one exact launch run."""

    disposition: LocalAssetDisposition
    role: TrainingRole
    launch_plan_sha256: str
    run_plan_sha256: str
    corpus_binding_sha256: str
    training_dataset_sha256: str
    model_id: str
    revision: str
    expected_weights_sha256: str
    observed_weights_sha256: str | None
    model_verifier_id: str | None
    model_verifier_version: str | None
    model_verifier_receipt_sha256: str | None
    model_network_accessed: bool
    model_remote_code_allowed: bool
    model_gated_terms_accepted: bool
    expected_corpus_sha256: str
    observed_corpus_sha256: str | None
    expected_corpus_byte_count: int
    observed_corpus_byte_count: int | None
    blockers: tuple[str, ...]
    attestation_version: str = _ATTESTATION_VERSION

    def __post_init__(self) -> None:
        if self.attestation_version != _ATTESTATION_VERSION:
            raise TrainingLocalAssetAttestationError(
                f"attestation_version must be exactly {_ATTESTATION_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "PASS"):
            raise TrainingLocalAssetAttestationError("disposition must be BLOCKED or PASS")
        if self.role not in ("compact", "reasoner"):
            raise TrainingLocalAssetAttestationError("role must be compact or reasoner")
        for sha_name, sha_value in (
            ("launch_plan_sha256", self.launch_plan_sha256),
            ("run_plan_sha256", self.run_plan_sha256),
            ("corpus_binding_sha256", self.corpus_binding_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("expected_weights_sha256", self.expected_weights_sha256),
            ("expected_corpus_sha256", self.expected_corpus_sha256),
        ):
            _require_sha256(sha_value, field=sha_name)
        for optional_name, optional_value in (
            ("observed_weights_sha256", self.observed_weights_sha256),
            ("model_verifier_receipt_sha256", self.model_verifier_receipt_sha256),
            ("observed_corpus_sha256", self.observed_corpus_sha256),
        ):
            if optional_value is not None:
                _require_sha256(optional_value, field=optional_name)
        _require_text(self.model_id, field="model_id")
        if _GIT_SHA.fullmatch(self.revision) is None:
            raise TrainingLocalAssetAttestationError(
                "revision must be exactly 40 lowercase hex characters"
            )
        for bool_name, bool_value in (
            ("model_network_accessed", self.model_network_accessed),
            ("model_remote_code_allowed", self.model_remote_code_allowed),
            ("model_gated_terms_accepted", self.model_gated_terms_accepted),
        ):
            if type(bool_value) is not bool:
                raise TrainingLocalAssetAttestationError(f"{bool_name} must be a bool")
        _require_count(self.expected_corpus_byte_count, field="expected_corpus_byte_count")
        if self.observed_corpus_byte_count is not None:
            _require_count(self.observed_corpus_byte_count, field="observed_corpus_byte_count")
        if not isinstance(self.blockers, tuple):
            raise TrainingLocalAssetAttestationError("blockers must be an immutable tuple")
        if any(not isinstance(item, str) or not item for item in self.blockers):
            raise TrainingLocalAssetAttestationError(
                "blockers must contain non-empty strings only"
            )
        if self.disposition == "PASS":
            self._validate_pass()

    def _validate_pass(self) -> None:
        if self.blockers:
            raise TrainingLocalAssetAttestationError("PASS attestation cannot have blockers")
        if self.observed_weights_sha256 != self.expected_weights_sha256:
            raise TrainingLocalAssetAttestationError(
                "PASS attestation requires exact expected/observed weight identity equality"
            )
        if self.observed_corpus_sha256 != self.expected_corpus_sha256:
            raise TrainingLocalAssetAttestationError(
                "PASS attestation requires exact expected/observed corpus SHA equality"
            )
        if self.observed_corpus_byte_count != self.expected_corpus_byte_count:
            raise TrainingLocalAssetAttestationError(
                "PASS attestation requires exact expected/observed corpus byte equality"
            )
        if (
            self.model_verifier_id is None
            or self.model_verifier_version is None
            or self.model_verifier_receipt_sha256 is None
        ):
            raise TrainingLocalAssetAttestationError(
                "PASS attestation requires a complete model verifier receipt"
            )
        if (
            self.model_network_accessed
            or self.model_remote_code_allowed
            or self.model_gated_terms_accepted
        ):
            raise TrainingLocalAssetAttestationError(
                "PASS attestation forbids network, remote code, or gated-term acceptance"
            )

    @property
    def can_execute_training(self) -> bool:
        return self.disposition == "PASS" and not self.blockers

    @property
    def attestation_sha256(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "attestation_version": self.attestation_version,
            "blockers": list(self.blockers),
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "disposition": self.disposition,
            "expected_corpus_byte_count": self.expected_corpus_byte_count,
            "expected_corpus_sha256": self.expected_corpus_sha256,
            "expected_weights_sha256": self.expected_weights_sha256,
            "launch_plan_sha256": self.launch_plan_sha256,
            "model_gated_terms_accepted": self.model_gated_terms_accepted,
            "model_id": self.model_id,
            "model_network_accessed": self.model_network_accessed,
            "model_remote_code_allowed": self.model_remote_code_allowed,
            "model_verifier_id": self.model_verifier_id,
            "model_verifier_receipt_sha256": self.model_verifier_receipt_sha256,
            "model_verifier_version": self.model_verifier_version,
            "observed_corpus_byte_count": self.observed_corpus_byte_count,
            "observed_corpus_sha256": self.observed_corpus_sha256,
            "observed_weights_sha256": self.observed_weights_sha256,
            "revision": self.revision,
            "role": self.role,
            "run_plan_sha256": self.run_plan_sha256,
            "training_dataset_sha256": self.training_dataset_sha256,
        }


def attest_local_training_assets(
    *,
    launch_plan: TrainingLaunchPlan,
    corpus_binding: TrainingCorpusBindingReport,
    role: TrainingRole,
    model_root: Path,
    corpus_path: Path,
    verifier: LocalModelAssetVerifier,
) -> TrainingLocalAssetAttestationReport:
    """Attest one launch run against already-local model and corpus assets."""
    if type(launch_plan) is not TrainingLaunchPlan:
        raise TrainingLocalAssetAttestationError(
            "launch_plan must be an exact TrainingLaunchPlan"
        )
    if type(corpus_binding) is not TrainingCorpusBindingReport:
        raise TrainingLocalAssetAttestationError(
            "corpus_binding must be an exact TrainingCorpusBindingReport"
        )
    if role not in ("compact", "reasoner"):
        raise TrainingLocalAssetAttestationError("role must be compact or reasoner")
    if not isinstance(model_root, Path) or not isinstance(corpus_path, Path):
        raise TrainingLocalAssetAttestationError(
            "model_root and corpus_path must be pathlib.Path"
        )

    run_plan = launch_plan.compact if role == "compact" else launch_plan.reasoner
    blockers: list[str] = []
    if not corpus_binding.can_attest_local_artifact:
        blockers.append("corpus binding is not PASS")
    if run_plan.training_dataset_sha256 != corpus_binding.training_dataset_sha256:
        blockers.append("launch run training dataset does not match corpus binding")

    corpus_sha, corpus_bytes = _attest_corpus(
        corpus_path,
        binding=corpus_binding,
        blockers=blockers,
    )
    observation = _attest_model(
        model_root,
        verifier=verifier,
        role=role,
        run_plan=run_plan,
        blockers=blockers,
    )

    disposition: LocalAssetDisposition = "BLOCKED" if blockers else "PASS"
    return TrainingLocalAssetAttestationReport(
        disposition=disposition,
        role=role,
        launch_plan_sha256=launch_plan.plan_sha256,
        run_plan_sha256=run_plan.run_plan_sha256,
        corpus_binding_sha256=corpus_binding.binding_sha256,
        training_dataset_sha256=run_plan.training_dataset_sha256,
        model_id=run_plan.model_id,
        revision=run_plan.revision,
        expected_weights_sha256=run_plan.weights_sha256,
        observed_weights_sha256=None if observation is None else observation.weights_sha256,
        model_verifier_id=None if observation is None else observation.verifier_id,
        model_verifier_version=None if observation is None else observation.verifier_version,
        model_verifier_receipt_sha256=(
            None if observation is None else observation.verifier_receipt_sha256
        ),
        model_network_accessed=False if observation is None else observation.network_accessed,
        model_remote_code_allowed=False if observation is None else observation.remote_code_allowed,
        model_gated_terms_accepted=(
            False if observation is None else observation.gated_terms_accepted
        ),
        expected_corpus_sha256=corpus_binding.canonical_jsonl_sha256,
        observed_corpus_sha256=corpus_sha,
        expected_corpus_byte_count=corpus_binding.canonical_jsonl_byte_count,
        observed_corpus_byte_count=corpus_bytes,
        blockers=tuple(blockers),
    )


def _attest_corpus(
    path: Path,
    *,
    binding: TrainingCorpusBindingReport,
    blockers: list[str],
) -> tuple[str | None, int | None]:
    if path.is_symlink():
        blockers.append("corpus path must not be a symlink")
        return None, None
    if not path.is_file():
        blockers.append("corpus path is not an existing regular file")
        return None, None
    observed_sha, observed_bytes = _observe_file(path)
    if observed_sha != binding.canonical_jsonl_sha256:
        blockers.append("local corpus SHA does not match canonical corpus binding")
    if observed_bytes != binding.canonical_jsonl_byte_count:
        blockers.append("local corpus byte count does not match canonical corpus binding")
    return observed_sha, observed_bytes


def _attest_model(
    model_root: Path,
    *,
    verifier: LocalModelAssetVerifier,
    role: TrainingRole,
    run_plan: TrainingRunPlan,
    blockers: list[str],
) -> LocalModelAssetObservation | None:
    if model_root.is_symlink():
        blockers.append("model root must not be a symlink")
        return None
    if not model_root.is_dir():
        blockers.append("model root is not an existing directory")
        return None
    try:
        candidate = verifier.verify(role=role, model_root=model_root, run_plan=run_plan)
    except Exception:
        blockers.append("local model verifier failed")
        return None
    if type(candidate) is not LocalModelAssetObservation:
        blockers.append("local model verifier returned a non-canonical observation")
        return None
    _check_model_observation(candidate, run_plan=run_plan, role=role, blockers=blockers)
    return candidate


def _check_model_observation(
    observation: LocalModelAssetObservation,
    *,
    run_plan: TrainingRunPlan,
    role: TrainingRole,
    blockers: list[str],
) -> None:
    for label, observed, expected in (
        ("role", observation.role, role),
        ("model_id", observation.model_id, run_plan.model_id),
        ("revision", observation.revision, run_plan.revision),
        ("weights_sha256", observation.weights_sha256, run_plan.weights_sha256),
    ):
        if observed != expected:
            blockers.append(f"local model {label} does not match launch run")
    if observation.network_accessed:
        blockers.append("local model verification accessed the network")
    if observation.remote_code_allowed:
        blockers.append("local model verification allowed remote code")
    if observation.gated_terms_accepted:
        blockers.append("local model verification accepted gated terms")


def _observe_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK_SIZE):
            digest.update(chunk)
            byte_count += len(chunk)
    return digest.hexdigest(), byte_count


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingLocalAssetAttestationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TrainingLocalAssetAttestationError(f"{field} must be non-empty NUL-free text")
    return value


def _require_count(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise TrainingLocalAssetAttestationError(f"{field} must be a non-negative int")
    return value
