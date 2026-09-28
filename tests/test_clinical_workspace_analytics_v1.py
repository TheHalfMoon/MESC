"""CW-015 acceptance tests: local workspace analytics over stored reviews."""

# mypy: disable-error-code="import-not-found"

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
from medscale_workspace import analytics as analytics_mod  # noqa: E402 runtime import
from medscale_workspace import asr as asr_mod  # noqa: E402 runtime import
from medscale_workspace import draft as draft_mod  # noqa: E402 runtime import
from medscale_workspace import review as review_mod  # noqa: E402 runtime import
from medscale_workspace.asr import AsrStatus  # noqa: E402 runtime import
from medscale_workspace.draft import SupportStatus  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    AnalyticsInputError,
    AnalyticsRevisionError,
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
T7 = "2026-09-23T10:06:00+03:00"
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


def stored_review_lineage(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, UUID, UUID]:
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
    return (genesis.review_id, reviewed.review_id, finalized.review_id)


def test_metric_definitions_are_versioned(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        record = analytics_mod.read_analytics(store, binding.object_id)
        assert record.metric_name is analytics_mod.MetricName.REVIEW_STATUS_COUNTS
        assert record.metric_version == "1"
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store, trail, "review-status-counts-and-more", "1", review_ids, ACTOR, T7
            )
        with pytest.raises(AnalyticsRevisionError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "2",
                review_ids,
                ACTOR,
                T7,
            )


def test_status_counts_are_deterministic_and_correct(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        first = analytics_mod.analytics_id_for(
            WORKSPACE_ALPHA,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            analytics_mod._input_digest_for(
                WORKSPACE_ALPHA,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                review_ids,
            ),
        )
        reordered = analytics_mod.analytics_id_for(
            WORKSPACE_ALPHA,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            analytics_mod._input_digest_for(
                WORKSPACE_ALPHA,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                (review_ids[2], review_ids[0], review_ids[1]),
            ),
        )
        assert first == reordered
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        assert binding.object_id == first
        record = analytics_mod.read_analytics(store, binding.object_id)
        by_label = {item.label: item.value for item in record.counts}
        assert by_label == {"draft": 1, "reviewed": 1, "finalized": 1}
        assert record.input_count == 3
        stored_provenance = read_provenance(store, binding)
        assert stored_provenance.review_state is ReviewState.IMPORTED
        stored_provenance.verify_payload(analytics_mod.analytics_payload_bytes(record))


def test_suggestion_counts_aggregate_decisions(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        draft = stored_draft(store, trail)
        genesis_binding = review_mod.create_review(store, trail, draft, ACTOR, T5)
        genesis = review_mod.read_review(store, genesis_binding.object_id)
        suggestion_id = review_mod.suggestion_id_for(
            WORKSPACE_ALPHA,
            SESSION_ONE,
            draft.draft_id,
            review_mod.SuggestionKind.TASK,
            "synthetic follow-up task",
        )
        pending = review_mod.SuggestionRecord(
            suggestion_id=suggestion_id,
            kind=review_mod.SuggestionKind.TASK,
            text="synthetic follow-up task",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.PENDING,
        )
        reviewed_binding = review_mod.revise_review(
            store,
            trail,
            genesis.review_id,
            review_mod.ReviewStatus.REVIEWED,
            carry_spans(genesis),
            (pending,),
            ACTOR,
            T6,
        )
        reviewed = review_mod.read_review(store, reviewed_binding.object_id)
        accepted = review_mod.SuggestionRecord(
            suggestion_id=suggestion_id,
            kind=review_mod.SuggestionKind.TASK,
            text="synthetic follow-up task",
            status=review_mod.SuggestionStatus.DRAFT,
            decision=review_mod.SuggestionDecision.ACCEPTED,
        )
        finalized_binding = review_mod.revise_review(
            store,
            trail,
            reviewed.review_id,
            review_mod.ReviewStatus.FINALIZED,
            carry_spans(reviewed),
            (accepted,),
            ACTOR,
            T6,
        )
        finalized = review_mod.read_review(store, finalized_binding.object_id)
        review_ids = (genesis.review_id, reviewed.review_id, finalized.review_id)
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_SUGGESTION_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        record = analytics_mod.read_analytics(store, binding.object_id)
        by_label = {item.label: item.value for item in record.counts}
        assert by_label == {"pending": 1, "accepted": 1, "rejected": 0}


def test_sensitive_dimensions_are_absent_by_construction(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        record = analytics_mod.read_analytics(store, binding.object_id)
        document = record.to_document()
        assert set(document["counts"][0]) == {"label", "value"}
        labels = [item["label"] for item in document["counts"]]
        assert labels == ["draft", "reviewed", "finalized"]
        payload = json.dumps(document, sort_keys=True)
        for review_id in review_ids:
            assert str(review_id) not in payload
        assert str(SESSION_ONE) not in payload
        assert ACTOR not in payload
        assert "compute_analytics" not in payload


def test_analytics_remain_workspace_domain(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        record = analytics_mod.read_analytics(store, binding.object_id)
        assert record.to_document()["data_class"] == analytics_mod.analytics_data_class_value()
        assert analytics_mod.analytics_data_class_value() == "OPERATIONAL_ANALYTICS"
        from medscale_workspace import nobackflow as guard_mod
        from medscale_workspace.binding import ObjectBinding
        from medscale_workspace.data_class import (
            DataClass,
            TrustDomain,
            classify,
        )
        from medscale_workspace.errors import TelemetryBackflowError
        from medscale_workspace.identity import WorkspaceObjectType

        classification = classify(DataClass.OPERATIONAL_ANALYTICS)
        classified = guard_mod.classify_object(
            binding=ObjectBinding(
                workspace_id=WORKSPACE_ALPHA,
                object_id=binding.object_id,
                object_type=WorkspaceObjectType.WORKSPACE_ANALYTICS,
                object_revision=analytics_mod.ANALYTICS_REVISION,
            ),
            classification=classification,
            payload=analytics_mod.analytics_payload_bytes(record),
        )
        evaluation = guard_mod.evaluate_object_flow(classified, TrustDomain.RESEARCH_CORE)
        assert evaluation.admitted is False
        assert evaluation.refusal is TelemetryBackflowError
        with pytest.raises(TelemetryBackflowError):
            guard_mod.guard_object_handoff(classified, TrustDomain.RESEARCH_CORE)


def test_export_is_explicit_and_no_automatic_telemetry(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        events_before = list(trail.events())
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        fresh_events = list(trail.events())[len(events_before) :]
        kinds = [event.event_type for event in fresh_events]
        assert AuditEventType.OBJECT_CREATE in kinds
        assert AuditEventType.EXPORT not in kinds
        count_before = len(list(trail.events()))
        analytics_mod.read_analytics(store, binding.object_id)
        assert len(list(trail.events())) == count_before


def test_caller_totals_are_never_trusted(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        binding = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        record = analytics_mod.read_analytics(store, binding.object_id)
        by_label = {item.label: item.value for item in record.counts}
        assert sum(by_label.values()) == record.input_count == 3
        forged = analytics_mod.AnalyticsRecord(
            workspace_id=WORKSPACE_ALPHA,
            analytics_id=record.analytics_id,
            metric_name=analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            metric_version="1",
            input_count=3,
            input_digest=record.input_digest,
            counts=(
                analytics_mod.MetricCount(label="draft", value=3).validated(),
                analytics_mod.MetricCount(label="reviewed", value=0).validated(),
                analytics_mod.MetricCount(label="finalized", value=0).validated(),
            ),
        )
        assert forged.validated().counts[0].value == 3
        assert by_label["draft"] == 1
