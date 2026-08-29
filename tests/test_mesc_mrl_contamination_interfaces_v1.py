"""MRL-0602 tests for exact/near/semantic contamination interfaces."""

from __future__ import annotations

import pytest

from medscale.mesc._mrl_contamination_interfaces_v1 import (
    ContaminationCheckEvidence,
    ContaminationCheckKind,
    ContaminationDisposition,
    ContaminationEvidenceReport,
    ContaminationInterfaceError,
    build_contamination_evidence_report,
)
from medscale.mesc._mrl_training_example_lineage_v1 import build_training_example_lineage
from test_mesc_mrl_training_example_lineage_v1 import _example


def _checks(*, exact: ContaminationDisposition = ContaminationDisposition.CLEAR):
    return (
        ContaminationCheckEvidence(
            kind=ContaminationCheckKind.EXACT,
            detector_id="exact-detector",
            detector_artifact_sha256="1" * 64,
            evidence_artifact_sha256="2" * 64,
            disposition=exact,
        ),
        ContaminationCheckEvidence(
            kind=ContaminationCheckKind.NEAR,
            detector_id="near-detector",
            detector_artifact_sha256="3" * 64,
            evidence_artifact_sha256="4" * 64,
            disposition=ContaminationDisposition.CLEAR,
            similarity_decimal="0.2",
            threshold_decimal="0.8",
        ),
        ContaminationCheckEvidence(
            kind=ContaminationCheckKind.SEMANTIC,
            detector_id="semantic-detector",
            detector_artifact_sha256="5" * 64,
            evidence_artifact_sha256="6" * 64,
            disposition=ContaminationDisposition.CLEAR,
            similarity_decimal="0.3",
            threshold_decimal="0.9",
        ),
    )


def test_complete_clear_report_is_deterministic_and_non_authoritative() -> None:
    lineage = build_training_example_lineage(_example())

    first = build_contamination_evidence_report(lineage, _checks())
    second = build_contamination_evidence_report(lineage, _checks())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.training_lineage_sha256 == lineage.content_sha256
    assert first.disposition is ContaminationDisposition.CLEAR
    assert first.can_authorize_training is False
    assert first.can_authorize_model_promotion is False
    assert b"PROMOTED" not in first.semantic_bytes


def test_any_blocked_interface_blocks_the_complete_report() -> None:
    lineage = build_training_example_lineage(_example())
    report = build_contamination_evidence_report(
        lineage,
        _checks(exact=ContaminationDisposition.BLOCKED),
    )

    assert report.disposition is ContaminationDisposition.BLOCKED


def test_near_and_semantic_thresholds_are_fail_closed() -> None:
    with pytest.raises(ContaminationInterfaceError, match="does not match"):
        ContaminationCheckEvidence(
            kind=ContaminationCheckKind.NEAR,
            detector_id="near-detector",
            detector_artifact_sha256="3" * 64,
            evidence_artifact_sha256="4" * 64,
            disposition=ContaminationDisposition.CLEAR,
            similarity_decimal="0.9",
            threshold_decimal="0.8",
        )


def test_report_requires_all_three_interfaces_in_canonical_order() -> None:
    checks = _checks()
    with pytest.raises(ContaminationInterfaceError, match="exactly three"):
        ContaminationEvidenceReport(
            training_lineage_sha256="a" * 64,
            checks=checks[:2],
        )
    with pytest.raises(ContaminationInterfaceError, match="ordered EXACT, NEAR, SEMANTIC"):
        ContaminationEvidenceReport(
            training_lineage_sha256="a" * 64,
            checks=(checks[1], checks[0], checks[2]),
        )


def test_indeterminate_interface_preserves_uncertainty() -> None:
    checks = list(_checks())
    checks[2] = ContaminationCheckEvidence(
        kind=ContaminationCheckKind.SEMANTIC,
        detector_id="semantic-detector",
        detector_artifact_sha256="5" * 64,
        evidence_artifact_sha256="6" * 64,
        disposition=ContaminationDisposition.INDETERMINATE,
    )
    report = ContaminationEvidenceReport(
        training_lineage_sha256="a" * 64,
        checks=tuple(checks),
    )

    assert report.disposition is ContaminationDisposition.INDETERMINATE


def test_mutated_lineage_fails_closed() -> None:
    lineage = build_training_example_lineage(_example())
    object.__setattr__(lineage.example, "source_sha256", "not-a-sha")

    with pytest.raises(ContaminationInterfaceError, match="canonical revalidation"):
        build_contamination_evidence_report(lineage, _checks())
