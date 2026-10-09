"""Synthetic independent approval, merge and fresh-main admission boundaries."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0809_evidence_recovery_3_effectiveness_v1 as effectiveness
from medscale.mesc._mrl_0809_evidence_recovery_3_gate_v1 import (
    STATIC_MANIFEST,
    EvidenceRecovery3AuthorityIdentity,
    MRL0809EvidenceRecovery3GateError,
)

HEAD = "a" * 40
TREE = "b" * 40
APPROVED = "c" * 40
MERGE = "d" * 40
DIGEST = "e" * 64


def _decision(*, state: str = "APPROVED") -> dict[str, object]:
    return {
        "decision_id": "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3",
        "state": state,
        "implementation_sha": APPROVED,
        "static_manifest_sha256": DIGEST,
        "pull_request": 543,
        "allocations_authorized": 1,
        "provider_class": "GOOGLE_COLAB_FREE",
        "gpu_class": "STANDARD_T4",
        "paid_compute_authorized": False,
        "automatic_retry_authorized": False,
    }


def _comment(*, state: str = "APPROVED", comment_id: int = 10) -> dict[str, object]:
    return {
        "id": comment_id,
        "created_at": "2026-10-08T00:00:00Z",
        "updated_at": "2026-10-08T00:00:00Z",
        "user": {"login": "TheHalfMoon", "id": 285091250},
        "author_association": "OWNER",
        "body": effectiveness._APPROVAL_HEADER + json.dumps(_decision(state=state)),
    }


def test_exact_separate_approval_is_bound_to_its_body_and_comment() -> None:
    comment = _comment()
    assert effectiveness._approval([comment], approved_head=APPROVED, manifest_sha256=DIGEST) == (
        10,
        hashlib.sha256(str(comment["body"]).encode()).hexdigest(),
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("implementation_sha", "f" * 40),
        ("static_manifest_sha256", "f" * 64),
        ("allocations_authorized", True),
        ("allocations_authorized", 2),
        ("paid_compute_authorized", 0),
        ("paid_compute_authorized", True),
        ("automatic_retry_authorized", True),
        ("pull_request", 541),
        ("provider_class", "PAID"),
        ("gpu_class", "A100"),
    ],
)
def test_approval_mismatch_and_bool_integer_equivalence_are_rejected(
    field: str,
    value: object,
) -> None:
    comment = _comment()
    decision = _decision()
    decision[field] = value
    comment["body"] = effectiveness._APPROVAL_HEADER + json.dumps(decision)
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="latest Founder decision"):
        effectiveness._approval([comment], approved_head=APPROVED, manifest_sha256=DIGEST)


@pytest.mark.parametrize(
    "field,value",
    [
        ("user", {"login": "other", "id": 285091250}),
        ("user", {"login": "TheHalfMoon", "id": 1}),
        ("author_association", "CONTRIBUTOR"),
        ("body", "Accept this bounded Recovery-3 decision"),
    ],
)
def test_foreign_or_implementation_only_decision_cannot_arm(
    field: str,
    value: object,
) -> None:
    comment = _comment()
    comment[field] = value
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="missing separate"):
        effectiveness._approval([comment], approved_head=APPROVED, manifest_sha256=DIGEST)


def test_edited_approval_is_rejected() -> None:
    comment = _comment()
    comment["updated_at"] = "2026-10-08T00:01:00Z"
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="edited"):
        effectiveness._approval([comment], approved_head=APPROVED, manifest_sha256=DIGEST)


def test_newer_revocation_supersedes_old_approval() -> None:
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="revoked"):
        effectiveness._approval(
            [_comment(), _comment(state="REVOKED", comment_id=11)],
            approved_head=APPROVED,
            manifest_sha256=DIGEST,
        )


def _run(path: str, *, run_id: int = 1) -> dict[str, object]:
    return {
        "id": run_id,
        "head_sha": HEAD,
        "head_branch": "main",
        "event": "push",
        "path": path,
        "status": "completed",
        "conclusion": "success",
        "run_attempt": 1,
        "updated_at": "2026-10-07T23:59:00Z",
        "repository": {"full_name": "TheHalfMoon/MESC"},
    }


def test_all_four_workflows_require_exact_latest_success(monkeypatch: pytest.MonkeyPatch) -> None:
    paths: list[str] = []

    def api(path: str) -> object:
        paths.append(path)
        workflow = next(p for p in effectiveness._WORKFLOWS if p.rsplit("/", 1)[1] in path)
        return {"total_count": 1, "workflow_runs": [_run(workflow)]}

    monkeypatch.setattr(effectiveness, "_api_json", api)
    effectiveness._require_workflow_runs(HEAD)
    assert len(paths) == 4
    assert all(f"head_sha={HEAD}" in path for path in paths)


@pytest.mark.parametrize(
    "field,value",
    [
        ("head_sha", APPROVED),
        ("head_branch", "feature"),
        ("event", "pull_request"),
        ("path", ".github/workflows/other.yml"),
        ("status", "in_progress"),
        ("conclusion", "failure"),
        ("run_attempt", True),
        ("repository", {"full_name": "other/MESC"}),
    ],
)
def test_newer_bad_workflow_invalidates_earlier_success(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    old = _run(effectiveness._WORKFLOWS[0])
    latest = _run(effectiveness._WORKFLOWS[0], run_id=2)
    latest[field] = value
    monkeypatch.setattr(
        effectiveness,
        "_api_json",
        lambda _path: {
            "total_count": 2,
            "workflow_runs": [old, latest],
        },
    )
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="latest workflow"):
        effectiveness._require_workflow_runs(HEAD)


def _admission_fixture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> tuple[dict[str, bytes], dict[str, object]]:
    source = tmp_path / "effectiveness.py"
    source.write_bytes(b"synthetic canonical source\n")
    manifest = json.dumps({"sources": [{"path": source.name}]}).encode()
    git = {
        "rev-parse HEAD": (HEAD + "\n").encode(),
        "status --porcelain --untracked-files=all": b"",
        "rev-parse HEAD^{tree}": (TREE + "\n").encode(),
        f"show -s --format=%P {MERGE}": ("f" * 40 + " " + APPROVED).encode(),
        f"merge-base --is-ancestor {MERGE} {HEAD}": b"",
        f"show {HEAD}:{STATIC_MANIFEST}": manifest,
        f"show {HEAD}:{source.name}": source.read_bytes(),
    }
    main: dict[str, object] = {"sha": HEAD, "commit": {"tree": {"sha": TREE}}}
    repository = {"full_name": "TheHalfMoon/MESC"}
    pr: dict[str, object] = {
        "merged": True,
        "state": "closed",
        "merge_commit_sha": MERGE,
        "head": {"sha": APPROVED, "ref": "feat/recovery3", "repo": repository},
        "merged_at": "2026-10-08T00:01:00Z",
        "base": {"ref": "main", "repo": repository},
    }
    api: dict[str, object] = {
        "/repos/TheHalfMoon/MESC/commits/main": main,
        "/repos/TheHalfMoon/MESC/pulls/543": pr,
    }
    authority = EvidenceRecovery3AuthorityIdentity(DIGEST, DIGEST, DIGEST, DIGEST, HEAD, TREE)
    monkeypatch.setattr(effectiveness, "__file__", str(source))
    monkeypatch.setattr(effectiveness, "_git", lambda _root, *args: git[" ".join(args)])
    monkeypatch.setattr(effectiveness, "_api_json", lambda path: copy.deepcopy(api[path]))
    monkeypatch.setattr(
        effectiveness, "validate_evidence_recovery_3_authority", lambda *_: authority
    )
    monkeypatch.setattr(effectiveness, "_comments", lambda: [_comment()])
    monkeypatch.setattr(
        effectiveness,
        "_require_workflow_runs",
        lambda _revision, **_kwargs: ["2026-10-07T23:59:00Z"],
    )
    return git, api


def test_complete_synthetic_admission_returns_bound_identity(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _admission_fixture(monkeypatch, tmp_path)
    identity = effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)
    assert identity.canonical_revision == HEAD
    assert identity.canonical_tree == TREE
    assert identity.approved_implementation_sha == APPROVED
    assert identity.implementation_merge_sha == MERGE
    assert identity.approval_comment_id == 10


@pytest.mark.parametrize("revision", ["HEAD", "a" * 39, "A" * 40, "g" * 40])
def test_revision_aliases_and_non_hex_revisions_are_rejected(tmp_path: Path, revision: str) -> None:
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="hexadecimal"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, revision)


@pytest.mark.parametrize(
    "mutation", ["dirty", "wrong_head", "wrong_tree", "squash", "wrong_parent"]
)
def test_local_and_merge_provenance_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    git, _ = _admission_fixture(monkeypatch, tmp_path)
    if mutation == "dirty":
        git["status --porcelain --untracked-files=all"] = b" M modified.py"
    elif mutation == "wrong_head":
        git["rev-parse HEAD"] = APPROVED.encode()
    elif mutation == "wrong_tree":
        git["rev-parse HEAD^{tree}"] = HEAD.encode()
    elif mutation == "squash":
        git[f"show -s --format=%P {MERGE}"] = HEAD.encode()
    else:
        git[f"show -s --format=%P {MERGE}"] = (HEAD + " " + HEAD).encode()
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="NOT_EFFECTIVE"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)


def test_canonical_source_mismatch_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    git, _ = _admission_fixture(monkeypatch, tmp_path)
    git[f"show {HEAD}:effectiveness.py"] = b"different executing code"
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="source differs"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)


def test_live_main_move_during_observation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _, api = _admission_fixture(monkeypatch, tmp_path)
    observations = 0

    def moving_api(path: str) -> object:
        nonlocal observations
        if path.endswith("/commits/main"):
            observations += 1
            if observations == 2:
                return {"sha": APPROVED}
        return copy.deepcopy(api[path])

    monkeypatch.setattr(effectiveness, "_api_json", moving_api)
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="moved during"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)


@pytest.mark.parametrize(
    "merged_at,qualified_at,reason",
    [
        ("2026-10-07T23:59:00Z", ["2026-10-07T23:58:00Z"], "approval did not precede"),
        ("2026-10-08T00:01:00Z", ["2026-10-08T00:00:30Z"], "qualification did not precede"),
    ],
)
def test_approval_must_follow_exact_head_ci_and_precede_merge(
    merged_at: str,
    qualified_at: list[str],
    reason: str,
) -> None:
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match=reason):
        effectiveness._approval(
            [_comment()],
            approved_head=APPROVED,
            manifest_sha256=DIGEST,
            merged_at=merged_at,
            qualified_at=qualified_at,
        )


def test_failed_exact_head_qualification_blocks_admission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _admission_fixture(monkeypatch, tmp_path)
    calls: list[str] = []

    def workflows(revision: str, **_kwargs: object) -> list[str]:
        calls.append(revision)
        if revision == APPROVED:
            raise MRL0809EvidenceRecovery3GateError("exact head failed")
        return []

    monkeypatch.setattr(effectiveness, "_require_workflow_runs", workflows)
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="exact head failed"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)
    assert calls == [APPROVED]


@pytest.mark.parametrize(
    "value", [None, "", "2026-10-08", "2026-10-08T00:01:00", "2026-10-08T00:01:00+00:00"]
)
def test_missing_or_non_utc_merge_timestamp_blocks_admission(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    value: object,
) -> None:
    _, api = _admission_fixture(monkeypatch, tmp_path)
    pr = api["/repos/TheHalfMoon/MESC/pulls/543"]
    assert isinstance(pr, dict)
    pr["merged_at"] = value
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="timestamp"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)


def test_revocation_during_workflow_observation_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _admission_fixture(monkeypatch, tmp_path)
    observations = 0

    def comments() -> list[object]:
        nonlocal observations
        observations += 1
        return (
            [_comment()]
            if observations == 1
            else [_comment(), _comment(state="REVOKED", comment_id=11)]
        )

    monkeypatch.setattr(effectiveness, "_comments", comments)
    with pytest.raises(MRL0809EvidenceRecovery3GateError, match="revoked"):
        effectiveness.validate_recovery_3_effectiveness(tmp_path, HEAD)
