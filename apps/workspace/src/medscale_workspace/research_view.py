"""Research workspace views for CW-016 with deterministic fixtures only.

CW-016 exposes Research Core artifacts through a local product view. The
Workspace package cannot import Research Core (the boundary guard forbids it)
and holds no network capability, so a view pins caller-supplied versioned
artifact identities through existing versioned interfaces only: the caller
names an artifact identity, kind, revision, evidence digest, and interface
version, and this module validates, stores, and displays exactly those pinned
identities. Nothing here reaches Research Core, live or otherwise.

Admitted artifact kinds are a closed set of research metadata classes
(evidence records, benchmark results, model cards, dataset manifests). Every
descriptor carries an exact member set: artifact identity, kind, revision,
evidence digest, interface name, and interface version. Any other member --
in particular any patient, session, encounter, draft, review, transcript, or
identifier member smuggled into a descriptor -- fails closed. No patient
context enters research views automatically because no parameter, member, or
code path exists that could carry it.

Views are immutable pinned records with deterministic uuid5 identities. Reads
re-verify the provenance digest and the workspace binding. No mutation API
exists in this module: there is no update, refresh, attach, link, export, or
write entry point, and the no-backflow guard refuses every Workspace to
Research Core flow. Displayed text is data, not authority: artifact labels
and revisions are stored verbatim, never evaluated, never executed, and never
consulted for capability, policy, or governance decisions. Malicious strings
remain inert.
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
    ObjectNotFoundError,
    ProvenanceDigestMismatchError,
    ResearchViewConflictError,
    ResearchViewInputError,
    ResearchViewRevisionError,
    ResearchViewStaleError,
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
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

RESEARCH_VIEW_NAMESPACE = UUID("9c16d016-0002-4000-8000-000000000016")
VIEW_REVISION = "workspace-research-view-00000001"
PRODUCER_VERSION = "cw016-v1"
DERIVATION_METHOD = "cw016-deterministic-view"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw016-research-view/1"
ADMITTED_INTERFACE_VERSION = "1"
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_REVISION_CHARS = 64
MAXIMUM_INTERFACE_CHARS = 64
MAXIMUM_VIEW_BYTES = 32768
MAXIMUM_OCCURRED_AT_CHARS = 64


class ArtifactKind(StrEnum):
    """Admitted Research Core artifact classes a view may pin. Read-only."""

    EVIDENCE_RECORD = "evidence-record"
    BENCHMARK_RESULT = "benchmark-result"
    MODEL_CARD = "model-card"
    DATASET_MANIFEST = "dataset-manifest"


@dataclass(frozen=True, slots=True)
class ResearchArtifactDescriptor:
    """One validated caller-held artifact descriptor. Never a stored object."""

    artifact_id: UUID
    artifact_kind: ArtifactKind
    artifact_revision: str
    evidence_digest: str
    interface_name: str
    interface_version: str

    def validated(self):
        if not isinstance(self.artifact_id, UUID):
            raise ResearchViewInputError("an artifact identity must be a UUID value")
        if not isinstance(self.artifact_kind, ArtifactKind):
            raise ResearchViewInputError("an artifact kind is not admitted here")
        revision = _admit_revision(self.artifact_revision)
        digest = _admit_digest(self.evidence_digest)
        interface = _admit_interface_name(self.interface_name)
        version = _admit_interface_version(self.interface_version)
        return ResearchArtifactDescriptor(
            artifact_id=self.artifact_id,
            artifact_kind=self.artifact_kind,
            artifact_revision=revision,
            evidence_digest=digest,
            interface_name=interface,
            interface_version=version,
        )


@dataclass(frozen=True, slots=True)
class ResearchViewRecord:
    """One immutable pinned view of versioned artifact identities."""

    workspace_id: UUID
    view_id: UUID
    artifact_id: UUID
    artifact_kind: ArtifactKind
    artifact_revision: str
    evidence_digest: str
    interface_name: str
    interface_version: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise ResearchViewInputError("a workspace id must be a UUID value")
        if not isinstance(self.view_id, UUID):
            raise ResearchViewInputError("a view identity must be a UUID value")
        if not isinstance(self.artifact_id, UUID):
            raise ResearchViewInputError("an artifact identity must be a UUID value")
        if not isinstance(self.artifact_kind, ArtifactKind):
            raise ResearchViewInputError("an artifact kind is not admitted here")
        revision = _admit_revision(self.artifact_revision)
        digest = _admit_digest(self.evidence_digest)
        interface = _admit_interface_name(self.interface_name)
        version = _admit_interface_version(self.interface_version)
        expected = view_id_for(
            self.workspace_id,
            self.artifact_id,
            self.artifact_kind,
            revision,
            digest,
            interface,
            version,
        )
        if self.view_id != expected:
            raise ResearchViewRevisionError("a view identity does not match its pinned inputs")
        return ResearchViewRecord(
            workspace_id=self.workspace_id,
            view_id=self.view_id,
            artifact_id=self.artifact_id,
            artifact_kind=self.artifact_kind,
            artifact_revision=revision,
            evidence_digest=digest,
            interface_name=interface,
            interface_version=version,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "artifact_id": str(admitted.artifact_id),
            "artifact_kind": admitted.artifact_kind.value,
            "artifact_revision": admitted.artifact_revision,
            "data_class": _research_view_data_class_value(),
            "derivation_method": DERIVATION_METHOD,
            "derivation_method_version": DERIVATION_METHOD_VERSION,
            "evidence_digest": admitted.evidence_digest,
            "interface_name": admitted.interface_name,
            "interface_version": admitted.interface_version,
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "view_id": str(admitted.view_id),
            "view_revision": VIEW_REVISION,
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ResearchViewInputError("a stored research view must be a JSON object")
        expected = {
            "artifact_id",
            "artifact_kind",
            "artifact_revision",
            "data_class",
            "derivation_method",
            "derivation_method_version",
            "evidence_digest",
            "interface_name",
            "interface_version",
            "policy_version",
            "schema_version",
            "view_id",
            "view_revision",
            "workspace_id",
        }
        if set(document) != expected:
            raise ResearchViewInputError("a stored research view carries unadmitted members")
        if document["view_revision"] != VIEW_REVISION:
            raise ResearchViewRevisionError("a stored view revision is mismatched")
        if document["data_class"] != _research_view_data_class_value():
            raise ResearchViewInputError("a stored view data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise ResearchViewInputError("a stored view policy version is not supported")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise ResearchViewRevisionError("a stored view derivation method is mismatched")
        if document["derivation_method_version"] != DERIVATION_METHOD_VERSION:
            raise ResearchViewRevisionError("a stored view derivation version is mismatched")
        if document["schema_version"] != SCHEMA_VERSION:
            raise ResearchViewRevisionError("a stored view schema version is mismatched")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            view_id = UUID(str(document["view_id"]))
            artifact_id = UUID(str(document["artifact_id"]))
        except ValueError as error:
            raise ResearchViewInputError("a stored view identity is not admitted") from error
        return ResearchViewRecord(
            workspace_id=workspace_id,
            view_id=view_id,
            artifact_id=artifact_id,
            artifact_kind=_admit_artifact_kind(document["artifact_kind"]),
            artifact_revision=_string_member(document, "artifact_revision"),
            evidence_digest=_string_member(document, "evidence_digest"),
            interface_name=_string_member(document, "interface_name"),
            interface_version=_string_member(document, "interface_version"),
        ).validated()


def research_view_data_class_value():
    """Return the wire value of the public research-metadata data class."""
    return _research_view_data_class_value()


def admit_research_descriptor(
    artifact_id,
    artifact_kind,
    artifact_revision,
    evidence_digest,
    interface_name,
    interface_version,
):
    """Admit one caller-supplied artifact descriptor with an exact member set.

    The descriptor carries exactly the six admitted members. Any additional
    member -- including patient, session, or encounter context -- has nowhere
    to go: this function takes no further parameters and admits no further
    members, so smuggled context cannot be supplied at all.
    """
    if not isinstance(artifact_id, UUID):
        raise ResearchViewInputError("an artifact identity must be a UUID value")
    return ResearchArtifactDescriptor(
        artifact_id=artifact_id,
        artifact_kind=_admit_artifact_kind(artifact_kind),
        artifact_revision=artifact_revision,
        evidence_digest=evidence_digest,
        interface_name=interface_name,
        interface_version=interface_version,
    ).validated()


def view_id_for(
    workspace_id,
    artifact_id,
    artifact_kind,
    artifact_revision,
    evidence_digest,
    interface_name,
    interface_version,
):
    """Return the deterministic view identity for one exact pinned input set."""
    if not isinstance(workspace_id, UUID):
        raise ResearchViewInputError("a workspace id must be a UUID value")
    if not isinstance(artifact_id, UUID):
        raise ResearchViewInputError("an artifact identity must be a UUID value")
    admitted_kind = _admit_artifact_kind(artifact_kind)
    revision = _admit_revision(artifact_revision)
    digest = _admit_digest(evidence_digest)
    interface = _admit_interface_name(interface_name)
    version = _admit_interface_version(interface_version)
    return uuid5(
        RESEARCH_VIEW_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(artifact_id),
                admitted_kind.value,
                revision,
                digest,
                interface,
                version,
            )
        ),
    )


def view_binding(workspace_id, view_id):
    """Return the store binding of one research view."""
    if not isinstance(workspace_id, UUID):
        raise ResearchViewInputError("a workspace id must be a UUID value")
    if not isinstance(view_id, UUID):
        raise ResearchViewInputError("a view identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=view_id,
        object_type=WorkspaceObjectType.WORKSPACE_RESEARCH_VIEW,
        object_revision=VIEW_REVISION,
    )


def view_payload_bytes(record):
    """Return the canonical storage payload of one research view."""
    if not isinstance(record, ResearchViewRecord):
        raise ResearchViewInputError("a view payload needs a ResearchViewRecord instance")
    return _canonical_bytes(record.to_document())


def store_research_view(store, trail, workspace_id, descriptor, actor_id, occurred_at):
    """Pin one artifact descriptor as an immutable workspace view.

    The descriptor is re-validated here; the stored view binds the exact
    pinned identities with provenance and an object-create audit event. No
    patient context is accepted, attached, or recorded at any point.
    """
    if not isinstance(store, WorkspaceStore):
        raise ResearchViewInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ResearchViewInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise ResearchViewInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a research view crossed the workspace boundary")
    if not isinstance(descriptor, ResearchArtifactDescriptor):
        raise ResearchViewInputError("a view needs a ResearchArtifactDescriptor instance")
    admitted = descriptor.validated()
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    record = ResearchViewRecord(
        workspace_id=workspace_id,
        view_id=view_id_for(
            workspace_id,
            admitted.artifact_id,
            admitted.artifact_kind,
            admitted.artifact_revision,
            admitted.evidence_digest,
            admitted.interface_name,
            admitted.interface_version,
        ),
        artifact_id=admitted.artifact_id,
        artifact_kind=admitted.artifact_kind,
        artifact_revision=admitted.artifact_revision,
        evidence_digest=admitted.evidence_digest,
        interface_name=admitted.interface_name,
        interface_version=admitted.interface_version,
    ).validated()
    stored = _canonical_bytes(record.to_document())
    if len(stored) > MAXIMUM_VIEW_BYTES:
        raise ResearchViewInputError("a research view exceeds the admitted size")
    source_refs = (
        SourceRef(
            kind=SourceKind.RESEARCH_ARTIFACT_VIEW,
            source_id=str(admitted.artifact_id),
            source_revision=admitted.artifact_revision,
            locator=admitted.interface_name,
        ).validated(),
    )
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=actor, version=PRODUCER_VERSION
    )
    provenance_record = describe_revision(
        binding=view_binding(workspace_id, record.view_id),
        payload=stored,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, provenance_record, stored)
    except StoreConflictError as error:
        raise ResearchViewConflictError("the research view identity already exists") from error
    trail.append(
        event_type=AuditEventType.OBJECT_CREATE,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=record.view_id,
                object_type=WorkspaceObjectType.WORKSPACE_RESEARCH_VIEW,
                object_revision=VIEW_REVISION,
                content_digest=provenance_record.content_digest,
            ),
        ),
        metadata=(
            ("artifact_kind", admitted.artifact_kind.value),
            ("artifact_revision", admitted.artifact_revision),
            ("interface_name", admitted.interface_name),
            ("view_digest", provenance_record.content_digest),
        ),
    )
    return view_binding(workspace_id, record.view_id)


def read_research_view(store, view_id):
    """Read and verify one stored research view."""
    if not isinstance(store, WorkspaceStore):
        raise ResearchViewInputError("a workspace store is required")
    if not isinstance(view_id, UUID):
        raise ResearchViewInputError("a view identity must be a UUID value")
    binding = view_binding(store.workspace_id, view_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ResearchViewInputError("the view identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ResearchViewInputError("a stored research view is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ResearchViewInputError("a stored research view is not JSON") from error
    record = ResearchViewRecord.from_document(document)
    if record.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a research view crossed the workspace boundary")
    if record.view_id != view_id:
        raise ResearchViewInputError("a stored view identity does not match its binding")
    stored_provenance = read_provenance(store, binding)
    try:
        stored_provenance.verify_payload(raw)
    except ProvenanceDigestMismatchError as error:
        raise ResearchViewStaleError("a research view digest no longer matches") from error
    return record.validated()


def delete_research_view(store, trail, view_id, actor_id, occurred_at):
    """Delete one research view; the audit trail survives."""
    if not isinstance(store, WorkspaceStore):
        raise ResearchViewInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ResearchViewInputError("an audit trail is required")
    if not isinstance(view_id, UUID):
        raise ResearchViewInputError("a view identity must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    record = read_research_view(store, view_id)
    binding = view_binding(store.workspace_id, record.view_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def _research_view_data_class_value():
    return admit_data_class("PUBLIC").value


def _admit_artifact_kind(raw):
    if isinstance(raw, ArtifactKind):
        return raw
    if isinstance(raw, str):
        try:
            return ArtifactKind(raw.strip())
        except ValueError as error:
            raise ResearchViewInputError("an artifact kind is not admitted here") from error
    raise ResearchViewInputError("an artifact kind must be admitted here")


def _admit_revision(raw):
    if not isinstance(raw, str):
        raise ResearchViewInputError("an artifact revision must be a string")
    value = raw.strip()
    if not value:
        raise ResearchViewInputError("an artifact revision must be non-empty")
    if len(value) > MAXIMUM_REVISION_CHARS:
        raise ResearchViewInputError("an artifact revision is longer than the admitted maximum")
    if not value.isascii():
        raise ResearchViewInputError("an artifact revision must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ResearchViewInputError(
                "an artifact revision must not contain whitespace or controls"
            )
    return value


def _admit_digest(raw):
    if not isinstance(raw, str):
        raise ResearchViewInputError("an evidence digest must be a string")
    value = raw.strip()
    if not value.startswith("sha256:"):
        raise ResearchViewInputError("an evidence digest must be a sha256 digest")
    remainder = value[len("sha256:") :]
    if len(remainder) != 64:
        raise ResearchViewInputError("an evidence digest must carry 64 hex characters")
    for character in remainder:
        if character not in "0123456789abcdef":
            raise ResearchViewInputError("an evidence digest must carry lowercase hex")
    return value


def _admit_interface_name(raw):
    if not isinstance(raw, str):
        raise ResearchViewInputError("an interface name must be a string")
    value = raw.strip()
    if not value:
        raise ResearchViewInputError("an interface name must be non-empty")
    if len(value) > MAXIMUM_INTERFACE_CHARS:
        raise ResearchViewInputError("an interface name is longer than the admitted maximum")
    if not value.isascii():
        raise ResearchViewInputError("an interface name must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ResearchViewInputError(
                "an interface name must not contain whitespace or controls"
            )
    return value


def _admit_interface_version(raw):
    if not isinstance(raw, str):
        raise ResearchViewInputError("an interface version must be a string")
    value = raw.strip()
    if not value:
        raise ResearchViewInputError("an interface version must be non-empty")
    if len(value) > MAXIMUM_INTERFACE_CHARS:
        raise ResearchViewInputError("an interface version is longer than the admitted maximum")
    if not value.isascii():
        raise ResearchViewInputError("an interface version must be ASCII")
    if value != ADMITTED_INTERFACE_VERSION:
        raise ResearchViewRevisionError("an interface version is not supported here")
    return value


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise ResearchViewInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ResearchViewInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise ResearchViewInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ResearchViewInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ResearchViewInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_occurred_at(raw):
    value = _admit_identifier(raw, "view occurrence time")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise ResearchViewInputError("a view occurrence time is longer than admitted")
    if len(value) < 20 or value[10:11] != "T":
        raise ResearchViewInputError("a view occurrence time must be an ISO instant with zone")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise ResearchViewInputError(f"a stored {name} must be a string")
    return value
