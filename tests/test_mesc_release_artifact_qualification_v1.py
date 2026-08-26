"""Tests for fail-closed MESC release-artifact qualification."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._release_artifact_qualification_v1 import (
    ReleaseArtifactQualificationError,
    ReleaseAssetObservation,
    ReleaseEvidenceBinding,
    ReleaseObservation,
    qualify_release_artifact,
)
from medscale.mesc._release_semantic_evidence_v1 import (
    ReleaseBoundEvidenceDocument,
    ReleaseSemanticEvidenceBundle,
    TrainingExecutionEvidence,
)
from medscale.reproducibility import content_hash

_REPOSITORY = "TheHalfMoon/MESC"
_TAG = "v0.1.1"
_RELEASE_ID = 1
_A = "a" * 64
_B = "b" * 64


def _asset(
    *,
    name: str = "mesc-compact-adapter.safetensors",
    size_bytes: int = 1024,
    content_sha256: str = _A,
    browser_download_url: str = "https://example.invalid/mesc-compact-adapter.safetensors",
) -> ReleaseAssetObservation:
    return ReleaseAssetObservation(
        name=name,
        size_bytes=size_bytes,
        content_sha256=content_sha256,
        browser_download_url=browser_download_url,
    )


def _training_evidence() -> TrainingExecutionEvidence:
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
    payload: dict[str, object] = {
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
    return TrainingExecutionEvidence(canonical_json_bytes(payload))


def _asset_manifest(
    assets: tuple[ReleaseAssetObservation, ...],
    *,
    repository: str = _REPOSITORY,
    tag_name: str = _TAG,
    release_id: int = _RELEASE_ID,
) -> str:
    provisional = ReleaseObservation(
        repository=repository,
        tag_name=tag_name,
        release_id=release_id,
        assets=assets,
        evidence_binding=None,
    )
    return provisional.asset_manifest_sha256


def _artifact_bytes(kind: str, *, asset_manifest: str, training_sha: str) -> bytes:
    if kind == "PROVENANCE":
        payload: dict[str, object] = {
            "asset_manifest_sha256": asset_manifest,
            "training_execution_receipt_sha256": training_sha,
        }
    elif kind == "RIGHTS":
        payload = {
            "asset_manifest_sha256": asset_manifest,
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
            "asset_manifest_sha256": asset_manifest,
            "disposition": "PASS",
            "training_execution_receipt_sha256": training_sha,
        }
    else:  # pragma: no cover - fixture contract
        raise AssertionError(kind)
    return canonical_json_bytes(payload)


def _document(
    kind: str,
    *,
    repository: str,
    tag_name: str,
    release_id: int,
    asset_manifest: str,
    training_sha: str,
) -> ReleaseBoundEvidenceDocument:
    artifact = _artifact_bytes(
        kind,
        asset_manifest=asset_manifest,
        training_sha=training_sha,
    )
    envelope = {
        "artifact_byte_count": len(artifact),
        "artifact_sha256": hashlib.sha256(artifact).hexdigest(),
        "asset_manifest_sha256": asset_manifest,
        "disposition": "PASS",
        "kind": f"mesc.release.{kind.lower()}.v1",
        "release_id": release_id,
        "repository": repository,
        "tag_name": tag_name,
        "training_execution_receipt_sha256": training_sha,
    }
    return ReleaseBoundEvidenceDocument(
        kind=kind,  # type: ignore[arg-type]
        canonical_envelope_bytes=canonical_json_bytes(envelope),
        artifact_bytes=artifact,
    )


def _semantic(
    assets: tuple[ReleaseAssetObservation, ...],
    *,
    repository: str = _REPOSITORY,
    tag_name: str = _TAG,
    release_id: int = _RELEASE_ID,
) -> ReleaseSemanticEvidenceBundle:
    training = _training_evidence()
    asset_manifest = _asset_manifest(
        assets,
        repository=repository,
        tag_name=tag_name,
        release_id=release_id,
    )
    common = {
        "repository": repository,
        "tag_name": tag_name,
        "release_id": release_id,
        "asset_manifest": asset_manifest,
        "training_sha": training.receipt_sha256,
    }
    return ReleaseSemanticEvidenceBundle(
        training_execution=training,
        provenance=_document("PROVENANCE", **common),
        rights=_document("RIGHTS", **common),
        sbom=_document("SBOM", **common),
        evaluation=_document("EVALUATION", **common),
    )


def _binding(
    assets: tuple[ReleaseAssetObservation, ...],
    *,
    semantic: ReleaseSemanticEvidenceBundle | None = None,
    repository: str = _REPOSITORY,
    tag_name: str = _TAG,
    release_id: int = _RELEASE_ID,
    **overrides: object,
) -> ReleaseEvidenceBinding:
    selected = (
        _semantic(
            assets,
            repository=repository,
            tag_name=tag_name,
            release_id=release_id,
        )
        if semantic is None
        else semantic
    )
    kwargs: dict[str, object] = {
        "repository": repository,
        "tag_name": tag_name,
        "release_id": release_id,
        "asset_manifest_sha256": _asset_manifest(
            assets,
            repository=repository,
            tag_name=tag_name,
            release_id=release_id,
        ),
        "provenance_sha256": selected.provenance.document_sha256,
        "rights_sha256": selected.rights.document_sha256,
        "sbom_sha256": selected.sbom.document_sha256,
        "evaluation_report_sha256": selected.evaluation.document_sha256,
        "training_execution_receipt_sha256": selected.training_execution.receipt_sha256,
        "independent_refetch_verified": True,
        "asset_hashes_verified": True,
    }
    kwargs.update(overrides)
    return ReleaseEvidenceBinding(**kwargs)  # type: ignore[arg-type]


def _observation(
    *,
    repository: str = _REPOSITORY,
    tag_name: str = _TAG,
    release_id: int = _RELEASE_ID,
    assets: tuple[ReleaseAssetObservation, ...] | None = None,
    include_semantic: bool = True,
    **overrides: object,
) -> ReleaseObservation:
    selected_assets = (_asset(),) if assets is None else assets
    semantic = (
        _semantic(
            selected_assets,
            repository=repository,
            tag_name=tag_name,
            release_id=release_id,
        )
        if include_semantic
        else None
    )
    kwargs: dict[str, object] = {
        "repository": repository,
        "tag_name": tag_name,
        "release_id": release_id,
        "assets": selected_assets,
        "evidence_binding": _binding(
            selected_assets,
            semantic=semantic,
            repository=repository,
            tag_name=tag_name,
            release_id=release_id,
        ),
        "semantic_evidence": semantic,
    }
    kwargs.update(overrides)
    return ReleaseObservation(**kwargs)  # type: ignore[arg-type]


def test_complete_verified_release_is_ready() -> None:
    report = qualify_release_artifact(_observation())
    assert report.disposition == "RELEASE_READY"
    assert report.asset_count == 1
    assert report.blockers == ()
    assert report.medscale_spec_012_admission_readiness == "READY"


def test_opaque_hash_binding_without_semantic_evidence_is_blocked() -> None:
    report = qualify_release_artifact(_observation(include_semantic=False))
    assert report.disposition == "BLOCKED"
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert "semantic release evidence is absent" in report.blockers


def test_live_empty_v010_shape_is_blocked_and_not_ready() -> None:
    observation = ReleaseObservation(
        repository=_REPOSITORY,
        tag_name="v0.1.0",
        release_id=352847712,
        assets=(),
        evidence_binding=None,
    )
    report = qualify_release_artifact(observation)
    assert report.disposition == "BLOCKED"
    assert report.asset_count == 0
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert "release assets are empty" in report.blockers
    assert "evidence_binding is absent" in report.blockers
    assert "semantic release evidence is absent" in report.blockers


def test_unbound_evidence_digests_remain_blocked() -> None:
    assets = (_asset(),)
    semantic = _semantic(assets)
    mismatched = _binding(
        assets,
        semantic=semantic,
        repository="OtherOrg/OtherRepo",
        tag_name="v9.9.9",
        release_id=999,
        asset_manifest_sha256="0" * 64,
    )
    report = qualify_release_artifact(
        _observation(assets=assets, evidence_binding=mismatched)
    )
    assert report.disposition == "BLOCKED"
    assert "evidence_binding repository does not match observation" in report.blockers
    assert "evidence_binding tag_name does not match observation" in report.blockers
    assert "evidence_binding release_id does not match observation" in report.blockers
    assert "evidence_binding asset_manifest_sha256 does not match assets" in report.blockers


def test_refuses_unverified_hashes_even_with_semantic_evidence() -> None:
    assets = (_asset(),)
    semantic = _semantic(assets)
    binding = _binding(
        assets,
        semantic=semantic,
        independent_refetch_verified=False,
        asset_hashes_verified=False,
    )
    report = qualify_release_artifact(
        _observation(assets=assets, semantic_evidence=semantic, evidence_binding=binding)
    )
    assert report.disposition == "BLOCKED"
    assert "independent re-fetch verification is false" in report.blockers
    assert "asset hash verification is false" in report.blockers


def test_binding_hashes_must_equal_semantic_documents() -> None:
    observation = _observation()
    assert observation.evidence_binding is not None
    forged = replace(observation.evidence_binding, evaluation_report_sha256="0" * 64)
    report = qualify_release_artifact(replace(observation, evidence_binding=forged))

    assert report.disposition == "BLOCKED"
    assert (
        "evidence_binding evaluation_report_sha256 does not match semantic evidence"
        in report.blockers
    )


def test_asset_manifest_hash_is_order_independent() -> None:
    first = _asset(name="a-adapter.safetensors", content_sha256=_A)
    second = _asset(
        name="b-adapter.safetensors",
        content_sha256=_B,
        browser_download_url="https://example.invalid/b-adapter.safetensors",
    )
    left = ReleaseObservation(
        repository=_REPOSITORY,
        tag_name=_TAG,
        release_id=_RELEASE_ID,
        assets=(first, second),
        evidence_binding=None,
    )
    right = ReleaseObservation(
        repository=_REPOSITORY,
        tag_name=_TAG,
        release_id=_RELEASE_ID,
        assets=(second, first),
        evidence_binding=None,
    )
    assert left.asset_manifest_sha256 == right.asset_manifest_sha256


def test_refuses_zero_size_asset() -> None:
    with pytest.raises(ReleaseArtifactQualificationError, match="size_bytes"):
        _asset(size_bytes=0)


def test_deterministic_observation_identity() -> None:
    left = qualify_release_artifact(_observation())
    right = qualify_release_artifact(_observation())
    assert left.observation_sha256 == right.observation_sha256
    changed = qualify_release_artifact(_observation(tag_name="v0.1.2"))
    assert changed.observation_sha256 != left.observation_sha256


def test_refuses_duplicate_asset_names() -> None:
    with pytest.raises(ReleaseArtifactQualificationError, match="unique"):
        _observation(assets=(_asset(), _asset()))


def test_refuses_non_exact_observation_type() -> None:
    with pytest.raises(ReleaseArtifactQualificationError, match="exactly"):
        qualify_release_artifact(object())  # type: ignore[arg-type]


def test_ready_report_rejects_blockers_on_construct() -> None:
    ready = qualify_release_artifact(_observation())
    with pytest.raises(ReleaseArtifactQualificationError, match="blockers"):
        replace(ready, blockers=("forged",))
