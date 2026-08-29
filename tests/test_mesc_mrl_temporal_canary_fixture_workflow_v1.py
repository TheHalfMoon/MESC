"""MRL-0606 tests for the sealed temporal-canary fixture workflow."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_temporal_canary_fixture_workflow_v1 import (
    TemporalCanaryFixtureWorkflowError,
    run_temporal_canary_fixture_workflow,
)
from medscale.mesc._mrl_temporal_canary_manifest_v1 import TemporalCanarySourceKind
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_temporal_canary_manifest_v1 import _manifest


def test_fixture_canary_workflow_is_deterministic_and_identity_bound() -> None:
    manifest = _manifest()
    evaluator = _evaluator()
    surface = _surface(evaluator)

    first = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())
    second = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.manifest_sha256 == manifest.content_sha256
    assert first.canary_artifact_sha256 == manifest.canary_artifact_sha256
    assert first.surface_sha256 == surface.content_sha256
    assert first.evaluator_sha256 == evaluator.content_sha256
    assert first.observed_score == 1
    assert first.observed_max_score == 2


def test_hand_authored_fixture_canary_remains_r2_fixture_only() -> None:
    manifest = _manifest(source_kind=TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE)
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert receipt.source_kind is TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE
    assert receipt.fixture_only is True
    assert receipt.sealed is True


def test_receipt_never_exposes_or_recycles_canary_content() -> None:
    manifest = _manifest()
    evaluator = _evaluator()
    surface = _surface(evaluator)
    receipt = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert receipt.exposes_canary_content is False
    assert receipt.can_enter_training is False
    assert receipt.can_enter_search is False
    assert receipt.can_authorize is False
    assert receipt.semantic_dict()["workflow_mode"] == "R2_FIXTURE_ONLY"


def test_mutated_manifest_fails_closed() -> None:
    manifest = _manifest()
    object.__setattr__(manifest, "canary_artifact_sha256", "invalid")
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())


def test_evaluator_surface_mismatch_fails_closed() -> None:
    manifest = _manifest()
    evaluator = _evaluator()
    other_evaluator = _evaluator(targets=(_values()[0],))
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            other_evaluator,
            _values(),
        )


def test_wrong_manifest_type_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="exact TemporalCanaryManifest"):
        run_temporal_canary_fixture_workflow(
            object(),  # type: ignore[arg-type]
            surface,
            evaluator,
            _values(),
        )
