"""MRL-0605 tests for the R2-compatible temporal-canary manifest."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_temporal_canary_manifest_v1 import (
    TemporalCanaryManifest,
    TemporalCanaryManifestError,
    TemporalCanarySourceKind,
)


def _manifest(
    *,
    source_kind: TemporalCanarySourceKind = TemporalCanarySourceKind.SYNTHETIC,
    artifact: str = "a" * 64,
) -> TemporalCanaryManifest:
    return TemporalCanaryManifest(
        canary_id="canary-001",
        source_kind=source_kind,
        canary_artifact_sha256=artifact,
        temporal_boundary_at="2026-01-01T00:00:00Z",
        created_at="2026-02-01T00:00:00Z",
        evaluator_artifact_sha256="b" * 64,
        topic_tags=("fixture", "temporal"),
    )


def test_synthetic_canary_manifest_is_deterministic_and_sealed() -> None:
    first = _manifest()
    second = _manifest()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.semantic_dict()["sealed"] is True
    assert first.can_enter_training is False
    assert first.can_enter_search is False
    assert first.can_authorize is False


def test_hand_authored_fixture_is_the_only_other_current_r2_source_kind() -> None:
    manifest = _manifest(source_kind=TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE)

    assert manifest.semantic_dict()["source_kind"] == "HAND_AUTHORED_FIXTURE"


def test_canary_must_be_created_strictly_after_frozen_boundary() -> None:
    with pytest.raises(TemporalCanaryManifestError, match="strictly after"):
        TemporalCanaryManifest(
            canary_id="canary-001",
            source_kind=TemporalCanarySourceKind.SYNTHETIC,
            canary_artifact_sha256="a" * 64,
            temporal_boundary_at="2026-02-01T00:00:00Z",
            created_at="2026-02-01T00:00:00Z",
            evaluator_artifact_sha256="b" * 64,
            topic_tags=("fixture",),
        )


def test_manifest_identity_changes_with_canary_artifact_identity() -> None:
    first = _manifest(artifact="a" * 64)
    second = _manifest(artifact="c" * 64)

    assert first.content_sha256 != second.content_sha256


def test_topic_tags_must_be_nonempty_sorted_and_unique() -> None:
    with pytest.raises(TemporalCanaryManifestError, match="sorted and unique"):
        TemporalCanaryManifest(
            canary_id="canary-001",
            source_kind=TemporalCanarySourceKind.SYNTHETIC,
            canary_artifact_sha256="a" * 64,
            temporal_boundary_at="2026-01-01T00:00:00Z",
            created_at="2026-02-01T00:00:00Z",
            evaluator_artifact_sha256="b" * 64,
            topic_tags=("temporal", "fixture"),
        )
