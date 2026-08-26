"""Tests for semantic MESC release evidence validation."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._release_semantic_evidence_v1 import (
    ReleaseBoundEvidenceDocument,
    ReleaseSemanticEvidenceBundle,
    ReleaseSemanticEvidenceError,
    TrainingExecutionEvidence,
)
from medscale.reproducibility import content_hash

_REPOSITORY = "TheHalfMoon/MESC"
_TAG = "v0.1.1"
_RELEASE_ID = 7
_ASSET_MANIFEST = "a" * 64


def _training_payload() -> dict[str, object]:
    artifacts = [
        {
            "byte_count": 10,
            "path": "experiments/compact/outputs/adapter.safetensors",
            "sha256": "1" * 64,
        },
        {
            "byte_count": 20,
            "path": "experiments/compact/results/metrics.json",
            "sha256": "2" * 64,
        },
    ]
    result_manifest = content_hash(
        {
            "artifacts": artifacts,
            "kind": "mesc.training_execution.results.v1",
        }
    )
    return {
        "backend_id": "hf-local-sft",
        "backend_version": "v1",
        "corpus_binding_sha256": "3" * 64,
        "dependency_lock_sha256": "4" * 64,
        "disposition": "SUCCEEDED",
        "environment_sha256": "5" * 64,
        "execution_manifest_sha256": "6" * 64,
        "executor_version": "MESC-TRAINING-EXECUTOR-V1",
        "experiment_id": "mesc-t6-compact-sft",
        "failure_reason": None,
        "finished_at": "2026-08-26T06:00:02Z",
        "launch_plan_sha256": "7" * 64,
        "local_asset_attestation_sha256": "8" * 64,
        "model_id": "fixture/compact",
        "readiness_manifest_sha256": "9" * 64,
        "repository_sha": "a" * 40,
        "repository_tree": "b" * 40,
        "result_artifacts": artifacts,
        "result_manifest_sha256": result_manifest,
        "revision": "c" * 40,
        "role": "compact",
        "run_plan_sha256": "b" * 64,
        "runtime_qualification_sha256": "c" * 64,
        "started_at": "2026-08-26T06:00:00Z",
        "training_authorization_receipt_sha256": "d" * 64,
        "training_dataset_sha256": "e" * 64,
        "weights_sha256": "f" * 64,
    }


def _training_evidence() -> TrainingExecutionEvidence:
    return TrainingExecutionEvidence(canonical_json_bytes(_training_payload()))


def _artifact_bytes(kind: str, training_sha: str) -> bytes:
    if kind == "PROVENANCE":
        payload: dict[str, object] = {
            "asset_manifest_sha256": _ASSET_MANIFEST,
            "training_execution_receipt_sha256": training_sha,
        }
    elif kind == "RIGHTS":
        payload = {
            "asset_manifest_sha256": _ASSET_MANIFEST,
            "disposition": "PASS",
        }
    elif kind == "SBOM":
        payload = {
            "bomFormat": "CycloneDX",
            "components": [{"name": "mesc-adapter", "version": "0.1.1"}],
            "specVersion": "1.6",
        }
    elif kind == "EVALUATION":
        payload = {
            "asset_manifest_sha256": _ASSET_MANIFEST,
            "disposition": "PASS",
            "training_execution_receipt_sha256": training_sha,
        }
    else:  # pragma: no cover - fixture contract
        raise AssertionError(kind)
    return canonical_json_bytes(payload)


def _document(kind: str, training_sha: str) -> ReleaseBoundEvidenceDocument:
    artifact = _artifact_bytes(kind, training_sha)
    envelope = {
        "artifact_byte_count": len(artifact),
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "asset_manifest_sha256": _ASSET_MANIFEST,
        "disposition": "PASS",
        "kind": f"mesc.release.{kind.lower()}.v1",
        "release_id": _RELEASE_ID,
        "repository": _REPOSITORY,
        "tag_name": _TAG,
        "training_execution_receipt_sha256": training_sha,
    }
    return ReleaseBoundEvidenceDocument(
        kind=kind,  # type: ignore[arg-type]
        canonical_envelope_bytes=canonical_json_bytes(envelope),
        artifact_bytes=artifact,
    )


def _bundle() -> ReleaseSemanticEvidenceBundle:
    training = _training_evidence()
    return ReleaseSemanticEvidenceBundle(
        training_execution=training,
        provenance=_document("PROVENANCE", training.receipt_sha256),
        rights=_document("RIGHTS", training.receipt_sha256),
        sbom=_document("SBOM", training.receipt_sha256),
        evaluation=_document("EVALUATION", training.receipt_sha256),
    )


def test_complete_semantic_bundle_is_deterministic() -> None:
    left = _bundle()
    right = _bundle()

    assert left.repository == _REPOSITORY
    assert left.tag_name == _TAG
    assert left.release_id == _RELEASE_ID
    assert left.asset_manifest_sha256 == _ASSET_MANIFEST
    assert len(left.bundle_sha256) == 64
    assert left.bundle_sha256 == right.bundle_sha256


def test_failed_training_receipt_is_rejected() -> None:
    payload = _training_payload()
    payload["disposition"] = "FAILED"
    payload["failure_reason"] = "fixture failure"

    with pytest.raises(ReleaseSemanticEvidenceError, match="SUCCEEDED"):
        TrainingExecutionEvidence(canonical_json_bytes(payload))


def test_training_result_manifest_must_match_artifacts() -> None:
    payload = _training_payload()
    payload["result_manifest_sha256"] = "0" * 64

    with pytest.raises(ReleaseSemanticEvidenceError, match="result_manifest_sha256"):
        TrainingExecutionEvidence(canonical_json_bytes(payload))


def test_evidence_envelope_cannot_hash_different_artifact_bytes() -> None:
    training = _training_evidence()
    artifact = _artifact_bytes("RIGHTS", training.receipt_sha256)
    envelope = {
        "artifact_byte_count": len(artifact),
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "asset_manifest_sha256": _ASSET_MANIFEST,
        "disposition": "PASS",
        "kind": "mesc.release.rights.v1",
        "release_id": _RELEASE_ID,
        "repository": _REPOSITORY,
        "tag_name": _TAG,
        "training_execution_receipt_sha256": training.receipt_sha256,
    }

    with pytest.raises(ReleaseSemanticEvidenceError, match="artifact_sha256"):
        ReleaseBoundEvidenceDocument(
            kind="RIGHTS",
            canonical_envelope_bytes=canonical_json_bytes(envelope),
            artifact_bytes=artifact + b" ",
        )


def test_bundle_rejects_document_bound_to_other_training_receipt() -> None:
    bundle = _bundle()
    wrong = _document("EVALUATION", "0" * 64)

    with pytest.raises(ReleaseSemanticEvidenceError, match="training receipt identity"):
        replace(bundle, evaluation=wrong)


def test_sbom_must_identify_supported_json_format() -> None:
    training = _training_evidence()
    artifact = canonical_json_bytes({"components": []})
    envelope = {
        "artifact_byte_count": len(artifact),
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "asset_manifest_sha256": _ASSET_MANIFEST,
        "disposition": "PASS",
        "kind": "mesc.release.sbom.v1",
        "release_id": _RELEASE_ID,
        "repository": _REPOSITORY,
        "tag_name": _TAG,
        "training_execution_receipt_sha256": training.receipt_sha256,
    }

    with pytest.raises(ReleaseSemanticEvidenceError, match="CycloneDX or SPDX"):
        ReleaseBoundEvidenceDocument(
            kind="SBOM",
            canonical_envelope_bytes=canonical_json_bytes(envelope),
            artifact_bytes=artifact,
        )


def test_noncanonical_or_duplicate_envelope_is_rejected() -> None:
    training = _training_evidence()
    artifact = _artifact_bytes("RIGHTS", training.receipt_sha256)
    duplicate = (
        b'{"artifact_byte_count":1,"artifact_byte_count":2,'
        b'"artifact_sha256":"' + b"a" * 64 + b'"}\n'
    )

    with pytest.raises(ReleaseSemanticEvidenceError):
        ReleaseBoundEvidenceDocument(
            kind="RIGHTS",
            canonical_envelope_bytes=duplicate,
            artifact_bytes=artifact,
        )
