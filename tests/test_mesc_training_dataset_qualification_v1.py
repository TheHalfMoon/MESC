"""Qualification tests for the MESC T5 training-dataset gate."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.dataset.builder.freeze import SplitAssignmentFreeze
from medscale.dataset.builder.manifest import AuditReport, DatasetReleaseManifest, QualityReport
from medscale.dataset.split import SplitStrategy
from medscale.mesc._training_dataset_qualification_v1 import (
    EvidenceArtifactBinding,
    TrainingDatasetEvidenceBundle,
    TrainingDatasetQualificationError,
    TrainingDatasetQualificationReport,
    build_readiness_manifest_from_qualified_dataset,
    qualify_training_dataset,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    assess_training_readiness,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe
from medscale.reproducibility import content_hash

_DATASET_FINGERPRINT = "a" * 64
_MANIFEST_SHA = "b" * 64
_BUNDLE_REGISTRY_SHA = "c" * 64
_PROVENANCE_SHA = "1" * 64
_DECONTAMINATION_SHA = "2" * 64
_LICENSE_SHA = "3" * 64
_PHI_SHA = "4" * 64
_R2_SHA = "5" * 64
_HELDOUT_SHA = "6" * 64
_HELDOUT_RECORDS_SHA = "7" * 64


def _training_record_ids_sha256(train: tuple[str, ...]) -> str:
    return content_hash(
        {
            "kind": "mesc.training_dataset.record_ids.v1",
            "record_ids": sorted(train),
        }
    )


def _release() -> DatasetReleaseManifest:
    return DatasetReleaseManifest(
        dataset_id="mesc-training-v1",
        dataset_version="1.0.0",
        dataset_fingerprint=_DATASET_FINGERPRINT,
        release_id="release-1",
        released_at="2026-08-24T00:00:00Z",
        released_by="fixture",
        dataset_manifest_sha256=_MANIFEST_SHA,
        bundle_id_registry_sha256=_BUNDLE_REGISTRY_SHA,
        validation_summary={"green": True},
        quality_summary={"green": True},
    )


def _freeze(*, train: tuple[str, ...] = ("train-1", "train-2")) -> SplitAssignmentFreeze:
    return SplitAssignmentFreeze(
        source_dataset_fingerprint=_DATASET_FINGERPRINT,
        strategy=SplitStrategy.DETERMINISTIC_HASH_SPLIT,
        seed=42,
        train=train,
        validation=("validation-1",),
        test=("test-1",),
    )


def _audit(*, record_count: int = 4, green: bool = True) -> AuditReport:
    return AuditReport(
        dataset_id="mesc-training-v1",
        dataset_version="1.0.0",
        audit_timestamp="2026-08-24T00:00:00Z",
        green=green,
        record_count=record_count,
        validation_statuses={"schema": "PASS", "split": "PASS"},
        checksum_verification={"manifest": "PASS", "splits": "PASS"},
    )


def _binding(artifact_sha256: str, covered_sha256: str) -> EvidenceArtifactBinding:
    return EvidenceArtifactBinding(
        artifact_sha256=artifact_sha256,
        covered_record_ids_sha256=covered_sha256,
        disposition="PASS",
    )


def _evidence(*, train: tuple[str, ...] = ("train-1", "train-2")) -> TrainingDatasetEvidenceBundle:
    covered = _training_record_ids_sha256(train)
    return TrainingDatasetEvidenceBundle(
        provenance=_binding(_PROVENANCE_SHA, covered),
        decontamination=_binding(_DECONTAMINATION_SHA, covered),
        license_review=_binding(_LICENSE_SHA, covered),
        phi_scan=_binding(_PHI_SHA, covered),
        r2_review=_binding(_R2_SHA, covered),
        heldout_exclusion=_binding(_HELDOUT_SHA, covered),
        heldout_eval_record_ids_sha256=_HELDOUT_RECORDS_SHA,
        phi_present=False,
        r2_training_data_only=True,
        heldout_training_overlap_count=0,
    )


def _quality(*, train: tuple[str, ...] = ("train-1", "train-2")) -> QualityReport:
    covered = _training_record_ids_sha256(train)
    return QualityReport(
        dataset_id="mesc-training-v1",
        dataset_version="1.0.0",
        stage_quality_summaries={
            "provenance": {
                "covered_record_ids_sha256": covered,
                "disposition": "PASS",
                "ledger_sha256": _PROVENANCE_SHA,
            },
            "phi_scan": {
                "covered_record_ids_sha256": covered,
                "disposition": "PASS",
                "phi_present": False,
                "report_sha256": _PHI_SHA,
            },
            "r2_policy": {
                "covered_record_ids_sha256": covered,
                "disposition": "PASS",
                "r2_training_data_only": True,
                "report_sha256": _R2_SHA,
            },
        },
        contamination_summary={
            "covered_record_ids_sha256": covered,
            "disposition": "PASS",
            "report_sha256": _DECONTAMINATION_SHA,
        },
        license_audit={
            "covered_record_ids_sha256": covered,
            "disposition": "PASS",
            "review_sha256": _LICENSE_SHA,
        },
        benchmark_linkage_status={
            "covered_record_ids_sha256": covered,
            "disposition": "PASS",
            "heldout_eval_record_ids_sha256": _HELDOUT_RECORDS_SHA,
            "report_sha256": _HELDOUT_SHA,
            "training_overlap_count": 0,
        },
        green=True,
    )


def _qualify(
    *,
    train: tuple[str, ...] = ("train-1", "train-2"),
    release: DatasetReleaseManifest | None = None,
    audit: AuditReport | None = None,
    quality: QualityReport | None = None,
    evidence: TrainingDatasetEvidenceBundle | None = None,
) -> TrainingDatasetQualificationReport:
    freeze = _freeze(train=train)
    expected_count = freeze.assignment_count
    return qualify_training_dataset(
        release=_release() if release is None else release,
        audit=_audit(record_count=expected_count) if audit is None else audit,
        quality=_quality(train=train) if quality is None else quality,
        split_freeze=freeze,
        evidence=_evidence(train=train) if evidence is None else evidence,
    )


def test_exact_t5_evidence_passes_and_is_content_addressed() -> None:
    report = _qualify()
    rebuilt = _qualify()

    assert report.disposition == "PASS"
    assert report.blockers == ()
    assert report.can_bind_to_readiness
    assert report.r2_training_data_only
    assert report.heldout_eval_excluded_from_training
    assert not report.phi_present
    assert len(report.training_dataset_sha256) == 64
    assert len(report.qualification_sha256) == 64
    assert report.qualification_sha256 == rebuilt.qualification_sha256
    assert report.training_dataset_sha256 == rebuilt.training_dataset_sha256


def test_training_dataset_identity_changes_when_train_membership_changes() -> None:
    first = _qualify(train=("train-1", "train-2"))
    second = _qualify(train=("train-1", "train-3"))

    assert first.disposition == "PASS"
    assert second.disposition == "PASS"
    assert first.training_record_ids_sha256 != second.training_record_ids_sha256
    assert first.training_dataset_sha256 != second.training_dataset_sha256


def test_evidence_must_cover_exact_training_record_set() -> None:
    evidence = _evidence()
    wrong_provenance = replace(
        evidence.provenance,
        covered_record_ids_sha256="f" * 64,
    )
    report = _qualify(evidence=replace(evidence, provenance=wrong_provenance))

    assert report.disposition == "BLOCKED"
    assert not report.can_bind_to_readiness
    assert any("provenance evidence does not cover" in blocker for blocker in report.blockers)


def test_heldout_overlap_phi_and_non_r2_data_block_training_dataset() -> None:
    evidence = replace(
        _evidence(),
        heldout_training_overlap_count=1,
        phi_present=True,
        r2_training_data_only=False,
    )
    report = _qualify(evidence=evidence)

    assert report.disposition == "BLOCKED"
    assert not report.heldout_eval_excluded_from_training
    assert report.phi_present
    assert not report.r2_training_data_only
    assert any("overlap" in blocker for blocker in report.blockers)
    assert any("PHI" in blocker for blocker in report.blockers)
    assert any("R2-compatible" in blocker for blocker in report.blockers)


def test_quality_summary_must_bind_same_decontamination_artifact() -> None:
    quality = _quality()
    contaminated = dict(quality.contamination_summary)
    contaminated["report_sha256"] = "f" * 64
    report = _qualify(
        quality=replace(quality, contamination_summary=contaminated),
    )

    assert report.disposition == "BLOCKED"
    assert any("contamination_summary.report_sha256" in blocker for blocker in report.blockers)


def test_dataset_release_audit_quality_and_split_identity_must_agree() -> None:
    release = replace(_release(), dataset_id="different-dataset")
    report = _qualify(release=release)

    assert report.disposition == "BLOCKED"
    assert any("dataset_id values must match" in blocker for blocker in report.blockers)

    bad_audit = replace(_audit(), green=False, failures=("checksum mismatch",))
    report = _qualify(audit=bad_audit)
    assert report.disposition == "BLOCKED"
    assert any("audit is not green" in blocker for blocker in report.blockers)
    assert any("audit contains failures" in blocker for blocker in report.blockers)


def test_direct_pass_report_cannot_forge_hard_scientific_flags() -> None:
    report = _qualify()

    with pytest.raises(TrainingDatasetQualificationError, match="phi_present=false"):
        replace(report, phi_present=True)
    with pytest.raises(TrainingDatasetQualificationError, match="r2_training_data_only=true"):
        replace(report, r2_training_data_only=False)
    with pytest.raises(
        TrainingDatasetQualificationError,
        match="heldout_eval_excluded_from_training=true",
    ):
        replace(report, heldout_eval_excluded_from_training=False)


def _candidate(*, role: str) -> TrainingCandidate:
    if role == "compact":
        return TrainingCandidate(
            model_id="fixture/compact",
            revision="8" * 40,
            weights_sha256="8" * 64,
            license_id="apache-2.0",
        )
    return TrainingCandidate(
        model_id="fixture/reasoner",
        revision="9" * 40,
        weights_sha256="9" * 64,
        license_id="apache-2.0",
    )


def _recipe(candidate: TrainingCandidate, dataset_sha256: str) -> TrainingRecipe:
    return TrainingRecipe(
        base=ModelRef(
            model_id=candidate.model_id,
            revision=candidate.revision,
            quantization="nf4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef(
            name="mesc-training-v1",
            version="1.0.0",
            content_sha256=dataset_sha256,
        ),
        seed=42,
        max_steps=100,
    )


def test_pass_t5_report_builds_readiness_manifest_without_launch_authority() -> None:
    qualification = _qualify()
    compact = _candidate(role="compact")
    reasoner = _candidate(role="reasoner")

    manifest = build_readiness_manifest_from_qualified_dataset(
        qualification=qualification,
        compact_candidate=compact,
        reasoner_candidate=reasoner,
        compact_recipe=_recipe(compact, qualification.training_dataset_sha256),
        reasoner_recipe=_recipe(reasoner, qualification.training_dataset_sha256),
        pilot_closeout_sha256="a" * 64,
        tournament_report_sha256="b" * 64,
        evaluation_contract_sha256="c" * 64,
        pilot_closeout_disposition="PASS",
        tournament_disposition="PASS",
    )
    readiness = assess_training_readiness(manifest)

    assert manifest.training_dataset_sha256 == qualification.training_dataset_sha256
    assert manifest.provenance_ledger_sha256 == qualification.provenance_ledger_sha256
    assert manifest.decontamination_report_sha256 == qualification.decontamination_report_sha256
    assert manifest.license_review_sha256 == qualification.license_review_sha256
    assert readiness.disposition == "READY_FOR_AUTHORIZATION"
    assert not readiness.can_launch_training
    assert len(readiness.launch_requirements) == 3
    assert "canonical corpus binding is required" in readiness.launch_requirements
    assert "runtime qualification receipt is required" in readiness.launch_requirements
    assert "training authorization receipt is required" in readiness.launch_requirements


def test_blocked_t5_report_cannot_bind_to_readiness() -> None:
    blocked = _qualify(evidence=replace(_evidence(), phi_present=True))
    compact = _candidate(role="compact")
    reasoner = _candidate(role="reasoner")

    with pytest.raises(TrainingDatasetQualificationError, match="must be PASS"):
        build_readiness_manifest_from_qualified_dataset(
            qualification=blocked,
            compact_candidate=compact,
            reasoner_candidate=reasoner,
            compact_recipe=_recipe(compact, blocked.training_dataset_sha256),
            reasoner_recipe=_recipe(reasoner, blocked.training_dataset_sha256),
            pilot_closeout_sha256="a" * 64,
            tournament_report_sha256="b" * 64,
            evaluation_contract_sha256="c" * 64,
            pilot_closeout_disposition="PASS",
            tournament_disposition="PASS",
        )
