"""CW-015 adversarial tests: isolation, staleness, and boundary attacks."""

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
    AnalyticsConflictError,
    AnalyticsInputError,
    AnalyticsRevisionError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import content_digest_of  # noqa: E402 runtime import

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7dd9e9f4-1c3b-40b4-b10f-5b16db71b00f")
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


def test_duplicate_inputs_are_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                (review_ids[0], review_ids[0], review_ids[1]),
                ACTOR,
                T7,
            )
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store, trail, analytics_mod.MetricName.REVIEW_STATUS_COUNTS, "1", (), ACTOR, T7
            )


def test_unknown_or_foreign_inputs_are_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        unknown = UUID("11111111-2222-3333-4444-555555555555")
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                (review_ids[0], unknown),
                ACTOR,
                T7,
            )
        with pytest.raises(AnalyticsInputError):
            analytics_mod.read_analytics(store, unknown)


def test_cross_workspace_read_is_refused(tmp_path: Path) -> None:
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
        beta_root = tmp_path / "beta"
        beta_root.mkdir(parents=True, exist_ok=True)
        with (
            open_store(beta_root, WORKSPACE_BETA) as foreign,
            pytest.raises((AnalyticsInputError, WorkspaceIsolationError)),
        ):
            analytics_mod.read_analytics(foreign, binding.object_id)


def test_replay_collides_instead_of_overwriting(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        first = analytics_mod.compute_analytics(
            store,
            trail,
            analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
            "1",
            review_ids,
            ACTOR,
            T7,
        )
        with pytest.raises(AnalyticsConflictError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                (review_ids[2], review_ids[0], review_ids[1]),
                ACTOR,
                T7,
            )
        record = analytics_mod.read_analytics(store, first.object_id)
        assert record.input_count == 3


def test_malicious_metric_text_grants_no_capability(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        for hostile in (
            "review-status-counts;DROP TABLE analytics",
            "__import__('socket')",
            "review-status-counts\nEXPORT",
        ):
            with pytest.raises((AnalyticsInputError, AnalyticsRevisionError)):
                analytics_mod.compute_analytics(store, trail, hostile, "1", review_ids, ACTOR, T7)
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
        assert [item.label for item in record.counts] == ["draft", "reviewed", "finalized"]


def test_oversized_inputs_are_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        review_ids = stored_review_lineage(store, trail)
        assert len(review_ids) == 3
        oversized = tuple(review_ids[0] for _ in range(129))
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1",
                oversized,
                ACTOR,
                T7,
            )
        with pytest.raises(AnalyticsInputError):
            analytics_mod.compute_analytics(
                store,
                trail,
                analytics_mod.MetricName.REVIEW_STATUS_COUNTS,
                "1" * 65,
                review_ids,
                ACTOR,
                T7,
            )


def test_forged_result_documents_fail_closed(tmp_path: Path) -> None:
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
        tampered_counts = dict(document)
        tampered_counts["counts"] = [
            {"label": "draft", "value": 3},
            {"label": "reviewed", "value": 3},
            {"label": "finalized", "value": 3},
        ]
        with pytest.raises(AnalyticsRevisionError):
            analytics_mod.AnalyticsRecord.from_document(tampered_counts)
        tampered_class = dict(document)
        tampered_class["data_class"] = "RESEARCH_ARTIFACT"
        with pytest.raises(AnalyticsInputError):
            analytics_mod.AnalyticsRecord.from_document(tampered_class)
        tampered_labels = dict(document)
        tampered_labels["counts"] = [
            {"label": "patient-001", "value": 1},
            {"label": "reviewed", "value": 1},
            {"label": "finalized", "value": 1},
        ]
        with pytest.raises(AnalyticsInputError):
            analytics_mod.AnalyticsRecord.from_document(tampered_labels)


def test_stale_inputs_after_review_deletion(tmp_path: Path) -> None:
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
        assert record.input_count == 3
        analytics_mod.delete_analytics(store, trail, binding.object_id, ACTOR, T7)
        with pytest.raises(AnalyticsInputError):
            analytics_mod.read_analytics(store, binding.object_id)
