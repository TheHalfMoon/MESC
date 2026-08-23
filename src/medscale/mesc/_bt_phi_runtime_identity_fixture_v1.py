"""Fail-closed fixture validation for Phi runtime object identity evidence.

This module validates only caller-supplied evidence for the descriptor-relative
runtime-object identity requirements in ``FD-MESC-BT-EXEC-1`` Section C.3. It
does not call ``openat2(2)``, open files, traverse a filesystem, import remote
code, execute subprocesses, access a network, access a model, dispatch prompts,
run inference, generate output, rank candidates, select a winner, or train.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)

_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_RESOLVE_FLAGS: Final = frozenset(
    {
        "RESOLVE_BENEATH",
        "RESOLVE_NO_MAGICLINKS",
        "RESOLVE_NO_SYMLINKS",
    }
)
_REQUIRED_OPEN_FLAGS: Final = frozenset({"O_CLOEXEC", "O_NOFOLLOW", "O_RDONLY"})


class PhiRuntimeIdentityError(ValueError):
    """Base class for fail-closed Phi runtime identity evidence violations."""


class PhiRuntimeIdentityManifestError(PhiRuntimeIdentityError):
    """The supplied manifest is not a parser-validated canonical manifest."""


class PhiRuntimeIdentityResolutionError(PhiRuntimeIdentityError):
    """Injected runtime identity evidence is missing, malformed, or inconsistent."""


@dataclass(frozen=True, slots=True)
class RuntimePhiObjectObservation:
    """Injected evidence for one acquired and import-bound Phi code object."""

    path: str
    open_api: str
    descriptor_relative: bool
    resolve_flags: frozenset[str]
    open_flags: frozenset[str]
    approved_input_root: bool
    input_root_read_only: bool
    fstat_regular_file: bool
    verification_device: int
    verification_inode: int
    verification_byte_length: int
    verification_sha256: str
    handoff_device: int
    handoff_inode: int
    handoff_byte_length: int
    handoff_sha256: str
    handoff_mount_read_only: bool
    identity_checked_immediately_before_import: bool


RuntimePhiObjectResolver = Callable[[str], RuntimePhiObjectObservation]


def verify_phi_runtime_identity_evidence(
    manifest: PhiRemoteCodeManifest,
    resolve: RuntimePhiObjectResolver,
) -> None:
    """Verify injected descriptor-relative and same-object identity evidence."""
    _revalidate_manifest(manifest)

    for entry in manifest.entries:
        observation = _resolve_observation(entry, resolve)
        _verify_observation(entry, observation)


def _revalidate_manifest(manifest: PhiRemoteCodeManifest) -> None:
    if type(manifest) is not PhiRemoteCodeManifest:
        raise PhiRuntimeIdentityManifestError("manifest is not parser-validated")

    try:
        canonical = canonical_phi_remote_code_manifest_bytes(manifest.entries)
        reparsed = parse_phi_remote_code_manifest(canonical)
    except Exception as error:
        raise PhiRuntimeIdentityManifestError(
            "manifest object does not contain valid canonical manifest content"
        ) from error

    if reparsed != manifest:
        raise PhiRuntimeIdentityManifestError(
            "manifest object identity does not match its canonical bytes"
        )


def _resolve_observation(
    entry: PhiRemoteCodeManifestEntry,
    resolve: RuntimePhiObjectResolver,
) -> RuntimePhiObjectObservation:
    try:
        observation = resolve(entry.path)
    except Exception as error:
        raise PhiRuntimeIdentityResolutionError(
            f"failed to resolve runtime identity evidence for {entry.path!r}"
        ) from error

    if type(observation) is not RuntimePhiObjectObservation:
        raise PhiRuntimeIdentityResolutionError(
            f"resolver returned invalid runtime identity evidence for {entry.path!r}"
        )
    return observation


def _verify_observation(
    entry: PhiRemoteCodeManifestEntry,
    observation: RuntimePhiObjectObservation,
) -> None:
    _verify_path_and_open_contract(entry, observation)
    _verify_boolean_controls(entry, observation)
    _verify_numeric_identity(entry, observation)
    _verify_digest_identity(entry, observation)


def _verify_path_and_open_contract(
    entry: PhiRemoteCodeManifestEntry,
    observation: RuntimePhiObjectObservation,
) -> None:
    if type(observation.path) is not str or observation.path != entry.path:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime evidence path mismatch for {entry.path!r}"
        )
    if type(observation.open_api) is not str or observation.open_api != "openat2":
        raise PhiRuntimeIdentityResolutionError(
            f"runtime evidence for {entry.path!r} must use openat2"
        )
    if type(observation.resolve_flags) is not frozenset:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime resolve flags are malformed for {entry.path!r}"
        )
    if observation.resolve_flags != _REQUIRED_RESOLVE_FLAGS:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime resolve flags do not match the required set for {entry.path!r}"
        )
    if type(observation.open_flags) is not frozenset:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime open flags are malformed for {entry.path!r}"
        )
    if observation.open_flags != _REQUIRED_OPEN_FLAGS:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime open flags do not match the required set for {entry.path!r}"
        )


def _verify_boolean_controls(
    entry: PhiRemoteCodeManifestEntry,
    observation: RuntimePhiObjectObservation,
) -> None:
    controls = (
        ("descriptor_relative", observation.descriptor_relative),
        ("approved_input_root", observation.approved_input_root),
        ("input_root_read_only", observation.input_root_read_only),
        ("fstat_regular_file", observation.fstat_regular_file),
        ("handoff_mount_read_only", observation.handoff_mount_read_only),
        (
            "identity_checked_immediately_before_import",
            observation.identity_checked_immediately_before_import,
        ),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise PhiRuntimeIdentityResolutionError(
                f"runtime control {name} is not proven for {entry.path!r}"
            )


def _verify_numeric_identity(
    entry: PhiRemoteCodeManifestEntry,
    observation: RuntimePhiObjectObservation,
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
            raise PhiRuntimeIdentityResolutionError(
                f"runtime identity field {name} is invalid for {entry.path!r}"
            )
    for name, value in positive_values:
        if type(value) is not int or value <= 0:
            raise PhiRuntimeIdentityResolutionError(
                f"runtime identity field {name} is invalid for {entry.path!r}"
            )

    if observation.verification_byte_length != entry.byte_length:
        raise PhiRuntimeIdentityResolutionError(
            f"verified runtime byte length mismatches manifest for {entry.path!r}"
        )
    if observation.handoff_device != observation.verification_device:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime device identity changed before import for {entry.path!r}"
        )
    if observation.handoff_inode != observation.verification_inode:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime inode identity changed before import for {entry.path!r}"
        )
    if observation.handoff_byte_length != observation.verification_byte_length:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime byte length changed before import for {entry.path!r}"
        )


def _verify_digest_identity(
    entry: PhiRemoteCodeManifestEntry,
    observation: RuntimePhiObjectObservation,
) -> None:
    if type(observation.verification_sha256) is not str:
        raise PhiRuntimeIdentityResolutionError(
            f"verified runtime SHA-256 is malformed for {entry.path!r}"
        )
    if type(observation.handoff_sha256) is not str:
        raise PhiRuntimeIdentityResolutionError(
            f"handoff runtime SHA-256 is malformed for {entry.path!r}"
        )
    if _SHA256_RE.fullmatch(observation.verification_sha256) is None:
        raise PhiRuntimeIdentityResolutionError(
            f"verified runtime SHA-256 is invalid for {entry.path!r}"
        )
    if _SHA256_RE.fullmatch(observation.handoff_sha256) is None:
        raise PhiRuntimeIdentityResolutionError(
            f"handoff runtime SHA-256 is invalid for {entry.path!r}"
        )
    if observation.verification_sha256 != entry.sha256:
        raise PhiRuntimeIdentityResolutionError(
            f"verified runtime SHA-256 mismatches manifest for {entry.path!r}"
        )
    if observation.handoff_sha256 != observation.verification_sha256:
        raise PhiRuntimeIdentityResolutionError(
            f"runtime SHA-256 changed before import for {entry.path!r}"
        )
