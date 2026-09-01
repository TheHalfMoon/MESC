"""MRL-0704 tests for deterministic machine-state generation and admission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from medscale.mesc._mrl_machine_state_generation_v1 import (
    _REAL_EVIDENCE,
    MachineStateGenerationError,
    admit_project_state_projection,
    generate_machine_state,
    load_canonical_snapshot,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_FILES = (
    "CAPABILITY_MATRIX.json",
    "PROJECT_STATE.json",
    "RESEARCH_PROGRAM_INDEX.json",
)
_REQUIRED_PROJECT_SOURCES = {
    "docs/adr/0035-mrl-governance-constitution.md",
    "specs/mesc-research-loop-v1/README.md",
    "specs/mesc-research-loop-v1/closeout-evidence-v1.json",
    "specs/mesc-research-loop-v1/plan.md",
    "specs/mesc-research-loop-v1/project-state-contract.md",
    "specs/mesc-research-loop-v1/project-state-v1.schema.json",
    "specs/mesc-research-loop-v1/spec.md",
    "specs/mesc-research-loop-v1/tasks.md",
    "specs/mesc-training-readiness-v1/README.md",
    "src/medscale/mesc/_training_authorization_trust_v1.py",
    "src/medscale/mesc/_training_runtime_qualification_v1.py",
}


def _payload(path: Path) -> dict[str, object]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def test_generation_is_deterministic_and_binds_exact_git_head(
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = generate_machine_state(_REPOSITORY_ROOT, first_dir)
    second = generate_machine_state(_REPOSITORY_ROOT, second_dir)

    assert first.commit_sha == second.commit_sha
    assert first.tree_sha == second.tree_sha
    assert first.files() == second.files()
    assert tuple(path.name for path in sorted(first_dir.iterdir())) == _EXPECTED_FILES

    for filename in _EXPECTED_FILES:
        assert (first_dir / filename).read_bytes() == (second_dir / filename).read_bytes()
        payload = _payload(first_dir / filename)
        repository = payload["repository"]
        assert isinstance(repository, dict)
        assert repository["commit_sha"] == first.commit_sha
        assert repository["tree_sha"] == first.tree_sha
        assert payload["can_authorize"] is False
        assert payload["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"

    admitted = admit_project_state_projection(
        _REPOSITORY_ROOT,
        first.project_state,
    )
    assert admitted["repository"] == {
        "commit_sha": first.commit_sha,
        "tree_sha": first.tree_sha,
    }


def test_source_bindings_match_exact_head_blob_and_content_hashes(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "state"
    generate_machine_state(_REPOSITORY_ROOT, output_dir)
    snapshot = load_canonical_snapshot(_REPOSITORY_ROOT)

    projected_sources: dict[str, tuple[str, str]] = {}
    for filename in _EXPECTED_FILES:
        payload = _payload(output_dir / filename)
        sources = payload["sources"]
        assert isinstance(sources, list)
        for source in sources:
            assert isinstance(source, dict)
            path = source["path"]
            git_blob_sha = source["git_blob_sha"]
            sha256 = source["sha256"]
            assert isinstance(path, str)
            assert isinstance(git_blob_sha, str)
            assert isinstance(sha256, str)
            projected_sources[path] = (git_blob_sha, sha256)

    for source in snapshot.sources:
        if source.path not in projected_sources:
            continue
        assert projected_sources[source.path] == (
            source.git_blob_sha,
            source.sha256,
        )
        repository_bytes = (_REPOSITORY_ROOT / source.path).read_bytes()
        assert hashlib.sha256(repository_bytes).hexdigest() == source.sha256


def test_research_program_and_capability_semantics_come_from_canonical_sources(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "state"
    generate_machine_state(_REPOSITORY_ROOT, output_dir)

    research = _payload(output_dir / "RESEARCH_PROGRAM_INDEX.json")
    questions = research["questions"]
    namespaces = research["namespaces"]
    assert isinstance(questions, list)
    assert isinstance(namespaces, list)
    assert [item["question_id"] for item in questions] == [f"RQ{i}" for i in range(1, 8)]
    assert {item["question_namespace"] for item in namespaces} == {
        "AMGE-RQ-<NNNN>",
        "ARABIC-RQ-<NNNN>",
        "MCRL-RQ-<NNNN>",
        "MESC-RQ-<NNNN>",
        "MRL-RQ-<NNNN>",
        "OMNI-RQ-<NNNN>",
    }

    capability = _payload(output_dir / "CAPABILITY_MATRIX.json")
    rows = capability["capabilities"]
    assert isinstance(rows, list)
    indexed = {row["capability_id"]: row for row in rows}
    assert indexed["PILOT_01_B0_BASELINE"]["evidence_state"] == "PROVEN"
    assert indexed["T0_REPOSITORY_FOUNDATION"]["implementation_state"] == "IMPLEMENTED"
    assert indexed["TRAINING_EXECUTION"]["authority_state"] == "NOT_AUTHORIZED"


def test_external_real_evidence_hold_excludes_dependency_only_gates() -> None:
    assert (
        frozenset(
            {
                "MRL-0801",
                "MRL-0802",
                "MRL-0803",
                "MRL-0804",
                "MRL-0805",
                "MRL-0806",
                "MRL-0807",
                "MRL-0808",
            }
        )
        == _REAL_EVIDENCE
    )
    assert "MRL-0809" not in _REAL_EVIDENCE
    assert "MRL-0899" not in _REAL_EVIDENCE


def test_project_state_matches_frozen_schema_without_freezing_live_gate_states(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "state"
    rendered = generate_machine_state(_REPOSITORY_ROOT, output_dir)
    project = _payload(output_dir / "PROJECT_STATE.json")
    assert set(project) == {
        "can_authorize",
        "projection_kind",
        "repository",
        "schema_version",
        "source_set_sha256",
        "sources",
        "tasks",
    }
    sources = project["sources"]
    assert isinstance(sources, list)
    assert {source["path"] for source in sources} == _REQUIRED_PROJECT_SOURCES
    tasks = project["tasks"]
    assert isinstance(tasks, list)
    indexed = {task["task_id"]: task for task in tasks}

    for task_id in ("MRL-0299", "MRL-0399", "MRL-0799", "MRL-0800"):
        assert task_id in indexed
    for task_id in _REAL_EVIDENCE:
        assert indexed[task_id]["state"] == "PLANNED"
        assert indexed[task_id]["evidence_refs"] == []
    assert project["can_authorize"] is False
    admit_project_state_projection(_REPOSITORY_ROOT, rendered.project_state)


def test_check_accepts_exact_bytes_and_rejects_manual_edit(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "state"
    generate_machine_state(_REPOSITORY_ROOT, output_dir)

    verified = generate_machine_state(
        _REPOSITORY_ROOT,
        output_dir,
        check=True,
    )
    assert verified.commit_sha

    capability_path = output_dir / "CAPABILITY_MATRIX.json"
    capability_path.write_bytes(capability_path.read_bytes() + b" ")
    with pytest.raises(
        MachineStateGenerationError,
        match="projection drift detected",
    ):
        generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)


def test_check_rejects_missing_or_unexpected_json_output(tmp_path: Path) -> None:
    output_dir = tmp_path / "state"
    generate_machine_state(_REPOSITORY_ROOT, output_dir)
    (output_dir / "PROJECT_STATE.json").unlink()

    with pytest.raises(
        MachineStateGenerationError,
        match="missing or unreadable",
    ):
        generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)

    generate_machine_state(_REPOSITORY_ROOT, output_dir)
    (output_dir / "MANUAL.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        MachineStateGenerationError,
        match="unexpected machine-state JSON",
    ):
        generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)
