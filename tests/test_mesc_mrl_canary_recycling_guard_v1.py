"""MRL-0607 tests for temporal-canary training/search recycling enforcement."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_canary_recycling_guard_v1 import (
    CanaryArtifactUse,
    CanaryRecyclingDisposition,
    CanaryRecyclingError,
    CanaryRecyclingTarget,
    build_canary_recycling_guard_report,
    require_no_canary_recycling,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import build_fixture_candidate
from medscale.mesc._mrl_temporal_canary_fixture_workflow_v1 import (
    TemporalCanaryFixtureReceipt,
    run_temporal_canary_fixture_workflow,
)
from test_mesc_mrl_fixture_research_surface_v1 import _evaluator, _surface, _values
from test_mesc_mrl_temporal_canary_manifest_v1 import _manifest


def _receipt() -> TemporalCanaryFixtureReceipt:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    parameter_values = _values()
    candidate = build_fixture_candidate(surface, parameter_values)
    manifest = replace(
        _manifest(artifact=candidate.content_sha256),
        evaluator_artifact_sha256=evaluator.content_sha256,
    )
    return run_temporal_canary_fixture_workflow(
        manifest,
        surface,
        evaluator,
        parameter_values,
    )


def test_clear_guard_is_deterministic_but_never_authoritative() -> None:
    receipt = _receipt()
    attempted = (
        CanaryArtifactUse(
            target=CanaryRecyclingTarget.SEARCH,
            artifact_sha256="1" * 64,
        ),
        CanaryArtifactUse(
            target=CanaryRecyclingTarget.TRAINING,
            artifact_sha256="2" * 64,
        ),
    )

    first = build_canary_recycling_guard_report(receipt, attempted)
    second = build_canary_recycling_guard_report(receipt, attempted)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.disposition is CanaryRecyclingDisposition.CLEAR
    assert first.blocked_uses == ()
    assert first.can_authorize_training is False
    assert first.can_authorize_search is False
    assert first.can_authorize is False
    assert require_no_canary_recycling(receipt, attempted).content_sha256 == first.content_sha256


def test_canary_artifact_cannot_enter_training() -> None:
    receipt = _receipt()
    attempted = (
        CanaryArtifactUse(
            target=CanaryRecyclingTarget.TRAINING,
            artifact_sha256=receipt.canary_artifact_sha256,
        ),
    )

    report = build_canary_recycling_guard_report(receipt, attempted)

    assert report.disposition is CanaryRecyclingDisposition.BLOCKED
    assert report.blocked_uses[0].target is CanaryRecyclingTarget.TRAINING
    with pytest.raises(CanaryRecyclingError, match="recycling into training/search is prohibited"):
        require_no_canary_recycling(receipt, attempted)


def test_canary_artifact_cannot_enter_search() -> None:
    receipt = _receipt()
    attempted = (
        CanaryArtifactUse(
            target=CanaryRecyclingTarget.SEARCH,
            artifact_sha256=receipt.canary_artifact_sha256,
        ),
    )

    report = build_canary_recycling_guard_report(receipt, attempted)

    assert report.disposition is CanaryRecyclingDisposition.BLOCKED
    assert report.blocked_uses[0].target is CanaryRecyclingTarget.SEARCH


def test_complete_sealed_canary_chain_is_protected_from_recycling() -> None:
    receipt = _receipt()
    protected = (
        receipt.content_sha256,
        receipt.manifest_sha256,
        receipt.canary_artifact_sha256,
        receipt.evaluation_sha256,
    )

    for artifact_sha256 in protected:
        report = build_canary_recycling_guard_report(
            receipt,
            (
                CanaryArtifactUse(
                    target=CanaryRecyclingTarget.SEARCH,
                    artifact_sha256=artifact_sha256,
                ),
            ),
        )
        assert report.disposition is CanaryRecyclingDisposition.BLOCKED


def test_mutated_receipt_fails_closed_before_recycling_comparison() -> None:
    receipt = _receipt()
    object.__setattr__(receipt, "evaluation_sha256", "invalid")

    with pytest.raises(CanaryRecyclingError, match="receipt failed canonical revalidation"):
        build_canary_recycling_guard_report(receipt, ())


def test_valid_receipt_identity_drift_fails_closed() -> None:
    receipt = _receipt()
    object.__setattr__(receipt, "evaluation_sha256", "f" * 64)

    with pytest.raises(CanaryRecyclingError, match="receipt failed canonical revalidation"):
        build_canary_recycling_guard_report(receipt, ())


def test_mutated_attempted_use_cannot_change_report_semantics() -> None:
    receipt = _receipt()
    use = CanaryArtifactUse(
        target=CanaryRecyclingTarget.SEARCH,
        artifact_sha256="1" * 64,
    )
    report = build_canary_recycling_guard_report(receipt, (use,))
    object.__setattr__(report.attempted_uses[0], "artifact_sha256", receipt.canary_artifact_sha256)

    with pytest.raises(CanaryRecyclingError, match="identity changed"):
        _ = report.disposition
    with pytest.raises(CanaryRecyclingError, match="identity changed"):
        _ = report.content_sha256


def test_mutated_report_identity_fails_closed() -> None:
    receipt = _receipt()
    report = build_canary_recycling_guard_report(receipt, ())
    object.__setattr__(report, "canary_receipt_sha256", "f" * 64)

    with pytest.raises(CanaryRecyclingError, match="report identity changed after construction"):
        _ = report.content_sha256


def test_valid_attempted_use_drift_fails_closed_before_new_report() -> None:
    receipt = _receipt()
    use = CanaryArtifactUse(
        target=CanaryRecyclingTarget.TRAINING,
        artifact_sha256="1" * 64,
    )
    object.__setattr__(use, "artifact_sha256", "f" * 64)

    with pytest.raises(CanaryRecyclingError, match="identity changed"):
        build_canary_recycling_guard_report(receipt, (use,))


def test_attempted_use_set_must_be_sorted_and_unique() -> None:
    receipt = _receipt()
    search = CanaryArtifactUse(
        target=CanaryRecyclingTarget.SEARCH,
        artifact_sha256="2" * 64,
    )
    training = CanaryArtifactUse(
        target=CanaryRecyclingTarget.TRAINING,
        artifact_sha256="1" * 64,
    )

    with pytest.raises(CanaryRecyclingError, match="unique and sorted"):
        build_canary_recycling_guard_report(receipt, (training, search))
    with pytest.raises(CanaryRecyclingError, match="unique and sorted"):
        build_canary_recycling_guard_report(receipt, (search, search))


def test_wrong_receipt_and_use_types_fail_closed() -> None:
    receipt = _receipt()

    with pytest.raises(CanaryRecyclingError, match="exact TemporalCanaryFixtureReceipt"):
        build_canary_recycling_guard_report(object(), ())  # type: ignore[arg-type]
    with pytest.raises(CanaryRecyclingError, match="invalid item type"):
        build_canary_recycling_guard_report(receipt, (object(),))  # type: ignore[arg-type]
