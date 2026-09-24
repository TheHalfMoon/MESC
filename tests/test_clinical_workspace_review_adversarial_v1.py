"""CW-008 adversarial tests: the review workflow must fail closed under attack."""

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
    ReviewConflictError,
    ReviewInputError,
    ReviewRevisionError,
    ReviewSuggestionError,
    ReviewSupportError,
    ReviewTransitionError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7de0a0a5-2d4c-41c5-b20f-6c27ec82b0aa")
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
        store.workspace_id,
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
    transcript_id = asr_mod.transcript_id_for(store.workspace_id, SESSION_ONE, INPUT_ONE)
    return transcript_id, asr_mod.read_transcript(store, transcript_id)


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


def stored_draft(
    store: WorkspaceStore, trail: AuditTrail, spans: tuple[draft_mod.DraftSpan, ...] | None = None
) -> draft_mod.Draft:
    transcript_id, transcript = stored_transcript(store, trail)
    segment_text = transcript.segments[0].text
    template = draft_mod.expected_template()
    raw = json.dumps(
        transcript.to_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    bundle = draft_mod.input_bundle_digest_for(
        transcript_id,
        asr_mod.TRANSCRIPT_REVISION,
        "sha256:" + hashlib.sha256(raw).hexdigest(),
        template,
    )
    draft = draft_mod.synthesize_synthetic(
        store.workspace_id,
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
        spans
        if spans is not None
        else (supported_span(transcript_id, segment_text), unsupported_span()),
    )
    binding = draft_mod.store_draft(store, trail, draft, ACTOR, T4)
    return draft_mod.read_draft(store, binding.object_id)


def genesis_review(
    store: WorkspaceStore, trail: AuditTrail
) -> tuple[draft_mod.Draft, review_mod.ReviewRecord]:
    draft = stored_draft(store, trail)
    binding = review_mod.create_review(store, trail, draft, ACTOR, T5)
    return draft, review_mod.read_review(store, binding.object_id)


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


def test_all_illegal_transitions_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        # DRAFT -> FINALIZED is forbidden.
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
        # FINALIZED admits no children at all.
        for target in review_mod.ReviewStatus:
            with pytest.raises(ReviewTransitionError):
                review_mod.revise_review(
                    store,
                    trail,
                    finalized.review_id,
                    target,
                    carry_spans(finalized),
                    (),
                    ACTOR,
                    T6,
                )


def test_stored_payload_tampering_detected(tmp_path: Path) -> None:
    from medscale_workspace.errors import ProvenanceDigestMismatchError
    from medscale_workspace.provenance import read_provenance

    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        binding = review_mod.review_binding(WORKSPACE_ALPHA, genesis.review_id)
        raw = store.get_object(binding)
        record = read_provenance(store, binding)
        record.verify_payload(raw)
        with pytest.raises(ProvenanceDigestMismatchError):
            record.verify_payload(raw + b" ")
        with pytest.raises(ProvenanceDigestMismatchError):
            record.verify_payload(raw[:-1])


def test_revision_replay_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        review_mod.create_review(store, trail, draft, ACTOR, T5)
        with pytest.raises(ReviewConflictError):
            review_mod.create_review(store, trail, draft, ACTOR, T5)


def test_wrong_workspace_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
    with open_store(tmp_path, WORKSPACE_BETA) as other, pytest.raises(ReviewInputError):
        review_mod.read_review(other, genesis.review_id)


def test_forged_parent_and_session_rejected(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        forged_parent = uuid4()
        assert forged_parent != genesis.review_id
        with pytest.raises(ReviewInputError):
            review_mod.revise_review(
                store,
                trail,
                forged_parent,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            )
        forged = review_mod.ReviewRecord(
            workspace_id=genesis.workspace_id,
            session_id=uuid4(),
            draft_id=genesis.draft_id,
            review_id=genesis.review_id,
            revision_number=genesis.revision_number,
            parent_review_id=genesis.parent_review_id,
            status=genesis.status,
            spans=genesis.spans,
            suggestions=genesis.suggestions,
        )
        with pytest.raises(ReviewRevisionError):
            review_mod.validate_review_chain(store, forged)


def test_unchanged_text_downgrade_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        downgrade = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text=item.text,
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
        with pytest.raises(ReviewSupportError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                downgrade,
                (),
                ACTOR,
                T6,
            )


def test_edit_with_mismatched_reason_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        mismatched = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text="rewritten wording here" if item.span_id == "span-supported-1" else item.text,
                prior_status=item.prior_status,
                current_status=(
                    SupportStatus.PARTIALLY_SUPPORTED
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
        with pytest.raises(ReviewSupportError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                mismatched,
                (),
                ACTOR,
                T6,
            )


def test_failed_span_blocks_review_and_cannot_be_edited(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        failed = draft_mod.DraftSpan(
            span_id="span-failed-1",
            text="failed generation",
            status=SupportStatus.FAILED,
            sources=(),
            relation_note="",
            failure_reason=draft_mod.FailureReason.EMPTY_INPUT.value,
            abstention_reason="",
        )
        draft = stored_draft(store, trail, (failed,))
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, draft, ACTOR, T5).object_id
        )
        with pytest.raises(ReviewTransitionError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.REVIEWED,
                carry_spans(genesis),
                (),
                ACTOR,
                T6,
            )
        edited_failure = tuple(
            review_mod.SpanReview(
                span_id=item.span_id,
                text="reviewer rewrote failure",
                prior_status=item.prior_status,
                current_status=SupportStatus.UNSUPPORTED,
                invalidation_reason=review_mod.InvalidationReason.EDIT_LOST_SUPPORT.value,
            )
            for item in genesis.spans
        )
        with pytest.raises(ReviewSupportError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                edited_failure,
                (),
                ACTOR,
                T6,
            )


def test_suggestion_decision_is_one_way(tmp_path: Path) -> None:
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
                review_mod.SuggestionKind.TASK,
                "schedule follow up",
            ),
            kind=review_mod.SuggestionKind.TASK,
            text="schedule follow up",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.PENDING,
        )
        first = review_mod.read_review(
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
        accepted = review_mod.SuggestionRecord(
            suggestion_id=suggestion.suggestion_id,
            kind=suggestion.kind,
            text=suggestion.text,
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.ACCEPTED,
        )
        second = review_mod.read_review(
            store,
            review_mod.revise_review(
                store,
                trail,
                first.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(first),
                (accepted,),
                ACTOR,
                T6,
            ).object_id,
        )
        flipped = review_mod.SuggestionRecord(
            suggestion_id=suggestion.suggestion_id,
            kind=suggestion.kind,
            text=suggestion.text,
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.REJECTED,
        )
        with pytest.raises(ReviewSuggestionError):
            review_mod.revise_review(
                store,
                trail,
                second.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(second),
                (flipped,),
                ACTOR,
                T6,
            )
        refused_id = review_mod.review_id_for(
            WORKSPACE_ALPHA, SESSION_ONE, draft.draft_id, second.revision_number + 1
        )
        with pytest.raises(ReviewInputError):
            review_mod.read_review(store, refused_id)
        preset = review_mod.SuggestionRecord(
            suggestion_id=review_mod.suggestion_id_for(
                WORKSPACE_ALPHA,
                SESSION_ONE,
                draft.draft_id,
                review_mod.SuggestionKind.CODE,
                "preset code",
            ),
            kind=review_mod.SuggestionKind.CODE,
            text="preset code",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.ACCEPTED,
        )
        with pytest.raises(ReviewSuggestionError):
            review_mod.revise_review(
                store,
                trail,
                second.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(second),
                (accepted, preset),
                ACTOR,
                T6,
            )


def test_suggestion_identity_must_match_content(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
        forged = review_mod.SuggestionRecord(
            suggestion_id=uuid4(),
            kind=review_mod.SuggestionKind.ORDER,
            text="forged order",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.PENDING,
        )
        with pytest.raises(ReviewSuggestionError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(genesis),
                (forged,),
                ACTOR,
                T6,
            )


def test_branching_from_stale_revision_refused(tmp_path: Path) -> None:
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
                review_mod.SuggestionKind.TASK,
                "branch task",
            ),
            kind=review_mod.SuggestionKind.TASK,
            text="branch task",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.PENDING,
        )
        review_mod.revise_review(
            store,
            trail,
            genesis.review_id,
            review_mod.ReviewStatus.DRAFT,
            carry_spans(genesis),
            (suggestion,),
            ACTOR,
            T6,
        )
        # A second child of the same parent collides on the derived identity.
        with pytest.raises(ReviewConflictError):
            review_mod.revise_review(
                store,
                trail,
                genesis.review_id,
                review_mod.ReviewStatus.DRAFT,
                carry_spans(genesis),
                (suggestion,),
                ACTOR,
                T6,
            )


def test_no_external_capability_exists() -> None:
    import re as re_mod

    for name in dir(review_mod):
        lowered = name.lower()
        for stem in ("submit", "transmit", "export", "ehr", "prescri", "billing", "dispatch"):
            assert stem not in lowered, name
    source = (
        REPOSITORY_ROOT / "apps" / "workspace" / "src" / "medscale_workspace" / "review.py"
    ).read_text(encoding="ascii")
    roots = set()
    for line in source.splitlines():
        match = re_mod.match(r"\s*(?:from|import)\s+([a-zA-Z0-9_.]+)", line)
        if match:
            roots.add(match.group(1).split(".")[0])
    assert roots <= {
        "__future__",
        "hashlib",
        "json",
        "dataclasses",
        "enum",
        "uuid",
        "medscale_workspace",
    }, sorted(roots)
    assert not hasattr(review_mod, "submit_order")
    assert not hasattr(review_mod, "submit_code")
    assert not hasattr(review_mod, "transmit")
    assert not hasattr(review_mod, "export")


def test_audit_events_carry_no_clinical_text(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        transcript_id, transcript = stored_transcript(store, trail)
        segment_text = transcript.segments[0].text
        marker = "marker-clinical-phrase-zzz"
        template = draft_mod.expected_template()
        raw = json.dumps(
            transcript.to_document(), sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        bundle = draft_mod.input_bundle_digest_for(
            transcript_id,
            asr_mod.TRANSCRIPT_REVISION,
            "sha256:" + hashlib.sha256(raw).hexdigest(),
            template,
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
            (supported_span(transcript_id, segment_text),),
        )
        stored = draft_mod.read_draft(
            store, draft_mod.store_draft(store, trail, draft, ACTOR, T4).object_id
        )
        edited_span = review_mod.SpanReview(
            span_id="span-supported-1",
            text=marker,
            prior_status=SupportStatus.SUPPORTED,
            current_status=SupportStatus.UNSUPPORTED,
            invalidation_reason=review_mod.InvalidationReason.EDIT_LOST_SUPPORT.value,
        )
        genesis = review_mod.read_review(
            store, review_mod.create_review(store, trail, stored, ACTOR, T5).object_id
        )
        review_mod.revise_review(
            store,
            trail,
            genesis.review_id,
            review_mod.ReviewStatus.DRAFT,
            (edited_span,),
            (),
            ACTOR,
            T6,
        )
        for event in trail.events():
            assert marker.encode("ascii") not in event.canonical_bytes()


def test_support_states_stay_distinct() -> None:
    assert SupportStatus.FAILED != SupportStatus.ABSTAINED
    assert SupportStatus.ABSTAINED != SupportStatus.UNSUPPORTED
    assert SupportStatus.PARTIALLY_SUPPORTED != SupportStatus.SUPPORTED
    assert review_mod.ReviewStatus.DRAFT != review_mod.ReviewStatus.REVIEWED
    assert review_mod.ReviewStatus.REVIEWED != review_mod.ReviewStatus.FINALIZED
    assert review_mod.ReviewStatus.DRAFT != review_mod.ReviewStatus.FINALIZED


def test_finalize_emits_no_export_or_write_events(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, genesis = genesis_review(store, trail)
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
        forbidden = {
            AuditEventType.EXPORT,
            AuditEventType.CONNECTOR_WRITE,
            AuditEventType.CONNECTOR_READ,
            AuditEventType.BACKUP,
            AuditEventType.RESTORE,
        }
        kinds = {event.event_type for event in trail.events()}
        assert not (kinds & forbidden)
