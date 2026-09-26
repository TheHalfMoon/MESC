"""Local object identity primitives for the synthetic-only CW-001 shell."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

_SYNTHETIC_NAMESPACE = UUID("86ac0bb4-9e71-4c11-a7a5-f491c6a2c8e1")


class WorkspaceObjectType(StrEnum):
    """Object classes admitted by the CW-001 synthetic fixture boundary."""

    PATIENT = "Patient"
    ENCOUNTER = "Encounter"
    # CW-003 (Issue #471) admits the provenance and audit record classes so the
    # provenance spine and the append-only audit spine can live in the same
    # workspace store as the objects they describe.
    PROVENANCE_RECORD = "ProvenanceRecord"
    AUDIT_EVENT = "AuditEvent"
    ENCOUNTER_SESSION = "EncounterSession"
    ENCOUNTER_CHUNK = "EncounterChunk"
    # CW-006 (Issue #480) admits the transcript class so offline ASR results
    # live in the same workspace store as the audio they describe.
    ASR_TRANSCRIPT = "AsrTranscript"
    # CW-007 (Issue #484) admits the clinical draft class so source-linked
    # draft results live in the same workspace store as the transcripts
    # they are validated against.
    CLINICAL_DRAFT = "ClinicalDraft"
    # CW-008 (Issue #487) admits the clinical review class so human review
    # and finalization revisions live in the same workspace store as the
    # drafts they review, with lineage bound to the reviewed draft.
    CLINICAL_REVIEW = "ClinicalReview"
    # CW-009 (Issue #490) admits the evidence corpus classes so corpus
    # sources, retrieval snapshots, queries, and result sets live in the
    # same workspace store as the objects they describe.
    EVIDENCE_CORPUS_SOURCE = "EvidenceCorpusSource"
    EVIDENCE_SNAPSHOT = "EvidenceSnapshot"
    EVIDENCE_QUERY = "EvidenceQuery"
    EVIDENCE_RESULT = "EvidenceResult"
    # CW-010 (Issue #495) admits the claim-source and evidence-strength classes so
    # claim sets, claim-source links, and strength assessments live in the same
    # workspace store as the corpus sources and snapshots they are validated
    # against. A citation string alone is never a link; only a stored link object
    # counts as SOURCE_LINKED evidence.
    EVIDENCE_CLAIM_SET = "EvidenceClaimSet"
    EVIDENCE_CLAIM_LINK = "EvidenceClaimLink"
    EVIDENCE_ASSESSMENT = "EvidenceAssessment"
    # CW-011 (Issue #498) admits the longitudinal patient graph classes so nodes,
    # edges, and derived graph views live in the same workspace store as the
    # corpus sources they are derived from. Graph state is derived, never
    # authoritative; source objects remain the truth.
    GRAPH_NODE = "PatientGraphNode"
    GRAPH_EDGE = "PatientGraphEdge"
    GRAPH_VIEW = "PatientGraphView"


@dataclass(frozen=True, slots=True)
class WorkspaceObjectIdentity:
    """Stable local identity carrying explicit workspace and object scope."""

    workspace_id: UUID
    object_id: UUID
    object_type: WorkspaceObjectType
    source_key: str


def synthetic_identity(
    workspace_id: UUID,
    object_type: WorkspaceObjectType,
    source_key: str,
) -> WorkspaceObjectIdentity:
    """Create a deterministic identity for a declared synthetic fixture."""

    normalized = source_key.strip()
    if not normalized:
        raise ValueError("source_key must be non-empty")
    object_id = uuid5(_SYNTHETIC_NAMESPACE, f"{workspace_id}:{object_type.value}:{normalized}")
    return WorkspaceObjectIdentity(
        workspace_id=workspace_id,
        object_id=object_id,
        object_type=object_type,
        source_key=normalized,
    )
