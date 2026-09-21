"""Synthetic-only MedScale Clinical Workspace package.

CW-001 established the fail-closed Workspace boundary and the synthetic fixture
shell. CW-002 adds the governed local protected store: standard-library SQLite with
AES-256-GCM envelope encryption, HKDF-SHA-256 key derivation, an explicit
key-version state machine and no plaintext fallback. CW-003 adds the provenance
spine and the append-only audit spine that sit on top of that store.
"""

from __future__ import annotations

from medscale_workspace.aead import NONCE_SIZE_BYTES
from medscale_workspace.app import workspace_snapshot
from medscale_workspace.audit import (
    AuditChainReport,
    AuditEvent,
    AuditEventType,
    AuditObjectRef,
    AuditTrail,
)
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.errors import (
    AuditChainError,
    AuditError,
    AuditReplayError,
    ProvenanceDigestMismatchError,
    ProvenanceError,
    WorkspaceStoreError,
)
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
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ProvenanceRecord,
    ReviewState,
    SourceKind,
    SourceRef,
    content_digest_of,
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
    verify_provenance,
)
from medscale_workspace.storage import KeyState, ObjectWrite, WorkspaceStore
from medscale_workspace.store_path import resolve_workspace_store_path

__all__ = [
    "NONCE_SIZE_BYTES",
    "AuditChainError",
    "AuditChainReport",
    "AuditError",
    "AuditEvent",
    "AuditEventType",
    "AuditObjectRef",
    "AuditReplayError",
    "AuditTrail",
    "InMemoryTestKeyProvider",
    "KeyProvider",
    "KeyProviderCapabilities",
    "KeyState",
    "ObjectBinding",
    "ObjectWrite",
    "ProducerIdentity",
    "ProducerKind",
    "ProvenanceDigestMismatchError",
    "ProvenanceError",
    "ProvenanceRecord",
    "ReviewState",
    "SourceKind",
    "SourceRef",
    "SyntheticEncounter",
    "SyntheticPatient",
    "UnavailablePlatformKeyProvider",
    "WorkspaceObjectIdentity",
    "WorkspaceObjectType",
    "WorkspaceStore",
    "WorkspaceStoreError",
    "content_digest_of",
    "describe_revision",
    "provenance_binding_for",
    "read_provenance",
    "resolve_platform_key_provider",
    "resolve_workspace_store_path",
    "store_with_provenance",
    "synthetic_encounter",
    "synthetic_patient",
    "verify_provenance",
    "workspace_snapshot",
]

__version__ = "0.1.0.dev1"
