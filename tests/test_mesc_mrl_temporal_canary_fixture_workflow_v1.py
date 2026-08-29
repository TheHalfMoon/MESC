"""MRL-0606 tests for the sealed temporal-canary fixture workflow."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_research_surface_v1 import FixtureEvaluator
from medscale.mesc._mrl_temporal_canary_fixture_workflow_v1 import (
    TemporalCanaryFixtureWorkflowError,
    run_temporal_canary_fixture_workflow,
)
from medscale.mesc._mrl_temporal_canary_manifest_v1 import (
    TemporalCanaryManifest,
    TemporalCanarySourceKind,
)
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_temporal_canary_manifest_v1 import _manifest


def _bound_manifest(
    evaluator: FixtureEvaluator,
    *,
    source_kind: TemporalCanarySourceKind = TemporalCanarySourceKind.SYNTHETIC,
) -> TemporalCanaryManifest:
    return replace(
        _manifest(source_kind=source_kind),
        evaluator_artifact_sha256=evaluator.content_sha256,
    )


def test_fixture_canary_workflow_is_deterministic_and_identity_bound() -> None:
    evaluator = _evaluator()
    manifest = _bound_manifest(evaluator)
    surface = _surface(evaluator)

    first = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())
    second = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.manifest_sha256 == manifest.content_sha256
    assert first.canary_artifact_sha256 == manifest.canary_artifact_sha256
    assert first.surface_sha256 == surface.content_sha256
    assert first.evaluator_sha256 == evaluator.content_sha256
    assert first.evaluator_sha256 == manifest.evaluator_artifact_sha256
    assert first.observed_score == 1
    assert first.observed_max_score == 2


def test_hand_authored_fixture_canary_remains_r2_fixture_only() -> None:
    evaluator = _evaluator()
    manifest = _bound_manifest(
        evaluator,
        source_kind=TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE,
    )
    surface = _surface(evaluator)
    receipt = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert receipt.source_kind is TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE
    assert receipt.fixture_only is True
    assert receipt.sealed is True


def test_receipt_never_exposes_or_recycles_canary_content() -> None:
    evaluator = _evaluator()
    manifest = _bound_manifest(evaluator)
    surface = _surface(evaluator)
    receipt = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())

    assert receipt.exposes_canary_content is False
    assert receipt.can_enter_training is False
    assert receipt.can_enter_search is False
    assert receipt.can_authorize is False
    assert receipt.semantic_dict()["workflow_mode"] == "R2_FIXTURE_ONLY"


def test_mutated_manifest_fails_closed() -> None:
    evaluator = _evaluator()
    manifest = _bound_manifest(evaluator)
    object.__setattr__(manifest, "canary_artifact_sha256", "invalid")
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())


def test_manifest_evaluator_identity_mismatch_fails_closed() -> None:
    evaluator = _evaluator()
    manifest = replace(
        _bound_manifest(evaluator),
        evaluator_artifact_sha256="f" * 64,
    )
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="manifest evaluator identity"):
        run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())


def test_evaluator_surface_mismatch_fails_closed() -> None:
    evaluator = _evaluator()
    other_evaluator = _evaluator(targets=(_values()[0],))
    manifest = _bound_manifest(other_evaluator)
    surface = _surface(evaluator)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            other_evaluator,
            _values(),
        )


def test_mutated_receipt_fails_closed_on_public_views() -> None:
    evaluator = _evaluator()
    manifest = _bound_manifest(evaluator)
    surface = _surface(evaluator)
    receipt = run_temporal_canary_fixture_workflow(manifest, surface, evaluator, _values())
    object.__setattr__(receipt, "evaluation_sha256", "invalid")

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="64 lowercase hex"):
        receipt.semantic_dict()
    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="64 lowercase hex"):
        _ = receipt.content_sha256


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
