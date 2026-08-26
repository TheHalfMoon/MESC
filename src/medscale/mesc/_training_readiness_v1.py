"""Fail-closed MESC training-readiness assessment.

This module binds the first authorized post-tournament training launch to exact finalist,
data, provenance, decontamination, evaluation, license, recipe, corpus, runtime, and
operator-authorization identities. Hash presence alone is never authority: launch-ready
assessment requires the matching typed, semantically valid receipts. It plans no provider
work and executes no training.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.mesc._training_authorization_receipt_v1 import TrainingAuthorizationReceipt
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationReceipt,
)
from medscale.modelkit.recipes import TrainingRecipe

TrainingReadinessDisposition = Literal[
    "BLOCKED",
    "READY_FOR_AUTHORIZATION",
    "READY_TO_LAUNCH",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REVISION: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_PROGRAM_VERSION: Final = "MESC-TRAINING-READINESS-V1"
_AUTHORIZATION_SUBJECT_KIND: Final = "mesc.training_readiness.authorization_subject.v1"


@dataclass(frozen=True, slots=True)
class TrainingCandidate:
    """One exact tournament-selected training candidate."""

    model_id: str
    revision: str
    weights_sha256: str
    license_id: str

    def __post_init__(self) -> None:
        if type(self.model_id) is not str or not self.model_id.strip():
            raise ValueError("model_id must be non-empty")
        if type(self.revision) is not str or _REVISION.fullmatch(self.revision) is None:
            raise ValueError("revision must be exactly 40 lowercase hex characters")
        _require_sha256(self.weights_sha256, field="weights_sha256")
        if type(self.license_id) is not str or not self.license_id.strip():
            raise ValueError("license_id must be non-empty")


@dataclass(frozen=True, slots=True)
class TrainingReadinessManifest:
    """All identities and authority evidence required before a MESC training launch."""

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
    corpus_binding_sha256: str | None = None
    runtime_qualification_sha256: str | None = None
    training_authorization_receipt_sha256: str | None = None
    runtime_qualification_receipt: TrainingRuntimeQualificationReceipt | None = None
    training_authorization_receipt: TrainingAuthorizationReceipt | None = None
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise ValueError(f"program_version must be exactly {_PROGRAM_VERSION}")
        for field_name, required_sha in (
            ("pilot_closeout_sha256", self.pilot_closeout_sha256),
            ("tournament_report_sha256", self.tournament_report_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("provenance_ledger_sha256", self.provenance_ledger_sha256),
            ("decontamination_report_sha256", self.decontamination_report_sha256),
            ("evaluation_contract_sha256", self.evaluation_contract_sha256),
            ("license_review_sha256", self.license_review_sha256),
        ):
            _require_sha256(required_sha, field=field_name)
        optional_shas: tuple[tuple[str, str | None], ...] = (
            ("corpus_binding_sha256", self.corpus_binding_sha256),
            ("runtime_qualification_sha256", self.runtime_qualification_sha256),
            (
                "training_authorization_receipt_sha256",
                self.training_authorization_receipt_sha256,
            ),
        )
        for field_name, optional_sha in optional_shas:
            if optional_sha is not None:
                _require_sha256(optional_sha, field=field_name)
        bool_fields: tuple[tuple[str, bool], ...] = (
            ("r2_training_data_only", self.r2_training_data_only),
            ("heldout_eval_excluded_from_training", self.heldout_eval_excluded_from_training),
            ("phi_present", self.phi_present),
        )
        for field_name, flag in bool_fields:
            if type(flag) is not bool:
                raise ValueError(f"{field_name} must be an exact bool")

        if self.runtime_qualification_receipt is not None:
            if type(self.runtime_qualification_receipt) is not TrainingRuntimeQualificationReceipt:
                raise ValueError(
                    "runtime_qualification_receipt must be an exact "
                    "TrainingRuntimeQualificationReceipt"
                )
            if self.runtime_qualification_sha256 is None:
                raise ValueError(
                    "runtime_qualification_receipt requires runtime_qualification_sha256"
                )
            if (
                self.runtime_qualification_receipt.receipt_sha256
                != self.runtime_qualification_sha256
            ):
                raise ValueError(
                    "runtime_qualification_receipt does not match runtime_qualification_sha256"
                )
        if self.training_authorization_receipt is not None:
            if type(self.training_authorization_receipt) is not TrainingAuthorizationReceipt:
                raise ValueError(
                    "training_authorization_receipt must be an exact TrainingAuthorizationReceipt"
                )
            if self.training_authorization_receipt_sha256 is None:
                raise ValueError(
                    "training_authorization_receipt requires training_authorization_receipt_sha256"
                )
            if (
                self.training_authorization_receipt.receipt_sha256
                != self.training_authorization_receipt_sha256
            ):
                raise ValueError("training_authorization_receipt does not match its manifest SHA")

    @property
    def manifest_sha256(self) -> str:
        """Return a deterministic identity for the complete final readiness manifest."""
        return _payload_sha256(self._canonical_payload())

    @property
    def authorization_subject_sha256(self) -> str:
        """Return the stable pre-authorization subject identity.

        The authorization receipt hash is deliberately excluded, breaking the historical
        fixed-point cycle while retaining every other readiness identity, including the
        runtime qualification and canonical corpus binding.
        """
        payload = self._canonical_payload()
        del payload["training_authorization_receipt_sha256"]
        payload["kind"] = _AUTHORIZATION_SUBJECT_KIND
        return _payload_sha256(payload)

    def _canonical_payload(self) -> dict[str, object]:
        return {
            "compact_candidate": _candidate_payload(self.compact_candidate),
            "compact_recipe_id": self.compact_recipe.recipe_id,
            "corpus_binding_sha256": self.corpus_binding_sha256,
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
            "training_authorization_receipt_sha256": self.training_authorization_receipt_sha256,
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


def assess_training_readiness(
    manifest: TrainingReadinessManifest,
) -> TrainingReadinessReport:
    """Assess readiness from canonical identities plus typed authority evidence only."""
    if type(manifest) is not TrainingReadinessManifest:
        raise ValueError("manifest must be an exact TrainingReadinessManifest")
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

    launch_requirements: list[str] = []
    if manifest.corpus_binding_sha256 is None:
        launch_requirements.append("canonical corpus binding is required")
    if manifest.runtime_qualification_sha256 is None:
        launch_requirements.append("runtime qualification receipt is required")
    elif manifest.runtime_qualification_receipt is None:
        launch_requirements.append("validated runtime qualification receipt is required")
    else:
        _validate_runtime_receipt(manifest, blockers=blockers)

    if manifest.training_authorization_receipt_sha256 is None:
        launch_requirements.append("training authorization receipt is required")
    elif manifest.training_authorization_receipt is None:
        launch_requirements.append("validated training authorization receipt is required")
    else:
        _validate_authorization_receipt(manifest, blockers=blockers)

    if blockers:
        return TrainingReadinessReport(
            disposition="BLOCKED",
            manifest_sha256=manifest.manifest_sha256,
            blockers=tuple(blockers),
            launch_requirements=(),
        )

    disposition: TrainingReadinessDisposition = (
        "READY_FOR_AUTHORIZATION" if launch_requirements else "READY_TO_LAUNCH"
    )
    return TrainingReadinessReport(
        disposition=disposition,
        manifest_sha256=manifest.manifest_sha256,
        blockers=(),
        launch_requirements=tuple(launch_requirements),
    )


def _validate_runtime_receipt(
    manifest: TrainingReadinessManifest,
    *,
    blockers: list[str],
) -> None:
    receipt = manifest.runtime_qualification_receipt
    if type(receipt) is not TrainingRuntimeQualificationReceipt:
        blockers.append("runtime qualification receipt is non-canonical")
        return
    if receipt.receipt_sha256 != manifest.runtime_qualification_sha256:
        blockers.append("runtime qualification receipt hash does not match manifest")
    if receipt.disposition != "PASS" or not receipt.platform_qualified:
        blockers.append("runtime qualification receipt is not platform-qualified PASS")
    if receipt.blockers:
        blockers.append("runtime qualification receipt retains blockers")
    if receipt.smoke_disposition != "PASS" or receipt.smoke_receipt_sha256 is None:
        blockers.append("runtime qualification receipt lacks validated PASS smoke evidence")
    if receipt.network_accessed or receipt.remote_code_allowed:
        blockers.append("runtime qualification receipt records unsafe runtime access")


def _validate_authorization_receipt(
    manifest: TrainingReadinessManifest,
    *,
    blockers: list[str],
) -> None:
    receipt = manifest.training_authorization_receipt
    if type(receipt) is not TrainingAuthorizationReceipt:
        blockers.append("training authorization receipt is non-canonical")
        return
    if receipt.receipt_sha256 != manifest.training_authorization_receipt_sha256:
        blockers.append("training authorization receipt hash does not match manifest")
    if receipt.disposition != "AUTHORIZED" or not receipt.real_training_authorized:
        blockers.append("training authorization receipt is not explicitly AUTHORIZED")
    if receipt.blockers:
        blockers.append("training authorization receipt retains blockers")
    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:
        blockers.append("training authorization receipt targets a different readiness subject")
    if receipt.runtime_qualification_sha256 != manifest.runtime_qualification_sha256:
        blockers.append("training authorization receipt targets a different runtime qualification")
    if manifest.corpus_binding_sha256 is None:
        blockers.append("training authorization receipt cannot bind absent corpus identity")
    elif receipt.corpus_binding_sha256 != manifest.corpus_binding_sha256:
        blockers.append("training authorization receipt targets a different corpus binding")


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


def _payload_sha256(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field} must be exactly 64 lowercase hex characters")
    return value


__all__ = [
    "TrainingCandidate",
    "TrainingReadinessDisposition",
    "TrainingReadinessManifest",
    "TrainingReadinessReport",
    "assess_training_readiness",
]
