"""Tests for fail-closed readiness receipt binding."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt,
)
from medscale.mesc._training_readiness_receipt_binding_v1 import (
    TrainingReadinessReceiptBindingError,
    bind_runtime_qualification_to_readiness,
    bind_training_authorization_to_readiness,
    construct_ready_to_launch_readiness,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
    assess_training_readiness,
)
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationReceipt,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import RunnerClass
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe

_DATASET_SHA = "d" * 64
_CORPUS = "c" * 64
_ATTEST = "e" * 64
_SMOKE = "f" * 64


def _candidate(*, model_id: str, revision: str, weight_byte: str) -> TrainingCandidate:
    return TrainingCandidate(
        model_id=model_id,
        revision=revision,
        weights_sha256=weight_byte * 64,
        license_id="apache-2.0",
    )


def _recipe(candidate: TrainingCandidate) -> TrainingRecipe:
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
            content_sha256=_DATASET_SHA,
        ),
        seed=42,
        max_steps=100,
    )


def _scientific_manifest(**overrides: object) -> TrainingReadinessManifest:
    compact = _candidate(model_id="fixture/compact", revision="1" * 40, weight_byte="a")
    reasoner = _candidate(model_id="fixture/reasoner", revision="2" * 40, weight_byte="b")
    kwargs: dict[str, object] = {
        "compact_candidate": compact,
        "reasoner_candidate": reasoner,
        "compact_recipe": _recipe(compact),
        "reasoner_recipe": _recipe(reasoner),
        "pilot_closeout_sha256": "1" * 64,
        "tournament_report_sha256": "2" * 64,
        "training_dataset_sha256": _DATASET_SHA,
        "provenance_ledger_sha256": "3" * 64,
        "decontamination_report_sha256": "4" * 64,
        "evaluation_contract_sha256": "5" * 64,
        "license_review_sha256": "6" * 64,
        "pilot_closeout_disposition": "PASS",
        "tournament_disposition": "PASS",
        "decontamination_disposition": "PASS",
        "license_disposition": "PASS",
        "r2_training_data_only": True,
        "heldout_eval_excluded_from_training": True,
        "phi_present": False,
        "runtime_qualification_sha256": None,
        "training_authorization_receipt_sha256": None,
    }
    kwargs.update(overrides)
    return TrainingReadinessManifest(**kwargs)  # type: ignore[arg-type]


def _runtime(*, smoke: bool = True) -> TrainingRuntimeQualificationReceipt:
    return build_training_runtime_qualification_receipt(
        runner_class=RunnerClass.LOCAL,
        python_version="3.12.14",
        os_name="linux",
        gpu_model="fixture-gpu",
        dependency_lock_sha256="a" * 64,
        repository_sha="b" * 40,
        repository_tree="c" * 40,
        probe_id="fixture-probe",
        probe_version="v1",
        smoke_disposition="PASS" if smoke else "SKIPPED",
        smoke_receipt_sha256=_SMOKE if smoke else None,
    )


def test_binds_pass_runtime_and_authorized_receipt_to_ready_to_launch() -> None:
    scientific = _scientific_manifest()
    runtime = _runtime(smoke=True)
    with_runtime = bind_runtime_qualification_to_readiness(scientific, runtime)
    assert with_runtime.runtime_qualification_sha256 == runtime.receipt_sha256
    assert assess_training_readiness(with_runtime).disposition == "READY_FOR_AUTHORIZATION"

    auth = build_training_authorization_receipt(
        authorizer_id="founder",
        subject_readiness_manifest_sha256=with_runtime.manifest_sha256,
        runtime_qualification_sha256=runtime.receipt_sha256,
        corpus_binding_sha256=_CORPUS,
        local_asset_attestation_sha256=_ATTEST,
        authorization_statement="Authorize TRAINING_EXECUTION for the bound subject.",
        authorize=True,
    )
    final, report = construct_ready_to_launch_readiness(
        scientific,
        runtime_qualification=runtime,
        training_authorization=auth,
    )
    assert report.disposition == "READY_TO_LAUNCH"
    assert final.runtime_qualification_sha256 == runtime.receipt_sha256
    assert final.training_authorization_receipt_sha256 == auth.receipt_sha256


def test_refuses_observed_runtime_without_smoke() -> None:
    with pytest.raises(TrainingReadinessReceiptBindingError, match="platform_qualified"):
        bind_runtime_qualification_to_readiness(_scientific_manifest(), _runtime(smoke=False))


def test_refuses_blocked_authorization() -> None:
    scientific = _scientific_manifest()
    runtime = _runtime(smoke=True)
    with_runtime = bind_runtime_qualification_to_readiness(scientific, runtime)
    blocked = build_training_authorization_receipt(
        authorizer_id="founder",
        subject_readiness_manifest_sha256=with_runtime.manifest_sha256,
        runtime_qualification_sha256=runtime.receipt_sha256,
        corpus_binding_sha256=_CORPUS,
        local_asset_attestation_sha256=_ATTEST,
        authorization_statement="Refuse TRAINING_EXECUTION.",
        authorize=False,
    )
    with pytest.raises(TrainingReadinessReceiptBindingError, match="AUTHORIZED"):
        bind_training_authorization_to_readiness(with_runtime, blocked)


def test_refuses_authorization_subject_mismatch() -> None:
    scientific = _scientific_manifest()
    runtime = _runtime(smoke=True)
    with_runtime = bind_runtime_qualification_to_readiness(scientific, runtime)
    auth = build_training_authorization_receipt(
        authorizer_id="founder",
        subject_readiness_manifest_sha256="0" * 64,
        runtime_qualification_sha256=runtime.receipt_sha256,
        corpus_binding_sha256=_CORPUS,
        local_asset_attestation_sha256=_ATTEST,
        authorization_statement="Authorize TRAINING_EXECUTION.",
        authorize=True,
    )
    with pytest.raises(TrainingReadinessReceiptBindingError, match="subject_readiness"):
        bind_training_authorization_to_readiness(with_runtime, auth)


def test_refuses_authorization_without_runtime() -> None:
    scientific = _scientific_manifest()
    auth = build_training_authorization_receipt(
        authorizer_id="founder",
        subject_readiness_manifest_sha256=scientific.manifest_sha256,
        runtime_qualification_sha256="a" * 64,
        corpus_binding_sha256=_CORPUS,
        local_asset_attestation_sha256=_ATTEST,
        authorization_statement="Authorize TRAINING_EXECUTION.",
        authorize=True,
    )
    with pytest.raises(TrainingReadinessReceiptBindingError, match="runtime_qualification"):
        bind_training_authorization_to_readiness(scientific, auth)


def test_refuses_scientific_blocker() -> None:
    blocked = replace(_scientific_manifest(), phi_present=True)
    with pytest.raises(TrainingReadinessReceiptBindingError, match="BLOCKED"):
        bind_runtime_qualification_to_readiness(blocked, _runtime(smoke=True))
