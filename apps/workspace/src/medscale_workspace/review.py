"""Human review and finalization workflow for CW-008 with deterministic fixtures only.

A review revision tracks one CW-007 source-linked draft through an explicit
state machine: DRAFT != REVIEWED != FINALIZED. Every human edit produces a new
immutable stored revision with explicit parent lineage; prior revisions are
never mutated in place. Edited spans are mechanically re-examined against the
reviewed draft: unchanged text preserves its support state, changed text must
be explicitly marked PARTIALLY_SUPPORTED or UNSUPPORTED with a recorded
invalidation reason, and ABSTAINED/FAILED spans are carried unchanged. Support
is never silently preserved across an edit.

FINALIZED is a terminal local-workspace state only. It never implies export,
transmission, submission, EHR commitment, ordering, prescribing, billing, or
any external action: FINALIZED != EXTERNALLY_WRITTEN. No external-write,
EHR-write, order, prescription, billing, network, or inference capability
exists in this module, and none may be added under this unit.

Direct DRAFT -> FINALIZED is forbidden: every finalization passes through
REVIEWED. FINALIZED revisions are terminal: no child revision may extend them,
so a finalized historical revision can never be silently mutated. Any further
correction needs a new draft cycle owned by a later capability.

Order, code, and task suggestions are DRAFT artifacts only. Accepting a
suggestion records reviewer agreement in the audit chain; it never executes,
submits, dispatches, or transmits anything.

This unit admits no PHI, no real patient data, no production use, and no real
generation model. Reviews are produced by a human actor identity admitted by
existing governance.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.draft import (
    SupportStatus,
    read_draft,
    validate_draft_support,
)
from medscale_workspace.errors import (
    ObjectNotFoundError,
    ReviewConflictError,
    ReviewInputError,
    ReviewRevisionError,
    ReviewSuggestionError,
    ReviewSupportError,
    ReviewTransitionError,
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

REVIEW_NAMESPACE = UUID("c41f2a77-9b3e-4c5d-8e6f-7a8b9c0d1e2f")
SUGGESTION_NAMESPACE = UUID("d52a3b88-0c4f-4d6e-9f7a-8b9c0d1e2f3a")
REVIEW_REVISION = "review-00000001"
PRODUCER_VERSION = "cw008-v1"
MAXIMUM_SPANS = 64
MAXIMUM_SUGGESTIONS = 32
MAXIMUM_TEXT_CHARS = 1024
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_OCCURRED_AT_CHARS = 64


class ReviewStatus(StrEnum):
    """Legal lifecycle states of a review revision. Never collapsed."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"


class SuggestionKind(StrEnum):
    """Admitted order/code/task suggestion classes. Draft artifacts only."""

    ORDER = "order"
    CODE = "code"
    TASK = "task"


class SuggestionStatus(StrEnum):
    """Lifecycle state of a suggestion. Suggestions never leave draft."""

    DRAFT = "draft"


class SuggestionDecision(StrEnum):
    """Reviewer decision recorded for one suggestion. One-way from pending."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class InvalidationReason(StrEnum):
    """Admitted reasons an edit changed a span support state."""

    EDIT_LOST_SUPPORT = "edit_lost_support"
    EDIT_PARTIAL_SUPPORT = "edit_partial_support"


# DRAFT may remain DRAFT (edit) or advance to REVIEWED. REVIEWED may return to
# DRAFT as a new revision (rework), stay REVIEWED for suggestion decisions, or
# advance to FINALIZED. FINALIZED is terminal and absent from this map.
LEGAL_TRANSITIONS = {
    ReviewStatus.DRAFT: (ReviewStatus.DRAFT, ReviewStatus.REVIEWED),
    ReviewStatus.REVIEWED: (
        ReviewStatus.DRAFT,
        ReviewStatus.REVIEWED,
        ReviewStatus.FINALIZED,
    ),
}


@dataclass(frozen=True, slots=True)
class SuggestionRecord:
    """One order/code/task suggestion. A draft artifact: never executable."""

    suggestion_id: UUID
    kind: SuggestionKind
    text: str
    status: SuggestionStatus
    decision: SuggestionDecision

    def validated(self):
        if not isinstance(self.suggestion_id, UUID):
            raise ReviewInputError("a suggestion id must be a UUID value")
        if not isinstance(self.kind, SuggestionKind):
            raise ReviewSuggestionError("a suggestion kind is not admitted here")
        text = _admit_text(self.text, "suggestion text")
        if not isinstance(self.status, SuggestionStatus):
            raise ReviewSuggestionError("a suggestion status is not admitted here")
        if self.status is not SuggestionStatus.DRAFT:
            raise ReviewSuggestionError("a suggestion must remain a draft artifact")
        if not isinstance(self.decision, SuggestionDecision):
            raise ReviewSuggestionError("a suggestion decision is not admitted here")
        return SuggestionRecord(
            suggestion_id=self.suggestion_id,
            kind=self.kind,
            text=text,
            status=self.status,
            decision=self.decision,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "decision": admitted.decision.value,
            "kind": admitted.kind.value,
            "status": admitted.status.value,
            "suggestion_id": str(admitted.suggestion_id),
            "text": admitted.text,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ReviewInputError("a stored suggestion must be a JSON object")
        expected = {"decision", "kind", "status", "suggestion_id", "text"}
        if set(document) != expected:
            raise ReviewInputError("a stored suggestion carries unadmitted members")
        try:
            suggestion_id = UUID(str(document["suggestion_id"]))
            kind = SuggestionKind(str(document["kind"]))
            status = SuggestionStatus(str(document["status"]))
            decision = SuggestionDecision(str(document["decision"]))
        except ValueError as error:
            raise ReviewInputError("a stored suggestion identity is not admitted") from error
        return SuggestionRecord(
            suggestion_id=suggestion_id,
            kind=kind,
            text=_string_member(document, "text"),
            status=status,
            decision=decision,
        ).validated()


@dataclass(frozen=True, slots=True)
class SpanReview:
    """Reviewer state of one draft span inside one review revision."""

    span_id: str
    text: str
    prior_status: SupportStatus
    current_status: SupportStatus
    invalidation_reason: str

    def validated(self):
        span_id = _admit_identifier(self.span_id, "span id")
        text = _admit_text(self.text, "span text")
        if not isinstance(self.prior_status, SupportStatus):
            raise ReviewSupportError("a span prior status is not admitted here")
        if not isinstance(self.current_status, SupportStatus):
            raise ReviewSupportError("a span current status is not admitted here")
        reason = _admit_invalidation_reason(self.invalidation_reason)
        return SpanReview(
            span_id=span_id,
            text=text,
            prior_status=self.prior_status,
            current_status=self.current_status,
            invalidation_reason=reason,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "current_status": admitted.current_status.value,
            "invalidation_reason": admitted.invalidation_reason,
            "prior_status": admitted.prior_status.value,
            "span_id": admitted.span_id,
            "text": admitted.text,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ReviewInputError("a stored span review must be a JSON object")
        expected = {
            "current_status",
            "invalidation_reason",
            "prior_status",
            "span_id",
            "text",
        }
        if set(document) != expected:
            raise ReviewInputError("a stored span review carries unadmitted members")
        try:
            prior_status = SupportStatus(str(document["prior_status"]))
            current_status = SupportStatus(str(document["current_status"]))
        except ValueError as error:
            raise ReviewInputError("a stored span review status is not admitted") from error
        return SpanReview(
            span_id=_string_member(document, "span_id"),
            text=_string_member(document, "text"),
            prior_status=prior_status,
            current_status=current_status,
            invalidation_reason=_string_member(document, "invalidation_reason"),
        ).validated()


@dataclass(frozen=True, slots=True)
class ReviewRecord:
    """One immutable human review revision bound to exact identities."""

    workspace_id: UUID
    session_id: UUID
    draft_id: UUID
    review_id: UUID
    revision_number: int
    parent_review_id: UUID
    status: ReviewStatus
    spans: tuple
    suggestions: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise ReviewInputError("a workspace id must be a UUID value")
        if not isinstance(self.session_id, UUID):
            raise ReviewInputError("a session id must be a UUID value")
        if not isinstance(self.draft_id, UUID):
            raise ReviewInputError("a draft id must be a UUID value")
        if not isinstance(self.review_id, UUID):
            raise ReviewInputError("a review id must be a UUID value")
        number = _admit_revision_number(self.revision_number)
        if not isinstance(self.parent_review_id, UUID):
            raise ReviewRevisionError("a parent review id must be a UUID value")
        if not isinstance(self.status, ReviewStatus):
            raise ReviewTransitionError("a review status is not admitted here")
        if not isinstance(self.spans, tuple):
            raise ReviewSupportError("review spans must be a tuple")
        if len(self.spans) < 1 or len(self.spans) > MAXIMUM_SPANS:
            raise ReviewSupportError("a review carries an unadmitted span count")
        checked_spans = tuple(
            item.validated() if isinstance(item, SpanReview) else None for item in self.spans
        )
        if any(item is None for item in checked_spans):
            raise ReviewSupportError("review spans need SpanReview instances")
        _check_duplicate_span_ids(checked_spans)
        if not isinstance(self.suggestions, tuple):
            raise ReviewSuggestionError("review suggestions must be a tuple")
        if len(self.suggestions) > MAXIMUM_SUGGESTIONS:
            raise ReviewSuggestionError("a review carries an unadmitted suggestion count")
        checked_suggestions = tuple(
            item.validated() if isinstance(item, SuggestionRecord) else None
            for item in self.suggestions
        )
        if any(item is None for item in checked_suggestions):
            raise ReviewSuggestionError("review suggestions need SuggestionRecord instances")
        _check_duplicate_suggestion_ids(checked_suggestions)
        return ReviewRecord(
            workspace_id=self.workspace_id,
            session_id=self.session_id,
            draft_id=self.draft_id,
            review_id=self.review_id,
            revision_number=number,
            parent_review_id=self.parent_review_id,
            status=self.status,
            spans=checked_spans,
            suggestions=checked_suggestions,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "draft_id": str(admitted.draft_id),
            "parent_review_id": str(admitted.parent_review_id),
            "policy_version": POLICY_VERSION,
            "review_id": str(admitted.review_id),
            "review_revision": REVIEW_REVISION,
            "revision_number": admitted.revision_number,
            "session_id": str(admitted.session_id),
            "spans": [item.to_document() for item in admitted.spans],
            "status": admitted.status.value,
            "suggestions": [item.to_document() for item in admitted.suggestions],
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ReviewInputError("a stored review must be a JSON object")
        expected = {
            "data_class",
            "draft_id",
            "parent_review_id",
            "policy_version",
            "review_id",
            "review_revision",
            "revision_number",
            "session_id",
            "spans",
            "status",
            "suggestions",
            "workspace_id",
        }
        if set(document) != expected:
            raise ReviewInputError("a stored review carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise ReviewInputError("a stored review data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise ReviewInputError("a stored review policy version is not supported")
        if document["review_revision"] != REVIEW_REVISION:
            raise ReviewRevisionError("a stored review revision is mismatched")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            session_id = UUID(str(document["session_id"]))
            draft_id = UUID(str(document["draft_id"]))
            review_id = UUID(str(document["review_id"]))
            parent_review_id = UUID(str(document["parent_review_id"]))
            status = ReviewStatus(str(document["status"]))
        except ValueError as error:
            raise ReviewInputError("a stored review identity is not admitted") from error
        raw_spans = document["spans"]
        if not isinstance(raw_spans, list):
            raise ReviewInputError("stored review spans must be a JSON array")
        spans = tuple(SpanReview.from_document(item) for item in raw_spans)
        raw_suggestions = document["suggestions"]
        if not isinstance(raw_suggestions, list):
            raise ReviewInputError("stored review suggestions must be a JSON array")
        suggestions = tuple(SuggestionRecord.from_document(item) for item in raw_suggestions)
        return ReviewRecord(
            workspace_id=workspace_id,
            session_id=session_id,
            draft_id=draft_id,
            review_id=review_id,
            revision_number=document["revision_number"],
            parent_review_id=parent_review_id,
            status=status,
            spans=spans,
            suggestions=suggestions,
        ).validated()


def review_id_for(workspace_id, session_id, draft_id, revision_number):
    """Return the deterministic review identity for one draft revision number."""
    if not isinstance(workspace_id, UUID):
        raise ReviewInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise ReviewInputError("a session id must be a UUID value")
    if not isinstance(draft_id, UUID):
        raise ReviewInputError("a draft id must be a UUID value")
    number = _admit_revision_number(revision_number)
    return uuid5(
        REVIEW_NAMESPACE,
        ":".join((str(workspace_id), str(session_id), str(draft_id), str(number))),
    )


def suggestion_id_for(workspace_id, session_id, draft_id, kind, text):
    """Return the deterministic suggestion identity for one suggestion text."""
    if not isinstance(workspace_id, UUID):
        raise ReviewInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise ReviewInputError("a session id must be a UUID value")
    if not isinstance(draft_id, UUID):
        raise ReviewInputError("a draft id must be a UUID value")
    if not isinstance(kind, SuggestionKind):
        raise ReviewSuggestionError("a suggestion kind is not admitted here")
    admitted = _admit_text(text, "suggestion text")
    digest = hashlib.sha256(admitted.encode("utf-8")).hexdigest()
    return uuid5(
        SUGGESTION_NAMESPACE,
        ":".join((str(workspace_id), str(session_id), str(draft_id), kind.value, digest)),
    )


def review_binding(workspace_id, review_id):
    """Return the store binding of one review revision."""
    if not isinstance(workspace_id, UUID):
        raise ReviewInputError("a workspace id must be a UUID value")
    if not isinstance(review_id, UUID):
        raise ReviewInputError("a review id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=review_id,
        object_type=WorkspaceObjectType.CLINICAL_REVIEW,
        object_revision=REVIEW_REVISION,
    )


def review_payload_bytes(review):
    """Return the canonical storage payload of one review revision."""
    if not isinstance(review, ReviewRecord):
        raise ReviewInputError("a review payload needs a ReviewRecord instance")
    return _canonical_bytes(review.to_document())


def _provenance_review_state(status):
    if status is ReviewStatus.DRAFT:
        return ReviewState.DRAFT
    if status is ReviewStatus.REVIEWED:
        return ReviewState.REVIEWED
    if status is ReviewStatus.FINALIZED:
        return ReviewState.FINALIZED
    raise ReviewTransitionError("a review status is not admitted here")


def create_review(store, trail, draft, actor_id, occurred_at):
    """Open the genesis DRAFT review revision for one stored draft."""
    if not isinstance(store, WorkspaceStore):
        raise ReviewInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ReviewInputError("an audit trail is required")
    validated_draft = validate_draft_support(store, draft)
    if validated_draft.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a review crossed the workspace boundary")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    spans = tuple(
        SpanReview(
            span_id=span.span_id,
            text=span.text,
            prior_status=span.status,
            current_status=span.status,
            invalidation_reason="",
        )
        for span in validated_draft.spans
    )
    review = ReviewRecord(
        workspace_id=validated_draft.workspace_id,
        session_id=validated_draft.session_id,
        draft_id=validated_draft.draft_id,
        review_id=review_id_for(
            validated_draft.workspace_id,
            validated_draft.session_id,
            validated_draft.draft_id,
            1,
        ),
        revision_number=1,
        parent_review_id=validated_draft.draft_id,
        status=ReviewStatus.DRAFT,
        spans=spans,
        suggestions=(),
    ).validated()
    _store_revision(store, trail, review, validated_draft, actor, moment)
    return review_binding(review.workspace_id, review.review_id)


def revise_review(
    store,
    trail,
    parent_review_id,
    status,
    spans,
    suggestions,
    actor_id,
    occurred_at,
):
    """Store one child review revision after mechanical transition checks.

    The caller supplies the complete new span set, suggestion set, and target
    status explicitly; this function admits the revision only when every
    transition, lineage, support, and suggestion rule holds, failing closed.
    """
    if not isinstance(store, WorkspaceStore):
        raise ReviewInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ReviewInputError("an audit trail is required")
    if not isinstance(parent_review_id, UUID):
        raise ReviewRevisionError("a parent review id must be a UUID value")
    if not isinstance(status, ReviewStatus):
        raise ReviewTransitionError("a review status is not admitted here")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    parent = read_review(store, parent_review_id)
    if parent.status is ReviewStatus.FINALIZED:
        raise ReviewTransitionError("a finalized revision is terminal and immutable")
    if status not in LEGAL_TRANSITIONS[parent.status]:
        raise ReviewTransitionError("the requested review transition is not legal")
    validated_draft = validate_draft_support(store, read_draft(store, parent.draft_id))
    checked_spans = _admit_span_set(spans)
    checked_suggestions = _admit_suggestion_set(suggestions)
    _check_span_support_against_draft(checked_spans, validated_draft)
    parent_texts = {item.span_id: item.text for item in parent.spans}
    new_texts = {item.span_id: item.text for item in checked_spans}
    if new_texts != parent_texts and status is not ReviewStatus.DRAFT:
        raise ReviewTransitionError("edited spans force the revision back to draft")
    if status in (ReviewStatus.REVIEWED, ReviewStatus.FINALIZED):
        failed = [
            item.span_id for item in checked_spans if item.current_status is SupportStatus.FAILED
        ]
        if failed:
            raise ReviewTransitionError("a failed span cannot be reviewed or finalized")
    _check_suggestion_lineage(checked_suggestions, parent, validated_draft)
    if (
        status is parent.status
        and new_texts == parent_texts
        and tuple(item.current_status for item in checked_spans)
        == tuple(item.current_status for item in parent.spans)
        and tuple(item.invalidation_reason for item in checked_spans)
        == tuple(item.invalidation_reason for item in parent.spans)
        and checked_suggestions == parent.suggestions
    ):
        raise ReviewRevisionError("an unchanged review creates no new revision")
    review = ReviewRecord(
        workspace_id=parent.workspace_id,
        session_id=parent.session_id,
        draft_id=parent.draft_id,
        review_id=review_id_for(
            parent.workspace_id, parent.session_id, parent.draft_id, parent.revision_number + 1
        ),
        revision_number=parent.revision_number + 1,
        parent_review_id=parent.review_id,
        status=status,
        spans=checked_spans,
        suggestions=checked_suggestions,
    ).validated()
    _store_revision(store, trail, review, validated_draft, actor, moment)
    _record_suggestion_decisions(trail, parent, review, actor, moment)
    return review_binding(review.workspace_id, review.review_id)


def read_review(store, review_id):
    """Read and verify one stored review revision with its full chain."""
    if not isinstance(store, WorkspaceStore):
        raise ReviewInputError("a workspace store is required")
    if not isinstance(review_id, UUID):
        raise ReviewInputError("a review id must be a UUID value")
    binding = review_binding(store.workspace_id, review_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ReviewInputError("the review identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ReviewInputError("a stored review is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ReviewInputError("a stored review is not JSON") from error
    review = ReviewRecord.from_document(document)
    if review.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a review crossed the workspace boundary")
    if review.review_id != review_id:
        raise ReviewInputError("a stored review identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return validate_review_chain(store, review)


def validate_review_chain(store, review):
    """Mechanically validate one review revision against its draft and lineage."""
    if not isinstance(store, WorkspaceStore):
        raise ReviewInputError("a workspace store is required")
    admitted = review.validated() if isinstance(review, ReviewRecord) else None
    if admitted is None:
        raise ReviewInputError("chain validation needs a ReviewRecord instance")
    if admitted.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a review crossed the workspace boundary")
    validated_draft = validate_draft_support(store, read_draft(store, admitted.draft_id))
    if validated_draft.session_id != admitted.session_id:
        raise ReviewRevisionError("a review crossed the session boundary")
    expected_id = review_id_for(
        admitted.workspace_id, admitted.session_id, admitted.draft_id, admitted.revision_number
    )
    if admitted.review_id != expected_id:
        raise ReviewRevisionError("a review identity does not match its lineage")
    if admitted.revision_number == 1:
        if admitted.parent_review_id != admitted.draft_id:
            raise ReviewRevisionError("a genesis review must be parented to its draft")
        if admitted.status is not ReviewStatus.DRAFT:
            raise ReviewTransitionError("a genesis review must open as draft")
        parent = None
    else:
        expected_parent = review_id_for(
            admitted.workspace_id,
            admitted.session_id,
            admitted.draft_id,
            admitted.revision_number - 1,
        )
        if admitted.parent_review_id != expected_parent:
            raise ReviewRevisionError("a review parent does not match its lineage")
        parent = read_review(store, expected_parent)
        if admitted.status not in LEGAL_TRANSITIONS[parent.status]:
            raise ReviewTransitionError("a stored review transition is not legal")
    _check_span_support_against_draft(admitted.spans, validated_draft)
    _check_suggestion_lineage(admitted.suggestions, parent, validated_draft)
    return admitted


def _store_revision(store, trail, review, validated_draft, actor, moment):
    binding = review_binding(review.workspace_id, review.review_id)
    payload = review_payload_bytes(review)
    source_refs = (
        SourceRef(
            kind=SourceKind.HUMAN_EDIT,
            source_id="review-parent",
            source_revision=str(review.parent_review_id),
        ).validated(),
    )
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=source_refs,
        review_state=_provenance_review_state(review.status),
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise ReviewConflictError("the review revision identity already exists") from error
    event_type = (
        AuditEventType.NOTE_FINALIZE
        if review.status is ReviewStatus.FINALIZED
        else AuditEventType.OBJECT_CREATE
    )
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
        event_type=event_type,
    )


def _record_suggestion_decisions(trail, parent, review, actor, moment):
    previous = {item.suggestion_id: item.decision for item in parent.suggestions}
    binding = review_binding(review.workspace_id, review.review_id)
    payload = review_payload_bytes(review)
    for item in review.suggestions:
        before = previous.get(item.suggestion_id, SuggestionDecision.PENDING)
        if before is not SuggestionDecision.PENDING and before is not item.decision:
            raise ReviewSuggestionError("a recorded suggestion decision is immutable")
        if before is SuggestionDecision.PENDING and item.decision is not SuggestionDecision.PENDING:
            event_type = (
                AuditEventType.SUGGESTION_ACCEPT
                if item.decision is SuggestionDecision.ACCEPTED
                else AuditEventType.SUGGESTION_REJECT
            )
            reference = AuditObjectRef(
                object_id=binding.object_id,
                object_type=binding.object_type,
                object_revision=binding.object_revision,
                content_digest=content_digest_of(payload),
            )
            trail.append(
                event_type=event_type,
                actor_id=actor,
                occurred_at=moment,
                object_refs=(reference,),
                metadata=(
                    ("suggestion_id", str(item.suggestion_id)),
                    ("decision", item.decision.value),
                ),
            )


def _check_span_support_against_draft(spans, validated_draft):
    by_id = {span.span_id: span for span in validated_draft.spans}
    if {item.span_id for item in spans} != set(by_id):
        raise ReviewSupportError("a review must cover exactly the draft span set")
    for item in spans:
        draft_span = by_id[item.span_id]
        if item.prior_status is not draft_span.status:
            raise ReviewSupportError("a span prior status does not match the draft")
        if draft_span.status in (SupportStatus.ABSTAINED, SupportStatus.FAILED):
            if (
                item.text != draft_span.text
                or item.current_status is not draft_span.status
                or item.invalidation_reason != ""
            ):
                raise ReviewSupportError("an abstained or failed span is carried unchanged")
            continue
        if item.text == draft_span.text:
            if item.current_status is not draft_span.status or item.invalidation_reason != "":
                raise ReviewSupportError("unchanged text preserves its support state")
        elif item.current_status is SupportStatus.PARTIALLY_SUPPORTED:
            if item.invalidation_reason != InvalidationReason.EDIT_PARTIAL_SUPPORT.value:
                raise ReviewSupportError("partial support on edit needs its reason")
        elif item.current_status is SupportStatus.UNSUPPORTED:
            if item.invalidation_reason != InvalidationReason.EDIT_LOST_SUPPORT.value:
                raise ReviewSupportError("lost support on edit needs its reason")
        else:
            raise ReviewSupportError("edited text cannot retain supported status")


def _check_suggestion_lineage(suggestions, parent, validated_draft):
    seen = set()
    for item in suggestions:
        if item.suggestion_id in seen:
            raise ReviewSuggestionError("a suggestion identity is duplicated")
        seen.add(item.suggestion_id)
        expected = suggestion_id_for(
            validated_draft.workspace_id,
            validated_draft.session_id,
            validated_draft.draft_id,
            item.kind,
            item.text,
        )
        if item.suggestion_id != expected:
            raise ReviewSuggestionError("a suggestion identity does not match its content")
    previous = (
        {item.suggestion_id: item.decision for item in parent.suggestions}
        if parent is not None
        else {}
    )
    for item in suggestions:
        if item.suggestion_id not in previous:
            if item.decision is not SuggestionDecision.PENDING:
                raise ReviewSuggestionError("a new suggestion must enter as pending")
        elif previous[item.suggestion_id] is SuggestionDecision.PENDING:
            continue
        elif previous[item.suggestion_id] is not item.decision:
            raise ReviewSuggestionError("a recorded suggestion decision is immutable")


def _admit_span_set(spans):
    if not isinstance(spans, tuple):
        raise ReviewSupportError("review spans must be a tuple")
    if len(spans) < 1 or len(spans) > MAXIMUM_SPANS:
        raise ReviewSupportError("a review carries an unadmitted span count")
    checked = tuple(item.validated() if isinstance(item, SpanReview) else None for item in spans)
    if any(item is None for item in checked):
        raise ReviewSupportError("review spans need SpanReview instances")
    _check_duplicate_span_ids(checked)
    return checked


def _admit_suggestion_set(suggestions):
    if not isinstance(suggestions, tuple):
        raise ReviewSuggestionError("review suggestions must be a tuple")
    if len(suggestions) > MAXIMUM_SUGGESTIONS:
        raise ReviewSuggestionError("a review carries an unadmitted suggestion count")
    checked = tuple(
        item.validated() if isinstance(item, SuggestionRecord) else None for item in suggestions
    )
    if any(item is None for item in checked):
        raise ReviewSuggestionError("review suggestions need SuggestionRecord instances")
    _check_duplicate_suggestion_ids(checked)
    return checked


def _check_duplicate_span_ids(spans):
    seen = set()
    for item in spans:
        if item.span_id in seen:
            raise ReviewSupportError("a review carries a duplicated span id")
        seen.add(item.span_id)


def _check_duplicate_suggestion_ids(suggestions):
    seen = set()
    for item in suggestions:
        if item.suggestion_id in seen:
            raise ReviewSuggestionError("a review carries a duplicated suggestion id")
        seen.add(item.suggestion_id)


def _admit_revision_number(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ReviewRevisionError("a revision number must be an integer")
    if raw < 1:
        raise ReviewRevisionError("a revision number starts at one")
    return raw


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise ReviewInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ReviewInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise ReviewInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ReviewInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ReviewInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_text(raw, label):
    if not isinstance(raw, str):
        raise ReviewInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ReviewInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_TEXT_CHARS:
        raise ReviewInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ReviewInputError(f"{label} must be ASCII")
    for character in value:
        if not character.isprintable():
            raise ReviewInputError(f"{label} must not contain control characters")
    return value


def _admit_invalidation_reason(raw):
    if not isinstance(raw, str):
        raise ReviewSupportError("an invalidation reason must be a string")
    if raw == "":
        return ""
    try:
        reason = InvalidationReason(raw)
    except ValueError as error:
        raise ReviewSupportError("an invalidation reason is not admitted") from error
    return reason.value


def _admit_actor(raw):
    value = _admit_identifier(raw, "actor id")
    return value


def _admit_occurred_at(raw):
    value = _admit_text(raw, "review occurrence time")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise ReviewInputError("a review occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise ReviewInputError("a review occurrence time must be an ISO-8601 instant with a zone")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise ReviewInputError(f"a stored {name} must be a string")
    return value
