"""The single module permitted to resolve the CW-002 workspace store path.

ADR-0039 decision 7 adds a rule that workspace code may only touch the single
workspace store path resolved by one dedicated module. This is that module, and
the CW-002 boundary guard enforces it mechanically: ``sqlite3`` may be imported
only by ``storage.py``, and every ``sqlite3.connect`` call there must take its
path from :func:`resolve_workspace_store_path`.

The root is supplied by the caller as an explicit absolute path. No environment
variable, current directory, user profile or default location is consulted, and
path components are validated as data rather than trusted.
"""

from __future__ import annotations

from uuid import UUID

from medscale_workspace.errors import StorePathError

STORE_FILENAME_SUFFIX = ".workspace.sqlite3"
_POSIX_SEPARATOR = "/"
_WINDOWS_SEPARATOR = "\\"


def _is_absolute(root: str) -> bool:
    if root.startswith("\\\\") or root.startswith("//"):
        return True
    if len(root) >= 2 and root[1] == ":" and root[0].isalpha():
        return True
    return root.startswith("/")


def _admitted_root(store_root: str) -> tuple[str, str]:
    if not isinstance(store_root, str):
        raise StorePathError("store root must be a string")
    root = store_root
    if not root or not root.strip():
        raise StorePathError("store root must be a non-empty absolute path")
    if "\x00" in root:
        raise StorePathError("store root must not contain NUL")
    if any(character.isspace() and character != " " for character in root):
        raise StorePathError("store root must not contain control whitespace")
    has_posix = _POSIX_SEPARATOR in root
    has_windows = _WINDOWS_SEPARATOR in root
    if has_posix and has_windows:
        raise StorePathError("store root must not mix path separators")
    separator = _WINDOWS_SEPARATOR if has_windows else _POSIX_SEPARATOR
    if not _is_absolute(root):
        raise StorePathError("store root must be absolute")
    body = root[2:] if separator == _WINDOWS_SEPARATOR and _is_absolute(root) else root
    for component in body.split(separator):
        if component in {".", ".."}:
            raise StorePathError("store root must not contain traversal components")
    return root, separator


def resolve_workspace_store_path(store_root: str, workspace_id: UUID) -> str:
    """Return the one admitted store path for a workspace inside an explicit root."""

    if not isinstance(workspace_id, UUID):
        raise StorePathError("workspace id must be a UUID value")
    root, separator = _admitted_root(store_root)
    trimmed = root.rstrip(separator)
    filename = f"{workspace_id}{STORE_FILENAME_SUFFIX}"
    resolved = f"{trimmed}{separator}{filename}"
    if resolved.count(separator) < root.count(separator):
        raise StorePathError("resolved store path escaped its root")
    return resolved
