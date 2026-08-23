"""Fixture-only qualification for the executor allowlist primitive."""

from __future__ import annotations

import hashlib

import pytest

from medscale.mesc._bt_executor_allowlist_v1 import (
    ExecutorAllowlistCanonicalizationError,
    ExecutorAllowlistDuplicateMemberError,
    ExecutorAllowlistJsonError,
    ExecutorAllowlistResolutionError,
    ExecutorAllowlistSchemaError,
    ResolvedExecutorObject,
    canonical_executor_allowlist_bytes,
    parse_executor_allowlist,
    verify_executor_allowlist_objects,
)

_SHA_A = "a" * 40
_SHA_B = "b" * 40


def _entry(blob_sha: str, path: str) -> str:
    return f'{{"git_blob_sha":"{blob_sha}","path":"{path}"}}'


def _payload(*entries: str) -> bytes:
    return ("[" + ",".join(entries) + "]").encode("ascii")


def _single_entry_payload(
    blob_sha: str = _SHA_A,
    path: str = "a.py",
) -> bytes:
    return _payload(_entry(blob_sha, path))


def test_valid_canonical_allowlist_binds_exact_bytes_and_digest() -> None:
    payload = _payload(
        _entry(_SHA_A, "scripts/runner.py"),
        _entry(_SHA_B, "src/medscale/mesc/harness.py"),
    )
    allowlist = parse_executor_allowlist(payload)

    assert [entry.path for entry in allowlist.entries] == [
        "scripts/runner.py",
        "src/medscale/mesc/harness.py",
    ]
    assert allowlist.sha256 == hashlib.sha256(payload).hexdigest()
    assert allowlist.byte_length == len(payload)
    assert canonical_executor_allowlist_bytes(allowlist.entries) == payload
    assert not payload.endswith(b"\n")


def test_utf8_bom_is_rejected() -> None:
    with pytest.raises(ExecutorAllowlistJsonError, match="BOM"):
        parse_executor_allowlist(b"\xef\xbb\xbf[]")


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(ExecutorAllowlistJsonError, match="UTF-8"):
        parse_executor_allowlist(b"[\xff]")


def test_top_level_must_be_array() -> None:
    with pytest.raises(ExecutorAllowlistSchemaError, match="top level"):
        parse_executor_allowlist(b"{}")


def test_duplicate_path_member_is_rejected() -> None:
    duplicate = f'{{"git_blob_sha":"{_SHA_A}","path":"a.py","path":"b.py"}}'
    with pytest.raises(ExecutorAllowlistDuplicateMemberError, match="path"):
        parse_executor_allowlist(_payload(duplicate))


def test_duplicate_git_blob_member_is_rejected() -> None:
    duplicate = f'{{"git_blob_sha":"{_SHA_A}","git_blob_sha":"{_SHA_B}","path":"a.py"}}'
    with pytest.raises(
        ExecutorAllowlistDuplicateMemberError,
        match="git_blob_sha",
    ):
        parse_executor_allowlist(_payload(duplicate))


@pytest.mark.parametrize(
    "payload",
    [
        b"[[]]",
        _payload(f'{{"git_blob_sha":"{_SHA_A}"}}'),
        _payload(f'{{"git_blob_sha":"{_SHA_A}","path":"a.py","extra":"x"}}'),
        _payload(f'{{"git_blob_sha":"{_SHA_A}","path":1}}'),
        b'[{"git_blob_sha":1,"path":"a.py"}]',
    ],
)
def test_closed_entry_schema_is_enforced(payload: bytes) -> None:
    with pytest.raises(ExecutorAllowlistSchemaError):
        parse_executor_allowlist(payload)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute.py",
        "a//b.py",
        ".",
        "..",
        "a/./b.py",
        "a/../b.py",
        "a\\b.py",
    ],
)
def test_path_grammar_is_fail_closed(path: str) -> None:
    escaped = path.replace("\\", "\\\\")
    with pytest.raises(ExecutorAllowlistSchemaError):
        parse_executor_allowlist(_single_entry_payload(path=escaped))


def test_non_ascii_path_is_fail_closed() -> None:
    payload = f'[{{"git_blob_sha":"{_SHA_A}","path":"ümlaut.py"}}]'.encode()
    with pytest.raises(ExecutorAllowlistSchemaError, match="ASCII"):
        parse_executor_allowlist(payload)


@pytest.mark.parametrize(
    "blob_sha",
    ["A" * 40, "a" * 39, "g" * 40, ""],
)
def test_git_blob_sha_must_be_lowercase_40_hex(blob_sha: str) -> None:
    with pytest.raises(ExecutorAllowlistSchemaError, match="Git blob SHA"):
        parse_executor_allowlist(_single_entry_payload(blob_sha=blob_sha))


def test_duplicate_decoded_paths_are_rejected() -> None:
    payload = _payload(
        _entry(_SHA_A, "a.py"),
        _entry(_SHA_B, "a.py"),
    )
    with pytest.raises(ExecutorAllowlistSchemaError, match="duplicate executor path"):
        parse_executor_allowlist(payload)


def test_entries_must_be_sorted_by_ascii_path() -> None:
    payload = _payload(
        _entry(_SHA_B, "b.py"),
        _entry(_SHA_A, "a.py"),
    )
    with pytest.raises(ExecutorAllowlistCanonicalizationError, match="sorted"):
        parse_executor_allowlist(payload)


@pytest.mark.parametrize(
    "payload",
    [
        f'[ {{"git_blob_sha":"{_SHA_A}","path":"a.py"}}]'.encode("ascii"),
        f'[{{"path":"a.py","git_blob_sha":"{_SHA_A}"}}]'.encode("ascii"),
        f'[{{"git_blob_sha":"{_SHA_A}","path":"a.py"}}]\n'.encode("ascii"),
        f'[{{"git_blob_sha":"{_SHA_A}","path":"a\\u002epy"}}]'.encode("ascii"),
    ],
)
def test_noncanonical_serialization_is_rejected(payload: bytes) -> None:
    with pytest.raises(ExecutorAllowlistCanonicalizationError):
        parse_executor_allowlist(payload)


def test_nonstandard_json_constant_is_rejected() -> None:
    with pytest.raises(ExecutorAllowlistJsonError, match="constant"):
        parse_executor_allowlist(b"[NaN]")


def test_regular_file_blob_resolution_passes() -> None:
    payload = _payload(
        _entry(_SHA_A, "scripts/runner.py"),
        _entry(_SHA_B, "src/medscale/mesc/harness.py"),
    )
    allowlist = parse_executor_allowlist(payload)
    resolved = {
        "scripts/runner.py": ResolvedExecutorObject("blob", "100755", _SHA_A),
        "src/medscale/mesc/harness.py": ResolvedExecutorObject(
            "blob",
            "100644",
            _SHA_B,
        ),
    }
    verify_executor_allowlist_objects(allowlist, resolved.__getitem__)


@pytest.mark.parametrize(
    "mode",
    ["120000", "160000", "040000", "100600"],
)
def test_non_regular_or_unapproved_modes_are_blocked(mode: str) -> None:
    allowlist = parse_executor_allowlist(_single_entry_payload())

    def resolve(_: str) -> ResolvedExecutorObject:
        return ResolvedExecutorObject("blob", mode, _SHA_A)

    with pytest.raises(ExecutorAllowlistResolutionError, match="prohibited mode"):
        verify_executor_allowlist_objects(allowlist, resolve)


def test_non_blob_object_is_blocked() -> None:
    allowlist = parse_executor_allowlist(_single_entry_payload())

    def resolve(_: str) -> ResolvedExecutorObject:
        return ResolvedExecutorObject("tree", "040000", _SHA_A)

    with pytest.raises(ExecutorAllowlistResolutionError, match="must resolve"):
        verify_executor_allowlist_objects(allowlist, resolve)


def test_blob_identity_mismatch_is_blocked() -> None:
    allowlist = parse_executor_allowlist(_single_entry_payload())

    def resolve(_: str) -> ResolvedExecutorObject:
        return ResolvedExecutorObject("blob", "100644", _SHA_B)

    with pytest.raises(ExecutorAllowlistResolutionError, match="Git blob mismatch"):
        verify_executor_allowlist_objects(allowlist, resolve)


def test_resolver_failure_is_fail_closed() -> None:
    allowlist = parse_executor_allowlist(_single_entry_payload())

    def resolve(_: str) -> ResolvedExecutorObject:
        raise KeyError("missing")

    with pytest.raises(ExecutorAllowlistResolutionError, match="failed to resolve"):
        verify_executor_allowlist_objects(allowlist, resolve)
