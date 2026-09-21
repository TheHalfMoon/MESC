"""CW-003 adversarial tests for the provenance and audit spines.

Hostile cases are kept independent of the benign suite: every test here tries to
break a property CW-003 must hold, and each asserts a specific fail-closed outcome.
Nothing here establishes readiness, acceptance or authority.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open; these tests import it at runtime.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_MODULES = WORKSPACE_SRC / "medscale_workspace"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402
from medscale_workspace import (  # noqa: E402
    AuditEventType,
    AuditObjectRef,
    AuditTrail,
    ObjectBinding,
    ObjectWrite,
    ProducerIdentity,
    ProducerKind,
    ProvenanceRecord,
    ReviewState,
    SourceKind,
    SourceRef,
    WorkspaceObjectType,
    WorkspaceStore,
    content_digest_of,
    describe_revision,
    store_with_provenance,
    verify_provenance,
)
from medscale_workspace.audit import (  # noqa: E402
    AUDIT_OBJECT_NAMESPACE,
    EVENT_ID_PREFIX,
    GENESIS_EVENT_DIGEST,
    AuditEvent,
    _build_event,
    _event_digest,
)
from medscale_workspace.errors import (  # noqa: E402
    AuditChainError,
    AuditError,
    AuditReplayError,
    EnvelopeAuthenticationError,
    ObjectNotFoundError,
    ProvenanceError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import InMemoryTestKeyProvider, new_root_secret  # noqa: E402
from medscale_workspace.provenance import _record_from_document  # noqa: E402
from medscale_workspace.store_path import resolve_workspace_store_path  # noqa: E402

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("1a3d7c22-42f4-4b76-9d6f-0c2c8db0f3a1")
NOTE_OBJECT = UUID("2f1b7c8e-6a4d-4f9c-8f1e-5b6a7c8d9e0f")
SENSITIVE_SYNTHETIC_NOTE = b"SYNTHETIC-NOT-REAL:adversarial-audit-fixture"
OCCURRED_AT_ONE = "2026-09-21T18:00:00+03:00"
OCCURRED_AT_TWO = "2026-09-21T18:05:00+03:00"
OCCURRED_AT_THREE = "2026-09-21T18:10:00+03:00"


def note_binding(revision: str = "rev-0001") -> ObjectBinding:
    return ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=NOTE_OBJECT,
        object_type=WorkspaceObjectType.ENCOUNTER,
        object_revision=revision,
    )


def open_store(root: Path, *, root_secret: bytes | None = None) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=InMemoryTestKeyProvider(root_secret or new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def model_producer() -> ProducerIdentity:
    return ProducerIdentity(
        kind=ProducerKind.MODEL,
        identifier="synthetic-local-drafter",
        version="0.0.1-synthetic",
    )


def transcript_source() -> SourceRef:
    return SourceRef(
        kind=SourceKind.TRANSCRIPT_RANGE,
        source_id="synthetic-transcript-0001",
        source_revision="rev-0002",
    )


def raw(store_path: str) -> sqlite3.Connection:
    connection = sqlite3.connect(store_path)
    connection.isolation_level = None
    return connection


def raw_execute(store_path: str, statement: str, parameters: tuple[object, ...] = ()) -> None:
    connection = raw(store_path)
    try:
        connection.execute(statement, parameters)
    finally:
        connection.close()


def seeded_trail(tmp_path: Path, root_secret: bytes) -> tuple[AuditEvent, ...]:
    with open_store(tmp_path, root_secret=root_secret) as store:
        trail = AuditTrail(store)
        trail.append(
            event_type=AuditEventType.WORKSPACE_OPEN,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
        trail.append(
            event_type=AuditEventType.PATIENT_READ,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_TWO,
        )
        trail.append(
            event_type=AuditEventType.WORKSPACE_CLOSE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_THREE,
        )
        return tuple(trail.events())


def store_path_of(tmp_path: Path) -> str:
    return str(resolve_workspace_store_path(str(tmp_path), WORKSPACE_ALPHA))


# ---------------------------------------------------------------------------
# Audit chain attacks
# ---------------------------------------------------------------------------


def test_removing_a_middle_event_breaks_the_chain(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    with open_store(tmp_path, root_secret=root_secret) as store:
        assert store.delete_object(events[1].binding()) is True
        with pytest.raises(AuditChainError):
            AuditTrail(store).verify()


def test_tail_truncation_is_only_detected_with_an_external_anchor(tmp_path: Path) -> None:
    """Recorded limitation: a removed tail event still verifies internally."""

    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    with open_store(tmp_path, root_secret=root_secret) as store:
        assert store.delete_object(events[-1].binding()) is True
        trail = AuditTrail(store)
        unanchored = trail.verify()
        assert unanchored.events_verified == 2
        assert unanchored.head_event_digest == events[1].event_digest
        with pytest.raises(AuditChainError):
            trail.verify(expected_head_event_digest=events[-1].event_digest)
    documented = " ".join(
        (WORKSPACE_MODULES / "audit.py").read_text(encoding="utf-8").lower().split()
    )
    assert "tail" in documented and "retained head digest" in documented


def test_swapping_stored_audit_envelopes_fails_authentication(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    seeded_trail(tmp_path, root_secret)
    store_path = store_path_of(tmp_path)
    connection = raw(store_path)
    try:
        rows = connection.execute(
            "SELECT object_id, envelope FROM objects WHERE object_type = ? ORDER BY object_id",
            (WorkspaceObjectType.AUDIT_EVENT.value,),
        ).fetchall()
    finally:
        connection.close()
    assert len(rows) == 3
    swapped = {str(object_id): bytes(envelope) for object_id, envelope in rows}
    ordered_ids = sorted(swapped)
    first_id, second_id = ordered_ids[0], ordered_ids[1]
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ?",
        (swapped[second_id], first_id),
    )
    with (
        open_store(tmp_path, root_secret=root_secret) as store,
        pytest.raises(EnvelopeAuthenticationError),
    ):
        AuditTrail(store).verify()


def test_replaying_an_event_object_is_refused(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    replay = events[0]
    with open_store(tmp_path, root_secret=root_secret) as store:
        with pytest.raises(StoreConflictError):
            store.put_objects_atomic(
                (
                    ObjectWrite(
                        binding=replay.binding(),
                        payload=replay.canonical_bytes(),
                    ),
                )
            )
        assert AuditTrail(store).verify().events_verified == 3


def test_a_duplicate_sequence_event_is_detected(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    seeded_trail(tmp_path, root_secret)
    forged = _build_event(
        sequence=1,
        previous_event_digest=GENESIS_EVENT_DIGEST,
        event_type=AuditEventType.SECURITY_FAILURE,
        workspace_id=WORKSPACE_ALPHA,
        actor_id="synthetic-adversary",
        occurred_at=OCCURRED_AT_THREE,
        object_refs=(),
        metadata=(),
    )
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=forged.binding(), payload=forged.canonical_bytes()),)
        )
        with pytest.raises(AuditChainError):
            AuditTrail(store).verify()


def test_an_event_identity_not_derived_from_its_digest_is_detected(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    head = events[-1]
    forged_id = f"{EVENT_ID_PREFIX}{hashlib.sha256(b'not-the-event').hexdigest()}"
    forged = AuditEvent(
        event_id=forged_id,
        event_digest=head.event_digest,
        chain_format_version=head.chain_format_version,
        sequence=head.sequence,
        event_type=head.event_type,
        workspace_id=head.workspace_id,
        actor_id=head.actor_id,
        occurred_at=head.occurred_at,
        object_refs=head.object_refs,
        metadata=head.metadata,
        previous_event_digest=head.previous_event_digest,
    )
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic(
            (ObjectWrite(binding=forged.binding(), payload=forged.canonical_bytes()),)
        )
        with pytest.raises((AuditChainError, AuditReplayError)):
            AuditTrail(store).verify()


def test_tampering_with_a_stored_event_payload_fails_closed(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    store_path = store_path_of(tmp_path)
    connection = raw(store_path)
    try:
        row = connection.execute(
            "SELECT envelope FROM objects WHERE object_id = ?",
            (str(events[1].binding().object_id),),
        ).fetchone()
    finally:
        connection.close()
    assert row is not None
    envelope = bytes(row[0])
    raw_execute(
        store_path,
        "UPDATE objects SET envelope = ? WHERE object_id = ?",
        (envelope[:-1], str(events[1].binding().object_id)),
    )
    with (
        open_store(tmp_path, root_secret=root_secret) as store,
        pytest.raises((EnvelopeAuthenticationError, AuditError)),
    ):
        AuditTrail(store).verify()


def test_a_forged_event_document_is_rejected(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    head_document = json.loads(events[-1].canonical_bytes().decode("ascii"))
    head_document["event_type"] = "not_an_admitted_event_type"
    forged_payload = json.dumps(
        head_document, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    forged_binding = ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=uuid5(AUDIT_OBJECT_NAMESPACE, str(head_document["event_id"])),
        object_type=WorkspaceObjectType.AUDIT_EVENT,
        object_revision="audit-00000099",
    )
    with open_store(tmp_path, root_secret=root_secret) as store:
        store.put_objects_atomic((ObjectWrite(binding=forged_binding, payload=forged_payload),))
        with pytest.raises(AuditError):
            AuditTrail(store).verify()


def test_audit_metadata_bounds_are_enforced(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(AuditError):
            trail.append(
                event_type=AuditEventType.POLICY_CHANGE,
                actor_id="synthetic-clinician",
                occurred_at=OCCURRED_AT_ONE,
                metadata=tuple((f"k{index}", "v") for index in range(9)),
            )
        with pytest.raises(AuditError):
            trail.append(
                event_type=AuditEventType.POLICY_CHANGE,
                actor_id="synthetic-clinician",
                occurred_at=OCCURRED_AT_ONE,
                metadata=(("k", "v" * 257),),
            )
        with pytest.raises(AuditError):
            trail.append(
                event_type=AuditEventType.POLICY_CHANGE,
                actor_id="synthetic-clinician",
                occurred_at="",
            )
        with pytest.raises(AuditError):
            trail.append(
                event_type=AuditEventType.POLICY_CHANGE,
                actor_id="",
                occurred_at=OCCURRED_AT_ONE,
            )
        assert trail.verify().events_verified == 0


def test_an_event_for_another_workspace_cannot_be_stored(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        forged = _build_event(
            sequence=1,
            previous_event_digest=GENESIS_EVENT_DIGEST,
            event_type=AuditEventType.WORKSPACE_OPEN,
            workspace_id=WORKSPACE_BETA,
            actor_id="synthetic-adversary",
            occurred_at=OCCURRED_AT_ONE,
            object_refs=(),
            metadata=(),
        )
        with pytest.raises(WorkspaceIsolationError):
            store.put_objects_atomic(
                (ObjectWrite(binding=forged.binding(), payload=forged.canonical_bytes()),)
            )
        assert AuditTrail(store).verify().events_verified == 0


def test_an_event_digest_that_does_not_match_its_payload_is_detected(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    events = seeded_trail(tmp_path, root_secret)
    head = events[-1]
    payload = head.payload_document()
    payload["actor_id"] = "synthetic-other-actor"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert _event_digest(canonical.encode("ascii")) != head.event_digest


# ---------------------------------------------------------------------------
# Provenance attacks
# ---------------------------------------------------------------------------


def test_a_provenance_record_cannot_overwrite_an_existing_one(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        first = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, first, SENSITIVE_SYNTHETIC_NOTE)
        second = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.FINALIZED,
        )
        with pytest.raises(StoreConflictError):
            store_with_provenance(store, second, SENSITIVE_SYNTHETIC_NOTE)
        assert verify_provenance(store, binding).review_state is ReviewState.DRAFT


def test_an_audit_event_cannot_carry_provenance(tmp_path: Path) -> None:
    event_binding = ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=NOTE_OBJECT,
        object_type=WorkspaceObjectType.AUDIT_EVENT,
        object_revision="audit-00000001",
    )
    with pytest.raises(ProvenanceError):
        ProvenanceRecord(
            binding=event_binding,
            content_digest=content_digest_of(SENSITIVE_SYNTHETIC_NOTE),
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        ).validated()


@pytest.mark.parametrize(
    "source_ref",
    [
        SourceRef(kind=SourceKind.IMPORT, source_id="", source_revision="rev-0001"),
        SourceRef(kind=SourceKind.IMPORT, source_id="has space", source_revision="rev-0001"),
        SourceRef(kind=SourceKind.IMPORT, source_id="synthetic", source_revision="r" * 129),
        SourceRef(kind=SourceKind.IMPORT, source_id="synthétique", source_revision="rev-0001"),
    ],
)
def test_malformed_source_identity_is_refused(source_ref: SourceRef) -> None:
    with pytest.raises(ProvenanceError):
        source_ref.validated()


def test_provenance_producer_identity_must_be_declared() -> None:
    with pytest.raises(ProvenanceError):
        ProducerIdentity(kind=ProducerKind.MODEL, identifier="", version="1").validated()
    with pytest.raises(ProvenanceError):
        describe_revision(
            binding=note_binding(),
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=ProducerIdentity(
                kind=ProducerKind.MODEL,
                identifier="synthetic-local-drafter",
                version="",
            ),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )


def test_provenance_digest_field_is_admitted_only_as_sha256(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        record = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, record, SENSITIVE_SYNTHETIC_NOTE)
        forged_payload = json.loads(record.canonical_bytes().decode("ascii"))
        forged_payload["content_digest"] = hashlib.sha256(SENSITIVE_SYNTHETIC_NOTE).hexdigest()
        with pytest.raises(ProvenanceError):
            _record_from_document(forged_payload)


def test_audit_object_refs_reject_unadmitted_types_and_digests() -> None:
    unadmitted_type: Any = "Encounter"
    with pytest.raises(AuditError):
        AuditObjectRef(
            object_id=NOTE_OBJECT,
            object_type=unadmitted_type,
            object_revision="rev-0001",
        ).validated()
    with pytest.raises(AuditError):
        AuditObjectRef(
            object_id=NOTE_OBJECT,
            object_type=WorkspaceObjectType.ENCOUNTER,
            object_revision="rev-0001",
            content_digest=hashlib.sha256(SENSITIVE_SYNTHETIC_NOTE).hexdigest(),
        ).validated()
    with pytest.raises(AuditError):
        AuditObjectRef(
            object_id=NOTE_OBJECT,
            object_type=WorkspaceObjectType.ENCOUNTER,
            object_revision="",
        ).validated()


def test_audit_deletion_requires_existing_content(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(ObjectNotFoundError):
            trail.record_object_deletion(
                binding=note_binding(),
                actor_id="synthetic-clinician",
                occurred_at=OCCURRED_AT_ONE,
            )
        assert trail.verify().events_verified == 0


def test_provenance_and_audit_do_not_leak_payload_into_documents(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        record = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, record, SENSITIVE_SYNTHETIC_NOTE)
        event = AuditTrail(store).record_object_write(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
    for document in (record.canonical_bytes(), event.canonical_bytes()):
        assert SENSITIVE_SYNTHETIC_NOTE not in document
        assert b"SYNTHETIC-NOT-REAL:" not in document
