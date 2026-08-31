"""MRL-0606 tests for the sealed temporal-canary fixture workflow."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

import pytest

import medscale.mesc._mrl_temporal_canary_fixture_workflow_v1 as canary_module
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureCandidate,
    FixtureEvaluator,
    FixtureParameterValue,
    FixtureResearchSurface,
    build_fixture_candidate,
)
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
    surface: FixtureResearchSurface,
    parameter_values: tuple[FixtureParameterValue, ...],
    *,
    source_kind: TemporalCanarySourceKind = TemporalCanarySourceKind.SYNTHETIC,
) -> TemporalCanaryManifest:
    candidate = build_fixture_candidate(surface, parameter_values)
    return replace(
        _manifest(
            source_kind=source_kind,
            artifact=candidate.content_sha256,
        ),
        evaluator_artifact_sha256=evaluator.content_sha256,
    )


def test_fixture_canary_workflow_is_deterministic_and_identity_bound() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)

    first = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )
    second = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.manifest_sha256 == manifest.content_sha256
    assert first.canary_artifact_sha256 == manifest.canary_artifact_sha256
    assert first.canary_artifact_sha256 == first.candidate_sha256
    assert first.surface_sha256 == surface.content_sha256
    assert first.evaluator_sha256 == evaluator.content_sha256
    assert first.evaluator_sha256 == manifest.evaluator_artifact_sha256
    assert first.observed_score == 1
    assert first.observed_max_score == 2


def test_workflow_uses_fixture_snapshots_if_live_evaluator_drifts_mid_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    original_evaluator_sha256 = evaluator.content_sha256
    original_metric_id = evaluator.metric_id
    original_build_candidate: Callable[
        [FixtureResearchSurface, tuple[FixtureParameterValue, ...]], FixtureCandidate
    ] = canary_module.build_fixture_candidate
    mutation_performed = False

    def mutate_live_evaluator_then_build_snapshot(
        surface_snapshot: FixtureResearchSurface,
        values: tuple[FixtureParameterValue, ...],
    ) -> FixtureCandidate:
        nonlocal mutation_performed
        if not mutation_performed:
            mutation_performed = True
            object.__setattr__(evaluator, "metric_id", "fixture-metric-mutated")
        return original_build_candidate(surface_snapshot, values)

    monkeypatch.setattr(
        canary_module,
        "build_fixture_candidate",
        mutate_live_evaluator_then_build_snapshot,
    )

    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )

    assert mutation_performed is True
    assert receipt.evaluator_sha256 == original_evaluator_sha256
    assert receipt.metric_id == original_metric_id
    assert evaluator.content_sha256 != original_evaluator_sha256


def test_hand_authored_fixture_canary_remains_r2_fixture_only() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(
        evaluator,
        surface,
        parameter_values,
        source_kind=TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE,
    )
    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )

    assert receipt.source_kind is TemporalCanarySourceKind.HAND_AUTHORED_FIXTURE
    assert receipt.fixture_only is True
    assert receipt.sealed is True


def test_receipt_never_exposes_or_recycles_canary_content() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )

    assert receipt.exposes_canary_content is False
    assert receipt.can_enter_training is False
    assert receipt.can_enter_search is False
    assert receipt.can_authorize is False
    assert receipt.semantic_dict()["workflow_mode"] == "R2_FIXTURE_ONLY"


def test_manifest_canary_artifact_must_match_executed_fixture_candidate() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    manifest = _bound_manifest(evaluator, surface, _values())

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="artifact identity"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            evaluator,
            _values(beta=10),
        )


def test_mutated_manifest_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    object.__setattr__(manifest, "canary_artifact_sha256", "invalid")

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            evaluator,
            parameter_values,
        )


def test_valid_manifest_identity_mutation_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    object.__setattr__(manifest, "evaluator_artifact_sha256", "f" * 64)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            evaluator,
            parameter_values,
        )


def test_manifest_evaluator_identity_mismatch_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = replace(
        _bound_manifest(evaluator, surface, parameter_values),
        evaluator_artifact_sha256="f" * 64,
    )

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="manifest evaluator identity"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            evaluator,
            parameter_values,
        )


def test_evaluator_surface_mismatch_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    other_evaluator = _evaluator(targets=(parameter_values[0],))
    manifest = _bound_manifest(
        other_evaluator,
        surface,
        parameter_values,
    )

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="canonical validation"):
        run_temporal_canary_fixture_workflow(
            manifest,
            surface,
            other_evaluator,
            parameter_values,
        )


def test_mutated_receipt_candidate_identity_fails_closed_on_public_views() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )
    object.__setattr__(receipt, "candidate_sha256", "f" * 64)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="candidate identity"):
        receipt.semantic_dict()
    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="candidate identity"):
        _ = receipt.content_sha256


def test_valid_receipt_identity_mutation_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )
    object.__setattr__(receipt, "evaluation_sha256", "f" * 64)

    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="identity changed"):
        receipt.semantic_dict()
    with pytest.raises(TemporalCanaryFixtureWorkflowError, match="identity changed"):
        _ = receipt.content_sha256


def test_mutated_receipt_fails_closed_on_public_views() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    manifest = _bound_manifest(evaluator, surface, parameter_values)
    receipt = run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )
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
