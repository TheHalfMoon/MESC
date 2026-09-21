"""Synthetic-only MedScale Clinical Workspace package.

CW-001 established the fail-closed Workspace boundary and the synthetic fixture
shell. CW-002 adds the governed local protected store: standard-library SQLite with
AES-256-GCM envelope encryption, HKDF-SHA-256 key derivation, an explicit
key-version state machine and no plaintext fallback.
"""

from __future__ import annotations

from medscale_workspace.aead import NONCE_SIZE_BYTES
from medscale_workspace.app import workspace_snapshot
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.errors import WorkspaceStoreError
from medscale_workspace.fixtures import (
    SyntheticEncounter,
    SyntheticPatient,
    synthetic_encounter,
    synthetic_patient,
)
from medscale_workspace.identity import WorkspaceObjectIdentity, WorkspaceObjectType
from medscale_workspace.keyprovider import (
    InMemoryTestKeyProvider,
    KeyProvider,
    KeyProviderCapabilities,
    UnavailablePlatformKeyProvider,
    resolve_platform_key_provider,
)
from medscale_workspace.storage import KeyState, ObjectWrite, WorkspaceStore
from medscale_workspace.store_path import resolve_workspace_store_path

__all__ = [
    "NONCE_SIZE_BYTES",
    "InMemoryTestKeyProvider",
    "KeyProvider",
    "KeyProviderCapabilities",
    "KeyState",
    "ObjectBinding",
    "ObjectWrite",
    "SyntheticEncounter",
    "SyntheticPatient",
    "UnavailablePlatformKeyProvider",
    "WorkspaceObjectIdentity",
    "WorkspaceObjectType",
    "WorkspaceStore",
    "WorkspaceStoreError",
    "resolve_platform_key_provider",
    "resolve_workspace_store_path",
    "synthetic_encounter",
    "synthetic_patient",
    "workspace_snapshot",
]

__version__ = "0.1.0.dev1"
