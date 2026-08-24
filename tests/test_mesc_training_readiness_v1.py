"""Tests for the fail-closed MESC training-readiness gate."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
    assess_training_readiness,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe

_DATASET_SHA = "d" * 64


def _candidate(*, model_id: str, revision: str, weight_byte: str) -> TrainingCandidate:
    return TrainingCandidate(
        model_id=model_id,
        revision=revision,
        weights_sha256=weight_byte * 64,
        license_id="apache-2.0",
    )


def _recipe(candidate: TrainingCandidate, *, dataset_sha: str = _DATASET_SHA) -> TrainingRecipe:
    return TrainingRecipe(
        base=ModelRef(
            model_id=candidate.model_id,
            revision=candidate.revision,
            quantization="nf4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef(
            name="mesc-evidence-sft-v1",
            version="1.0.0",
            content_sha256=dataset_sha,
        ),
        seed=42,
        max_steps=100,
    )


def _manifest(
    *,
    runtime_receipt: str | None = "7" * 64,
    authorization_receipt: str | None = "8" * 64,
) -> TrainingReadinessManifest:
    compact = _candidate(
        model_id="fixture/compact",
        revision="1" * 40,
        weight_byte="a",
    )
    reasoner = _candidate(
        model_id="fixture/reasoner",
        revision="2" * 40,
        weight_byte="b",
    )
    return TrainingReadinessManifest(
        compact_candidate=compact,
        reasoner_candidate=reasoner,
        compact_recipe=_recipe(compact),
        reasoner_recipe=_recipe(reasoner),
        pilot_closeout_sha256="1" * 64,
        tournament_report_sha256="2" * 64,
        training_dataset_sha256=_DATASET_SHA,
        provenance_ledger_sha256="3" * 64,
        decontamination_report_sha256="4" * 64,
        evaluation_contract_sha256="5" * 64,
        license_review_sha256="6" * 64,
        pilot_closeout_disposition="PASS",
        tournament_disposition="PASS",
        decontamination_disposition="PASS",
        license_disposition="PASS",
        r2_training_data_only=True,
        heldout_eval_excluded_from_training=True,
        phi_present=False,
        runtime_qualification_sha256=runtime_receipt,
        training_authorization_receipt_sha256=authorization_receipt,
    )


def test_complete_manifest_is_ready_to_launch() -> None:
    manifest = _manifest()

    report = assess_training_readiness(manifest)

    assert report.disposition == "READY_TO_LAUNCH"
    assert report.can_launch_training is True
    assert report.blockers == ()
    assert report.launch_requirements == ()
    assert report.manifest_sha256 == manifest.manifest_sha256
    assert len(report.manifest_sha256) == 64


def test_manifest_without_live_receipts_is_ready_for_authorization() -> None:
    report = assess_training_readiness(
        _manifest(runtime_receipt=None, authorization_receipt=None)
    )

    assert report.disposition == "READY_FOR_AUTHORIZATION"
    assert report.can_launch_training is False
    assert report.blockers == ()
    assert report.launch_requirements == (
        "runtime qualification receipt is required",
        "training authorization receipt is required",
    )


def test_policy_and_closeout_failures_block_training() -> None:
    manifest = replace(
        _manifest(),
        pilot_closeout_disposition="BLOCKED",
        tournament_disposition="BLOCKED",
        decontamination_disposition="BLOCKED",
        license_disposition="BLOCKED",
        r2_training_data_only=False,
        heldout_eval_excluded_from_training=False,
        phi_present=True,
    )

    report = assess_training_readiness(manifest)

    assert report.disposition == "BLOCKED"
    assert report.can_launch_training is False
    assert report.launch_requirements == ()
    assert report.blockers == (
        "pilot_closeout_disposition must be exactly PASS",
        "tournament_disposition must be exactly PASS",
        "decontamination_disposition must be exactly PASS",
        "license_disposition must be exactly PASS",
        "training data is not proven R2-compatible",
        "held-out evaluation data is not proven excluded from training",
        "PHI is present in the proposed training input",
    )


def test_recipe_must_bind_exact_candidate_and_dataset() -> None:
    manifest = _manifest()
    wrong_base = TrainingRecipe(
        base=ModelRef(
            model_id="fixture/not-selected",
            revision="9" * 40,
            quantization="nf4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef(
            name="wrong-data",
            version="1",
            content_sha256="e" * 64,
        ),
        seed=42,
        max_steps=100,
    )

    report = assess_training_readiness(replace(manifest, compact_recipe=wrong_base))

    assert report.disposition == "BLOCKED"
    assert report.blockers == (
        "compact recipe base model_id does not match selected candidate",
        "compact recipe base revision does not match selected candidate",
        "compact recipe dataset hash does not match training dataset",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pilot_closeout_sha256", "A" * 64),
        ("tournament_report_sha256", "x" * 64),
        ("training_dataset_sha256", "0" * 63),
        ("provenance_ledger_sha256", ""),
        ("decontamination_report_sha256", "abc"),
        ("evaluation_contract_sha256", "g" * 64),
        ("license_review_sha256", "h" * 64),
        ("runtime_qualification_sha256", "F" * 64),
        ("training_authorization_receipt_sha256", "1" * 65),
    ],
)
def test_manifest_rejects_noncanonical_sha256(field: str, value: str) -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        replace(_manifest(), **{field: value})


def test_candidate_requires_exact_revision_and_weight_identity() -> None:
    with pytest.raises(ValueError, match="40 lowercase hex"):
        _candidate(model_id="fixture/model", revision="A" * 40, weight_byte="a")

    with pytest.raises(ValueError, match="64 lowercase hex"):
        TrainingCandidate(
            model_id="fixture/model",
            revision="a" * 40,
            weights_sha256="z" * 64,
            license_id="apache-2.0",
        )


def test_manifest_identity_changes_when_launch_authority_changes() -> None:
    pre_authority = _manifest(runtime_receipt=None, authorization_receipt=None)
    launch_ready = _manifest()

    assert pre_authority.manifest_sha256 != launch_ready.manifest_sha256


def test_program_version_is_frozen() -> None:
    with pytest.raises(ValueError, match="program_version"):
        replace(_manifest(), program_version="MESC-TRAINING-READINESS-V2")
