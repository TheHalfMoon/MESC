"""Typed fail-closed errors for CW-002 protected local storage.

Every CW-002 failure is a distinct class so callers never have to parse messages to
decide what happened, and so a failure can never be silently reinterpreted as a
success or downgraded into a plaintext fallback.
"""

from __future__ import annotations


class WorkspaceStoreError(Exception):
    """Base class for every CW-002 storage, key, envelope and version failure."""


class StorePathError(WorkspaceStoreError):
    """The workspace store path is not a single admitted file path."""


class ObjectBindingError(WorkspaceStoreError):
    """An object binding is malformed or not immutable enough to bind as AEAD data."""


class KeyProviderUnavailableError(WorkspaceStoreError):
    """Protected key storage is unavailable; CW-002 has no plaintext fallback."""


class KeyMaterialUnavailableError(WorkspaceStoreError):
    """The requested key version cannot be produced by the active key provider."""


class KeyStateError(WorkspaceStoreError):
    """A key version was used in a state the CW-002 key state machine forbids."""


class KeyRotationError(WorkspaceStoreError):
    """A key-rotation transition violated its preconditions."""


class EnvelopeFormatError(WorkspaceStoreError):
    """The envelope is malformed or uses an unsupported encryption format version."""


class EnvelopeAuthenticationError(WorkspaceStoreError):
    """AEAD authentication failed: the ciphertext or its binding was altered."""


class StoreVersionError(WorkspaceStoreError):
    """Recorded store versions are absent, unreadable, or unsupported here."""


class StoreIntegrityError(WorkspaceStoreError):
    """A declared store invariant is violated (key state, metadata, pragmas)."""


class WorkspaceIsolationError(WorkspaceStoreError):
    """An operation crossed the workspace boundary and was refused."""


class ObjectNotFoundError(WorkspaceStoreError):
    """The requested object revision is not present in this workspace store."""


class StoreConflictError(WorkspaceStoreError):
    """An immutable object revision already exists and cannot be overwritten."""
