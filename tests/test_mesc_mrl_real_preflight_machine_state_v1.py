"""Fail-closed machine-state binding tests for trusted MRL-8 real-preflight evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from medscale.mesc import _mrl_real_preflight_evidence_v1 as real_evidence
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_machine_state_generation_v1 import (
    _REAL_EVIDENCE_INDEX,
    MachineStateGenerationError,
    _parse_real_evidence_index,
    generate_machine_state,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_TASKS = Path("specs/mesc-research-loop-v1/tasks.md")
_SLOT = Path("specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0806.json")
_INDEX = Path(_REAL_EVIDENCE_INDEX)
_SHA_A = "a" * 64
_SHA_F = "f" * 64


def _run_git(repository: Path, *arguments: str) -> None:
    subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
    )


def _git_text(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


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
    _run_git(clone, "config", "user.name", "MRL Real Evidence Fixture")
    _run_git(clone, "config", "user.email", "mrl-real-evidence@example.invalid")
    _run_git(
        clone,
        "update-ref",
        "refs/remotes/origin/main",
        _git_text(clone, "rev-parse", "HEAD"),
    )
    return clone


def _objective_evidence() -> bytes:
    return canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": "mesc.mrl.real_preflight.objective_budgets.v1",
            "payload": {
                "adaptive_query_budget": 3,
                "compute_units": 1,
                "frozen_externally": True,
                "monetary_budget_microunits": 0,
                "research_objective_sha256": _SHA_A,
                "result_exposure_budget": 2,
                "storage_bytes": 1024,
                "token_budget": 4096,
                "wall_clock_seconds": 60,
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": _SHA_F,
            "task_id": "MRL-0806",
        }
    )


def _install_0806_candidate(repository: Path) -> str:
    raw = _objective_evidence()
    digest = hashlib.sha256(raw).hexdigest()
    (repository / _SLOT).write_bytes(raw)
    (repository / _INDEX).write_bytes(
        canonical_json_bytes(
            {
                "records": [
                    {
                        "evidence_path": _SLOT.as_posix(),
                        "evidence_sha256": digest,
                        "task_id": "MRL-0806",
                    }
                ],
                "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-INDEX-V1",
            }
        )
    )
    tasks = repository / _TASKS
    text = tasks.read_text(encoding="utf-8")
    unchecked = "- [ ] **MRL-0806 — Freeze real research objective and all budgets**"
    checked = "- [x] **MRL-0806 — Freeze real research objective and all budgets**"
    assert text.count(unchecked) == 1
    assert text.count(checked) == 0
    tasks.write_text(text.replace(unchecked, checked), encoding="utf-8")
    _run_git(repository, "add", _SLOT.as_posix(), _INDEX.as_posix(), _TASKS.as_posix())
    _run_git(repository, "commit", "--quiet", "-m", "test: admit synthetic MRL-0806 fixture")
    return digest


def _task(project_state: bytes, task_id: str) -> dict[str, object]:
    document = json.loads(project_state)
    assert isinstance(document, dict)
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    row = next(item for item in tasks if isinstance(item, dict) and item["task_id"] == task_id)
    assert isinstance(row, dict)
    return row


def test_empty_index_and_absent_slots_preserve_live_real_evidence_state(tmp_path: Path) -> None:
    rendered = generate_machine_state(_REPOSITORY_ROOT, tmp_path / "state")
    row = _task(rendered.project_state, "MRL-0806")
    assert row["state"] == "PLANNED"
    assert row["evidence_refs"] == []


def test_canonical_trusted_real_evidence_can_be_derived_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _clone_repository(tmp_path)
    digest = _install_0806_candidate(repository)
    head = _git_text(repository, "rev-parse", "HEAD")
    _run_git(repository, "update-ref", "refs/remotes/origin/main", head)
    monkeypatch.setattr(
        real_evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({digest}),
    )

    rendered = generate_machine_state(repository, tmp_path / "canonical")
    row = _task(rendered.project_state, "MRL-0806")
    assert row["state"] == "CLOSED_CANONICAL"
    assert row["evidence_refs"] == sorted(
        [
            f"canonical-main:{head}",
            f"real-preflight-evidence:{digest}",
            f"real-preflight-path:{_SLOT.as_posix()}",
        ]
    )


def test_branch_local_trusted_evidence_does_not_claim_canonical_closure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _clone_repository(tmp_path)
    canonical_main = _git_text(repository, "rev-parse", "refs/remotes/origin/main")
    digest = _install_0806_candidate(repository)
    assert _git_text(repository, "rev-parse", "HEAD") != canonical_main
    monkeypatch.setattr(
        real_evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({digest}),
    )

    rendered = generate_machine_state(repository, tmp_path / "branch")
    row = _task(rendered.project_state, "MRL-0806")
    assert row["state"] == "PLANNED"
    assert row["evidence_refs"] == []


def test_indexed_but_untrusted_real_evidence_fails_closed(tmp_path: Path) -> None:
    repository = _clone_repository(tmp_path)
    _install_0806_candidate(repository)

    with pytest.raises(MachineStateGenerationError, match="admission failed"):
        generate_machine_state(repository, tmp_path / "untrusted")


def test_non_absent_unindexed_slot_fails_closed(tmp_path: Path) -> None:
    repository = _clone_repository(tmp_path)
    (repository / _SLOT).write_bytes(_objective_evidence())
    _run_git(repository, "add", _SLOT.as_posix())
    _run_git(repository, "commit", "--quiet", "-m", "test: unindexed real-evidence slot")

    with pytest.raises(MachineStateGenerationError, match="absent from the admission index"):
        generate_machine_state(repository, tmp_path / "unindexed")


def test_real_evidence_index_rejects_duplicate_task_records() -> None:
    digest = "1" * 64
    record = {
        "evidence_path": _SLOT.as_posix(),
        "evidence_sha256": digest,
        "task_id": "MRL-0806",
    }
    raw = canonical_json_bytes(
        {
            "records": [record, record],
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-INDEX-V1",
        }
    )
    with pytest.raises(MachineStateGenerationError, match="task-sorted and task-unique"):
        _parse_real_evidence_index(raw)


def test_real_evidence_index_rejects_noncanonical_bytes() -> None:
    raw = b'{"schema_version":"MRL-REAL-PREFLIGHT-EVIDENCE-INDEX-V1","records":[]} \n'
    with pytest.raises(MachineStateGenerationError, match="exact canonical JSON bytes"):
        _parse_real_evidence_index(raw)
