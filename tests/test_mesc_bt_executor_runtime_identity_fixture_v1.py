from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._bt_executor_allowlist_v1 import (
    ExecutorAllowlist,
    ExecutorAllowlistEntry,
    parse_executor_allowlist,
)
from medscale.mesc._bt_executor_runtime_identity_fixture_v1 import (
    ExecutorRuntimeIdentityAllowlistError,
    ExecutorRuntimeIdentityResolutionError,
    RuntimeExecutorObjectObservation,
    verify_executor_runtime_identity_evidence,
)

_BLOB_SHA = "a" * 40
_EXECUTION_CODE_SHA = "b" * 40
_EXECUTION_CODE_TREE = "c" * 40
_PATH = "src/runner.py"


class _StringSubclass(str):
    pass


class _ObservationSubclass(RuntimeExecutorObjectObservation):
    pass


class _AllowlistSubclass(ExecutorAllowlist):
    pass


def _allowlist() -> ExecutorAllowlist:
    payload = f'[{{"git_blob_sha":"{_BLOB_SHA}","path":"{_PATH}"}}]'.encode()
    return parse_executor_allowlist(payload)


def _observation() -> RuntimeExecutorObjectObservation:
    return RuntimeExecutorObjectObservation(
        path=_PATH,
        open_api="openat2",
        descriptor_relative=True,
        resolve_flags=frozenset(
            {
                "RESOLVE_BENEATH",
                "RESOLVE_NO_MAGICLINKS",
                "RESOLVE_NO_SYMLINKS",
                "RESOLVE_NO_XDEV",
            }
        ),
        open_flags=frozenset({"O_CLOEXEC", "O_NOFOLLOW", "O_RDONLY"}),
        repository_checkout_sha=_EXECUTION_CODE_SHA,
        repository_checkout_tree=_EXECUTION_CODE_TREE,
        checkout_root_read_only=True,
        fstat_regular_file=True,
        git_blob_recomputed_from_exact_opened_bytes=True,
        verification_device=7,
        verification_inode=11,
        verification_byte_length=123,
        verification_git_blob_sha=_BLOB_SHA,
        handoff_device=7,
        handoff_inode=11,
        handoff_byte_length=123,
        handoff_git_blob_sha=_BLOB_SHA,
        handoff_mount_read_only=True,
        handoff_mount_immutable=True,
        identity_checked_immediately_before_execution_or_import=True,
        execution_or_import_uses_same_opened_object_or_proven_equivalent=True,
    )


def _forge_observation_field(
    observation: RuntimeExecutorObjectObservation,
    *,
    field: str,
    value: object,
) -> RuntimeExecutorObjectObservation:
    object.__setattr__(observation, field, value)
    return observation


def _verify(observation: RuntimeExecutorObjectObservation) -> None:
    verify_executor_runtime_identity_evidence(
        _allowlist(),
        execution_code_sha=_EXECUTION_CODE_SHA,
        execution_code_tree=_EXECUTION_CODE_TREE,
        resolve=lambda _path: observation,
    )


def test_accepts_exact_runtime_identity_evidence() -> None:
    _verify(_observation())


def test_rejects_allowlist_subclass() -> None:
    valid = _allowlist()
    forged = _AllowlistSubclass(
        entries=valid.entries,
        sha256=valid.sha256,
        byte_length=valid.byte_length,
    )

    with pytest.raises(ExecutorRuntimeIdentityAllowlistError, match="not parser-validated"):
        verify_executor_runtime_identity_evidence(
            forged,
            execution_code_sha=_EXECUTION_CODE_SHA,
            execution_code_tree=_EXECUTION_CODE_TREE,
            resolve=lambda _path: _observation(),
        )


def test_rejects_non_exact_allowlist_entry_type() -> None:
    valid = _allowlist()
    forged_entry = ExecutorAllowlistEntry(git_blob_sha=_BLOB_SHA, path=_PATH)
    object.__setattr__(valid, "entries", [forged_entry])

    with pytest.raises(ExecutorRuntimeIdentityAllowlistError, match="non-exact field types"):
        verify_executor_runtime_identity_evidence(
            valid,
            execution_code_sha=_EXECUTION_CODE_SHA,
            execution_code_tree=_EXECUTION_CODE_TREE,
            resolve=lambda _path: _observation(),
        )


@pytest.mark.parametrize("field", ["execution_code_sha", "execution_code_tree"])
def test_rejects_invalid_execution_git_identity(field: str) -> None:
    kwargs = {
        "execution_code_sha": _EXECUTION_CODE_SHA,
        "execution_code_tree": _EXECUTION_CODE_TREE,
    }
    kwargs[field] = "INVALID"

    with pytest.raises(
        ExecutorRuntimeIdentityResolutionError,
        match="lowercase 40-hex Git identity",
    ):
        verify_executor_runtime_identity_evidence(
            _allowlist(),
            execution_code_sha=kwargs["execution_code_sha"],
            execution_code_tree=kwargs["execution_code_tree"],
            resolve=lambda _path: _observation(),
        )


def test_rejects_execution_git_identity_string_subclass() -> None:
    with pytest.raises(
        ExecutorRuntimeIdentityResolutionError,
        match="lowercase 40-hex Git identity",
    ):
        verify_executor_runtime_identity_evidence(
            _allowlist(),
            execution_code_sha=cast(str, _StringSubclass(_EXECUTION_CODE_SHA)),
            execution_code_tree=_EXECUTION_CODE_TREE,
            resolve=lambda _path: _observation(),
        )


def test_rejects_resolver_failure() -> None:
    def _raise(_path: str) -> RuntimeExecutorObjectObservation:
        raise RuntimeError("boom")

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="failed to resolve"):
        verify_executor_runtime_identity_evidence(
            _allowlist(),
            execution_code_sha=_EXECUTION_CODE_SHA,
            execution_code_tree=_EXECUTION_CODE_TREE,
            resolve=_raise,
        )


def test_rejects_observation_subclass() -> None:
    valid = _observation()
    forged = _ObservationSubclass(
        **{field: getattr(valid, field) for field in valid.__dataclass_fields__}
    )

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="invalid runtime identity"):
        _verify(forged)


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("path", "src/other.py", "path mismatch"),
        ("open_api", "open", "must use openat2"),
        ("repository_checkout_sha", "d" * 40, "checkout SHA mismatch"),
        ("repository_checkout_tree", "d" * 40, "checkout tree mismatch"),
    ],
)
def test_rejects_identity_binding_mismatch(field: str, value: object, pattern: str) -> None:
    observation = _forge_observation_field(_observation(), field=field, value=value)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match=pattern):
        _verify(observation)


@pytest.mark.parametrize(
    "field",
    [
        "repository_checkout_sha",
        "repository_checkout_tree",
        "path",
        "open_api",
        "verification_git_blob_sha",
        "handoff_git_blob_sha",
    ],
)
def test_rejects_string_subclass_at_scalar_boundaries(field: str) -> None:
    observation = _observation()
    value = _StringSubclass(cast(str, getattr(observation, field)))
    observation = _forge_observation_field(observation, field=field, value=value)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError):
        _verify(observation)


def test_rejects_missing_or_extra_resolve_flags() -> None:
    for flags in (
        frozenset({"RESOLVE_BENEATH", "RESOLVE_NO_MAGICLINKS", "RESOLVE_NO_SYMLINKS"}),
        frozenset(
            {
                "RESOLVE_BENEATH",
                "RESOLVE_NO_MAGICLINKS",
                "RESOLVE_NO_SYMLINKS",
                "RESOLVE_NO_XDEV",
                "EXTRA",
            }
        ),
    ):
        observation = _forge_observation_field(_observation(), field="resolve_flags", value=flags)
        with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="required set"):
            _verify(observation)


def test_rejects_non_exact_resolve_flag_string() -> None:
    flags = frozenset(
        {
            "RESOLVE_BENEATH",
            "RESOLVE_NO_MAGICLINKS",
            "RESOLVE_NO_SYMLINKS",
            _StringSubclass("RESOLVE_NO_XDEV"),
        }
    )
    observation = _forge_observation_field(_observation(), field="resolve_flags", value=flags)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="malformed"):
        _verify(observation)


def test_rejects_wrong_open_flags() -> None:
    observation = _forge_observation_field(
        _observation(),
        field="open_flags",
        value=frozenset({"O_CLOEXEC", "O_RDONLY"}),
    )

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="required set"):
        _verify(observation)


@pytest.mark.parametrize(
    "field",
    [
        "descriptor_relative",
        "checkout_root_read_only",
        "fstat_regular_file",
        "git_blob_recomputed_from_exact_opened_bytes",
        "handoff_mount_read_only",
        "handoff_mount_immutable",
        "identity_checked_immediately_before_execution_or_import",
        "execution_or_import_uses_same_opened_object_or_proven_equivalent",
    ],
)
def test_rejects_unproven_boolean_control(field: str) -> None:
    observation = _forge_observation_field(_observation(), field=field, value=False)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="not proven"):
        _verify(observation)


@pytest.mark.parametrize(
    "field",
    [
        "descriptor_relative",
        "checkout_root_read_only",
        "fstat_regular_file",
        "git_blob_recomputed_from_exact_opened_bytes",
    ],
)
def test_rejects_integer_boolean_substitution(field: str) -> None:
    observation = _forge_observation_field(_observation(), field=field, value=1)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="not proven"):
        _verify(observation)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("verification_device", -1),
        ("verification_inode", 0),
        ("verification_byte_length", -1),
        ("handoff_device", -1),
        ("handoff_inode", 0),
        ("handoff_byte_length", -1),
        ("verification_device", True),
        ("handoff_inode", True),
    ],
)
def test_rejects_invalid_numeric_identity(field: str, value: object) -> None:
    observation = _forge_observation_field(_observation(), field=field, value=value)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match="identity field"):
        _verify(observation)


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    [
        ("handoff_device", 8, "device identity changed"),
        ("handoff_inode", 12, "inode identity changed"),
        ("handoff_byte_length", 124, "byte length changed"),
        ("verification_git_blob_sha", "d" * 40, "mismatches allowlist"),
        ("handoff_git_blob_sha", "d" * 40, "Git blob identity changed"),
    ],
)
def test_rejects_runtime_object_identity_change(field: str, value: object, pattern: str) -> None:
    observation = _forge_observation_field(_observation(), field=field, value=value)

    with pytest.raises(ExecutorRuntimeIdentityResolutionError, match=pattern):
        _verify(observation)
