"""CW-007 adversarial tests: support spoofing, binding escape, and creep are refused."""

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import asr as asr_mod  # noqa: E402 runtime import
from medscale_workspace import draft as draft_mod  # noqa: E402 runtime import
from medscale_workspace.draft import (  # noqa: E402 runtime import
    AbstentionReason,
    FailureReason,
    SupportRelation,
    SupportStatus,
)
from medscale_workspace.errors import (  # noqa: E402 runtime import
    DraftConflictError,
    DraftInputError,
    DraftRevisionError,
    DraftSupportError,
    DraftTemplateError,
    ProvenanceDigestMismatchError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7de0f0a5-2d4c-5d6e-9f70-8b9c0d1e2f30")
SESSION_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
SESSION_TWO = UUID("2d3e4f50-6a7b-8c9d-0e1f-2a3b4c5d6e7f")
INPUT_ONE = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
INPUT_TWO = UUID("2c3d4e5f-6a7b-8c9d-0e1f-2a3b4c5d6e7f")
ACTOR = "synthetic-operator"
T1 = "2026-09-23T10:00:00+03:00"
T2 = "2026-09-23T10:01:00+03:00"
T3 = "2026-09-23T10:02:00+03:00"
INPUT_REVISION = "chunk-00000001"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    owned = root / ("ws-" + str(workspace_id)[:8])
    owned.mkdir(parents=True, exist_ok=True)
    return WorkspaceStore.open(
        store_root=str(owned),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def stored_transcript(
    store: WorkspaceStore,
    trail: AuditTrail,
    session: UUID = SESSION_ONE,
    input_id: UUID = INPUT_ONE,
) -> tuple[UUID, asr_mod.AsrResult]:
    result = asr_mod.transcribe_synthetic(
        store.workspace_id,
        session,
        input_id,
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
    asr_mod.store_transcript(store, trail, result, ACTOR, T3)
    transcript_id = asr_mod.transcript_id_for(store.workspace_id, session, input_id)
    return transcript_id, asr_mod.read_transcript(store, transcript_id)


def bundle_for(
    transcript_id: UUID, transcript: asr_mod.AsrResult, template: draft_mod.TemplateIdentity
) -> str:
    raw = json.dumps(
        transcript.to_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    from medscale_workspace.provenance import content_digest_of

    return str(
        draft_mod.input_bundle_digest_for(
            transcript_id, asr_mod.TRANSCRIPT_REVISION, content_digest_of(raw), template
        )
    )


def digest_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def valid_ref(transcript_id: UUID, segment_text: str) -> draft_mod.SourceReference:
    start, end = 0, min(9, len(segment_text))
    return draft_mod.SourceReference(
        transcript_id=transcript_id,
        transcript_revision=asr_mod.TRANSCRIPT_REVISION,
        source_range=draft_mod.SourceRange(
            segment_index=0,
            char_start=start,
            char_end=end,
            source_digest=digest_of(segment_text[start:end]),
        ),
        relation=SupportRelation.EXACT_QUOTE,
    )


def build(
    store: WorkspaceStore,
    transcript_id: UUID,
    transcript: asr_mod.AsrResult,
    spans: tuple[draft_mod.DraftSpan, ...],
    session: UUID | None = None,
    template: draft_mod.TemplateIdentity | None = None,
    bundle: str | None = None,
) -> draft_mod.Draft:
    template = template or draft_mod.expected_template()
    bundle = bundle if bundle is not None else bundle_for(transcript_id, transcript, template)
    return draft_mod.synthesize_synthetic(
        store.workspace_id,
        session or SESSION_ONE,
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


def unsupported_span(span_id: str = "s-u") -> draft_mod.DraftSpan:
    return draft_mod.DraftSpan(
        span_id=span_id,
        text="unverified",
        status=SupportStatus.UNSUPPORTED,
        sources=(),
        relation_note="",
        failure_reason="",
        abstention_reason="",
    )


def test_invented_fact_cannot_become_source_backed(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _transcript_id, _transcript = stored_transcript(store, trail)
        with pytest.raises(DraftSupportError):
            draft_mod.DraftSpan(
                span_id="s-invented",
                text="invented diagnosis",
                status=SupportStatus.SUPPORTED,
                sources=(),
                relation_note="",
                failure_reason="",
                abstention_reason="",
            ).validated()


def test_unsupported_fact_remains_unsupported(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        draft = build(store, transcript_id, transcript, (unsupported_span(),))
        validated = draft_mod.validate_draft_support(store, draft)
        assert validated.spans[0].status is SupportStatus.UNSUPPORTED


def test_partial_support_cannot_become_supported(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        partial = draft_mod.DraftSpan(
            span_id="s-p",
            text="partial",
            status=SupportStatus.PARTIALLY_SUPPORTED,
            sources=(valid_ref(transcript_id, segment_text),),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        draft = build(store, transcript_id, transcript, (partial,))
        validated = draft_mod.validate_draft_support(store, draft)
        assert validated.spans[0].status is SupportStatus.PARTIALLY_SUPPORTED
        assert validated.spans[0].status is not SupportStatus.SUPPORTED


def test_source_range_out_of_bounds_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        bad = draft_mod.SourceReference(
            transcript_id=transcript_id,
            transcript_revision=asr_mod.TRANSCRIPT_REVISION,
            source_range=draft_mod.SourceRange(
                segment_index=0,
                char_start=0,
                char_end=len(segment_text) + 50,
                source_digest=digest_of("x"),
            ),
            relation=SupportRelation.EXACT_QUOTE,
        )
        span = draft_mod.DraftSpan(
            span_id="s-oob",
            text="oob",
            status=SupportStatus.SUPPORTED,
            sources=(bad,),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        draft = build(store, transcript_id, transcript, (span,))
        with pytest.raises(DraftSupportError):
            draft_mod.validate_draft_support(store, draft)


def test_wrong_transcript_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        foreign = uuid4()
        bad = draft_mod.SourceReference(
            transcript_id=foreign,
            transcript_revision=asr_mod.TRANSCRIPT_REVISION,
            source_range=draft_mod.SourceRange(
                segment_index=0,
                char_start=0,
                char_end=min(9, len(segment_text)),
                source_digest=digest_of(segment_text[0 : min(9, len(segment_text))]),
            ),
            relation=SupportRelation.EXACT_QUOTE,
        )
        span = draft_mod.DraftSpan(
            span_id="s-wt",
            text="wrong transcript",
            status=SupportStatus.SUPPORTED,
            sources=(bad,),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        draft = build(store, transcript_id, transcript, (span,))
        with pytest.raises(DraftSupportError):
            draft_mod.validate_draft_support(store, draft)


def test_wrong_transcript_revision_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, _transcript = stored_transcript(store, trail)
        with pytest.raises(DraftRevisionError):
            draft_mod.TranscriptReference(
                transcript_id=transcript_id, transcript_revision="transcript-00000002"
            ).validated()


def test_wrong_session_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        draft = build(
            store,
            transcript_id,
            transcript,
            (
                draft_mod.DraftSpan(
                    span_id="s-sess",
                    text="supported",
                    status=SupportStatus.SUPPORTED,
                    sources=(valid_ref(transcript_id, segment_text),),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
            ),
            session=SESSION_TWO,
        )
        with pytest.raises(DraftSupportError):
            draft_mod.validate_draft_support(store, draft)


def test_wrong_workspace_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        template = draft_mod.expected_template()
        bundle = bundle_for(transcript_id, transcript, template)
        draft = draft_mod.synthesize_synthetic(
            WORKSPACE_BETA,
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
                runtime_name=draft_mod.RUNTIME_NAME,
                runtime_version=draft_mod.RUNTIME_VERSION,
            ),
            (
                draft_mod.DraftSpan(
                    span_id="s-ws",
                    text="supported",
                    status=SupportStatus.SUPPORTED,
                    sources=(valid_ref(transcript_id, segment_text),),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
            ),
        )
        with pytest.raises(WorkspaceIsolationError):
            draft_mod.validate_draft_support(store, draft)


def test_wrong_source_digest_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        bad = draft_mod.SourceReference(
            transcript_id=transcript_id,
            transcript_revision=asr_mod.TRANSCRIPT_REVISION,
            source_range=draft_mod.SourceRange(
                segment_index=0,
                char_start=0,
                char_end=min(9, len(segment_text)),
                source_digest=digest_of("tampered-slice"),
            ),
            relation=SupportRelation.EXACT_QUOTE,
        )
        span = draft_mod.DraftSpan(
            span_id="s-digest",
            text="digest",
            status=SupportStatus.SUPPORTED,
            sources=(bad,),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        draft = build(store, transcript_id, transcript, (span,))
        with pytest.raises(DraftSupportError):
            draft_mod.validate_draft_support(store, draft)


def test_malformed_source_relation_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        start, end = 0, min(9, len(segment_text))
        document = {
            "relation": "self_certified",
            "source_range": {
                "char_end": end,
                "char_start": start,
                "segment_index": 0,
                "source_digest": digest_of(segment_text[start:end]),
            },
            "transcript_id": str(transcript_id),
            "transcript_revision": asr_mod.TRANSCRIPT_REVISION,
        }
        with pytest.raises(DraftInputError):
            draft_mod.SourceReference.from_document(document)


def test_duplicate_span_ids_and_ranges_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        ref = valid_ref(transcript_id, segment_text)
        span_a = draft_mod.DraftSpan(
            span_id="s-dup",
            text="a",
            status=SupportStatus.SUPPORTED,
            sources=(ref,),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        span_b = draft_mod.DraftSpan(
            span_id="s-dup",
            text="b",
            status=SupportStatus.UNSUPPORTED,
            sources=(),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        with pytest.raises(DraftSupportError):
            build(store, transcript_id, transcript, (span_a, span_b))
        dup_sources = draft_mod.DraftSpan(
            span_id="s-dup-range",
            text="c",
            status=SupportStatus.SUPPORTED,
            sources=(ref, ref),
            relation_note="",
            failure_reason="",
            abstention_reason="",
        )
        with pytest.raises(DraftSupportError):
            dup_sources.validated()


def test_stale_template_and_digest_mismatch_rejected() -> None:
    good = draft_mod.expected_template().to_document()
    stale = dict(good)
    stale["template_revision"] = "template-00000002"
    with pytest.raises(DraftTemplateError):
        draft_mod.TemplateIdentity.from_document(stale)
    drifted = dict(good)
    drifted["template_digest"] = digest_of("other-template")
    with pytest.raises(DraftTemplateError):
        draft_mod.TemplateIdentity.from_document(drifted)


def test_mutable_model_revision_rejected() -> None:
    from medscale_workspace.draft import ModelIdentity

    for mutable in ("main", "latest"):
        with pytest.raises(DraftRevisionError):
            ModelIdentity(model_id=draft_mod.MODEL_ID, model_revision=mutable).validated()


def test_cross_workspace_read_blocked(tmp_path: Path) -> None:
    with open_store(tmp_path, WORKSPACE_ALPHA) as store_a:
        trail_a = AuditTrail(store_a)
        transcript_id, transcript = stored_transcript(store_a, trail_a)
        draft = build(store_a, transcript_id, transcript, (unsupported_span("s-x"),))
        binding = draft_mod.store_draft(store_a, trail_a, draft, ACTOR, T3)
        with open_store(tmp_path, WORKSPACE_BETA) as store_b, pytest.raises(DraftInputError):
            draft_mod.read_draft(store_b, binding.object_id)


def test_cross_session_binding_blocked(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, _ = stored_transcript(store, trail, session=SESSION_ONE)
        _, transcript_two = stored_transcript(store, trail, session=SESSION_TWO, input_id=INPUT_TWO)
        draft = build(
            store,
            transcript_id,
            transcript_two,
            (unsupported_span("s-cs"),),
            session=SESSION_TWO,
        )
        with pytest.raises(DraftSupportError):
            draft_mod.validate_draft_support(store, draft)


def test_provenance_tampering_detected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        draft = build(
            store,
            transcript_id,
            transcript,
            (
                draft_mod.DraftSpan(
                    span_id="s-t",
                    text="supported",
                    status=SupportStatus.SUPPORTED,
                    sources=(valid_ref(transcript_id, segment_text),),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
            ),
        )
        binding = draft_mod.store_draft(store, trail, draft, ACTOR, T3)
        raw = store.get_object(binding)
        from medscale_workspace.provenance import read_provenance

        record = read_provenance(store, binding)
        with pytest.raises(ProvenanceDigestMismatchError):
            record.verify_payload(raw + b" ")
        with pytest.raises(DraftConflictError):
            draft_mod.store_draft(store, trail, draft, ACTOR, T3)


def test_audit_event_contains_no_clinical_text(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        marker = "marker-clinical-phrase-zzz"
        draft = build(
            store,
            transcript_id,
            transcript,
            (
                draft_mod.DraftSpan(
                    span_id="s-audit",
                    text=marker,
                    status=SupportStatus.SUPPORTED,
                    sources=(valid_ref(transcript_id, segment_text),),
                    relation_note="",
                    failure_reason="",
                    abstention_reason="",
                ),
            ),
        )
        draft_mod.store_draft(store, trail, draft, ACTOR, T3)
        for event in trail.events():
            assert marker.encode("ascii") not in event.canonical_bytes()


def test_failure_abstention_unsupported_distinct() -> None:
    assert SupportStatus.FAILED != SupportStatus.ABSTAINED
    assert SupportStatus.ABSTAINED != SupportStatus.UNSUPPORTED
    assert SupportStatus.FAILED != SupportStatus.UNSUPPORTED
    assert FailureReason.EMPTY_INPUT.value != AbstentionReason.INSUFFICIENT_SOURCE.value
    failed = draft_mod.DraftSpan(
        span_id="s-f",
        text="f",
        status=SupportStatus.FAILED,
        sources=(),
        relation_note="",
        failure_reason=FailureReason.EMPTY_INPUT.value,
        abstention_reason="",
    ).validated()
    abstained = draft_mod.DraftSpan(
        span_id="s-a",
        text="a",
        status=SupportStatus.ABSTAINED,
        sources=(),
        relation_note="",
        failure_reason="",
        abstention_reason=AbstentionReason.INSUFFICIENT_SOURCE.value,
    ).validated()
    assert failed.status is SupportStatus.FAILED
    assert abstained.status is SupportStatus.ABSTAINED


def test_no_finalization_ehr_or_remote_api() -> None:
    for name in (
        "finalize",
        "mark_reviewed",
        "mark_finalized",
        "ehr_write",
        "write_ehr",
        "submit_order",
        "remote",
        "download",
        "fetch",
    ):
        assert not hasattr(draft_mod, name), name
