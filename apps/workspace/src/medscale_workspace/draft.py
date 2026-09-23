"""Source-linked clinical draft engine for CW-007 with deterministic fixtures only.

A draft is a collection of typed spans. Each span carries one support status
(SUPPORTED, PARTIALLY_SUPPORTED, UNSUPPORTED, ABSTAINED, FAILED) and, where the
status requires it, explicit references to transcript source ranges. A backend
is never trusted to self-certify support: host validation reloads the admitted
transcript from the protected store and verifies workspace, session, transcript
identity and revision, segment existence, character offsets, source text digest,
span identity, admitted support relation, admitted template identity, and the
admitted input bundle digest. Any malformed backend result fails closed.

This unit admits no real generation model. Producer, model, and runtime
identities below are explicit placeholder values for the deterministic path.
A future real-model path needs a separate model ADR plus explicit Founder
ratification. Mutable revision labels are never admitted.

Stored drafts are DRAFT revisions only. No review, finalization, export, or
write path exists in this module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.asr import TRANSCRIPT_REVISION, read_transcript
from medscale_workspace.audit import AuditEventType, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    AsrInputError,
    DraftBackendError,
    DraftConflictError,
    DraftInputError,
    DraftRevisionError,
    DraftSupportError,
    DraftTemplateError,
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

DRAFT_NAMESPACE = UUID("9a4b6c2d-7f1e-4a3b-8c5d-2e6f8a9b0c1d")
DRAFT_REVISION = "draft-00000001"
PRODUCER_ID = "cw007-synthetic-draft-backend"
PRODUCER_VERSION = "cw007-v1"
MODEL_ID = "synthetic-cw007-draft-backend"
MODEL_REVISION = "synthetic-00000001"
RUNTIME_NAME = "cw007-synthetic-runtime"
RUNTIME_VERSION = "1"
TEMPLATE_ID = "cw007-synthetic-soap/1"
TEMPLATE_REVISION = "template-00000001"
TEMPLATE_SECTIONS = ("subjective", "objective", "assessment", "plan")
MUTABLE_REVISIONS = ("main", "latest")
MAXIMUM_SPANS = 64
MAXIMUM_SPAN_CHARS = 1024
MAXIMUM_TEXT_CHARS = 4096
MAXIMUM_REASON_CHARS = 512
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_DIGEST_CHARS = 128
MAXIMUM_OCCURRED_AT_CHARS = 64


class DraftStatus(StrEnum):
    """Lifecycle state of a stored draft. Only drafts exist here."""

    DRAFT = "draft"


class SupportStatus(StrEnum):
    """Mechanical support state of one generated span. Never collapsed."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    ABSTAINED = "abstained"
    FAILED = "failed"


class SupportRelation(StrEnum):
    """Admitted relation between a span and one source range."""

    EXACT_QUOTE = "exact_quote"
    CLOSE_PARAPHRASE = "close_paraphrase"
    SUMMARY_OF_RANGE = "summary_of_range"


class FailureReason(StrEnum):
    """Admitted failure causes. Distinct from abstention by construction."""

    EMPTY_INPUT = "empty_input"
    MISSING_TRANSCRIPT = "missing_transcript"
    TRANSCRIPT_MISMATCH = "transcript_mismatch"
    SOURCE_RANGE_INVALID = "source_range_invalid"
    SOURCE_DIGEST_MISMATCH = "source_digest_mismatch"
    TEMPLATE_MISMATCH = "template_mismatch"
    INPUT_BUNDLE_MISMATCH = "input_bundle_mismatch"
    BACKEND_MALFORMED = "backend_malformed"
    STORE_CONFLICT = "store_conflict"


class AbstentionReason(StrEnum):
    """Admitted abstention causes. Distinct from failure and from unsupported."""

    INSUFFICIENT_SOURCE = "insufficient_source"
    LOW_CONFIDENCE = "low_confidence"
    OUT_OF_SCOPE_TEMPLATE = "out_of_scope_template"


@dataclass(frozen=True, slots=True)
class TemplateIdentity:
    """Governed template identity bound to every stored draft."""

    template_id: str
    template_revision: str
    template_digest: str

    def validated(self):
        template_id = _admit_identifier(self.template_id, "template id")
        revision = _admit_identifier(self.template_revision, "template revision")
        digest = _admit_digest(self.template_digest, "template digest")
        if template_id != TEMPLATE_ID:
            raise DraftTemplateError("the template id is not admitted here")
        if revision != TEMPLATE_REVISION:
            raise DraftTemplateError("the template revision is stale or mismatched")
        expected = _expected_template_digest()
        if digest != expected:
            raise DraftTemplateError("the template digest is mismatched")
        return TemplateIdentity(
            template_id=template_id, template_revision=revision, template_digest=digest
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "template_digest": admitted.template_digest,
            "template_id": admitted.template_id,
            "template_revision": admitted.template_revision,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftTemplateError("a stored template must be a JSON object")
        expected = {"template_digest", "template_id", "template_revision"}
        if set(document) != expected:
            raise DraftTemplateError("a stored template carries unadmitted members")
        return TemplateIdentity(
            template_id=_string_member(document, "template_id"),
            template_revision=_string_member(document, "template_revision"),
            template_digest=_string_member(document, "template_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    """Placeholder model identity for the deterministic path only."""

    model_id: str
    model_revision: str

    def validated(self):
        model_id = _admit_identifier(self.model_id, "model id")
        revision = _admit_identifier(self.model_revision, "model revision")
        if revision in MUTABLE_REVISIONS:
            raise DraftRevisionError("a mutable model revision is never admitted")
        if model_id != MODEL_ID:
            raise DraftRevisionError("the model id is not admitted here")
        if revision != MODEL_REVISION:
            raise DraftRevisionError("the model revision is mismatched")
        return ModelIdentity(model_id=model_id, model_revision=revision)

    def to_document(self):
        admitted = self.validated()
        return {"model_id": admitted.model_id, "model_revision": admitted.model_revision}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftRevisionError("a stored model identity must be a JSON object")
        expected = {"model_id", "model_revision"}
        if set(document) != expected:
            raise DraftRevisionError("a stored model identity carries unadmitted members")
        return ModelIdentity(
            model_id=_string_member(document, "model_id"),
            model_revision=_string_member(document, "model_revision"),
        ).validated()


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    """Placeholder runtime identity for the deterministic path only."""

    runtime_name: str
    runtime_version: str

    def validated(self):
        name = _admit_identifier(self.runtime_name, "runtime name")
        version = _admit_identifier(self.runtime_version, "runtime version")
        if name != RUNTIME_NAME:
            raise DraftRevisionError("the runtime name is mismatched")
        if version != RUNTIME_VERSION:
            raise DraftRevisionError("the runtime version is mismatched")
        return RuntimeIdentity(runtime_name=name, runtime_version=version)

    def to_document(self):
        admitted = self.validated()
        return {"runtime_name": admitted.runtime_name, "runtime_version": admitted.runtime_version}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftRevisionError("a stored runtime identity must be a JSON object")
        expected = {"runtime_name", "runtime_version"}
        if set(document) != expected:
            raise DraftRevisionError("a stored runtime identity carries unadmitted members")
        return RuntimeIdentity(
            runtime_name=_string_member(document, "runtime_name"),
            runtime_version=_string_member(document, "runtime_version"),
        ).validated()


@dataclass(frozen=True, slots=True)
class TranscriptReference:
    """Exact transcript identity a draft is validated against."""

    transcript_id: UUID
    transcript_revision: str

    def validated(self):
        if not isinstance(self.transcript_id, UUID):
            raise DraftInputError("a transcript id must be a UUID value")
        revision = _admit_identifier(self.transcript_revision, "transcript revision")
        if revision != TRANSCRIPT_REVISION:
            raise DraftRevisionError("the transcript revision is mismatched")
        return TranscriptReference(transcript_id=self.transcript_id, transcript_revision=revision)

    def to_document(self):
        admitted = self.validated()
        return {
            "transcript_id": str(admitted.transcript_id),
            "transcript_revision": admitted.transcript_revision,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftInputError("a stored transcript reference must be a JSON object")
        expected = {"transcript_id", "transcript_revision"}
        if set(document) != expected:
            raise DraftInputError("a stored transcript reference carries unadmitted members")
        try:
            transcript_id = UUID(str(document["transcript_id"]))
        except ValueError as error:
            raise DraftInputError("a stored transcript id is not admitted") from error
        return TranscriptReference(
            transcript_id=transcript_id,
            transcript_revision=_string_member(document, "transcript_revision"),
        ).validated()


@dataclass(frozen=True, slots=True)
class SourceRange:
    """One character range inside one transcript segment."""

    segment_index: int
    char_start: int
    char_end: int
    source_digest: str

    def validated(self):
        if not isinstance(self.segment_index, int) or isinstance(self.segment_index, bool):
            raise DraftInputError("a segment index must be an integer")
        if self.segment_index < 0:
            raise DraftInputError("a segment index is out of range")
        for label, value in (("char start", self.char_start), ("char end", self.char_end)):
            if not isinstance(value, int) or isinstance(value, bool):
                raise DraftInputError("a " + label + " must be an integer")
            if value < 0:
                raise DraftInputError("a " + label + " is out of range")
        if self.char_end <= self.char_start:
            raise DraftInputError("a source range end must be after its start")
        digest = _admit_digest(self.source_digest, "source digest")
        return SourceRange(
            segment_index=self.segment_index,
            char_start=self.char_start,
            char_end=self.char_end,
            source_digest=digest,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "char_end": admitted.char_end,
            "char_start": admitted.char_start,
            "segment_index": admitted.segment_index,
            "source_digest": admitted.source_digest,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftInputError("a stored source range must be a JSON object")
        expected = {"char_end", "char_start", "segment_index", "source_digest"}
        if set(document) != expected:
            raise DraftInputError("a stored source range carries unadmitted members")
        return SourceRange(
            segment_index=_integer_member(document, "segment_index"),
            char_start=_integer_member(document, "char_start"),
            char_end=_integer_member(document, "char_end"),
            source_digest=_string_member(document, "source_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class SourceReference:
    """One admitted link between a span and a transcript source range."""

    transcript_id: UUID
    transcript_revision: str
    source_range: SourceRange
    relation: SupportRelation

    def validated(self):
        if not isinstance(self.transcript_id, UUID):
            raise DraftInputError("a transcript id must be a UUID value")
        revision = _admit_identifier(self.transcript_revision, "transcript revision")
        if revision != TRANSCRIPT_REVISION:
            raise DraftRevisionError("the transcript revision is mismatched")
        if not isinstance(self.relation, SupportRelation):
            raise DraftInputError("a support relation is not admitted here")
        checked_range = (
            self.source_range.validated() if isinstance(self.source_range, SourceRange) else None
        )
        if checked_range is None:
            raise DraftInputError("a source range needs a SourceRange instance")
        return SourceReference(
            transcript_id=self.transcript_id,
            transcript_revision=revision,
            source_range=checked_range,
            relation=self.relation,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "relation": admitted.relation.value,
            "source_range": admitted.source_range.to_document(),
            "transcript_id": str(admitted.transcript_id),
            "transcript_revision": admitted.transcript_revision,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftInputError("a stored source reference must be a JSON object")
        expected = {"relation", "source_range", "transcript_id", "transcript_revision"}
        if set(document) != expected:
            raise DraftInputError("a stored source reference carries unadmitted members")
        try:
            transcript_id = UUID(str(document["transcript_id"]))
        except ValueError as error:
            raise DraftInputError("a stored transcript id is not admitted") from error
        try:
            relation = SupportRelation(str(document["relation"]))
        except ValueError as error:
            raise DraftInputError("a stored support relation is not admitted") from error
        raw_range = document["source_range"]
        if not isinstance(raw_range, dict):
            raise DraftInputError("a stored source range must be a JSON object")
        return SourceReference(
            transcript_id=transcript_id,
            transcript_revision=_string_member(document, "transcript_revision"),
            source_range=SourceRange.from_document(raw_range),
            relation=relation,
        ).validated()


@dataclass(frozen=True, slots=True)
class DraftSpan:
    """One generated span with an explicit mechanical support state."""

    span_id: str
    text: str
    status: SupportStatus
    sources: tuple
    relation_note: str
    failure_reason: str
    abstention_reason: str

    def validated(self):
        span_id = _admit_identifier(self.span_id, "span id")
        text = _admit_span_text(self.text)
        if not isinstance(self.status, SupportStatus):
            raise DraftInputError("a span status is not admitted here")
        if not isinstance(self.sources, tuple):
            raise DraftInputError("span sources must be a tuple")
        checked = tuple(
            item.validated() if isinstance(item, SourceReference) else None for item in self.sources
        )
        if any(item is None for item in checked):
            raise DraftInputError("span sources need SourceReference instances")
        note = _admit_optional_text(self.relation_note, MAXIMUM_REASON_CHARS, "relation note")
        if self.status is SupportStatus.SUPPORTED:
            if len(checked) < 1:
                raise DraftSupportError("a supported span needs at least one source")
            if self.failure_reason != "" or self.abstention_reason != "":
                raise DraftSupportError("a supported span must not carry failure or abstention")
        elif self.status is SupportStatus.PARTIALLY_SUPPORTED:
            if len(checked) < 1:
                raise DraftSupportError("a partial span needs at least one source")
            if self.failure_reason != "" or self.abstention_reason != "":
                raise DraftSupportError("a partial span must not carry failure or abstention")
        elif self.status is SupportStatus.UNSUPPORTED:
            if len(checked) != 0:
                raise DraftSupportError("an unsupported span must not carry sources")
            if self.failure_reason != "" or self.abstention_reason != "":
                raise DraftSupportError("an unsupported span must not carry failure or abstention")
        elif self.status is SupportStatus.ABSTAINED:
            if len(checked) != 0:
                raise DraftSupportError("an abstention must not carry sources")
            if self.failure_reason != "":
                raise DraftSupportError("an abstention must not carry a failure reason")
            _admit_abstention_reason(self.abstention_reason)
        else:
            if len(checked) != 0:
                raise DraftSupportError("a failure must not carry sources")
            if self.abstention_reason != "":
                raise DraftSupportError("a failure must not carry an abstention reason")
            _admit_failure_reason(self.failure_reason)
        _check_duplicate_source_ranges(checked)
        return DraftSpan(
            span_id=span_id,
            text=text,
            status=self.status,
            sources=checked,
            relation_note=note,
            failure_reason=self.failure_reason,
            abstention_reason=self.abstention_reason,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "abstention_reason": admitted.abstention_reason,
            "failure_reason": admitted.failure_reason,
            "relation_note": admitted.relation_note,
            "sources": [item.to_document() for item in admitted.sources],
            "span_id": admitted.span_id,
            "status": admitted.status.value,
            "text": admitted.text,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftInputError("a stored span must be a JSON object")
        expected = {
            "abstention_reason",
            "failure_reason",
            "relation_note",
            "sources",
            "span_id",
            "status",
            "text",
        }
        if set(document) != expected:
            raise DraftInputError("a stored span carries unadmitted members")
        try:
            status = SupportStatus(str(document["status"]))
        except ValueError as error:
            raise DraftInputError("a stored span status is not admitted") from error
        raw_sources = document["sources"]
        if not isinstance(raw_sources, list):
            raise DraftInputError("stored span sources must be a JSON array")
        sources = tuple(SourceReference.from_document(item) for item in raw_sources)
        return DraftSpan(
            span_id=_string_member(document, "span_id"),
            text=_string_member(document, "text"),
            status=status,
            sources=sources,
            relation_note=_string_member(document, "relation_note"),
            failure_reason=_string_member(document, "failure_reason"),
            abstention_reason=_string_member(document, "abstention_reason"),
        ).validated()


@dataclass(frozen=True, slots=True)
class Draft:
    """One source-linked clinical draft revision bound to exact identities."""

    workspace_id: UUID
    session_id: UUID
    draft_id: UUID
    draft_revision: str
    transcript: TranscriptReference
    template: TemplateIdentity
    input_bundle_digest: str
    model: ModelIdentity
    runtime: RuntimeIdentity
    status: DraftStatus
    spans: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise DraftInputError("a workspace id must be a UUID value")
        if not isinstance(self.session_id, UUID):
            raise DraftInputError("a session id must be a UUID value")
        if not isinstance(self.draft_id, UUID):
            raise DraftInputError("a draft id must be a UUID value")
        revision = _admit_identifier(self.draft_revision, "draft revision")
        if revision != DRAFT_REVISION:
            raise DraftRevisionError("the draft revision is mismatched")
        if not isinstance(self.status, DraftStatus):
            raise DraftInputError("a draft status is not admitted here")
        transcript = (
            self.transcript.validated()
            if isinstance(self.transcript, TranscriptReference)
            else None
        )
        if transcript is None:
            raise DraftInputError("a draft needs a TranscriptReference instance")
        template = (
            self.template.validated() if isinstance(self.template, TemplateIdentity) else None
        )
        if template is None:
            raise DraftInputError("a draft needs a TemplateIdentity instance")
        bundle = _admit_digest(self.input_bundle_digest, "input bundle digest")
        model = self.model.validated() if isinstance(self.model, ModelIdentity) else None
        if model is None:
            raise DraftInputError("a draft needs a ModelIdentity instance")
        runtime = self.runtime.validated() if isinstance(self.runtime, RuntimeIdentity) else None
        if runtime is None:
            raise DraftInputError("a draft needs a RuntimeIdentity instance")
        if not isinstance(self.spans, tuple):
            raise DraftInputError("draft spans must be a tuple")
        if len(self.spans) < 1 or len(self.spans) > MAXIMUM_SPANS:
            raise DraftInputError("a draft carries an unadmitted span count")
        checked = tuple(
            item.validated() if isinstance(item, DraftSpan) else None for item in self.spans
        )
        if any(item is None for item in checked):
            raise DraftInputError("draft spans need DraftSpan instances")
        _check_duplicate_span_ids(checked)
        return Draft(
            workspace_id=self.workspace_id,
            session_id=self.session_id,
            draft_id=self.draft_id,
            draft_revision=revision,
            transcript=transcript,
            template=template,
            input_bundle_digest=bundle,
            model=model,
            runtime=runtime,
            status=self.status,
            spans=checked,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "draft_id": str(admitted.draft_id),
            "draft_revision": admitted.draft_revision,
            "input_bundle_digest": admitted.input_bundle_digest,
            "model": admitted.model.to_document(),
            "policy_version": POLICY_VERSION,
            "runtime": admitted.runtime.to_document(),
            "session_id": str(admitted.session_id),
            "spans": [item.to_document() for item in admitted.spans],
            "status": admitted.status.value,
            "template": admitted.template.to_document(),
            "transcript": admitted.transcript.to_document(),
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DraftInputError("a stored draft must be a JSON object")
        expected = {
            "data_class",
            "draft_id",
            "draft_revision",
            "input_bundle_digest",
            "model",
            "policy_version",
            "runtime",
            "session_id",
            "spans",
            "status",
            "template",
            "transcript",
            "workspace_id",
        }
        if set(document) != expected:
            raise DraftInputError("a stored draft carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise DraftInputError("a stored draft data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise DraftInputError("a stored draft policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            session_id = UUID(str(document["session_id"]))
            draft_id = UUID(str(document["draft_id"]))
            status = DraftStatus(str(document["status"]))
        except ValueError as error:
            raise DraftInputError("a stored draft identity is not admitted") from error
        raw_spans = document["spans"]
        if not isinstance(raw_spans, list):
            raise DraftInputError("stored draft spans must be a JSON array")
        spans = tuple(DraftSpan.from_document(item) for item in raw_spans)
        raw_transcript = document["transcript"]
        raw_template = document["template"]
        raw_model = document["model"]
        raw_runtime = document["runtime"]
        if not isinstance(raw_transcript, dict):
            raise DraftInputError("a stored transcript reference must be a JSON object")
        if not isinstance(raw_template, dict):
            raise DraftTemplateError("a stored template must be a JSON object")
        if not isinstance(raw_model, dict):
            raise DraftRevisionError("a stored model identity must be a JSON object")
        if not isinstance(raw_runtime, dict):
            raise DraftRevisionError("a stored runtime identity must be a JSON object")
        return Draft(
            workspace_id=workspace_id,
            session_id=session_id,
            draft_id=draft_id,
            draft_revision=_string_member(document, "draft_revision"),
            transcript=TranscriptReference.from_document(raw_transcript),
            template=TemplateIdentity.from_document(raw_template),
            input_bundle_digest=_string_member(document, "input_bundle_digest"),
            model=ModelIdentity.from_document(raw_model),
            runtime=RuntimeIdentity.from_document(raw_runtime),
            status=status,
            spans=spans,
        ).validated()


def expected_template():
    """Return the governed template identity for the deterministic path."""
    return TemplateIdentity(
        template_id=TEMPLATE_ID,
        template_revision=TEMPLATE_REVISION,
        template_digest=_expected_template_digest(),
    ).validated()


def verify_template(template):
    """Fail closed unless the template is the governed identity."""
    if not isinstance(template, TemplateIdentity):
        raise DraftTemplateError("a template needs a TemplateIdentity instance")
    return template.validated()


def input_bundle_digest_for(transcript_id, transcript_revision, transcript_digest, template):
    """Return the deterministic input bundle digest bound to a draft."""
    if not isinstance(transcript_id, UUID):
        raise DraftInputError("a transcript id must be a UUID value")
    revision = _admit_identifier(transcript_revision, "transcript revision")
    digest = _admit_digest(transcript_digest, "transcript digest")
    checked_template = verify_template(template)
    document = {
        "template_digest": checked_template.template_digest,
        "template_id": checked_template.template_id,
        "template_revision": checked_template.template_revision,
        "transcript_digest": digest,
        "transcript_id": str(transcript_id),
        "transcript_revision": revision,
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()


def draft_id_for(workspace_id, session_id, transcript_id, template, input_bundle_digest):
    """Return the deterministic draft identity for one input bundle."""
    if not isinstance(workspace_id, UUID):
        raise DraftInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise DraftInputError("a session id must be a UUID value")
    if not isinstance(transcript_id, UUID):
        raise DraftInputError("a transcript id must be a UUID value")
    checked_template = verify_template(template)
    bundle = _admit_digest(input_bundle_digest, "input bundle digest")
    return uuid5(
        DRAFT_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(session_id),
                str(transcript_id),
                checked_template.template_id,
                checked_template.template_revision,
                bundle,
            )
        ),
    )


def draft_binding(workspace_id, draft_id):
    """Return the store binding of one draft revision."""
    if not isinstance(workspace_id, UUID):
        raise DraftInputError("a workspace id must be a UUID value")
    if not isinstance(draft_id, UUID):
        raise DraftInputError("a draft id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=draft_id,
        object_type=WorkspaceObjectType.CLINICAL_DRAFT,
        object_revision=DRAFT_REVISION,
    )


def draft_payload_bytes(draft):
    """Return the canonical storage payload of one draft."""
    if not isinstance(draft, Draft):
        raise DraftInputError("a draft payload needs a Draft instance")
    return _canonical_bytes(draft.to_document())


def mock_draft_backend(transcript_text, segments, template, requested_sections):
    """Deterministic placeholder backend with fixed outputs only, never a model."""
    checked_template = verify_template(template)
    if not isinstance(transcript_text, str):
        raise DraftBackendError("a backend transcript must be a string")
    if not isinstance(segments, tuple):
        raise DraftBackendError("backend segments must be a tuple")
    if not isinstance(requested_sections, tuple):
        raise DraftBackendError("backend sections must be a tuple")
    for section in requested_sections:
        if section not in TEMPLATE_SECTIONS:
            raise DraftBackendError("a backend section is not admitted here")
    _ = checked_template
    return ("draft", requested_sections, "synthetic")


def synthesize_with_backend(
    workspace_id,
    session_id,
    transcript_id,
    transcript_revision,
    transcript_text,
    segments,
    template,
    input_bundle_digest,
    model,
    runtime,
    span_plan,
    backend,
):
    """Build a draft through an injected backend under the deterministic contract."""
    if not isinstance(workspace_id, UUID):
        raise DraftInputError("a workspace id must be a UUID value")
    if not isinstance(session_id, UUID):
        raise DraftInputError("a session id must be a UUID value")
    if not isinstance(transcript_id, UUID):
        raise DraftInputError("a transcript id must be a UUID value")
    revision = _admit_identifier(transcript_revision, "transcript revision")
    if revision != TRANSCRIPT_REVISION:
        raise DraftRevisionError("the transcript revision is mismatched")
    checked_template = verify_template(template)
    bundle = _admit_digest(input_bundle_digest, "input bundle digest")
    checked_model = model.validated() if isinstance(model, ModelIdentity) else None
    if checked_model is None:
        raise DraftInputError("a draft needs a ModelIdentity instance")
    checked_runtime = runtime.validated() if isinstance(runtime, RuntimeIdentity) else None
    if checked_runtime is None:
        raise DraftInputError("a draft needs a RuntimeIdentity instance")
    if not isinstance(span_plan, tuple):
        raise DraftBackendError("a span plan must be a tuple")
    if not callable(backend):
        raise DraftBackendError("a backend must be callable")
    if not isinstance(transcript_text, str):
        raise DraftInputError("a transcript text must be a string")
    if not isinstance(segments, tuple):
        raise DraftInputError("segments must be a tuple")
    out = backend(transcript_text, segments, checked_template, ("subjective",))
    if not isinstance(out, tuple) or len(out) != 3:
        raise DraftBackendError("a backend must return a three member tuple")
    kind, _sections, _marker = out
    if kind != "draft":
        raise DraftBackendError("a backend kind is not admitted here")
    spans = tuple(item.validated() if isinstance(item, DraftSpan) else None for item in span_plan)
    if any(item is None for item in spans):
        raise DraftBackendError("a span plan needs DraftSpan instances")
    draft_id = draft_id_for(workspace_id, session_id, transcript_id, checked_template, bundle)
    return Draft(
        workspace_id=workspace_id,
        session_id=session_id,
        draft_id=draft_id,
        draft_revision=DRAFT_REVISION,
        transcript=TranscriptReference(transcript_id=transcript_id, transcript_revision=revision),
        template=checked_template,
        input_bundle_digest=bundle,
        model=checked_model,
        runtime=checked_runtime,
        status=DraftStatus.DRAFT,
        spans=spans,
    ).validated()


def synthesize_synthetic(
    workspace_id,
    session_id,
    transcript_id,
    transcript_revision,
    transcript_text,
    segments,
    template,
    input_bundle_digest,
    model,
    runtime,
    span_plan,
):
    """Build a draft with the deterministic placeholder backend."""
    return synthesize_with_backend(
        workspace_id,
        session_id,
        transcript_id,
        transcript_revision,
        transcript_text,
        segments,
        template,
        input_bundle_digest,
        model,
        runtime,
        span_plan,
        mock_draft_backend,
    )


def validate_draft_support(store, draft):
    """Mechanically validate every support claim of a draft against its transcript."""
    if not isinstance(store, WorkspaceStore):
        raise DraftInputError("a workspace store is required")
    admitted = draft.validated() if isinstance(draft, Draft) else None
    if admitted is None:
        raise DraftInputError("support validation needs a Draft instance")
    if admitted.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a draft crossed the workspace boundary")
    try:
        transcript = read_transcript(store, admitted.transcript.transcript_id)
    except ObjectNotFoundError as error:
        raise DraftSupportError("the bound transcript is absent in this store") from error
    except (AsrInputError, DraftInputError, DraftRevisionError) as error:
        raise DraftSupportError("the bound transcript binding is refused") from error
    if transcript.workspace_id != admitted.workspace_id:
        raise WorkspaceIsolationError("a draft crossed the workspace boundary")
    if transcript.session_id != admitted.session_id:
        raise DraftSupportError("a draft crossed the session boundary")
    if admitted.transcript.transcript_revision != TRANSCRIPT_REVISION:
        raise DraftSupportError("the transcript revision is mismatched")
    texts = tuple(segment.text for segment in transcript.segments)
    if len(texts) < 1:
        raise DraftSupportError("the bound transcript carries no segments")
    expected_bundle = input_bundle_digest_for(
        admitted.transcript.transcript_id,
        admitted.transcript.transcript_revision,
        content_digest_of(_canonical_bytes(transcript.to_document())),
        admitted.template,
    )
    if admitted.input_bundle_digest != expected_bundle:
        raise DraftSupportError("the input bundle digest is mismatched")
    for span in admitted.spans:
        _validate_span_against_transcript(span, admitted.transcript.transcript_id, texts)
    return admitted


def store_draft(store, trail, draft, actor_id, occurred_at):
    """Store one draft with provenance and audit, failing closed."""
    if not isinstance(store, WorkspaceStore):
        raise DraftInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise DraftInputError("an audit trail is required")
    validated = validate_draft_support(store, draft)
    if validated.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a draft crossed the workspace boundary")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    binding = draft_binding(validated.workspace_id, validated.draft_id)
    payload = draft_payload_bytes(validated)
    source_refs = _provenance_source_refs(validated)
    producer = ProducerIdentity(
        kind=ProducerKind.MODEL, identifier=PRODUCER_ID, version=PRODUCER_VERSION
    )
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.DRAFT,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise DraftConflictError("the draft identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
        event_type=AuditEventType.AI_GENERATION,
    )
    return binding


def read_draft(store, draft_id):
    """Read and verify one stored draft against its provenance digest."""
    if not isinstance(store, WorkspaceStore):
        raise DraftInputError("a workspace store is required")
    if not isinstance(draft_id, UUID):
        raise DraftInputError("a draft id must be a UUID value")
    binding = draft_binding(store.workspace_id, draft_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise DraftInputError("the draft identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise DraftInputError("a stored draft is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise DraftInputError("a stored draft is not JSON") from error
    draft = Draft.from_document(document)
    if draft.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a draft crossed the workspace boundary")
    if draft.draft_id != draft_id:
        raise DraftInputError("a stored draft identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return validate_draft_support(store, draft)


def _expected_template_digest():
    document = {
        "intended_sections": list(TEMPLATE_SECTIONS),
        "output_contract": "draft-spans-with-support-status",
        "supported_input_types": ["transcript"],
        "template_id": TEMPLATE_ID,
        "template_revision": TEMPLATE_REVISION,
    }
    return "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()


def _provenance_source_refs(draft):
    refs = []
    seen = set()
    for span in draft.spans:
        if span.status not in (SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED):
            continue
        for source in span.sources:
            key = (
                str(source.transcript_id),
                source.transcript_revision,
                source.source_range.segment_index,
            )
            if key in seen:
                continue
            seen.add(key)
            refs.append(
                SourceRef(
                    kind=SourceKind.TRANSCRIPT_RANGE,
                    source_id=str(source.transcript_id),
                    source_revision=source.transcript_revision,
                    locator="segment:" + str(source.source_range.segment_index),
                )
            )
    if not refs:
        refs.append(
            SourceRef(
                kind=SourceKind.TRANSCRIPT_RANGE,
                source_id=str(draft.transcript.transcript_id),
                source_revision=draft.transcript.transcript_revision,
                locator="draft-bundle",
            )
        )
    return tuple(refs)


def _validate_span_against_transcript(span, transcript_id, texts):
    if span.status in (SupportStatus.SUPPORTED, SupportStatus.PARTIALLY_SUPPORTED):
        if len(span.sources) < 1:
            raise DraftSupportError("a backed span needs at least one source")
        for source in span.sources:
            if source.transcript_id != transcript_id:
                raise DraftSupportError("a source transcript identity is mismatched")
            if source.transcript_revision != TRANSCRIPT_REVISION:
                raise DraftSupportError("a source transcript revision is mismatched")
            if not isinstance(source.relation, SupportRelation):
                raise DraftSupportError("a support relation is not admitted here")
            index = source.source_range.segment_index
            if index >= len(texts):
                raise DraftSupportError("a source segment does not exist")
            segment_text = texts[index]
            start = source.source_range.char_start
            end = source.source_range.char_end
            if end > len(segment_text):
                raise DraftSupportError("a source range is out of bounds")
            expected = (
                "sha256:" + hashlib.sha256(segment_text[start:end].encode("utf-8")).hexdigest()
            )
            if source.source_range.source_digest != expected:
                raise DraftSupportError("a source text digest is mismatched")
    elif span.status is SupportStatus.UNSUPPORTED:
        if len(span.sources) != 0:
            raise DraftSupportError("an unsupported span must not carry sources")
    elif span.status is SupportStatus.ABSTAINED:
        if len(span.sources) != 0:
            raise DraftSupportError("an abstention must not carry sources")
        _admit_abstention_reason(span.abstention_reason)
        if span.failure_reason != "":
            raise DraftSupportError("an abstention must not carry a failure reason")
    else:
        if len(span.sources) != 0:
            raise DraftSupportError("a failure must not carry sources")
        _admit_failure_reason(span.failure_reason)
        if span.abstention_reason != "":
            raise DraftSupportError("a failure must not carry an abstention reason")
    return span


def _check_duplicate_span_ids(spans):
    seen = set()
    for span in spans:
        if span.span_id in seen:
            raise DraftSupportError("duplicate span identities are refused")
        seen.add(span.span_id)


def _check_duplicate_source_ranges(sources):
    seen = set()
    for source in sources:
        key = (
            str(source.transcript_id),
            source.source_range.segment_index,
            source.source_range.char_start,
            source.source_range.char_end,
        )
        if key in seen:
            raise DraftSupportError("duplicate source ranges are refused")
        seen.add(key)


def _canonical_bytes(document):
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return encoded.encode("ascii")


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise DraftInputError("a " + label + " must be a string")
    value = raw.strip()
    if not value:
        raise DraftInputError("a " + label + " must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise DraftInputError("a " + label + " is longer than the admitted maximum")
    if not value.isascii():
        raise DraftInputError("a " + label + " must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise DraftInputError("a " + label + " must not contain whitespace")
    return value


def _admit_digest(raw, label):
    if not isinstance(raw, str):
        raise DraftInputError("a " + label + " must be a string")
    value = raw.strip()
    if not value:
        raise DraftInputError("a " + label + " must be non-empty")
    if len(value) > MAXIMUM_DIGEST_CHARS:
        raise DraftInputError("a " + label + " is longer than the admitted maximum")
    if not value.isascii() or not value.isprintable():
        raise DraftInputError("a " + label + " must be printable ASCII")
    if not value.startswith("sha256:"):
        raise DraftInputError("a " + label + " must carry a digest prefix")
    body = value[len("sha256:") :]
    if len(body) != 64:
        raise DraftInputError("a " + label + " must carry the admitted length")
    for character in body:
        if character not in "0123456789abcdef":
            raise DraftInputError("a " + label + " must be lowercase hex")
    return value


def _admit_span_text(raw):
    if not isinstance(raw, str):
        raise DraftInputError("a span text must be a string")
    if not raw.strip():
        raise DraftInputError("a span text must be non-empty")
    if len(raw) > MAXIMUM_SPAN_CHARS:
        raise DraftInputError("a span text is longer than the admitted maximum")
    if not raw.isprintable():
        raise DraftInputError("a span text must not contain control characters")
    return raw


def _admit_optional_text(raw, maximum, label):
    if not isinstance(raw, str):
        raise DraftInputError("a " + label + " must be a string")
    if len(raw) > maximum:
        raise DraftInputError("a " + label + " is longer than the admitted maximum")
    if raw != "" and (not raw.isascii() or not raw.isprintable()):
        raise DraftInputError("a " + label + " must be printable ASCII")
    return raw


def _admit_failure_reason(raw):
    if not isinstance(raw, str):
        raise DraftInputError("a failure reason must be a string")
    try:
        return FailureReason(raw)
    except ValueError as error:
        raise DraftInputError("a failure reason is not admitted here") from error


def _admit_abstention_reason(raw):
    if not isinstance(raw, str):
        raise DraftInputError("an abstention reason must be a string")
    try:
        return AbstentionReason(raw)
    except ValueError as error:
        raise DraftInputError("an abstention reason is not admitted here") from error


def _admit_actor(raw):
    if not isinstance(raw, str):
        raise DraftInputError("an actor id must be a string")
    value = raw.strip()
    if not value:
        raise DraftInputError("an actor id must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise DraftInputError("an actor id is longer than the admitted maximum")
    if not value.isascii():
        raise DraftInputError("an actor id must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise DraftInputError("an actor id must not contain whitespace")
    return value


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise DraftInputError("an occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise DraftInputError("an occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise DraftInputError("an occurrence time is longer than the admitted maximum")
    if not value.isascii():
        raise DraftInputError("an occurrence time must be ASCII")
    for character in value:
        if not character.isprintable():
            raise DraftInputError("an occurrence time must not contain controls")
    return value


def _string_member(document, name):
    value = document.get(name)
    if not isinstance(value, str):
        raise DraftInputError("stored member " + name + " must be a string")
    return value


def _integer_member(document, name):
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise DraftInputError("stored member " + name + " must be an integer")
    return value
