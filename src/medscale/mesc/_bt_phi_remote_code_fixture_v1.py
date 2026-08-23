"""Fail-closed fixture validation for the Phi remote-code manifest.

This module implements only the canonical ``PHI_REMOTE_CODE_MANIFEST`` parser
and injected exact-object verification required by ``FD-MESC-BT-EXEC-1``
Section C.3. It performs no repository fetch, filesystem traversal, remote-code
import, subprocess execution, network access, model access, prompt dispatch,
inference, generation, ranking, winner selection, or training.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Never, cast

_PATH_RE: Final = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
_GIT_BLOB_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_REGULAR_FILE_MODES: Final = frozenset({"100644", "100755"})
_REQUIRED_ENTRY_KEYS: Final = frozenset({"byte_length", "git_blob_sha", "path", "sha256"})
_UTF8_BOM: Final = b"\xef\xbb\xbf"


class PhiRemoteCodeManifestError(ValueError):
    """Base class for fail-closed Phi remote-code manifest violations."""


class PhiRemoteCodeManifestJsonError(PhiRemoteCodeManifestError):
    """The supplied bytes are not duplicate-safe UTF-8 JSON."""


class PhiRemoteCodeManifestDuplicateMemberError(PhiRemoteCodeManifestJsonError):
    """A JSON object contains a duplicate member name."""


class PhiRemoteCodeManifestSchemaError(PhiRemoteCodeManifestError):
    """The parsed value violates the closed manifest schema."""


class PhiRemoteCodeManifestCanonicalizationError(PhiRemoteCodeManifestError):
    """The supplied bytes are not the exact canonical manifest bytes."""


class PhiRemoteCodeManifestResolutionError(PhiRemoteCodeManifestError):
    """A manifest path does not resolve to the required immutable Git object."""


@dataclass(frozen=True, slots=True)
class PhiRemoteCodeManifestEntry:
    """One exact Phi remote-code file identity."""

    byte_length: int
    git_blob_sha: str
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PhiRemoteCodeManifest:
    """A validated canonical Phi remote-code manifest."""

    entries: tuple[PhiRemoteCodeManifestEntry, ...]
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class ResolvedPhiRemoteCodeObject:
    """Injected exact Git/file facts from a separately reviewed resolver."""

    object_type: str
    mode: str
    git_blob_sha: str
    byte_length: int
    sha256: str


PhiRemoteCodeObjectResolver = Callable[[str], ResolvedPhiRemoteCodeObject]


def parse_phi_remote_code_manifest(payload: bytes) -> PhiRemoteCodeManifest:
    """Parse exact canonical ``PHI_REMOTE_CODE_MANIFEST`` bytes."""
    if type(payload) is not bytes:
        raise PhiRemoteCodeManifestJsonError("payload must be exact bytes")
    if payload.startswith(_UTF8_BOM):
        raise PhiRemoteCodeManifestJsonError("UTF-8 BOM is prohibited")

    parsed = _load_duplicate_safe_json(payload)
    if not isinstance(parsed, list):
        raise PhiRemoteCodeManifestSchemaError("top level must be a JSON array")

    raw_entries = cast(list[object], parsed)
    if not raw_entries:
        raise PhiRemoteCodeManifestSchemaError("manifest must contain at least one entry")
    entries = _validate_entries(raw_entries)
    canonical = canonical_phi_remote_code_manifest_bytes(entries)
    if payload != canonical:
        raise PhiRemoteCodeManifestCanonicalizationError(
            "payload is not the exact canonical serialization"
        )

    return PhiRemoteCodeManifest(
        entries=entries,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
    )


def canonical_phi_remote_code_manifest_bytes(
    entries: tuple[PhiRemoteCodeManifestEntry, ...],
) -> bytes:
    """Serialize validated manifest entries without a terminal newline."""
    document = [
        {
            "byte_length": entry.byte_length,
            "git_blob_sha": entry.git_blob_sha,
            "path": entry.path,
            "sha256": entry.sha256,
        }
        for entry in entries
    ]
    try:
        text = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("ascii")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise PhiRemoteCodeManifestCanonicalizationError(
            "manifest cannot be serialized as canonical ASCII JSON"
        ) from error


def verify_phi_remote_code_git_objects(
    manifest: PhiRemoteCodeManifest,
    resolve: PhiRemoteCodeObjectResolver,
) -> None:
    """Verify manifest entries against injected pinned-revision Git/file facts."""
    if not isinstance(manifest, PhiRemoteCodeManifest):
        raise PhiRemoteCodeManifestResolutionError("manifest is not validated")

    for entry in manifest.entries:
        resolved = _resolve_entry(entry, resolve)
        _verify_resolved_entry(entry, resolved)


def _validate_entries(
    raw_entries: list[object],
) -> tuple[PhiRemoteCodeManifestEntry, ...]:
    entries: list[PhiRemoteCodeManifestEntry] = []
    seen_paths: set[str] = set()

    for index, raw_entry in enumerate(raw_entries):
        entry = _validate_entry(raw_entry, index=index)
        if entry.path in seen_paths:
            raise PhiRemoteCodeManifestSchemaError(
                f"duplicate Phi remote-code path: {entry.path!r}"
            )
        seen_paths.add(entry.path)
        entries.append(entry)

    paths = [entry.path for entry in entries]
    expected = sorted(paths, key=lambda value: value.encode("ascii"))
    if paths != expected:
        raise PhiRemoteCodeManifestCanonicalizationError(
            "entries are not sorted by decoded path ASCII bytes"
        )
    return tuple(entries)


def _validate_entry(
    raw_entry: object,
    *,
    index: int,
) -> PhiRemoteCodeManifestEntry:
    if not isinstance(raw_entry, dict):
        raise PhiRemoteCodeManifestSchemaError(f"manifest entry {index} must be a JSON object")
    entry = cast(dict[str, object], raw_entry)

    if frozenset(entry) != _REQUIRED_ENTRY_KEYS:
        raise PhiRemoteCodeManifestSchemaError(
            f"manifest entry {index} must contain byte_length, git_blob_sha, path, and sha256"
        )

    raw_byte_length = entry["byte_length"]
    raw_blob = entry["git_blob_sha"]
    raw_path = entry["path"]
    raw_sha256 = entry["sha256"]

    if type(raw_byte_length) is not int or raw_byte_length < 0:
        raise PhiRemoteCodeManifestSchemaError(
            f"manifest entry {index} byte_length must be a JSON integer >= 0"
        )
    if type(raw_blob) is not str or type(raw_path) is not str or type(raw_sha256) is not str:
        raise PhiRemoteCodeManifestSchemaError(
            f"manifest entry {index} identity values must be JSON strings"
        )

    try:
        raw_blob.encode("ascii")
        raw_path.encode("ascii")
        raw_sha256.encode("ascii")
    except UnicodeEncodeError as error:
        raise PhiRemoteCodeManifestSchemaError(
            f"manifest entry {index} identity values must be ASCII"
        ) from error

    if _PATH_RE.fullmatch(raw_path) is None:
        raise PhiRemoteCodeManifestSchemaError(f"manifest entry {index} has invalid path grammar")
    if any(component in {".", ".."} for component in raw_path.split("/")):
        raise PhiRemoteCodeManifestSchemaError(
            f"manifest entry {index} contains a dot path component"
        )
    if _GIT_BLOB_RE.fullmatch(raw_blob) is None:
        raise PhiRemoteCodeManifestSchemaError(f"manifest entry {index} has invalid Git blob SHA")
    if _SHA256_RE.fullmatch(raw_sha256) is None:
        raise PhiRemoteCodeManifestSchemaError(f"manifest entry {index} has invalid SHA-256")

    return PhiRemoteCodeManifestEntry(
        byte_length=raw_byte_length,
        git_blob_sha=raw_blob,
        path=raw_path,
        sha256=raw_sha256,
    )


def _resolve_entry(
    entry: PhiRemoteCodeManifestEntry,
    resolve: PhiRemoteCodeObjectResolver,
) -> ResolvedPhiRemoteCodeObject:
    try:
        resolved = resolve(entry.path)
    except Exception as error:
        raise PhiRemoteCodeManifestResolutionError(
            f"failed to resolve Phi remote-code path {entry.path!r}"
        ) from error

    if not isinstance(resolved, ResolvedPhiRemoteCodeObject):
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned an invalid object for {entry.path!r}"
        )
    return resolved


def _verify_resolved_entry(
    entry: PhiRemoteCodeManifestEntry,
    resolved: ResolvedPhiRemoteCodeObject,
) -> None:
    if type(resolved.object_type) is not str or type(resolved.mode) is not str:
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned invalid object metadata for {entry.path!r}"
        )
    if type(resolved.git_blob_sha) is not str or type(resolved.sha256) is not str:
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned invalid identity metadata for {entry.path!r}"
        )
    if resolved.object_type != "blob":
        raise PhiRemoteCodeManifestResolutionError(
            f"Phi remote-code path {entry.path!r} must resolve to a blob"
        )
    if resolved.mode not in _ALLOWED_REGULAR_FILE_MODES:
        raise PhiRemoteCodeManifestResolutionError(
            f"Phi remote-code path {entry.path!r} has prohibited mode {resolved.mode!r}"
        )
    if _GIT_BLOB_RE.fullmatch(resolved.git_blob_sha) is None:
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned an invalid Git blob SHA for {entry.path!r}"
        )
    if type(resolved.byte_length) is not int or resolved.byte_length < 0:
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned an invalid byte length for {entry.path!r}"
        )
    if _SHA256_RE.fullmatch(resolved.sha256) is None:
        raise PhiRemoteCodeManifestResolutionError(
            f"resolver returned an invalid SHA-256 for {entry.path!r}"
        )
    if resolved.git_blob_sha != entry.git_blob_sha:
        raise PhiRemoteCodeManifestResolutionError(
            f"Git blob mismatch for Phi remote-code path {entry.path!r}"
        )
    if resolved.byte_length != entry.byte_length:
        raise PhiRemoteCodeManifestResolutionError(
            f"byte-length mismatch for Phi remote-code path {entry.path!r}"
        )
    if resolved.sha256 != entry.sha256:
        raise PhiRemoteCodeManifestResolutionError(
            f"SHA-256 mismatch for Phi remote-code path {entry.path!r}"
        )


def _load_duplicate_safe_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PhiRemoteCodeManifestJsonError("payload must be valid UTF-8") from error

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_from_unique_pairs,
            parse_constant=_reject_json_constant,
        )
    except PhiRemoteCodeManifestJsonError:
        raise
    except json.JSONDecodeError as error:
        raise PhiRemoteCodeManifestJsonError("payload is not valid JSON") from error


def _object_from_unique_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise PhiRemoteCodeManifestDuplicateMemberError(f"duplicate JSON member: {key!r}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> Never:
    raise PhiRemoteCodeManifestJsonError(f"non-standard JSON constant is prohibited: {value}")
