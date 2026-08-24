"""Fail-closed MESC training-readiness assessment.

This module binds the first authorized post-tournament training launch to exact
finalist, data, provenance, decontamination, evaluation, license, recipe, runtime,
and operator-authorization identities. It plans no provider work and executes no
training.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.modelkit.recipes import TrainingRecipe

TrainingReadinessDisposition = Literal[
    "BLOCKED",
    "READY_FOR_AUTHORIZATION",
    "READY_TO_LAUNCH",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REVISION: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_PROGRAM_VERSION: Final = "MESC-TRAINING-READINESS-V1"


@dataclass(frozen=True, slots=True)
class TrainingCandidate:
    """One exact tournament-selected training candidate."""

    model_id: str
    revision: str
    weights_sha256: str
    license_id: str

    def __post_init__(self) -> None:
        if not self.model_id.strip():
            raise ValueError("model_id must be non-empty")
        if _REVISION.fullmatch(self.revision) is None:
            raise ValueError("revision must be exactly 40 lowercase hex characters")
        _require_sha256(self.weights_sha256, field="weights_sha256")
        if not self.license_id.strip():
            raise ValueError("license_id must be non-empty")


@dataclass(frozen=True, slots=True)
class TrainingReadinessManifest:
    """All identities and policy facts required before a first MESC training launch."""

    compact_candidate: TrainingCandidate
    reasoner_candidate: TrainingCandidate
    compact_recipe: TrainingRecipe
    reasoner_recipe: TrainingRecipe
    pilot_closeout_sha256: str
    tournament_report_sha256: str
    training_dataset_sha256: str
    provenance_ledger_sha256: str
    decontamination_report_sha256: str
    evaluation_contract_sha256: str
    license_review_sha256: str
    pilot_closeout_disposition: str
    tournament_disposition: str
    decontamination_disposition: str
    license_disposition: str
    r2_training_data_only: bool
    heldout_eval_excluded_from_training: bool
    phi_present: bool
    runtime_qualification_sha256: str | None = None
    training_authorization_receipt_sha256: str | None = None
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise ValueError(f"program_version must be exactly {_PROGRAM_VERSION}")
        for field, value in (
            ("pilot_closeout_sha256", self.pilot_closeout_sha256),
            ("tournament_report_sha256", self.tournament_report_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("provenance_ledger_sha256", self.provenance_ledger_sha256),
            ("decontamination_report_sha256", self.decontamination_report_sha256),
            ("evaluation_contract_sha256", self.evaluation_contract_sha256),
            ("license_review_sha256", self.license_review_sha256),
        ):
            _require_sha256(value, field=field)
        if self.runtime_qualification_sha256 is not None:
            _require_sha256(
                self.runtime_qualification_sha256,
                field="runtime_qualification_sha256",
            )
        if self.training_authorization_receipt_sha256 is not None:
            _require_sha256(
                self.training_authorization_receipt_sha256,
                field="training_authorization_receipt_sha256",
            )

    @property
    def manifest_sha256(self) -> str:
        """Return a deterministic identity for the complete readiness manifest."""
        payload = json.dumps(
            self._canonical_payload(),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        return hashlib.sha256(payload).hexdigest()

    def _canonical_payload(self) -> dict[str, object]:
        return {
            "compact_candidate": _candidate_payload(self.compact_candidate),
            "compact_recipe_id": self.compact_recipe.recipe_id,
            "decontamination_disposition": self.decontamination_disposition,
            "decontamination_report_sha256": self.decontamination_report_sha256,
            "evaluation_contract_sha256": self.evaluation_contract_sha256,
            "heldout_eval_excluded_from_training": self.heldout_eval_excluded_from_training,
            "license_disposition": self.license_disposition,
            "license_review_sha256": self.license_review_sha256,
            "phi_present": self.phi_present,
            "pilot_closeout_disposition": self.pilot_closeout_disposition,
            "pilot_closeout_sha256": self.pilot_closeout_sha256,
            "program_version": self.program_version,
            "provenance_ledger_sha256": self.provenance_ledger_sha256,
            "r2_training_data_only": self.r2_training_data_only,
            "reasoner_candidate": _candidate_payload(self.reasoner_candidate),
            "reasoner_recipe_id": self.reasoner_recipe.recipe_id,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
            "tournament_disposition": self.tournament_disposition,
            "tournament_report_sha256": self.tournament_report_sha256,
            "training_authorization_receipt_sha256": (
                self.training_authorization_receipt_sha256
            ),
            "training_dataset_sha256": self.training_dataset_sha256,
        }


@dataclass(frozen=True, slots=True)
class TrainingReadinessReport:
    """Deterministic fail-closed result of assessing one readiness manifest."""

    disposition: TrainingReadinessDisposition
    manifest_sha256: str
    blockers: tuple[str, ...]
    launch_requirements: tuple[str, ...]

    @property
    def can_launch_training(self) -> bool:
        return self.disposition == "READY_TO_LAUNCH"


def assess_training_readiness(manifest: TrainingReadinessManifest) -> TrainingReadinessReport:
    """Assess training readiness without accessing models, data, providers, or runtimes."""
    blockers: list[str] = []

    _require_pass(
        manifest.pilot_closeout_disposition,
        field="pilot_closeout_disposition",
        blockers=blockers,
    )
    _require_pass(
        manifest.tournament_disposition,
        field="tournament_disposition",
        blockers=blockers,
    )
    _require_pass(
        manifest.decontamination_disposition,
        field="decontamination_disposition",
        blockers=blockers,
    )
    _require_pass(
        manifest.license_disposition,
        field="license_disposition",
        blockers=blockers,
    )

    if not manifest.r2_training_data_only:
        blockers.append("training data is not proven R2-compatible")
    if not manifest.heldout_eval_excluded_from_training:
        blockers.append("held-out evaluation data is not proven excluded from training")
    if manifest.phi_present:
        blockers.append("PHI is present in the proposed training input")

    _check_recipe_binding(
        role="compact",
        candidate=manifest.compact_candidate,
        recipe=manifest.compact_recipe,
        training_dataset_sha256=manifest.training_dataset_sha256,
        blockers=blockers,
    )
    _check_recipe_binding(
        role="reasoner",
        candidate=manifest.reasoner_candidate,
        recipe=manifest.reasoner_recipe,
        training_dataset_sha256=manifest.training_dataset_sha256,
        blockers=blockers,
    )

    if blockers:
        return TrainingReadinessReport(
            disposition="BLOCKED",
            manifest_sha256=manifest.manifest_sha256,
            blockers=tuple(blockers),
            launch_requirements=(),
        )

    launch_requirements: list[str] = []
    if manifest.runtime_qualification_sha256 is None:
        launch_requirements.append("runtime qualification receipt is required")
    if manifest.training_authorization_receipt_sha256 is None:
        launch_requirements.append("training authorization receipt is required")

    disposition: TrainingReadinessDisposition = (
        "READY_FOR_AUTHORIZATION" if launch_requirements else "READY_TO_LAUNCH"
    )
    return TrainingReadinessReport(
        disposition=disposition,
        manifest_sha256=manifest.manifest_sha256,
        blockers=(),
        launch_requirements=tuple(launch_requirements),
    )


def _candidate_payload(candidate: TrainingCandidate) -> dict[str, str]:
    return {
        "license_id": candidate.license_id,
        "model_id": candidate.model_id,
        "revision": candidate.revision,
        "weights_sha256": candidate.weights_sha256,
    }


def _check_recipe_binding(
    *,
    role: str,
    candidate: TrainingCandidate,
    recipe: TrainingRecipe,
    training_dataset_sha256: str,
    blockers: list[str],
) -> None:
    if recipe.base.model_id != candidate.model_id:
        blockers.append(f"{role} recipe base model_id does not match selected candidate")
    if recipe.base.revision != candidate.revision:
        blockers.append(f"{role} recipe base revision does not match selected candidate")
    if recipe.dataset.content_sha256 != training_dataset_sha256:
        blockers.append(f"{role} recipe dataset hash does not match training dataset")


def _require_pass(value: str, *, field: str, blockers: list[str]) -> None:
    if value != "PASS":
        blockers.append(f"{field} must be exactly PASS")


def _require_sha256(value: str, *, field: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be exactly 64 lowercase hex characters")
