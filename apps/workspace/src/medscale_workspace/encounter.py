"""Synthetic encounter session lifecycle for CW-005.

This module implements encounter identity and recording-state semantics with
synthetic audio fixtures only. Capture is simulated: no microphone, no audio
device, and no network are used or required. Every transition is fail-closed,
deterministic, and recorded through the protected store, the provenance and
audit spine, and the classification vocabulary.

Lifecycle: create a stable session identity in consent-pending state, grant
recording and processing consent with retention policy, start, pause, resume,
and stop through one deterministic state machine, append ordered synthetic
audio chunks atomically with session state, recover by verifying sequence,
digests, retention, and workspace binding, and delete with a cascade that
removes session, chunk, and provenance objects while keeping audit metadata.

Chunk and session commits share one store transaction so a crash cannot leave
a chunk without its session update or a session update without its chunk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    EncounterChunkError,
    EncounterConcurrentError,
    EncounterConsentError,
    EncounterDeleteError,
    EncounterIdentityError,
    EncounterReplayError,
    EncounterRetentionError,
    EncounterSessionError,
    EncounterStateError,
    ObjectNotFoundError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    SourceKind,
    SourceRef,
    content_digest_of,
    describe_revision,
    provenance_binding_for,
)
from medscale_workspace.storage import ObjectWrite, WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

SESSION_NAMESPACE = UUID("c6a1a2b4-8f2e-4d9a-9c1e-2b3a4d5e6f70")
CHUNK_NAMESPACE = UUID("d7b2b3c5-9f3f-4eab-ad2f-3c4b5d6e7f81")

SESSION_REVISION_PREFIX = "session-"
CHUNK_REVISION_PREFIX = "chunk-"
CAPTURE_MODE = "simulated"
RETENTION_CLASS = "session-scoped"
RETENTION_VERSION = 1
PRODUCER_ID = "synthetic-capture"
OPERATOR_ID = "synthetic-operator"
PRODUCER_VERSION = "cw005-v1"
ENCOUNTER_SOURCE_REVISION = "encounter-001"

MAXIMUM_SESSION_KEY_LENGTH = 128
MAXIMUM_ACTOR_LENGTH = 128
MAXIMUM_OCCURRED_AT_LENGTH = 64
MAXIMUM_AUDIO_BYTES = 65536
MAXIMUM_CHUNKS = 4096


class EncounterState(StrEnum):
    """Deterministic recording states for one synthetic encounter session."""

    CONSENT_PENDING = "consent_pending"
    READY = "ready"
    CAPTURING = "capturing"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    """Recording and processing consent bound to one session revision."""

    recording: bool
    processing: bool
    actor: str
    granted_at: str
    retention: str


@dataclass(frozen=True, slots=True)
class RetentionRecord:
    """Retention metadata bound to sessions and chunks."""

    retention_class: str
    retention_version: int


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """Validated synthetic encounter session state at one immutable revision."""

    workspace_id: UUID
    session_id: UUID
    encounter_id: UUID
    session_key: str
    state: EncounterState
    consent: ConsentRecord
    retention: RetentionRecord
    chunk_count: int
    last_chunk_digest: str | None
    revision_counter: int
    revision: str
    policy_version: str
    capture_mode: str
    is_synthetic: bool
    data_class_value: str


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    """Validated synthetic audio chunk bound to one session and sequence."""

    workspace_id: UUID
    session_id: UUID
    chunk_id: UUID
    sequence: int
    audio_bytes: bytes
    audio_digest: str
    retention: RetentionRecord
    revision: str
    policy_version: str
    capture_mode: str
    is_synthetic: bool
    data_class_value: str


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Verified extent of one session after crash-recovery checks."""

    session_id: UUID
    revision_counter: int
    chunk_count: int
    last_chunk_digest: str | None
    chunks_verified: int


def session_id_for(workspace_id: UUID, encounter_id: UUID, session_key: str) -> UUID:
    """Return the stable deterministic session identity for one encounter."""

    if not isinstance(workspace_id, UUID) or not isinstance(encounter_id, UUID):
        raise EncounterIdentityError("workspace and encounter ids must be UUID values")
    key = _admit_session_key(session_key)
    return uuid5(SESSION_NAMESPACE, f"{workspace_id}:{encounter_id}:{key}")


def chunk_id_for(session_id: UUID, sequence: int) -> UUID:
    """Return the deterministic chunk identity for one session and sequence."""

    if not isinstance(session_id, UUID):
        raise EncounterIdentityError("session id must be a UUID value")
    admitted = _admit_sequence(sequence)
    return uuid5(CHUNK_NAMESPACE, f"{session_id}:{admitted:08d}")


def session_binding(workspace_id: UUID, session_id: UUID, revision_counter: int) -> ObjectBinding:
    """Return the store binding of one session revision."""

    admitted = _admit_revision_counter(revision_counter)
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=session_id,
        object_type=WorkspaceObjectType.ENCOUNTER_SESSION,
        object_revision=f"{SESSION_REVISION_PREFIX}{admitted:08d}",
    )


def chunk_binding(workspace_id: UUID, chunk_id: UUID, sequence: int) -> ObjectBinding:
    """Return the store binding of one chunk revision."""

    admitted = _admit_sequence(sequence)
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=chunk_id,
        object_type=WorkspaceObjectType.ENCOUNTER_CHUNK,
        object_revision=f"{CHUNK_REVISION_PREFIX}{admitted:08d}",
    )


def create_session(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    encounter_id: UUID,
    session_key: str,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Create one synthetic session in consent-pending state."""

    if not isinstance(store, WorkspaceStore) or not isinstance(trail, AuditTrail):
        raise EncounterStateError("a workspace store and audit trail are required")
    if not isinstance(encounter_id, UUID):
        raise EncounterIdentityError("encounter id must be a UUID value")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    key = _admit_session_key(session_key)
    session_id = session_id_for(store.workspace_id, encounter_id, key)
    try:
        _load_latest_session(store, session_id)
    except EncounterIdentityError:
        pass
    else:
        raise EncounterConcurrentError("the session identity already exists")
    record = SessionRecord(
        workspace_id=store.workspace_id,
        session_id=session_id,
        encounter_id=encounter_id,
        session_key=key,
        state=EncounterState.CONSENT_PENDING,
        consent=ConsentRecord(
            recording=False,
            processing=False,
            actor="",
            granted_at="",
            retention="",
        ),
        retention=RetentionRecord(
            retention_class=RETENTION_CLASS,
            retention_version=RETENTION_VERSION,
        ),
        chunk_count=0,
        last_chunk_digest=None,
        revision_counter=1,
        revision=f"{SESSION_REVISION_PREFIX}00000001",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )
    _store_session_revision(store, record, encounter_source=str(encounter_id))
    trail.record_object_write(
        binding=session_binding(store.workspace_id, session_id, 1),
        payload=session_payload_bytes(record),
        actor_id=actor,
        occurred_at=moment,
    )
    return record


def grant_consent(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Grant recording and processing consent, moving consent-pending to ready."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    if current.state is not EncounterState.CONSENT_PENDING:
        raise EncounterStateError("consent can only be granted from consent-pending")
    record = SessionRecord(
        workspace_id=current.workspace_id,
        session_id=current.session_id,
        encounter_id=current.encounter_id,
        session_key=current.session_key,
        state=EncounterState.READY,
        consent=ConsentRecord(
            recording=True,
            processing=True,
            actor=actor,
            granted_at=moment,
            retention=RETENTION_CLASS,
        ),
        retention=current.retention,
        chunk_count=current.chunk_count,
        last_chunk_digest=current.last_chunk_digest,
        revision_counter=current.revision_counter + 1,
        revision=f"{SESSION_REVISION_PREFIX}{current.revision_counter + 1:08d}",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.POLICY_CHANGE,
    )
    return record


def revoke_consent(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Revoke consent immediately, forcing capturing or paused sessions to stop."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    if current.state is EncounterState.STOPPED:
        raise EncounterStateError("consent cannot be revoked from a stopped session")
    if current.state is EncounterState.CONSENT_PENDING:
        raise EncounterStateError("consent is already pending")
    if current.state in (EncounterState.CAPTURING, EncounterState.PAUSED):
        next_state = EncounterState.STOPPED
    else:
        next_state = EncounterState.CONSENT_PENDING
    record = SessionRecord(
        workspace_id=current.workspace_id,
        session_id=current.session_id,
        encounter_id=current.encounter_id,
        session_key=current.session_key,
        state=next_state,
        consent=ConsentRecord(
            recording=False,
            processing=False,
            actor=actor,
            granted_at=moment,
            retention="",
        ),
        retention=current.retention,
        chunk_count=current.chunk_count,
        last_chunk_digest=current.last_chunk_digest,
        revision_counter=current.revision_counter + 1,
        revision=f"{SESSION_REVISION_PREFIX}{current.revision_counter + 1:08d}",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.POLICY_CHANGE,
    )
    if next_state is EncounterState.STOPPED:
        _audit_session(
            trail,
            record,
            actor_id=actor,
            occurred_at=moment,
            event_type=AuditEventType.CAPTURE_STOP,
        )
    return record


def start_capture(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Start simulated capture from the ready state."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    _require_consent(current)
    if current.state is not EncounterState.READY:
        raise EncounterStateError("capture can only start from the ready state")
    record = _next_session_state(current, EncounterState.CAPTURING)
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.CAPTURE_START,
    )
    return record


def pause_capture(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Pause simulated capture, refusing pause before start or after stop."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    _require_consent(current)
    if current.state is not EncounterState.CAPTURING:
        raise EncounterStateError("capture can only pause while capturing")
    record = _next_session_state(current, EncounterState.PAUSED)
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.CAPTURE_PAUSE,
    )
    return record


def resume_capture(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Resume simulated capture, refusing resume without a preceding pause."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    _require_consent(current)
    if current.state is not EncounterState.PAUSED:
        raise EncounterStateError("capture can only resume from the paused state")
    record = _next_session_state(current, EncounterState.CAPTURING)
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.CAPTURE_RESUME,
    )
    return record


def stop_capture(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> SessionRecord:
    """Stop simulated capture from capturing or paused, refusing double stop."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    if current.state not in (EncounterState.CAPTURING, EncounterState.PAUSED):
        raise EncounterStateError("capture can only stop while capturing or paused")
    record = _next_session_state(current, EncounterState.STOPPED)
    _store_session_revision(store, record, encounter_source=str(record.encounter_id))
    _audit_session(
        trail,
        record,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.CAPTURE_STOP,
    )
    return record


def append_chunk(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    audio_bytes: bytes,
    actor_id: str,
    occurred_at: str,
) -> tuple[SessionRecord, ChunkRecord]:
    """Append one ordered synthetic audio chunk atomically with session state."""

    current = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    _require_consent(current)
    if current.state is not EncounterState.CAPTURING:
        raise EncounterStateError("chunks can only be written while capturing")
    payload = _admit_audio_bytes(audio_bytes)
    if current.chunk_count + 1 > MAXIMUM_CHUNKS:
        raise EncounterChunkError("the session chunk limit has been reached")
    sequence = current.chunk_count + 1
    chunk_id = chunk_id_for(current.session_id, sequence)
    digest = content_digest_of(payload)
    chunk = ChunkRecord(
        workspace_id=current.workspace_id,
        session_id=current.session_id,
        chunk_id=chunk_id,
        sequence=sequence,
        audio_bytes=payload,
        audio_digest=digest,
        retention=current.retention,
        revision=f"{CHUNK_REVISION_PREFIX}{sequence:08d}",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )
    record = SessionRecord(
        workspace_id=current.workspace_id,
        session_id=current.session_id,
        encounter_id=current.encounter_id,
        session_key=current.session_key,
        state=current.state,
        consent=current.consent,
        retention=current.retention,
        chunk_count=sequence,
        last_chunk_digest=digest,
        revision_counter=current.revision_counter + 1,
        revision=f"{SESSION_REVISION_PREFIX}{current.revision_counter + 1:08d}",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )
    chunk_payload = _canonical_bytes(chunk_to_document(chunk))
    session_payload = _canonical_bytes(session_to_document(record))
    chunk_binding_value = chunk_binding(chunk.workspace_id, chunk.chunk_id, chunk.sequence)
    session_binding_value = session_binding(
        record.workspace_id, record.session_id, record.revision_counter
    )
    chunk_record = describe_revision(
        binding=chunk_binding_value,
        payload=chunk_payload,
        producer=ProducerIdentity(
            kind=ProducerKind.HUMAN,
            identifier=PRODUCER_ID,
            version=PRODUCER_VERSION,
        ),
        source_refs=(
            SourceRef(
                kind=SourceKind.AUDIO_RANGE,
                source_id=str(record.session_id),
                source_revision=current.revision,
            ),
        ),
        review_state=ReviewState.DRAFT,
    )
    session_record_value = describe_revision(
        binding=session_binding_value,
        payload=session_payload,
        producer=ProducerIdentity(
            kind=ProducerKind.HUMAN,
            identifier=OPERATOR_ID,
            version=PRODUCER_VERSION,
        ),
        source_refs=(
            SourceRef(
                kind=SourceKind.SOURCE_DOCUMENT,
                source_id=str(record.encounter_id),
                source_revision=ENCOUNTER_SOURCE_REVISION,
            ),
        ),
        review_state=ReviewState.DRAFT,
    )
    try:
        store.put_objects_atomic(
            (
                ObjectWrite(binding=chunk_binding_value, payload=chunk_payload),
                ObjectWrite(
                    binding=provenance_binding_for(chunk_binding_value),
                    payload=chunk_record.canonical_bytes(),
                ),
                ObjectWrite(binding=session_binding_value, payload=session_payload),
                ObjectWrite(
                    binding=provenance_binding_for(session_binding_value),
                    payload=session_record_value.canonical_bytes(),
                ),
            )
        )
    except StoreConflictError as error:
        raise EncounterReplayError(
            "the chunk identity or session revision already exists"
        ) from error
    trail.record_object_write(
        binding=chunk_binding_value,
        payload=chunk_payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return record, chunk


def read_session(store: WorkspaceStore, session_id: UUID) -> SessionRecord:
    """Return the latest validated session revision."""

    return _require_session(store, session_id)


def list_chunks(store: WorkspaceStore, session_id: UUID) -> tuple[ChunkRecord, ...]:
    """Return every validated chunk of one session in sequence order."""

    session = _require_session(store, session_id)
    chunks: list[ChunkRecord] = []
    for sequence in range(1, session.chunk_count + 1):
        chunk_id = chunk_id_for(session.session_id, sequence)
        binding = chunk_binding(store.workspace_id, chunk_id, sequence)
        try:
            raw = store.get_object(binding)
        except ObjectNotFoundError as error:
            raise EncounterChunkError("a committed chunk revision is missing") from error
        chunks.append(chunk_from_bytes(binding, raw))
    return tuple(chunks)


def recover_session(store: WorkspaceStore, session_id: UUID) -> RecoveryReport:
    """Verify session, chunk, digest, retention, and workspace consistency."""

    session = _require_session(store, session_id)
    verified = 0
    expected_digest: str | None = None
    for sequence in range(1, session.chunk_count + 1):
        chunk_id = chunk_id_for(session.session_id, sequence)
        binding = chunk_binding(store.workspace_id, chunk_id, sequence)
        try:
            raw = store.get_object(binding)
        except ObjectNotFoundError as error:
            raise EncounterChunkError(
                "crash recovery found a committed sequence without its chunk"
            ) from error
        chunk = chunk_from_bytes(binding, raw)
        if chunk.session_id != session.session_id:
            raise EncounterIdentityError("a chunk is bound to a foreign session")
        if chunk.sequence != sequence:
            raise EncounterChunkError("a chunk sequence is out of order")
        if chunk.retention != session.retention:
            raise EncounterRetentionError("a chunk retention contradicts session policy")
        if chunk.workspace_id != store.workspace_id:
            raise WorkspaceIsolationError("a chunk crossed the workspace boundary")
        expected_digest = chunk.audio_digest
        verified += 1
    if session.chunk_count == 0:
        if session.last_chunk_digest is not None:
            raise EncounterChunkError("an empty session must not carry a chunk digest")
    elif session.last_chunk_digest != expected_digest:
        raise EncounterChunkError("the session head digest does not match its last chunk")
    _detect_orphan_chunks(store, session)
    return RecoveryReport(
        session_id=session.session_id,
        revision_counter=session.revision_counter,
        chunk_count=session.chunk_count,
        last_chunk_digest=session.last_chunk_digest,
        chunks_verified=verified,
    )


def delete_session(
    store: WorkspaceStore,
    trail: AuditTrail,
    *,
    session_id: UUID,
    actor_id: str,
    occurred_at: str,
) -> int:
    """Delete session revisions, chunks, and provenance while keeping audit events."""

    session = _require_session(store, session_id)
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    deletions: list[ObjectBinding] = []
    for counter in range(1, session.revision_counter + 1):
        binding = session_binding(store.workspace_id, session.session_id, counter)
        deletions.append(binding)
        deletions.append(provenance_binding_for(binding))
    for sequence in range(1, session.chunk_count + 1):
        chunk_id = chunk_id_for(session.session_id, sequence)
        binding = chunk_binding(store.workspace_id, chunk_id, sequence)
        deletions.append(binding)
        deletions.append(provenance_binding_for(binding))
    removed = 0
    for binding in deletions:
        try:
            trail.record_object_deletion(
                binding=binding,
                actor_id=actor,
                occurred_at=moment,
            )
            removed += 1
        except ObjectNotFoundError:
            continue
    remaining = [
        revision
        for object_id, revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_SESSION)
        if object_id == session.session_id
    ]
    if remaining:
        raise EncounterDeleteError("the delete cascade left session state behind")
    expected_chunks = {
        chunk_id_for(session.session_id, sequence) for sequence in range(1, session.chunk_count + 1)
    }
    for object_id, _revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_CHUNK):
        if object_id in expected_chunks:
            raise EncounterDeleteError("the delete cascade left chunk state behind")
    return removed


def session_payload_bytes(record: SessionRecord) -> bytes:
    """Return the canonical payload bytes of one validated session revision."""

    validated = session_from_document(session_to_document(record))
    return _canonical_bytes(session_to_document(validated))


def chunk_payload_bytes(record: ChunkRecord) -> bytes:
    """Return the canonical payload bytes of one validated chunk."""

    validated = chunk_from_bytes(
        chunk_binding(record.workspace_id, record.chunk_id, record.sequence),
        _canonical_bytes(chunk_to_document(record)),
    )
    return _canonical_bytes(chunk_to_document(validated))


def session_to_document(record: SessionRecord) -> dict[str, object]:
    """Return the canonical session document of one record."""

    return {
        "capture_mode": record.capture_mode,
        "chunk_count": record.chunk_count,
        "consent": {
            "actor": record.consent.actor,
            "granted_at": record.consent.granted_at,
            "processing": record.consent.processing,
            "recording": record.consent.recording,
            "retention": record.consent.retention,
        },
        "data_class": record.data_class_value,
        "encounter_id": str(record.encounter_id),
        "is_synthetic": record.is_synthetic,
        "last_chunk_digest": record.last_chunk_digest,
        "policy_version": record.policy_version,
        "retention": {
            "retention_class": record.retention.retention_class,
            "retention_version": record.retention.retention_version,
        },
        "revision": record.revision,
        "revision_counter": record.revision_counter,
        "session_id": str(record.session_id),
        "session_key": record.session_key,
        "state": record.state.value,
        "workspace_id": str(record.workspace_id),
    }


def chunk_to_document(record: ChunkRecord) -> dict[str, object]:
    """Return the canonical chunk document of one record."""

    return {
        "audio_digest": record.audio_digest,
        "audio_hex": record.audio_bytes.hex(),
        "capture_mode": record.capture_mode,
        "chunk_id": str(record.chunk_id),
        "data_class": record.data_class_value,
        "is_synthetic": record.is_synthetic,
        "policy_version": record.policy_version,
        "retention": {
            "retention_class": record.retention.retention_class,
            "retention_version": record.retention.retention_version,
        },
        "revision": record.revision,
        "sequence": record.sequence,
        "session_id": str(record.session_id),
        "workspace_id": str(record.workspace_id),
    }


def session_from_document(document: object) -> SessionRecord:
    """Validate one stored session document, failing closed on any defect."""

    if not isinstance(document, dict):
        raise EncounterStateError("a stored session must be a JSON object")
    expected = {
        "capture_mode",
        "chunk_count",
        "consent",
        "data_class",
        "encounter_id",
        "is_synthetic",
        "last_chunk_digest",
        "policy_version",
        "retention",
        "revision",
        "revision_counter",
        "session_id",
        "session_key",
        "state",
        "workspace_id",
    }
    if set(document) != expected:
        raise EncounterStateError("a stored session carries unadmitted members")
    try:
        workspace_id = UUID(str(document["workspace_id"]))
        session_id = UUID(str(document["session_id"]))
        encounter_id = UUID(str(document["encounter_id"]))
    except ValueError as error:
        raise EncounterIdentityError("a session identity is not a UUID value") from error
    try:
        state = EncounterState(str(document["state"]))
    except ValueError as error:
        raise EncounterStateError("a stored session state is not admitted") from error
    consent_document = document["consent"]
    if not isinstance(consent_document, dict) or set(consent_document) != {
        "actor",
        "granted_at",
        "processing",
        "recording",
        "retention",
    }:
        raise EncounterConsentError("stored consent carries unadmitted members")
    recording = consent_document["recording"]
    processing = consent_document["processing"]
    if type(recording) is not bool or type(processing) is not bool:
        raise EncounterConsentError("stored consent flags must be booleans")
    actor_value = str(consent_document["actor"])
    granted_value = str(consent_document["granted_at"])
    retention_name = str(consent_document["retention"])
    if state is EncounterState.CONSENT_PENDING:
        if recording or processing:
            raise EncounterConsentError("a pending session must not carry granted consent")
    else:
        if not recording or not processing:
            raise EncounterConsentError("an active session must carry granted consent")
        if not actor_value.strip():
            raise EncounterConsentError("granted consent must record actor and time")
        if not granted_value.strip():
            raise EncounterConsentError("granted consent must record actor and time")
        if not retention_name.strip():
            raise EncounterConsentError("granted consent must record actor and time")
        if retention_name != RETENTION_CLASS:
            raise EncounterRetentionError("stored consent retention is not admitted")
    retention = _retention_from_document(document["retention"])
    chunk_count = document["chunk_count"]
    if not isinstance(chunk_count, int) or isinstance(chunk_count, bool):
        raise EncounterChunkError("stored chunk count must be an integer")
    if chunk_count < 0 or chunk_count > MAXIMUM_CHUNKS:
        raise EncounterChunkError("stored chunk count is out of range")
    last_digest = document["last_chunk_digest"]
    if last_digest is not None:
        if not isinstance(last_digest, str):
            raise EncounterChunkError("stored head digest must be a string or null")
        _admit_digest(last_digest)
        if chunk_count == 0:
            raise EncounterChunkError("an empty session must not carry a head digest")
    elif chunk_count != 0:
        raise EncounterChunkError("a non-empty session must carry a head digest")
    revision_counter = document["revision_counter"]
    if not isinstance(revision_counter, int) or isinstance(revision_counter, bool):
        raise EncounterIdentityError("stored revision counter must be an integer")
    if revision_counter < 1:
        raise EncounterIdentityError("stored revision counter is out of range")
    revision = str(document["revision"])
    if revision != f"{SESSION_REVISION_PREFIX}{revision_counter:08d}":
        raise EncounterIdentityError("stored session revision does not match its counter")
    if str(document["policy_version"]) != POLICY_VERSION:
        raise EncounterStateError("stored policy version is not supported here")
    if str(document["capture_mode"]) != CAPTURE_MODE:
        raise EncounterStateError("stored capture mode is not the simulated mode")
    if document["is_synthetic"] is not True:
        raise EncounterStateError("stored session must be marked as synthetic-only")
    if str(document["data_class"]) != synthetic_data_class_value():
        raise EncounterStateError("stored data class is not the admitted value")
    session_key = _admit_session_key(str(document["session_key"]))
    if session_id_for(workspace_id, encounter_id, session_key) != session_id:
        raise EncounterIdentityError("stored session identity does not match its key")
    return SessionRecord(
        workspace_id=workspace_id,
        session_id=session_id,
        encounter_id=encounter_id,
        session_key=session_key,
        state=state,
        consent=ConsentRecord(
            recording=recording,
            processing=processing,
            actor=actor_value,
            granted_at=granted_value,
            retention=retention_name,
        ),
        retention=retention,
        chunk_count=chunk_count,
        last_chunk_digest=last_digest,
        revision_counter=revision_counter,
        revision=revision,
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )


def chunk_from_bytes(binding: ObjectBinding, raw: bytes) -> ChunkRecord:
    """Validate one stored chunk payload against its binding."""

    admitted_binding = binding.validated()
    if admitted_binding.object_type is not WorkspaceObjectType.ENCOUNTER_CHUNK:
        raise EncounterChunkError("a chunk binding carries an unadmitted object type")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise EncounterChunkError("a stored chunk is not canonical ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise EncounterChunkError("a stored chunk is not JSON") from error
    if not isinstance(document, dict):
        raise EncounterChunkError("a stored chunk must be a JSON object")
    expected = {
        "audio_digest",
        "audio_hex",
        "capture_mode",
        "chunk_id",
        "data_class",
        "is_synthetic",
        "policy_version",
        "retention",
        "revision",
        "sequence",
        "session_id",
        "workspace_id",
    }
    if set(document) != expected:
        raise EncounterChunkError("a stored chunk carries unadmitted members")
    try:
        workspace_id = UUID(str(document["workspace_id"]))
        session_id = UUID(str(document["session_id"]))
        chunk_id = UUID(str(document["chunk_id"]))
    except ValueError as error:
        raise EncounterIdentityError("a chunk identity is not a UUID value") from error
    sequence = document["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise EncounterChunkError("stored chunk sequence must be an integer")
    _admit_sequence(sequence)
    if chunk_id != chunk_id_for(session_id, sequence):
        raise EncounterIdentityError("stored chunk identity does not match its sequence")
    if admitted_binding.object_id != chunk_id:
        raise EncounterIdentityError("stored chunk identity does not match its binding")
    if admitted_binding.workspace_id != workspace_id:
        raise WorkspaceIsolationError("a chunk crossed the workspace boundary")
    if admitted_binding.object_revision != f"{CHUNK_REVISION_PREFIX}{sequence:08d}":
        raise EncounterIdentityError("stored chunk revision does not match its sequence")
    if str(document["revision"]) != admitted_binding.object_revision:
        raise EncounterIdentityError("stored chunk revision does not match its binding")
    audio_hex = str(document["audio_hex"])
    try:
        audio_bytes = bytes.fromhex(audio_hex)
    except ValueError as error:
        raise EncounterChunkError("stored audio is not hexadecimal") from error
    _admit_audio_bytes(audio_bytes)
    digest = _admit_digest(str(document["audio_digest"]))
    if content_digest_of(audio_bytes) != digest:
        raise EncounterChunkError("stored audio digest does not match its audio bytes")
    retention = _retention_from_document(document["retention"])
    if str(document["policy_version"]) != POLICY_VERSION:
        raise EncounterStateError("stored chunk policy version is not supported here")
    if str(document["capture_mode"]) != CAPTURE_MODE:
        raise EncounterStateError("stored chunk capture mode is not the simulated mode")
    if document["is_synthetic"] is not True:
        raise EncounterStateError("stored chunk must be marked as synthetic-only")
    if str(document["data_class"]) != synthetic_data_class_value():
        raise EncounterStateError("stored chunk data class is not the admitted value")
    return ChunkRecord(
        workspace_id=workspace_id,
        session_id=session_id,
        chunk_id=chunk_id,
        sequence=sequence,
        audio_bytes=audio_bytes,
        audio_digest=digest,
        retention=retention,
        revision=admitted_binding.object_revision,
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )


def _require_session(store: WorkspaceStore, session_id: UUID) -> SessionRecord:
    if not isinstance(session_id, UUID):
        raise EncounterIdentityError("session id must be a UUID value")
    record = _load_latest_session(store, session_id)
    if record.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a session crossed the workspace boundary")
    return record


def _load_latest_session(store: WorkspaceStore, session_id: UUID) -> SessionRecord:
    revisions = [
        revision
        for object_id, revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_SESSION)
        if object_id == session_id
    ]
    if not revisions:
        raise EncounterIdentityError("the session identity is not present in this store")
    latest = sorted(revisions)[-1]
    binding = ObjectBinding(
        workspace_id=store.workspace_id,
        object_id=session_id,
        object_type=WorkspaceObjectType.ENCOUNTER_SESSION,
        object_revision=latest,
    )
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise EncounterIdentityError("the latest session revision is missing") from error
    try:
        document = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EncounterStateError("a stored session is not canonical JSON") from error
    record = session_from_document(document)
    if record.revision != latest:
        raise EncounterIdentityError("the stored session revision does not match binding")
    if record.session_id != session_id:
        raise EncounterIdentityError("a session object does not match its identity")
    return record


def _store_session_revision(
    store: WorkspaceStore, record: SessionRecord, *, encounter_source: str
) -> None:
    binding = session_binding(record.workspace_id, record.session_id, record.revision_counter)
    payload = _canonical_bytes(session_to_document(record))
    described = describe_revision(
        binding=binding,
        payload=payload,
        producer=ProducerIdentity(
            kind=ProducerKind.HUMAN,
            identifier=OPERATOR_ID,
            version=PRODUCER_VERSION,
        ),
        source_refs=(
            SourceRef(
                kind=SourceKind.SOURCE_DOCUMENT,
                source_id=encounter_source,
                source_revision=ENCOUNTER_SOURCE_REVISION,
            ),
        ),
        review_state=ReviewState.DRAFT,
    )
    try:
        store.put_objects_atomic(
            (
                ObjectWrite(binding=binding, payload=payload),
                ObjectWrite(
                    binding=provenance_binding_for(binding),
                    payload=described.canonical_bytes(),
                ),
            )
        )
    except StoreConflictError as error:
        raise EncounterConcurrentError(
            "the session revision already exists; a concurrent transition collided"
        ) from error


def _next_session_state(current: SessionRecord, state: EncounterState) -> SessionRecord:
    return SessionRecord(
        workspace_id=current.workspace_id,
        session_id=current.session_id,
        encounter_id=current.encounter_id,
        session_key=current.session_key,
        state=state,
        consent=current.consent,
        retention=current.retention,
        chunk_count=current.chunk_count,
        last_chunk_digest=current.last_chunk_digest,
        revision_counter=current.revision_counter + 1,
        revision=f"{SESSION_REVISION_PREFIX}{current.revision_counter + 1:08d}",
        policy_version=POLICY_VERSION,
        capture_mode=CAPTURE_MODE,
        is_synthetic=True,
        data_class_value=synthetic_data_class_value(),
    )


def _require_consent(record: SessionRecord) -> None:
    consent = record.consent
    if not consent.recording or not consent.processing:
        raise EncounterConsentError("simulated capture requires granted recording consent")
    if not consent.actor.strip():
        raise EncounterConsentError("granted consent must record actor and time")
    if not consent.granted_at.strip():
        raise EncounterConsentError("granted consent must record actor and time")
    if consent.retention != RETENTION_CLASS:
        raise EncounterRetentionError("session consent retention is not admitted")


def _audit_session(
    trail: AuditTrail,
    record: SessionRecord,
    *,
    actor_id: str,
    occurred_at: str,
    event_type: AuditEventType,
) -> None:
    binding = session_binding(record.workspace_id, record.session_id, record.revision_counter)
    payload = _canonical_bytes(session_to_document(record))
    reference = AuditObjectRef(
        object_id=binding.object_id,
        object_type=binding.object_type,
        object_revision=binding.object_revision,
        content_digest=content_digest_of(payload),
    )
    trail.append(
        event_type=event_type,
        actor_id=actor_id,
        occurred_at=occurred_at,
        object_refs=(reference,),
        metadata=(
            ("session_id", str(record.session_id)),
            ("state", record.state.value),
            ("revision", record.revision),
        ),
    )


def _detect_orphan_chunks(
    store: WorkspaceStore, session: SessionRecord, *, allow_missing: bool = False
) -> None:
    expected = {
        chunk_id_for(session.session_id, sequence) for sequence in range(1, session.chunk_count + 1)
    }
    for object_id, revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_CHUNK):
        try:
            raw = store.get_object(
                ObjectBinding(
                    workspace_id=store.workspace_id,
                    object_id=object_id,
                    object_type=WorkspaceObjectType.ENCOUNTER_CHUNK,
                    object_revision=revision,
                )
            )
        except ObjectNotFoundError:
            continue
        try:
            text = raw.decode("ascii")
            document = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        raw_session = document.get("session_id")
        if raw_session != str(session.session_id):
            continue
        if object_id not in expected:
            if allow_missing:
                continue
            raise EncounterChunkError("crash recovery found an orphaned session chunk")


def _retention_from_document(document: object) -> RetentionRecord:
    if not isinstance(document, dict) or set(document) != {
        "retention_class",
        "retention_version",
    }:
        raise EncounterRetentionError("stored retention carries unadmitted members")
    retention_class = str(document["retention_class"])
    version = document["retention_version"]
    if retention_class != RETENTION_CLASS:
        raise EncounterRetentionError("stored retention class is not admitted")
    if not isinstance(version, int) or isinstance(version, bool):
        raise EncounterRetentionError("stored retention version must be an integer")
    if version != RETENTION_VERSION:
        raise EncounterRetentionError("stored retention version is not supported here")
    return RetentionRecord(
        retention_class=retention_class,
        retention_version=version,
    )


def _admit_session_key(raw: object) -> str:
    if not isinstance(raw, str):
        raise EncounterIdentityError("session key must be a string")
    value = raw.strip()
    if not value:
        raise EncounterIdentityError("session key must be non-empty")
    if len(value) > MAXIMUM_SESSION_KEY_LENGTH:
        raise EncounterIdentityError("session key is longer than the admitted maximum")
    if not value.isascii():
        raise EncounterIdentityError("session key must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise EncounterIdentityError("session key must not contain whitespace")
    return value


def _admit_actor(raw: object) -> str:
    if not isinstance(raw, str):
        raise EncounterSessionError("actor id must be a string")
    value = raw.strip()
    if not value:
        raise EncounterSessionError("actor id must be non-empty")
    if len(value) > MAXIMUM_ACTOR_LENGTH:
        raise EncounterSessionError("actor id is longer than the admitted maximum")
    if not value.isascii():
        raise EncounterSessionError("actor id must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise EncounterSessionError("actor id must not contain whitespace")
    return value


def _admit_occurred_at(raw: object) -> str:
    if not isinstance(raw, str):
        raise EncounterSessionError("occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise EncounterSessionError("occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_LENGTH:
        raise EncounterSessionError("occurrence time is longer than the admitted maximum")
    if not value.isascii():
        raise EncounterSessionError("occurrence time must be ASCII")
    for character in value:
        if not character.isprintable():
            raise EncounterSessionError("occurrence time must not contain controls")
    return value


def _admit_sequence(raw: object) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise EncounterChunkError("chunk sequence must be an integer")
    if raw < 1 or raw > MAXIMUM_CHUNKS:
        raise EncounterChunkError("chunk sequence is out of range")
    return raw


def _admit_revision_counter(raw: object) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise EncounterIdentityError("revision counter must be an integer")
    if raw < 1:
        raise EncounterIdentityError("revision counter is out of range")
    return raw


def _admit_audio_bytes(raw: object) -> bytes:
    if not isinstance(raw, bytes):
        raise EncounterChunkError("audio payload must be bytes")
    if not raw:
        raise EncounterChunkError("audio payload must be non-empty")
    if len(raw) > MAXIMUM_AUDIO_BYTES:
        raise EncounterChunkError("audio payload exceeds the admitted maximum")
    return raw


def _admit_digest(raw: str) -> str:
    prefix = "sha256:"
    if not raw.startswith(prefix):
        raise EncounterChunkError("a digest must carry the admitted prefix")
    hex_part = raw[len(prefix) :]
    if len(hex_part) != 64:
        raise EncounterChunkError("a digest must carry 64 hex characters")
    for character in hex_part:
        if character not in "0123456789abcdef":
            raise EncounterChunkError("a digest must be lowercase hex")
    return raw


def _canonical_bytes(document: dict[str, object]) -> bytes:
    encoded = json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return encoded.encode("ascii")
