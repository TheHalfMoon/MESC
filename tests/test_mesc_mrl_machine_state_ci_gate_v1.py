"""MRL-0705/0707 CI proofs for machine-state precedence and drift rejection."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    generate_machine_state,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TASKS_PATH = Path("specs/mesc-research-loop-v1/tasks.md")
_ROADMAP_PATH = Path("ROADMAP.md")


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


def _load_project_state(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _project_state_entry(payload: dict[str, object], state_id: str) -> dict[str, object]:
    entries = payload["entries"]
    assert isinstance(entries, list)
    match = next(
        entry for entry in entries if isinstance(entry, dict) and entry.get("state_id") == state_id
    )
    assert isinstance(match, dict)
    return match


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


def test_projection_precedence_rejects_narrative_and_projection_authority_claims(
    tmp_path: Path,
) -> None:
    repository = _clone_repository(tmp_path)
    roadmap = repository / _ROADMAP_PATH
    roadmap.write_text(
        roadmap.read_text(encoding="utf-8")
        + "\n<!-- MRL-0707 adversarial fixture: MRL-0800 CLOSED_CANONICAL -->\n",
        encoding="utf-8",
    )
    _run_git(repository, "add", _ROADMAP_PATH.as_posix())
    _run_git(
        repository,
        "commit",
        "--quiet",
        "-m",
        "test: add conflicting narrative status fixture",
    )

    output_dir = tmp_path / "machine-state"
    generate_machine_state(repository, output_dir)
    project_path = output_dir / "PROJECT_STATE.json"
    canonical_payload = _load_project_state(project_path)
    canonical_entry = _project_state_entry(canonical_payload, "MRL-0800")

    assert canonical_entry["lifecycle_state"] != "CLOSED_CANONICAL"
    assert canonical_payload["can_authorize"] is False

    forged_payload = _load_project_state(project_path)
    forged_entry = _project_state_entry(forged_payload, "MRL-0800")
    forged_entry["lifecycle_state"] = "CLOSED_CANONICAL"
    forged_entry["evidence_refs"] = ["narrative:ROADMAP.md:MRL-0800"]
    project_path.write_bytes(canonical_json_bytes(forged_payload))

    with pytest.raises(MachineStateGenerationError, match="projection drift detected"):
        generate_machine_state(repository, output_dir, check=True)

    regenerated = generate_machine_state(repository, output_dir)
    admitted_payload = json.loads(regenerated.project_state)
    assert isinstance(admitted_payload, dict)
    admitted_entry = _project_state_entry(admitted_payload, "MRL-0800")
    assert admitted_entry["lifecycle_state"] != "CLOSED_CANONICAL"
    assert admitted_payload["can_authorize"] is False
    generate_machine_state(repository, output_dir, check=True)
