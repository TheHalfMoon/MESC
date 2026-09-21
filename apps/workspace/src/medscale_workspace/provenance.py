"""Object provenance spine for CW-003.

CW-003 acceptance (Issue #471, contract section 11 of the Clinical Workspace V1
specification): generated, imported and edited objects must carry an immutable
revision identity and an explicit source identity, and provenance must stay a
separate concept from audit.

A provenance record is therefore its own immutable workspace object bound to the
object revision it describes. It records the producer identity, the source
references, the review state, the recorded content digest, the provenance format
version and the policy version; it never records payload content.

This module holds no clock, no network and no cipher of its own: provenance is
serialized into the CW-002 store, which encrypts it like any other sensitive
payload and binds it to the same associated data.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.binding import ObjectBinding
from medscale_workspace.errors import ProvenanceDigestMismatchError, ProvenanceError
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.storage import ObjectWrite, WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION, PROVENANCE_FORMAT_VERSION

PROVENANCE_NAMESPACE = UUID("7f4c2b91-0d5a-4c67-9f2e-6b8d1a3c5e70")
CONTENT_DIGEST_PREFIX = "sha256:"
MAXIMUM_IDENTIFIER_LENGTH = 128


class SourceKind(StrEnum):
    """Admitted source classes a workspace object may be traceable to."""

    SOURCE_DOCUMENT = "source_document"
    FHIR_RESOURCE = "fhir_resource"
    TRANSCRIPT_RANGE = "transcript_range"
    AUDIO_RANGE = "audio_range"
    EVIDENCE_SOURCE = "evidence_source"
    MODEL_GENERATION = "model_generation"
    HUMAN_EDIT = "human_edit"
    IMPORT = "import"


class ProducerKind(StrEnum):
    """Who produced the object revision."""

    HUMAN = "human"
    IMPORT = "import"
    MODEL = "model"


class ReviewState(StrEnum):
    """Human review state of the object revision."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    FINALIZED = "finalized"
    IMPORTED = "imported"


def content_digest_of(payload: bytes) -> str:
    """Return the recorded content digest of a payload."""

    if not isinstance(payload, bytes):
        raise ProvenanceError("payload must be bytes")
    return f"{CONTENT_DIGEST_PREFIX}{hashlib.sha256(payload).hexdigest()}"


def _admitted_identifier(raw: object, *, label: str) -> str:
    if not isinstance(raw, str):
        raise ProvenanceError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ProvenanceError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_LENGTH:
        raise ProvenanceError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ProvenanceError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ProvenanceError(f"{label} must not contain whitespace or controls")
    return value


def _admitted_digest(raw: object) -> str:
    if not isinstance(raw, str) or not raw.startswith(CONTENT_DIGEST_PREFIX):
        raise ProvenanceError("content digest must be a sha256: digest")
    hex_part = raw[len(CONTENT_DIGEST_PREFIX) :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise ProvenanceError("content digest must carry 64 lowercase hex characters")
    return raw


@dataclass(frozen=True, slots=True)
class SourceRef:
    """One explicit source a workspace object revision is traceable to."""

    kind: SourceKind
    source_id: str
    source_revision: str
    locator: str | None = None

    def validated(self) -> SourceRef:
        if not isinstance(self.kind, SourceKind):
            raise ProvenanceError("source kind must be an admitted source kind")
        locator = None
        if self.locator is not None:
            locator = _admitted_identifier(self.locator, label="source locator")
        return SourceRef(
            kind=self.kind,
            source_id=_admitted_identifier(self.source_id, label="source id"),
            source_revision=_admitted_identifier(self.source_revision, label="source revision"),
            locator=locator,
        )

    def to_document(self) -> dict[str, object]:
        admitted = self.validated()
        return {
            "kind": admitted.kind.value,
            "locator": admitted.locator,
            "source_id": admitted.source_id,
            "source_revision": admitted.source_revision,
        }


@dataclass(frozen=True, slots=True)
class ProducerIdentity:
    """The producer of an object revision, recorded explicitly."""

    kind: ProducerKind
    identifier: str
    version: str

    def validated(self) -> ProducerIdentity:
        if not isinstance(self.kind, ProducerKind):
            raise ProvenanceError("producer kind must be an admitted producer kind")
        return ProducerIdentity(
            kind=self.kind,
            identifier=_admitted_identifier(self.identifier, label="producer identifier"),
            version=_admitted_identifier(self.version, label="producer version"),
        )

    def to_document(self) -> dict[str, object]:
        admitted = self.validated()
        return {
            "identifier": admitted.identifier,
            "kind": admitted.kind.value,
            "version": admitted.version,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """The provenance of exactly one immutable object revision."""

    binding: ObjectBinding
    content_digest: str
    producer: ProducerIdentity
    source_refs: tuple[SourceRef, ...]
    review_state: ReviewState
    provenance_format_version: int = PROVENANCE_FORMAT_VERSION
    policy_version: str = POLICY_VERSION

    def validated(self) -> ProvenanceRecord:
        binding = self.binding.validated()
        if binding.object_type in {WorkspaceObjectType.AUDIT_EVENT}:
            raise ProvenanceError("audit events are not provenance-bearing objects")
        if not isinstance(self.review_state, ReviewState):
            raise ProvenanceError("review state must be an admitted review state")
        if self.provenance_format_version != PROVENANCE_FORMAT_VERSION:
            raise ProvenanceError("provenance format version is not supported here")
        if not isinstance(self.policy_version, str) or not self.policy_version.strip():
            raise ProvenanceError("policy version must be recorded")
        producer = self.producer.validated()
        refs = tuple(source_ref.validated() for source_ref in self.source_refs)
        if producer.kind is ProducerKind.MODEL and not refs:
            raise ProvenanceError(
                "generated content must reference at least one source; unsupported content "
                "may not become source-backed"
            )
        return ProvenanceRecord(
            binding=binding,
            content_digest=_admitted_digest(self.content_digest),
            producer=producer,
            source_refs=refs,
            review_state=self.review_state,
            provenance_format_version=self.provenance_format_version,
            policy_version=self.policy_version,
        )

    def to_document(self) -> dict[str, object]:
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "object_id": str(admitted.binding.object_id),
            "object_revision": admitted.binding.object_revision,
            "object_type": admitted.binding.object_type.value,
            "policy_version": admitted.policy_version,
            "producer": admitted.producer.to_document(),
            "provenance_format_version": admitted.provenance_format_version,
            "review_state": admitted.review_state.value,
            "source_refs": [source_ref.to_document() for source_ref in admitted.source_refs],
            "workspace_id": str(admitted.binding.workspace_id),
        }

    def canonical_bytes(self) -> bytes:
        """Return the canonical, deterministic serialization of this record."""

        encoded = json.dumps(
            self.to_document(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return encoded.encode("ascii")

    def verify_payload(self, payload: bytes) -> None:
        """Raise when the recorded digest does not match the payload it describes."""

        admitted = self.validated()
        if content_digest_of(payload) != admitted.content_digest:
            raise ProvenanceDigestMismatchError(
                "the recorded content digest does not match the object payload"
            )


def provenance_binding_for(binding: ObjectBinding) -> ObjectBinding:
    """Return the immutable provenance object identity of one object revision."""

    admitted = binding.validated()
    return ObjectBinding(
        workspace_id=admitted.workspace_id,
        object_id=uuid5(
            PROVENANCE_NAMESPACE,
            f"{admitted.object_id}:{admitted.object_revision}",
        ),
        object_type=WorkspaceObjectType.PROVENANCE_RECORD,
        object_revision=admitted.object_revision,
    )


def describe_revision(
    *,
    binding: ObjectBinding,
    payload: bytes,
    producer: ProducerIdentity,
    source_refs: tuple[SourceRef, ...],
    review_state: ReviewState,
) -> ProvenanceRecord:
    """Build the provenance record for a payload about to be stored."""

    return ProvenanceRecord(
        binding=binding,
        content_digest=content_digest_of(payload),
        producer=producer,
        source_refs=source_refs,
        review_state=review_state,
    ).validated()


def store_with_provenance(store: WorkspaceStore, record: ProvenanceRecord, payload: bytes) -> None:
    """Store one object revision together with its provenance record, atomically."""

    admitted = record.validated()
    admitted.verify_payload(payload)
    provenance_write = ObjectWrite(
        binding=provenance_binding_for(admitted.binding),
        payload=admitted.canonical_bytes(),
    )
    store.put_objects_atomic(
        (ObjectWrite(binding=admitted.binding, payload=payload), provenance_write)
    )


def read_provenance(store: WorkspaceStore, binding: ObjectBinding) -> ProvenanceRecord:
    """Read and validate the provenance record of one object revision."""

    admitted = binding.validated()
    raw = store.get_object(provenance_binding_for(admitted))
    try:
        document = json.loads(raw.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ProvenanceError("stored provenance record is not canonical ASCII JSON") from error
    return _record_from_document(document)


def _record_from_document(document: object) -> ProvenanceRecord:
    if not isinstance(document, dict):
        raise ProvenanceError("stored provenance record must be a JSON object")
    expected_members = {
        "content_digest",
        "object_id",
        "object_revision",
        "object_type",
        "policy_version",
        "producer",
        "provenance_format_version",
        "review_state",
        "source_refs",
        "workspace_id",
    }
    if set(document) != expected_members:
        raise ProvenanceError("stored provenance record members are not the admitted members")
    producer_document = document["producer"]
    if not isinstance(producer_document, dict):
        raise ProvenanceError("stored producer identity must be a JSON object")
    source_documents = document["source_refs"]
    if not isinstance(source_documents, list):
        raise ProvenanceError("stored source references must be a JSON array")
    try:
        source_refs: list[SourceRef] = []
        for source_document in source_documents:
            if not isinstance(source_document, dict):
                raise ProvenanceError("stored source reference must be a JSON object")
            source_refs.append(
                SourceRef(
                    kind=SourceKind(_string_member(source_document, "kind")),
                    source_id=_string_member(source_document, "source_id"),
                    source_revision=_string_member(source_document, "source_revision"),
                    locator=_optional_string_member(source_document, "locator"),
                )
            )
        record = ProvenanceRecord(
            binding=ObjectBinding(
                workspace_id=UUID(_string_member(document, "workspace_id")),
                object_id=UUID(_string_member(document, "object_id")),
                object_type=WorkspaceObjectType(_string_member(document, "object_type")),
                object_revision=_string_member(document, "object_revision"),
            ),
            content_digest=_string_member(document, "content_digest"),
            producer=ProducerIdentity(
                kind=ProducerKind(_string_member(producer_document, "kind")),
                identifier=_string_member(producer_document, "identifier"),
                version=_string_member(producer_document, "version"),
            ),
            source_refs=tuple(source_refs),
            review_state=ReviewState(_string_member(document, "review_state")),
            provenance_format_version=_integer_member(document, "provenance_format_version"),
            policy_version=_string_member(document, "policy_version"),
        )
    except ValueError as error:
        raise ProvenanceError(
            "stored provenance record carries an unadmitted member value"
        ) from error
    return record.validated()


def _string_member(document: dict[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str):
        raise ProvenanceError(f"stored provenance member {name!r} must be a string")
    return value


def _optional_string_member(document: dict[str, object], name: str) -> str | None:
    value = document.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ProvenanceError(f"stored provenance member {name!r} must be a string or null")
    return value


def _integer_member(document: dict[str, object], name: str) -> int:
    value = document.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProvenanceError(f"stored provenance member {name!r} must be an integer")
    return value


def verify_provenance(store: WorkspaceStore, binding: ObjectBinding) -> ProvenanceRecord:
    """Re-verify that stored content still matches its recorded provenance digest."""

    admitted = binding.validated()
    record = read_provenance(store, admitted)
    record.verify_payload(store.get_object(admitted))
    return record
