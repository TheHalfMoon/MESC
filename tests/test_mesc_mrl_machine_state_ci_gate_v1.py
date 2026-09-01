"""MRL-0705/0707 CI proofs for machine-state precedence and admission."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    admit_project_state_projection,
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


def _project_state_task(
    payload: dict[str, object],
    task_id: str,
) -> dict[str, object]:
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    match = next(
        task for task in tasks if isinstance(task, dict) and task.get("task_id") == task_id
    )
    assert isinstance(match, dict)
    return match


def test_ci_gate_rejects_manually_edited_projection(tmp_path: Path) -> None:
    output_dir = tmp_path / "machine-state"
    generated = generate_machine_state(_REPOSITORY_ROOT, output_dir)
    project_state = output_dir / "PROJECT_STATE.json"
    project_state.write_bytes(project_state.read_bytes() + b" ")

    with pytest.raises(
        MachineStateGenerationError,
        match="projection drift detected",
    ):
        generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)
    with pytest.raises(
        MachineStateGenerationError,
        match="canonical JSON bytes",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            generated.project_state + b" ",
        )


def test_ci_gate_rejects_projection_after_canonical_source_commit_changes(
    tmp_path: Path,
) -> None:
    repository = _clone_repository(tmp_path)
    output_dir = tmp_path / "machine-state"
    generated = generate_machine_state(repository, output_dir)

    tasks = repository / _TASKS_PATH
    tasks.write_text(
        tasks.read_text(encoding="utf-8") + "\n<!-- MRL-0705 stale projection fixture -->\n",
        encoding="utf-8",
    )
    _run_git(repository, "add", _TASKS_PATH.as_posix())
    _run_git(
        repository,
        "commit",
        "--quiet",
        "-m",
        "test: advance canonical source fixture",
    )

    with pytest.raises(
        MachineStateGenerationError,
        match="projection drift detected",
    ):
        generate_machine_state(repository, output_dir, check=True)
    with pytest.raises(
        MachineStateGenerationError,
        match="stale for current Git HEAD",
    ):
        admit_project_state_projection(repository, generated.project_state)

    regenerated = generate_machine_state(repository, output_dir)
    assert regenerated.commit_sha != generated.commit_sha
    assert regenerated.project_state != generated.project_state
    admit_project_state_projection(repository, regenerated.project_state)
    generate_machine_state(repository, output_dir, check=True)


def test_merge_commit_cannot_invent_checked_qualified_parent(tmp_path: Path) -> None:
    repository = _clone_repository(tmp_path)
    _run_git(repository, "switch", "-c", "unchecked-side-parent")
    roadmap = repository / _ROADMAP_PATH
    roadmap.write_text(
        roadmap.read_text(encoding="utf-8")
        + "\n<!-- MRL qualifying-parent adversarial fixture -->\n",
        encoding="utf-8",
    )
    _run_git(repository, "add", _ROADMAP_PATH.as_posix())
    _run_git(repository, "commit", "--quiet", "-m", "test: create unchecked side parent")
    _run_git(repository, "switch", "-")
    _run_git(repository, "merge", "--no-ff", "--no-commit", "unchecked-side-parent")

    tasks = repository / _TASKS_PATH
    original = tasks.read_text(encoding="utf-8")
    unchecked = "- [ ] **MRL-0800 — Enter real autonomous research preflight**"
    checked = "- [x] **MRL-0800 — Enter real autonomous research preflight**"
    assert original.count(unchecked) == 1
    tasks.write_text(original.replace(unchecked, checked), encoding="utf-8")
    _run_git(repository, "add", _TASKS_PATH.as_posix())
    _run_git(repository, "commit", "--quiet", "-m", "test: forge checked state only in merge")

    output_dir = tmp_path / "machine-state-merge-parent"
    rendered = generate_machine_state(repository, output_dir)
    payload = admit_project_state_projection(repository, rendered.project_state)
    task = _project_state_task(payload, "MRL-0800")
    assert task["state"] != "CLOSED_CANONICAL"
    assert task["evidence_refs"] == []


def test_projection_precedence_rejects_narrative_and_projected_authority_claims(
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
        "test: add conflicting narrative fixture",
    )

    output_dir = tmp_path / "machine-state"
    rendered = generate_machine_state(repository, output_dir)
    project_path = output_dir / "PROJECT_STATE.json"
    canonical_payload = _load_project_state(project_path)
    canonical_task = _project_state_task(canonical_payload, "MRL-0800")

    assert canonical_task["state"] != "CLOSED_CANONICAL"
    assert canonical_payload["can_authorize"] is False
    admit_project_state_projection(repository, rendered.project_state)

    forged_payload = _load_project_state(project_path)
    forged_task = _project_state_task(forged_payload, "MRL-0800")
    forged_task["state"] = "CLOSED_CANONICAL"
    forged_task["evidence_refs"] = ["narrative:ROADMAP.md:MRL-0800"]
    forged_bytes = canonical_json_bytes(forged_payload)
    project_path.write_bytes(forged_bytes)

    with pytest.raises(
        MachineStateGenerationError,
        match="projection drift detected",
    ):
        generate_machine_state(repository, output_dir, check=True)
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(repository, forged_bytes)

    regenerated = generate_machine_state(repository, output_dir)
    admitted = admit_project_state_projection(repository, regenerated.project_state)
    admitted_task = _project_state_task(admitted, "MRL-0800")
    assert admitted_task["state"] != "CLOSED_CANONICAL"
    assert admitted["can_authorize"] is False
