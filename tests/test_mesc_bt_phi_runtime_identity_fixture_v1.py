"""Fixture-only qualification for the Phi runtime identity evidence primitive."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    parse_phi_remote_code_manifest,
)
from medscale.mesc._bt_phi_runtime_identity_fixture_v1 import (
    PhiRuntimeIdentityManifestError,
    PhiRuntimeIdentityResolutionError,
    RuntimePhiObjectObservation,
    RuntimePhiObjectResolver,
    verify_phi_runtime_identity_evidence,
)

_BLOB_A = "a" * 40
_BLOB_B = "b" * 40
_DIGEST_A = "c" * 64
_DIGEST_B = "d" * 64
_REQUIRED_RESOLVE_FLAGS = frozenset(
    {
        "RESOLVE_BENEATH",
        "RESOLVE_NO_MAGICLINKS",
        "RESOLVE_NO_SYMLINKS",
    }
)
_REQUIRED_OPEN_FLAGS = frozenset({"O_CLOEXEC", "O_NOFOLLOW", "O_RDONLY"})


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


def _manifest() -> PhiRemoteCodeManifest:
    payload = (
        "["
        + ",".join(
            [
                _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
                _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
            ]
        )
        + "]"
    ).encode("ascii")
    return parse_phi_remote_code_manifest(payload)


def _observation(
    entry: PhiRemoteCodeManifestEntry,
    *,
    inode: int,
) -> RuntimePhiObjectObservation:
    return RuntimePhiObjectObservation(
        path=entry.path,
        open_api="openat2",
        descriptor_relative=True,
        resolve_flags=_REQUIRED_RESOLVE_FLAGS,
        open_flags=_REQUIRED_OPEN_FLAGS,
        approved_input_root=True,
        input_root_read_only=True,
        fstat_regular_file=True,
        verification_device=17,
        verification_inode=inode,
        verification_byte_length=entry.byte_length,
        verification_sha256=entry.sha256,
        handoff_device=17,
        handoff_inode=inode,
        handoff_byte_length=entry.byte_length,
        handoff_sha256=entry.sha256,
        handoff_mount_read_only=True,
        identity_checked_immediately_before_import=True,
    )


def test_valid_runtime_identity_evidence_covers_every_manifest_entry() -> None:
    manifest = _manifest()
    observations = {
        entry.path: _observation(entry, inode=100 + index)
        for index, entry in enumerate(manifest.entries, start=1)
    }
    calls: list[str] = []

    def resolve(path: str) -> RuntimePhiObjectObservation:
        calls.append(path)
        return observations[path]

    verify_phi_runtime_identity_evidence(manifest, resolve)

    assert calls == [entry.path for entry in manifest.entries]


def test_forged_manifest_object_is_rejected_before_resolver_call() -> None:
    manifest = _manifest()
    forged = PhiRemoteCodeManifest(
        entries=manifest.entries,
        sha256="0" * 64,
        byte_length=manifest.byte_length,
    )
    called = False

    def resolve(path: str) -> RuntimePhiObjectObservation:
        nonlocal called
        called = True
        raise AssertionError(path)

    with pytest.raises(PhiRuntimeIdentityManifestError, match="canonical bytes"):
        verify_phi_runtime_identity_evidence(forged, resolve)

    assert called is False


def test_manifest_must_be_exact_validated_type() -> None:
    manifest = _manifest()

    with pytest.raises(PhiRuntimeIdentityManifestError, match="parser-validated"):
        verify_phi_runtime_identity_evidence(cast(PhiRemoteCodeManifest, object()), lambda _: None)


def test_resolver_exception_is_wrapped() -> None:
    manifest = _manifest()

    def resolve(path: str) -> RuntimePhiObjectObservation:
        raise RuntimeError(path)

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="failed to resolve"):
        verify_phi_runtime_identity_evidence(manifest, resolve)


def test_resolver_must_return_exact_observation_type() -> None:
    manifest = _manifest()
    resolver = cast(RuntimePhiObjectResolver, lambda _: object())

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="invalid runtime identity evidence"):
        verify_phi_runtime_identity_evidence(manifest, resolver)


def test_path_and_open_api_are_exact() -> None:
    manifest = _manifest()
    entry = manifest.entries[0]
    valid = _observation(entry, inode=101)

    for invalid in (
        replace(valid, path="other.py"),
        replace(valid, open_api="open"),
    ):
        with pytest.raises(PhiRuntimeIdentityResolutionError):
            verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_resolve_flags_must_be_exact_openat2_set() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)

    invalid = replace(
        valid,
        resolve_flags=frozenset({"RESOLVE_BENEATH", "RESOLVE_NO_SYMLINKS"}),
    )
    with pytest.raises(PhiRuntimeIdentityResolutionError, match="resolve flags"):
        verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_open_flags_must_be_exact_required_set() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)

    invalid = replace(valid, open_flags=frozenset({"O_CLOEXEC", "O_RDONLY"}))
    with pytest.raises(PhiRuntimeIdentityResolutionError, match="open flags"):
        verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_runtime_control_booleans_all_must_be_exact_true() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)
    invalid_observations = (
        replace(valid, descriptor_relative=False),
        replace(valid, approved_input_root=False),
        replace(valid, input_root_read_only=False),
        replace(valid, fstat_regular_file=False),
        replace(valid, handoff_mount_read_only=False),
        replace(valid, identity_checked_immediately_before_import=False),
        replace(valid, descriptor_relative=cast(bool, 1)),
    )

    for invalid in invalid_observations:
        with pytest.raises(PhiRuntimeIdentityResolutionError, match="not proven"):
            verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_numeric_identity_rejects_bool_negative_and_zero_inode() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)
    invalid_observations = (
        replace(valid, verification_device=cast(int, True)),
        replace(valid, verification_device=-1),
        replace(valid, verification_inode=0),
        replace(valid, handoff_inode=-1),
    )

    for invalid in invalid_observations:
        with pytest.raises(PhiRuntimeIdentityResolutionError, match="identity field"):
            verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_verified_byte_length_must_match_manifest() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)
    invalid = replace(valid, verification_byte_length=13, handoff_byte_length=13)

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="mismatches manifest"):
        verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_verified_sha256_must_match_manifest() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)
    invalid = replace(valid, verification_sha256="e" * 64, handoff_sha256="e" * 64)

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="mismatches manifest"):
        verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)


def test_handoff_device_and_inode_must_equal_verified_object() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="device identity changed"):
        verify_phi_runtime_identity_evidence(
            manifest,
            lambda _: replace(valid, handoff_device=18),
        )
    with pytest.raises(PhiRuntimeIdentityResolutionError, match="inode identity changed"):
        verify_phi_runtime_identity_evidence(
            manifest,
            lambda _: replace(valid, handoff_inode=102),
        )


def test_handoff_bytes_must_equal_verified_object() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)

    with pytest.raises(PhiRuntimeIdentityResolutionError, match="byte length changed"):
        verify_phi_runtime_identity_evidence(
            manifest,
            lambda _: replace(valid, handoff_byte_length=13),
        )
    with pytest.raises(PhiRuntimeIdentityResolutionError, match="SHA-256 changed"):
        verify_phi_runtime_identity_evidence(
            manifest,
            lambda _: replace(valid, handoff_sha256="e" * 64),
        )


def test_sha256_fields_must_be_lowercase_64_hex() -> None:
    manifest = _manifest()
    valid = _observation(manifest.entries[0], inode=101)

    for invalid in (
        replace(valid, verification_sha256="A" * 64),
        replace(valid, handoff_sha256="g" * 64),
    ):
        with pytest.raises(PhiRuntimeIdentityResolutionError, match="SHA-256"):
            verify_phi_runtime_identity_evidence(manifest, lambda _: invalid)
