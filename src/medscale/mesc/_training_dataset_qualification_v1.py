"""Deterministic T5 qualification for one exact MESC training dataset.

This module composes the existing dataset release, audit, quality, and split-freeze
contracts into a fail-closed training-data qualification artifact. It performs no
dataset reads, network access, model access, inference, or training.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.dataset.builder.freeze import SplitAssignmentFreeze
from medscale.dataset.builder.manifest import AuditReport, DatasetReleaseManifest, QualityReport
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
)
from medscale.modelkit.recipes import TrainingRecipe
from medscale.reproducibility import content_hash

EvidenceDisposition = Literal["PASS", "FAIL"]
TrainingDatasetQualificationDisposition = Literal["BLOCKED", "PASS"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_QUALIFICATION_VERSION: Final = "MESC-TRAINING-DATASET-QUALIFICATION-V1"
_TRAINING_DATASET_KIND: Final = "mesc.training_dataset.train_split.v1"
_TRAINING_RECORD_SET_KIND: Final = "mesc.training_dataset.record_ids.v1"


class TrainingDatasetQualificationError(ValueError):
    """Fail-closed training-dataset qualification error."""


@dataclass(frozen=True, slots=True)
class EvidenceArtifactBinding:
    """One content-addressed evidence artifact over the exact training record set."""

    artifact_sha256: str
    covered_record_ids_sha256: str
    disposition: EvidenceDisposition

    def __post_init__(self) -> None:
        _require_sha256(self.artifact_sha256, field="artifact_sha256")
        _require_sha256(
            self.covered_record_ids_sha256,
            field="covered_record_ids_sha256",
        )
        if self.disposition not in ("PASS", "FAIL"):
            raise TrainingDatasetQualificationError("disposition must be exactly PASS or FAIL")

    def to_dict(self) -> dict[str, str]:
        return {
            "artifact_sha256": self.artifact_sha256,
            "covered_record_ids_sha256": self.covered_record_ids_sha256,
            "disposition": self.disposition,
        }


@dataclass(frozen=True, slots=True)
class TrainingDatasetEvidenceBundle:
    """Evidence required to prove an exact train split is eligible for MESC training."""

    provenance: EvidenceArtifactBinding
    decontamination: EvidenceArtifactBinding
    license_review: EvidenceArtifactBinding
    phi_scan: EvidenceArtifactBinding
    r2_review: EvidenceArtifactBinding
    heldout_exclusion: EvidenceArtifactBinding
    heldout_eval_record_ids_sha256: str
    phi_present: bool
    r2_training_data_only: bool
    heldout_training_overlap_count: int

    def __post_init__(self) -> None:
        _require_sha256(
            self.heldout_eval_record_ids_sha256,
            field="heldout_eval_record_ids_sha256",
        )
        if type(self.phi_present) is not bool:
            raise TrainingDatasetQualificationError("phi_present must be a bool")
        if type(self.r2_training_data_only) is not bool:
            raise TrainingDatasetQualificationError("r2_training_data_only must be a bool")
        if (
            type(self.heldout_training_overlap_count) is not int
            or self.heldout_training_overlap_count < 0
        ):
            raise TrainingDatasetQualificationError(
                "heldout_training_overlap_count must be a non-negative int"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "decontamination": self.decontamination.to_dict(),
            "heldout_eval_record_ids_sha256": self.heldout_eval_record_ids_sha256,
            "heldout_exclusion": self.heldout_exclusion.to_dict(),
            "heldout_training_overlap_count": self.heldout_training_overlap_count,
            "license_review": self.license_review.to_dict(),
            "phi_present": self.phi_present,
            "phi_scan": self.phi_scan.to_dict(),
            "provenance": self.provenance.to_dict(),
            "r2_review": self.r2_review.to_dict(),
            "r2_training_data_only": self.r2_training_data_only,
        }


@dataclass(frozen=True, slots=True)
class TrainingDatasetQualificationReport:
    """Deterministic qualification result for one exact training split."""

    disposition: TrainingDatasetQualificationDisposition
    dataset_release_sha256: str
    audit_report_sha256: str
    quality_report_sha256: str
    split_freeze_sha256: str
    training_record_ids_sha256: str
    training_dataset_sha256: str
    provenance_ledger_sha256: str
    decontamination_report_sha256: str
    license_review_sha256: str
    phi_scan_sha256: str
    r2_review_sha256: str
    heldout_exclusion_report_sha256: str
    heldout_eval_record_ids_sha256: str
    r2_training_data_only: bool
    heldout_eval_excluded_from_training: bool
    phi_present: bool
    blockers: tuple[str, ...]
    qualification_version: str = _QUALIFICATION_VERSION

    def __post_init__(self) -> None:
        if self.qualification_version != _QUALIFICATION_VERSION:
            raise TrainingDatasetQualificationError(
                f"qualification_version must be exactly {_QUALIFICATION_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "PASS"):
            raise TrainingDatasetQualificationError("disposition must be exactly BLOCKED or PASS")
        for field, value in (
            ("dataset_release_sha256", self.dataset_release_sha256),
            ("audit_report_sha256", self.audit_report_sha256),
            ("quality_report_sha256", self.quality_report_sha256),
            ("split_freeze_sha256", self.split_freeze_sha256),
            ("training_record_ids_sha256", self.training_record_ids_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("provenance_ledger_sha256", self.provenance_ledger_sha256),
            ("decontamination_report_sha256", self.decontamination_report_sha256),
            ("license_review_sha256", self.license_review_sha256),
            ("phi_scan_sha256", self.phi_scan_sha256),
            ("r2_review_sha256", self.r2_review_sha256),
            ("heldout_exclusion_report_sha256", self.heldout_exclusion_report_sha256),
            ("heldout_eval_record_ids_sha256", self.heldout_eval_record_ids_sha256),
        ):
            _require_sha256(value, field=field)
        if self.disposition == "PASS" and self.blockers:
            raise TrainingDatasetQualificationError("PASS qualification cannot contain blockers")

    @property
    def can_bind_to_readiness(self) -> bool:
        return self.disposition == "PASS" and not self.blockers

    @property
    def qualification_sha256(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "audit_report_sha256": self.audit_report_sha256,
            "blockers": list(self.blockers),
            "dataset_release_sha256": self.dataset_release_sha256,
            "decontamination_report_sha256": self.decontamination_report_sha256,
            "disposition": self.disposition,
            "heldout_eval_excluded_from_training": self.heldout_eval_excluded_from_training,
            "heldout_eval_record_ids_sha256": self.heldout_eval_record_ids_sha256,
            "heldout_exclusion_report_sha256": self.heldout_exclusion_report_sha256,
            "license_review_sha256": self.license_review_sha256,
            "phi_present": self.phi_present,
            "phi_scan_sha256": self.phi_scan_sha256,
            "provenance_ledger_sha256": self.provenance_ledger_sha256,
            "qualification_version": self.qualification_version,
            "quality_report_sha256": self.quality_report_sha256,
            "r2_review_sha256": self.r2_review_sha256,
            "r2_training_data_only": self.r2_training_data_only,
            "split_freeze_sha256": self.split_freeze_sha256,
            "training_dataset_sha256": self.training_dataset_sha256,
            "training_record_ids_sha256": self.training_record_ids_sha256,
        }


def qualify_training_dataset(
    *,
    release: DatasetReleaseManifest,
    audit: AuditReport,
    quality: QualityReport,
    split_freeze: SplitAssignmentFreeze,
    evidence: TrainingDatasetEvidenceBundle,
) -> TrainingDatasetQualificationReport:
    """Qualify supplied deterministic artifacts without reading the underlying dataset."""
    dataset_release_sha256 = _dataset_release_sha256(release)
    audit_report_sha256 = _audit_report_sha256(audit)
    quality_report_sha256 = _quality_report_sha256(quality)
    split_freeze_sha256 = split_freeze.freeze_fingerprint
    training_record_ids_sha256 = _training_record_ids_sha256(split_freeze)
    training_dataset_sha256 = _training_dataset_sha256(
        release=release,
        split_freeze=split_freeze,
        training_record_ids_sha256=training_record_ids_sha256,
    )

    blockers: list[str] = []

    _require_sha256_or_block(
        release.dataset_fingerprint,
        field="release.dataset_fingerprint",
        blockers=blockers,
    )
    _require_sha256_or_block(
        release.dataset_manifest_sha256,
        field="release.dataset_manifest_sha256",
        blockers=blockers,
    )
    _require_sha256_or_block(
        release.bundle_id_registry_sha256,
        field="release.bundle_id_registry_sha256",
        blockers=blockers,
    )

    if release.dataset_id != audit.dataset_id or release.dataset_id != quality.dataset_id:
        blockers.append("release, audit, and quality dataset_id values must match exactly")
    if (
        release.dataset_version != audit.dataset_version
        or release.dataset_version != quality.dataset_version
    ):
        blockers.append("release, audit, and quality dataset_version values must match exactly")
    if split_freeze.source_dataset_fingerprint != release.dataset_fingerprint:
        blockers.append("split freeze source fingerprint does not match released dataset")
    if not split_freeze.train:
        blockers.append("training split must contain at least one record")
    if audit.record_count != split_freeze.assignment_count:
        blockers.append("audit record_count does not match split-freeze assignment count")

    if not audit.green:
        blockers.append("dataset audit is not green")
    if audit.failures:
        blockers.append("dataset audit contains failures")
    _require_all_pass(
        audit.validation_statuses,
        label="audit.validation_statuses",
        blockers=blockers,
    )
    _require_all_pass(
        audit.checksum_verification,
        label="audit.checksum_verification",
        blockers=blockers,
    )
    if not quality.green:
        blockers.append("dataset quality report is not green")

    if release.validation_summary.get("green") is not True:
        blockers.append("release validation_summary must record green=true")
    if release.quality_summary.get("green") is not True:
        blockers.append("release quality_summary must record green=true")

    bindings = (
        ("provenance", evidence.provenance),
        ("decontamination", evidence.decontamination),
        ("license_review", evidence.license_review),
        ("phi_scan", evidence.phi_scan),
        ("r2_review", evidence.r2_review),
        ("heldout_exclusion", evidence.heldout_exclusion),
    )
    for label, binding in bindings:
        if binding.disposition != "PASS":
            blockers.append(f"{label} evidence disposition must be exactly PASS")
        if binding.covered_record_ids_sha256 != training_record_ids_sha256:
            blockers.append(f"{label} evidence does not cover the exact training record set")

    if evidence.phi_present:
        blockers.append("PHI is present in the proposed training record set")
    if not evidence.r2_training_data_only:
        blockers.append("training record set is not proven R2-compatible")
    heldout_excluded = evidence.heldout_training_overlap_count == 0
    if not heldout_excluded:
        blockers.append("held-out evaluation records overlap the training record set")
    if evidence.heldout_eval_record_ids_sha256 == training_record_ids_sha256:
        blockers.append(
            "held-out evaluation identity must differ from training record-set identity"
        )

    _require_summary_subset(
        quality.stage_quality_summaries.get("provenance"),
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "ledger_sha256": evidence.provenance.artifact_sha256,
        },
        label="quality.stage_quality_summaries.provenance",
        blockers=blockers,
    )
    _require_summary_subset(
        quality.contamination_summary,
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "report_sha256": evidence.decontamination.artifact_sha256,
        },
        label="quality.contamination_summary",
        blockers=blockers,
    )
    _require_summary_subset(
        quality.license_audit,
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "review_sha256": evidence.license_review.artifact_sha256,
        },
        label="quality.license_audit",
        blockers=blockers,
    )
    _require_summary_subset(
        quality.stage_quality_summaries.get("phi_scan"),
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "phi_present": evidence.phi_present,
            "report_sha256": evidence.phi_scan.artifact_sha256,
        },
        label="quality.stage_quality_summaries.phi_scan",
        blockers=blockers,
    )
    _require_summary_subset(
        quality.stage_quality_summaries.get("r2_policy"),
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "r2_training_data_only": evidence.r2_training_data_only,
            "report_sha256": evidence.r2_review.artifact_sha256,
        },
        label="quality.stage_quality_summaries.r2_policy",
        blockers=blockers,
    )
    _require_summary_subset(
        quality.benchmark_linkage_status,
        expected={
            "covered_record_ids_sha256": training_record_ids_sha256,
            "disposition": "PASS",
            "heldout_eval_record_ids_sha256": evidence.heldout_eval_record_ids_sha256,
            "report_sha256": evidence.heldout_exclusion.artifact_sha256,
            "training_overlap_count": evidence.heldout_training_overlap_count,
        },
        label="quality.benchmark_linkage_status",
        blockers=blockers,
    )

    disposition: TrainingDatasetQualificationDisposition = "BLOCKED" if blockers else "PASS"
    return TrainingDatasetQualificationReport(
        disposition=disposition,
        dataset_release_sha256=dataset_release_sha256,
        audit_report_sha256=audit_report_sha256,
        quality_report_sha256=quality_report_sha256,
        split_freeze_sha256=split_freeze_sha256,
        training_record_ids_sha256=training_record_ids_sha256,
        training_dataset_sha256=training_dataset_sha256,
        provenance_ledger_sha256=evidence.provenance.artifact_sha256,
        decontamination_report_sha256=evidence.decontamination.artifact_sha256,
        license_review_sha256=evidence.license_review.artifact_sha256,
        phi_scan_sha256=evidence.phi_scan.artifact_sha256,
        r2_review_sha256=evidence.r2_review.artifact_sha256,
        heldout_exclusion_report_sha256=evidence.heldout_exclusion.artifact_sha256,
        heldout_eval_record_ids_sha256=evidence.heldout_eval_record_ids_sha256,
        r2_training_data_only=evidence.r2_training_data_only,
        heldout_eval_excluded_from_training=heldout_excluded,
        phi_present=evidence.phi_present,
        blockers=tuple(blockers),
    )


def build_readiness_manifest_from_qualified_dataset(
    *,
    qualification: TrainingDatasetQualificationReport,
    compact_candidate: TrainingCandidate,
    reasoner_candidate: TrainingCandidate,
    compact_recipe: TrainingRecipe,
    reasoner_recipe: TrainingRecipe,
    pilot_closeout_sha256: str,
    tournament_report_sha256: str,
    evaluation_contract_sha256: str,
    pilot_closeout_disposition: str,
    tournament_disposition: str,
    runtime_qualification_sha256: str | None = None,
    training_authorization_receipt_sha256: str | None = None,
) -> TrainingReadinessManifest:
    """Build the canonical V1 readiness manifest only from a PASS T5 qualification."""
    if not qualification.can_bind_to_readiness:
        raise TrainingDatasetQualificationError(
            "training dataset qualification must be PASS before readiness binding"
        )
    return TrainingReadinessManifest(
        compact_candidate=compact_candidate,
        reasoner_candidate=reasoner_candidate,
        compact_recipe=compact_recipe,
        reasoner_recipe=reasoner_recipe,
        pilot_closeout_sha256=pilot_closeout_sha256,
        tournament_report_sha256=tournament_report_sha256,
        training_dataset_sha256=qualification.training_dataset_sha256,
        provenance_ledger_sha256=qualification.provenance_ledger_sha256,
        decontamination_report_sha256=qualification.decontamination_report_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        license_review_sha256=qualification.license_review_sha256,
        pilot_closeout_disposition=pilot_closeout_disposition,
        tournament_disposition=tournament_disposition,
        decontamination_disposition="PASS",
        license_disposition="PASS",
        r2_training_data_only=qualification.r2_training_data_only,
        heldout_eval_excluded_from_training=(
            qualification.heldout_eval_excluded_from_training
        ),
        phi_present=qualification.phi_present,
        runtime_qualification_sha256=runtime_qualification_sha256,
        training_authorization_receipt_sha256=training_authorization_receipt_sha256,
    )


def _training_record_ids_sha256(split_freeze: SplitAssignmentFreeze) -> str:
    return content_hash(
        {
            "kind": _TRAINING_RECORD_SET_KIND,
            "record_ids": sorted(split_freeze.train),
        }
    )


def _training_dataset_sha256(
    *,
    release: DatasetReleaseManifest,
    split_freeze: SplitAssignmentFreeze,
    training_record_ids_sha256: str,
) -> str:
    return content_hash(
        {
            "dataset_fingerprint": release.dataset_fingerprint,
            "dataset_id": release.dataset_id,
            "dataset_version": release.dataset_version,
            "kind": _TRAINING_DATASET_KIND,
            "split_freeze_sha256": split_freeze.freeze_fingerprint,
            "split_name": "train",
            "training_record_ids_sha256": training_record_ids_sha256,
        }
    )


def _dataset_release_sha256(release: DatasetReleaseManifest) -> str:
    return content_hash(
        {
            "bundle_id_registry_sha256": release.bundle_id_registry_sha256,
            "dataset_fingerprint": release.dataset_fingerprint,
            "dataset_id": release.dataset_id,
            "dataset_manifest_sha256": release.dataset_manifest_sha256,
            "dataset_version": release.dataset_version,
            "previous_release_id": release.previous_release_id,
            "quality_summary": dict(release.quality_summary),
            "release_id": release.release_id,
            "release_notes": release.release_notes,
            "released_at": release.released_at,
            "released_by": release.released_by,
            "validation_summary": dict(release.validation_summary),
        }
    )


def _audit_report_sha256(audit: AuditReport) -> str:
    return content_hash(
        {
            "analytics_report_version": audit.analytics_report_version,
            "audit_timestamp": audit.audit_timestamp,
            "bundle_ids": list(audit.bundle_ids),
            "checksum_verification": dict(audit.checksum_verification),
            "coverage_report_version": audit.coverage_report_version,
            "dataset_id": audit.dataset_id,
            "dataset_version": audit.dataset_version,
            "failures": list(audit.failures),
            "green": audit.green,
            "record_count": audit.record_count,
            "rejection_counts": dict(audit.rejection_counts),
            "validation_statuses": dict(audit.validation_statuses),
        }
    )


def _quality_report_sha256(quality: QualityReport) -> str:
    return content_hash(
        {
            "benchmark_linkage_status": dict(quality.benchmark_linkage_status),
            "bias_monitoring_summary": dict(quality.bias_monitoring_summary),
            "contamination_summary": dict(quality.contamination_summary),
            "dataset_id": quality.dataset_id,
            "dataset_version": quality.dataset_version,
            "green": quality.green,
            "license_audit": dict(quality.license_audit),
            "rejection_counts": dict(quality.rejection_counts),
            "stage_quality_summaries": dict(quality.stage_quality_summaries),
            "synthetic_proportions": dict(quality.synthetic_proportions),
        }
    )


def _require_summary_subset(
    summary: object,
    *,
    expected: dict[str, object],
    label: str,
    blockers: list[str],
) -> None:
    if not isinstance(summary, dict):
        blockers.append(f"{label} must be a mapping")
        return
    for key, value in expected.items():
        if summary.get(key) != value:
            blockers.append(f"{label}.{key} does not match required T5 evidence")


def _require_all_pass(values: dict[str, str], *, label: str, blockers: list[str]) -> None:
    if not values:
        blockers.append(f"{label} must be non-empty")
        return
    for key in sorted(values):
        if values[key] != "PASS":
            blockers.append(f"{label}.{key} must be exactly PASS")


def _require_sha256_or_block(value: str, *, field: str, blockers: list[str]) -> None:
    if _SHA256.fullmatch(value) is None:
        blockers.append(f"{field} must be exactly 64 lowercase hex characters")


def _require_sha256(value: str, *, field: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise TrainingDatasetQualificationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
