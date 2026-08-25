"""Tests for the MESC training-corpus binding gate."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from medscale.mesc._training_corpus_binding_v1 import (
    TrainingCorpusBindingError,
    bind_training_corpus,
)
from medscale.mesc._training_dataset_qualification_v1 import TrainingDatasetQualificationReport
from medscale.mesc._training_example_contract_v1 import (
    TrainingCorpusV1,
    TrainingExampleV1,
    TrainingMessage,
    build_training_corpus,
)
from medscale.reproducibility import content_hash

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64
_SHA_F = "f" * 64
_TRAINING_RECORD_SET_KIND = "mesc.training_dataset.record_ids.v1"


def _record_ids_sha256(record_ids: tuple[str, ...]) -> str:
    return content_hash(
        {
            "kind": _TRAINING_RECORD_SET_KIND,
            "record_ids": sorted(record_ids),
        }
    )


def _pass_qualification(record_ids: tuple[str, ...]) -> TrainingDatasetQualificationReport:
    return TrainingDatasetQualificationReport(
        disposition="PASS",
        dataset_release_sha256=_SHA_A,
        audit_report_sha256=_SHA_B,
        quality_report_sha256=_SHA_C,
        split_freeze_sha256=_SHA_D,
        training_record_ids_sha256=_record_ids_sha256(record_ids),
        training_dataset_sha256=_SHA_E,
        provenance_ledger_sha256=_SHA_A,
        decontamination_report_sha256=_SHA_B,
        license_review_sha256=_SHA_C,
        phi_scan_sha256=_SHA_D,
        r2_review_sha256=_SHA_E,
        heldout_exclusion_report_sha256=_SHA_F,
        heldout_eval_record_ids_sha256="1" * 64,
        r2_training_data_only=True,
        heldout_eval_excluded_from_training=True,
        phi_present=False,
        blockers=(),
    )


def _blocked_qualification(record_ids: tuple[str, ...]) -> TrainingDatasetQualificationReport:
    return TrainingDatasetQualificationReport(
        disposition="BLOCKED",
        dataset_release_sha256=_SHA_A,
        audit_report_sha256=_SHA_B,
        quality_report_sha256=_SHA_C,
        split_freeze_sha256=_SHA_D,
        training_record_ids_sha256=_record_ids_sha256(record_ids),
        training_dataset_sha256=_SHA_E,
        provenance_ledger_sha256=_SHA_A,
        decontamination_report_sha256=_SHA_B,
        license_review_sha256=_SHA_C,
        phi_scan_sha256=_SHA_D,
        r2_review_sha256=_SHA_E,
        heldout_exclusion_report_sha256=_SHA_F,
        heldout_eval_record_ids_sha256="1" * 64,
        r2_training_data_only=False,
        heldout_eval_excluded_from_training=False,
        phi_present=False,
        blockers=("qualification blocked",),
    )


def _example(
    *,
    example_id: str,
    training_record_id: str,
    source_sha256: str,
    source_license: str = "Apache-2.0",
) -> TrainingExampleV1:
    return TrainingExampleV1(
        example_id=example_id,
        training_record_id=training_record_id,
        source_id=f"source-{example_id}",
        source_revision="rev-1",
        source_license=source_license,
        source_sha256=source_sha256,
        source_timestamp="2026-08-01T00:00:00+00:00",
        origin="synthetic",
        synthetic_provenance_sha256=_SHA_F,
        evidence_refs=(f"evidence-{example_id}",),
        task_type="evidence-grounded-answer",
        specialty="internal-medicine",
        patient_population="adult",
        language="en",
        training_stage="evidence_sft",
        prompt=(TrainingMessage(role="user", content="What is supported?"),),
        completion=TrainingMessage(role="assistant", content="The evidence supports X."),
        uncertainty_class="SUPPORTED",
        abstention_target="ANSWER_SUPPORTED",
        contradiction_state="NONE",
        verification_state="VERIFIED",
        clinician_review_state="REVIEWED_PASS",
        contamination_state="CLEAR",
    )


def _corpus() -> TrainingCorpusV1:
    return build_training_corpus(
        (
            _example(
                example_id="example-1",
                training_record_id="record-1",
                source_sha256=_SHA_A,
            ),
            _example(
                example_id="example-2",
                training_record_id="record-2",
                source_sha256=_SHA_B,
            ),
        )
    )


def test_exact_t5_membership_binds_and_freezes_jsonl_bytes() -> None:
    corpus = _corpus()
    qualification = _pass_qualification(corpus.training_record_ids)

    report = bind_training_corpus(qualification=qualification, corpus=corpus)
    raw = corpus.canonical_jsonl().encode("utf-8")

    assert report.disposition == "PASS"
    assert report.can_attest_local_artifact is True
    assert report.qualification_sha256 == qualification.qualification_sha256
    assert report.training_dataset_sha256 == qualification.training_dataset_sha256
    assert report.corpus_sha256 == corpus.corpus_sha256
    assert report.corpus_training_record_ids_sha256 == qualification.training_record_ids_sha256
    assert report.canonical_jsonl_sha256 == hashlib.sha256(raw).hexdigest()
    assert report.canonical_jsonl_byte_count == len(raw)
    assert report.example_count == 2
    assert len(report.binding_sha256) == 64


def test_missing_or_extra_training_record_blocks_binding() -> None:
    corpus = _corpus()

    missing = bind_training_corpus(
        qualification=_pass_qualification(("record-1",)),
        corpus=corpus,
    )
    extra = bind_training_corpus(
        qualification=_pass_qualification(("record-1", "record-2", "record-3")),
        corpus=corpus,
    )

    assert missing.disposition == "BLOCKED"
    assert extra.disposition == "BLOCKED"
    assert "does not match T5 qualification" in missing.blockers[0]
    assert "does not match T5 qualification" in extra.blockers[0]


def test_multiple_examples_may_share_one_qualified_training_record() -> None:
    corpus = build_training_corpus(
        (
            _example(
                example_id="example-1",
                training_record_id="record-1",
                source_sha256=_SHA_A,
            ),
            _example(
                example_id="example-2",
                training_record_id="record-1",
                source_sha256=_SHA_B,
            ),
        )
    )
    report = bind_training_corpus(
        qualification=_pass_qualification(("record-1",)),
        corpus=corpus,
    )

    assert report.disposition == "PASS"
    assert report.example_count == 2


def test_metadata_change_changes_corpus_and_raw_identity_not_membership_identity() -> None:
    original = build_training_corpus(
        (
            _example(
                example_id="example-1",
                training_record_id="record-1",
                source_sha256=_SHA_A,
            ),
        )
    )
    changed = build_training_corpus(
        (
            _example(
                example_id="example-1",
                training_record_id="record-1",
                source_sha256=_SHA_A,
                source_license="MIT",
            ),
        )
    )
    qualification = _pass_qualification(("record-1",))

    left = bind_training_corpus(qualification=qualification, corpus=original)
    right = bind_training_corpus(qualification=qualification, corpus=changed)

    assert left.disposition == right.disposition == "PASS"
    assert left.corpus_training_record_ids_sha256 == right.corpus_training_record_ids_sha256
    assert left.corpus_sha256 != right.corpus_sha256
    assert left.canonical_jsonl_sha256 != right.canonical_jsonl_sha256


def test_unicode_record_ids_use_exact_t5_hash_algorithm() -> None:
    alpha = f"{chr(0x03B1)}-1"
    beta = f"{chr(0x03B2)}-2"
    corpus = build_training_corpus(
        (
            _example(example_id="example-1", training_record_id=beta, source_sha256=_SHA_A),
            _example(example_id="example-2", training_record_id=alpha, source_sha256=_SHA_B),
        )
    )
    qualification = _pass_qualification((beta, alpha))

    report = bind_training_corpus(qualification=qualification, corpus=corpus)

    assert report.disposition == "PASS"
    assert report.corpus_training_record_ids_sha256 == _record_ids_sha256((alpha, beta))


def test_blocked_t5_qualification_cannot_produce_pass_binding() -> None:
    corpus = _corpus()
    report = bind_training_corpus(
        qualification=_blocked_qualification(corpus.training_record_ids),
        corpus=corpus,
    )

    assert report.disposition == "BLOCKED"
    assert report.can_attest_local_artifact is False
    assert "qualification is not PASS" in report.blockers[0]


def test_binding_is_deterministic() -> None:
    corpus = _corpus()
    qualification = _pass_qualification(corpus.training_record_ids)

    first = bind_training_corpus(qualification=qualification, corpus=corpus)
    second = bind_training_corpus(qualification=qualification, corpus=corpus)

    assert first == second
    assert first.binding_sha256 == second.binding_sha256


def test_direct_pass_report_cannot_claim_mismatch_zero_size_or_blockers() -> None:
    corpus = _corpus()
    report = bind_training_corpus(
        qualification=_pass_qualification(corpus.training_record_ids),
        corpus=corpus,
    )

    with pytest.raises(TrainingCorpusBindingError, match="identity equality"):
        replace(report, corpus_training_record_ids_sha256=_SHA_F)
    with pytest.raises(TrainingCorpusBindingError, match="positive canonical_jsonl"):
        replace(report, canonical_jsonl_byte_count=0)
    with pytest.raises(TrainingCorpusBindingError, match="positive example_count"):
        replace(report, example_count=0)
    with pytest.raises(TrainingCorpusBindingError, match="cannot have blockers"):
        replace(report, blockers=("forged",))


def test_binding_rejects_subclassed_canonical_inputs() -> None:
    class FakeCorpus(TrainingCorpusV1):
        pass

    class FakeQualification(TrainingDatasetQualificationReport):
        pass

    corpus = _corpus()
    qualification = _pass_qualification(corpus.training_record_ids)
    fake_corpus = FakeCorpus(examples=corpus.examples)
    fake_qualification = FakeQualification(
        disposition="PASS",
        dataset_release_sha256=qualification.dataset_release_sha256,
        audit_report_sha256=qualification.audit_report_sha256,
        quality_report_sha256=qualification.quality_report_sha256,
        split_freeze_sha256=qualification.split_freeze_sha256,
        training_record_ids_sha256=qualification.training_record_ids_sha256,
        training_dataset_sha256=qualification.training_dataset_sha256,
        provenance_ledger_sha256=qualification.provenance_ledger_sha256,
        decontamination_report_sha256=qualification.decontamination_report_sha256,
        license_review_sha256=qualification.license_review_sha256,
        phi_scan_sha256=qualification.phi_scan_sha256,
        r2_review_sha256=qualification.r2_review_sha256,
        heldout_exclusion_report_sha256=qualification.heldout_exclusion_report_sha256,
        heldout_eval_record_ids_sha256=qualification.heldout_eval_record_ids_sha256,
        r2_training_data_only=True,
        heldout_eval_excluded_from_training=True,
        phi_present=False,
        blockers=(),
    )

    with pytest.raises(TrainingCorpusBindingError, match="exact TrainingCorpusV1"):
        bind_training_corpus(qualification=qualification, corpus=fake_corpus)
    with pytest.raises(
        TrainingCorpusBindingError,
        match="exact TrainingDatasetQualificationReport",
    ):
        bind_training_corpus(qualification=fake_qualification, corpus=corpus)
