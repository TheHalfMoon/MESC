"""Tests for fail-closed MESC release-artifact qualification."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._release_artifact_qualification_v1 import (
    ReleaseArtifactQualificationError,
    ReleaseAssetObservation,
    ReleaseObservation,
    qualify_release_artifact,
)

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64
_E = "e" * 64
_F = "f" * 64


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


def _observation(**overrides: object) -> ReleaseObservation:
    kwargs: dict[str, object] = {
        "repository": "TheHalfMoon/MESC",
        "tag_name": "v0.1.1",
        "release_id": 1,
        "assets": (_asset(),),
        "provenance_sha256": _B,
        "rights_sha256": _C,
        "sbom_sha256": _D,
        "evaluation_report_sha256": _E,
        "training_execution_receipt_sha256": _F,
        "independent_refetch_verified": True,
        "asset_hashes_verified": True,
    }
    kwargs.update(overrides)
    return ReleaseObservation(**kwargs)  # type: ignore[arg-type]


def test_complete_verified_release_is_ready() -> None:
    report = qualify_release_artifact(_observation())
    assert report.disposition == "RELEASE_READY"
    assert report.asset_count == 1
    assert report.blockers == ()
    assert report.medscale_spec_012_admission_readiness == "READY"


def test_live_empty_v010_shape_is_blocked_and_not_ready() -> None:
    observation = _observation(
        tag_name="v0.1.0",
        release_id=352847712,
        assets=(),
        provenance_sha256=None,
        rights_sha256=None,
        sbom_sha256=None,
        evaluation_report_sha256=None,
        training_execution_receipt_sha256=None,
        independent_refetch_verified=False,
        asset_hashes_verified=False,
    )
    report = qualify_release_artifact(observation)
    assert report.disposition == "BLOCKED"
    assert report.asset_count == 0
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert "release assets are empty" in report.blockers
    assert "provenance_sha256 is absent" in report.blockers
    assert "rights_sha256 is absent" in report.blockers
    assert "sbom_sha256 is absent" in report.blockers
    assert "evaluation_report_sha256 is absent" in report.blockers
    assert "training_execution_receipt_sha256 is absent" in report.blockers
    assert "independent re-fetch verification is false" in report.blockers
    assert "asset hash verification is false" in report.blockers


def test_refuses_unverified_hashes_even_with_assets() -> None:
    report = qualify_release_artifact(
        _observation(independent_refetch_verified=False, asset_hashes_verified=False)
    )
    assert report.disposition == "BLOCKED"
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert "independent re-fetch verification is false" in report.blockers
    assert "asset hash verification is false" in report.blockers


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
