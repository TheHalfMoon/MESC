"""CW-007 focused acceptance tests for the source-linked draft engine."""

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditEventType,
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import asr as asr_mod  # noqa: E402 runtime import
from medscale_workspace import draft as draft_mod  # noqa: E402 runtime import
from medscale_workspace.asr import AsrStatus  # noqa: E402 runtime import
from medscale_workspace.draft import (  # noqa: E402 runtime import
    AbstentionReason,
    DraftStatus,
    FailureReason,
    SupportRelation,
    SupportStatus,
)
from medscale_workspace.errors import (  # noqa: E402 runtime import
    DraftRevisionError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    content_digest_of,
    read_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
SESSION_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
INPUT_ONE = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
ACTOR = "synthetic-operator"
T1 = "2026-09-23T10:00:00+03:00"
T2 = "2026-09-23T10:01:00+03:00"
T3 = "2026-09-23T10:02:00+03:00"
INPUT_REVISION = "chunk-00000001"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def stored_transcript(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, asr_mod.AsrResult]:
    result = asr_mod.transcribe_synthetic(
        WORKSPACE_ALPHA,
        SESSION_ONE,
        INPUT_ONE,
        INPUT_REVISION,
        b"synthetic-pcm-00000001",
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
    assert result.status is AsrStatus.SUCCESS
    asr_mod.store_transcript(store, trail, result, ACTOR, T3)
    transcript_id = asr_mod.transcript_id_for(WORKSPACE_ALPHA, SESSION_ONE, INPUT_ONE)
    loaded = asr_mod.read_transcript(store, transcript_id)
    return transcript_id, loaded


def bundle_for(
    transcript_id: UUID, transcript: asr_mod.AsrResult, template: draft_mod.TemplateIdentity
) -> str:
    raw = json.dumps(
        transcript.to_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return str(
        draft_mod.input_bundle_digest_for(
            transcript_id, asr_mod.TRANSCRIPT_REVISION, content_digest_of(raw), template
        )
    )


def source_digest_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def supported_span(
    transcript_id: UUID, segment_text: str, span_id: str = "span-supported-1"
) -> draft_mod.DraftSpan:
    start, end = 0, min(9, len(segment_text))
    return draft_mod.DraftSpan(
        span_id=span_id,
        text="supported finding",
        status=SupportStatus.SUPPORTED,
        sources=(
            draft_mod.SourceReference(
                transcript_id=transcript_id,
                transcript_revision=asr_mod.TRANSCRIPT_REVISION,
                source_range=draft_mod.SourceRange(
                    segment_index=0,
                    char_start=start,
                    char_end=end,
                    source_digest=source_digest_of(segment_text[start:end]),
                ),
                relation=SupportRelation.EXACT_QUOTE,
            ),
        ),
        relation_note="",
        failure_reason="",
        abstention_reason="",
    )


def build_draft(
    store: WorkspaceStore,
    transcript_id: UUID,
    transcript: asr_mod.AsrResult,
    spans: tuple[draft_mod.DraftSpan, ...],
) -> draft_mod.Draft:
    template = draft_mod.expected_template()
    bundle = bundle_for(transcript_id, transcript, template)
    return draft_mod.synthesize_synthetic(
        WORKSPACE_ALPHA,
        SESSION_ONE,
        transcript_id,
        asr_mod.TRANSCRIPT_REVISION,
        transcript.transcript,
        transcript.segments,
        template,
        bundle,
        draft_mod.ModelIdentity(
            model_id=draft_mod.MODEL_ID, model_revision=draft_mod.MODEL_REVISION
        ),
        draft_mod.RuntimeIdentity(
            runtime_name=draft_mod.RUNTIME_NAME, runtime_version=draft_mod.RUNTIME_VERSION
        ),
        spans,
    )


def test_template_matches_governed_identities() -> None:
    template = draft_mod.expected_template()
    assert template.template_id == draft_mod.TEMPLATE_ID
    assert template.template_revision == draft_mod.TEMPLATE_REVISION
    assert template.template_digest == draft_mod._expected_template_digest()


def test_mutable_model_revision_rejected() -> None:
    with pytest.raises(DraftRevisionError):
        draft_mod.ModelIdentity(model_id=draft_mod.MODEL_ID, model_revision="main").validated()
    with pytest.raises(DraftRevisionError):
        draft_mod.ModelIdentity(model_id=draft_mod.MODEL_ID, model_revision="latest").validated()


def test_synthetic_draft_validates_and_stores(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        draft = build_draft(
            store,
            transcript_id,
            transcript,
            (
                supported_span(transcript_id, segment_text),
                draft_mod.DraftSpan(
                    span_id="span-unsupported-1",
                    text="unverified impression",
                    status=SupportStatus.UNSUPPORTED,
                    sources=(),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
            ),
        )
        validated = draft_mod.validate_draft_support(store, draft)
        assert validated.spans[0].status is SupportStatus.SUPPORTED
        assert validated.spans[1].status is SupportStatus.UNSUPPORTED
        binding = draft_mod.store_draft(store, trail, draft, ACTOR, T3)
        assert binding.object_revision == draft_mod.DRAFT_REVISION
        stored = read_provenance(store, binding)
        assert stored.binding == binding
        events = trail.events()
        kinds = [event.event_type for event in events]
        assert AuditEventType.AI_GENERATION in kinds
        report = trail.verify()
        assert report.events_verified == len(events)
        loaded = draft_mod.read_draft(store, draft.draft_id)
        assert loaded.draft_id == draft.draft_id
        assert [span.status for span in loaded.spans] == [
            SupportStatus.SUPPORTED,
            SupportStatus.UNSUPPORTED,
        ]


def test_all_five_support_states_first_class(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        start, end = 0, min(9, len(segment_text))
        digest = source_digest_of(segment_text[start:end])
        ref = draft_mod.SourceReference(
            transcript_id=transcript_id,
            transcript_revision=asr_mod.TRANSCRIPT_REVISION,
            source_range=draft_mod.SourceRange(
                segment_index=0, char_start=start, char_end=end, source_digest=digest
            ),
            relation=SupportRelation.SUMMARY_OF_RANGE,
        )
        partial = draft_mod.DraftSpan(
            span_id="span-partial-1",
            text="partial finding",
            status=SupportStatus.PARTIALLY_SUPPORTED,
            sources=(ref,),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        abstained = draft_mod.DraftSpan(
            span_id="span-abstained-1",
            text="unclear finding",
            status=SupportStatus.ABSTAINED,
            sources=(),
            relation_note="",
            failure_reason="",
            abstention_reason=AbstentionReason.INSUFFICIENT_SOURCE.value,
        )
        failed = draft_mod.DraftSpan(
            span_id="span-failed-1",
            text="failed finding",
            status=SupportStatus.FAILED,
            sources=(),
            relation_note="",
            failure_reason=FailureReason.EMPTY_INPUT.value,
            abstention_reason="",
        )
        draft = build_draft(
            store,
            transcript_id,
            transcript,
            (
                supported_span(transcript_id, segment_text),
                partial,
                draft_mod.DraftSpan(
                    span_id="span-unsupported-1",
                    text="unverified",
                    status=SupportStatus.UNSUPPORTED,
                    sources=(),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
                abstained,
                failed,
            ),
        )
        validated = draft_mod.validate_draft_support(store, draft)
        states = [span.status for span in validated.spans]
        assert states == [
            SupportStatus.SUPPORTED,
            SupportStatus.PARTIALLY_SUPPORTED,
            SupportStatus.UNSUPPORTED,
            SupportStatus.ABSTAINED,
            SupportStatus.FAILED,
        ]
        assert len(set(states)) == 5


def test_no_finalization_api_exists() -> None:
    assert set(DraftStatus) == {DraftStatus.DRAFT}
    for name in (
        "finalize",
        "mark_reviewed",
        "mark_finalized",
        "submit_order",
        "submit_prescription",
        "commit_diagnosis",
        "transmit",
        "ehr_write",
        "write_ehr",
    ):
        assert not hasattr(draft_mod, name), name


def test_no_ehr_write_or_remote_api_exists() -> None:
    names = dir(draft_mod)
    for name in names:
        lowered = name.lower()
        assert "ehr" not in lowered, name
        assert "finaliz" not in lowered, name
    for name in ("remote", "download", "fetch", "http", "urlopen", "socket"):
        assert not hasattr(draft_mod, name), name
