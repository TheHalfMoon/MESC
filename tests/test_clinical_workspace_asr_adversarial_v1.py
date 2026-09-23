"""CW-006 adversarial tests for the offline ASR adapter.""

Scope: synthetic fixtures and hostile backend outputs only. Every case must fail
closed with a typed error and must never become Research Core data. Activation:
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
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import asr as asr_mod  # noqa: E402 runtime import
from medscale_workspace.data_class import (  # noqa: E402 runtime import
    DataClass,
    TrustDomain,
    classify,
)
from medscale_workspace.errors import (  # noqa: E402 runtime import
    AsrBackendError,
    AsrConflictError,
    AsrInputError,
    AsrLanguageError,
    AsrManifestError,
    AsrRevisionError,
    AsrTimestampError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.nobackflow import evaluate_flow  # noqa: E402 runtime import

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7de9f9f4-1c3b-40b4-b10f-5b16db71a9fe")
SESSION_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
SESSION_TWO = UUID("2b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
INPUT_ONE = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
ACTOR = "synthetic-operator"
T1 = "2026-09-22T10:00:00+03:00"
T2 = "2026-09-22T10:01:00+03:00"
T3 = "2026-09-22T10:02:00+03:00"
INPUT_REVISION = "chunk-00000001"


def open_store(root: Path) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def open_beta_store(root: Path) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=WORKSPACE_BETA,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def synthetic_audio(sequence: int) -> bytes:
    return f"synthetic-pcm-{sequence:08d}".encode("ascii")


def base_kwargs() -> dict[str, object]:
    return {
        "workspace_id": WORKSPACE_ALPHA,
        "session_id": SESSION_ONE,
        "input_id": INPUT_ONE,
        "input_revision": INPUT_REVISION,
        "audio_bytes": synthetic_audio(1),
        "requested_language": "en",
        "input_occurred_at": T1,
        "result_occurred_at": T2,
        "manifest": asr_mod.expected_manifest(),
        "model_snapshot_present": True,
        "model_snapshot_revision": asr_mod.MODEL_REVISION,
        "trust_remote_code": False,
        "local_files_only": True,
        "allow_download": False,
    }


def drifted_manifest(field: str, value: object) -> asr_mod.AsrManifest:
    base = asr_mod.expected_manifest().to_document()
    base[field] = value
    return asr_mod.AsrManifest.from_document(base)


def test_revision_spectrum_rejected() -> None:
    with pytest.raises(AsrRevisionError):
        drifted_manifest("model_revision", "main")
    with pytest.raises(AsrRevisionError):
        drifted_manifest("model_revision", "latest")
    with pytest.raises(AsrRevisionError):
        drifted_manifest("model_revision", "0" * 40)
    with pytest.raises(AsrRevisionError):
        drifted_manifest("runtime_version", "4.44.0")
    with pytest.raises(AsrRevisionError):
        drifted_manifest("torch_version", "2.12.0")


def test_identity_and_license_drift_rejected() -> None:
    with pytest.raises(AsrManifestError):
        drifted_manifest("model_id", "openai/whisper-large-v3")
    with pytest.raises(AsrManifestError):
        drifted_manifest("model_license", "apache-2.0")
    with pytest.raises(AsrManifestError):
        drifted_manifest("weight_sha256", "0" * 64)
    with pytest.raises(AsrManifestError):
        drifted_manifest("weight_size_bytes", 1617824865)
    with pytest.raises(AsrManifestError):
        drifted_manifest("config_blob", "0" * 40)
    with pytest.raises(AsrManifestError):
        drifted_manifest("tokenizer_blob", "0" * 40)


def test_snapshot_and_flags_rejected() -> None:
    with pytest.raises(AsrRevisionError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), model_snapshot_revision="main"))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), trust_remote_code=True))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), local_files_only=False))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), allow_download=True))


def test_audio_shapes_rejected() -> None:
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), audio_bytes="not-bytes"))
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), audio_bytes=b""))
    oversize = b"x" * 65537  # oversize audio
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), audio_bytes=oversize))


def french_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    one = asr_mod.AsrSegment(
        index=0,
        start_s=0.0,
        end_s=1.0,
        text="transcript francais",
    )
    return ("success", "transcript francais", (one,), "fr", "")


def empty_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    return ("success", "", (), "en", "")


def reasonless_failed_backend(audio: bytes, manifest: object, language: str) -> tuple[object, ...]:
    return ("failed", "", (), "en", "")


def reasonless_partial_backend(audio: bytes, manifest: object, language: str) -> tuple[object, ...]:
    return ("partial", "partial transcript", (), "en", "")


def list_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    return ("success", "text", ["not-a-segment"], "en", "")


def short_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    return ("success", "text", ())


def weird_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    return ("weird", "text", (), "en", "")


def overlap_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    first = asr_mod.AsrSegment(index=0, start_s=0.0, end_s=1.0, text="first")
    second = asr_mod.AsrSegment(index=1, start_s=0.5, end_s=2.0, text="second")
    return ("success", "first second", (first, second), "en", "")


def gap_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    first = asr_mod.AsrSegment(index=0, start_s=0.0, end_s=1.0, text="first")
    third = asr_mod.AsrSegment(index=2, start_s=1.0, end_s=2.0, text="third")
    return ("success", "first third", (first, third), "en", "")


def nan_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    bad = asr_mod.AsrSegment(index=0, start_s=float("nan"), end_s=1.0, text="bad")
    return ("success", "bad", (bad,), "en", "")


def inf_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    bad = asr_mod.AsrSegment(index=0, start_s=0.0, end_s=float("inf"), text="bad")
    return ("success", "bad", (bad,), "en", "")


def reversed_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    bad = asr_mod.AsrSegment(index=0, start_s=2.0, end_s=1.0, text="bad")
    return ("success", "bad", (bad,), "en", "")


def overseg_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    many = tuple(
        asr_mod.AsrSegment(index=i, start_s=float(i), end_s=float(i) + 0.5, text="seg")
        for i in range(257)
    )
    return ("success", "many", many, "en", "")


def longtext_backend(
    audio_bytes: bytes, manifest: object, requested_language: str
) -> tuple[object, ...]:
    big = "y" * 4097  # long text
    one = asr_mod.AsrSegment(index=0, start_s=0.0, end_s=1.0, text=big)
    return ("success", big, (one,), "en", "")


def test_segment_spectrum_rejected() -> None:
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=gap_backend))
    with pytest.raises(AsrTimestampError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=nan_backend))
    with pytest.raises(AsrTimestampError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=inf_backend))
    with pytest.raises(AsrTimestampError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=reversed_backend))
    with pytest.raises(AsrTimestampError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=overlap_backend))


def test_malformed_backends_rejected() -> None:
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=None))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=list_backend))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=short_backend))
    with pytest.raises(AsrBackendError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=weird_backend))


def test_excess_and_long_rejected() -> None:
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=overseg_backend))
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=longtext_backend))


def test_language_smuggling_rejected() -> None:
    with pytest.raises(AsrLanguageError):
        asr_mod.transcribe_synthetic(**dict(base_kwargs(), requested_language="fr"))
    with pytest.raises(AsrLanguageError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=french_backend))


def test_typing_violations_rejected() -> None:
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=empty_backend))
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=reasonless_failed_backend))
    with pytest.raises(AsrInputError):
        asr_mod.transcribe_with_backend(**dict(base_kwargs(), backend=reasonless_partial_backend))


def test_cross_boundary_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        foreign = asr_mod.transcribe_synthetic(
            WORKSPACE_BETA,
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
        with pytest.raises(WorkspaceIsolationError):
            asr_mod.store_transcript(store, trail, foreign, ACTOR, T3)
        with pytest.raises(AsrInputError):
            asr_mod.read_transcript(store, INPUT_ONE)
        other_session = asr_mod.transcript_id_for(WORKSPACE_ALPHA, SESSION_TWO, INPUT_ONE)
        with pytest.raises(AsrInputError):
            asr_mod.read_transcript(store, other_session)


def test_replay_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = asr_mod.transcribe_synthetic(**base_kwargs())
        asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        with pytest.raises(AsrConflictError):
            asr_mod.store_transcript(store, trail, result, ACTOR, T3)


def test_research_core_unreachable(tmp_path: Path) -> None:
    evaluation = evaluate_flow(classify(DataClass.SYNTHETIC), TrustDomain.RESEARCH_CORE)
    assert evaluation.admitted is False
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        result = asr_mod.transcribe_synthetic(**base_kwargs())
        binding = asr_mod.store_transcript(store, trail, result, ACTOR, T3)
        payload = store.get_object(binding)
        assert b"research" not in payload.lower()


def test_malformed_documents_rejected() -> None:
    with pytest.raises(AsrManifestError):
        asr_mod.AsrManifest.from_document({})
    with pytest.raises(AsrInputError):
        asr_mod.AsrResult.from_document({})
    with pytest.raises(AsrInputError):
        asr_mod.AsrSegment.from_document({})
