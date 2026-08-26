"""Tests for the final MESC training-code readiness audit."""

from __future__ import annotations

from pathlib import Path

import pytest

from medscale.mesc._training_code_readiness_v1 import (
    TrainingCodeReadinessError,
    audit_training_code_readiness,
)
from medscale.mesc._training_orchestrator_v1 import hash_dependency_lock

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_live_repository_is_training_code_ready() -> None:
    report = audit_training_code_readiness(repository_root=_REPOSITORY_ROOT)
    assert report.disposition == "TRAINING_CODE_READY"
    assert report.blockers == ()
    assert report.missing_modules == ()
    assert report.missing_specs == ()
    assert report.real_training_authorized is False
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert report.dependency_lock_sha256 == hash_dependency_lock(_REPOSITORY_ROOT / "uv.lock")
    assert report.audit_sha256


def test_audit_blocks_when_spec_missing(tmp_path: Path) -> None:
    # Copy only a subset of required paths by pointing at an empty tree.
    empty = tmp_path / "repo"
    empty.mkdir()
    (empty / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0'\ndependencies=[]\n"
        "[project.optional-dependencies]\n"
        "training-hf-sft=['accelerate==1.14.0']\n",
        encoding="utf-8",
    )
    (empty / "uv.lock").write_text("placeholder\n", encoding="utf-8")
    report = audit_training_code_readiness(repository_root=empty)
    assert report.disposition == "BLOCKED"
    assert report.missing_specs
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert report.real_training_authorized is False


def test_report_forbids_claiming_real_training_authorization() -> None:
    report = audit_training_code_readiness(repository_root=_REPOSITORY_ROOT)
    with pytest.raises(TrainingCodeReadinessError, match="authorize real training"):
        type(report)(
            disposition="TRAINING_CODE_READY",
            repository_root=report.repository_root,
            dependency_lock_sha256=report.dependency_lock_sha256,
            training_extra_pins=report.training_extra_pins,
            present_modules=report.present_modules,
            missing_modules=(),
            present_specs=report.present_specs,
            missing_specs=(),
            blockers=(),
            real_training_authorized=True,
            medscale_spec_012_admission_readiness="NOT_READY",
        )
