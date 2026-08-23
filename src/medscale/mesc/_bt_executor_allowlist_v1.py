"""Fail-closed Backbone Tournament executor allowlist parsing.

This module implements only the immutable executor and harness allowlist
primitive required by ``FD-MESC-BT-EXEC-1`` Section D. It performs no model
access, retrieval, prompt dispatch, inference, generation, ranking, winner
selection, network access, subprocess execution, or filesystem mutation.
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
_ALLOWED_REGULAR_FILE_MODES: Final = frozenset({"100644", "100755"})
_REQUIRED_ENTRY_KEYS: Final = frozenset({"git_blob_sha", "path"})
_UTF8_BOM: Final = b"\xef\xbb\xbf"


class ExecutorAllowlistError(ValueError):
    """Base class for fail-closed executor allowlist violations."""


class ExecutorAllowlistJsonError(ExecutorAllowlistError):
    """The supplied bytes are not duplicate-safe UTF-8 JSON."""


class ExecutorAllowlistDuplicateMemberError(ExecutorAllowlistJsonError):
    """A JSON object contains a duplicate member name."""


class ExecutorAllowlistSchemaError(ExecutorAllowlistError):
    """The parsed value violates the closed allowlist schema."""


class ExecutorAllowlistCanonicalizationError(ExecutorAllowlistError):
    """The supplied bytes are not the exact canonical bytes."""


class ExecutorAllowlistResolutionError(ExecutorAllowlistError):
    """An allowlisted path does not resolve to its required Git blob."""


@dataclass(frozen=True, slots=True)
class ExecutorAllowlistEntry:
    """One exact path and its expected Git blob identity."""

    git_blob_sha: str
    path: str


@dataclass(frozen=True, slots=True)
class ExecutorAllowlist:
    """A validated canonical allowlist and exact-byte digest."""

    entries: tuple[ExecutorAllowlistEntry, ...]
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class ResolvedExecutorObject:
    """Git metadata returned by a separately reviewed resolver."""

    object_type: str
    mode: str
    git_blob_sha: str


ExecutorObjectResolver = Callable[[str], ResolvedExecutorObject]


def parse_executor_allowlist(payload: bytes) -> ExecutorAllowlist:
    """Parse exact canonical ``EXECUTOR_PATHS_AND_BLOB_SHAS`` bytes."""
    if type(payload) is not bytes:
        raise ExecutorAllowlistJsonError("payload must be exact bytes")
    if payload.startswith(_UTF8_BOM):
        raise ExecutorAllowlistJsonError("UTF-8 BOM is prohibited")

    parsed = _load_duplicate_safe_json(payload)
    if not isinstance(parsed, list):
        raise ExecutorAllowlistSchemaError("top level must be a JSON array")

    raw_entries = cast(list[object], parsed)
    entries = _validate_entries(raw_entries)
    canonical = canonical_executor_allowlist_bytes(entries)
    if payload != canonical:
        raise ExecutorAllowlistCanonicalizationError(
            "payload is not the exact canonical serialization"
        )

    return ExecutorAllowlist(
        entries=entries,
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_length=len(payload),
    )


def canonical_executor_allowlist_bytes(
    entries: tuple[ExecutorAllowlistEntry, ...],
) -> bytes:
    """Serialize validated entries without a terminal newline."""
    document = [{"git_blob_sha": entry.git_blob_sha, "path": entry.path} for entry in entries]
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
        raise ExecutorAllowlistCanonicalizationError(
            "allowlist cannot be serialized as canonical ASCII JSON"
        ) from error


def verify_executor_allowlist_objects(
    allowlist: ExecutorAllowlist,
    resolve: ExecutorObjectResolver,
) -> None:
    """Verify each entry against exact-commit Git object metadata."""
    if not isinstance(allowlist, ExecutorAllowlist):
        raise ExecutorAllowlistResolutionError("allowlist is not validated")

    for entry in allowlist.entries:
        resolved = _resolve_entry(entry, resolve)
        _verify_resolved_entry(entry, resolved)


def _validate_entries(
    raw_entries: list[object],
) -> tuple[ExecutorAllowlistEntry, ...]:
    entries: list[ExecutorAllowlistEntry] = []
    seen_paths: set[str] = set()

    for index, raw_entry in enumerate(raw_entries):
        entry = _validate_entry(raw_entry, index=index)
        if entry.path in seen_paths:
            raise ExecutorAllowlistSchemaError(f"duplicate executor path: {entry.path!r}")
        seen_paths.add(entry.path)
        entries.append(entry)

    paths = [entry.path for entry in entries]
    expected = sorted(paths, key=lambda value: value.encode("ascii"))
    if paths != expected:
        raise ExecutorAllowlistCanonicalizationError(
            "entries are not sorted by decoded path ASCII bytes"
        )
    return tuple(entries)


def _resolve_entry(
    entry: ExecutorAllowlistEntry,
    resolve: ExecutorObjectResolver,
) -> ResolvedExecutorObject:
    try:
        resolved = resolve(entry.path)
    except Exception as error:
        raise ExecutorAllowlistResolutionError(
            f"failed to resolve executor path {entry.path!r}"
        ) from error

    if not isinstance(resolved, ResolvedExecutorObject):
        raise ExecutorAllowlistResolutionError(
            f"resolver returned an invalid object for {entry.path!r}"
        )
    return resolved


def _verify_resolved_entry(
    entry: ExecutorAllowlistEntry,
    resolved: ResolvedExecutorObject,
) -> None:
    if resolved.object_type != "blob":
        raise ExecutorAllowlistResolutionError(
            f"executor path {entry.path!r} must resolve to a blob"
        )
    if resolved.mode not in _ALLOWED_REGULAR_FILE_MODES:
        raise ExecutorAllowlistResolutionError(
            f"executor path {entry.path!r} has prohibited mode {resolved.mode!r}"
        )
    if _GIT_BLOB_RE.fullmatch(resolved.git_blob_sha) is None:
        raise ExecutorAllowlistResolutionError(
            f"resolver returned an invalid Git blob SHA for {entry.path!r}"
        )
    if resolved.git_blob_sha != entry.git_blob_sha:
        raise ExecutorAllowlistResolutionError(
            f"Git blob mismatch for executor path {entry.path!r}"
        )


def _load_duplicate_safe_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExecutorAllowlistJsonError("payload must be valid UTF-8") from error

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_from_unique_pairs,
            parse_constant=_reject_json_constant,
        )
    except ExecutorAllowlistJsonError:
        raise
    except json.JSONDecodeError as error:
        raise ExecutorAllowlistJsonError("payload is not valid JSON") from error


def _object_from_unique_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ExecutorAllowlistDuplicateMemberError(f"duplicate JSON member: {key!r}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> Never:
    raise ExecutorAllowlistJsonError(f"non-standard JSON constant is prohibited: {value}")


def _validate_entry(
    raw_entry: object,
    *,
    index: int,
) -> ExecutorAllowlistEntry:
    if not isinstance(raw_entry, dict):
        raise ExecutorAllowlistSchemaError(f"allowlist entry {index} must be a JSON object")
    entry = cast(dict[str, object], raw_entry)

    if frozenset(entry) != _REQUIRED_ENTRY_KEYS:
        raise ExecutorAllowlistSchemaError(
            f"allowlist entry {index} must contain git_blob_sha and path"
        )

    raw_path = entry["path"]
    raw_blob = entry["git_blob_sha"]
    if type(raw_path) is not str or type(raw_blob) is not str:
        raise ExecutorAllowlistSchemaError(f"allowlist entry {index} values must be JSON strings")

    try:
        raw_path.encode("ascii")
        raw_blob.encode("ascii")
    except UnicodeEncodeError as error:
        raise ExecutorAllowlistSchemaError(
            f"allowlist entry {index} values must be ASCII"
        ) from error

    if _PATH_RE.fullmatch(raw_path) is None:
        raise ExecutorAllowlistSchemaError(f"allowlist entry {index} has invalid path grammar")
    if any(component in {".", ".."} for component in raw_path.split("/")):
        raise ExecutorAllowlistSchemaError(f"allowlist entry {index} contains a dot path component")
    if _GIT_BLOB_RE.fullmatch(raw_blob) is None:
        raise ExecutorAllowlistSchemaError(f"allowlist entry {index} has invalid Git blob SHA")

    return ExecutorAllowlistEntry(
        git_blob_sha=raw_blob,
        path=raw_path,
    )
