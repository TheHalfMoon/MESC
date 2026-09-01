"""Negative fixtures for the canonical MRL project-state admission validator."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_sha256
from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    admit_project_state_projection,
    generate_machine_state,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _valid_payload(tmp_path: Path) -> tuple[bytes, dict[str, object]]:
    rendered = generate_machine_state(_REPOSITORY_ROOT, tmp_path / "state")
    loaded = json.loads(rendered.project_state)
    assert isinstance(loaded, dict)
    return rendered.project_state, loaded


def _task(document: dict[str, object], task_id: str) -> dict[str, object]:
    tasks = document["tasks"]
    assert isinstance(tasks, list)
    found = next(
        task
        for task in tasks
        if isinstance(task, dict) and task.get("task_id") == task_id
    )
    assert isinstance(found, dict)
    return found


def _canonical(document: dict[str, object]) -> bytes:
    return canonical_json_bytes(document)


def test_admission_accepts_exact_generated_bytes(tmp_path: Path) -> None:
    payload, _ = _valid_payload(tmp_path)
    admitted = admit_project_state_projection(_REPOSITORY_ROOT, payload)
    assert admitted["can_authorize"] is False


def test_duplicate_json_members_are_rejected_before_semantic_use(
    tmp_path: Path,
) -> None:
    payload, _ = _valid_payload(tmp_path)
    forged = payload.replace(
        b'"can_authorize":false',
        b'"can_authorize":false,"can_authorize":false',
        1,
    )
    with pytest.raises(
        MachineStateGenerationError,
        match="duplicate JSON member",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, forged)


def test_duplicate_source_and_task_identities_are_rejected(tmp_path: Path) -> None:
    _, document = _valid_payload(tmp_path)
    source_forgery = copy.deepcopy(document)
    sources = source_forgery["sources"]
    assert isinstance(sources, list)
    duplicate_source = copy.deepcopy(sources[0])
    assert isinstance(duplicate_source, dict)
    duplicate_source["sha256"] = "f" * 64
    sources.insert(1, duplicate_source)
    source_forgery["source_set_sha256"] = canonical_sha256(sources)
    with pytest.raises(
        MachineStateGenerationError,
        match="source path is duplicated",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(source_forgery),
        )

    task_forgery = copy.deepcopy(document)
    tasks = task_forgery["tasks"]
    assert isinstance(tasks, list)
    duplicate_task = copy.deepcopy(tasks[0])
    assert isinstance(duplicate_task, dict)
    duplicate_task["state"] = "BLOCKED"
    duplicate_task["evidence_refs"] = []
    tasks.insert(1, duplicate_task)
    with pytest.raises(
        MachineStateGenerationError,
        match="task_id is invalid or duplicated",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(task_forgery),
        )


def test_duplicate_dependencies_and_evidence_refs_are_rejected(
    tmp_path: Path,
) -> None:
    _, document = _valid_payload(tmp_path)
    dependency_forgery = copy.deepcopy(document)
    gate = _task(dependency_forgery, "MRL-0299")
    dependencies = gate["dependencies"]
    assert isinstance(dependencies, list) and dependencies
    dependencies.append(dependencies[-1])
    with pytest.raises(
        MachineStateGenerationError,
        match="dependencies must be sorted and unique",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(dependency_forgery),
        )

    evidence_forgery = copy.deepcopy(document)
    closed = _task(evidence_forgery, "MRL-0299")
    evidence_refs = closed["evidence_refs"]
    assert isinstance(evidence_refs, list) and evidence_refs
    evidence_refs.append(evidence_refs[-1])
    with pytest.raises(
        MachineStateGenerationError,
        match="evidence_refs must be sorted and unique",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(evidence_forgery),
        )


@pytest.mark.parametrize(
    "forged_path",
    [
        "/absolute.md",
        "docs//double.md",
        "docs/./dot.md",
        "docs/../parent.md",
        "docs\\back.md",
    ],
)
def test_ambiguous_source_paths_are_rejected(
    tmp_path: Path,
    forged_path: str,
) -> None:
    _, document = _valid_payload(tmp_path)
    forged = copy.deepcopy(document)
    sources = forged["sources"]
    assert isinstance(sources, list)
    first = sources[0]
    assert isinstance(first, dict)
    first["path"] = forged_path
    sources.sort(key=lambda item: item["path"])
    forged["source_set_sha256"] = canonical_sha256(sources)
    with pytest.raises(MachineStateGenerationError, match="source path"):
        admit_project_state_projection(_REPOSITORY_ROOT, _canonical(forged))


def test_stale_repository_source_and_required_source_omission_fail_closed(
    tmp_path: Path,
) -> None:
    _, document = _valid_payload(tmp_path)
    stale = copy.deepcopy(document)
    repository = stale["repository"]
    assert isinstance(repository, dict)
    repository["commit_sha"] = "0" * 40
    with pytest.raises(
        MachineStateGenerationError,
        match="stale for current Git HEAD",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, _canonical(stale))

    source_tamper = copy.deepcopy(document)
    sources = source_tamper["sources"]
    assert isinstance(sources, list)
    first = sources[0]
    assert isinstance(first, dict)
    first["sha256"] = "0" * 64 if first["sha256"] != "0" * 64 else "1" * 64
    source_tamper["source_set_sha256"] = canonical_sha256(sources)
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(source_tamper),
        )

    omitted = copy.deepcopy(document)
    omitted_sources = omitted["sources"]
    assert isinstance(omitted_sources, list)
    omitted_sources.pop(0)
    omitted["source_set_sha256"] = canonical_sha256(omitted_sources)
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, _canonical(omitted))


def test_manual_task_state_dependency_and_evidence_edits_are_rejected(
    tmp_path: Path,
) -> None:
    _, document = _valid_payload(tmp_path)
    state_forgery = copy.deepcopy(document)
    target = _task(state_forgery, "MRL-0800")
    target["state"] = "CLOSED_CANONICAL"
    target["evidence_refs"] = ["fabricated:authority"]
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(state_forgery),
        )

    dependency_forgery = copy.deepcopy(document)
    target = _task(dependency_forgery, "MRL-0800")
    dependencies = target["dependencies"]
    assert isinstance(dependencies, list)
    dependencies.pop()
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(dependency_forgery),
        )

    evidence_forgery = copy.deepcopy(document)
    target = _task(evidence_forgery, "MRL-0299")
    evidence = target["evidence_refs"]
    assert isinstance(evidence, list)
    evidence[0] = "canonical-merge:" + "0" * 40
    evidence.sort()
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(
            _REPOSITORY_ROOT,
            _canonical(evidence_forgery),
        )


def test_indeterminate_real_evidence_task_cannot_supply_its_own_answer(
    tmp_path: Path,
) -> None:
    _, document = _valid_payload(tmp_path)
    forged = copy.deepcopy(document)
    target = _task(forged, "MRL-0801")
    target["state"] = "ELIGIBLE"
    with pytest.raises(
        MachineStateGenerationError,
        match="independent canonical recomputation",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, _canonical(forged))


def test_authority_bearing_and_noncanonical_variants_are_rejected(
    tmp_path: Path,
) -> None:
    payload, document = _valid_payload(tmp_path)
    authority = copy.deepcopy(document)
    authority["can_authorize"] = True
    with pytest.raises(
        MachineStateGenerationError,
        match="authority/schema constants",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, _canonical(authority))

    with pytest.raises(
        MachineStateGenerationError,
        match="canonical JSON bytes",
    ):
        admit_project_state_projection(_REPOSITORY_ROOT, payload + b" ")
