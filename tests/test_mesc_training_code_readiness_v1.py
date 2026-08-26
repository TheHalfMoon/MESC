"""Tests for the final MESC training-code readiness audit."""

from __future__ import annotations

import shutil
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


def test_audit_blocks_when_module_sources_missing(tmp_path: Path) -> None:
    empty = tmp_path / "repo"
    empty.mkdir()
    (empty / "pyproject.toml").write_text(
        "[project]\nname='x'\nversion='0'\ndependencies=[]\n"
        "[project.optional-dependencies]\n"
        "training-hf-sft=[\n"
        "  'accelerate==1.14.0',\n"
        "  'bitsandbytes==0.50.1',\n"
        "  'datasets==5.0.1',\n"
        "  'peft==0.20.0',\n"
        "  'torch==2.13.0',\n"
        "  'transformers==5.15.1',\n"
        "  'trl==1.10.0',\n"
        "]\n",
        encoding="utf-8",
    )
    (empty / "uv.lock").write_text("placeholder\n", encoding="utf-8")
    report = audit_training_code_readiness(repository_root=empty)
    assert report.disposition == "BLOCKED"
    assert report.missing_modules
    assert report.missing_specs
    assert "missing module: medscale.mesc._training_orchestrator_v1" in report.blockers
    assert report.medscale_spec_012_admission_readiness == "NOT_READY"
    assert report.real_training_authorized is False


def test_audit_blocks_when_authorization_trust_module_missing(tmp_path: Path) -> None:
    live = audit_training_code_readiness(repository_root=_REPOSITORY_ROOT)
    assert live.disposition == "TRAINING_CODE_READY"

    root = tmp_path / "repo"
    root.mkdir()
    for module_name in live.present_modules:
        relative = Path("src", *module_name.split(".")).with_suffix(".py")
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPOSITORY_ROOT / relative, target)
    for relative_text in live.present_specs:
        relative = Path(relative_text)
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_REPOSITORY_ROOT / relative, target)
    shutil.copy2(_REPOSITORY_ROOT / "pyproject.toml", root / "pyproject.toml")
    shutil.copy2(_REPOSITORY_ROOT / "uv.lock", root / "uv.lock")

    trust_relative = Path("src/medscale/mesc/_training_authorization_trust_v1.py")
    (root / trust_relative).unlink()

    report = audit_training_code_readiness(repository_root=root)
    assert report.disposition == "BLOCKED"
    assert report.missing_modules == ("medscale.mesc._training_authorization_trust_v1",)
    assert "missing module: medscale.mesc._training_authorization_trust_v1" in report.blockers
    assert report.real_training_authorized is False


def test_audit_blocks_invalid_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text("not = [toml\n", encoding="utf-8")
    (root / "uv.lock").write_text("placeholder\n", encoding="utf-8")
    report = audit_training_code_readiness(repository_root=root)
    assert report.disposition == "BLOCKED"
    assert any("pyproject.toml is invalid" in item for item in report.blockers)


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
