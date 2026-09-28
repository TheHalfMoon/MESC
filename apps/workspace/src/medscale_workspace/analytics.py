"""Local workspace analytics for CW-015 with deterministic fixtures only.

CW-015 computes local operational metrics without turning them into research
claims. Every computation is an explicit caller-invoked pure derivation over
exact stored CW-008 review revisions: the caller names a versioned metric
definition and a tuple of review identities, this module re-reads and
re-verifies each review against the store (chain, digest, workspace binding),
tallies the admitted aggregate, and stores one immutable analytics result with
CW-003 provenance and an audit record. Caller-supplied totals are never
trusted; there is no totals parameter at all.

Admitted metrics (name/version):

* ``review-status-counts/1`` -- counts supplied reviews by review status
  (draft, reviewed, finalized);
* ``review-suggestion-counts/1`` -- counts suggestions across supplied
  reviews by reviewer decision (pending, accepted, rejected).

Patient-sensitive dimensions are protected by construction: the only admitted
breakdowns are the workflow states above. No per-patient, per-session,
per-draft, per-actor, or per-identifier breakdown exists in this module; no
dimensions parameter exists, and result documents carry only aggregate counts
plus the input digest, never identifier lists. Residual-identifier behavior
fails closed because there is no identifier-bearing output to evaluate.

Analytics results are Workspace-domain operational state. They are stored with
the operational analytics data class, they never become research artifacts,
they never mutate MRL status, and they are never automatically exported or
telemetered. Export, if ever needed, is a separate explicit Domain X
quarantine decision owned by later governance; this module emits no export
event, performs no network I/O, runs no background collection, and holds no
network, filesystem, or model capability by design.

Response text and metric labels are data, not authority. Stored labels are
never evaluated, never executed, and never consulted for capability, policy,
or governance decisions. Malicious strings remain inert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import admit_data_class
from medscale_workspace.errors import (
    AnalyticsConflictError,
    AnalyticsInputError,
    AnalyticsRevisionError,
    AnalyticsStaleError,
    ObjectNotFoundError,
    ProvenanceDigestMismatchError,
    ReviewError,
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
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

ANALYTICS_NAMESPACE = UUID("7a15b015-0001-4000-8000-000000000015")
ANALYTICS_REVISION = "workspace-analytics-00000001"
PRODUCER_VERSION = "cw015-v1"
DERIVATION_METHOD = "cw015-deterministic-analytics"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw015-analytics/1"
ADMITTED_METRIC_VERSION = "1"
MAXIMUM_METRIC_NAME_CHARS = 64
MAXIMUM_LABEL_CHARS = 64
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_REVIEWS_PER_COMPUTATION = 128
MAXIMUM_COUNTS_PER_RESULT = 8
MAXIMUM_ANALYTICS_BYTES = 32768
MAXIMUM_OCCURRED_AT_CHARS = 64


class MetricName(StrEnum):
    """Admitted operational metric definitions. Aggregates only."""

    REVIEW_STATUS_COUNTS = "review-status-counts"
    REVIEW_SUGGESTION_COUNTS = "review-suggestion-counts"


@dataclass(frozen=True, slots=True)
class MetricCount:
    """One admitted aggregate count inside an analytics result."""

    label: str
    value: int

    def validated(self):
        label = _admit_label(self.label)
        value = _admit_count_value(self.value)
        return MetricCount(label=label, value=value)

    def to_document(self):
        admitted = self.validated()
        return {"label": admitted.label, "value": admitted.value}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise AnalyticsInputError("a stored metric count must be a JSON object")
        if set(document) != {"label", "value"}:
            raise AnalyticsInputError("a stored metric count carries unadmitted members")
        return MetricCount(
            label=_string_member(document, "label"),
            value=document["value"],
        ).validated()


@dataclass(frozen=True, slots=True)
class AnalyticsRecord:
    """One immutable locally computed operational aggregate."""

    workspace_id: UUID
    analytics_id: UUID
    metric_name: MetricName
    metric_version: str
    input_count: int
    input_digest: str
    counts: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise AnalyticsInputError("a workspace id must be a UUID value")
        if not isinstance(self.analytics_id, UUID):
            raise AnalyticsInputError("an analytics identity must be a UUID value")
        if not isinstance(self.metric_name, MetricName):
            raise AnalyticsInputError("a metric name is not admitted here")
        version = _admit_metric_version(self.metric_version)
        count = _admit_input_count(self.input_count)
        digest = _admit_digest(self.input_digest)
        if not isinstance(self.counts, tuple):
            raise AnalyticsInputError("analytics counts must be a tuple")
        if len(self.counts) < 1 or len(self.counts) > MAXIMUM_COUNTS_PER_RESULT:
            raise AnalyticsInputError("an analytics result carries an unadmitted count")
        checked = tuple(
            item.validated() if isinstance(item, MetricCount) else None for item in self.counts
        )
        if any(item is None for item in checked):
            raise AnalyticsInputError("analytics counts need MetricCount instances")
        _check_duplicate_labels(checked)
        _check_expected_labels(self.metric_name, checked)
        total = 0
        for item in checked:
            total = total + item.value
        if self.metric_name is MetricName.REVIEW_STATUS_COUNTS and total != count:
            raise AnalyticsRevisionError("status counts must sum to the input count")
        return AnalyticsRecord(
            workspace_id=self.workspace_id,
            analytics_id=self.analytics_id,
            metric_name=self.metric_name,
            metric_version=version,
            input_count=count,
            input_digest=digest,
            counts=checked,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "analytics_id": str(admitted.analytics_id),
            "analytics_revision": ANALYTICS_REVISION,
            "counts": [item.to_document() for item in admitted.counts],
            "data_class": _analytics_data_class_value(),
            "derivation_method": DERIVATION_METHOD,
            "derivation_method_version": DERIVATION_METHOD_VERSION,
            "input_count": admitted.input_count,
            "input_digest": admitted.input_digest,
            "metric_name": admitted.metric_name.value,
            "metric_version": admitted.metric_version,
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise AnalyticsInputError("a stored analytics result must be a JSON object")
        expected = {
            "analytics_id",
            "analytics_revision",
            "counts",
            "data_class",
            "derivation_method",
            "derivation_method_version",
            "input_count",
            "input_digest",
            "metric_name",
            "metric_version",
            "policy_version",
            "schema_version",
            "workspace_id",
        }
        if set(document) != expected:
            raise AnalyticsInputError("a stored analytics result carries unadmitted members")
        if document["analytics_revision"] != ANALYTICS_REVISION:
            raise AnalyticsRevisionError("a stored analytics revision is mismatched")
        if document["data_class"] != _analytics_data_class_value():
            raise AnalyticsInputError("a stored analytics data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise AnalyticsInputError("a stored analytics policy version is not supported")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise AnalyticsRevisionError("a stored analytics derivation method is mismatched")
        if document["derivation_method_version"] != DERIVATION_METHOD_VERSION:
            raise AnalyticsRevisionError("a stored analytics derivation version is mismatched")
        if document["schema_version"] != SCHEMA_VERSION:
            raise AnalyticsRevisionError("a stored analytics schema version is mismatched")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            analytics_id = UUID(str(document["analytics_id"]))
        except ValueError as error:
            raise AnalyticsInputError("a stored analytics identity is not admitted") from error
        metric_name = _admit_metric_name(document["metric_name"])
        raw_counts = document["counts"]
        if not isinstance(raw_counts, list):
            raise AnalyticsInputError("stored analytics counts must be a JSON array")
        counts = tuple(MetricCount.from_document(item) for item in raw_counts)
        return AnalyticsRecord(
            workspace_id=workspace_id,
            analytics_id=analytics_id,
            metric_name=metric_name,
            metric_version=_admit_metric_version(document["metric_version"]),
            input_count=document["input_count"],
            input_digest=_string_member(document, "input_digest"),
            counts=counts,
        ).validated()


def analytics_data_class_value():
    """Return the wire value of the operational analytics data class."""
    return _analytics_data_class_value()


def analytics_id_for(workspace_id, metric_name, metric_version, input_digest):
    """Return the deterministic analytics identity for one exact input set."""
    if not isinstance(workspace_id, UUID):
        raise AnalyticsInputError("a workspace id must be a UUID value")
    admitted_name = _admit_metric_name(metric_name)
    admitted_version = _admit_metric_version(metric_version)
    admitted_digest = _admit_digest(input_digest)
    return uuid5(
        ANALYTICS_NAMESPACE,
        ":".join((str(workspace_id), admitted_name.value, admitted_version, admitted_digest)),
    )


def analytics_binding(workspace_id, analytics_id):
    """Return the store binding of one analytics result."""
    if not isinstance(workspace_id, UUID):
        raise AnalyticsInputError("a workspace id must be a UUID value")
    if not isinstance(analytics_id, UUID):
        raise AnalyticsInputError("an analytics identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=analytics_id,
        object_type=WorkspaceObjectType.WORKSPACE_ANALYTICS,
        object_revision=ANALYTICS_REVISION,
    )


def analytics_payload_bytes(record):
    """Return the canonical storage payload of one analytics result."""
    if not isinstance(record, AnalyticsRecord):
        raise AnalyticsInputError("an analytics payload needs an AnalyticsRecord instance")
    return _canonical_bytes(record.to_document())


def compute_analytics(
    store,
    trail,
    metric_name,
    metric_version,
    review_ids,
    actor_id,
    occurred_at,
):
    """Compute one operational aggregate over exact stored review revisions.

    Each supplied review identity is re-read and re-verified against the
    store; tallies are derived from verified stored state, never from
    caller-supplied totals. The result is stored immutably with provenance
    and recorded with an object-create audit event. No export event is
    emitted, no telemetry is scheduled, and no research state is touched.
    """
    from medscale_workspace import review as review_mod

    if not isinstance(store, WorkspaceStore):
        raise AnalyticsInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise AnalyticsInputError("an audit trail is required")
    if not isinstance(store.workspace_id, UUID):
        raise AnalyticsInputError("a workspace store identity is required")
    workspace_id = store.workspace_id
    admitted_name = _admit_metric_name(metric_name)
    admitted_version = _admit_metric_version(metric_version)
    admitted_ids = _admit_review_ids(review_ids)
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    verified = []
    for review_id in admitted_ids:
        try:
            loaded = review_mod.read_review(store, review_id)
        except WorkspaceIsolationError:
            raise
        except ReviewError as error:
            raise AnalyticsInputError("an analytics input review is not admitted") from error
        if loaded.workspace_id != workspace_id:
            raise WorkspaceIsolationError("an analytics input crossed the workspace boundary")
        verified.append(loaded)
    if admitted_name is MetricName.REVIEW_STATUS_COUNTS:
        counts = _tally_review_statuses(verified)
    elif admitted_name is MetricName.REVIEW_SUGGESTION_COUNTS:
        counts = _tally_suggestion_decisions(verified)
    else:
        raise AnalyticsInputError("a metric name is not admitted here")
    input_digest = _input_digest_for(workspace_id, admitted_name, admitted_version, admitted_ids)
    record = AnalyticsRecord(
        workspace_id=workspace_id,
        analytics_id=analytics_id_for(workspace_id, admitted_name, admitted_version, input_digest),
        metric_name=admitted_name,
        metric_version=admitted_version,
        input_count=len(admitted_ids),
        input_digest=input_digest,
        counts=counts,
    ).validated()
    stored = _canonical_bytes(record.to_document())
    if len(stored) > MAXIMUM_ANALYTICS_BYTES:
        raise AnalyticsInputError("an analytics result exceeds the admitted size")
    source_refs = tuple(
        SourceRef(
            kind=SourceKind.ANALYTICS_INPUT,
            source_id=str(item.review_id),
            source_revision=str(item.revision_number),
            locator=admitted_name.value,
        ).validated()
        for item in verified
    )
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    provenance_record = describe_revision(
        binding=analytics_binding(workspace_id, record.analytics_id),
        payload=stored,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, provenance_record, stored)
    except StoreConflictError as error:
        raise AnalyticsConflictError("the analytics result identity already exists") from error
    trail.append(
        event_type=AuditEventType.OBJECT_CREATE,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=record.analytics_id,
                object_type=WorkspaceObjectType.WORKSPACE_ANALYTICS,
                object_revision=ANALYTICS_REVISION,
                content_digest=provenance_record.content_digest,
            ),
        ),
        metadata=(
            ("metric_name", admitted_name.value),
            ("metric_version", admitted_version),
            ("input_count", str(len(admitted_ids))),
            ("analytics_digest", provenance_record.content_digest),
        ),
    )
    return analytics_binding(workspace_id, record.analytics_id)


def read_analytics(store, analytics_id):
    """Read and verify one stored analytics result."""
    if not isinstance(store, WorkspaceStore):
        raise AnalyticsInputError("a workspace store is required")
    if not isinstance(analytics_id, UUID):
        raise AnalyticsInputError("an analytics identity must be a UUID value")
    binding = analytics_binding(store.workspace_id, analytics_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise AnalyticsInputError("the analytics identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise AnalyticsInputError("a stored analytics result is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise AnalyticsInputError("a stored analytics result is not JSON") from error
    record = AnalyticsRecord.from_document(document)
    if record.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("an analytics result crossed the workspace boundary")
    if record.analytics_id != analytics_id:
        raise AnalyticsInputError("a stored analytics identity does not match its binding")
    stored_provenance = read_provenance(store, binding)
    try:
        stored_provenance.verify_payload(raw)
    except ProvenanceDigestMismatchError as error:
        raise AnalyticsStaleError("an analytics digest no longer matches") from error
    return record.validated()


def delete_analytics(store, trail, analytics_id, actor_id, occurred_at):
    """Delete one analytics result; the audit trail survives."""
    if not isinstance(store, WorkspaceStore):
        raise AnalyticsInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise AnalyticsInputError("an audit trail is required")
    if not isinstance(analytics_id, UUID):
        raise AnalyticsInputError("an analytics identity must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    record = read_analytics(store, analytics_id)
    binding = analytics_binding(store.workspace_id, record.analytics_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def _tally_review_statuses(verified):
    from medscale_workspace import review as review_mod

    draft_total = 0
    reviewed_total = 0
    finalized_total = 0
    for item in verified:
        if item.status is review_mod.ReviewStatus.DRAFT:
            draft_total = draft_total + 1
        elif item.status is review_mod.ReviewStatus.REVIEWED:
            reviewed_total = reviewed_total + 1
        elif item.status is review_mod.ReviewStatus.FINALIZED:
            finalized_total = finalized_total + 1
        else:
            raise AnalyticsRevisionError("a review status is not admitted here")
    return (
        MetricCount(label="draft", value=draft_total).validated(),
        MetricCount(label="reviewed", value=reviewed_total).validated(),
        MetricCount(label="finalized", value=finalized_total).validated(),
    )


def _tally_suggestion_decisions(verified):
    from medscale_workspace import review as review_mod

    pending_total = 0
    accepted_total = 0
    rejected_total = 0
    for item in verified:
        for suggestion in item.suggestions:
            if suggestion.decision is review_mod.SuggestionDecision.PENDING:
                pending_total = pending_total + 1
            elif suggestion.decision is review_mod.SuggestionDecision.ACCEPTED:
                accepted_total = accepted_total + 1
            elif suggestion.decision is review_mod.SuggestionDecision.REJECTED:
                rejected_total = rejected_total + 1
            else:
                raise AnalyticsRevisionError("a suggestion decision is not admitted here")
    return (
        MetricCount(label="pending", value=pending_total).validated(),
        MetricCount(label="accepted", value=accepted_total).validated(),
        MetricCount(label="rejected", value=rejected_total).validated(),
    )


def _input_digest_for(workspace_id, metric_name, metric_version, review_ids):
    ordered = sorted(str(item) for item in review_ids)
    document = {
        "metric_name": metric_name.value,
        "metric_version": metric_version,
        "review_ids": ordered,
        "workspace_id": str(workspace_id),
    }
    return content_digest_of(_canonical_bytes(document))


def _analytics_data_class_value():
    return admit_data_class("OPERATIONAL_ANALYTICS").value


def _admit_metric_name(raw):
    if isinstance(raw, MetricName):
        return raw
    if isinstance(raw, str):
        try:
            return MetricName(raw.strip())
        except ValueError as error:
            raise AnalyticsInputError("a metric name is not admitted here") from error
    raise AnalyticsInputError("a metric name must be admitted here")


def _admit_metric_version(raw):
    if not isinstance(raw, str):
        raise AnalyticsInputError("a metric version must be a string")
    value = raw.strip()
    if not value:
        raise AnalyticsInputError("a metric version must be non-empty")
    if len(value) > MAXIMUM_METRIC_NAME_CHARS:
        raise AnalyticsInputError("a metric version is longer than the admitted maximum")
    if not value.isascii():
        raise AnalyticsInputError("a metric version must be ASCII")
    if value != ADMITTED_METRIC_VERSION:
        raise AnalyticsRevisionError("a metric version is not supported here")
    return value


def _admit_review_ids(raw):
    if not isinstance(raw, tuple):
        raise AnalyticsInputError("review identities must be a tuple")
    if len(raw) < 1 or len(raw) > MAXIMUM_REVIEWS_PER_COMPUTATION:
        raise AnalyticsInputError("an analytics computation carries an unadmitted input count")
    for item in raw:
        if not isinstance(item, UUID):
            raise AnalyticsInputError("a review identity must be a UUID value")
    seen = set()
    for item in raw:
        if item in seen:
            raise AnalyticsInputError("a review identity is duplicated")
        seen.add(item)
    return raw


def _admit_input_count(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise AnalyticsInputError("an input count must be an integer")
    if raw < 1 or raw > MAXIMUM_REVIEWS_PER_COMPUTATION:
        raise AnalyticsInputError("an input count is not admitted here")
    return raw


def _admit_count_value(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise AnalyticsInputError("a metric count value must be an integer")
    if raw < 0 or raw > MAXIMUM_REVIEWS_PER_COMPUTATION:
        raise AnalyticsInputError("a metric count value is not admitted here")
    return raw


def _admit_label(raw):
    if not isinstance(raw, str):
        raise AnalyticsInputError("a metric label must be a string")
    value = raw.strip()
    if not value:
        raise AnalyticsInputError("a metric label must be non-empty")
    if len(value) > MAXIMUM_LABEL_CHARS:
        raise AnalyticsInputError("a metric label is longer than the admitted maximum")
    if not value.isascii():
        raise AnalyticsInputError("a metric label must be ASCII")
    for character in value:
        if not character.isprintable():
            raise AnalyticsInputError("a metric label must not contain control characters")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str):
        raise AnalyticsInputError("a content digest must be a string")
    value = raw.strip()
    if not value.startswith("sha256:"):
        raise AnalyticsInputError("a content digest must be a sha256 digest")
    remainder = value[len("sha256:") :]
    if len(remainder) != 64:
        raise AnalyticsInputError("a content digest must carry 64 hex characters")
    for character in remainder:
        if character not in "0123456789abcdef":
            raise AnalyticsInputError("a content digest must carry lowercase hex")
    return value


def _check_duplicate_labels(counts):
    seen = set()
    for item in counts:
        if item.label in seen:
            raise AnalyticsInputError("a metric label is duplicated")
        seen.add(item.label)


def _check_expected_labels(metric_name, counts):
    if metric_name is MetricName.REVIEW_STATUS_COUNTS:
        expected = ("draft", "reviewed", "finalized")
    elif metric_name is MetricName.REVIEW_SUGGESTION_COUNTS:
        expected = ("pending", "accepted", "rejected")
    else:
        raise AnalyticsInputError("a metric name is not admitted here")
    observed = tuple(item.label for item in counts)
    if observed != expected:
        raise AnalyticsInputError("an analytics result carries unadmitted labels")


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise AnalyticsInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise AnalyticsInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise AnalyticsInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise AnalyticsInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise AnalyticsInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_occurred_at(raw):
    value = _admit_identifier(raw, "analytics occurrence time")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise AnalyticsInputError("an analytics occurrence time is longer than admitted")
    if len(value) < 20 or value[10:11] != "T":
        raise AnalyticsInputError("an analytics occurrence time must be an ISO instant with zone")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise AnalyticsInputError(f"a stored {name} must be a string")
    return value
