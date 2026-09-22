"""Offline ASR adapter for CW-006 with synthetic fixtures only.""

The adapter binds the ADR-0040 model and reference runtime identities in a
deterministic local manifest, verifies that manifest before any transcription,
and fails closed on a missing snapshot, a revision mismatch, or any network,
download, remote, or cloud behavior. Unit tests use a deterministic synthetic
backend with mock outputs only. No quality, language, or clinical claim follows
from mock outputs. Real model load qualification needs permitted fixtures and
is recorded as a separate blocked input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditEventType, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    AsrBackendError,
    AsrConflictError,
    AsrInputError,
    AsrLanguageError,
    AsrManifestError,
    AsrModelUnavailableError,
    AsrRevisionError,
    AsrTimestampError,
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
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION


MODEL_ID = "openai/whisper-large-v3-turbo"
MODEL_REVISION = "41f01f3fe87f28c78e2fbf8b568835947dd65ed9"
MODEL_LICENSE = "mit"
RUNTIME_NAME = "transformers"
RUNTIME_VERSION = "5.16.1"
TORCH_VERSION = "2.13.0"
WEIGHT_FILE = "model.safetensors"
WEIGHT_SHA256 = "542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1"
WEIGHT_SIZE_BYTES = 1617824864
CONFIG_BLOB = "ad2f44ff1ed66e12765b2392dc041469db91a462"
PROCESSOR_BLOB = "931c77a740890c46365c7ae0c9d350ba3cca908f"
TOKENIZER_BLOB = "17456db595adc78a973f97d69d8cb50bc87c0b1c"
TRANSCRIPT_REVISION = "transcript-00000001"
PRODUCER_ID = "cw006-reference-adapter"
PRODUCER_VERSION = "cw006-v1"
MAXIMUM_AUDIO_BYTES = 65536
MAXIMUM_SEGMENTS = 256
MAXIMUM_TEXT_CHARS = 4096
MAXIMUM_TRANSCRIPT_CHARS = 65536
MAXIMUM_REASON_CHARS = 512
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_OCCURRED_AT_CHARS = 64
MAXIMUM_SEGMENT_SECONDS = 30.0
SAMPLES_PER_SECOND = 16000
MUTABLE_REVISIONS = ("main", "latest")
REQUESTED_LANGUAGES = ("ar", "en", "auto")
DETECTED_LANGUAGES = ("ar", "en", "unknown")
ASR_NAMESPACE = UUID("7d3c9e2a-1b4f-4a8e-9c5d-6e7f8a9b0c1d")


class AsrStatus(StrEnum):
    """Typed transcription outcomes, success and partial and failed."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AsrManifest:
    """The deterministic local artifact manifest bound to the ADR identities."""

    model_id: str
    model_revision: str
    model_license: str
    runtime_name: str
    runtime_version: str
    torch_version: str
    weight_file: str
    weight_sha256: str
    weight_size_bytes: int
    config_blob: str
    processor_blob: str
    tokenizer_blob: str
    trust_remote_code: bool
    local_files_only: bool
    allow_download: bool

    def validated(self):
        """Fail closed unless every member matches the expected identities."""
        if self.model_id != MODEL_ID:
            raise AsrManifestError("the manifest model id is not admitted here")
        if self.model_revision in MUTABLE_REVISIONS:
            raise AsrRevisionError("a mutable model revision never satisfies the manifest")
        if self.model_revision != MODEL_REVISION:
            raise AsrRevisionError("the manifest model revision is mismatched")
        if self.model_license != MODEL_LICENSE:
            raise AsrManifestError("the manifest model license is not admitted here")
        if self.runtime_name != RUNTIME_NAME:
            raise AsrRevisionError("the manifest runtime name is mismatched")
        if self.runtime_version != RUNTIME_VERSION:
            raise AsrRevisionError("the manifest runtime version is mismatched")
        if self.torch_version != TORCH_VERSION:
            raise AsrRevisionError("the manifest torch version is mismatched")
        if self.weight_file != WEIGHT_FILE:
            raise AsrManifestError("the manifest weight file is not admitted here")
        _admit_hex_digest(self.weight_sha256, 64, "weight sha256")
        if self.weight_sha256 != WEIGHT_SHA256:
            raise AsrManifestError("the manifest weight digest is mismatched")
        if not isinstance(self.weight_size_bytes, int) or isinstance(self.weight_size_bytes, bool):
            raise AsrManifestError("the manifest weight size must be an integer")
        if self.weight_size_bytes != WEIGHT_SIZE_BYTES:
            raise AsrManifestError("the manifest weight size is mismatched")
        _admit_hex_digest(self.config_blob, 40, "config blob")
        if self.config_blob != CONFIG_BLOB:
            raise AsrManifestError("the manifest config identity is mismatched")
        _admit_hex_digest(self.processor_blob, 40, "processor blob")
        if self.processor_blob != PROCESSOR_BLOB:
            raise AsrManifestError("the manifest processor identity is mismatched")
        _admit_hex_digest(self.tokenizer_blob, 40, "tokenizer blob")
        if self.tokenizer_blob != TOKENIZER_BLOB:
            raise AsrManifestError("the manifest tokenizer identity is mismatched")
        if self.trust_remote_code is not False:
            raise AsrManifestError("the manifest must forbid remote code")
        if self.local_files_only is not True:
            raise AsrManifestError("the manifest must require local files only")
        if self.allow_download is not False:
            raise AsrManifestError("the manifest must forbid automatic download")
        return self

    def to_document(self):
        """Return the canonical manifest document."""
        admitted = self.validated()
        return {
            "allow_download": admitted.allow_download,
            "config_blob": admitted.config_blob,
            "local_files_only": admitted.local_files_only,
            "model_id": admitted.model_id,
            "model_license": admitted.model_license,
            "model_revision": admitted.model_revision,
            "processor_blob": admitted.processor_blob,
            "runtime_name": admitted.runtime_name,
            "runtime_version": admitted.runtime_version,
            "tokenizer_blob": admitted.tokenizer_blob,
            "torch_version": admitted.torch_version,
            "trust_remote_code": admitted.trust_remote_code,
            "weight_file": admitted.weight_file,
            "weight_sha256": admitted.weight_sha256,
            "weight_size_bytes": admitted.weight_size_bytes,
        }

    def canonical_bytes(self):
        """Return the deterministic ASCII encoding of this manifest."""
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        """Re-admit a serialized manifest, refusing any drifted member."""
        if not isinstance(document, dict):
            raise AsrManifestError("a stored manifest must be a JSON object")
        expected = {
            "allow_download",
            "config_blob",
            "local_files_only",
            "model_id",
            "model_license",
            "model_revision",
            "processor_blob",
            "runtime_name",
            "runtime_version",
            "tokenizer_blob",
            "torch_version",
            "trust_remote_code",
            "weight_file",
            "weight_sha256",
            "weight_size_bytes",
        }
        if set(document) != expected:
            raise AsrManifestError("a stored manifest carries unadmitted members")
        return AsrManifest(
            model_id=_string_member(document, "model_id"),
            model_revision=_string_member(document, "model_revision"),
            model_license=_string_member(document, "model_license"),
            runtime_name=_string_member(document, "runtime_name"),
            runtime_version=_string_member(document, "runtime_version"),
            torch_version=_string_member(document, "torch_version"),
            weight_file=_string_member(document, "weight_file"),
            weight_sha256=_string_member(document, "weight_sha256"),
            weight_size_bytes=_integer_member(document, "weight_size_bytes"),
            config_blob=_string_member(document, "config_blob"),
            processor_blob=_string_member(document, "processor_blob"),
            tokenizer_blob=_string_member(document, "tokenizer_blob"),
            trust_remote_code=_bool_member(document, "trust_remote_code"),
            local_files_only=_bool_member(document, "local_files_only"),
            allow_download=_bool_member(document, "allow_download"),
        ).validated()


def expected_manifest():
    """Return the manifest bound to the ratified ADR identities."""
    return AsrManifest(
        model_id=MODEL_ID,
        model_revision=MODEL_REVISION,
        model_license=MODEL_LICENSE,
        runtime_name=RUNTIME_NAME,
        runtime_version=RUNTIME_VERSION,
        torch_version=TORCH_VERSION,
        weight_file=WEIGHT_FILE,
        weight_sha256=WEIGHT_SHA256,
        weight_size_bytes=WEIGHT_SIZE_BYTES,
        config_blob=CONFIG_BLOB,
        processor_blob=PROCESSOR_BLOB,
        tokenizer_blob=TOKENIZER_BLOB,
        trust_remote_code=False,
        local_files_only=True,
        allow_download=False,
    ).validated()


def verify_manifest(manifest):
    """Fail closed unless the manifest matches the expected identities."""
    if not isinstance(manifest, AsrManifest):
        raise AsrManifestError("a manifest must be an AsrManifest instance")
    return manifest.validated()


@dataclass(frozen=True, slots=True)
class AsrSegment:
    """One validated transcript segment with preserved timestamps."""

    index: int
    start_s: float
    end_s: float
    text: str

    def validated(self):
        """Fail closed unless the segment identity, times, and text are admitted."""
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise AsrInputError("a segment index must be an integer")
        if self.index < 0:
            raise AsrInputError("a segment index is out of range")
        start = _admit_seconds(self.start_s, "segment start")
        end = _admit_seconds(self.end_s, "segment end")
        if start < 0.0:
            raise AsrTimestampError("a segment start must not be negative")
        if end <= start:
            raise AsrTimestampError("a segment end must be after its start")
        if end - start > MAXIMUM_SEGMENT_SECONDS:
            raise AsrTimestampError("a segment exceeds the admitted duration")
        text = _admit_text(self.text, MAXIMUM_TEXT_CHARS, "segment text")
        return AsrSegment(index=self.index, start_s=start, end_s=end, text=text)

    def to_document(self):
        """Return the canonical segment document."""
        admitted = self.validated()
        return {
            "end_s": admitted.end_s,
            "index": admitted.index,
            "start_s": admitted.start_s,
            "text": admitted.text,
        }

    @staticmethod
    def from_document(document):
        """Re-admit a serialized segment, refusing any drifted member."""
        if not isinstance(document, dict):
            raise AsrInputError("a stored segment must be a JSON object")
        expected = {"end_s", "index", "start_s", "text"}
        if set(document) != expected:
            raise AsrInputError("a stored segment carries unadmitted members")
        return AsrSegment(
            index=_integer_member(document, "index"),
            start_s=_number_member(document, "start_s"),
            end_s=_number_member(document, "end_s"),
            text=_string_member(document, "text"),
        ).validated()


@dataclass(frozen=True, slots=True)
class AsrResult:
    """One validated transcription outcome bound to its input and identities."""

    workspace_id: UUID
    session_id: UUID
    input_id: UUID
    input_revision: str
    status: AsrStatus
    transcript: str
    segments: tuple
    requested_language: str
    detected_language: str
    model_id: str
    model_revision: str
    runtime_name: str
    runtime_version: str
    input_occurred_at: str
    result_occurred_at: str
    reason: str

    def validated(self):
        """Fail closed unless the result typing and bindings are admitted."""
        if not isinstance(self.workspace_id, UUID):
            raise AsrInputError("a workspace id must be a UUID value")
        if not isinstance(self.session_id, UUID):
            raise AsrInputError("a session id must be a UUID value")
        if not isinstance(self.input_id, UUID):
            raise AsrInputError("an input id must be a UUID value")
        revision = _admit_input_revision(self.input_revision)
        if not isinstance(self.status, AsrStatus):
            raise AsrInputError("a result status must be an admitted status")
        requested = _admit_requested_language(self.requested_language)
        detected = _admit_detected_language(self.detected_language)
        input_at = _admit_occurred_at(self.input_occurred_at)
        result_at = _admit_occurred_at(self.result_occurred_at)
        if self.model_id != MODEL_ID:
            raise AsrRevisionError("the result model id is not admitted here")
        if self.model_revision != MODEL_REVISION:
            raise AsrRevisionError("the result model revision is mismatched")
        if self.runtime_name != RUNTIME_NAME:
            raise AsrRevisionError("the result runtime name is mismatched")
        if self.runtime_version != RUNTIME_VERSION:
            raise AsrRevisionError("the result runtime version is mismatched")
        if not isinstance(self.segments, tuple):
            raise AsrInputError("result segments must be a tuple")
        if len(self.segments) > MAXIMUM_SEGMENTS:
            raise AsrInputError("a result carries too many segments")
        checked = tuple(segment.validated() for segment in self.segments)
        if self.status is AsrStatus.SUCCESS:
            if self.reason != "":
                raise AsrInputError("a success must not carry a reason")
            transcript = _admit_text(self.transcript, MAXIMUM_TRANSCRIPT_CHARS, "transcript")
            if len(checked) < 1:
                raise AsrInputError("a success must carry at least one segment")
        elif self.status is AsrStatus.PARTIAL:
            reason = _admit_reason(self.reason)
            transcript = _admit_text(self.transcript, MAXIMUM_TRANSCRIPT_CHARS, "transcript")
        else:
            reason = _admit_reason(self.reason)
            if self.transcript != "":
                raise AsrInputError("a failure must not carry transcript text")
            if len(checked) != 0:
                raise AsrInputError("a failure must not carry segments")
            transcript = ""
        _check_segment_order(checked)
        if self.status is AsrStatus.SUCCESS:
            reason = ""
        return AsrResult(
            workspace_id=self.workspace_id,
            session_id=self.session_id,
            input_id=self.input_id,
            input_revision=revision,
            status=self.status,
            transcript=transcript,
            segments=checked,
            requested_language=requested,
            detected_language=detected,
            model_id=self.model_id,
            model_revision=self.model_revision,
            runtime_name=self.runtime_name,
            runtime_version=self.runtime_version,
            input_occurred_at=input_at,
            result_occurred_at=result_at,
            reason=reason,
        )

    def to_document(self):
        """Return the canonical transcript document."""
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "detected_language": admitted.detected_language,
            "input_id": str(admitted.input_id),
            "input_occurred_at": admitted.input_occurred_at,
            "input_revision": admitted.input_revision,
            "model_id": admitted.model_id,
            "model_revision": admitted.model_revision,
            "policy_version": POLICY_VERSION,
            "reason": admitted.reason,
            "requested_language": admitted.requested_language,
            "result_occurred_at": admitted.result_occurred_at,
            "runtime_name": admitted.runtime_name,
            "runtime_version": admitted.runtime_version,
            "segments": [segment.to_document() for segment in admitted.segments],
            "session_id": str(admitted.session_id),
            "status": admitted.status.value,
            "transcript": admitted.transcript,
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        """Return the deterministic ASCII encoding of this result."""
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        """Re-admit a serialized result, refusing any drifted member."""
        if not isinstance(document, dict):
            raise AsrInputError("a stored transcript must be a JSON object")
        expected = {
            "data_class",
            "detected_language",
            "input_id",
            "input_occurred_at",
            "input_revision",
            "model_id",
            "model_revision",
            "policy_version",
            "reason",
            "requested_language",
            "result_occurred_at",
            "runtime_name",
            "runtime_version",
            "segments",
            "session_id",
            "status",
            "transcript",
            "workspace_id",
        }
        if set(document) != expected:
            raise AsrInputError("a stored transcript carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise AsrInputError("a stored transcript data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise AsrInputError("a stored transcript policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            session_id = UUID(str(document["session_id"]))
            input_id = UUID(str(document["input_id"]))
            status = AsrStatus(str(document["status"]))
        except ValueError as error:
            raise AsrInputError("a stored transcript identity is not admitted") from error
        raw_segments = document["segments"]
        if not isinstance(raw_segments, list):
            raise AsrInputError("stored segments must be a JSON array")
        segments = tuple(AsrSegment.from_document(item) for item in raw_segments)
        return AsrResult(
            workspace_id=workspace_id,
            session_id=session_id,
            input_id=input_id,
            input_revision=_string_member(document, "input_revision"),
            status=status,
            transcript=_string_member(document, "transcript"),
            segments=segments,
            requested_language=_string_member(document, "requested_language"),
            detected_language=_string_member(document, "detected_language"),
            model_id=_string_member(document, "model_id"),
            model_revision=_string_member(document, "model_revision"),
            runtime_name=_string_member(document, "runtime_name"),
            runtime_version=_string_member(document, "runtime_version"),
            input_occurred_at=_string_member(document, "input_occurred_at"),
            result_occurred_at=_string_member(document, "result_occurred_at"),
            reason=_string_member(document, "reason"),
        ).validated()


def transcript_id_for(workspace_id, session_id, input_id):
    """Return the deterministic transcript identity for one input."""
    if not isinstance(workspace_id, UUID):
        raise AsrInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise AsrInputError("a session id must be a UUID value")
    if not isinstance(input_id, UUID):
        raise AsrInputError("an input id must be a UUID value")
    return uuid5(ASR_NAMESPACE, f"{workspace_id}:{session_id}:{input_id}")


def transcript_binding(workspace_id, transcript_id):
    """Return the store binding of one transcript revision."""
    if not isinstance(workspace_id, UUID):
        raise AsrInputError("a workspace id must be a UUID value")
    if not isinstance(transcript_id, UUID):
        raise AsrInputError("a transcript id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=transcript_id,
        object_type=WorkspaceObjectType.ASR_TRANSCRIPT,
        object_revision=TRANSCRIPT_REVISION,
    )


def transcript_payload_bytes(result):
    """Return the canonical storage payload of one result."""
    if not isinstance(result, AsrResult):
        raise AsrInputError("a transcript payload needs an AsrResult instance")
    return _canonical_bytes(result.to_document())


def transcript_from_document(document):
    """Re-admit a serialized transcript document."""
    return AsrResult.from_document(document)


def _canonical_bytes(document):
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return encoded.encode("ascii")


def _admit_hex_digest(raw, length, label):
    if not isinstance(raw, str):
        raise AsrManifestError(f"{label} must be a string")
    if len(raw) != length:
        raise AsrManifestError(f"{label} must carry the admitted length")
    for character in raw:
        if character not in "0123456789abcdef":
            raise AsrManifestError(f"{label} must be lowercase hex")
    return raw


def _string_member(document, name):
    value = document.get(name)
    if not isinstance(value, str):
        raise AsrManifestError(f"stored member {name} must be a string")
    return value


def _integer_member(document, name):
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise AsrManifestError(f"stored member {name} must be an integer")
    return value


def _bool_member(document, name):
    value = document.get(name)
    if not isinstance(value, bool):
        raise AsrManifestError(f"stored member {name} must be a boolean")
    return value


def _number_member(document, name):
    value = document.get(name)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AsrInputError(f"stored member {name} must be a number")
    return value


def _admit_seconds(raw, label):
    if not isinstance(raw, (int, float)) or isinstance(raw, bool):
        raise AsrTimestampError(f"{label} must be a number")
    value = float(raw)
    if value != value:
        raise AsrTimestampError(f"{label} must be finite")
    if value == float("inf") or value == float("-inf"):
        raise AsrTimestampError(f"{label} must be finite")
    return value


def _admit_text(raw, maximum, label):
    if not isinstance(raw, str):
        raise AsrInputError(f"{label} must be a string")
    if not raw.strip():
        raise AsrInputError(f"{label} must be non-empty")
    if len(raw) > maximum:
        raise AsrInputError(f"{label} is longer than the admitted maximum")
    if not raw.isprintable():
        raise AsrInputError(f"{label} must not contain control characters")
    return raw


def _admit_audio_bytes(raw):
    if not isinstance(raw, bytes):
        raise AsrInputError("an audio payload must be bytes")
    if not raw:
        raise AsrInputError("an audio payload must be non-empty")
    if len(raw) > MAXIMUM_AUDIO_BYTES:
        raise AsrInputError("an audio payload exceeds the admitted maximum")
    return raw


def _admit_requested_language(raw):
    if raw not in REQUESTED_LANGUAGES:
        raise AsrLanguageError("a requested language is not admitted here")
    return raw


def _admit_detected_language(raw):
    if raw not in DETECTED_LANGUAGES:
        raise AsrLanguageError("a detected language is not admitted here")
    return raw


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise AsrTimestampError("an occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise AsrTimestampError("an occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise AsrTimestampError("an occurrence time is longer than the admitted maximum")
    if not value.isascii():
        raise AsrTimestampError("an occurrence time must be ASCII")
    for character in value:
        if not character.isprintable():
            raise AsrTimestampError("an occurrence time must not contain controls")
    return value


def _admit_input_revision(raw):
    if not isinstance(raw, str):
        raise AsrInputError("an input revision must be a string")
    value = raw.strip()
    if not value:
        raise AsrInputError("an input revision must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise AsrInputError("an input revision is longer than the admitted maximum")
    if not value.isascii():
        raise AsrInputError("an input revision must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise AsrInputError("an input revision must not contain whitespace")
    return value


def _admit_reason(raw):
    if not isinstance(raw, str):
        raise AsrInputError("a reason must be a string")
    if not raw.strip():
        raise AsrInputError("a reason must be non-empty")
    if len(raw) > MAXIMUM_REASON_CHARS:
        raise AsrInputError("a reason is longer than the admitted maximum")
    if not raw.isascii() or not raw.isprintable():
        raise AsrInputError("a reason must be printable ASCII")
    return raw


def _admit_actor(raw):
    if not isinstance(raw, str):
        raise AsrInputError("an actor id must be a string")
    value = raw.strip()
    if not value:
        raise AsrInputError("an actor id must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise AsrInputError("an actor id is longer than the admitted maximum")
    if not value.isascii():
        raise AsrInputError("an actor id must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise AsrInputError("an actor id must not contain whitespace")
    return value


def _check_segment_order(segments):
    """Fail closed unless segment indexes order and times do not overlap."""
    expected = 0
    previous_end = 0.0
    for segment in segments:
        if segment.index != expected:
            raise AsrInputError("segment indexes must order from zero without gaps")
        if segment.start_s < previous_end:
            raise AsrTimestampError("segments must not overlap")
        expected += 1
        previous_end = segment.end_s


def _admit_model_snapshot(present, revision):
    if present is not True:
        raise AsrModelUnavailableError("the local model snapshot is absent")
    if not isinstance(revision, str):
        raise AsrRevisionError("a snapshot revision must be a string")
    if revision in MUTABLE_REVISIONS:
        raise AsrRevisionError("a mutable snapshot revision is never admitted")
    if revision != MODEL_REVISION:
        raise AsrRevisionError("the snapshot revision is mismatched")
    return revision


def _admit_runtime_contract(trust_remote_code, local_files_only, allow_download):
    if trust_remote_code is not False:
        raise AsrBackendError("remote code is never admitted on the protected path")
    if local_files_only is not True:
        raise AsrBackendError("only local files are admitted on the protected path")
    if allow_download is not False:
        raise AsrBackendError("automatic download is never admitted on the protected path")


def mock_backend(audio_bytes, manifest, requested_language):
    """Deterministic synthetic backend with mock outputs only, never a model."""
    verified = verify_manifest(manifest)
    payload = _admit_audio_bytes(audio_bytes)
    requested = _admit_requested_language(requested_language)
    digest = content_digest_of(payload)
    short = digest[7:15]
    duration = len(payload) / SAMPLES_PER_SECOND
    if requested == "auto":
        detected = "en"
    else:
        detected = requested
    if requested == "ar":
        transcript = f"synthetic transcript ar {short}"
    else:
        transcript = f"synthetic transcript en {short}"
    segment = AsrSegment(index=0, start_s=0.0, end_s=duration, text=transcript)
    checked = segment.validated()
    return ("success", transcript, (checked,), detected, "")


def transcribe_with_backend(
    workspace_id,
    session_id,
    input_id,
    input_revision,
    audio_bytes,
    requested_language,
    input_occurred_at,
    result_occurred_at,
    manifest,
    model_snapshot_present,
    model_snapshot_revision,
    trust_remote_code,
    local_files_only,
    allow_download,
    backend,
):
    """Transcribe through an injected backend under the protected contract."""
    verified = verify_manifest(manifest)
    _admit_model_snapshot(model_snapshot_present, model_snapshot_revision)
    _admit_runtime_contract(trust_remote_code, local_files_only, allow_download)
    payload = _admit_audio_bytes(audio_bytes)
    requested = _admit_requested_language(requested_language)
    input_at = _admit_occurred_at(input_occurred_at)
    result_at = _admit_occurred_at(result_occurred_at)
    revision = _admit_input_revision(input_revision)
    if not isinstance(workspace_id, UUID):
        raise AsrInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise AsrInputError("a session id must be a UUID value")
    if not isinstance(input_id, UUID):
        raise AsrInputError("an input id must be a UUID value")
    if not callable(backend):
        raise AsrBackendError("a backend must be callable")
    out = backend(payload, verified, requested)
    if not isinstance(out, tuple) or len(out) != 5:
        raise AsrBackendError("a backend must return a five member tuple")
    status_value, transcript, raw_segments, detected_value, reason_value = out
    if status_value == "success":
        status = AsrStatus.SUCCESS
    elif status_value == "partial":
        status = AsrStatus.PARTIAL
    elif status_value == "failed":
        status = AsrStatus.FAILED
    else:
        raise AsrBackendError("a backend status is not admitted here")
    detected = _admit_detected_language(detected_value)
    if not isinstance(raw_segments, tuple):
        raise AsrBackendError("backend segments must be a tuple")
    if not isinstance(reason_value, str):
        raise AsrBackendError("a backend reason must be a string")
    return AsrResult(
        workspace_id=workspace_id,
        session_id=session_id,
        input_id=input_id,
        input_revision=revision,
        status=status,
        transcript=transcript,
        segments=raw_segments,
        requested_language=requested,
        detected_language=detected,
        model_id=verified.model_id,
        model_revision=verified.model_revision,
        runtime_name=verified.runtime_name,
        runtime_version=verified.runtime_version,
        input_occurred_at=input_at,
        result_occurred_at=result_at,
        reason=reason_value,
    ).validated()


def transcribe_synthetic(
    workspace_id,
    session_id,
    input_id,
    input_revision,
    audio_bytes,
    requested_language,
    input_occurred_at,
    result_occurred_at,
    manifest,
    model_snapshot_present,
    model_snapshot_revision,
    trust_remote_code,
    local_files_only,
    allow_download,
):
    """Transcribe with the deterministic synthetic backend."""
    return transcribe_with_backend(
        workspace_id,
        session_id,
        input_id,
        input_revision,
        audio_bytes,
        requested_language,
        input_occurred_at,
        result_occurred_at,
        manifest,
        model_snapshot_present,
        model_snapshot_revision,
        trust_remote_code,
        local_files_only,
        allow_download,
        mock_backend,
    )


def store_transcript(store, trail, result, actor_id, occurred_at):
    """Store one transcript with provenance and audit, failing closed."""
    if not isinstance(store, WorkspaceStore):
        raise AsrInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise AsrInputError("an audit trail is required")
    admitted = result.validated() if isinstance(result, AsrResult) else None
    if admitted is None:
        raise AsrInputError("a transcript needs an AsrResult instance")
    if admitted.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a transcript crossed the workspace boundary")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    binding = transcript_binding(admitted.workspace_id, transcript_id_for(
        admitted.workspace_id, admitted.session_id, admitted.input_id))
    payload = transcript_payload_bytes(admitted)
    producer = ProducerIdentity(
        kind=ProducerKind.MODEL,
        identifier=MODEL_ID,
        version=MODEL_REVISION,
    )
    source = SourceRef(
        kind=SourceKind.AUDIO_RANGE,
        source_id=str(admitted.input_id),
        source_revision=admitted.input_revision,
    )
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(source,),
        review_state=ReviewState.DRAFT,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise AsrConflictError("the transcript identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.TRANSCRIPT_CREATE,
    )
    return binding


def read_transcript(store, transcript_id):
    """Read and verify one stored transcript against its provenance digest."""
    if not isinstance(store, WorkspaceStore):
        raise AsrInputError("a workspace store is required")
    if not isinstance(transcript_id, UUID):
        raise AsrInputError("a transcript id must be a UUID value")
    binding = transcript_binding(store.workspace_id, transcript_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise AsrInputError("the transcript identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise AsrInputError("a stored transcript is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise AsrInputError("a stored transcript is not JSON") from error
    result = transcript_from_document(document)
    expected_id = transcript_id_for(result.workspace_id, result.session_id, result.input_id)
    if expected_id != transcript_id:
        raise AsrInputError("a stored transcript identity does not match its binding")
    if result.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a transcript crossed the workspace boundary")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return result
