"""MRL-0705 CI proofs for stale and manually edited machine-state projections."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    generate_machine_state,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TASKS_PATH = Path("specs/mesc-research-loop-v1/tasks.md")


def _run_git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
    )


def _clone_repository(tmp_path: Path) -> Path:
    clone = tmp_path / "repository"
    subprocess.run(
        (
            "git",
            "clone",
            "--quiet",
            "--no-hardlinks",
            str(_REPOSITORY_ROOT),
            str(clone),
        ),
        check=True,
        capture_output=True,
    )
    _run_git(clone, "config", "user.name", "MRL CI Fixture")
    _run_git(clone, "config", "user.email", "mrl-ci-fixture@example.invalid")
    return clone


def test_ci_gate_rejects_manually_edited_projection(tmp_path: Path) -> None:
    output_dir = tmp_path / "machine-state"
    generate_machine_state(_REPOSITORY_ROOT, output_dir)

    project_state = output_dir / "PROJECT_STATE.json"
    project_state.write_bytes(project_state.read_bytes() + b" ")

    with pytest.raises(MachineStateGenerationError, match="projection drift detected"):
        generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)


def test_ci_gate_rejects_projection_after_canonical_source_commit_changes(tmp_path: Path) -> None:
    repository = _clone_repository(tmp_path)
    output_dir = tmp_path / "machine-state"
    generated = generate_machine_state(repository, output_dir)

    tasks = repository / _TASKS_PATH
    tasks.write_text(
        tasks.read_text(encoding="utf-8") + "\n<!-- MRL-0705 stale projection fixture -->\n",
        encoding="utf-8",
    )
    _run_git(repository, "add", _TASKS_PATH.as_posix())
    _run_git(repository, "commit", "--quiet", "-m", "test: advance canonical source fixture")

    with pytest.raises(MachineStateGenerationError, match="projection drift detected"):
        generate_machine_state(repository, output_dir, check=True)

    regenerated = generate_machine_state(repository, output_dir)
    assert regenerated.commit_sha != generated.commit_sha
    assert regenerated.project_state != generated.project_state
    generate_machine_state(repository, output_dir, check=True)
