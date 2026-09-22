"""Synthetic-only MedScale Clinical Workspace package.

CW-001 established the fail-closed Workspace boundary and the synthetic fixture
shell. CW-002 adds the governed local protected store: standard-library SQLite with
AES-256-GCM envelope encryption, HKDF-SHA-256 key derivation, an explicit
key-version state machine and no plaintext fallback. CW-003 adds the provenance
spine and the append-only audit spine that sit on top of that store. CW-004 adds the
canonical typed data classification and the mechanical no-backflow guard that keeps
Workspace state, Domain X export staging and Research Core mechanically separate.
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
from medscale_workspace.data_class import (
    DATA_CLASS_ADMISSIONS,
    OPERATIONAL_DATA_CLASSES,
    SYNTHETIC_DATA_CLASS,
    DataClass,
    DataClassAdmission,
    DataClassification,
    TrustDomain,
    admit_data_class,
    admit_trust_domain,
    class_admission_of,
    classification_from_document,
    classify,
    domain_of,
    synthetic_data_class_value,
    validate_admission_table,
)
from medscale_workspace.errors import (
    AuditChainError,
    AuditError,
    AuditReplayError,
    BackflowError,
    DataClassificationError,
    ExplicitExportRequestError,
    ExportAdmissionError,
    ExportBoundaryError,
    ProvenanceDigestMismatchError,
    ProvenanceError,
    ResearchBackflowError,
    SecretEgressError,
    TelemetryBackflowError,
    UnavailableAuthorityError,
    UndeclaredFlowError,
    WorkspaceAdmissionError,
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
from medscale_workspace.nobackflow import (
    DOMAIN_FLOWS,
    ClassifiedObject,
    DomainFlow,
    ExportEnvelope,
    ExportPathAdmission,
    FlowDecision,
    FlowDisposition,
    FlowEvaluation,
    admit_export_path,
    admit_flow,
    classify_object,
    evaluate_flow,
    evaluate_object_flow,
    guard_object_handoff,
    stage_export,
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
    "DATA_CLASS_ADMISSIONS",
    "DOMAIN_FLOWS",
    "NONCE_SIZE_BYTES",
    "OPERATIONAL_DATA_CLASSES",
    "SYNTHETIC_DATA_CLASS",
    "AuditChainError",
    "AuditChainReport",
    "AuditError",
    "AuditEvent",
    "AuditEventType",
    "AuditObjectRef",
    "AuditReplayError",
    "AuditTrail",
    "BackflowError",
    "ClassifiedObject",
    "DataClass",
    "DataClassAdmission",
    "DataClassification",
    "DataClassificationError",
    "DomainFlow",
    "ExplicitExportRequestError",
    "ExportAdmissionError",
    "ExportBoundaryError",
    "ExportEnvelope",
    "ExportPathAdmission",
    "FlowDecision",
    "FlowDisposition",
    "FlowEvaluation",
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
    "ResearchBackflowError",
    "ReviewState",
    "SecretEgressError",
    "SourceKind",
    "SourceRef",
    "SyntheticEncounter",
    "SyntheticPatient",
    "TelemetryBackflowError",
    "TrustDomain",
    "UnavailableAuthorityError",
    "UnavailablePlatformKeyProvider",
    "UndeclaredFlowError",
    "WorkspaceAdmissionError",
    "WorkspaceObjectIdentity",
    "WorkspaceObjectType",
    "WorkspaceStore",
    "WorkspaceStoreError",
    "admit_data_class",
    "admit_export_path",
    "admit_flow",
    "admit_trust_domain",
    "class_admission_of",
    "classification_from_document",
    "classify",
    "classify_object",
    "content_digest_of",
    "describe_revision",
    "domain_of",
    "evaluate_flow",
    "evaluate_object_flow",
    "guard_object_handoff",
    "provenance_binding_for",
    "read_provenance",
    "resolve_platform_key_provider",
    "resolve_workspace_store_path",
    "stage_export",
    "store_with_provenance",
    "synthetic_data_class_value",
    "synthetic_encounter",
    "synthetic_patient",
    "validate_admission_table",
    "verify_provenance",
    "workspace_snapshot",
]

__version__ = "0.1.0.dev1"
