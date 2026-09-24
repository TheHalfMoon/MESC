"""Synthetic evidence corpus for CW-009 with deterministic source identity.

A corpus is a named collection of admitted synthetic evidence sources inside
one workspace. Every source carries a stable identity derived from the
workspace, the corpus key, the canonical locator, and the source revision, so
changed bytes, changed revisions, or changed locators always yield a different
identity and can never silently stand in for each other. The recorded content
digest binds the exact admitted bytes of every source.

Corpus content is untrusted data. Evidence text is stored and returned
verbatim; it is never evaluated, never executed, and never consulted for
capability, policy, or governance decisions. A malicious document is DATA, not
INSTRUCTION AUTHORITY. No network, retrieval-connector, model, or execution
capability exists in this module.

Retrieval snapshots over these sources live in ``retrieval.py``. Research Core
corpus machinery (``litdb``, dataset snapshots) belongs to a different trust
domain and is deliberately not imported here: the Workspace consumes only what
it admits itself, and nothing admitted here may flow back into Research Core.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    CorpusConflictError,
    CorpusInputError,
    CorpusRevisionError,
    ObjectNotFoundError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    describe_revision,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

SOURCE_NAMESPACE = UUID("e11f2a33-4b5c-4d6e-8f7a-9b0c1d2e3f4a")
SOURCE_REVISION = "source-00000001"
PRODUCER_ID = "cw009-synthetic-corpus-fixture"
PRODUCER_VERSION = "cw009-v1"
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_TITLE_CHARS = 256
MAXIMUM_TEXT_CHARS = 4096
MAXIMUM_DATE_CHARS = 32
MAXIMUM_OCCURRED_AT_CHARS = 64


@dataclass(frozen=True, slots=True)
class CorpusSource:
    """One admitted synthetic evidence source bound to exact identities."""

    workspace_id: UUID
    corpus_key: str
    source_id: UUID
    locator: str
    title: str
    source_revision: str
    source_date: str
    content_digest: str
    text: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise CorpusInputError("a workspace id must be a UUID value")
        corpus_key = _admit_identifier(self.corpus_key, "corpus key")
        if not isinstance(self.source_id, UUID):
            raise CorpusInputError("a source id must be a UUID value")
        locator = _admit_identifier(self.locator, "source locator")
        title = _admit_title(self.title)
        revision = _admit_identifier(self.source_revision, "source revision")
        date = _admit_source_date(self.source_date)
        digest = _admit_digest(self.content_digest)
        text = _admit_evidence_text(self.text)
        expected = source_id_for(self.workspace_id, corpus_key, locator, revision)
        if self.source_id != expected:
            raise CorpusRevisionError("a source identity does not match its lineage")
        if digest != _digest_of_text(text):
            raise CorpusRevisionError("a source digest does not match its text")
        return CorpusSource(
            workspace_id=self.workspace_id,
            corpus_key=corpus_key,
            source_id=self.source_id,
            locator=locator,
            title=title,
            source_revision=revision,
            source_date=date,
            content_digest=digest,
            text=text,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "corpus_key": admitted.corpus_key,
            "data_class": synthetic_data_class_value(),
            "locator": admitted.locator,
            "policy_version": POLICY_VERSION,
            "source_date": admitted.source_date,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "text": admitted.text,
            "title": admitted.title,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise CorpusInputError("a stored source must be a JSON object")
        expected = {
            "content_digest",
            "corpus_key",
            "data_class",
            "locator",
            "policy_version",
            "source_date",
            "source_id",
            "source_revision",
            "text",
            "title",
            "workspace_id",
        }
        if set(document) != expected:
            raise CorpusInputError("a stored source carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise CorpusInputError("a stored source data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise CorpusInputError("a stored source policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise CorpusInputError("a stored source identity is not admitted") from error
        return CorpusSource(
            workspace_id=workspace_id,
            corpus_key=_string_member(document, "corpus_key"),
            source_id=source_id,
            locator=_string_member(document, "locator"),
            title=_string_member(document, "title"),
            source_revision=_string_member(document, "source_revision"),
            source_date=_string_member(document, "source_date"),
            content_digest=_string_member(document, "content_digest"),
            text=_string_member(document, "text"),
        ).validated()


def source_id_for(workspace_id, corpus_key, locator, source_revision):
    """Return the deterministic identity of one corpus source revision."""
    if not isinstance(workspace_id, UUID):
        raise CorpusInputError("a workspace id must be a UUID value")
    key = _admit_identifier(corpus_key, "corpus key")
    admitted_locator = _admit_identifier(locator, "source locator")
    revision = _admit_identifier(source_revision, "source revision")
    return uuid5(
        SOURCE_NAMESPACE,
        ":".join((str(workspace_id), key, admitted_locator, revision)),
    )


def source_binding(workspace_id, source_id):
    """Return the store binding of one corpus source."""
    if not isinstance(workspace_id, UUID):
        raise CorpusInputError("a workspace id must be a UUID value")
    if not isinstance(source_id, UUID):
        raise CorpusInputError("a source id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=source_id,
        object_type=WorkspaceObjectType.EVIDENCE_CORPUS_SOURCE,
        object_revision=SOURCE_REVISION,
    )


def source_payload_bytes(source):
    """Return the canonical storage payload of one corpus source."""
    if not isinstance(source, CorpusSource):
        raise CorpusInputError("a source payload needs a CorpusSource instance")
    return _canonical_bytes(source.to_document())


def corpus_id_for(workspace_id, corpus_key):
    """Return the deterministic identity of one named corpus."""
    if not isinstance(workspace_id, UUID):
        raise CorpusInputError("a workspace id must be a UUID value")
    key = _admit_identifier(corpus_key, "corpus key")
    return uuid5(
        SOURCE_NAMESPACE,
        ":".join((str(workspace_id), key)),
    )


def admit_source(
    store,
    trail,
    workspace_id,
    corpus_key,
    locator,
    title,
    source_revision,
    source_date,
    text,
    actor_id,
    occurred_at,
):
    """Admit one synthetic evidence source revision, failing closed."""
    if not isinstance(store, WorkspaceStore):
        raise CorpusInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise CorpusInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise CorpusInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a corpus source crossed the workspace boundary")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    key = _admit_identifier(corpus_key, "corpus key")
    admitted_locator = _admit_identifier(locator, "source locator")
    revision = _admit_identifier(source_revision, "source revision")
    source = CorpusSource(
        workspace_id=workspace_id,
        corpus_key=key,
        source_id=source_id_for(workspace_id, key, admitted_locator, revision),
        locator=admitted_locator,
        title=title,
        source_revision=revision,
        source_date=source_date,
        content_digest=_digest_of_text(_admit_evidence_text(text)),
        text=text,
    ).validated()
    binding = source_binding(workspace_id, source.source_id)
    payload = source_payload_bytes(source)
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=PRODUCER_ID, version=PRODUCER_VERSION
    )
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise CorpusConflictError("the corpus source identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_source(store, source_id):
    """Read and verify one stored corpus source."""
    if not isinstance(store, WorkspaceStore):
        raise CorpusInputError("a workspace store is required")
    if not isinstance(source_id, UUID):
        raise CorpusInputError("a source id must be a UUID value")
    binding = source_binding(store.workspace_id, source_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise CorpusInputError("the source identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise CorpusInputError("a stored source is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise CorpusInputError("a stored source is not JSON") from error
    source = CorpusSource.from_document(document)
    if source.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a corpus source crossed the workspace boundary")
    if source.source_id != source_id:
        raise CorpusInputError("a stored source identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return source.validated()


def _digest_of_text(text):
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise CorpusInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise CorpusInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise CorpusInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise CorpusInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise CorpusInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_title(raw):
    if not isinstance(raw, str):
        raise CorpusInputError("source title must be a string")
    value = raw.strip()
    if not value:
        raise CorpusInputError("source title must be non-empty")
    if len(value) > MAXIMUM_TITLE_CHARS:
        raise CorpusInputError("source title is longer than the admitted maximum")
    if not value.isascii():
        raise CorpusInputError("source title must be ASCII")
    for character in value:
        if not character.isprintable() and character not in (" ",):
            raise CorpusInputError("source title must not contain control characters")
    return " ".join(value.split())


def _admit_source_date(raw):
    if not isinstance(raw, str):
        raise CorpusInputError("source date must be a string")
    value = raw.strip()
    if value == "":
        return ""
    if len(value) > MAXIMUM_DATE_CHARS:
        raise CorpusInputError("source date is longer than the admitted maximum")
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        raise CorpusInputError("source date must be empty or YYYY-MM-DD")
    for index in (0, 1, 2, 3, 5, 6, 8, 9):
        if value[index] not in "0123456789":
            raise CorpusInputError("source date must be empty or YYYY-MM-DD")
    if not value.isascii():
        raise CorpusInputError("source date must be ASCII")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise CorpusInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise CorpusInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_evidence_text(raw):
    if not isinstance(raw, str):
        raise CorpusInputError("evidence text must be a string")
    value = raw.strip()
    if not value:
        raise CorpusInputError("evidence text must be non-empty")
    if len(value) > MAXIMUM_TEXT_CHARS:
        raise CorpusInputError("evidence text is longer than the admitted maximum")
    if not value.isascii():
        raise CorpusInputError("evidence text must be ASCII")
    for character in value:
        if character in ("\n", "\t"):
            continue
        if not character.isprintable():
            raise CorpusInputError("evidence text must not contain control characters")
    return value


def _admit_actor(raw):
    return _admit_identifier(raw, "actor id")


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise CorpusInputError("a corpus occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise CorpusInputError("a corpus occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise CorpusInputError("a corpus occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise CorpusInputError("a corpus occurrence time must be an ISO-8601 instant with a zone")
    if not value.isascii():
        raise CorpusInputError("a corpus occurrence time must be ASCII")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise CorpusInputError(f"a stored {name} must be a string")
    return value
