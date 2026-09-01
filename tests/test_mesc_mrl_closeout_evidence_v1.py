"""Adversarial regressions for MRL canonical closeout-evidence admission."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from medscale.mesc import _mrl_machine_state_generation_v1 as generation

_MERGE = "a" * 40
_HEAD = "b" * 40
_TASK = "MRL-0201"


def _record(
    *,
    merge_sha: str = _MERGE,
    head_sha: str = _HEAD,
    task_ids: tuple[str, ...] = (_TASK,),
) -> generation._CloseoutEvidence:
    return generation._CloseoutEvidence(
        canonical_merge_sha=merge_sha,
        qualified_head_sha=head_sha,
        pr_number=1,
        evidence_profile="MRL_REPOSITORY_EXACT_HEAD_V1",
        successful_ci_run_ids=(1,),
        successful_codeql_run_ids=(2,),
        independent_exact_head_evidence_refs=(),
        qodo_exact_head_comment_ids=(),
        owner_exact_head_review_ids=(),
        coderabbit_success_status_ids=(),
        task_ids=task_ids,
    )


def _shape(
    _root: Path,
    _decision_base: str,
    _canonical_main_sha: str,
    _task_id: str,
) -> tuple[str, str]:
    return (_MERGE, _HEAD)


def _no_shape(
    _root: Path,
    _decision_base: str,
    _canonical_main_sha: str,
    _task_id: str,
) -> None:
    return None


def test_merge_shape_without_admitted_evidence_cannot_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(generation, "_merge_shape_closure", _shape)
    monkeypatch.setattr(
        generation,
        "_evidence_by_task",
        lambda _root, _decision_base: {},
    )

    assert generation._closure_proof(tmp_path, _HEAD, _HEAD, _TASK) is None


@pytest.mark.parametrize(
    ("merge_sha", "head_sha"),
    [
        ("c" * 40, _HEAD),
        (_MERGE, "d" * 40),
    ],
)
def test_wrong_merge_or_qualified_head_cannot_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    merge_sha: str,
    head_sha: str,
) -> None:
    monkeypatch.setattr(generation, "_merge_shape_closure", _shape)

    def evidence(
        _root: Path,
        _decision_base: str,
    ) -> dict[str, generation._CloseoutEvidence]:
        return {_TASK: _record(merge_sha=merge_sha, head_sha=head_sha)}

    monkeypatch.setattr(generation, "_evidence_by_task", evidence)
    assert generation._closure_proof(tmp_path, _HEAD, _HEAD, _TASK) is None


def test_exact_transition_and_evidence_binding_can_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(generation, "_merge_shape_closure", _shape)

    def evidence(
        _root: Path,
        _decision_base: str,
    ) -> dict[str, generation._CloseoutEvidence]:
        return {_TASK: _record()}

    monkeypatch.setattr(generation, "_evidence_by_task", evidence)
    assert generation._closure_proof(tmp_path, _HEAD, _HEAD, _TASK) == (
        _MERGE,
        _HEAD,
    )


def test_branch_local_or_noncanonical_merge_cannot_close(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(generation, "_merge_shape_closure", _no_shape)

    def evidence(
        _root: Path,
        _decision_base: str,
    ) -> dict[str, generation._CloseoutEvidence]:
        return {_TASK: _record()}

    monkeypatch.setattr(generation, "_evidence_by_task", evidence)
    assert generation._closure_proof(tmp_path, _HEAD, _HEAD, _TASK) is None


@pytest.mark.parametrize(
    "task_id",
    (
        "MRL-0801",
        "MRL-0802",
        "MRL-0803",
        "MRL-0804",
        "MRL-0805",
        "MRL-0806",
        "MRL-0807",
        "MRL-0808",
    ),
)
def test_real_evidence_tasks_cannot_close_from_repository_only_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    task_id: str,
) -> None:
    monkeypatch.setattr(generation, "_merge_shape_closure", _shape)

    def evidence(
        _root: Path,
        _decision_base: str,
    ) -> dict[str, generation._CloseoutEvidence]:
        return {task_id: _record(task_ids=(task_id,))}

    monkeypatch.setattr(generation, "_evidence_by_task", evidence)
    assert generation._closure_proof(tmp_path, _HEAD, _HEAD, task_id) is None


def _manifest_record(task_id: str = _TASK) -> dict[str, object]:
    return {
        "canonical_merge_sha": _MERGE,
        "coderabbit_success_status_ids": [],
        "evidence_profile": "MRL_REPOSITORY_EXACT_HEAD_V1",
        "independent_exact_head_evidence_refs": [],
        "owner_exact_head_review_ids": [],
        "pr_number": 1,
        "qodo_exact_head_comment_ids": [],
        "qualified_head_sha": _HEAD,
        "successful_ci_run_ids": [1],
        "successful_codeql_run_ids": [2],
        "task_ids": [task_id],
    }


def test_duplicate_task_evidence_fails_closed() -> None:
    record = _manifest_record()
    payload = json.dumps(
        {
            "records": [record, record],
            "schema_version": "MRL-CLOSEOUT-EVIDENCE-V1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(
        generation.MachineStateGenerationError,
        match="duplicates task",
    ):
        generation._parse_closeout_evidence(payload)


def test_review_profile_cannot_omit_required_review_evidence() -> None:
    record = _manifest_record("MRL-0100")
    record["evidence_profile"] = "MRL_REVIEWED_EXACT_HEAD_V1"
    payload = json.dumps(
        {
            "records": [record],
            "schema_version": "MRL-CLOSEOUT-EVIDENCE-V1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(
        generation.MachineStateGenerationError,
        match="wrong profile",
    ):
        generation._parse_closeout_evidence(payload)


def test_review_profile_accepts_typed_trusted_exact_head_evidence() -> None:
    record = _manifest_record("MRL-0109")
    record["evidence_profile"] = "MRL_REVIEWED_EXACT_HEAD_V1"
    record["independent_exact_head_evidence_refs"] = ["review:3"]
    payload = json.dumps(
        {
            "records": [record],
            "schema_version": "MRL-CLOSEOUT-EVIDENCE-V1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    parsed = generation._parse_closeout_evidence(payload)
    assert parsed["MRL-0109"].independent_exact_head_evidence_refs == ("review:3",)


@pytest.mark.parametrize("value", ["3", "review:0", "issue:3", "review:x"])
def test_invalid_independent_evidence_ref_fails_closed(value: str) -> None:
    record = _manifest_record("MRL-0100")
    record["evidence_profile"] = "MRL_REVIEWED_EXACT_HEAD_V1"
    record["independent_exact_head_evidence_refs"] = [value]
    payload = json.dumps(
        {
            "records": [record],
            "schema_version": "MRL-CLOSEOUT-EVIDENCE-V1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    with pytest.raises(
        generation.MachineStateGenerationError,
        match="evidence ref is invalid",
    ):
        generation._parse_closeout_evidence(payload)


def test_dependency_parser_captures_wrapped_external_governance() -> None:
    dependencies = generation._dependencies(
        [
            "  - Depends on: MRL-0299, MRL-0399, MRL-0499, MRL-0599, MRL-0699,",
            "    MRL-0799, and current training/runtime governance.",
        ],
        "MRL-0800",
    )
    assert dependencies == (
        "MRL-0299",
        "MRL-0399",
        "MRL-0499",
        "MRL-0599",
        "MRL-0699",
        "MRL-0799",
    )


def test_dependency_parser_rejects_unmodeled_external_requirement() -> None:
    with pytest.raises(
        generation.MachineStateGenerationError,
        match="unmodeled external dependency",
    ):
        generation._dependencies(
            ["  - Depends on: MRL-0201 and arbitrary operator approval."],
            "MRL-0202",
        )


def test_task_parser_rejects_malformed_mrl_task_record() -> None:
    with pytest.raises(
        generation.MachineStateGenerationError,
        match="malformed task record",
    ):
        generation._task_records("- [x] **MRL-0201 - malformed task delimiter**")


def test_manifest_is_bound_project_state_source(tmp_path: Path) -> None:
    output_dir = tmp_path / "state"
    generation.generate_machine_state(
        Path(__file__).resolve().parents[1],
        output_dir,
    )
    project = json.loads((output_dir / "PROJECT_STATE.json").read_bytes())
    sources = project["sources"]
    tasks = project["tasks"]
    assert isinstance(sources, list)
    assert isinstance(tasks, list)
    bound = [
        source
        for source in sources
        if isinstance(source, dict)
        and source.get("path")
        == "specs/mesc-research-loop-v1/closeout-evidence-v1.json"
    ]
    assert len(bound) == 1
    assert isinstance(bound[0].get("git_blob_sha"), str)
    assert isinstance(bound[0].get("sha256"), str)
    assert tasks
    assert all(
        isinstance(task, dict)
        and isinstance(task.get("task_id"), str)
        and isinstance(task.get("state"), str)
        for task in tasks
    )
