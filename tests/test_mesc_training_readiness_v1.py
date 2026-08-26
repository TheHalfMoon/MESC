"""Tests for the fail-closed MESC training-readiness gate."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

from _training_authorization_test_support import (
    install_training_authorization_test_trust,
    restore_training_authorization_test_trust,
)
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    TrainingAuthorizationReceiptError,
)
from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt as _build_training_authorization_receipt,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
    assess_training_readiness,
)
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationReceipt,
    TrainingRuntimeSmokeEvidence,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import RunnerClass
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe

_DATASET_SHA = "d" * 64
_CORPUS_SHA = "c" * 64
_LOCK_SHA = "a" * 64
_REPO_SHA = "b" * 40
_TREE_SHA = "e" * 40


def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    authorization_subject_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    authorization_statement: str,
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Build explicit synthetic evidence under a test-only temporary trust registry."""
    artifact = None
    if authorize:
        artifact = canonical_json_bytes(
            {
                "authorization_scope": "TRAINING_EXECUTION",
                "authorization_statement": authorization_statement,
                "authorization_subject_sha256": authorization_subject_sha256,
                "authorize": True,
                "authorizer_id": authorizer_id,
                "corpus_binding_sha256": corpus_binding_sha256,
                "kind": "mesc.training_authorization.v1",
                "runtime_qualification_sha256": runtime_qualification_sha256,
            }
        )
    if artifact is None:
        return _build_training_authorization_receipt(
            authorizer_id=authorizer_id,
            authorization_subject_sha256=authorization_subject_sha256,
            runtime_qualification_sha256=runtime_qualification_sha256,
            corpus_binding_sha256=corpus_binding_sha256,
            authorization_statement=authorization_statement,
            authorize=authorize,
            authorization_artifact=None,
        )
    install_training_authorization_test_trust(artifact)
    return _build_training_authorization_receipt(
        authorizer_id=authorizer_id,
        authorization_subject_sha256=authorization_subject_sha256,
        runtime_qualification_sha256=runtime_qualification_sha256,
        corpus_binding_sha256=corpus_binding_sha256,
        authorization_statement=authorization_statement,
        authorize=authorize,
        authorization_artifact=artifact,
    )


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


def _runtime_receipt() -> TrainingRuntimeQualificationReceipt:
    payload = {
        "dependency_lock_sha256": _LOCK_SHA,
        "disposition": "PASS",
        "gpu_model": "fixture-gpu",
        "kind": "mesc.training_runtime_smoke.v1",
        "network_accessed": False,
        "os_name": "linux",
        "probe_id": "fixture-probe",
        "probe_version": "v1",
        "python_version": "3.12.14",
        "remote_code_allowed": False,
        "repository_sha": _REPO_SHA,
        "repository_tree": _TREE_SHA,
        "runner_class": RunnerClass.LOCAL.value,
    }
    smoke = TrainingRuntimeSmokeEvidence(canonical_json_bytes(payload))
    return build_training_runtime_qualification_receipt(
        runner_class=RunnerClass.LOCAL,
        python_version="3.12.14",
        os_name="linux",
        gpu_model="fixture-gpu",
        dependency_lock_sha256=_LOCK_SHA,
        repository_sha=_REPO_SHA,
        repository_tree=_TREE_SHA,
        probe_id="fixture-probe",
        probe_version="v1",
        smoke_evidence=smoke,
    )


def _manifest_without_authorization() -> TrainingReadinessManifest:
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
    runtime = _runtime_receipt()
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
        corpus_binding_sha256=_CORPUS_SHA,
        runtime_qualification_sha256=runtime.receipt_sha256,
        runtime_qualification_receipt=runtime,
    )


def _authorized_manifest() -> TrainingReadinessManifest:
    pre_authority = _manifest_without_authorization()
    authorization = build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=pre_authority.authorization_subject_sha256,
        runtime_qualification_sha256=pre_authority.runtime_qualification_sha256 or "",
        corpus_binding_sha256=pre_authority.corpus_binding_sha256 or "",
        authorization_statement="Fixture authorization for the exact training subject.",
        authorize=True,
    )
    return replace(
        pre_authority,
        training_authorization_receipt_sha256=authorization.receipt_sha256,
        training_authorization_receipt=authorization,
    )


def test_complete_typed_authority_manifest_is_ready_to_launch() -> None:
    manifest = _authorized_manifest()
    report = assess_training_readiness(manifest)

    assert report.disposition == "READY_TO_LAUNCH"
    assert report.can_launch_training is True
    assert report.blockers == ()
    assert report.launch_requirements == ()
    assert report.manifest_sha256 == manifest.manifest_sha256


def test_authorization_subject_is_stable_without_fixed_point() -> None:
    pre_authority = _manifest_without_authorization()
    final = _authorized_manifest()

    assert pre_authority.authorization_subject_sha256 == final.authorization_subject_sha256
    assert pre_authority.manifest_sha256 != final.manifest_sha256


def test_presence_only_hashes_do_not_unlock_launch() -> None:
    base = _manifest_without_authorization()
    forged = replace(
        base,
        runtime_qualification_receipt=None,
        runtime_qualification_sha256="7" * 64,
        training_authorization_receipt_sha256="8" * 64,
        training_authorization_receipt=None,
    )
    report = assess_training_readiness(forged)

    assert report.disposition == "READY_FOR_AUTHORIZATION"
    assert report.can_launch_training is False
    assert "validated runtime qualification receipt is required" in report.launch_requirements
    assert "validated training authorization receipt is required" in report.launch_requirements


def test_manifest_without_live_receipts_is_ready_for_authorization() -> None:
    base = _manifest_without_authorization()
    manifest = replace(
        base,
        corpus_binding_sha256=None,
        runtime_qualification_sha256=None,
        runtime_qualification_receipt=None,
    )
    report = assess_training_readiness(manifest)

    assert report.disposition == "READY_FOR_AUTHORIZATION"
    assert report.can_launch_training is False
    assert report.launch_requirements == (
        "canonical corpus binding is required",
        "runtime qualification receipt is required",
        "training authorization receipt is required",
    )


def test_caller_created_canonical_authorization_cannot_unlock_readiness() -> None:
    pre = _manifest_without_authorization()
    artifact = canonical_json_bytes(
        {
            "authorization_scope": "TRAINING_EXECUTION",
            "authorization_statement": "Forged caller authorization.",
            "authorization_subject_sha256": pre.authorization_subject_sha256,
            "authorize": True,
            "authorizer_id": "caller",
            "corpus_binding_sha256": pre.corpus_binding_sha256,
            "kind": "mesc.training_authorization.v1",
            "runtime_qualification_sha256": pre.runtime_qualification_sha256,
        }
    )
    with pytest.raises(TrainingAuthorizationReceiptError, match="trusted authorization registry"):
        _build_training_authorization_receipt(
            authorizer_id="caller",
            authorization_subject_sha256=pre.authorization_subject_sha256,
            runtime_qualification_sha256=pre.runtime_qualification_sha256 or "",
            corpus_binding_sha256=pre.corpus_binding_sha256 or "",
            authorization_statement="Forged caller authorization.",
            authorize=True,
            authorization_artifact=artifact,
        )

    report = assess_training_readiness(pre)
    assert report.disposition == "READY_FOR_AUTHORIZATION"
    assert report.can_launch_training is False


def test_authorization_for_different_subject_blocks() -> None:
    manifest = _authorized_manifest()
    changed = replace(manifest, tournament_report_sha256="9" * 64)
    report = assess_training_readiness(changed)

    assert report.disposition == "BLOCKED"
    assert "training authorization receipt targets a different readiness subject" in report.blockers


def test_policy_and_closeout_failures_block_training() -> None:
    manifest = replace(
        _authorized_manifest(),
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
    assert "pilot_closeout_disposition must be exactly PASS" in report.blockers
    assert "training data is not proven R2-compatible" in report.blockers
    assert "PHI is present in the proposed training input" in report.blockers


def test_recipe_must_bind_exact_candidate_and_dataset() -> None:
    manifest = _authorized_manifest()
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
    assert "compact recipe base model_id does not match selected candidate" in report.blockers
    assert "compact recipe dataset hash does not match training dataset" in report.blockers


_ManifestMutation = Callable[[TrainingReadinessManifest], TrainingReadinessManifest]
_HASH_MUTATIONS: tuple[_ManifestMutation, ...] = (
    lambda manifest: replace(manifest, pilot_closeout_sha256="A" * 64),
    lambda manifest: replace(manifest, tournament_report_sha256="x" * 64),
    lambda manifest: replace(manifest, training_dataset_sha256="0" * 63),
    lambda manifest: replace(manifest, provenance_ledger_sha256=""),
    lambda manifest: replace(manifest, decontamination_report_sha256="abc"),
    lambda manifest: replace(manifest, evaluation_contract_sha256="g" * 64),
    lambda manifest: replace(manifest, license_review_sha256="h" * 64),
    lambda manifest: replace(manifest, corpus_binding_sha256="F" * 64),
)


@pytest.mark.parametrize("mutation", _HASH_MUTATIONS)
def test_manifest_rejects_noncanonical_sha256(mutation: _ManifestMutation) -> None:
    with pytest.raises(ValueError, match="64 lowercase hex"):
        mutation(_authorized_manifest())


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


def test_manifest_rejects_receipt_hash_mismatch() -> None:
    base = _manifest_without_authorization()
    with pytest.raises(ValueError, match="does not match runtime_qualification_sha256"):
        replace(base, runtime_qualification_sha256="f" * 64)


def test_program_version_is_frozen() -> None:
    with pytest.raises(ValueError, match="program_version"):
        replace(_authorized_manifest(), program_version="MESC-TRAINING-READINESS-V2")


def test_revoked_authorization_blocks_ready_to_launch() -> None:
    manifest = _authorized_manifest()
    assert assess_training_readiness(manifest).disposition == "READY_TO_LAUNCH"

    restore_training_authorization_test_trust()
    report = assess_training_readiness(manifest)

    assert report.disposition == "BLOCKED"
    assert report.can_launch_training is False
    assert (
        "training authorization receipt is not trusted by the current canonical registry"
        in report.blockers
    )
