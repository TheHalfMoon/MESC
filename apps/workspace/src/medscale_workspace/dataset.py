"""Dataset workspace and export quarantine for CW-017 with deterministic fixtures only.

CW-017 separates research datasets from clinical export staging. The Workspace
package cannot import Research Core (the boundary guard forbids it) and holds
no network capability, so both modes below are local and mechanical:

Research dataset mode is read-only. A dataset collection pins the identities
of already-stored dataset-manifest research views (CW-016) through the existing
versioned read interface. Every member is re-read and re-verified at store
time; a view of any other artifact kind, an unknown view identity, or a
cross-workspace view fails closed. Collections carry no content, only pinned
identities, and no collection member can become a Research Core dataset
identity: this module mints nothing in Research Core and holds no admission
entry point into it.

Export staging mode stages references, never content. An export manifest pins
the identities, revisions, and recorded payload digests of already-stored
Workspace objects together with an explicit quarantine target, a closed
consent scope, closed source rights, and a recorded de-identification
transformation. Each source payload is re-read and its digest recomputed at
stage time, so a deleted or drifted source fails closed. Content bytes never
enter the manifest: the admitted de-identification method is reference-only,
so residual identifiers cannot travel even when source content carries
identifier-like strings. The quarantine target is proven strictly below a
declared Domain X root and outside every declared Research Core root by pure
path algebra; no file is written. Staging requires an explicit caller export
request; automatic staging is refused.

De-identification is recorded as a transformation of an export, never as an
admission: a staged export remains Domain X and is never marked research
admitted.

Reads re-verify currency as well as integrity. Reading a collection re-reads
every pinned member view, and reading an export manifest re-reads every staged
source and recomputes its digest; a deleted, drifted, or re-kinded reference
fails closed as stale instead of returning a record that points at state which
no longer exists. Deletion verifies integrity only, so a stale record can
still be removed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID, uuid5

from medscale_workspace import research_view as research_view_mod
from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import admit_data_class
from medscale_workspace.errors import (
    DatasetCollectionConflictError,
    DatasetCollectionInputError,
    DatasetCollectionRevisionError,
    DatasetCollectionStaleError,
    ExplicitExportRequestError,
    ExportBoundaryError,
    ExportStagingConflictError,
    ExportStagingInputError,
    ExportStagingStaleError,
    ObjectNotFoundError,
    ProvenanceDigestMismatchError,
    ResearchViewInputError,
    ResearchViewStaleError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.nobackflow import admit_export_path
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

DATASET_COLLECTION_NAMESPACE = UUID("c5a1d017-0003-4000-8000-000000000017")
EXPORT_MANIFEST_NAMESPACE = UUID("d6b2e017-0004-4000-8000-000000000017")
COLLECTION_REVISION = "workspace-dataset-collection-00000001"
EXPORT_REVISION = "workspace-export-manifest-00000001"
PRODUCER_VERSION = "cw017-v1"
DERIVATION_METHOD = "cw017-deterministic-staging"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw017-dataset/1"
ADMITTED_INTERFACE_VERSION = "1"
ADMITTED_CONSENT_SCOPE = "synthetic-only"
ADMITTED_SOURCE_RIGHTS = "synthetic-fixture"
ADMITTED_DEIDENTIFICATION_METHOD = "reference-only"
ADMITTED_DEIDENTIFICATION_VERSION = "1"
COLLECTION_MEMBER_LABEL = "dataset-collection"
MAXIMUM_COLLECTION_MEMBERS = 64
MAXIMUM_EXPORT_ITEMS = 64
MAXIMUM_NAME_CHARS = 64
MAXIMUM_REVISION_CHARS = 128
MAXIMUM_INTERFACE_CHARS = 64
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_VIEW_BYTES = 32768
MAXIMUM_OCCURRED_AT_CHARS = 64
MAXIMUM_PATH_CHARS = 512
MAXIMUM_RESEARCH_ROOTS = 8

EXPORTABLE_SOURCE_TYPES = frozenset(
    {
        WorkspaceObjectType.LINKED_DOCUMENT,
        WorkspaceObjectType.LINKED_TABLE,
        WorkspaceObjectType.FHIR_RESOURCE,
        WorkspaceObjectType.CLINICAL_REVIEW,
        WorkspaceObjectType.EVIDENCE_RESULT,
        WorkspaceObjectType.EVIDENCE_SNAPSHOT,
        WorkspaceObjectType.WORKSPACE_ANALYTICS,
        WorkspaceObjectType.WORKSPACE_RESEARCH_VIEW,
    }
)


@dataclass(frozen=True, slots=True)
class DatasetCollectionDescriptor:
    """One validated caller-held dataset collection request. Never a stored object."""

    collection_name: str
    view_ids: tuple[UUID, ...]
    interface_version: str

    def validated(self):
        name = _admit_name(self.collection_name)
        members = _admit_view_ids(self.view_ids)
        version = _admit_collection_interface_version(self.interface_version)
        return DatasetCollectionDescriptor(
            collection_name=name,
            view_ids=members,
            interface_version=version,
        )


@dataclass(frozen=True, slots=True)
class DatasetCollectionRecord:
    """One immutable pinned collection of dataset-manifest view identities."""

    workspace_id: UUID
    collection_id: UUID
    collection_name: str
    view_ids: tuple[UUID, ...]
    interface_version: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise DatasetCollectionInputError("a workspace id must be a UUID value")
        if not isinstance(self.collection_id, UUID):
            raise DatasetCollectionInputError("a collection identity must be a UUID value")
        name = _admit_name(self.collection_name)
        members = _admit_view_ids(self.view_ids)
        version = _admit_collection_interface_version(self.interface_version)
        expected = collection_id_for(self.workspace_id, name, members, version)
        if self.collection_id != expected:
            raise DatasetCollectionRevisionError(
                "a collection identity does not match its pinned inputs"
            )
        return DatasetCollectionRecord(
            workspace_id=self.workspace_id,
            collection_id=self.collection_id,
            collection_name=name,
            view_ids=members,
            interface_version=version,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "collection_id": str(admitted.collection_id),
            "collection_name": admitted.collection_name,
            "collection_revision": COLLECTION_REVISION,
            "data_class": _collection_data_class_value(),
            "derivation_method": DERIVATION_METHOD,
            "derivation_method_version": DERIVATION_METHOD_VERSION,
            "interface_version": admitted.interface_version,
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "view_ids": [str(member) for member in admitted.view_ids],
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise DatasetCollectionInputError("a stored collection must be a JSON object")
        expected = {
            "collection_id",
            "collection_name",
            "collection_revision",
            "data_class",
            "derivation_method",
            "derivation_method_version",
            "interface_version",
            "policy_version",
            "schema_version",
            "view_ids",
            "workspace_id",
        }
        if set(document) != expected:
            raise DatasetCollectionInputError("a stored collection carries unadmitted members")
        if document["collection_revision"] != COLLECTION_REVISION:
            raise DatasetCollectionRevisionError("a stored collection revision is mismatched")
        if document["data_class"] != _collection_data_class_value():
            raise DatasetCollectionInputError("a stored collection data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise DatasetCollectionInputError("a stored collection policy version is not supported")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise DatasetCollectionRevisionError(
                "a stored collection derivation method is mismatched"
            )
        if document["derivation_method_version"] != DERIVATION_METHOD_VERSION:
            raise DatasetCollectionRevisionError(
                "a stored collection derivation version is mismatched"
            )
        if document["schema_version"] != SCHEMA_VERSION:
            raise DatasetCollectionRevisionError("a stored collection schema version is mismatched")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            collection_id = UUID(str(document["collection_id"]))
        except ValueError as error:
            raise DatasetCollectionInputError(
                "a stored collection identity is not admitted"
            ) from error
        raw_members = document["view_ids"]
        if not isinstance(raw_members, list):
            raise DatasetCollectionInputError("stored collection members must be a JSON array")
        try:
            members = tuple(UUID(str(member)) for member in raw_members)
        except ValueError as error:
            raise DatasetCollectionInputError(
                "a stored collection member is not admitted"
            ) from error
        return DatasetCollectionRecord(
            workspace_id=workspace_id,
            collection_id=collection_id,
            collection_name=_string_member(
                document, "collection_name", DatasetCollectionInputError
            ),
            view_ids=members,
            interface_version=_string_member(
                document, "interface_version", DatasetCollectionInputError
            ),
        ).validated()


@dataclass(frozen=True, slots=True)
class ExportSourceDescriptor:
    """One validated caller-held export source reference. Never a stored object."""

    object_id: UUID
    object_kind: WorkspaceObjectType
    object_revision: str

    def validated(self):
        if not isinstance(self.object_id, UUID):
            raise ExportStagingInputError("an export source identity must be a UUID value")
        kind = _admit_source_kind(self.object_kind)
        revision = _admit_revision(self.object_revision)
        return ExportSourceDescriptor(
            object_id=self.object_id,
            object_kind=kind,
            object_revision=revision,
        )


@dataclass(frozen=True, slots=True)
class ExportManifestRecord:
    """One immutable staged export manifest pinned in Domain X."""

    workspace_id: UUID
    export_id: UUID
    items: tuple[ExportSourceDescriptor, ...]
    payload_digests: tuple[str, ...]
    quarantine_target: str
    consent_scope: str
    source_rights: str
    deidentification_method: str
    deidentification_version: str
    deidentification_input_digest: str
    deidentification_output_digest: str
    interface_version: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise ExportStagingInputError("a workspace id must be a UUID value")
        if not isinstance(self.export_id, UUID):
            raise ExportStagingInputError("an export identity must be a UUID value")
        items = _admit_items(self.items)
        digests = _admit_digests(self.payload_digests, len(items))
        target = _admit_path_value(self.quarantine_target)
        consent = _admit_consent_scope(self.consent_scope)
        rights = _admit_source_rights(self.source_rights)
        method = _admit_deidentification_method(self.deidentification_method)
        method_version = _admit_deidentification_version(self.deidentification_version)
        input_digest = _admit_digest(self.deidentification_input_digest)
        output_digest = _admit_digest(self.deidentification_output_digest)
        version = _admit_interface_version(self.interface_version)
        expected = export_id_for(
            self.workspace_id,
            items,
            digests,
            target,
            consent,
            rights,
            method,
            method_version,
            version,
        )
        if self.export_id != expected:
            raise ExportStagingInputError("an export identity does not match its pinned inputs")
        return ExportManifestRecord(
            workspace_id=self.workspace_id,
            export_id=self.export_id,
            items=items,
            payload_digests=digests,
            quarantine_target=target,
            consent_scope=consent,
            source_rights=rights,
            deidentification_method=method,
            deidentification_version=method_version,
            deidentification_input_digest=input_digest,
            deidentification_output_digest=output_digest,
            interface_version=version,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "consent_scope": admitted.consent_scope,
            "data_class": _export_data_class_value(),
            "deidentification": {
                "input_digest": admitted.deidentification_input_digest,
                "method": admitted.deidentification_method,
                "output_digest": admitted.deidentification_output_digest,
                "version": admitted.deidentification_version,
            },
            "derivation_method": DERIVATION_METHOD,
            "derivation_method_version": DERIVATION_METHOD_VERSION,
            "export_id": str(admitted.export_id),
            "export_revision": EXPORT_REVISION,
            "interface_version": admitted.interface_version,
            "items": [
                {
                    "object_id": str(item.object_id),
                    "object_kind": item.object_kind.value,
                    "object_revision": item.object_revision,
                    "payload_digest": digest,
                }
                for item, digest in zip(admitted.items, admitted.payload_digests, strict=True)
            ],
            "policy_version": POLICY_VERSION,
            "quarantine_target": admitted.quarantine_target,
            "schema_version": SCHEMA_VERSION,
            "source_rights": admitted.source_rights,
            "workspace_id": str(admitted.workspace_id),
        }

    def canonical_bytes(self):
        return _canonical_bytes(self.to_document())

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ExportStagingInputError("a stored export manifest must be a JSON object")
        expected = {
            "consent_scope",
            "data_class",
            "deidentification",
            "derivation_method",
            "derivation_method_version",
            "export_id",
            "export_revision",
            "interface_version",
            "items",
            "policy_version",
            "quarantine_target",
            "schema_version",
            "source_rights",
            "workspace_id",
        }
        if set(document) != expected:
            raise ExportStagingInputError("a stored export manifest carries unadmitted members")
        if document["export_revision"] != EXPORT_REVISION:
            raise ExportStagingInputError("a stored export revision is mismatched")
        if document["data_class"] != _export_data_class_value():
            raise ExportStagingInputError("a stored export data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise ExportStagingInputError("a stored export policy version is not supported")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise ExportStagingInputError("a stored export derivation method is mismatched")
        if document["derivation_method_version"] != DERIVATION_METHOD_VERSION:
            raise ExportStagingInputError("a stored export derivation version is mismatched")
        if document["schema_version"] != SCHEMA_VERSION:
            raise ExportStagingInputError("a stored export schema version is mismatched")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            export_id = UUID(str(document["export_id"]))
        except ValueError as error:
            raise ExportStagingInputError("a stored export identity is not admitted") from error
        raw_items = document["items"]
        if not isinstance(raw_items, list):
            raise ExportStagingInputError("stored export items must be a JSON array")
        items = tuple(_export_item_from_document(member) for member in raw_items)
        raw_deidentification = document["deidentification"]
        if not isinstance(raw_deidentification, dict):
            raise ExportStagingInputError("a stored de-identification record must be a JSON object")
        if set(raw_deidentification) != {"input_digest", "method", "output_digest", "version"}:
            raise ExportStagingInputError("a stored de-identification record is not admitted")
        return ExportManifestRecord(
            workspace_id=workspace_id,
            export_id=export_id,
            items=items,
            payload_digests=tuple(
                _string_member(member, "payload_digest", ExportStagingInputError)
                for member in raw_items
            ),
            quarantine_target=_string_member(
                document, "quarantine_target", ExportStagingInputError
            ),
            consent_scope=_string_member(document, "consent_scope", ExportStagingInputError),
            source_rights=_string_member(document, "source_rights", ExportStagingInputError),
            deidentification_method=_string_member(
                raw_deidentification, "method", ExportStagingInputError
            ),
            deidentification_version=_string_member(
                raw_deidentification, "version", ExportStagingInputError
            ),
            deidentification_input_digest=_string_member(
                raw_deidentification, "input_digest", ExportStagingInputError
            ),
            deidentification_output_digest=_string_member(
                raw_deidentification, "output_digest", ExportStagingInputError
            ),
            interface_version=_string_member(
                document, "interface_version", ExportStagingInputError
            ),
        ).validated()


def dataset_collection_data_class_value():
    """Return the wire value of the public dataset-collection data class."""
    return _collection_data_class_value()


def export_manifest_data_class_value():
    """Return the wire value of the export-quarantine manifest data class."""
    return _export_data_class_value()


def admit_dataset_collection(collection_name, view_ids, interface_version):
    """Admit one caller-supplied dataset collection request with an exact member set.

    The request carries exactly a collection name, a tuple of view identities,
    and an interface version. No content, no patient context, and no Research
    Core identity travels with it.
    """
    if not isinstance(view_ids, tuple):
        raise DatasetCollectionInputError("collection members must be a tuple of view identities")
    return DatasetCollectionDescriptor(
        collection_name=collection_name,
        view_ids=view_ids,
        interface_version=interface_version,
    ).validated()


def collection_id_for(workspace_id, collection_name, view_ids, interface_version):
    """Return the deterministic collection identity for one exact pinned input set."""
    if not isinstance(workspace_id, UUID):
        raise DatasetCollectionInputError("a workspace id must be a UUID value")
    name = _admit_name(collection_name)
    members = _admit_view_ids(view_ids)
    version = _admit_collection_interface_version(interface_version)
    return uuid5(
        DATASET_COLLECTION_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                name,
                version,
                ",".join(sorted(str(member) for member in members)),
            )
        ),
    )


def dataset_collection_binding(workspace_id, collection_id):
    """Return the store binding of one dataset collection."""
    if not isinstance(workspace_id, UUID):
        raise DatasetCollectionInputError("a workspace id must be a UUID value")
    if not isinstance(collection_id, UUID):
        raise DatasetCollectionInputError("a collection identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=collection_id,
        object_type=WorkspaceObjectType.WORKSPACE_DATASET_COLLECTION,
        object_revision=COLLECTION_REVISION,
    )


def collection_payload_bytes(record):
    """Return the canonical storage payload of one dataset collection."""
    if not isinstance(record, DatasetCollectionRecord):
        raise DatasetCollectionInputError("a collection payload needs a DatasetCollectionRecord")
    return _canonical_bytes(record.to_document())


def store_dataset_collection(store, trail, workspace_id, descriptor, actor_id, occurred_at):
    """Pin one collection of dataset-manifest views as an immutable workspace record.

    Every member view is re-read through the existing versioned read interface
    and must be a dataset-manifest view bound to this workspace. The stored
    collection carries identities only, never content.
    """
    if not isinstance(store, WorkspaceStore):
        raise DatasetCollectionInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise DatasetCollectionInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise DatasetCollectionInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a dataset collection crossed the workspace boundary")
    if not isinstance(descriptor, DatasetCollectionDescriptor):
        raise DatasetCollectionInputError("a collection needs a DatasetCollectionDescriptor")
    admitted = descriptor.validated()
    actor = _admit_collection_identifier(actor_id, "actor id")
    moment = _admit_collection_occurred_at(occurred_at)
    for member in admitted.view_ids:
        try:
            view = research_view_mod.read_research_view(store, member)
        except (
            ResearchViewInputError,
            ResearchViewStaleError,
            WorkspaceIsolationError,
            ObjectNotFoundError,
        ) as error:
            raise DatasetCollectionInputError("a collected view is not admitted here") from error
        if view.artifact_kind is not research_view_mod.ArtifactKind.DATASET_MANIFEST:
            raise DatasetCollectionInputError("a collected view kind is not admitted here")
    record = DatasetCollectionRecord(
        workspace_id=workspace_id,
        collection_id=collection_id_for(
            workspace_id, admitted.collection_name, admitted.view_ids, admitted.interface_version
        ),
        collection_name=admitted.collection_name,
        view_ids=admitted.view_ids,
        interface_version=admitted.interface_version,
    ).validated()
    stored = _canonical_bytes(record.to_document())
    if len(stored) > MAXIMUM_VIEW_BYTES:
        raise DatasetCollectionInputError("a dataset collection exceeds the admitted size")
    source_refs = tuple(
        SourceRef(
            kind=SourceKind.RESEARCH_ARTIFACT_VIEW,
            source_id=str(member),
            source_revision=research_view_mod.VIEW_REVISION,
            locator=COLLECTION_MEMBER_LABEL,
        ).validated()
        for member in admitted.view_ids
    )
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=actor, version=PRODUCER_VERSION
    )
    provenance_record = describe_revision(
        binding=dataset_collection_binding(workspace_id, record.collection_id),
        payload=stored,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, provenance_record, stored)
    except StoreConflictError as error:
        raise DatasetCollectionConflictError(
            "the dataset collection identity already exists"
        ) from error
    trail.append(
        event_type=AuditEventType.OBJECT_CREATE,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=record.collection_id,
                object_type=WorkspaceObjectType.WORKSPACE_DATASET_COLLECTION,
                object_revision=COLLECTION_REVISION,
                content_digest=provenance_record.content_digest,
            ),
        ),
        metadata=(
            ("collection_kind", "dataset-collection"),
            ("collection_digest", provenance_record.content_digest),
            ("member_count", str(len(admitted.view_ids))),
        ),
    )
    return dataset_collection_binding(workspace_id, record.collection_id)


def read_dataset_collection(store, collection_id):
    """Read and verify one stored dataset collection with every member view still current."""
    record = _read_collection_record(store, collection_id)
    _current_collection_views(store, record)
    return record


def list_collection_views(store, collection_id):
    """Resolve every pinned view of one stored dataset collection, read-only."""
    record = _read_collection_record(store, collection_id)
    return _current_collection_views(store, record)


def _read_collection_record(store, collection_id):
    if not isinstance(store, WorkspaceStore):
        raise DatasetCollectionInputError("a workspace store is required")
    if not isinstance(collection_id, UUID):
        raise DatasetCollectionInputError("a collection identity must be a UUID value")
    binding = dataset_collection_binding(store.workspace_id, collection_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise DatasetCollectionInputError(
            "the collection identity is not present in this store"
        ) from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise DatasetCollectionInputError("a stored collection is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise DatasetCollectionInputError("a stored collection is not JSON") from error
    record = DatasetCollectionRecord.from_document(document)
    if record.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a dataset collection crossed the workspace boundary")
    if record.collection_id != collection_id:
        raise DatasetCollectionInputError("a stored collection identity does not match its binding")
    stored_provenance = read_provenance(store, binding)
    try:
        stored_provenance.verify_payload(raw)
    except ProvenanceDigestMismatchError as error:
        raise DatasetCollectionStaleError("a collection digest no longer matches") from error
    return record.validated()


def _current_collection_views(store, record):
    views = []
    for member in record.view_ids:
        try:
            view = research_view_mod.read_research_view(store, member)
        except (ResearchViewInputError, ResearchViewStaleError, ObjectNotFoundError) as error:
            raise DatasetCollectionStaleError("a collected view is no longer current") from error
        if view.artifact_kind is not research_view_mod.ArtifactKind.DATASET_MANIFEST:
            raise DatasetCollectionStaleError("a collected view kind is no longer admitted")
        views.append(view)
    return tuple(views)


def delete_dataset_collection(store, trail, collection_id, actor_id, occurred_at):
    """Delete one dataset collection; the audit trail survives."""
    if not isinstance(store, WorkspaceStore):
        raise DatasetCollectionInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise DatasetCollectionInputError("an audit trail is required")
    if not isinstance(collection_id, UUID):
        raise DatasetCollectionInputError("a collection identity must be a UUID value")
    actor = _admit_collection_identifier(actor_id, "actor id")
    moment = _admit_collection_occurred_at(occurred_at)
    record = _read_collection_record(store, collection_id)
    binding = dataset_collection_binding(store.workspace_id, record.collection_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def admit_export_source(object_id, object_kind, object_revision):
    """Admit one caller-supplied export source reference with an exact member set.

    The reference carries exactly a source identity, a closed source kind, and
    a source revision. Content bytes have no parameter here and cannot be
    supplied at all.
    """
    if not isinstance(object_id, UUID):
        raise ExportStagingInputError("an export source identity must be a UUID value")
    return ExportSourceDescriptor(
        object_id=object_id,
        object_kind=_admit_source_kind(object_kind),
        object_revision=object_revision,
    ).validated()


def export_id_for(
    workspace_id,
    items,
    payload_digests,
    quarantine_target,
    consent_scope,
    source_rights,
    deidentification_method,
    deidentification_version,
    interface_version,
):
    """Return the deterministic export identity for one exact pinned input set."""
    if not isinstance(workspace_id, UUID):
        raise ExportStagingInputError("a workspace id must be a UUID value")
    admitted_items = _admit_items(items)
    admitted_digests = _admit_digests(payload_digests, len(admitted_items))
    target = _admit_path_value(quarantine_target)
    consent = _admit_consent_scope(consent_scope)
    rights = _admit_source_rights(source_rights)
    method = _admit_deidentification_method(deidentification_method)
    method_version = _admit_deidentification_version(deidentification_version)
    version = _admit_interface_version(interface_version)
    return uuid5(
        EXPORT_MANIFEST_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                ",".join(
                    sorted(
                        ":".join(
                            (
                                str(item.object_id),
                                item.object_kind.value,
                                item.object_revision,
                                digest,
                            )
                        )
                        for item, digest in zip(admitted_items, admitted_digests, strict=True)
                    )
                ),
                target,
                consent,
                rights,
                method,
                method_version,
                version,
            )
        ),
    )


def export_binding(workspace_id, export_id):
    """Return the store binding of one export manifest."""
    if not isinstance(workspace_id, UUID):
        raise ExportStagingInputError("a workspace id must be a UUID value")
    if not isinstance(export_id, UUID):
        raise ExportStagingInputError("an export identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=export_id,
        object_type=WorkspaceObjectType.WORKSPACE_EXPORT_MANIFEST,
        object_revision=EXPORT_REVISION,
    )


def export_payload_bytes(record):
    """Return the canonical storage payload of one export manifest."""
    if not isinstance(record, ExportManifestRecord):
        raise ExportStagingInputError("an export payload needs an ExportManifestRecord instance")
    return _canonical_bytes(record.to_document())


def stage_export_manifest(
    store,
    trail,
    workspace_id,
    items,
    *,
    target_path,
    quarantine_root,
    research_core_roots,
    consent_scope,
    source_rights,
    deidentification_method,
    deidentification_version,
    explicit_export_request,
    interface_version,
    actor_id,
    occurred_at,
):
    """Stage one export manifest in Domain X from already-stored source revisions.

    Every source payload is re-read and its digest recomputed here; the stored
    manifest carries references and digests only, never content bytes. The
    quarantine target is proven below the quarantine root and outside every
    declared Research Core root; no file is written. Staging without an
    explicit caller export request is refused, and the staged export is never
    marked research admitted.
    """
    if not isinstance(store, WorkspaceStore):
        raise ExportStagingInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ExportStagingInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise ExportStagingInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("an export manifest crossed the workspace boundary")
    if not isinstance(explicit_export_request, bool) or not explicit_export_request:
        raise ExplicitExportRequestError("an export manifest needs an explicit export request")
    admitted_items = _admit_items(items)
    target = _admit_path_value(target_path)
    root = _admit_path_value(quarantine_root)
    roots = _admit_research_roots(research_core_roots)
    consent = _admit_consent_scope(consent_scope)
    rights = _admit_source_rights(source_rights)
    method = _admit_deidentification_method(deidentification_method)
    method_version = _admit_deidentification_version(deidentification_version)
    version = _admit_interface_version(interface_version)
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        admission = admit_export_path(
            target_path=target,
            quarantine_root=root,
            research_core_roots=roots,
        )
    except ExportBoundaryError as error:
        raise ExportStagingInputError("an export target is not admitted here") from error
    digests = tuple(_recorded_payload_digest(store, workspace_id, item) for item in admitted_items)
    input_digest = content_digest_of(",".join(sorted(digests)).encode("ascii"))
    items_section = _canonical_bytes({"items": _items_section(admitted_items, digests)})
    output_digest = content_digest_of(items_section)
    record = ExportManifestRecord(
        workspace_id=workspace_id,
        export_id=export_id_for(
            workspace_id,
            admitted_items,
            digests,
            admission.target_path,
            consent,
            rights,
            method,
            method_version,
            version,
        ),
        items=admitted_items,
        payload_digests=digests,
        quarantine_target=admission.target_path,
        consent_scope=consent,
        source_rights=rights,
        deidentification_method=method,
        deidentification_version=method_version,
        deidentification_input_digest=input_digest,
        deidentification_output_digest=output_digest,
        interface_version=version,
    ).validated()
    stored = _canonical_bytes(record.to_document())
    if len(stored) > MAXIMUM_VIEW_BYTES:
        raise ExportStagingInputError("an export manifest exceeds the admitted size")
    source_refs = tuple(
        SourceRef(
            kind=SourceKind.EXPORT_SOURCE,
            source_id=str(item.object_id),
            source_revision=item.object_revision,
            locator=item.object_kind.value,
        ).validated()
        for item in admitted_items
    )
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=actor, version=PRODUCER_VERSION
    )
    provenance_record = describe_revision(
        binding=export_binding(workspace_id, record.export_id),
        payload=stored,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, provenance_record, stored)
    except StoreConflictError as error:
        raise ExportStagingConflictError("the export manifest identity already exists") from error
    trail.append(
        event_type=AuditEventType.OBJECT_CREATE,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=record.export_id,
                object_type=WorkspaceObjectType.WORKSPACE_EXPORT_MANIFEST,
                object_revision=EXPORT_REVISION,
                content_digest=provenance_record.content_digest,
            ),
        ),
        metadata=(
            ("export_kind", "dataset-export"),
            ("export_digest", provenance_record.content_digest),
            ("item_count", str(len(admitted_items))),
            ("deidentification", method + "/" + method_version),
        ),
    )
    return export_binding(workspace_id, record.export_id)


def read_export_manifest(store, export_id):
    """Read and verify one staged export manifest with every staged source still current."""
    record = _read_export_record(store, export_id)
    for item, digest in zip(record.items, record.payload_digests, strict=True):
        try:
            current = _recorded_payload_digest(store, record.workspace_id, item)
        except ExportStagingInputError as error:
            raise ExportStagingStaleError("a staged export source is no longer present") from error
        if current != digest:
            raise ExportStagingStaleError("a staged export source digest no longer matches")
    return record


def _read_export_record(store, export_id):
    if not isinstance(store, WorkspaceStore):
        raise ExportStagingInputError("a workspace store is required")
    if not isinstance(export_id, UUID):
        raise ExportStagingInputError("an export identity must be a UUID value")
    binding = export_binding(store.workspace_id, export_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ExportStagingInputError("the export identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ExportStagingInputError("a stored export manifest is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ExportStagingInputError("a stored export manifest is not JSON") from error
    record = ExportManifestRecord.from_document(document)
    if record.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("an export manifest crossed the workspace boundary")
    if record.export_id != export_id:
        raise ExportStagingInputError("a stored export identity does not match its binding")
    stored_provenance = read_provenance(store, binding)
    try:
        stored_provenance.verify_payload(raw)
    except ProvenanceDigestMismatchError as error:
        raise ExportStagingStaleError("an export digest no longer matches") from error
    return record.validated()


def delete_export_manifest(store, trail, export_id, actor_id, occurred_at):
    """Delete one export manifest; the audit trail survives."""
    if not isinstance(store, WorkspaceStore):
        raise ExportStagingInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ExportStagingInputError("an audit trail is required")
    if not isinstance(export_id, UUID):
        raise ExportStagingInputError("an export identity must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    record = _read_export_record(store, export_id)
    binding = export_binding(store.workspace_id, record.export_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def _collection_data_class_value():
    return admit_data_class("PUBLIC").value


def _export_data_class_value():
    return admit_data_class("EXPORT_QUARANTINE").value


def _admit_name(raw):
    if not isinstance(raw, str):
        raise DatasetCollectionInputError("a collection name must be a string")
    value = raw.strip()
    if not value:
        raise DatasetCollectionInputError("a collection name must be non-empty")
    if len(value) > MAXIMUM_NAME_CHARS:
        raise DatasetCollectionInputError("a collection name is longer than the admitted maximum")
    if not value.isascii():
        raise DatasetCollectionInputError("a collection name must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise DatasetCollectionInputError(
                "a collection name must not contain whitespace or controls"
            )
    return value


def _admit_view_ids(raw):
    if not isinstance(raw, tuple):
        raise DatasetCollectionInputError("collection members must be a tuple of view identities")
    if not raw or len(raw) > MAXIMUM_COLLECTION_MEMBERS:
        raise DatasetCollectionInputError("a collection needs 1 to 64 member views")
    for member in raw:
        if not isinstance(member, UUID):
            raise DatasetCollectionInputError("a collection member must be a UUID value")
    if len(set(raw)) != len(raw):
        raise DatasetCollectionInputError("a collection must not repeat a member view")
    return raw


def _admit_items(raw):
    if not isinstance(raw, tuple):
        raise ExportStagingInputError("export items must be a tuple of source references")
    if not raw or len(raw) > MAXIMUM_EXPORT_ITEMS:
        raise ExportStagingInputError("an export needs 1 to 64 source items")
    items = tuple(
        item.validated() if isinstance(item, ExportSourceDescriptor) else _refuse_item()
        for item in raw
    )
    identities = [(item.object_id, item.object_kind, item.object_revision) for item in items]
    if len(set(identities)) != len(identities):
        raise ExportStagingInputError("an export must not repeat a source item")
    return items


def _refuse_item():
    raise ExportStagingInputError("an export item needs an ExportSourceDescriptor instance")


def _admit_digests(raw, count):
    if not isinstance(raw, tuple) or len(raw) != count:
        raise ExportStagingInputError("export digests must match the export items")
    return tuple(_admit_digest(digest) for digest in raw)


def _admit_source_kind(raw):
    if isinstance(raw, WorkspaceObjectType):
        member = raw
    elif isinstance(raw, str):
        try:
            member = WorkspaceObjectType(raw.strip())
        except ValueError as error:
            raise ExportStagingInputError("an export source kind is not admitted here") from error
    else:
        raise ExportStagingInputError("an export source kind must be admitted here")
    if member not in EXPORTABLE_SOURCE_TYPES:
        raise ExportStagingInputError("an export source kind is not admitted here")
    return member


def _admit_revision(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("an export source revision must be a string")
    value = raw.strip()
    if not value:
        raise ExportStagingInputError("an export source revision must be non-empty")
    if len(value) > MAXIMUM_REVISION_CHARS:
        raise ExportStagingInputError("an export source revision is longer than admitted")
    if not value.isascii():
        raise ExportStagingInputError("an export source revision must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ExportStagingInputError(
                "an export source revision must not contain whitespace or controls"
            )
    return value


def _admit_digest(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("an export digest must be a string")
    value = raw.strip()
    if not value.startswith("sha256:"):
        raise ExportStagingInputError("an export digest must be a sha256 digest")
    remainder = value[len("sha256:") :]
    if len(remainder) != 64:
        raise ExportStagingInputError("an export digest must carry 64 hex characters")
    for character in remainder:
        if character not in "0123456789abcdef":
            raise ExportStagingInputError("an export digest must carry lowercase hex")
    return value


def _admit_path_value(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("an export path must be a string")
    value = raw.strip()
    if not value:
        raise ExportStagingInputError("an export path must be non-empty")
    if len(value) > MAXIMUM_PATH_CHARS:
        raise ExportStagingInputError("an export path is longer than the admitted maximum")
    if not value.isascii():
        raise ExportStagingInputError("an export path must be ASCII")
    return value


def _admit_research_roots(raw):
    if not isinstance(raw, tuple) or not raw or len(raw) > MAXIMUM_RESEARCH_ROOTS:
        raise ExportStagingInputError("at least one Research Core root must be declared")
    for root in raw:
        _admit_path_value(root)
    return raw


def _admit_consent_scope(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("an export consent scope must be a string")
    value = raw.strip()
    if value != ADMITTED_CONSENT_SCOPE:
        raise ExportStagingInputError("an export consent scope is not admitted here")
    return value


def _admit_source_rights(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("export source rights must be a string")
    value = raw.strip()
    if value != ADMITTED_SOURCE_RIGHTS:
        raise ExportStagingInputError("export source rights are not admitted here")
    return value


def _admit_deidentification_method(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("a de-identification method must be a string")
    value = raw.strip()
    if value != ADMITTED_DEIDENTIFICATION_METHOD:
        raise ExportStagingInputError("a de-identification method is not admitted here")
    return value


def _admit_deidentification_version(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("a de-identification version must be a string")
    value = raw.strip()
    if value != ADMITTED_DEIDENTIFICATION_VERSION:
        raise ExportStagingInputError("a de-identification version is not supported here")
    return value


def _admit_interface_version(raw):
    if not isinstance(raw, str):
        raise ExportStagingInputError("an interface version must be a string")
    value = raw.strip()
    if not value:
        raise ExportStagingInputError("an interface version must be non-empty")
    if len(value) > MAXIMUM_INTERFACE_CHARS:
        raise ExportStagingInputError("an interface version is longer than admitted")
    if not value.isascii():
        raise ExportStagingInputError("an interface version must be ASCII")
    if value != ADMITTED_INTERFACE_VERSION:
        raise ExportStagingInputError("an interface version is not supported here")
    return value


def _admit_collection_interface_version(raw):
    if not isinstance(raw, str):
        raise DatasetCollectionInputError("an interface version must be a string")
    value = raw.strip()
    if not value:
        raise DatasetCollectionInputError("an interface version must be non-empty")
    if len(value) > MAXIMUM_INTERFACE_CHARS:
        raise DatasetCollectionInputError("an interface version is longer than admitted")
    if not value.isascii():
        raise DatasetCollectionInputError("an interface version must be ASCII")
    if value != ADMITTED_INTERFACE_VERSION:
        raise DatasetCollectionRevisionError("an interface version is not supported here")
    return value


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise ExportStagingInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ExportStagingInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise ExportStagingInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ExportStagingInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ExportStagingInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_occurred_at(raw):
    value = _admit_identifier(raw, "staging occurrence time")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise ExportStagingInputError("a staging occurrence time is longer than admitted")
    if len(value) < 20 or value[10:11] != "T":
        raise ExportStagingInputError("a staging occurrence time must be an ISO instant with zone")
    return value


def _admit_collection_identifier(raw, label):
    if not isinstance(raw, str):
        raise DatasetCollectionInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise DatasetCollectionInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise DatasetCollectionInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise DatasetCollectionInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise DatasetCollectionInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_collection_occurred_at(raw):
    value = _admit_collection_identifier(raw, "collection occurrence time")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise DatasetCollectionInputError("a collection occurrence time is longer than admitted")
    if len(value) < 20 or value[10:11] != "T":
        raise DatasetCollectionInputError(
            "a collection occurrence time must be an ISO instant with zone"
        )
    return value


def _recorded_payload_digest(store, workspace_id, item):
    binding = ObjectBinding(
        workspace_id=workspace_id,
        object_id=item.object_id,
        object_type=item.object_kind,
        object_revision=item.object_revision,
    )
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ExportStagingInputError("an export source is not present in this store") from error
    return content_digest_of(raw)


def _items_section(items, digests):
    return [
        {
            "object_id": str(item.object_id),
            "object_kind": item.object_kind.value,
            "object_revision": item.object_revision,
            "payload_digest": digest,
        }
        for item, digest in zip(items, digests, strict=True)
    ]


def _export_item_from_document(document):
    if not isinstance(document, dict):
        raise ExportStagingInputError("a stored export item must be a JSON object")
    if set(document) != {"object_id", "object_kind", "object_revision", "payload_digest"}:
        raise ExportStagingInputError("a stored export item carries unadmitted members")
    try:
        object_id = UUID(str(document["object_id"]))
    except ValueError as error:
        raise ExportStagingInputError("a stored export source identity is not admitted") from error
    return ExportSourceDescriptor(
        object_id=object_id,
        object_kind=_admit_source_kind(
            _string_member(document, "object_kind", ExportStagingInputError)
        ),
        object_revision=_string_member(document, "object_revision", ExportStagingInputError),
    ).validated()


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name, error_class):
    value = document[name]
    if not isinstance(value, str):
        raise error_class(f"a stored {name} must be a string")
    return value
