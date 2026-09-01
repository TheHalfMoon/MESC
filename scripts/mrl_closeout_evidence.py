#!/usr/bin/env python3
"""Reproduce and verify canonical MRL closeout evidence from live GitHub truth.

This verifier is read-only. It derives checked-task closeout transitions from canonical
``origin/main`` history, binds every transition to its merged PR and exact final head,
and verifies the task-specific qualification profile against GitHub objects that existed
before the merge. It grants no execution, model, data, training, promotion, release, or
clinical authority.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Final, cast

_SCHEMA_VERSION: Final = "MRL-CLOSEOUT-EVIDENCE-V1"
_TASKS_PATH: Final = "specs/mesc-research-loop-v1/tasks.md"
_TASK_RE: Final = re.compile(r"^- \[([ x])\] \*\*(MRL-[0-9]{4}) — ")
_REVIEW_REQUIRED_TASKS: Final = frozenset(
    {"MRL-0100", "MRL-0101", "MRL-0102", "MRL-0103", "MRL-0109"}
)
_TRUSTED_INDEPENDENT_REVIEWERS: Final = frozenset(
    {"coderabbitai[bot]", "qodo-code-review[bot]"}
)


class CloseoutEvidenceError(RuntimeError):
    """Raised when live historical closeout evidence cannot be reproduced."""


def _git(root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CloseoutEvidenceError(
            f"Git command failed: git {' '.join(arguments)}"
        ) from exc
    return completed.stdout.strip()


def _task_states_at(root: Path, revision: str) -> dict[str, bool]:
    text = _git(root, "show", f"{revision}:{_TASKS_PATH}")
    result: dict[str, bool] = {}
    for line in text.splitlines():
        match = _TASK_RE.match(line)
        if match is None:
            continue
        task_id = match.group(2)
        if task_id in result:
            raise CloseoutEvidenceError(
                f"duplicate historical task identity: {task_id}"
            )
        result[task_id] = match.group(1) == "x"
    if not result:
        raise CloseoutEvidenceError(f"no MRL tasks at {revision}")
    return result


class _GitHub:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.token = token

    def _request(self, url: str, *, body: dict[str, object] | None = None) -> object:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method="POST" if body is not None else "GET",
        )
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception as exc:
            raise CloseoutEvidenceError(f"GitHub request failed: {url}") from exc

    def api(self, path: str) -> dict[str, object]:
        value = self._request("https://api.github.com/" + path.lstrip("/"))
        if type(value) is not dict:
            raise CloseoutEvidenceError(f"expected object response for {path}")
        return cast(dict[str, object], value)

    def list_pages(self, path: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            value = self._request(
                "https://api.github.com/"
                + f"{path.lstrip('/')}{separator}per_page=100&page={page}"
            )
            if type(value) is not list:
                raise CloseoutEvidenceError(f"expected list response for {path}")
            batch = cast(list[object], value)
            if any(type(item) is not dict for item in batch):
                raise CloseoutEvidenceError(f"malformed list response for {path}")
            typed = cast(list[dict[str, object]], batch)
            items.extend(typed)
            if len(typed) < 100:
                return items
            page += 1

    def workflow_runs(self, head_sha: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        page = 1
        while True:
            payload = self.api(
                f"repos/{self.repository}/actions/runs?head_sha={head_sha}"
                f"&event=pull_request&per_page=100&page={page}"
            )
            value = payload.get("workflow_runs")
            if type(value) is not list:
                raise CloseoutEvidenceError("workflow_runs response is malformed")
            batch = cast(list[object], value)
            if any(type(item) is not dict for item in batch):
                raise CloseoutEvidenceError("workflow_runs entries are malformed")
            typed = cast(list[dict[str, object]], batch)
            items.extend(typed)
            if len(typed) < 100:
                return items
            page += 1

    def graphql(self, query: str, variables: dict[str, object]) -> dict[str, object]:
        value = self._request(
            "https://api.github.com/graphql",
            body={"query": query, "variables": variables},
        )
        if type(value) is not dict:
            raise CloseoutEvidenceError("GraphQL response is malformed")
        payload = cast(dict[str, object], value)
        if payload.get("errors"):
            raise CloseoutEvidenceError(f"GraphQL errors: {payload['errors']!r}")
        data = payload.get("data")
        if type(data) is not dict:
            raise CloseoutEvidenceError("GraphQL data is malformed")
        return cast(dict[str, object], data)


def _dict(value: object, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise CloseoutEvidenceError(f"{label} is malformed")
    return cast(dict[str, object], value)


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value:
        raise CloseoutEvidenceError(f"{label} is malformed")
    return cast(str, value)


def _int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise CloseoutEvidenceError(f"{label} is malformed")
    return cast(int, value)


def _unresolved_premerge_origin_threads(
    github: _GitHub,
    *,
    owner: str,
    name: str,
    number: int,
    merged_at: str,
) -> int:
    query = """
    query($owner:String!,$name:String!,$number:Int!,$after:String){
      repository(owner:$owner,name:$name){
        pullRequest(number:$number){
          reviewThreads(first:100,after:$after){
            pageInfo{hasNextPage endCursor}
            nodes{isResolved comments(first:1){nodes{createdAt}}}
          }
        }
      }
    }
    """
    cursor: str | None = None
    offenders = 0
    while True:
        data = github.graphql(
            query,
            {"owner": owner, "name": name, "number": number, "after": cursor},
        )
        repository = _dict(data.get("repository"), "GraphQL repository")
        pull_request = _dict(repository.get("pullRequest"), "GraphQL pull request")
        connection = _dict(pull_request.get("reviewThreads"), "reviewThreads")
        nodes = connection.get("nodes")
        if type(nodes) is not list:
            raise CloseoutEvidenceError("reviewThreads nodes are malformed")
        for raw_node in cast(list[object], nodes):
            node = _dict(raw_node, "review thread")
            comments = _dict(node.get("comments"), "review-thread comments").get("nodes")
            if type(comments) is not list:
                raise CloseoutEvidenceError("review-thread comments are malformed")
            comment_rows = cast(list[object], comments)
            if node.get("isResolved") is False and comment_rows:
                first = _dict(comment_rows[0], "review-thread first comment")
                if _text(first.get("createdAt"), "review-thread createdAt") <= merged_at:
                    offenders += 1
        page_info = _dict(connection.get("pageInfo"), "reviewThreads pageInfo")
        if page_info.get("hasNextPage") is False:
            return offenders
        cursor_value = page_info.get("endCursor")
        if type(cursor_value) is not str or not cursor_value:
            raise CloseoutEvidenceError("review-thread pagination lost its cursor")
        cursor = cursor_value


def _transitions(root: Path, canonical_main: str) -> dict[tuple[str, str], list[str]]:
    canonical_states = _task_states_at(root, canonical_main)
    history: list[tuple[str, tuple[str, ...]]] = []
    text = _git(
        root,
        "log",
        "--first-parent",
        "--format=%H%x09%P",
        canonical_main,
        "--",
        _TASKS_PATH,
    )
    for line in text.splitlines():
        commit, parents_text = line.split("\t", 1)
        history.append((commit, tuple(parents_text.split())))

    result: dict[tuple[str, str], list[str]] = {}
    for task_id, checked in sorted(canonical_states.items()):
        if not checked:
            continue
        found: tuple[str, str] | None = None
        for commit, parents in history:
            if not parents:
                continue
            current = _task_states_at(root, commit).get(task_id)
            previous = _task_states_at(root, parents[0]).get(task_id)
            if current == previous:
                continue
            if (
                current is True
                and previous is False
                and len(parents) == 2
                and _task_states_at(root, parents[1]).get(task_id) is True
            ):
                found = (commit, parents[1])
            break
        if found is None:
            raise CloseoutEvidenceError(
                f"checked task has no canonical merge transition: {task_id}"
            )
        result.setdefault(found, []).append(task_id)
    return result


def _independent_evidence_refs(
    *,
    reviews: list[dict[str, object]],
    comments: list[dict[str, object]],
    qualified_head: str,
    merged_at: str,
) -> list[str]:
    refs: set[str] = set()
    for item in reviews:
        user = _dict(item.get("user"), "review user")
        submitted_at = item.get("submitted_at")
        if (
            user.get("login") in _TRUSTED_INDEPENDENT_REVIEWERS
            and item.get("commit_id") == qualified_head
            and item.get("state") in {"APPROVED", "COMMENTED"}
            and type(submitted_at) is str
            and submitted_at <= merged_at
        ):
            refs.add(f"review:{_int(item.get('id'), 'review ID')}")
    for item in comments:
        user = _dict(item.get("user"), "comment user")
        created_at = item.get("created_at")
        updated_at = item.get("updated_at")
        body = item.get("body")
        if (
            user.get("login") in _TRUSTED_INDEPENDENT_REVIEWERS
            and type(created_at) is str
            and created_at <= merged_at
            and type(updated_at) is str
            and updated_at <= merged_at
            and type(body) is str
            and qualified_head in body
        ):
            refs.add(f"comment:{_int(item.get('id'), 'comment ID')}")
    return sorted(refs)


def harvest(
    *,
    root: Path,
    repository: str,
    token: str,
) -> bytes:
    """Return canonical JSON bytes for live historical closeout evidence."""
    github = _GitHub(repository, token)
    canonical_main = _git(root, "rev-parse", "--verify", "refs/remotes/origin/main")
    owner, name = repository.split("/", 1)
    records: list[dict[str, object]] = []

    for (merge_sha, qualified_head), task_ids in sorted(
        _transitions(root, canonical_main).items(), key=lambda item: item[1][0]
    ):
        pulls = github.list_pages(f"repos/{repository}/commits/{merge_sha}/pulls")
        matches = [
            pr
            for pr in pulls
            if pr.get("merge_commit_sha") == merge_sha
            or _dict(pr.get("head"), "PR head").get("sha") == qualified_head
        ]
        if len(matches) != 1:
            raise CloseoutEvidenceError(
                f"PR association is not unique for {merge_sha}: {len(matches)}"
            )
        pr_number = _int(matches[0].get("number"), "PR number")
        pr = github.api(f"repos/{repository}/pulls/{pr_number}")
        head = _dict(pr.get("head"), "PR head")
        if (
            pr.get("merged") is not True
            or head.get("sha") != qualified_head
            or pr.get("merge_commit_sha") != merge_sha
        ):
            raise CloseoutEvidenceError(f"PR identity mismatch for {merge_sha}")
        merged_at = _text(pr.get("merged_at"), "PR merged_at")

        successful = [
            run
            for run in github.workflow_runs(qualified_head)
            if run.get("conclusion") == "success"
            and type(run.get("created_at")) is str
            and cast(str, run["created_at"]) <= merged_at
            and type(run.get("updated_at")) is str
            and cast(str, run["updated_at"]) <= merged_at
        ]
        ci = sorted(
            _int(run.get("id"), "CI run ID")
            for run in successful
            if run.get("name") == "CI"
        )
        codeql = sorted(
            _int(run.get("id"), "CodeQL run ID")
            for run in successful
            if run.get("name") == "CodeQL"
        )
        if not ci or not codeql:
            raise CloseoutEvidenceError(
                f"missing completed premerge exact-head CI/CodeQL for PR #{pr_number}"
            )

        reviews = github.list_pages(f"repos/{repository}/pulls/{pr_number}/reviews")
        comments = github.list_pages(f"repos/{repository}/issues/{pr_number}/comments")
        review_required = bool(_REVIEW_REQUIRED_TASKS.intersection(task_ids))
        independent_refs: list[str] = []
        if review_required:
            independent_refs = _independent_evidence_refs(
                reviews=reviews,
                comments=comments,
                qualified_head=qualified_head,
                merged_at=merged_at,
            )
            if not independent_refs:
                raise CloseoutEvidenceError(
                    f"missing trusted premerge independent exact-head review evidence "
                    f"for PR #{pr_number}"
                )

        strict = "MRL-0099" in task_ids
        qodo: list[int] = []
        owner_reviews: list[int] = []
        coderabbit: list[int] = []
        if strict:
            qodo = sorted(
                _int(item.get("id"), "Qodo comment ID")
                for item in comments
                if _dict(item.get("user"), "comment user").get("login")
                == "qodo-code-review[bot]"
                and type(item.get("created_at")) is str
                and cast(str, item["created_at"]) <= merged_at
                and type(item.get("updated_at")) is str
                and cast(str, item["updated_at"]) <= merged_at
                and type(item.get("body")) is str
                and qualified_head in cast(str, item["body"])
            )
            owner_reviews = sorted(
                _int(item.get("id"), "owner review ID")
                for item in reviews
                if _dict(item.get("user"), "review user").get("login") == "TheHalfMoon"
                and item.get("commit_id") == qualified_head
                and item.get("state") in {"APPROVED", "COMMENTED"}
                and type(item.get("submitted_at")) is str
                and cast(str, item["submitted_at"]) <= merged_at
                and type(item.get("body")) is str
                and qualified_head in cast(str, item["body"])
                and "PASS" in cast(str, item["body"])
            )
            statuses = github.list_pages(
                f"repos/{repository}/commits/{qualified_head}/statuses"
            )
            coderabbit = sorted(
                _int(item.get("id"), "CodeRabbit status ID")
                for item in statuses
                if item.get("context") == "CodeRabbit"
                and _dict(item.get("creator"), "status creator").get("login")
                == "coderabbitai[bot]"
                and item.get("state") == "success"
                and type(item.get("created_at")) is str
                and cast(str, item["created_at"]) <= merged_at
                and type(item.get("updated_at")) is str
                and cast(str, item["updated_at"]) <= merged_at
            )
            if not qodo or not owner_reviews or not coderabbit:
                raise CloseoutEvidenceError(
                    f"MRL-0099 missing trusted Qodo/internal-review/CodeRabbit "
                    f"evidence on PR #{pr_number}"
                )
            unresolved = _unresolved_premerge_origin_threads(
                github,
                owner=owner,
                name=name,
                number=pr_number,
                merged_at=merged_at,
            )
            if unresolved:
                raise CloseoutEvidenceError(
                    f"MRL-0099 has {unresolved} unresolved premerge-origin review "
                    f"thread(s) on PR #{pr_number}"
                )

        profile = "MRL_REPOSITORY_EXACT_HEAD_V1"
        if review_required:
            profile = "MRL_REVIEWED_EXACT_HEAD_V1"
        if strict:
            profile = "MRL_CONSTITUTION_EXACT_HEAD_V1"
        records.append(
            {
                "canonical_merge_sha": merge_sha,
                "coderabbit_success_status_ids": coderabbit,
                "evidence_profile": profile,
                "independent_exact_head_evidence_refs": independent_refs,
                "owner_exact_head_review_ids": owner_reviews,
                "pr_number": pr_number,
                "qodo_exact_head_comment_ids": qodo,
                "qualified_head_sha": qualified_head,
                "successful_ci_run_ids": ci,
                "successful_codeql_run_ids": codeql,
                "task_ids": sorted(task_ids),
            }
        )

    document = {"records": records, "schema_version": _SCHEMA_VERSION}
    return (
        json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="repository working tree (default: current directory)",
    )
    parser.add_argument(
        "--repository",
        default=os.environ.get("GITHUB_REPOSITORY", "TheHalfMoon/MESC"),
        help="GitHub owner/repository identity",
    )
    parser.add_argument(
        "--verify",
        type=Path,
        help="fail unless this file exactly matches live reproduced evidence",
    )
    args = parser.parse_args(argv)
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise CloseoutEvidenceError("GH_TOKEN or GITHUB_TOKEN is required")
    root = args.repository_root.resolve()
    rendered = harvest(root=root, repository=args.repository, token=token)
    if args.verify is None:
        sys.stdout.buffer.write(rendered)
        return 0
    path = args.verify if args.verify.is_absolute() else root / args.verify
    try:
        existing = path.read_bytes()
    except OSError as exc:
        raise CloseoutEvidenceError(f"closeout evidence manifest is unreadable: {path}") from exc
    if existing != rendered:
        raise CloseoutEvidenceError(
            "checked-in MRL closeout evidence differs from live historical reproduction"
        )
    print("MRL closeout evidence live binding: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CloseoutEvidenceError as exc:
        print(f"MRL closeout evidence live binding: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
