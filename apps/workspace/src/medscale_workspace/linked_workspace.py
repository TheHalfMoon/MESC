"""Linked document/table/graph workspace for CW-012.

Documents, tables, graph objects, and timeline projections link to each other
through stable object identities. A link is derived state over admitted
members: both endpoints must exist, be current, and belong to the same
workspace, and every link carries its own corpus source references. Links never
become a backdoor for Research Core admission: research references are opaque
read-only strings that are never resolved, never fetched, and never cross the
no-backflow guard.

No donor schema is vendored. The document/table/link vocabulary below is
MedScale-owned and minimal; interaction principles may be studied elsewhere,
but no external tree is imported. Any future direct reuse needs file-level
license analysis with an exact path/revision/license record.

Linked content is data, not authority. Titles, sections, cells, and keys are
stored verbatim, never evaluated, never executed, and never consulted for
capability, policy, or governance decisions. Malicious strings remain inert.

No network, retrieval-connector, model, or execution capability exists in this
module, and none may be added under this unit. Research Core machinery belongs
to a different trust domain and is deliberately not imported here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace import corpus as corpus_mod
from medscale_workspace import patient_graph as graph_mod
from medscale_workspace.audit import AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    GraphInputError,
    GraphStaleError,
    LinkedConflictError,
    LinkedInputError,
    LinkedRevisionError,
    LinkedStaleError,
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
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

DOCUMENT_NAMESPACE = UUID("c012d0c0-0001-4000-8000-000000000012")
TABLE_NAMESPACE = UUID("c0127ab1-0002-4000-8000-000000000012")
LINK_NAMESPACE = UUID("c01211c0-0003-4000-8000-000000000012")
DOCUMENT_REVISION = "linked-document-00000001"
TABLE_REVISION = "linked-table-00000001"
LINK_REVISION = "workspace-link-00000001"
PRODUCER_VERSION = "cw012-v1"
DERIVATION_METHOD = "cw012-deterministic-linking"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw012-linked-workspace/1"
LINK_SCHEMA_VERSION = 1
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_KEY_CHARS = 128
MAXIMUM_TITLE_CHARS = 256
MAXIMUM_SECTIONS = 32
MAXIMUM_SECTION_CHARS = 1024
MAXIMUM_COLUMNS = 16
MAXIMUM_COLUMN_CHARS = 64
MAXIMUM_ROWS = 128
MAXIMUM_CELL_CHARS = 256
MAXIMUM_RESEARCH_REFS = 8
MAXIMUM_SOURCES_PER_LINK = 8
MAXIMUM_OCCURRED_AT_CHARS = 64


class LinkKind(StrEnum):
    """Admitted relationship between two linked workspace members."""

    CONTAINS = "contains"
    REFERENCES = "references"
    DERIVED_FROM = "derived_from"
    ATTACHED_TO = "attached_to"
    TIMELINE_ENTRY = "timeline_entry"


class LinkedMemberType(StrEnum):
    """Admitted member classes a workspace link may bind."""

    LINKED_DOCUMENT = "linked_document"
    LINKED_TABLE = "linked_table"
    GRAPH_NODE = "graph_node"
    GRAPH_EDGE = "graph_edge"
    GRAPH_VIEW = "graph_view"


_MEMBER_OBJECT_TYPES = {
    LinkedMemberType.LINKED_DOCUMENT: WorkspaceObjectType.LINKED_DOCUMENT,
    LinkedMemberType.LINKED_TABLE: WorkspaceObjectType.LINKED_TABLE,
    LinkedMemberType.GRAPH_NODE: WorkspaceObjectType.GRAPH_NODE,
    LinkedMemberType.GRAPH_EDGE: WorkspaceObjectType.GRAPH_EDGE,
    LinkedMemberType.GRAPH_VIEW: WorkspaceObjectType.GRAPH_VIEW,
}


@dataclass(frozen=True, slots=True)
class ResearchRef:
    """One opaque read-only reference to a Research Core artifact.

    The reference is never resolved, never fetched, and never admitted as a
    workspace source. It names an artifact so a linked object can cite what it
    was viewed against; the no-backflow guard keeps the direction read-only.
    """

    artifact_id: str
    artifact_version: str

    def validated(self):
        artifact_id = _admit_identifier(self.artifact_id, "artifact id")
        artifact_version = _admit_identifier(self.artifact_version, "artifact version")
        return ResearchRef(artifact_id=artifact_id, artifact_version=artifact_version)

    def to_document(self):
        admitted = self.validated()
        return {
            "artifact_id": admitted.artifact_id,
            "artifact_version": admitted.artifact_version,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored research reference must be a JSON object")
        expected = {"artifact_id", "artifact_version"}
        if set(document) != expected:
            raise LinkedInputError("a stored research reference carries unadmitted members")
        return ResearchRef(
            artifact_id=_string_member(document, "artifact_id"),
            artifact_version=_string_member(document, "artifact_version"),
        ).validated()


@dataclass(frozen=True, slots=True)
class LinkedDocument:
    """One derived workspace document bound to one corpus source revision."""

    workspace_id: UUID
    document_id: UUID
    document_key: str
    title: str
    sections: tuple
    source_id: UUID
    source_revision: str
    content_digest: str
    research_refs: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise LinkedInputError("a workspace id must be a UUID value")
        if not isinstance(self.document_id, UUID):
            raise LinkedInputError("a document id must be a UUID value")
        document_key = _admit_key(self.document_key, "document key")
        title = _admit_title(self.title)
        if not isinstance(self.sections, tuple) or not self.sections:
            raise LinkedInputError("a document needs a non-empty tuple of sections")
        if len(self.sections) > MAXIMUM_SECTIONS:
            raise LinkedInputError("a document carries an unadmitted section count")
        checked_sections = tuple(_admit_section(item) for item in self.sections)
        if not isinstance(self.source_id, UUID):
            raise LinkedInputError("a document source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision")
        digest = _admit_digest(self.content_digest)
        refs = _validated_research_refs(self.research_refs)
        expected = document_id_for(self.workspace_id, document_key, revision)
        if self.document_id != expected:
            raise LinkedRevisionError("a document identity does not match its lineage")
        return LinkedDocument(
            workspace_id=self.workspace_id,
            document_id=self.document_id,
            document_key=document_key,
            title=title,
            sections=checked_sections,
            source_id=self.source_id,
            source_revision=revision,
            content_digest=digest,
            research_refs=refs,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "data_class": synthetic_data_class_value(),
            "document_id": str(admitted.document_id),
            "document_key": admitted.document_key,
            "policy_version": POLICY_VERSION,
            "research_refs": [item.to_document() for item in admitted.research_refs],
            "schema_version": SCHEMA_VERSION,
            "sections": list(admitted.sections),
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "title": admitted.title,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored document must be a JSON object")
        expected = {
            "content_digest",
            "data_class",
            "document_id",
            "document_key",
            "policy_version",
            "research_refs",
            "schema_version",
            "sections",
            "source_id",
            "source_revision",
            "title",
            "workspace_id",
        }
        if set(document) != expected:
            raise LinkedInputError("a stored document carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise LinkedInputError("a stored document data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise LinkedInputError("a stored document policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise LinkedInputError("a stored document schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            document_id = UUID(str(document["document_id"]))
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise LinkedInputError("a stored document identity is not admitted") from error
        raw_sections = document["sections"]
        if not isinstance(raw_sections, list):
            raise LinkedInputError("stored document sections must be a JSON array")
        raw_refs = document["research_refs"]
        if not isinstance(raw_refs, list):
            raise LinkedInputError("stored research references must be a JSON array")
        return LinkedDocument(
            workspace_id=workspace_id,
            document_id=document_id,
            document_key=_string_member(document, "document_key"),
            title=_string_member(document, "title"),
            sections=tuple(_string_member_value(item) for item in raw_sections),
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
            research_refs=tuple(ResearchRef.from_document(item) for item in raw_refs),
        ).validated()


@dataclass(frozen=True, slots=True)
class LinkedTable:
    """One derived workspace table bound to one corpus source revision."""

    workspace_id: UUID
    table_id: UUID
    table_key: str
    title: str
    columns: tuple
    rows: tuple
    source_id: UUID
    source_revision: str
    content_digest: str
    research_refs: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise LinkedInputError("a workspace id must be a UUID value")
        if not isinstance(self.table_id, UUID):
            raise LinkedInputError("a table id must be a UUID value")
        table_key = _admit_key(self.table_key, "table key")
        title = _admit_title(self.title)
        if not isinstance(self.columns, tuple) or not self.columns:
            raise LinkedInputError("a table needs a non-empty tuple of columns")
        if len(self.columns) > MAXIMUM_COLUMNS:
            raise LinkedInputError("a table carries an unadmitted column count")
        checked_columns = tuple(_admit_column(item) for item in self.columns)
        if len(set(checked_columns)) != len(checked_columns):
            raise LinkedInputError("a table carries a duplicated column name")
        if not isinstance(self.rows, tuple):
            raise LinkedInputError("table rows must be a tuple")
        if len(self.rows) > MAXIMUM_ROWS:
            raise LinkedInputError("a table carries an unadmitted row count")
        checked_rows = tuple(_validated_row(item, len(checked_columns)) for item in self.rows)
        if not isinstance(self.source_id, UUID):
            raise LinkedInputError("a table source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision")
        digest = _admit_digest(self.content_digest)
        refs = _validated_research_refs(self.research_refs)
        expected = table_id_for(self.workspace_id, table_key, revision)
        if self.table_id != expected:
            raise LinkedRevisionError("a table identity does not match its lineage")
        return LinkedTable(
            workspace_id=self.workspace_id,
            table_id=self.table_id,
            table_key=table_key,
            title=title,
            columns=checked_columns,
            rows=checked_rows,
            source_id=self.source_id,
            source_revision=revision,
            content_digest=digest,
            research_refs=refs,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "columns": list(admitted.columns),
            "content_digest": admitted.content_digest,
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
            "research_refs": [item.to_document() for item in admitted.research_refs],
            "rows": [list(row) for row in admitted.rows],
            "schema_version": SCHEMA_VERSION,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "table_id": str(admitted.table_id),
            "table_key": admitted.table_key,
            "title": admitted.title,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored table must be a JSON object")
        expected = {
            "columns",
            "content_digest",
            "data_class",
            "policy_version",
            "research_refs",
            "rows",
            "schema_version",
            "source_id",
            "source_revision",
            "table_id",
            "table_key",
            "title",
            "workspace_id",
        }
        if set(document) != expected:
            raise LinkedInputError("a stored table carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise LinkedInputError("a stored table data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise LinkedInputError("a stored table policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise LinkedInputError("a stored table schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            table_id = UUID(str(document["table_id"]))
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise LinkedInputError("a stored table identity is not admitted") from error
        raw_columns = document["columns"]
        raw_rows = document["rows"]
        if not isinstance(raw_columns, list) or not isinstance(raw_rows, list):
            raise LinkedInputError("stored table columns and rows must be JSON arrays")
        raw_refs = document["research_refs"]
        if not isinstance(raw_refs, list):
            raise LinkedInputError("stored research references must be a JSON array")
        rows = tuple(
            tuple(_string_member_value(cell) for cell in row)
            if isinstance(row, list)
            else _reject_table_row()
            for row in raw_rows
        )
        return LinkedTable(
            workspace_id=workspace_id,
            table_id=table_id,
            table_key=_string_member(document, "table_key"),
            title=_string_member(document, "title"),
            columns=tuple(_string_member_value(item) for item in raw_columns),
            rows=rows,
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
            research_refs=tuple(ResearchRef.from_document(item) for item in raw_refs),
        ).validated()


@dataclass(frozen=True, slots=True)
class MemberRef:
    """One stable reference to a linked workspace member."""

    member_type: LinkedMemberType
    member_id: UUID

    def validated(self):
        if not isinstance(self.member_type, LinkedMemberType):
            raise LinkedInputError("a member type is not admitted here")
        if not isinstance(self.member_id, UUID):
            raise LinkedInputError("a member id must be a UUID value")
        return MemberRef(member_type=self.member_type, member_id=self.member_id)

    def to_document(self):
        admitted = self.validated()
        return {"member_id": str(admitted.member_id), "member_type": admitted.member_type.value}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored member reference must be a JSON object")
        expected = {"member_id", "member_type"}
        if set(document) != expected:
            raise LinkedInputError("a stored member reference carries unadmitted members")
        try:
            member_id = UUID(str(document["member_id"]))
            member_type = LinkedMemberType(str(document["member_type"]))
        except ValueError as error:
            raise LinkedInputError("a stored member reference is not admitted") from error
        return MemberRef(member_type=member_type, member_id=member_id).validated()


@dataclass(frozen=True, slots=True)
class LinkSource:
    """One admitted corpus source revision bound into a workspace link."""

    source_id: UUID
    source_revision: str
    content_digest: str

    def validated(self):
        if not isinstance(self.source_id, UUID):
            raise LinkedInputError("a link source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision")
        digest = _admit_digest(self.content_digest)
        return LinkSource(source_id=self.source_id, source_revision=revision, content_digest=digest)

    def to_document(self):
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored link source must be a JSON object")
        expected = {"content_digest", "source_id", "source_revision"}
        if set(document) != expected:
            raise LinkedInputError("a stored link source carries unadmitted members")
        try:
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise LinkedInputError("a stored link source id is not admitted") from error
        return LinkSource(
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class WorkspaceLink:
    """One derived link between two workspace members with its own sources."""

    workspace_id: UUID
    link_id: UUID
    source_member: MemberRef
    target_member: MemberRef
    link_kind: LinkKind
    sources: tuple
    derivation_method: str
    derivation_version: str
    link_schema_version: int

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise LinkedInputError("a workspace id must be a UUID value")
        if not isinstance(self.link_id, UUID):
            raise LinkedInputError("a link id must be a UUID value")
        if not isinstance(self.source_member, MemberRef):
            raise LinkedInputError("a link source member must be a MemberRef")
        if not isinstance(self.target_member, MemberRef):
            raise LinkedInputError("a link target member must be a MemberRef")
        source_member = self.source_member.validated()
        target_member = self.target_member.validated()
        if source_member == target_member:
            raise LinkedInputError("a link must connect two distinct members")
        if not isinstance(self.link_kind, LinkKind):
            raise LinkedInputError("a link kind is not admitted here")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise LinkedInputError("a link needs a non-empty tuple of sources")
        if len(self.sources) > MAXIMUM_SOURCES_PER_LINK:
            raise LinkedInputError("a link carries an unadmitted source count")
        checked = tuple(
            item.validated() if isinstance(item, LinkSource) else None for item in self.sources
        )
        if any(item is None for item in checked):
            raise LinkedInputError("link sources need LinkSource instances")
        seen = set()
        for item in checked:
            if item.source_id in seen:
                raise LinkedInputError("a link carries a duplicated source id")
            seen.add(item.source_id)
        method = _admit_identifier(self.derivation_method, "derivation method")
        if method != DERIVATION_METHOD:
            raise LinkedInputError("a link derivation method is not admitted here")
        version = _admit_identifier(self.derivation_version, "derivation version")
        if version != DERIVATION_METHOD_VERSION:
            raise LinkedInputError("a link derivation version is not admitted here")
        schema = self.link_schema_version
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise LinkedInputError("a link schema version must be an integer")
        if schema != LINK_SCHEMA_VERSION:
            raise LinkedInputError("a link schema version is not supported here")
        ordered = tuple(sorted(checked, key=lambda item: str(item.source_id)))
        expected = link_id_for(
            self.workspace_id,
            source_member,
            target_member,
            self.link_kind,
            ordered,
            method,
            version,
        )
        if self.link_id != expected:
            raise LinkedRevisionError("a link identity does not match its bindings")
        return WorkspaceLink(
            workspace_id=self.workspace_id,
            link_id=self.link_id,
            source_member=source_member,
            target_member=target_member,
            link_kind=self.link_kind,
            sources=ordered,
            derivation_method=method,
            derivation_version=version,
            link_schema_version=schema,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "derivation_method": admitted.derivation_method,
            "derivation_version": admitted.derivation_version,
            "link_id": str(admitted.link_id),
            "link_kind": admitted.link_kind.value,
            "link_schema_version": admitted.link_schema_version,
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "source_member": admitted.source_member.to_document(),
            "sources": [item.to_document() for item in admitted.sources],
            "target_member": admitted.target_member.to_document(),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkedInputError("a stored link must be a JSON object")
        expected = {
            "data_class",
            "derivation_method",
            "derivation_version",
            "link_id",
            "link_kind",
            "link_schema_version",
            "policy_version",
            "schema_version",
            "source_member",
            "sources",
            "target_member",
            "workspace_id",
        }
        if set(document) != expected:
            raise LinkedInputError("a stored link carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise LinkedInputError("a stored link data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise LinkedInputError("a stored link policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise LinkedInputError("a stored link schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            link_id = UUID(str(document["link_id"]))
            link_kind = LinkKind(str(document["link_kind"]))
        except ValueError as error:
            raise LinkedInputError("a stored link identity is not admitted") from error
        raw_sources = document["sources"]
        if not isinstance(raw_sources, list):
            raise LinkedInputError("stored link sources must be a JSON array")
        schema = document["link_schema_version"]
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise LinkedInputError("a stored link schema version must be an integer")
        return WorkspaceLink(
            workspace_id=workspace_id,
            link_id=link_id,
            source_member=MemberRef.from_document(document["source_member"]),
            target_member=MemberRef.from_document(document["target_member"]),
            link_kind=link_kind,
            sources=tuple(LinkSource.from_document(item) for item in raw_sources),
            derivation_method=_string_member(document, "derivation_method"),
            derivation_version=_string_member(document, "derivation_version"),
            link_schema_version=schema,
        ).validated()


def document_id_for(workspace_id, document_key, source_revision):
    """Return the deterministic identity of one linked document."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    key = _admit_key(document_key, "document key")
    revision = _admit_identifier(source_revision, "source revision")
    return uuid5(DOCUMENT_NAMESPACE, ":".join((str(workspace_id), key, revision)))


def table_id_for(workspace_id, table_key, source_revision):
    """Return the deterministic identity of one linked table."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    key = _admit_key(table_key, "table key")
    revision = _admit_identifier(source_revision, "source revision")
    return uuid5(TABLE_NAMESPACE, ":".join((str(workspace_id), key, revision)))


def link_id_for(workspace_id, source_member, target_member, link_kind, sources, method, version):
    """Return the deterministic identity of one workspace link."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if not isinstance(source_member, MemberRef):
        raise LinkedInputError("a link source member must be a MemberRef")
    if not isinstance(target_member, MemberRef):
        raise LinkedInputError("a link target member must be a MemberRef")
    source_member = source_member.validated()
    target_member = target_member.validated()
    if not isinstance(link_kind, LinkKind):
        raise LinkedInputError("a link kind is not admitted here")
    if not isinstance(sources, tuple) or not sources:
        raise LinkedInputError("a link needs a non-empty tuple of sources")
    checked = tuple(item.validated() if isinstance(item, LinkSource) else None for item in sources)
    if any(item is None for item in checked):
        raise LinkedInputError("link sources need LinkSource instances")
    ordered = tuple(sorted(checked, key=lambda item: str(item.source_id)))
    method = _admit_identifier(method, "derivation method")
    version = _admit_identifier(version, "derivation version")
    lines = "\n".join(
        ":".join((str(item.source_id), item.source_revision, item.content_digest))
        for item in ordered
    )
    return uuid5(
        LINK_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                source_member.member_type.value,
                str(source_member.member_id),
                target_member.member_type.value,
                str(target_member.member_id),
                link_kind.value,
                lines,
                method,
                version,
            )
        ),
    )


def document_binding(workspace_id, document_id):
    """Return the store binding of one linked document."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if not isinstance(document_id, UUID):
        raise LinkedInputError("a document id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=document_id,
        object_type=WorkspaceObjectType.LINKED_DOCUMENT,
        object_revision=DOCUMENT_REVISION,
    )


def table_binding(workspace_id, table_id):
    """Return the store binding of one linked table."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if not isinstance(table_id, UUID):
        raise LinkedInputError("a table id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=table_id,
        object_type=WorkspaceObjectType.LINKED_TABLE,
        object_revision=TABLE_REVISION,
    )


def link_binding(workspace_id, link_id):
    """Return the store binding of one workspace link."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if not isinstance(link_id, UUID):
        raise LinkedInputError("a link id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=link_id,
        object_type=WorkspaceObjectType.WORKSPACE_LINK,
        object_revision=LINK_REVISION,
    )


def member_binding(workspace_id, member):
    """Return the store binding of one linked member."""
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if not isinstance(member, MemberRef):
        raise LinkedInputError("a member reference must be a MemberRef")
    member = member.validated()
    if member.member_type is LinkedMemberType.LINKED_DOCUMENT:
        return document_binding(workspace_id, member.member_id)
    if member.member_type is LinkedMemberType.LINKED_TABLE:
        return table_binding(workspace_id, member.member_id)
    if member.member_type is LinkedMemberType.GRAPH_NODE:
        revision = graph_mod.NODE_REVISION
    elif member.member_type is LinkedMemberType.GRAPH_EDGE:
        revision = graph_mod.EDGE_REVISION
    else:
        revision = graph_mod.VIEW_REVISION
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=member.member_id,
        object_type=_MEMBER_OBJECT_TYPES[member.member_type],
        object_revision=revision,
    )


def admit_document(
    store,
    trail,
    workspace_id,
    document_key,
    title,
    sections,
    source_id,
    actor_id,
    occurred_at,
    research_refs=(),
):
    """Admit one derived workspace document bound to one corpus source."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkedInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a linked document crossed the workspace boundary")
    key = _admit_key(document_key, "document key")
    admitted_title = _admit_title(title)
    if not isinstance(sections, tuple) or not sections:
        raise LinkedInputError("a document needs a non-empty tuple of sections")
    if not isinstance(source_id, UUID):
        raise LinkedInputError("a document source id must be a UUID value")
    refs = _validated_research_refs(research_refs)
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        source = corpus_mod.read_source(store, source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkedRevisionError("the document source is absent in this store") from error
    document = LinkedDocument(
        workspace_id=workspace_id,
        document_id=document_id_for(workspace_id, key, source.source_revision),
        document_key=key,
        title=admitted_title,
        sections=tuple(_admit_section(item) for item in sections),
        source_id=source.source_id,
        source_revision=source.source_revision,
        content_digest=source.content_digest,
        research_refs=refs,
    ).validated()
    binding = document_binding(workspace_id, document.document_id)
    payload = _canonical_bytes(document.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(document.source_id),
                source_revision=document.source_revision,
                locator=None,
            ),
        ),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise LinkedConflictError("the linked document identity already exists") from error
    trail.record_object_write(binding=binding, payload=payload, actor_id=actor, occurred_at=moment)
    return binding


def read_document(store, document_id):
    """Read and verify one stored document with its source still current."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(document_id, UUID):
        raise LinkedInputError("a document id must be a UUID value")
    binding = document_binding(store.workspace_id, document_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkedInputError("the document identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise LinkedInputError("a stored document is not ASCII JSON") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LinkedInputError("a stored document is not JSON") from error
    document = LinkedDocument.from_document(payload)
    if document.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a linked document crossed the workspace boundary")
    if document.document_id != document_id:
        raise LinkedInputError("a stored document identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    try:
        source = corpus_mod.read_source(store, document.source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkedStaleError("a document source is no longer present") from error
    if source.source_revision != document.source_revision:
        raise LinkedStaleError("a document source revision no longer matches")
    if source.content_digest != document.content_digest:
        raise LinkedStaleError("a document source digest no longer matches")
    return document.validated()


def admit_table(
    store,
    trail,
    workspace_id,
    table_key,
    title,
    columns,
    rows,
    source_id,
    actor_id,
    occurred_at,
    research_refs=(),
):
    """Admit one derived workspace table bound to one corpus source."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkedInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a linked table crossed the workspace boundary")
    key = _admit_key(table_key, "table key")
    admitted_title = _admit_title(title)
    if not isinstance(columns, tuple) or not columns:
        raise LinkedInputError("a table needs a non-empty tuple of columns")
    if not isinstance(rows, tuple):
        raise LinkedInputError("table rows must be a tuple")
    if not isinstance(source_id, UUID):
        raise LinkedInputError("a table source id must be a UUID value")
    refs = _validated_research_refs(research_refs)
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        source = corpus_mod.read_source(store, source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkedRevisionError("the table source is absent in this store") from error
    checked_columns = tuple(_admit_column(item) for item in columns)
    table = LinkedTable(
        workspace_id=workspace_id,
        table_id=table_id_for(workspace_id, key, source.source_revision),
        table_key=key,
        title=admitted_title,
        columns=checked_columns,
        rows=tuple(_validated_row(item, len(checked_columns)) for item in rows),
        source_id=source.source_id,
        source_revision=source.source_revision,
        content_digest=source.content_digest,
        research_refs=refs,
    ).validated()
    binding = table_binding(workspace_id, table.table_id)
    payload = _canonical_bytes(table.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(table.source_id),
                source_revision=table.source_revision,
                locator=None,
            ),
        ),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise LinkedConflictError("the linked table identity already exists") from error
    trail.record_object_write(binding=binding, payload=payload, actor_id=actor, occurred_at=moment)
    return binding


def read_table(store, table_id):
    """Read and verify one stored table with its source still current."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(table_id, UUID):
        raise LinkedInputError("a table id must be a UUID value")
    binding = table_binding(store.workspace_id, table_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkedInputError("the table identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise LinkedInputError("a stored table is not ASCII JSON") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LinkedInputError("a stored table is not JSON") from error
    table = LinkedTable.from_document(payload)
    if table.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a linked table crossed the workspace boundary")
    if table.table_id != table_id:
        raise LinkedInputError("a stored table identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    try:
        source = corpus_mod.read_source(store, table.source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkedStaleError("a table source is no longer present") from error
    if source.source_revision != table.source_revision:
        raise LinkedStaleError("a table source revision no longer matches")
    if source.content_digest != table.content_digest:
        raise LinkedStaleError("a table source digest no longer matches")
    return table.validated()


def verify_member(store, member):
    """Verify one linked member is present and current, returning its binding."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(member, MemberRef):
        raise LinkedInputError("a member reference must be a MemberRef")
    member = member.validated()
    if member.member_type is LinkedMemberType.LINKED_DOCUMENT:
        try:
            read_document(store, member.member_id)
        except LinkedStaleError as error:
            raise LinkedStaleError("a linked member is stale") from error
        return document_binding(store.workspace_id, member.member_id)
    if member.member_type is LinkedMemberType.LINKED_TABLE:
        try:
            read_table(store, member.member_id)
        except LinkedStaleError as error:
            raise LinkedStaleError("a linked member is stale") from error
        return table_binding(store.workspace_id, member.member_id)
    try:
        _read_graph_member(store, member)
    except GraphStaleError as error:
        raise LinkedStaleError("a linked member is stale") from error
    except GraphInputError as error:
        raise LinkedRevisionError("a linked member is absent") from error
    return member_binding(store.workspace_id, member)


def admit_link(
    store,
    trail,
    workspace_id,
    source_member,
    target_member,
    link_kind,
    source_ids,
    actor_id,
    occurred_at,
):
    """Admit one derived link between two current workspace members."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkedInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise LinkedInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a workspace link crossed the workspace boundary")
    if not isinstance(source_member, MemberRef):
        raise LinkedInputError("a link source member must be a MemberRef")
    if not isinstance(target_member, MemberRef):
        raise LinkedInputError("a link target member must be a MemberRef")
    source_member = source_member.validated()
    target_member = target_member.validated()
    if not isinstance(link_kind, LinkKind):
        raise LinkedInputError("a link kind is not admitted here")
    if not isinstance(source_ids, tuple) or not source_ids:
        raise LinkedInputError("a link needs a non-empty tuple of source ids")
    if len(source_ids) > MAXIMUM_SOURCES_PER_LINK:
        raise LinkedInputError("a link carries an unadmitted source count")
    for source_id in source_ids:
        if not isinstance(source_id, UUID):
            raise LinkedInputError("a link source id must be a UUID value")
    if len(set(source_ids)) != len(source_ids):
        raise LinkedInputError("a link carries a duplicated source id")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        verify_member(store, source_member)
    except LinkedStaleError as error:
        raise LinkedRevisionError("a link endpoint member is stale") from error
    except LinkedInputError as error:
        raise LinkedRevisionError("a link endpoint member is absent") from error
    try:
        verify_member(store, target_member)
    except LinkedStaleError as error:
        raise LinkedRevisionError("a link endpoint member is stale") from error
    except LinkedInputError as error:
        raise LinkedRevisionError("a link endpoint member is absent") from error
    bound = []
    for source_id in source_ids:
        try:
            source = corpus_mod.read_source(store, source_id)
        except corpus_mod.CorpusInputError as error:
            raise LinkedRevisionError("a link source is absent in this store") from error
        bound.append(
            LinkSource(
                source_id=source.source_id,
                source_revision=source.source_revision,
                content_digest=source.content_digest,
            ).validated()
        )
    ordered = tuple(sorted(bound, key=lambda item: str(item.source_id)))
    link = WorkspaceLink(
        workspace_id=workspace_id,
        link_id=link_id_for(
            workspace_id,
            source_member,
            target_member,
            link_kind,
            ordered,
            DERIVATION_METHOD,
            DERIVATION_METHOD_VERSION,
        ),
        source_member=source_member,
        target_member=target_member,
        link_kind=link_kind,
        sources=ordered,
        derivation_method=DERIVATION_METHOD,
        derivation_version=DERIVATION_METHOD_VERSION,
        link_schema_version=LINK_SCHEMA_VERSION,
    ).validated()
    binding = link_binding(workspace_id, link.link_id)
    payload = _canonical_bytes(link.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    refs = tuple(
        SourceRef(
            kind=SourceKind.EVIDENCE_SOURCE,
            source_id=str(item.source_id),
            source_revision=item.source_revision,
            locator=None,
        )
        for item in link.sources
    )
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise LinkedConflictError("the workspace link identity already exists") from error
    trail.record_object_write(binding=binding, payload=payload, actor_id=actor, occurred_at=moment)
    return binding


def read_link(store, link_id):
    """Read and verify one stored link with members and sources current."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(link_id, UUID):
        raise LinkedInputError("a link id must be a UUID value")
    binding = link_binding(store.workspace_id, link_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkedInputError("the link identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise LinkedInputError("a stored link is not ASCII JSON") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise LinkedInputError("a stored link is not JSON") from error
    link = WorkspaceLink.from_document(payload)
    if link.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a workspace link crossed the workspace boundary")
    if link.link_id != link_id:
        raise LinkedInputError("a stored link identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    try:
        verify_member(store, link.source_member)
    except LinkedInputError as error:
        raise LinkedStaleError("a link endpoint member is no longer present") from error
    try:
        verify_member(store, link.target_member)
    except LinkedInputError as error:
        raise LinkedStaleError("a link endpoint member is no longer present") from error
    for bound in link.sources:
        try:
            source = corpus_mod.read_source(store, bound.source_id)
        except corpus_mod.CorpusInputError as error:
            raise LinkedStaleError("a link source is no longer present") from error
        if source.source_revision != bound.source_revision:
            raise LinkedStaleError("a link source revision no longer matches")
        if source.content_digest != bound.content_digest:
            raise LinkedStaleError("a link source digest no longer matches")
    return link.validated()


def resolve_link(store, link_id):
    """Resolve one link to its verified endpoints, failing closed on staleness."""
    link = read_link(store, link_id)
    verify_member(store, link.source_member)
    verify_member(store, link.target_member)
    return link


def links_for_member(store, member):
    """List current link identities touching one member, in sorted order."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(member, MemberRef):
        raise LinkedInputError("a member reference must be a MemberRef")
    member = member.validated()
    revisions = store.object_revisions(WorkspaceObjectType.WORKSPACE_LINK)
    found = []
    for link_id, _revision in sorted(revisions, key=lambda item: str(item[0])):
        try:
            link = read_link(store, link_id)
        except (LinkedInputError, LinkedStaleError):
            continue
        if link.source_member == member or link.target_member == member:
            found.append(link.link_id)
    return tuple(sorted(found, key=str))


def delete_link(store, trail, link_id, actor_id, occurred_at):
    """Delete one link revision and its provenance while keeping audit events."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkedInputError("an audit trail is required")
    if not isinstance(link_id, UUID):
        raise LinkedInputError("a link id must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    binding = link_binding(store.workspace_id, link_id)
    try:
        store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkedInputError("the link identity is not present") from error
    removed = 0
    for target in (binding, provenance_binding_for(binding)):
        try:
            trail.record_object_deletion(binding=target, actor_id=actor, occurred_at=moment)
            removed += 1
        except ObjectNotFoundError:
            continue
    return removed


def delete_member(store, trail, member, actor_id, occurred_at):
    """Delete one member, its incident links, and their provenance records."""
    if not isinstance(store, WorkspaceStore):
        raise LinkedInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkedInputError("an audit trail is required")
    if not isinstance(member, MemberRef):
        raise LinkedInputError("a member reference must be a MemberRef")
    member = member.validated()
    if member.member_type not in (
        LinkedMemberType.LINKED_DOCUMENT,
        LinkedMemberType.LINKED_TABLE,
    ):
        raise LinkedInputError("only workspace-owned members are deleted here")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    binding = member_binding(store.workspace_id, member)
    try:
        store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkedInputError("the member identity is not present") from error
    removed = 0
    for link_id in links_for_member(store, member):
        removed += delete_link(store, trail, link_id, actor, moment)
    for target in (binding, provenance_binding_for(binding)):
        try:
            trail.record_object_deletion(binding=target, actor_id=actor, occurred_at=moment)
            removed += 1
        except ObjectNotFoundError:
            continue
    return removed


def _read_graph_member(store, member):
    if member.member_type is LinkedMemberType.GRAPH_NODE:
        return graph_mod.read_node(store, member.member_id)
    if member.member_type is LinkedMemberType.GRAPH_EDGE:
        return graph_mod.read_edge(store, member.member_id)
    return graph_mod.read_view(store, member.member_id)


def _validated_research_refs(raw):
    if not isinstance(raw, tuple):
        raise LinkedInputError("research references must be a tuple")
    if len(raw) > MAXIMUM_RESEARCH_REFS:
        raise LinkedInputError("a member carries an unadmitted research reference count")
    checked = tuple(item.validated() if isinstance(item, ResearchRef) else None for item in raw)
    if any(item is None for item in checked):
        raise LinkedInputError("research references need ResearchRef instances")
    seen = set()
    for item in checked:
        key = (item.artifact_id, item.artifact_version)
        if key in seen:
            raise LinkedInputError("a member carries a duplicated research reference")
        seen.add(key)
    return checked


def _validated_row(raw, width):
    if not isinstance(raw, tuple):
        raise LinkedInputError("a table row must be a tuple")
    if len(raw) != width:
        raise LinkedInputError("a table row width must match its columns")
    return tuple(_admit_cell(item) for item in raw)


def _reject_table_row():
    raise LinkedInputError("a table row must be a JSON array")


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise LinkedInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise LinkedInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise LinkedInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise LinkedInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_key(raw, label):
    if not isinstance(raw, str):
        raise LinkedInputError(f"a {label} must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError(f"a {label} must be non-empty")
    if len(value) > MAXIMUM_KEY_CHARS:
        raise LinkedInputError(f"a {label} is longer than the admitted maximum")
    if not value.isascii():
        raise LinkedInputError(f"a {label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise LinkedInputError(f"a {label} must not contain whitespace or controls")
    return value


def _admit_title(raw):
    if not isinstance(raw, str):
        raise LinkedInputError("a title must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError("a title must be non-empty")
    if len(value) > MAXIMUM_TITLE_CHARS:
        raise LinkedInputError("a title is longer than the admitted maximum")
    if not value.isascii():
        raise LinkedInputError("a title must be ASCII")
    for character in value:
        if not character.isprintable() and character not in (" ",):
            raise LinkedInputError("a title must not contain control characters")
    return " ".join(value.split())


def _admit_section(raw):
    if not isinstance(raw, str):
        raise LinkedInputError("a section must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError("a section must be non-empty")
    if len(value) > MAXIMUM_SECTION_CHARS:
        raise LinkedInputError("a section is longer than the admitted maximum")
    if not value.isascii():
        raise LinkedInputError("a section must be ASCII")
    for character in value:
        if character in ("\n", "\t"):
            continue
        if not character.isprintable():
            raise LinkedInputError("a section must not contain control characters")
    return value


def _admit_column(raw):
    if not isinstance(raw, str):
        raise LinkedInputError("a column name must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError("a column name must be non-empty")
    if len(value) > MAXIMUM_COLUMN_CHARS:
        raise LinkedInputError("a column name is longer than the admitted maximum")
    if not value.isascii():
        raise LinkedInputError("a column name must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise LinkedInputError("a column name must not contain whitespace or controls")
    return value


def _admit_cell(raw):
    if not isinstance(raw, str):
        raise LinkedInputError("a cell must be a string")
    value = raw.strip()
    if len(value) > MAXIMUM_CELL_CHARS:
        raise LinkedInputError("a cell is longer than the admitted maximum")
    if value and not value.isascii():
        raise LinkedInputError("a cell must be ASCII")
    for character in value:
        if not character.isprintable():
            raise LinkedInputError("a cell must not contain control characters")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise LinkedInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise LinkedInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise LinkedInputError("a linked occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise LinkedInputError("a linked occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise LinkedInputError("a linked occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise LinkedInputError("a linked occurrence time must be an ISO-8601 instant")
    if not value.isascii():
        raise LinkedInputError("a linked occurrence time must be ASCII")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise LinkedInputError(f"a stored {name} must be a string")
    return value


def _string_member_value(value):
    if not isinstance(value, str):
        raise LinkedInputError("a stored text member must be a string")
    return value
