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
        independent_exact_head_review_ids=(),
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


def _manifest_record(task_id: str = _TASK) -> dict[str, object]:
    return {
        "canonical_merge_sha": _MERGE,
        "coderabbit_success_status_ids": [],
        "evidence_profile": "MRL_REPOSITORY_EXACT_HEAD_V1",
        "independent_exact_head_review_ids": [],
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


def test_review_profile_accepts_trusted_exact_head_review_binding() -> None:
    record = _manifest_record("MRL-0109")
    record["evidence_profile"] = "MRL_REVIEWED_EXACT_HEAD_V1"
    record["independent_exact_head_review_ids"] = [3]
    payload = json.dumps(
        {
            "records": [record],
            "schema_version": "MRL-CLOSEOUT-EVIDENCE-V1",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    parsed = generation._parse_closeout_evidence(payload)
    assert parsed["MRL-0109"].independent_exact_head_review_ids == (3,)


def test_manifest_is_bound_project_state_source_and_stale_gates_remain_open(
    tmp_path: Path,
) -> None:
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
    assert {
        source["path"]
        for source in sources
        if isinstance(source, dict)
    } >= {
        "specs/mesc-research-loop-v1/closeout-evidence-v1.json",
    }
    indexed = {
        task["task_id"]: task
        for task in tasks
        if isinstance(task, dict)
    }
    assert indexed["MRL-0299"]["state"] == "CLOSED_CANONICAL"
    assert indexed["MRL-0399"]["state"] != "CLOSED_CANONICAL"
    assert indexed["MRL-0799"]["state"] != "CLOSED_CANONICAL"
    for task_id in (
        "MRL-0801",
        "MRL-0802",
        "MRL-0803",
        "MRL-0804",
        "MRL-0805",
        "MRL-0806",
        "MRL-0807",
        "MRL-0808",
    ):
        assert indexed[task_id]["state"] == "PLANNED"
