"""Read-only, fail-closed admission for the single Recovery-3 allocation.

An implementation decision is not a final-head grant. Admission reads a
separate, exact Founder approval from GitHub; it never writes an approval.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._mrl_0809_evidence_recovery_3_gate_v1 import (
    STATIC_MANIFEST,
    EvidenceRecovery3AuthorityIdentity,
    MRL0809EvidenceRecovery3GateError,
    validate_evidence_recovery_3_authority,
)

_REPOSITORY: Final = "TheHalfMoon/MESC"
_FOUNDER_ID: Final = 285091250
_PR: Final = 543
_APPROVAL_HEADER: Final = "MESC_RECOVERY_3_FINAL_SHA_APPROVAL_V1\n"
_SHA40: Final = re.compile(r"[0-9a-f]{40}\Z")
_SHA256: Final = re.compile(r"[0-9a-f]{64}\Z")
_WORKFLOWS: Final = (
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/optional-extras.yml",
    ".github/workflows/hf-publication.yml",
)


@dataclass(frozen=True, slots=True)
class Recovery3EffectiveIdentity:
    canonical_revision: str
    canonical_tree: str
    approved_implementation_sha: str
    implementation_merge_sha: str
    approval_comment_id: int
    approval_body_sha256: str
    authority: EvidenceRecovery3AuthorityIdentity


def _fail(message: str) -> Never:
    raise MRL0809EvidenceRecovery3GateError(f"Recovery-3 launch NOT_EFFECTIVE: {message}")


def _object(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _array(value: object, label: str) -> list[object]:
    if type(value) is not list:
        _fail(f"{label} must be an array")
    return cast(list[object], value)


def _sha(value: object, label: str, *, digest: bool = False) -> str:
    pattern = _SHA256 if digest else _SHA40
    if type(value) is not str or pattern.fullmatch(value) is None:
        _fail(f"{label} is not an exact lowercase hexadecimal identity")
    return value


def _git(root: Path, *args: str) -> bytes:
    try:
        return subprocess.check_output(
            ("git", "-C", str(root), *args), stderr=subprocess.DEVNULL, timeout=20.0
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MRL0809EvidenceRecovery3GateError("Recovery-3 Git identity unavailable") from exc


def _reject_constant(value: str) -> Never:
    _fail(f"non-standard JSON constant: {value}")


def _api_json(path: str) -> object:
    """Fixed public GitHub origin, bounded reads, TLS verification, no retries."""
    if not path.startswith(f"/repos/{_REPOSITORY}/"):
        _fail("foreign GitHub repository requested")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "MESC-Recovery-3/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20.0) as response:
            if urllib.parse.urlsplit(response.url).hostname != "api.github.com":
                _fail("GitHub response changed origin")
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            _fail("GitHub response exceeded bounded size")
        return json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (OSError, urllib.error.URLError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MRL0809EvidenceRecovery3GateError(
            "Recovery-3 launch NOT_EFFECTIVE: independent GitHub evidence unavailable"
        ) from exc


def _comments() -> list[object]:
    comments: list[object] = []
    for page in range(1, 21):
        rows = _array(
            _api_json(f"/repos/{_REPOSITORY}/issues/450/comments?per_page=100&page={page}"),
            "Founder decision comments",
        )
        comments.extend(rows)
        if len(rows) < 100:
            return comments
    _fail("Founder decision pagination exceeded bounded size")


def _approval(
    comments: list[object],
    *,
    approved_head: str,
    manifest_sha256: str,
    merged_at: str | None = None,
    qualified_at: list[str] | None = None,
) -> tuple[int, str]:
    """The newest exact structured decision controls, including revocation.

    Human approval must precede this public record. An agent must never create
    this record under broad engineering authority or infer it from acceptance.
    """
    decisions: list[tuple[int, dict[str, object], str, str]] = []
    for value in comments:
        row = _object(value, "decision comment")
        body = row.get("body")
        if type(body) is not str or not body.startswith(_APPROVAL_HEADER):
            continue
        author = _object(row.get("user"), "decision author")
        if (
            type(author.get("id")) is not int
            or author.get("id") != _FOUNDER_ID
            or author.get("login") != "TheHalfMoon"
            or row.get("author_association") != "OWNER"
        ):
            continue
        comment_id = row.get("id")
        if type(comment_id) is not int or comment_id <= 0:
            _fail("decision comment identity is malformed")
        if (
            type(row.get("created_at")) is not str
            or not row.get("created_at")
            or row.get("created_at") != row.get("updated_at")
        ):
            _fail("Founder decision was edited; require a new immutable decision")
        try:
            document = _object(json.loads(body[len(_APPROVAL_HEADER) :]), "final-SHA decision")
        except json.JSONDecodeError as exc:
            raise MRL0809EvidenceRecovery3GateError("final-SHA decision JSON is malformed") from exc
        if document.get("decision_id") == "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3":
            decisions.append((comment_id, document, body, cast(str, row["created_at"])))
    if not decisions:
        _fail("missing separate Founder final-SHA approval")
    comment_id, document, body, created_at = max(decisions, key=lambda entry: entry[0])
    approval_time = _timestamp(created_at)
    if merged_at is not None and approval_time >= _timestamp(merged_at):
        _fail("final-SHA approval did not precede the normal implementation merge")
    if qualified_at is not None and any(
        _timestamp(value) > approval_time for value in qualified_at
    ):
        _fail("exact-head qualification did not precede final-SHA approval")
    expected: dict[str, object] = {
        "decision_id": "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3",
        "state": "APPROVED",
        "implementation_sha": approved_head,
        "static_manifest_sha256": manifest_sha256,
        "pull_request": _PR,
        "allocations_authorized": 1,
        "provider_class": "GOOGLE_COLAB_FREE",
        "gpu_class": "STANDARD_T4",
        "paid_compute_authorized": False,
        "automatic_retry_authorized": False,
    }
    if set(document) != set(expected) or any(
        type(document[key]) is not type(value) or document[key] != value
        for key, value in expected.items()
    ):
        _fail("latest Founder decision is revoked, mismatched, or outside the bounded grant")
    return comment_id, hashlib.sha256(body.encode("utf-8")).hexdigest()


def _timestamp(value: object) -> datetime:
    if type(value) is not str:
        _fail("GitHub qualification timestamp is missing")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is None:
        _fail("GitHub qualification timestamp is not exact UTC")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _fail("GitHub qualification timestamp is malformed")
    if result.tzinfo is None:
        _fail("GitHub qualification timestamp is not timezone-aware")
    return result


def _require_workflow_runs(
    revision: str,
    *,
    branch: str = "main",
    event: str = "push",
    workflows: tuple[str, ...] = _WORKFLOWS,
) -> list[str]:
    completed: list[str] = []
    for path in workflows:
        name = urllib.parse.quote(path.rsplit("/", 1)[1], safe="")
        response = _object(
            _api_json(
                f"/repos/{_REPOSITORY}/actions/workflows/{name}/runs"
                f"?head_sha={revision}&branch={urllib.parse.quote(branch, safe='')}"
                f"&event={event}&per_page=100"
            ),
            "workflow runs",
        )
        total = response.get("total_count")
        if type(total) is not int or not 0 < total <= 100:
            _fail(f"missing or unbounded workflow evidence: {path}")
        rows = [_object(row, "workflow run") for row in _array(response.get("workflow_runs"), path)]
        if not rows or any(type(row.get("id")) is not int for row in rows):
            _fail(f"malformed workflow identity: {path}")
        latest = max(rows, key=lambda row: cast(int, row["id"]))
        repository = _object(latest.get("repository"), "workflow repository")
        if (
            latest.get("head_sha") != revision
            or latest.get("head_branch") != branch
            or latest.get("event") != event
            or latest.get("path") != path
            or latest.get("status") != "completed"
            or latest.get("conclusion") != "success"
            or repository.get("full_name") != _REPOSITORY
            or type(latest.get("run_attempt")) is not int
            or cast(int, latest["run_attempt"]) < 1
        ):
            _fail(f"latest workflow is not successful fresh-main qualification: {path}")
        finished = latest.get("updated_at")
        _timestamp(finished)
        completed.append(cast(str, finished))
    return completed


def validate_recovery_3_effectiveness(root: Path, revision: str) -> Recovery3EffectiveIdentity:
    revision = _sha(revision, "canonical revision")
    root = root.resolve(strict=True)
    if _git(root, "rev-parse", "HEAD").decode().strip() != revision:
        _fail("executing HEAD differs from canonical revision")
    if _git(root, "status", "--porcelain", "--untracked-files=all").strip():
        _fail("executing repository is dirty")
    main = _object(_api_json(f"/repos/{_REPOSITORY}/commits/main"), "live main")
    if main.get("sha") != revision:
        _fail("executing revision differs from live canonical main")
    tree = _sha(
        _object(_object(main.get("commit"), "commit").get("tree"), "tree").get("sha"), "tree"
    )
    if _git(root, "rev-parse", "HEAD^{tree}").decode().strip() != tree:
        _fail("executing tree differs from live canonical tree")
    pr = _object(_api_json(f"/repos/{_REPOSITORY}/pulls/{_PR}"), "Recovery-3 PR")
    if pr.get("merged") is not True or pr.get("state") != "closed":
        _fail("final implementation was not canonically merged")
    head = _object(pr.get("head"), "PR head")
    base = _object(pr.get("base"), "PR base")
    if (
        _object(head.get("repo"), "head repository").get("full_name") != _REPOSITORY
        or _object(base.get("repo"), "base repository").get("full_name") != _REPOSITORY
        or base.get("ref") != "main"
    ):
        _fail("implementation provenance is foreign")
    approved_head = _sha(head.get("sha"), "approved implementation head")
    merge = _sha(pr.get("merge_commit_sha"), "implementation merge")
    parents = _git(root, "show", "-s", "--format=%P", merge).decode().strip().split()
    if len(parents) != 2 or parents[1] != approved_head:
        _fail("implementation merge is not a normal two-parent approved-head merge")
    _git(root, "merge-base", "--is-ancestor", merge, revision)
    authority = validate_evidence_recovery_3_authority(root, revision)
    approved_authority = validate_evidence_recovery_3_authority(root, approved_head)
    if authority != approved_authority:
        _fail("approved implementation source manifest changed")
    manifest_raw = _git(root, "show", f"{revision}:{STATIC_MANIFEST}")
    manifest = _object(json.loads(manifest_raw), "source manifest")
    sources = _array(manifest.get("sources"), "runtime sources")
    executing_module = Path(__file__).resolve()
    executing_module_seen = False
    for value in sources:
        row = _object(value, "runtime source")
        path = row.get("path")
        if type(path) is not str:
            _fail("runtime source path is malformed")
        local = (root / path).resolve(strict=True)
        if not local.is_relative_to(root):
            _fail("runtime source escapes canonical repository")
        if local.read_bytes() != _git(root, "show", f"{revision}:{path}"):
            _fail(f"executing source differs from canonical Git source: {path}")
        executing_module_seen |= local == executing_module
    if not executing_module_seen:
        _fail("executing effectiveness module is outside the frozen source manifest")
    merged_at = pr.get("merged_at")
    _timestamp(merged_at)
    head_branch = head.get("ref")
    if type(head_branch) is not str or not head_branch:
        _fail("approved implementation branch is missing")
    qualified_at = _require_workflow_runs(
        approved_head, branch=head_branch, event="pull_request", workflows=_WORKFLOWS[:3]
    )
    comment_id, body_sha = _approval(
        _comments(),
        approved_head=approved_head,
        manifest_sha256=authority.static_manifest_sha256,
        merged_at=cast(str, merged_at),
        qualified_at=qualified_at,
    )
    _require_workflow_runs(revision)
    # Fail closed if main moved during the bounded independent observations.
    if (
        _object(_api_json(f"/repos/{_REPOSITORY}/commits/main"), "final live main").get("sha")
        != revision
    ):
        _fail("canonical main moved during qualification")
    final_approval = _approval(
        _comments(),
        approved_head=approved_head,
        manifest_sha256=authority.static_manifest_sha256,
        merged_at=cast(str, merged_at),
        qualified_at=qualified_at,
    )
    if final_approval != (comment_id, body_sha):
        _fail("Founder approval changed during qualification")
    return Recovery3EffectiveIdentity(
        canonical_revision=revision,
        canonical_tree=tree,
        approved_implementation_sha=approved_head,
        implementation_merge_sha=merge,
        approval_comment_id=comment_id,
        approval_body_sha256=body_sha,
        authority=authority,
    )
