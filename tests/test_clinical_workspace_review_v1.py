"""CW-008 focused acceptance tests for the human review and finalization workflow."""

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
from medscale_workspace import review as review_mod  # noqa: E402 runtime import
from medscale_workspace.asr import AsrStatus  # noqa: E402 runtime import
from medscale_workspace.draft import SupportStatus  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    ReviewRevisionError,
    ReviewSupportError,
    ReviewTransitionError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    ReviewState,
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
T4 = "2026-09-23T10:03:00+03:00"
T5 = "2026-09-23T10:04:00+03:00"
T6 = "2026-09-23T10:05:00+03:00"
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


def source_digest_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def supported_span(transcript_id: UUID, segment_text: str) -> draft_mod.DraftSpan:
    start, end = 0, min(9, len(segment_text))
    return draft_mod.DraftSpan(
        span_id="span-supported-1",
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
                relation=draft_mod.SupportRelation.EXACT_QUOTE,
            ),
        ),
        relation_note="",
        failure_reason="",
        abstention_reason="",
    )


def unsupported_span() -> draft_mod.DraftSpan:
    return draft_mod.DraftSpan(
        span_id="span-unsupported-1",
        text="unverified impression",
        status=SupportStatus.UNSUPPORTED,
        sources=(),
        relation_note="",
        failure_reason="",
        abstention_reason="",
    )


def stored_draft(store: WorkspaceStore, trail: AuditTrail) -> draft_mod.Draft:
    transcript_id, transcript = stored_transcript(store, trail)
    segment_text = transcript.segments[0].text
    template = draft_mod.expected_template()
    raw = json.dumps(
        transcript.to_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    bundle = draft_mod.input_bundle_digest_for(
        transcript_id, asr_mod.TRANSCRIPT_REVISION, content_digest_of(raw), template
    )
    draft = draft_mod.synthesize_synthetic(
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
        (supported_span(transcript_id, segment_text), unsupported_span()),
    )
    binding = draft_mod.store_draft(store, trail, draft, ACTOR, T4)
    return draft_mod.read_draft(store, binding.object_id)


def carry_spans(review: review_mod.ReviewRecord) -> tuple[review_mod.SpanReview, ...]:
    return tuple(
        review_mod.SpanReview(
            span_id=item.span_id,
            text=item.text,
            prior_status=item.prior_status,
            current_status=item.current_status,
            invalidation_reason=item.invalidation_reason,
        )
        for item in review.spans
    )


def test_genesis_review_mirrors_draft(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        binding = review_mod.create_review(store, trail, draft, ACTOR, T5)
        review = review_mod.read_review(store, binding.object_id)
        assert review.revision_number == 1
        assert review.status is review_mod.ReviewStatus.DRAFT
        assert review.parent_review_id == draft.draft_id
        assert [item.span_id for item in review.spans] == ["span-supported-1", "span-unsupported-1"]
        for item in review.spans:
            assert item.current_status is item.prior_status
            assert item.invalidation_reason == ""
        record = read_provenance(store, binding)
        assert record.review_state is ReviewState.DRAFT


def test_review_lifecycle_separates_states(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis_binding = review_mod.create_review(store, trail, draft, ACTOR, T5)
        genesis = review_mod.read_review(store, genesis_binding.object_id)
        reviewed_binding = review_mod.revise_review(
            store,
            trail,
            genesis.review_id,
            review_mod.ReviewStatus.REVIEWED,
            carry_spans(genesis),
            (),
            ACTOR,
            T6,
        )
        reviewed = review_mod.read_review(store, reviewed_binding.object_id)
        assert reviewed.revision_number == 2
        assert reviewed.status is review_mod.ReviewStatus.REVIEWED
        assert reviewed.parent_review_id == genesis.review_id
        finalized_binding = review_mod.revise_review(
            store,
            trail,
            reviewed.review_id,
            review_mod.ReviewStatus.FINALIZED,
            carry_spans(reviewed),
            (),
            ACTOR,
            T6,
        )
        finalized = review_mod.read_review(store, finalized_binding.object_id)
        assert finalized.revision_number == 3
        assert finalized.status is review_mod.ReviewStatus.FINALIZED
        assert finalized.status is not reviewed.status
        assert reviewed.status is not genesis.status
        record = read_provenance(store, finalized_binding)
        assert record.review_state is ReviewState.FINALIZED


def test_direct_draft_to_finalized_is_forbidden(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        binding = review_mod.create_review(store, trail, draft, ACTOR, T5)
        genesis = review_mod.read_review(store, binding.object_id)
        with pytest.raises(ReviewTransitionError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.FINALIZED,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            )


def test_finalized_revision_is_terminal(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        reviewed = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.REVIEWED,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            ).object_id,
        )
        finalized = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                reviewed.review_id,
                review_mod.ReviewStatus.FINALIZED,
                carry_spans(reviewed),
                (),
                ACTOR,
                T6,
            ).object_id,
        )
        with pytest.raises(ReviewTransitionError):
            review_mod.revise_review(
                store,
                trail,
                finalized.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(finalized),
                (),
                ACTOR,
                T6,
            )


def test_edit_forces_draft_and_invalidates_support(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        edited = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text="edited clinical wording" if item.span_id == "span-supported-1" else item.text,
                prior_status=item.prior_status,
                current_status=(
                    SupportStatus.UNSUPPORTED
                    if item.span_id == "span-supported-1"
                    else item.current_status
                ),
                invalidation_reason=(
                    review_mod.InvalidationReason.EDIT_LOST_SUPPORT.value
                    if item.span_id == "span-supported-1"
                    else ""
                ),
            )
            for item in genesis.spans
        )
        child = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                edited,
                (),
                ACTOR,
                T6,
            ).object_id,
        )
        assert child.revision_number == 2
        assert child.status is review_mod.ReviewStatus.DRAFT
        changed = next(item for item in child.spans if item.span_id == "span-supported-1")
        assert changed.current_status is SupportStatus.UNSUPPORTED
        # Further edits in the same revision cannot jump straight to reviewed.
        edited_again = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text=item.text + "-again" if item.span_id == "span-supported-1" else item.text,
                prior_status=item.prior_status,
                current_status=(
                    SupportStatus.UNSUPPORTED
                    if item.span_id == "span-supported-1"
                    else item.current_status
                ),
                invalidation_reason=(
                    review_mod.InvalidationReason.EDIT_LOST_SUPPORT.value
                    if item.span_id == "span-supported-1"
                    else ""
                ),
            )
            for item in child.spans
        )
        with pytest.raises(ReviewTransitionError):
            review_mod.revise_review(
                store,
                trail,
                child.review_id,
                review_mod.ReviewStatus.REVIEWED,
                edited_again,
                (),
                ACTOR,
                T6,
            )
        # Carrying the edited text unchanged into the next revision may advance.
        advanced = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                child.review_id,
                review_mod.ReviewStatus.REVIEWED,
                carry_spans(child),
                (),
                ACTOR,
                T6,
            ).object_id,
        )
        assert advanced.status is review_mod.ReviewStatus.REVIEWED


def test_edited_text_cannot_retain_supported_status(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        cheating = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text="silently rewritten" if item.span_id == "span-supported-1" else item.text,
                prior_status=item.prior_status,
                current_status=item.current_status,
                invalidation_reason="",
            )
            for item in genesis.spans
        )
        with pytest.raises(ReviewSupportError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                cheating,
                (),
                ACTOR,
                T6,
            )


def test_unchanged_review_creates_no_revision(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        with pytest.raises(ReviewRevisionError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            )


def test_suggestions_remain_drafts_and_audit_records_decisions(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        suggestion = review_mod.SuggestionRecord(
            suggestion_id=review_mod.suggestion_id_for(
                WORKSPACE_ALPHA,
                SESSION_ONE,
                draft.draft_id,
                review_mod.SuggestionKind.ORDER,
                "consider cbc panel",
            ),
            kind=review_mod.SuggestionKind.ORDER,
            text="consider cbc panel",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.PENDING,
        )
        with_suggestion = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(genesis),
                (suggestion,),
                ACTOR,
                T6,
            ).object_id,
        )
        assert with_suggestion.suggestions[0].status is review_mod.SuggestionStatus.DRAFT
        decided = review_mod.SuggestionRecord(
            suggestion_id=suggestion.suggestion_id,
            kind=suggestion.kind,
            text=suggestion.text,
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.ACCEPTED,
        )
        accepted = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                with_suggestion.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(with_suggestion),
                (decided,),
                ACTOR,
                T6,
            ).object_id,
        )
        assert accepted.suggestions[0].decision is review_mod.SuggestionDecision.ACCEPTED
        assert accepted.suggestions[0].status is review_mod.SuggestionStatus.DRAFT
        kinds = [event.event_type for event in trail.events()]
        assert AuditEventType.SUGGESTION_ACCEPT in kinds


def test_review_identity_is_deterministic(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        first = review_mod.create_review(store, trail, draft, ACTOR, T5)
        expected = review_mod.review_id_for(WORKSPACE_ALPHA, SESSION_ONE, draft.draft_id, 1)
        assert first.object_id == expected


def test_finalize_audit_uses_note_finalize(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        reviewed = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.REVIEWED,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            ).object_id,
        )
        review_mod.revise_review(
            store,
            trail,
            reviewed.review_id,
            review_mod.ReviewStatus.FINALIZED,
            carry_spans(reviewed),
            (),
            ACTOR,
            T6,
        )
        kinds = [event.event_type for event in trail.events()]
        assert AuditEventType.OBJECT_CREATE in kinds
        assert AuditEventType.NOTE_FINALIZE in kinds
