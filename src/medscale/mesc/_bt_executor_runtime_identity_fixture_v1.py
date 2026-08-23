"""Fail-closed fixture validation for executor runtime-object identity evidence.

This module validates only caller-supplied evidence for the descriptor-relative
runtime-object identity requirements in ``FD-MESC-BT-EXEC-1`` Section D. It
does not call ``openat2(2)``, open files, traverse a filesystem, execute or
import harness code, start subprocesses, access a network, access a model,
dispatch prompts, run inference, rank candidates, select a winner, or train.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._bt_executor_allowlist_v1 import (
    ExecutorAllowlist,
    ExecutorAllowlistEntry,
    canonical_executor_allowlist_bytes,
    parse_executor_allowlist,
)

_GIT_OBJECT_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_REQUIRED_RESOLVE_FLAGS: Final = frozenset(
    {
        "RESOLVE_BENEATH",
        "RESOLVE_NO_MAGICLINKS",
        "RESOLVE_NO_SYMLINKS",
        "RESOLVE_NO_XDEV",
    }
)
_REQUIRED_OPEN_FLAGS: Final = frozenset({"O_CLOEXEC", "O_NOFOLLOW", "O_RDONLY"})


class ExecutorRuntimeIdentityError(ValueError):
    """Base class for fail-closed executor runtime identity evidence violations."""


class ExecutorRuntimeIdentityAllowlistError(ExecutorRuntimeIdentityError):
    """The supplied executor allowlist is not parser-validated canonical data."""


class ExecutorRuntimeIdentityResolutionError(ExecutorRuntimeIdentityError):
    """Injected runtime identity evidence is missing, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class RuntimeExecutorObjectObservation:
    """Injected evidence for one allowlisted runtime executor or harness object."""

    path: str
    open_api: str
    descriptor_relative: bool
    resolve_flags: frozenset[str]
    open_flags: frozenset[str]
    repository_checkout_sha: str
    repository_checkout_tree: str
    checkout_root_read_only: bool
    fstat_regular_file: bool
    git_blob_recomputed_from_exact_opened_bytes: bool
    verification_device: int
    verification_inode: int
    verification_byte_length: int
    verification_git_blob_sha: str
    handoff_device: int
    handoff_inode: int
    handoff_byte_length: int
    handoff_git_blob_sha: str
    handoff_mount_read_only: bool
    handoff_mount_immutable: bool
    identity_checked_immediately_before_execution_or_import: bool
    execution_or_import_uses_same_opened_object_or_proven_equivalent: bool


RuntimeExecutorObjectResolver = Callable[[str], RuntimeExecutorObjectObservation]


def verify_executor_runtime_identity_evidence(
    allowlist: ExecutorAllowlist,
    *,
    execution_code_sha: str,
    execution_code_tree: str,
    resolve: RuntimeExecutorObjectResolver,
) -> None:
    """Verify injected exact-checkout and same-object runtime identity evidence."""
    _revalidate_allowlist(allowlist)
    _validate_execution_identity(execution_code_sha, field="execution_code_sha")
    _validate_execution_identity(execution_code_tree, field="execution_code_tree")

    for entry in allowlist.entries:
        observation = _resolve_observation(entry, resolve)
        _verify_observation(
            entry,
            observation,
            execution_code_sha=execution_code_sha,
            execution_code_tree=execution_code_tree,
        )


def _revalidate_allowlist(allowlist: ExecutorAllowlist) -> None:
    if type(allowlist) is not ExecutorAllowlist:
        raise ExecutorRuntimeIdentityAllowlistError("allowlist is not parser-validated")
    if type(allowlist.entries) is not tuple:
        raise ExecutorRuntimeIdentityAllowlistError("allowlist contains non-exact field types")
    if type(allowlist.sha256) is not str or type(allowlist.byte_length) is not int:
        raise ExecutorRuntimeIdentityAllowlistError("allowlist contains non-exact field types")

    for entry in allowlist.entries:
        if type(entry) is not ExecutorAllowlistEntry:
            raise ExecutorRuntimeIdentityAllowlistError("allowlist contains non-exact field types")
        if type(entry.git_blob_sha) is not str or type(entry.path) is not str:
            raise ExecutorRuntimeIdentityAllowlistError("allowlist contains non-exact field types")

    try:
        canonical = canonical_executor_allowlist_bytes(allowlist.entries)
        reparsed = parse_executor_allowlist(canonical)
    except Exception as error:
        raise ExecutorRuntimeIdentityAllowlistError(
            "allowlist object does not contain valid canonical allowlist content"
        ) from error

    if reparsed != allowlist:
        raise ExecutorRuntimeIdentityAllowlistError(
            "allowlist object identity does not match its canonical bytes"
        )


def _validate_execution_identity(value: object, *, field: str) -> None:
    if type(value) is not str or _GIT_OBJECT_RE.fullmatch(value) is None:
        raise ExecutorRuntimeIdentityResolutionError(
            f"{field} must be an exact lowercase 40-hex Git identity"
        )


def _resolve_observation(
    entry: ExecutorAllowlistEntry,
    resolve: RuntimeExecutorObjectResolver,
) -> RuntimeExecutorObjectObservation:
    try:
        observation = resolve(entry.path)
    except Exception as error:
        raise ExecutorRuntimeIdentityResolutionError(
            f"failed to resolve runtime identity evidence for {entry.path!r}"
        ) from error

    if type(observation) is not RuntimeExecutorObjectObservation:
        raise ExecutorRuntimeIdentityResolutionError(
            f"resolver returned invalid runtime identity evidence for {entry.path!r}"
        )
    return observation


def _verify_observation(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
    *,
    execution_code_sha: str,
    execution_code_tree: str,
) -> None:
    _verify_path_and_open_contract(entry, observation)
    _verify_checkout_binding(
        entry,
        observation,
        execution_code_sha=execution_code_sha,
        execution_code_tree=execution_code_tree,
    )
    _verify_boolean_controls(entry, observation)
    _verify_numeric_identity(entry, observation)
    _verify_blob_identity(entry, observation)


def _verify_path_and_open_contract(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
) -> None:
    if type(observation.path) is not str or observation.path != entry.path:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime evidence path mismatch for {entry.path!r}"
        )
    if type(observation.open_api) is not str or observation.open_api != "openat2":
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime evidence for {entry.path!r} must use openat2"
        )
    _verify_flag_set(
        observation.resolve_flags,
        required=_REQUIRED_RESOLVE_FLAGS,
        label="resolve",
        path=entry.path,
    )
    _verify_flag_set(
        observation.open_flags,
        required=_REQUIRED_OPEN_FLAGS,
        label="open",
        path=entry.path,
    )


def _verify_flag_set(
    value: object,
    *,
    required: frozenset[str],
    label: str,
    path: str,
) -> None:
    if type(value) is not frozenset or any(type(flag) is not str for flag in value):
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime {label} flags are malformed for {path!r}"
        )
    if value != required:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime {label} flags do not match the required set for {path!r}"
        )


def _verify_checkout_binding(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
    *,
    execution_code_sha: str,
    execution_code_tree: str,
) -> None:
    if type(observation.repository_checkout_sha) is not str:
        raise ExecutorRuntimeIdentityResolutionError(
            f"repository checkout SHA is malformed for {entry.path!r}"
        )
    if type(observation.repository_checkout_tree) is not str:
        raise ExecutorRuntimeIdentityResolutionError(
            f"repository checkout tree is malformed for {entry.path!r}"
        )
    if observation.repository_checkout_sha != execution_code_sha:
        raise ExecutorRuntimeIdentityResolutionError(
            f"repository checkout SHA mismatch for {entry.path!r}"
        )
    if observation.repository_checkout_tree != execution_code_tree:
        raise ExecutorRuntimeIdentityResolutionError(
            f"repository checkout tree mismatch for {entry.path!r}"
        )


def _verify_boolean_controls(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
) -> None:
    controls = (
        ("descriptor_relative", observation.descriptor_relative),
        ("checkout_root_read_only", observation.checkout_root_read_only),
        ("fstat_regular_file", observation.fstat_regular_file),
        (
            "git_blob_recomputed_from_exact_opened_bytes",
            observation.git_blob_recomputed_from_exact_opened_bytes,
        ),
        ("handoff_mount_read_only", observation.handoff_mount_read_only),
        ("handoff_mount_immutable", observation.handoff_mount_immutable),
        (
            "identity_checked_immediately_before_execution_or_import",
            observation.identity_checked_immediately_before_execution_or_import,
        ),
        (
            "execution_or_import_uses_same_opened_object_or_proven_equivalent",
            observation.execution_or_import_uses_same_opened_object_or_proven_equivalent,
        ),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise ExecutorRuntimeIdentityResolutionError(
                f"runtime control {name} is not proven for {entry.path!r}"
            )


def _verify_numeric_identity(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
) -> None:
    nonnegative_values = (
        ("verification_device", observation.verification_device),
        ("verification_byte_length", observation.verification_byte_length),
        ("handoff_device", observation.handoff_device),
        ("handoff_byte_length", observation.handoff_byte_length),
    )
    positive_values = (
        ("verification_inode", observation.verification_inode),
        ("handoff_inode", observation.handoff_inode),
    )

    for name, value in nonnegative_values:
        if type(value) is not int or value < 0:
            raise ExecutorRuntimeIdentityResolutionError(
                f"runtime identity field {name} is invalid for {entry.path!r}"
            )
    for name, value in positive_values:
        if type(value) is not int or value <= 0:
            raise ExecutorRuntimeIdentityResolutionError(
                f"runtime identity field {name} is invalid for {entry.path!r}"
            )

    if observation.handoff_device != observation.verification_device:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime device identity changed before execution/import for {entry.path!r}"
        )
    if observation.handoff_inode != observation.verification_inode:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime inode identity changed before execution/import for {entry.path!r}"
        )
    if observation.handoff_byte_length != observation.verification_byte_length:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime byte length changed before execution/import for {entry.path!r}"
        )


def _verify_blob_identity(
    entry: ExecutorAllowlistEntry,
    observation: RuntimeExecutorObjectObservation,
) -> None:
    for label, value in (
        ("verification", observation.verification_git_blob_sha),
        ("handoff", observation.handoff_git_blob_sha),
    ):
        if type(value) is not str or _GIT_OBJECT_RE.fullmatch(value) is None:
            raise ExecutorRuntimeIdentityResolutionError(
                f"{label} runtime Git blob SHA is invalid for {entry.path!r}"
            )

    if observation.verification_git_blob_sha != entry.git_blob_sha:
        raise ExecutorRuntimeIdentityResolutionError(
            f"verified runtime Git blob mismatches allowlist for {entry.path!r}"
        )
    if observation.handoff_git_blob_sha != observation.verification_git_blob_sha:
        raise ExecutorRuntimeIdentityResolutionError(
            f"runtime Git blob identity changed before execution/import for {entry.path!r}"
        )
