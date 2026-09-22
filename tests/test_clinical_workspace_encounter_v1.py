"""CW-005 focused acceptance tests for synthetic encounter session lifecycle.

Scope: synthetic fixtures only. No microphone, no network, no real patient data.
Every timestamp below is a supplied literal because the Workspace package
imports no clock. Activation: Issue 477; dependencies CW-003 and CW-004 closed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402
from medscale_workspace import (  # noqa: E402
    AuditEventType,
    AuditTrail,
    WorkspaceObjectType,
    WorkspaceStore,
    synthetic_data_class_value,
    workspace_snapshot,
)
from medscale_workspace import encounter as encounter_mod  # noqa: E402
from medscale_workspace.encounter import (  # noqa: E402
    EncounterState,
    SessionRecord,
    append_chunk,
    create_session,
    delete_session,
    grant_consent,
    list_chunks,
    pause_capture,
    read_session,
    recover_session,
    resume_capture,
    start_capture,
    stop_capture,
)
from medscale_workspace.errors import (  # noqa: E402
    EncounterConsentError,
)
from medscale_workspace.keyprovider import (  # noqa: E402
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402
    read_provenance,
    verify_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ENCOUNTER_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
ENCOUNTER_TWO = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
ACTOR = "synthetic-operator"
T1 = "2026-09-22T10:00:00+03:00"
T2 = "2026-09-22T10:01:00+03:00"
T3 = "2026-09-22T10:02:00+03:00"
T4 = "2026-09-22T10:03:00+03:00"
T5 = "2026-09-22T10:04:00+03:00"
T6 = "2026-09-22T10:05:00+03:00"
T7 = "2026-09-22T10:06:00+03:00"
T8 = "2026-09-22T10:07:00+03:00"
T9 = "2026-09-22T10:08:00+03:00"


def open_store(root: Path) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def synthetic_audio(sequence: int) -> bytes:
    return f"synthetic-pcm-{sequence:08d}".encode("ascii")


def ready_session(
    store: WorkspaceStore, trail: AuditTrail, key: str = "session-001"
) -> SessionRecord:
    created = create_session(
        store,
        trail,
        encounter_id=ENCOUNTER_ONE,
        session_key=key,
        actor_id=ACTOR,
        occurred_at=T1,
    )
    return grant_consent(
        store,
        trail,
        session_id=created.session_id,
        actor_id=ACTOR,
        occurred_at=T2,
    )


def started_session(
    store: WorkspaceStore, trail: AuditTrail, key: str = "session-001"
) -> SessionRecord:
    ready = ready_session(store, trail, key=key)
    return start_capture(
        store,
        trail,
        session_id=ready.session_id,
        actor_id=ACTOR,
        occurred_at=T3,
    )


def test_session_identity_is_stable_and_deterministic(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = create_session(
            store,
            trail,
            encounter_id=ENCOUNTER_ONE,
            session_key="stable-001",
            actor_id=ACTOR,
            occurred_at=T1,
        )
        same = encounter_mod.session_id_for(WORKSPACE_ALPHA, ENCOUNTER_ONE, "stable-001")
        other_key = encounter_mod.session_id_for(WORKSPACE_ALPHA, ENCOUNTER_ONE, "stable-002")
        other_enc = encounter_mod.session_id_for(WORKSPACE_ALPHA, ENCOUNTER_TWO, "stable-001")
        assert first.session_id == same
        assert other_key != first.session_id
        assert other_enc != first.session_id
        assert first.state is EncounterState.CONSENT_PENDING
        assert first.chunk_count == 0
        assert first.revision == "session-00000001"
        assert first.is_synthetic is True
        assert first.capture_mode == "simulated"
        assert first.data_class_value == synthetic_data_class_value()


def test_consent_required_before_simulated_capture(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        created = create_session(
            store,
            trail,
            encounter_id=ENCOUNTER_ONE,
            session_key="consent-001",
            actor_id=ACTOR,
            occurred_at=T1,
        )
        with pytest.raises(EncounterConsentError):
            start_capture(
                store,
                trail,
                session_id=created.session_id,
                actor_id=ACTOR,
                occurred_at=T2,
            )
        with pytest.raises(EncounterConsentError):
            append_chunk(
                store,
                trail,
                session_id=created.session_id,
                audio_bytes=synthetic_audio(1),
                actor_id=ACTOR,
                occurred_at=T2,
            )
        granted = grant_consent(
            store,
            trail,
            session_id=created.session_id,
            actor_id=ACTOR,
            occurred_at=T2,
        )
        assert granted.state is EncounterState.READY
        assert granted.consent.recording is True
        assert granted.consent.processing is True
        started = start_capture(
            store,
            trail,
            session_id=created.session_id,
            actor_id=ACTOR,
            occurred_at=T3,
        )
        assert started.state is EncounterState.CAPTURING


def test_deterministic_start_pause_resume_stop(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="lifecycle-001")
        assert started.state is EncounterState.CAPTURING
        paused = pause_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T4,
        )
        assert paused.state is EncounterState.PAUSED
        resumed = resume_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T5,
        )
        assert resumed.state is EncounterState.CAPTURING
        stopped = stop_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T6,
        )
        assert stopped.state is EncounterState.STOPPED
        assert stopped.revision_counter == started.revision_counter + 3
        current = read_session(store, started.session_id)
        assert current.state is EncounterState.STOPPED
        assert current.chunk_count == 0


def test_chunk_identity_order_digests_and_retention(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="chunks-001")
        first_session, first_chunk = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        assert first_chunk.sequence == 1
        assert first_chunk.revision == "chunk-00000001"
        assert first_session.chunk_count == 1
        assert first_session.last_chunk_digest == first_chunk.audio_digest
        second_session, second_chunk = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(2),
            actor_id=ACTOR,
            occurred_at=T5,
        )
        assert second_chunk.sequence == 2
        assert second_chunk.chunk_id != first_chunk.chunk_id
        assert second_session.chunk_count == 2
        assert second_session.last_chunk_digest == second_chunk.audio_digest
        assert second_session.last_chunk_digest != first_chunk.audio_digest
        assert second_chunk.retention == second_session.retention
        assert second_chunk.retention.retention_class == "session-scoped"
        assert second_chunk.retention.retention_version == 1
        chunks = list_chunks(store, started.session_id)
        assert [item.sequence for item in chunks] == [1, 2]
        assert chunks[0].audio_bytes == synthetic_audio(1)
        assert chunks[1].audio_bytes == synthetic_audio(2)
        expected_first = encounter_mod.chunk_id_for(started.session_id, 1)
        expected_second = encounter_mod.chunk_id_for(started.session_id, 2)
        assert chunks[0].chunk_id == expected_first
        assert chunks[1].chunk_id == expected_second


def test_crash_recovery_fixture(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="recovery-001")
        empty = recover_session(store, started.session_id)
        assert empty.chunks_verified == 0
        assert empty.chunk_count == 0
        _, _ = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        _, _ = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(2),
            actor_id=ACTOR,
            occurred_at=T5,
        )
        paused = pause_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T6,
        )
        assert paused.state is EncounterState.PAUSED
        report = recover_session(store, started.session_id)
        assert report.chunk_count == 2
        assert report.chunks_verified == 2
        assert report.last_chunk_digest is not None
        stopped = stop_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T7,
        )
        assert stopped.state is EncounterState.STOPPED
        final = recover_session(store, started.session_id)
        assert final.chunk_count == 2
        assert final.chunks_verified == 2


def test_provenance_present_for_session_and_chunks(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="prov-001")
        _, chunk = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        session = read_session(store, started.session_id)
        session_binding = encounter_mod.session_binding(
            session.workspace_id, session.session_id, session.revision_counter
        )
        chunk_binding = encounter_mod.chunk_binding(
            chunk.workspace_id, chunk.chunk_id, chunk.sequence
        )
        session_prov = read_provenance(store, session_binding)
        chunk_prov = read_provenance(store, chunk_binding)
        assert session_prov.binding == session_binding
        assert chunk_prov.binding == chunk_binding
        verify_provenance(store, session_binding)
        verify_provenance(store, chunk_binding)


def test_audit_events_cover_lifecycle(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="audit-001")
        _, _ = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        paused = pause_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T5,
        )
        assert paused.state is EncounterState.PAUSED
        resumed = resume_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T6,
        )
        assert resumed.state is EncounterState.CAPTURING
        stopped = stop_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T7,
        )
        assert stopped.state is EncounterState.STOPPED
        events = trail.events()
        kinds = [event.event_type for event in events]
        assert AuditEventType.OBJECT_CREATE in kinds
        assert AuditEventType.POLICY_CHANGE in kinds
        assert AuditEventType.CAPTURE_START in kinds
        assert AuditEventType.CAPTURE_PAUSE in kinds
        assert AuditEventType.CAPTURE_RESUME in kinds
        assert AuditEventType.CAPTURE_STOP in kinds
        report = trail.verify()
        assert report.events_verified == len(events)


def test_delete_cascade_removes_session_and_chunks(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="delete-001")
        _, _ = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        _, _ = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(2),
            actor_id=ACTOR,
            occurred_at=T5,
        )
        stopped = stop_capture(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T6,
        )
        assert stopped.chunk_count == 2
        removed = delete_session(
            store,
            trail,
            session_id=started.session_id,
            actor_id=ACTOR,
            occurred_at=T7,
        )
        assert removed > 0
        sessions = [
            revision
            for object_id, revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_SESSION)
            if object_id == started.session_id
        ]
        assert sessions == []
        chunks = [
            revision
            for object_id, revision in store.object_revisions(WorkspaceObjectType.ENCOUNTER_CHUNK)
        ]
        assert chunks == []
        events = trail.events()
        assert any(event.event_type == AuditEventType.OBJECT_DELETE for event in events)


def test_no_microphone_and_synthetic_only(tmp_path: Path) -> None:
    snapshot = workspace_snapshot()
    assert snapshot["capabilities"]["microphone"] is False
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        started = started_session(store, trail, key="synthetic-001")
        session = read_session(store, started.session_id)
        assert session.is_synthetic is True
        assert session.capture_mode == "simulated"
        assert session.data_class_value == synthetic_data_class_value()
        _, chunk = append_chunk(
            store,
            trail,
            session_id=started.session_id,
            audio_bytes=synthetic_audio(1),
            actor_id=ACTOR,
            occurred_at=T4,
        )
        assert chunk.is_synthetic is True
        assert chunk.capture_mode == "simulated"
        assert chunk.data_class_value == synthetic_data_class_value()
