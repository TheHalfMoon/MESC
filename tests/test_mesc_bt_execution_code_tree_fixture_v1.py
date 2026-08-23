from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._bt_execution_code_tree_fixture_v1 import (
    ExecutionCodeTreeIdentityError,
    ExecutionCodeTreeResolutionError,
    ResolvedExecutionCodeCommit,
    verify_execution_code_commit_tree_evidence,
)

_EXECUTION_CODE_SHA = "a" * 40
_EXECUTION_CODE_TREE = "b" * 40


class _StringSubclass(str):
    pass


class _EqualitySpoof:
    def __eq__(self, other: object) -> bool:
        return True


class _ResolvedCommitSubclass(ResolvedExecutionCodeCommit):
    pass


def _valid_resolver(_: str) -> ResolvedExecutionCodeCommit:
    return ResolvedExecutionCodeCommit(
        object_type="commit",
        commit_sha=_EXECUTION_CODE_SHA,
        tree_sha=_EXECUTION_CODE_TREE,
    )


def test_valid_fixture_commit_tree_resolution_evidence_passes() -> None:
    verify_execution_code_commit_tree_evidence(
        _EXECUTION_CODE_SHA,
        _EXECUTION_CODE_TREE,
        _valid_resolver,
    )


@pytest.mark.parametrize(
    ("execution_code_sha", "execution_code_tree"),
    [
        ("A" * 40, _EXECUTION_CODE_TREE),
        ("a" * 39, _EXECUTION_CODE_TREE),
        ("g" * 40, _EXECUTION_CODE_TREE),
        (_EXECUTION_CODE_SHA, "B" * 40),
        (_EXECUTION_CODE_SHA, "b" * 39),
        (_EXECUTION_CODE_SHA, "z" * 40),
    ],
)
def test_expected_git_identities_require_lowercase_40_hex(
    execution_code_sha: str,
    execution_code_tree: str,
) -> None:
    with pytest.raises(ExecutionCodeTreeIdentityError):
        verify_execution_code_commit_tree_evidence(
            execution_code_sha,
            execution_code_tree,
            _valid_resolver,
        )


def test_expected_identity_rejects_string_subclass() -> None:
    with pytest.raises(ExecutionCodeTreeIdentityError):
        verify_execution_code_commit_tree_evidence(
            _StringSubclass(_EXECUTION_CODE_SHA),
            _EXECUTION_CODE_TREE,
            _valid_resolver,
        )


def test_expected_identity_rejects_non_string_runtime_value() -> None:
    with pytest.raises(ExecutionCodeTreeIdentityError):
        verify_execution_code_commit_tree_evidence(
            cast(str, 1),
            _EXECUTION_CODE_TREE,
            _valid_resolver,
        )


def test_resolver_failure_is_fail_closed() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        raise RuntimeError("fixture resolver failure")

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


def test_resolved_metadata_requires_exact_dataclass_type() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return _ResolvedCommitSubclass(
            object_type="commit",
            commit_sha=_EXECUTION_CODE_SHA,
            tree_sha=_EXECUTION_CODE_TREE,
        )

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


def test_resolved_object_type_must_be_commit() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return ResolvedExecutionCodeCommit(
            object_type="tree",
            commit_sha=_EXECUTION_CODE_SHA,
            tree_sha=_EXECUTION_CODE_TREE,
        )

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


def test_resolved_object_type_rejects_string_subclass() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return ResolvedExecutionCodeCommit(
            object_type=_StringSubclass("commit"),
            commit_sha=_EXECUTION_CODE_SHA,
            tree_sha=_EXECUTION_CODE_TREE,
        )

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


def test_resolved_commit_sha_must_match_expected_sha() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return ResolvedExecutionCodeCommit(
            object_type="commit",
            commit_sha="c" * 40,
            tree_sha=_EXECUTION_CODE_TREE,
        )

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


def test_resolved_tree_sha_must_match_expected_tree() -> None:
    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return ResolvedExecutionCodeCommit(
            object_type="commit",
            commit_sha=_EXECUTION_CODE_SHA,
            tree_sha="c" * 40,
        )

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


@pytest.mark.parametrize("field", ["commit_sha", "tree_sha"])
def test_resolved_git_identity_rejects_string_subclass(field: str) -> None:
    observation = ResolvedExecutionCodeCommit(
        object_type="commit",
        commit_sha=_EXECUTION_CODE_SHA,
        tree_sha=_EXECUTION_CODE_TREE,
    )
    object.__setattr__(observation, field, _StringSubclass(getattr(observation, field)))

    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return observation

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


@pytest.mark.parametrize("field", ["commit_sha", "tree_sha"])
def test_resolved_git_identity_rejects_equality_spoof(field: str) -> None:
    observation = ResolvedExecutionCodeCommit(
        object_type="commit",
        commit_sha=_EXECUTION_CODE_SHA,
        tree_sha=_EXECUTION_CODE_TREE,
    )
    object.__setattr__(observation, field, _EqualitySpoof())

    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return observation

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("commit_sha", "A" * 40),
        ("commit_sha", "a" * 39),
        ("tree_sha", "B" * 40),
        ("tree_sha", "b" * 39),
    ],
)
def test_resolved_git_identity_requires_canonical_form(field: str, value: str) -> None:
    observation = ResolvedExecutionCodeCommit(
        object_type="commit",
        commit_sha=_EXECUTION_CODE_SHA,
        tree_sha=_EXECUTION_CODE_TREE,
    )
    object.__setattr__(observation, field, value)

    def resolve(_: str) -> ResolvedExecutionCodeCommit:
        return observation

    with pytest.raises(ExecutionCodeTreeResolutionError):
        verify_execution_code_commit_tree_evidence(
            _EXECUTION_CODE_SHA,
            _EXECUTION_CODE_TREE,
            resolve,
        )
