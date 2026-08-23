"""Fail-closed fixture validation for execution-code commit/tree evidence.

This module validates only caller-supplied evidence for the Section D requirement
that ``EXECUTION_CODE_SHA`` resolve to ``EXECUTION_CODE_TREE``. It performs no
Git access, filesystem access, network access, subprocess execution, model
access, prompt dispatch, inference, generation, ranking, winner selection, or
training.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

_GIT_OBJECT_RE: Final = re.compile(r"^[0-9a-f]{40}$")


class ExecutionCodeTreeError(ValueError):
    """Base class for fail-closed execution-code tree evidence violations."""


class ExecutionCodeTreeIdentityError(ExecutionCodeTreeError):
    """Expected execution-code identities are malformed."""


class ExecutionCodeTreeResolutionError(ExecutionCodeTreeError):
    """Injected commit/tree resolution evidence is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class ResolvedExecutionCodeCommit:
    """Injected metadata for one exact execution-code commit lookup."""

    object_type: str
    commit_sha: str
    tree_sha: str


ExecutionCodeCommitResolver = Callable[[str], ResolvedExecutionCodeCommit]


def verify_execution_code_commit_tree_evidence(
    execution_code_sha: str,
    execution_code_tree: str,
    resolve: ExecutionCodeCommitResolver,
) -> None:
    """Verify injected evidence that the expected commit resolves to the tree."""
    _validate_expected_identity(execution_code_sha, field="EXECUTION_CODE_SHA")
    _validate_expected_identity(execution_code_tree, field="EXECUTION_CODE_TREE")

    try:
        resolved = resolve(execution_code_sha)
    except Exception as error:
        raise ExecutionCodeTreeResolutionError(
            "failed to resolve execution-code commit metadata"
        ) from error

    if type(resolved) is not ResolvedExecutionCodeCommit:
        raise ExecutionCodeTreeResolutionError(
            "resolver returned invalid execution-code commit metadata"
        )

    _validate_resolved_identity(resolved.object_type, field="resolved.object_type")
    _validate_resolved_identity(resolved.commit_sha, field="resolved.commit_sha")
    _validate_resolved_identity(resolved.tree_sha, field="resolved.tree_sha")

    if resolved.object_type != "commit":
        raise ExecutionCodeTreeResolutionError(
            "execution-code SHA must resolve to a Git commit object"
        )
    if resolved.commit_sha != execution_code_sha:
        raise ExecutionCodeTreeResolutionError(
            "resolved execution-code commit SHA does not match expected SHA"
        )
    if resolved.tree_sha != execution_code_tree:
        raise ExecutionCodeTreeResolutionError(
            "resolved execution-code tree does not match expected tree"
        )


def _validate_expected_identity(value: object, *, field: str) -> None:
    if type(value) is not str or _GIT_OBJECT_RE.fullmatch(value) is None:
        raise ExecutionCodeTreeIdentityError(
            f"{field} must be an exact lowercase 40-hex Git object identity"
        )


def _validate_resolved_identity(value: object, *, field: str) -> None:
    if type(value) is not str:
        raise ExecutionCodeTreeResolutionError(f"{field} must be an exact string")
    if field != "resolved.object_type" and _GIT_OBJECT_RE.fullmatch(value) is None:
        raise ExecutionCodeTreeResolutionError(
            f"{field} must be a lowercase 40-hex Git object identity"
        )
