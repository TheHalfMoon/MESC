"""CW-006 focused acceptance tests for the offline ASR adapter.""

Scope: synthetic fixtures and mock backend outputs only. No model download, no
network, no microphone, no real patient audio. Every timestamp below is a
supplied literal because the Workspace package imports no clock. Activation:
Issue 480 with ADR-0040 accepted. No quality claim follows from mock outputs.
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

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditEventType,
    AuditTrail,
    WorkspaceStore,
    workspace_snapshot,
)
from medscale_workspace import asr as asr_mod  # noqa: E402 runtime import
from medscale_workspace import encounter as encounter_mod  # noqa: E402 runtime import
from medscale_workspace.asr import (  # noqa: E402 runtime import
    AsrResult,
    AsrStatus,
)
from medscale_workspace.encounter import (  # noqa: E402 runtime import
    EncounterState,
)
from medscale_workspace.errors import (  # noqa: E402 runtime import
    AsrBackendError,
    AsrModelUnavailableError,
    AsrRevisionError,
    AsrTimestampError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    read_provenance,
    verify_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
SESSION_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
INPUT_ONE = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
ACTOR = "synthetic-operator"
T1 = "2026-09-22T10:00:00+03:00"
T2 = "2026-09-22T10:01:00+03:00"
T3 = "2026-09-22T10:02:00+03:00"
T4 = "2026-09-22T10:03:00+03:00"
T5 = "2026-09-22T10:04:00+03:00"
INPUT_REVISION = "chunk-00000001"


def open_store(root: Path) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def synthetic_audio(sequence: int) -> bytes:
    return f"synthetic-pcm-{sequence:08d}".encode("ascii")


def drifted_manifest(field: str, value: object) -> asr_mod.AsrManifest:
    base = asr_mod.expected_manifest().to_document()
    base[field] = value
    return asr_mod.AsrManifest.from_document(base)


def success_result(store: WorkspaceStore, trail: AuditTrail) -> AsrResult:
    return asr_mod.transcribe_synthetic(
        WORKSPACE_ALPHA,
        SESSION_ONE,
        INPUT_ONE,
        INPUT_REVISION,
        synthetic_audio(1),
        "en",
        T1,
        T2,
        asr_mod.expected_manifest(),
        True,
        asr_mod.MODEL_REVISION,
        False,
        True,
        False,
    )


def test_manifest_matches_ratified_identities() -> None:
    manifest = asr_mod.expected_manifest()
    assert manifest.model_id == asr_mod.MODEL_ID
    assert manifest.model_revision == asr_mod.MODEL_REVISION
    assert manifest.model_license == asr_mod.MODEL_LICENSE
    assert manifest.runtime_name == asr_mod.RUNTIME_NAME
    assert manifest.runtime_version == asr_mod.RUNTIME_VERSION
    assert manifest.torch_version == asr_mod.TORCH_VERSION
    assert manifest.weight_sha256 == asr_mod.WEIGHT_SHA256
    assert manifest.weight_size_bytes == asr_mod.WEIGHT_SIZE_BYTES
    assert manifest.trust_remote_code is False
    assert manifest.local_files_only is True
    assert manifest.allow_download is False
    assert asr_mod.verify_manifest(manifest) == manifest


def test_mutable_revision_rejected(tmp_path: Path) -> None:
    with pytest.raises(AsrRevisionError):
        drifted_manifest("model_revision", "main")
    with pytest.raises(AsrRevisionError):
        drifted_manifest("model_revision", "latest")


def test_synthetic_success_binds_identities(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = success_result(store, trail)
        assert result.status is AsrStatus.SUCCESS
        assert result.transcript != ""
        assert "synthetic transcript en" in result.transcript
        assert result.requested_language == "en"
        assert result.detected_language == "en"
        assert result.model_id == asr_mod.MODEL_ID
        assert result.model_revision == asr_mod.MODEL_REVISION
        assert result.runtime_name == asr_mod.RUNTIME_NAME
        assert result.runtime_version == asr_mod.RUNTIME_VERSION
        assert result.input_occurred_at == T1
        assert result.result_occurred_at == T2
        assert len(result.segments) == 1  # one segment
        segment = result.segments[0]
        assert segment.index == 0  # first index
        assert segment.start_s == 0.0  # zero start
        assert segment.end_s > 0.0
        assert segment.text == result.transcript


def test_store_provenance_and_audit(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = success_result(store, trail)
        binding = asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        assert binding.object_revision == asr_mod.TRANSCRIPT_REVISION
        stored = read_provenance(store, binding)
        assert stored.binding == binding
        verify_provenance(store, binding)
        events = trail.events()
        kinds = [event.event_type for event in events]
        assert AuditEventType.TRANSCRIPT_CREATE in kinds
        report = trail.verify()
        assert report.events_verified == len(events)


def test_read_returns_stored_result(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = success_result(store, trail)
        asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        transcript_id = asr_mod.transcript_id_for(WORKSPACE_ALPHA, SESSION_ONE, INPUT_ONE)
        loaded = asr_mod.read_transcript(store, transcript_id)
        assert loaded.transcript == result.transcript
        assert loaded.session_id == SESSION_ONE
        assert loaded.input_id == INPUT_ONE
        assert loaded.status is AsrStatus.SUCCESS


def test_missing_snapshot_fails_closed(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        AuditTrail(store)
        with pytest.raises(AsrModelUnavailableError):
            asr_mod.transcribe_synthetic(
                WORKSPACE_ALPHA,
                SESSION_ONE,
                INPUT_ONE,
                INPUT_REVISION,
                synthetic_audio(1),
                "en",
                T1,
                T2,
                asr_mod.expected_manifest(),
                False,
                asr_mod.MODEL_REVISION,
                False,
                True,
                False,
            )


def test_revision_mismatch_fails_closed(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        AuditTrail(store)
        with pytest.raises(AsrRevisionError):
            asr_mod.transcribe_synthetic(
                WORKSPACE_ALPHA,
                SESSION_ONE,
                INPUT_ONE,
                INPUT_REVISION,
                synthetic_audio(1),
                "en",
                T1,
                T2,
                asr_mod.expected_manifest(),
                True,
                "0" * 40,
                False,
                True,
                False,
            )


def test_trust_flags_enforced(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        AuditTrail(store)
        base = {
            "manifest": asr_mod.expected_manifest(),
            "model_snapshot_present": True,
            "model_snapshot_revision": asr_mod.MODEL_REVISION,
            "trust_remote_code": False,
            "local_files_only": True,
            "allow_download": False,
            "workspace_id": WORKSPACE_ALPHA,
            "session_id": SESSION_ONE,
            "input_id": INPUT_ONE,
            "input_revision": INPUT_REVISION,
            "audio_bytes": synthetic_audio(1),
            "requested_language": "en",
            "input_occurred_at": T1,
            "result_occurred_at": T2,
        }
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base, trust_remote_code=True))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base, local_files_only=False))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base, allow_download=True))


def partial_backend(audio_bytes: bytes, manifest: object, requested_language: str) -> tuple:
    return ("partial", "partial transcript", (), requested_language, "decoder stopped early")


def failed_backend(audio_bytes: bytes, manifest: object, requested_language: str) -> tuple:
    return ("failed", "", (), requested_language, "audio too short")


def test_partial_and_failed_typing(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        AuditTrail(store)
        partial = asr_mod.transcribe_with_backend(
            WORKSPACE_ALPHA,
            SESSION_ONE,
            INPUT_ONE,
            INPUT_REVISION,
            synthetic_audio(1),
            "en",
            T1,
            T2,
            asr_mod.expected_manifest(),
            True,
            asr_mod.MODEL_REVISION,
            False,
            True,
            False,
            partial_backend,
        )
        assert partial.status is AsrStatus.PARTIAL
        assert partial.transcript == "partial transcript"
        assert partial.reason == "decoder stopped early"
        failed = asr_mod.transcribe_with_backend(
            WORKSPACE_ALPHA,
            SESSION_ONE,
            INPUT_ONE,
            INPUT_REVISION,
            synthetic_audio(1),
            "en",
            T1,
            T2,
            asr_mod.expected_manifest(),
            True,
            asr_mod.MODEL_REVISION,
            False,
            True,
            False,
            failed_backend,
        )
        assert failed.status is AsrStatus.FAILED
        assert failed.transcript == ""
        assert failed.segments == ()
        assert failed.reason == "audio too short"


def test_audit_carries_no_transcript_text(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = success_result(store, trail)
        asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        for event in trail.events():
            payload_text = event.canonical_bytes().decode("ascii")
            assert result.transcript not in payload_text


def test_malformed_timestamps_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        AuditTrail(store)
        with pytest.raises(AsrTimestampError):
            asr_mod.transcribe_synthetic(
                WORKSPACE_ALPHA,
                SESSION_ONE,
                INPUT_ONE,
                INPUT_REVISION,
                synthetic_audio(1),
                "en",
                "",
                T2,
                asr_mod.expected_manifest(),
                True,
                asr_mod.MODEL_REVISION,
                False,
                True,
                False,
            )


def test_cw005_lifecycle_without_asr(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        created = encounter_mod.create_session(
            store,
            trail,
            encounter_id=SESSION_ONE,
            session_key="cw005-alone",
            actor_id=ACTOR,
            occurred_at=T1,
        )
        granted = encounter_mod.grant_consent(
            store,
            trail,
            session_id=created.session_id,
            actor_id=ACTOR,
            occurred_at=T2,
        )
        started = encounter_mod.start_capture(
            store,
            trail,
            session_id=created.session_id,
            actor_id=ACTOR,
            occurred_at=T3,
        )
        assert granted.state is EncounterState.READY
        assert started.state is EncounterState.CAPTURING
        snapshot = workspace_snapshot()
        assert snapshot["capabilities"]["microphone"] is False


def arabic_backend(audio_bytes: bytes, manifest: object, requested_language: str) -> tuple:
    word = chr(0x0646) + chr(0x0635) + chr(0x0020) + chr(0x0645)
    text = "synthetic ar " + word
    segment = asr_mod.AsrSegment(index=0, start_s=0.0, end_s=1.0, text=text).validated()
    return ("success", text, (segment,), "ar", "")


def test_arabic_text_roundtrip(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = asr_mod.transcribe_with_backend(
            WORKSPACE_ALPHA,
            SESSION_ONE,
            INPUT_ONE,
            INPUT_REVISION,
            synthetic_audio(2),
            "ar",
            T1,
            T2,
            asr_mod.expected_manifest(),
            True,
            asr_mod.MODEL_REVISION,
            False,
            True,
            False,
            arabic_backend,
        )
        assert result.detected_language == "ar"
        asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        transcript_id = asr_mod.transcript_id_for(WORKSPACE_ALPHA, SESSION_ONE, INPUT_ONE)
        loaded = asr_mod.read_transcript(store, transcript_id)
        assert loaded.transcript == result.transcript
        assert loaded.segments[0].text == result.segments[0].text
