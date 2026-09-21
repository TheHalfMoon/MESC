"""Append-only logical audit spine for CW-003.

CW-003 acceptance (Issue #471, contract section 12 of the Clinical Workspace V1
specification): audit events are append-only logical events, provenance and audit
are separate concepts, sensitive payloads are absent from audit records, tamper and
replay attempts are detected, and deletion can preserve audit metadata without
retaining the deleted content.

Design:

* each event is one immutable object in the CW-002 store, keyed by a digest-derived
  event identity and a chain position, so a replayed event — and a concurrent attempt
  to append two different events at the same position — collide with the stored object
  instead of silently appending a second event;
* every event carries the digest of its predecessor and its own digest over a
  canonical payload document, forming a hash chain from a genesis digest;
* the caller supplies ``occurred_at``: this package imports no clock, so ordering is
  explicit, deterministic and auditable;
* audit records carry object ids, object types, revisions, content digests and
  bounded metadata only — never payload content;
* deleting content and recording the deletion happen in one store transaction.

Recorded limitation: append-only is enforced by this API, by digest-derived object
identity and by chain verification. There is no database-level write-once trigger,
so a party with direct database write access could remove a trailing event; that
would be detected as a chain shortfall only against a retained head digest. Stricter
storage-level enforcement belongs to the CW-018 lifecycle work and the CW-019
independent security lane.

Cost note: every append re-verifies the whole chain before it writes, so append cost
grows with trail length. Checkpointing or anchored-head designs belong to CW-018.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.binding import ObjectBinding
from medscale_workspace.errors import (
    AuditChainError,
    AuditError,
    AuditReplayError,
    StoreConflictError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import content_digest_of
from medscale_workspace.storage import ObjectWrite, WorkspaceStore
from medscale_workspace.versions import AUDIT_CHAIN_FORMAT_VERSION, POLICY_VERSION

AUDIT_OBJECT_NAMESPACE = UUID("3ad1f5c8-2b64-4e19-8a70-9c5d2e6b4f81")
CHAIN_OBJECT_ID = uuid5(AUDIT_OBJECT_NAMESPACE, "audit-chain")
EVENT_ID_PREFIX = "mesc-ws-audit/1:sha256:"
GENESIS_EVENT_DIGEST = "0" * 64
MAXIMUM_IDENTIFIER_LENGTH = 128
MAXIMUM_METADATA_MEMBERS = 8
MAXIMUM_METADATA_VALUE_LENGTH = 256


class AuditEventType(StrEnum):
    """The audit event classes required by the Clinical Workspace audit contract."""

    LOGIN = "login"
    WORKSPACE_OPEN = "workspace_open"
    WORKSPACE_CLOSE = "workspace_close"
    PATIENT_READ = "patient_read"
    ENCOUNTER_READ = "encounter_read"
    CAPTURE_START = "capture_start"
    CAPTURE_PAUSE = "capture_pause"
    CAPTURE_RESUME = "capture_resume"
    CAPTURE_STOP = "capture_stop"
    TRANSCRIPT_CREATE = "transcript_create"
    TRANSCRIPT_EDIT = "transcript_edit"
    TRANSCRIPT_DELETE = "transcript_delete"
    AI_GENERATION = "ai_generation"
    EVIDENCE_QUERY = "evidence_query"
    EXPORT = "export"
    CONNECTOR_READ = "connector_read"
    CONNECTOR_WRITE = "connector_write"
    NOTE_FINALIZE = "note_finalize"
    SUGGESTION_ACCEPT = "suggestion_accept"
    SUGGESTION_REJECT = "suggestion_reject"
    BACKUP = "backup"
    RESTORE = "restore"
    OBJECT_CREATE = "object_create"
    OBJECT_DELETE = "object_delete"
    POLICY_CHANGE = "policy_change"
    KEY_ROTATION = "key_rotation"
    SECURITY_FAILURE = "security_failure"


def _admitted_text(raw: object, *, label: str, maximum: int) -> str:
    if not isinstance(raw, str):
        raise AuditError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise AuditError(f"{label} must be non-empty")
    if len(value) > maximum:
        raise AuditError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise AuditError(f"{label} must be ASCII")
    for character in value:
        if not character.isprintable():
            raise AuditError(f"{label} must not contain control characters")
    return value


def _admitted_occurred_at(raw: object) -> str:
    """Admit a well-formed ISO-8601 instant with an explicit zone.

    Shape validation only: the package holds no calendar and performs no date
    arithmetic, so this checks the recorded form, not calendar correctness.
    """

    value = _admitted_text(raw, label="audit occurrence time", maximum=64)
    separator = value[10:11]
    if len(value) < 20 or separator != "T":
        raise AuditError("audit occurrence time must be an ISO-8601 instant with a zone")
    date_part = value[:10]
    time_part = value[11:]
    if not (
        _digits(date_part[0:4], 4)
        and date_part[4:5] == "-"
        and _digits(date_part[5:7], 2)
        and date_part[7:8] == "-"
        and _digits(date_part[8:10], 2)
    ):
        raise AuditError("audit occurrence time must start with YYYY-MM-DD")
    month = int(date_part[5:7])
    day = int(date_part[8:10])
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise AuditError("audit occurrence time carries an out-of-range month or day")
    zone_offset = time_part.find("+", 1)
    if zone_offset < 0:
        zone_offset = time_part.find("-", 1)
    if zone_offset < 0:
        if not time_part.endswith("Z"):
            raise AuditError("audit occurrence time must carry Z or a numeric zone offset")
        clock = time_part[:-1]
        zone = "Z"
    else:
        clock = time_part[:zone_offset]
        zone = time_part[zone_offset:]
    fraction = clock.find(".")
    if fraction >= 0:
        if not _digits(clock[fraction + 1 :], 0) or not 1 <= len(clock) - fraction - 1 <= 6:
            raise AuditError("audit occurrence time fraction must carry one to six digits")
        clock = clock[:fraction]
    if (
        len(clock) != 8
        or not _digits(clock[0:2], 2)
        or clock[2:3] != ":"
        or not _digits(clock[3:5], 2)
        or clock[5:6] != ":"
        or not _digits(clock[6:8], 2)
    ):
        raise AuditError("audit occurrence time must carry HH:MM:SS")
    hour = int(clock[0:2])
    minute = int(clock[3:5])
    second = int(clock[6:8])
    if hour > 23 or minute > 59 or second > 60:
        raise AuditError("audit occurrence time carries an out-of-range clock value")
    if zone != "Z" and not (
        len(zone) == 6
        and zone[0:1] in {"+", "-"}
        and _digits(zone[1:3], 2)
        and zone[3:4] == ":"
        and _digits(zone[4:6], 2)
        and int(zone[1:3]) <= 23
        and int(zone[4:6]) <= 59
    ):
        raise AuditError("audit occurrence time zone offset must be +HH:MM or -HH:MM")
    return value


def _digits(raw: str, length: int) -> bool:
    if length and len(raw) != length:
        return False
    if not raw:
        return False
    return all(character in "0123456789" for character in raw)


def _admitted_digest(raw: object, *, label: str) -> str:
    if not isinstance(raw, str) or len(raw) != 64:
        raise AuditError(f"{label} must carry 64 lowercase hex characters")
    if any(character not in "0123456789abcdef" for character in raw):
        raise AuditError(f"{label} must carry 64 lowercase hex characters")
    return raw


def _canonical_bytes(document: object) -> bytes:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return encoded.encode("ascii")


@dataclass(frozen=True, slots=True)
class AuditObjectRef:
    """A reference to one object revision, with no payload content."""

    object_id: UUID
    object_type: WorkspaceObjectType
    object_revision: str
    content_digest: str | None = None

    def validated(self) -> AuditObjectRef:
        if not isinstance(self.object_id, UUID):
            raise AuditError("audit object reference id must be a UUID value")
        if not isinstance(self.object_type, WorkspaceObjectType):
            raise AuditError("audit object reference type must be an admitted object type")
        if not isinstance(self.object_revision, str) or not self.object_revision.strip():
            raise AuditError("audit object reference revision must be non-empty")
        digest = None
        if self.content_digest is not None:
            digest = _admitted_digest_text(self.content_digest)
        return AuditObjectRef(
            object_id=self.object_id,
            object_type=self.object_type,
            object_revision=_admitted_text(
                self.object_revision,
                label="audit object reference revision",
                maximum=128,
            ),
            content_digest=digest,
        )

    def to_document(self) -> dict[str, object]:
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "object_id": str(admitted.object_id),
            "object_revision": admitted.object_revision,
            "object_type": admitted.object_type.value,
        }


def _admitted_digest_text(raw: object) -> str:
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise AuditError("audit content digest must be a sha256: digest")
    _admitted_digest(raw[len("sha256:") :], label="audit content digest")
    return raw


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """One append-only logical audit event."""

    event_id: str
    event_digest: str
    chain_format_version: int
    sequence: int
    event_type: AuditEventType
    workspace_id: UUID
    actor_id: str
    occurred_at: str
    object_refs: tuple[AuditObjectRef, ...]
    metadata: tuple[tuple[str, str], ...]
    previous_event_digest: str

    def payload_document(self) -> dict[str, object]:
        """Return the digest-covered document, which excludes the event identity."""

        if not isinstance(self.event_type, AuditEventType):
            raise AuditError("audit event type must be an admitted event type")
        if not isinstance(self.workspace_id, UUID):
            raise AuditError("audit event workspace id must be a UUID value")
        if (
            not isinstance(self.sequence, int)
            or isinstance(self.sequence, bool)
            or self.sequence < 1
        ):
            raise AuditError("audit event sequence must be a positive integer")
        if self.chain_format_version != AUDIT_CHAIN_FORMAT_VERSION:
            raise AuditError("audit chain format version is not supported here")
        metadata: list[list[str]] = []
        if len(self.metadata) > MAXIMUM_METADATA_MEMBERS:
            raise AuditError("audit event metadata has too many members")
        for name, value in self.metadata:
            metadata.append(
                [
                    _admitted_text(
                        name, label="audit metadata name", maximum=MAXIMUM_METADATA_VALUE_LENGTH
                    ),
                    _admitted_text(
                        value, label="audit metadata value", maximum=MAXIMUM_METADATA_VALUE_LENGTH
                    ),
                ]
            )
        return {
            "actor_id": _admitted_text(
                self.actor_id,
                label="audit actor id",
                maximum=MAXIMUM_IDENTIFIER_LENGTH,
            ),
            "chain_format_version": self.chain_format_version,
            "event_type": self.event_type.value,
            "metadata": metadata,
            "object_refs": [reference.to_document() for reference in self.object_refs],
            "occurred_at": _admitted_occurred_at(self.occurred_at),
            "policy_version": POLICY_VERSION,
            "previous_event_digest": _admitted_digest(
                self.previous_event_digest,
                label="previous audit event digest",
            ),
            "sequence": self.sequence,
            "workspace_id": str(self.workspace_id),
        }

    def canonical_payload_bytes(self) -> bytes:
        return _canonical_bytes(self.payload_document())

    def canonical_bytes(self) -> bytes:
        document = self.payload_document()
        document["event_digest"] = self.event_digest
        document["event_id"] = self.event_id
        return _canonical_bytes(document)

    @property
    def object_revision(self) -> str:
        return f"audit-{self.sequence:08d}"

    def binding(self) -> ObjectBinding:
        return ObjectBinding(
            workspace_id=self.workspace_id,
            object_id=CHAIN_OBJECT_ID,
            object_type=WorkspaceObjectType.AUDIT_EVENT,
            object_revision=self.object_revision,
        )


@dataclass(frozen=True, slots=True)
class AuditChainReport:
    """The result of verifying the append-only audit chain."""

    events_verified: int
    first_sequence: int | None
    last_sequence: int | None
    head_event_digest: str | None


class AuditTrail:
    """The append-only audit spine of one workspace store."""

    def __init__(self, store: WorkspaceStore) -> None:
        self._store = store

    def events(self) -> tuple[AuditEvent, ...]:
        """Return every stored event in sequence order after verifying the chain."""

        events = self._stored_events()
        self._verify(events)
        return events

    def head(self) -> AuditEvent | None:
        """Return the current head event, or ``None`` for an empty trail."""

        events = self._stored_events()
        if not events:
            return None
        self._verify(events)
        return events[-1]

    def append(
        self,
        *,
        event_type: AuditEventType,
        actor_id: str,
        occurred_at: str,
        object_refs: tuple[AuditObjectRef, ...] = (),
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> AuditEvent:
        """Append one event to the chain, or refuse if it would not append cleanly."""

        head = self.head()
        event = _build_event(
            sequence=1 if head is None else head.sequence + 1,
            previous_event_digest=GENESIS_EVENT_DIGEST if head is None else head.event_digest,
            event_type=event_type,
            workspace_id=self._store.workspace_id,
            actor_id=actor_id,
            occurred_at=occurred_at,
            object_refs=object_refs,
            metadata=metadata,
        )
        self._store_event(event)
        return event

    def record_object_write(
        self,
        *,
        binding: ObjectBinding,
        payload: bytes,
        actor_id: str,
        occurred_at: str,
        event_type: AuditEventType = AuditEventType.OBJECT_CREATE,
    ) -> AuditEvent:
        """Append an event describing an object revision that was just written."""

        admitted = binding.validated()
        reference = AuditObjectRef(
            object_id=admitted.object_id,
            object_type=admitted.object_type,
            object_revision=admitted.object_revision,
            content_digest=content_digest_of(payload),
        )
        return self.append(
            event_type=event_type,
            actor_id=actor_id,
            occurred_at=occurred_at,
            object_refs=(reference,),
        )

    def record_object_deletion(
        self,
        *,
        binding: ObjectBinding,
        actor_id: str,
        occurred_at: str,
    ) -> AuditEvent:
        """Delete one object revision and record the deletion in one transaction.

        The audit event keeps the object id, type, revision and content digest; the
        deleted content is not retained anywhere in the event.
        """

        admitted = binding.validated()
        payload = self._store.get_object(admitted)
        reference = AuditObjectRef(
            object_id=admitted.object_id,
            object_type=admitted.object_type,
            object_revision=admitted.object_revision,
            content_digest=content_digest_of(payload),
        )
        head = self.head()
        event = _build_event(
            sequence=1 if head is None else head.sequence + 1,
            previous_event_digest=GENESIS_EVENT_DIGEST if head is None else head.event_digest,
            event_type=AuditEventType.OBJECT_DELETE,
            workspace_id=self._store.workspace_id,
            actor_id=actor_id,
            occurred_at=occurred_at,
            object_refs=(reference,),
            metadata=(),
        )
        self._store.delete_and_put_atomic(
            deletions=(admitted,),
            writes=(ObjectWrite(binding=event.binding(), payload=event.canonical_bytes()),),
        )
        return event

    def verify(self, *, expected_head_event_digest: str | None = None) -> AuditChainReport:
        """Verify the chain and return its verified extent.

        Supplying ``expected_head_event_digest`` turns this into an anchored check: a
        chain whose last event was removed still verifies internally, so detecting tail
        truncation requires a head digest retained outside the store.
        """

        events = self._stored_events()
        self._verify(events)
        report = AuditChainReport(
            events_verified=len(events),
            first_sequence=events[0].sequence if events else None,
            last_sequence=events[-1].sequence if events else None,
            head_event_digest=events[-1].event_digest if events else None,
        )
        if (
            expected_head_event_digest is not None
            and report.head_event_digest != expected_head_event_digest
        ):
            raise AuditChainError(
                "audit chain head does not match the retained anchor digest; the chain was "
                "truncated or replaced"
            )
        return report

    def _store_event(self, event: AuditEvent) -> None:
        try:
            self._store.put_objects_atomic(
                (ObjectWrite(binding=event.binding(), payload=event.canonical_bytes()),)
            )
        except StoreConflictError as error:
            raise AuditReplayError(
                "this audit chain position already holds an event; the event was not appended"
            ) from error

    def _stored_events(self) -> tuple[AuditEvent, ...]:
        events: list[AuditEvent] = []
        for object_id, revision in self._store.object_revisions(WorkspaceObjectType.AUDIT_EVENT):
            binding = ObjectBinding(
                workspace_id=self._store.workspace_id,
                object_id=object_id,
                object_type=WorkspaceObjectType.AUDIT_EVENT,
                object_revision=revision,
            )
            raw = self._store.get_object(binding)
            event = _event_from_bytes(raw)
            if event.binding() != binding:
                raise AuditChainError("stored audit event identity does not match its object")
            events.append(event)
        events.sort(key=lambda event: event.sequence)
        return tuple(events)

    @staticmethod
    def _verify(events: tuple[AuditEvent, ...]) -> None:
        previous = GENESIS_EVENT_DIGEST
        expected_sequence = 1
        seen: set[str] = set()
        for event in events:
            if event.sequence != expected_sequence:
                raise AuditChainError(
                    "audit chain sequence is not contiguous; an event was removed or reordered"
                )
            if event.previous_event_digest != previous:
                raise AuditChainError("audit chain link does not match the previous event digest")
            if event.event_digest in seen:
                raise AuditReplayError("an audit event digest appears more than once")
            recomputed = _event_digest(event.canonical_payload_bytes())
            if recomputed != event.event_digest:
                raise AuditChainError("audit event digest does not match its canonical payload")
            if event.event_id != f"{EVENT_ID_PREFIX}{event.event_digest}":
                raise AuditChainError("audit event identity is not derived from its digest")
            seen.add(event.event_digest)
            previous = event.event_digest
            expected_sequence += 1


def _event_digest(canonical_payload: bytes) -> str:
    return hashlib.sha256(canonical_payload).hexdigest()


def _build_event(
    *,
    sequence: int,
    previous_event_digest: str,
    event_type: AuditEventType,
    workspace_id: UUID,
    actor_id: str,
    occurred_at: str,
    object_refs: tuple[AuditObjectRef, ...],
    metadata: tuple[tuple[str, str], ...],
) -> AuditEvent:
    event_without_identity = AuditEvent(
        event_id="",
        event_digest="",
        chain_format_version=AUDIT_CHAIN_FORMAT_VERSION,
        sequence=sequence,
        event_type=event_type,
        workspace_id=workspace_id,
        actor_id=actor_id,
        occurred_at=occurred_at,
        object_refs=object_refs,
        metadata=metadata,
        previous_event_digest=previous_event_digest,
    )
    digest = _event_digest(event_without_identity.canonical_payload_bytes())
    return AuditEvent(
        event_id=f"{EVENT_ID_PREFIX}{digest}",
        event_digest=digest,
        chain_format_version=AUDIT_CHAIN_FORMAT_VERSION,
        sequence=sequence,
        event_type=event_type,
        workspace_id=workspace_id,
        actor_id=actor_id,
        occurred_at=occurred_at,
        object_refs=object_refs,
        metadata=metadata,
        previous_event_digest=previous_event_digest,
    )


def _event_from_bytes(raw: bytes) -> AuditEvent:
    try:
        document = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError("stored audit event is not canonical ASCII JSON") from error
    if not isinstance(document, dict):
        raise AuditError("stored audit event must be a JSON object")
    expected_members = {
        "actor_id",
        "chain_format_version",
        "event_digest",
        "event_id",
        "event_type",
        "metadata",
        "object_refs",
        "occurred_at",
        "policy_version",
        "previous_event_digest",
        "sequence",
        "workspace_id",
    }
    if set(document) != expected_members:
        raise AuditError("stored audit event members are not the admitted members")
    metadata_raw = document["metadata"]
    if not isinstance(metadata_raw, list):
        raise AuditError("stored audit event metadata must be a JSON array")
    metadata: list[tuple[str, str]] = []
    for pair in metadata_raw:
        if not isinstance(pair, list) or len(pair) != 2:
            raise AuditError("stored audit event metadata member must be a two-element array")
        metadata.append((str(pair[0]), str(pair[1])))
    refs_raw = document["object_refs"]
    if not isinstance(refs_raw, list):
        raise AuditError("stored audit event object references must be a JSON array")
    try:
        object_refs: list[AuditObjectRef] = []
        for reference in refs_raw:
            if not isinstance(reference, dict):
                raise AuditError("stored audit event object reference must be a JSON object")
            object_refs.append(
                AuditObjectRef(
                    object_id=UUID(_document_string(reference, "object_id")),
                    object_type=WorkspaceObjectType(_document_string(reference, "object_type")),
                    object_revision=_document_string(reference, "object_revision"),
                    content_digest=(
                        None
                        if reference.get("content_digest") is None
                        else _document_string(reference, "content_digest")
                    ),
                )
            )
        event = AuditEvent(
            event_id=_document_string(document, "event_id"),
            event_digest=_document_string(document, "event_digest"),
            chain_format_version=_document_integer(document, "chain_format_version"),
            sequence=_document_integer(document, "sequence"),
            event_type=AuditEventType(_document_string(document, "event_type")),
            workspace_id=UUID(_document_string(document, "workspace_id")),
            actor_id=_document_string(document, "actor_id"),
            occurred_at=_document_string(document, "occurred_at"),
            object_refs=tuple(object_refs),
            metadata=tuple(metadata),
            previous_event_digest=_document_string(document, "previous_event_digest"),
        )
    except ValueError as error:
        raise AuditError("stored audit event carries an unadmitted member value") from error
    event.payload_document()
    if event.event_id != f"{EVENT_ID_PREFIX}{event.event_digest}":
        raise AuditChainError("stored audit event identity is not derived from its digest")
    if event.binding().object_revision != event.object_revision:
        raise AuditChainError("stored audit event position does not match its sequence")
    return event


def _document_string(document: dict[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str):
        raise AuditError(f"stored audit member {name!r} must be a string")
    return value


def _document_integer(document: dict[str, object], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditError(f"stored audit member {name!r} must be an integer")
    return value
