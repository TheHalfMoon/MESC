"""Fixture-only qualification for the Phi remote-code manifest primitive."""

from __future__ import annotations

import hashlib

import pytest

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestCanonicalizationError,
    PhiRemoteCodeManifestDuplicateMemberError,
    PhiRemoteCodeManifestEntry,
    PhiRemoteCodeManifestJsonError,
    PhiRemoteCodeManifestResolutionError,
    PhiRemoteCodeManifestSchemaError,
    ResolvedPhiRemoteCodeObject,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
    verify_phi_remote_code_git_objects,
)

_BLOB_A = "a" * 40
_BLOB_B = "b" * 40
_DIGEST_A = "c" * 64
_DIGEST_B = "d" * 64


def _entry(
    byte_length: int,
    blob_sha: str,
    path: str,
    sha256: str,
) -> str:
    return (
        f'{{"byte_length":{byte_length},"git_blob_sha":"{blob_sha}",'
        f'"path":"{path}","sha256":"{sha256}"}}'
    )


def _payload(*entries: str) -> bytes:
    return ("[" + ",".join(entries) + "]").encode("ascii")


def _single_entry_payload(
    *,
    byte_length: int = 12,
    blob_sha: str = _BLOB_A,
    path: str = "modeling_phi4mm.py",
    sha256: str = _DIGEST_A,
) -> bytes:
    return _payload(_entry(byte_length, blob_sha, path, sha256))


def test_valid_canonical_manifest_binds_exact_bytes_and_digest() -> None:
    payload = _payload(
        _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
        _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
    )
    manifest = parse_phi_remote_code_manifest(payload)

    assert [entry.path for entry in manifest.entries] == [
        "modeling_phi4mm.py",
        "processing_phi4mm.py",
    ]
    assert manifest.sha256 == hashlib.sha256(payload).hexdigest()
    assert manifest.byte_length == len(payload)
    assert canonical_phi_remote_code_manifest_bytes(manifest.entries) == payload
    assert not payload.endswith(b"\n")


def test_empty_manifest_is_rejected() -> None:
    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="at least one"):
        parse_phi_remote_code_manifest(b"[]")


def test_utf8_bom_is_rejected() -> None:
    with pytest.raises(PhiRemoteCodeManifestJsonError, match="BOM"):
        parse_phi_remote_code_manifest(b"\xef\xbb\xbf[]")


def test_invalid_utf8_is_rejected() -> None:
    with pytest.raises(PhiRemoteCodeManifestJsonError, match="UTF-8"):
        parse_phi_remote_code_manifest(b"[\xff]")


def test_top_level_must_be_array() -> None:
    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="top level"):
        parse_phi_remote_code_manifest(b"{}")


@pytest.mark.parametrize(
    "member",
    ["byte_length", "git_blob_sha", "path", "sha256"],
)
def test_duplicate_members_are_rejected(member: str) -> None:
    values = {
        "byte_length": "12",
        "git_blob_sha": f'"{_BLOB_A}"',
        "path": '"modeling_phi4mm.py"',
        "sha256": f'"{_DIGEST_A}"',
    }
    parts = [
        f'"byte_length":{values["byte_length"]}',
        f'"git_blob_sha":{values["git_blob_sha"]}',
        f'"path":{values["path"]}',
        f'"sha256":{values["sha256"]}',
        f'"{member}":{values[member]}',
    ]
    payload = ("[{" + ",".join(parts) + "}]").encode("ascii")

    with pytest.raises(PhiRemoteCodeManifestDuplicateMemberError, match=member):
        parse_phi_remote_code_manifest(payload)


@pytest.mark.parametrize(
    "payload",
    [
        b"[[]]",
        (f'[{{"byte_length":12,"git_blob_sha":"{_BLOB_A}","path":"modeling_phi4mm.py"}}]').encode(
            "ascii"
        ),
        (
            f'[{{"byte_length":12,"git_blob_sha":"{_BLOB_A}",'
            f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}","extra":"x"}}]'
        ).encode("ascii"),
        (
            f'[{{"byte_length":"12","git_blob_sha":"{_BLOB_A}",'
            f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}"}}]'
        ).encode("ascii"),
    ],
)
def test_closed_entry_schema_is_enforced(payload: bytes) -> None:
    with pytest.raises(PhiRemoteCodeManifestSchemaError):
        parse_phi_remote_code_manifest(payload)


@pytest.mark.parametrize(
    "byte_length_literal",
    ["-1", "true", "1.0", '"12"'],
)
def test_byte_length_must_be_non_negative_json_integer(
    byte_length_literal: str,
) -> None:
    payload = (
        f'[{{"byte_length":{byte_length_literal},"git_blob_sha":"{_BLOB_A}",'
        f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}"}}]'
    ).encode("ascii")

    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="byte_length"):
        parse_phi_remote_code_manifest(payload)


def test_negative_zero_is_rejected_as_noncanonical() -> None:
    payload = (
        f'[{{"byte_length":-0,"git_blob_sha":"{_BLOB_A}",'
        f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}"}}]'
    ).encode("ascii")

    with pytest.raises(PhiRemoteCodeManifestCanonicalizationError):
        parse_phi_remote_code_manifest(payload)


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
        'a"b.py',
    ],
)
def test_path_grammar_is_fail_closed(path: str) -> None:
    escaped = path.replace("\\", "\\\\").replace('"', '\\"')
    payload = _single_entry_payload(path=escaped)

    with pytest.raises(PhiRemoteCodeManifestSchemaError):
        parse_phi_remote_code_manifest(payload)


def test_non_ascii_path_is_fail_closed() -> None:
    payload = (
        f'[{{"byte_length":12,"git_blob_sha":"{_BLOB_A}","path":"möd.py","sha256":"{_DIGEST_A}"}}]'
    ).encode()

    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="ASCII"):
        parse_phi_remote_code_manifest(payload)


@pytest.mark.parametrize(
    "blob_sha",
    ["A" * 40, "a" * 39, "g" * 40, ""],
)
def test_git_blob_sha_must_be_lowercase_40_hex(blob_sha: str) -> None:
    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="Git blob SHA"):
        parse_phi_remote_code_manifest(_single_entry_payload(blob_sha=blob_sha))


@pytest.mark.parametrize(
    "sha256",
    ["A" * 64, "a" * 63, "g" * 64, ""],
)
def test_sha256_must_be_lowercase_64_hex(sha256: str) -> None:
    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="SHA-256"):
        parse_phi_remote_code_manifest(_single_entry_payload(sha256=sha256))


def test_duplicate_decoded_paths_are_rejected() -> None:
    payload = _payload(
        _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
        _entry(34, _BLOB_B, "modeling_phi4mm.py", _DIGEST_B),
    )

    with pytest.raises(PhiRemoteCodeManifestSchemaError, match="duplicate"):
        parse_phi_remote_code_manifest(payload)


def test_entries_must_be_sorted_by_ascii_path() -> None:
    payload = _payload(
        _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
        _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
    )

    with pytest.raises(PhiRemoteCodeManifestCanonicalizationError, match="sorted"):
        parse_phi_remote_code_manifest(payload)


@pytest.mark.parametrize(
    "payload",
    [
        (
            f'[ {{"byte_length":12,"git_blob_sha":"{_BLOB_A}",'
            f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}"}}]'
        ).encode("ascii"),
        (
            f'[{{"git_blob_sha":"{_BLOB_A}","byte_length":12,'
            f'"path":"modeling_phi4mm.py","sha256":"{_DIGEST_A}"}}]'
        ).encode("ascii"),
        _single_entry_payload() + b"\n",
        (
            f'[{{"byte_length":12,"git_blob_sha":"{_BLOB_A}",'
            f'"path":"modeling_phi4mm\\u002epy","sha256":"{_DIGEST_A}"}}]'
        ).encode("ascii"),
    ],
)
def test_noncanonical_serialization_is_rejected(payload: bytes) -> None:
    with pytest.raises(PhiRemoteCodeManifestCanonicalizationError):
        parse_phi_remote_code_manifest(payload)


def test_nonstandard_json_constant_is_rejected() -> None:
    with pytest.raises(PhiRemoteCodeManifestJsonError, match="constant"):
        parse_phi_remote_code_manifest(b"[NaN]")


def test_oversized_integer_json_failure_is_fail_closed() -> None:
    payload = b"[" + b"9" * 5000 + b"]"

    with pytest.raises(PhiRemoteCodeManifestJsonError, match="valid JSON"):
        parse_phi_remote_code_manifest(payload)


def test_deep_json_nesting_is_fail_closed() -> None:
    payload = b"[" * 20000 + b"]" * 20000

    with pytest.raises(PhiRemoteCodeManifestJsonError, match="valid JSON"):
        parse_phi_remote_code_manifest(payload)


def test_forged_manifest_digest_is_rejected_before_resolution() -> None:
    parsed = parse_phi_remote_code_manifest(_single_entry_payload())
    forged = PhiRemoteCodeManifest(
        entries=parsed.entries,
        sha256="0" * 64,
        byte_length=parsed.byte_length,
    )
    resolver_called = False

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        nonlocal resolver_called
        resolver_called = True
        return ResolvedPhiRemoteCodeObject("blob", "100644", _BLOB_A, 12, _DIGEST_A)

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="identity"):
        verify_phi_remote_code_git_objects(forged, resolve)

    assert resolver_called is False


def test_forged_manifest_content_is_rejected_before_resolution() -> None:
    forged = PhiRemoteCodeManifest(
        entries=(
            PhiRemoteCodeManifestEntry(
                byte_length=12,
                git_blob_sha=_BLOB_A,
                path="../modeling_phi4mm.py",
                sha256=_DIGEST_A,
            ),
        ),
        sha256="0" * 64,
        byte_length=1,
    )
    resolver_called = False

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        nonlocal resolver_called
        resolver_called = True
        return ResolvedPhiRemoteCodeObject("blob", "100644", _BLOB_A, 12, _DIGEST_A)

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="valid canonical"):
        verify_phi_remote_code_git_objects(forged, resolve)

    assert resolver_called is False


def test_regular_file_blob_resolution_passes() -> None:
    payload = _payload(
        _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
        _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
    )
    manifest = parse_phi_remote_code_manifest(payload)
    resolved = {
        "modeling_phi4mm.py": ResolvedPhiRemoteCodeObject(
            "blob",
            "100644",
            _BLOB_A,
            12,
            _DIGEST_A,
        ),
        "processing_phi4mm.py": ResolvedPhiRemoteCodeObject(
            "blob",
            "100755",
            _BLOB_B,
            34,
            _DIGEST_B,
        ),
    }

    verify_phi_remote_code_git_objects(manifest, resolved.__getitem__)


@pytest.mark.parametrize(
    "mode",
    ["120000", "160000", "040000", "100600"],
)
def test_non_regular_or_unapproved_modes_are_blocked(mode: str) -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        return ResolvedPhiRemoteCodeObject(
            "blob",
            mode,
            _BLOB_A,
            12,
            _DIGEST_A,
        )

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="prohibited mode"):
        verify_phi_remote_code_git_objects(manifest, resolve)


def test_non_blob_object_is_blocked() -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        return ResolvedPhiRemoteCodeObject(
            "tree",
            "040000",
            _BLOB_A,
            12,
            _DIGEST_A,
        )

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="must resolve"):
        verify_phi_remote_code_git_objects(manifest, resolve)


@pytest.mark.parametrize(
    ("field", "resolved"),
    [
        (
            "Git blob mismatch",
            ResolvedPhiRemoteCodeObject(
                "blob",
                "100644",
                _BLOB_B,
                12,
                _DIGEST_A,
            ),
        ),
        (
            "byte-length mismatch",
            ResolvedPhiRemoteCodeObject(
                "blob",
                "100644",
                _BLOB_A,
                13,
                _DIGEST_A,
            ),
        ),
        (
            "SHA-256 mismatch",
            ResolvedPhiRemoteCodeObject(
                "blob",
                "100644",
                _BLOB_A,
                12,
                _DIGEST_B,
            ),
        ),
    ],
)
def test_exact_object_identity_mismatches_are_blocked(
    field: str,
    resolved: ResolvedPhiRemoteCodeObject,
) -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        return resolved

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match=field):
        verify_phi_remote_code_git_objects(manifest, resolve)


@pytest.mark.parametrize(
    "resolved",
    [
        ResolvedPhiRemoteCodeObject(
            1,  # type: ignore[arg-type]
            "100644",
            _BLOB_A,
            12,
            _DIGEST_A,
        ),
        ResolvedPhiRemoteCodeObject(
            "blob",
            100644,  # type: ignore[arg-type]
            _BLOB_A,
            12,
            _DIGEST_A,
        ),
        ResolvedPhiRemoteCodeObject(
            "blob",
            "100644",
            1,  # type: ignore[arg-type]
            12,
            _DIGEST_A,
        ),
        ResolvedPhiRemoteCodeObject(
            "blob",
            "100644",
            _BLOB_A,
            12,
            1,  # type: ignore[arg-type]
        ),
    ],
)
def test_invalid_resolved_metadata_types_are_fail_closed(
    resolved: ResolvedPhiRemoteCodeObject,
) -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        return resolved

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="metadata"):
        verify_phi_remote_code_git_objects(manifest, resolve)


def test_resolver_failure_is_fail_closed() -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        raise KeyError("missing")

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="failed to resolve"):
        verify_phi_remote_code_git_objects(manifest, resolve)


def test_invalid_resolver_result_is_fail_closed() -> None:
    manifest = parse_phi_remote_code_manifest(_single_entry_payload())

    def resolve(_: str) -> ResolvedPhiRemoteCodeObject:
        return "not-an-object"  # type: ignore[return-value]

    with pytest.raises(PhiRemoteCodeManifestResolutionError, match="invalid object"):
        verify_phi_remote_code_git_objects(manifest, resolve)
