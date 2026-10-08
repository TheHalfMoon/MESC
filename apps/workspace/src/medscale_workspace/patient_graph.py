"""Longitudinal patient graph and timeline for CW-011.

The graph is derived state, not an independent clinical truth store. Source
objects remain authoritative. Every node binds one admitted synthetic corpus
source revision; every edge binds two admitted nodes, a relationship type, a
mandatory epistemic state, and one or more admitted corpus source revisions.
A frozen graph view binds exact node and edge identities. All identities are
deterministic ``uuid5`` values so rebuilds are byte-identical when inputs are
identical and distinct when semantics changed.

Epistemic state is mandatory on every edge. The admitted vocabulary reuses the
planning labels ``EXTRACTED``, ``DERIVED``, ``INFERRED``, ``ASSERTED`` and
``AMBIGUOUS`` together with the evidence-strength states ``SUPPORTED``,
``PARTIALLY_SUPPORTED``, ``UNKNOWN``, ``CONTRADICTED``, ``MISSING_EVIDENCE``,
``ABSTAINED`` and ``FAILED`` where applicable. An edge existing never proves a
medical relationship; strength-style states are verdict metadata, not truth.

Source revision handling is deterministic. Corpus sources are immutable: a new
revision is a new source identity. Nodes and edges bound to an old revision keep
their identities as history but a new revision yields new derived identities.
Deleting a source revision makes every derived object bound to it stale: reads
and rebuilds fail closed with ``GraphStaleError`` instead of serving known-stale
state. Views are frozen snapshots and never mutate.

Node and edge text is data, not authority. Labels, keys, and source text are
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
from medscale_workspace import evidence_strength as strength_mod
from medscale_workspace.audit import AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    ClaimInputError,
    ClaimRevisionError,
    GraphConflictError,
    GraphInputError,
    GraphPathError,
    GraphRevisionError,
    GraphStaleError,
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

NODE_NAMESPACE = UUID("c011a1de-0001-4000-8000-000000000011")
EDGE_NAMESPACE = UUID("c011e1de-0002-4000-8000-000000000011")
VIEW_NAMESPACE = UUID("c011b1de-0003-4000-8000-000000000011")
NODE_REVISION = "graph-node-00000001"
EDGE_REVISION = "graph-edge-00000001"
VIEW_REVISION = "graph-view-00000001"
PRODUCER_VERSION = "cw011-v1"
DERIVATION_METHOD = "cw011-deterministic-derivation"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw011-patient-graph/1"
GRAPH_SCHEMA_VERSION = 1
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_NODE_KEY_CHARS = 128
MAXIMUM_LABEL_CHARS = 512
MAXIMUM_SOURCES_PER_EDGE = 8
MAXIMUM_NODES_PER_VIEW = 256
MAXIMUM_EDGES_PER_VIEW = 512
MAXIMUM_OCCURRED_AT_CHARS = 64
MAXIMUM_PATH_DEPTH = 16


class NodeKind(StrEnum):
    """Admitted node classes of the longitudinal graph."""

    PATIENT = "patient"
    ENCOUNTER = "encounter"
    CONDITION = "condition"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    OBSERVATION = "observation"
    PROCEDURE = "procedure"
    DIAGNOSTIC_REPORT = "diagnostic_report"
    DOCUMENT = "document"
    EVIDENCE_SOURCE = "evidence_source"
    CLINICAL_CLAIM = "clinical_claim"
    TASK = "task"
    APPOINTMENT = "appointment"
    PRACTITIONER = "practitioner"


class RelationshipType(StrEnum):
    """Admitted relationship types between two graph nodes."""

    HAS_ENCOUNTER = "has_encounter"
    HAS_CONDITION = "has_condition"
    HAS_MEDICATION = "has_medication"
    HAS_ALLERGY = "has_allergy"
    HAS_OBSERVATION = "has_observation"
    HAS_PROCEDURE = "has_procedure"
    HAS_REPORT = "has_report"
    HAS_DOCUMENT = "has_document"
    EVIDENCE_FOR = "evidence_for"
    DERIVED_FROM = "derived_from"
    FOLLOWS = "follows"
    PRECEDES = "precedes"
    RELATED_TO = "related_to"
    ASSERTED_LINK = "asserted_link"


class EpistemicState(StrEnum):
    """Mandatory epistemic state of one graph edge. Never collapsed.

    The first five members reuse the planning vocabulary. The remaining seven
    reuse the evidence-strength verdict vocabulary where applicable. Every
    member is a distinct decided state; edge existence alone proves nothing.
    """

    EXTRACTED = "extracted"
    DERIVED = "derived"
    INFERRED = "inferred"
    ASSERTED = "asserted"
    AMBIGUOUS = "ambiguous"
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"
    MISSING_EVIDENCE = "missing_evidence"
    ABSTAINED = "abstained"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One derived graph node bound to one admitted corpus source revision."""

    workspace_id: UUID
    node_id: UUID
    node_key: str
    node_kind: NodeKind
    label: str
    source_id: UUID
    source_revision: str
    content_digest: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise GraphInputError("a workspace id must be a UUID value")
        if not isinstance(self.node_id, UUID):
            raise GraphInputError("a node id must be a UUID value")
        node_key = _admit_node_key(self.node_key)
        if not isinstance(self.node_kind, NodeKind):
            raise GraphInputError("a node kind is not admitted here")
        label = _admit_label(self.label)
        if not isinstance(self.source_id, UUID):
            raise GraphInputError("a node source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision")
        digest = _admit_digest(self.content_digest)
        expected = node_id_for(self.workspace_id, node_key, self.node_kind, revision)
        if self.node_id != expected:
            raise GraphRevisionError("a node identity does not match its lineage")
        return GraphNode(
            workspace_id=self.workspace_id,
            node_id=self.node_id,
            node_key=node_key,
            node_kind=self.node_kind,
            label=label,
            source_id=self.source_id,
            source_revision=revision,
            content_digest=digest,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "content_digest": admitted.content_digest,
            "data_class": synthetic_data_class_value(),
            "label": admitted.label,
            "node_id": str(admitted.node_id),
            "node_key": admitted.node_key,
            "node_kind": admitted.node_kind.value,
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise GraphInputError("a stored node must be a JSON object")
        expected = {
            "content_digest",
            "data_class",
            "label",
            "node_id",
            "node_key",
            "node_kind",
            "policy_version",
            "schema_version",
            "source_id",
            "source_revision",
            "workspace_id",
        }
        if set(document) != expected:
            raise GraphInputError("a stored node carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise GraphInputError("a stored node data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise GraphInputError("a stored node policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise GraphInputError("a stored node schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            node_id = UUID(str(document["node_id"]))
            source_id = UUID(str(document["source_id"]))
            node_kind = NodeKind(str(document["node_kind"]))
        except ValueError as error:
            raise GraphInputError("a stored node identity is not admitted") from error
        return GraphNode(
            workspace_id=workspace_id,
            node_id=node_id,
            node_key=_string_member(document, "node_key"),
            node_kind=node_kind,
            label=_string_member(document, "label"),
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class GraphEdgeSource:
    """One admitted corpus source revision bound into an edge."""

    source_id: UUID
    source_revision: str
    content_digest: str

    def validated(self):
        if not isinstance(self.source_id, UUID):
            raise GraphInputError("an edge source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision")
        digest = _admit_digest(self.content_digest)
        return GraphEdgeSource(
            source_id=self.source_id,
            source_revision=revision,
            content_digest=digest,
        )

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
            raise GraphInputError("a stored edge source must be a JSON object")
        expected = {"content_digest", "source_id", "source_revision"}
        if set(document) != expected:
            raise GraphInputError("a stored edge source carries unadmitted members")
        try:
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise GraphInputError("a stored edge source id is not admitted") from error
        return GraphEdgeSource(
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One derived graph edge with mandatory epistemic state and source refs."""

    workspace_id: UUID
    edge_id: UUID
    source_node: UUID
    target_node: UUID
    relationship: RelationshipType
    epistemic: EpistemicState
    sources: tuple
    derivation_method: str
    derivation_version: str
    graph_schema_version: int
    claim_set_id: UUID | None
    claim_id: UUID | None

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise GraphInputError("a workspace id must be a UUID value")
        if not isinstance(self.edge_id, UUID):
            raise GraphInputError("an edge id must be a UUID value")
        if not isinstance(self.source_node, UUID):
            raise GraphInputError("an edge source node must be a UUID value")
        if not isinstance(self.target_node, UUID):
            raise GraphInputError("an edge target node must be a UUID value")
        if self.source_node == self.target_node:
            raise GraphInputError("an edge must connect two distinct nodes")
        if not isinstance(self.relationship, RelationshipType):
            raise GraphInputError("an edge relationship is not admitted here")
        if not isinstance(self.epistemic, EpistemicState):
            raise GraphInputError("an edge epistemic state is not admitted here")
        if not isinstance(self.sources, tuple) or not self.sources:
            raise GraphInputError("an edge needs a non-empty tuple of sources")
        if len(self.sources) > MAXIMUM_SOURCES_PER_EDGE:
            raise GraphInputError("an edge carries an unadmitted source count")
        checked = tuple(
            item.validated() if isinstance(item, GraphEdgeSource) else None for item in self.sources
        )
        if any(item is None for item in checked):
            raise GraphInputError("edge sources need GraphEdgeSource instances")
        _check_duplicate_edge_sources(checked)
        method = _admit_identifier(self.derivation_method, "derivation method")
        if method != DERIVATION_METHOD:
            raise GraphInputError("an edge derivation method is not admitted here")
        version = _admit_identifier(self.derivation_version, "derivation version")
        if version != DERIVATION_METHOD_VERSION:
            raise GraphInputError("an edge derivation version is not admitted here")
        schema = self.graph_schema_version
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise GraphInputError("a graph schema version must be an integer")
        if schema != GRAPH_SCHEMA_VERSION:
            raise GraphInputError("a graph schema version is not supported here")
        claim_set = _admit_optional_uuid(self.claim_set_id, "claim set id")
        claim = _admit_optional_uuid(self.claim_id, "claim id")
        if (claim_set is None) != (claim is None):
            raise GraphInputError("an edge claim context needs both set and claim")
        expected = edge_id_for(
            self.workspace_id,
            self.source_node,
            self.target_node,
            self.relationship,
            self.epistemic,
            checked,
            method,
            version,
            claim_set,
            claim,
        )
        if self.edge_id != expected:
            raise GraphRevisionError("an edge identity does not match its bindings")
        return GraphEdge(
            workspace_id=self.workspace_id,
            edge_id=self.edge_id,
            source_node=self.source_node,
            target_node=self.target_node,
            relationship=self.relationship,
            epistemic=self.epistemic,
            sources=checked,
            derivation_method=method,
            derivation_version=version,
            graph_schema_version=schema,
            claim_set_id=claim_set,
            claim_id=claim,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "claim_id": "" if admitted.claim_id is None else str(admitted.claim_id),
            "claim_set_id": "" if admitted.claim_set_id is None else str(admitted.claim_set_id),
            "data_class": synthetic_data_class_value(),
            "derivation_method": admitted.derivation_method,
            "derivation_version": admitted.derivation_version,
            "edge_id": str(admitted.edge_id),
            "epistemic": admitted.epistemic.value,
            "graph_schema_version": admitted.graph_schema_version,
            "policy_version": POLICY_VERSION,
            "relationship": admitted.relationship.value,
            "schema_version": SCHEMA_VERSION,
            "source_node": str(admitted.source_node),
            "sources": [item.to_document() for item in admitted.sources],
            "target_node": str(admitted.target_node),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise GraphInputError("a stored edge must be a JSON object")
        expected = {
            "claim_id",
            "claim_set_id",
            "data_class",
            "derivation_method",
            "derivation_version",
            "edge_id",
            "epistemic",
            "graph_schema_version",
            "policy_version",
            "relationship",
            "schema_version",
            "source_node",
            "sources",
            "target_node",
            "workspace_id",
        }
        if set(document) != expected:
            raise GraphInputError("a stored edge carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise GraphInputError("a stored edge data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise GraphInputError("a stored edge policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise GraphInputError("a stored edge schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            edge_id = UUID(str(document["edge_id"]))
            source_node = UUID(str(document["source_node"]))
            target_node = UUID(str(document["target_node"]))
            relationship = RelationshipType(str(document["relationship"]))
            epistemic = EpistemicState(str(document["epistemic"]))
        except ValueError as error:
            raise GraphInputError("a stored edge identity is not admitted") from error
        raw_sources = document["sources"]
        if not isinstance(raw_sources, list):
            raise GraphInputError("stored edge sources must be a JSON array")
        sources = tuple(GraphEdgeSource.from_document(item) for item in raw_sources)
        schema = document["graph_schema_version"]
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise GraphInputError("a stored graph schema version must be an integer")
        return GraphEdge(
            workspace_id=workspace_id,
            edge_id=edge_id,
            source_node=source_node,
            target_node=target_node,
            relationship=relationship,
            epistemic=epistemic,
            sources=sources,
            derivation_method=_string_member(document, "derivation_method"),
            derivation_version=_string_member(document, "derivation_version"),
            graph_schema_version=schema,
            claim_set_id=_optional_uuid_member(document, "claim_set_id"),
            claim_id=_optional_uuid_member(document, "claim_id"),
        ).validated()


@dataclass(frozen=True, slots=True)
class GraphView:
    """One frozen derived graph view over exact node and edge identities."""

    workspace_id: UUID
    view_id: UUID
    node_ids: tuple
    edge_ids: tuple
    derivation_method: str
    derivation_version: str
    graph_schema_version: int

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise GraphInputError("a workspace id must be a UUID value")
        if not isinstance(self.view_id, UUID):
            raise GraphInputError("a view id must be a UUID value")
        if not isinstance(self.node_ids, tuple):
            raise GraphInputError("view node ids must be a tuple")
        if not isinstance(self.edge_ids, tuple):
            raise GraphInputError("view edge ids must be a tuple")
        if len(self.node_ids) > MAXIMUM_NODES_PER_VIEW:
            raise GraphInputError("a view carries an unadmitted node count")
        if len(self.edge_ids) > MAXIMUM_EDGES_PER_VIEW:
            raise GraphInputError("a view carries an unadmitted edge count")
        for node_id in self.node_ids:
            if not isinstance(node_id, UUID):
                raise GraphInputError("a view node id must be a UUID value")
        for edge_id in self.edge_ids:
            if not isinstance(edge_id, UUID):
                raise GraphInputError("a view edge id must be a UUID value")
        if len(set(self.node_ids)) != len(self.node_ids):
            raise GraphInputError("a view carries a duplicated node id")
        if len(set(self.edge_ids)) != len(self.edge_ids):
            raise GraphInputError("a view carries a duplicated edge id")
        if tuple(sorted(self.node_ids, key=str)) != self.node_ids:
            raise GraphInputError("view node ids must be sorted by string order")
        if tuple(sorted(self.edge_ids, key=str)) != self.edge_ids:
            raise GraphInputError("view edge ids must be sorted by string order")
        method = _admit_identifier(self.derivation_method, "derivation method")
        if method != DERIVATION_METHOD:
            raise GraphInputError("a view derivation method is not admitted here")
        version = _admit_identifier(self.derivation_version, "derivation version")
        if version != DERIVATION_METHOD_VERSION:
            raise GraphInputError("a view derivation version is not admitted here")
        schema = self.graph_schema_version
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise GraphInputError("a graph schema version must be an integer")
        if schema != GRAPH_SCHEMA_VERSION:
            raise GraphInputError("a graph schema version is not supported here")
        expected = view_id_for(self.workspace_id, self.node_ids, self.edge_ids, method, version)
        if self.view_id != expected:
            raise GraphRevisionError("a view identity does not match its members")
        return GraphView(
            workspace_id=self.workspace_id,
            view_id=self.view_id,
            node_ids=self.node_ids,
            edge_ids=self.edge_ids,
            derivation_method=method,
            derivation_version=version,
            graph_schema_version=schema,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "derivation_method": admitted.derivation_method,
            "derivation_version": admitted.derivation_version,
            "edge_ids": [str(edge_id) for edge_id in admitted.edge_ids],
            "graph_schema_version": admitted.graph_schema_version,
            "node_ids": [str(node_id) for node_id in admitted.node_ids],
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "view_id": str(admitted.view_id),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise GraphInputError("a stored view must be a JSON object")
        expected = {
            "data_class",
            "derivation_method",
            "derivation_version",
            "edge_ids",
            "graph_schema_version",
            "node_ids",
            "policy_version",
            "schema_version",
            "view_id",
            "workspace_id",
        }
        if set(document) != expected:
            raise GraphInputError("a stored view carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise GraphInputError("a stored view data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise GraphInputError("a stored view policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise GraphInputError("a stored view schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            view_id = UUID(str(document["view_id"]))
        except ValueError as error:
            raise GraphInputError("a stored view identity is not admitted") from error
        raw_nodes = document["node_ids"]
        raw_edges = document["edge_ids"]
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise GraphInputError("stored view members must be JSON arrays")
        node_ids = tuple(_parse_uuid_member(value) for value in raw_nodes)
        edge_ids = tuple(_parse_uuid_member(value) for value in raw_edges)
        schema = document["graph_schema_version"]
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise GraphInputError("a stored graph schema version must be an integer")
        return GraphView(
            workspace_id=workspace_id,
            view_id=view_id,
            node_ids=node_ids,
            edge_ids=edge_ids,
            derivation_method=_string_member(document, "derivation_method"),
            derivation_version=_string_member(document, "derivation_version"),
            graph_schema_version=schema,
        ).validated()


@dataclass(frozen=True, slots=True)
class PathStep:
    """One explained edge traversal with its provenance binding."""

    edge_id: UUID
    source_node: UUID
    target_node: UUID
    relationship: RelationshipType
    epistemic: EpistemicState
    source_ids: tuple
    source_revisions: tuple
    derivation_method: str
    derivation_version: str
    provenance_digest: str


@dataclass(frozen=True, slots=True)
class PathExplanation:
    """One deterministic path explanation with inspectable provenance."""

    workspace_id: UUID
    source_node: UUID
    target_node: UUID
    node_ids: tuple
    steps: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise GraphPathError("a path workspace id must be a UUID value")
        if not isinstance(self.source_node, UUID):
            raise GraphPathError("a path source node must be a UUID value")
        if not isinstance(self.target_node, UUID):
            raise GraphPathError("a path target node must be a UUID value")
        if not isinstance(self.node_ids, tuple) or len(self.node_ids) < 2:
            raise GraphPathError("a path needs at least two nodes")
        if self.node_ids[0] != self.source_node or self.node_ids[-1] != self.target_node:
            raise GraphPathError("a path must start and end at its endpoints")
        if not isinstance(self.steps, tuple) or not self.steps:
            raise GraphPathError("a path needs at least one step")
        if len(self.steps) != len(self.node_ids) - 1:
            raise GraphPathError("a path step count must match its node count")
        for step in self.steps:
            if not isinstance(step, PathStep):
                raise GraphPathError("a path step must be a PathStep instance")
        return self


def node_id_for(workspace_id, node_key, node_kind, source_revision):
    """Return the deterministic identity of one graph node."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    key = _admit_node_key(node_key)
    if not isinstance(node_kind, NodeKind):
        raise GraphInputError("a node kind is not admitted here")
    revision = _admit_identifier(source_revision, "source revision")
    return uuid5(
        NODE_NAMESPACE,
        ":".join((str(workspace_id), key, node_kind.value, revision)),
    )


def edge_id_for(
    workspace_id,
    source_node,
    target_node,
    relationship,
    epistemic,
    sources,
    derivation_method,
    derivation_version,
    claim_set_id,
    claim_id,
):
    """Return the deterministic identity of one graph edge."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if not isinstance(source_node, UUID):
        raise GraphInputError("an edge source node must be a UUID value")
    if not isinstance(target_node, UUID):
        raise GraphInputError("an edge target node must be a UUID value")
    if not isinstance(relationship, RelationshipType):
        raise GraphInputError("an edge relationship is not admitted here")
    if not isinstance(epistemic, EpistemicState):
        raise GraphInputError("an edge epistemic state is not admitted here")
    if not isinstance(sources, tuple) or not sources:
        raise GraphInputError("an edge needs a non-empty tuple of sources")
    checked = tuple(
        item.validated() if isinstance(item, GraphEdgeSource) else None for item in sources
    )
    if any(item is None for item in checked):
        raise GraphInputError("edge sources need GraphEdgeSource instances")
    ordered = tuple(sorted(checked, key=lambda item: str(item.source_id)))
    method = _admit_identifier(derivation_method, "derivation method")
    version = _admit_identifier(derivation_version, "derivation version")
    claim_set = _admit_optional_uuid(claim_set_id, "claim set id")
    claim = _admit_optional_uuid(claim_id, "claim id")
    lines = "\n".join(
        ":".join((str(item.source_id), item.source_revision, item.content_digest))
        for item in ordered
    )
    claim_part = "" if claim_set is None else ":".join((str(claim_set), str(claim)))
    return uuid5(
        EDGE_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(source_node),
                str(target_node),
                relationship.value,
                epistemic.value,
                lines,
                method,
                version,
                claim_part,
            )
        ),
    )


def view_id_for(workspace_id, node_ids, edge_ids, derivation_method, derivation_version):
    """Return the deterministic identity of one frozen graph view."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if not isinstance(node_ids, tuple):
        raise GraphInputError("view node ids must be a tuple")
    if not isinstance(edge_ids, tuple):
        raise GraphInputError("view edge ids must be a tuple")
    for node_id in node_ids:
        if not isinstance(node_id, UUID):
            raise GraphInputError("a view node id must be a UUID value")
    for edge_id in edge_ids:
        if not isinstance(edge_id, UUID):
            raise GraphInputError("a view edge id must be a UUID value")
    method = _admit_identifier(derivation_method, "derivation method")
    version = _admit_identifier(derivation_version, "derivation version")
    node_lines = "\n".join(str(node_id) for node_id in node_ids)
    edge_lines = "\n".join(str(edge_id) for edge_id in edge_ids)
    return uuid5(
        VIEW_NAMESPACE,
        ":".join((str(workspace_id), node_lines, edge_lines, method, version)),
    )


def node_binding(workspace_id, node_id):
    """Return the store binding of one graph node."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if not isinstance(node_id, UUID):
        raise GraphInputError("a node id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=node_id,
        object_type=WorkspaceObjectType.GRAPH_NODE,
        object_revision=NODE_REVISION,
    )


def edge_binding(workspace_id, edge_id):
    """Return the store binding of one graph edge."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if not isinstance(edge_id, UUID):
        raise GraphInputError("an edge id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=edge_id,
        object_type=WorkspaceObjectType.GRAPH_EDGE,
        object_revision=EDGE_REVISION,
    )


def view_binding(workspace_id, view_id):
    """Return the store binding of one frozen graph view."""
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if not isinstance(view_id, UUID):
        raise GraphInputError("a view id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=view_id,
        object_type=WorkspaceObjectType.GRAPH_VIEW,
        object_revision=VIEW_REVISION,
    )


def admit_node(
    store,
    trail,
    workspace_id,
    node_key,
    node_kind,
    label,
    source_id,
    actor_id,
    occurred_at,
):
    """Admit one derived graph node bound to one corpus source revision."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise GraphInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph node crossed the workspace boundary")
    key = _admit_node_key(node_key)
    if not isinstance(node_kind, NodeKind):
        raise GraphInputError("a node kind is not admitted here")
    admitted_label = _admit_label(label)
    if not isinstance(source_id, UUID):
        raise GraphInputError("a node source id must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        source = corpus_mod.read_source(store, source_id)
    except corpus_mod.CorpusInputError as error:
        raise GraphRevisionError("the node source is absent in this store") from error
    node = GraphNode(
        workspace_id=workspace_id,
        node_id=node_id_for(workspace_id, key, node_kind, source.source_revision),
        node_key=key,
        node_kind=node_kind,
        label=admitted_label,
        source_id=source.source_id,
        source_revision=source.source_revision,
        content_digest=source.content_digest,
    ).validated()
    binding = node_binding(workspace_id, node.node_id)
    payload = _canonical_bytes(node.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(node.source_id),
                source_revision=node.source_revision,
                locator=None,
            ),
        ),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise GraphConflictError("the graph node identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_node(store, node_id):
    """Read and verify one stored graph node with its source still current."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(node_id, UUID):
        raise GraphInputError("a node id must be a UUID value")
    binding = node_binding(store.workspace_id, node_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise GraphInputError("the node identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise GraphInputError("a stored node is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphInputError("a stored node is not JSON") from error
    node = GraphNode.from_document(document)
    if node.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph node crossed the workspace boundary")
    if node.node_id != node_id:
        raise GraphInputError("a stored node identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    try:
        source = corpus_mod.read_source(store, node.source_id)
    except corpus_mod.CorpusInputError as error:
        raise GraphStaleError("a node source is no longer present") from error
    if source.source_revision != node.source_revision:
        raise GraphStaleError("a node source revision no longer matches")
    if source.content_digest != node.content_digest:
        raise GraphStaleError("a node source digest no longer matches")
    return node.validated()


def admit_edge(
    store,
    trail,
    workspace_id,
    source_node_id,
    target_node_id,
    relationship,
    epistemic,
    source_ids,
    actor_id,
    occurred_at,
    claim_set_id=None,
    claim_id=None,
):
    """Admit one derived graph edge with mandatory epistemic state."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise GraphInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph edge crossed the workspace boundary")
    if not isinstance(source_node_id, UUID):
        raise GraphInputError("an edge source node must be a UUID value")
    if not isinstance(target_node_id, UUID):
        raise GraphInputError("an edge target node must be a UUID value")
    if not isinstance(relationship, RelationshipType):
        raise GraphInputError("an edge relationship is not admitted here")
    if not isinstance(epistemic, EpistemicState):
        raise GraphInputError("an edge epistemic state is not admitted here")
    if not isinstance(source_ids, tuple) or not source_ids:
        raise GraphInputError("an edge needs a non-empty tuple of source ids")
    if len(source_ids) > MAXIMUM_SOURCES_PER_EDGE:
        raise GraphInputError("an edge carries an unadmitted source count")
    for source_id in source_ids:
        if not isinstance(source_id, UUID):
            raise GraphInputError("an edge source id must be a UUID value")
    if len(set(source_ids)) != len(source_ids):
        raise GraphInputError("an edge carries a duplicated source id")
    claim_set = _admit_optional_uuid(claim_set_id, "claim set id")
    claim = _admit_optional_uuid(claim_id, "claim id")
    if (claim_set is None) != (claim is None):
        raise GraphInputError("an edge claim context needs both set and claim")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    try:
        source_node = read_node(store, source_node_id)
    except GraphStaleError as error:
        raise GraphRevisionError("an edge endpoint node is stale") from error
    except GraphInputError as error:
        raise GraphRevisionError("an edge endpoint node is absent") from error
    try:
        target_node = read_node(store, target_node_id)
    except GraphStaleError as error:
        raise GraphRevisionError("an edge endpoint node is stale") from error
    except GraphInputError as error:
        raise GraphRevisionError("an edge endpoint node is absent") from error
    if source_node.workspace_id != workspace_id or target_node.workspace_id != workspace_id:
        raise WorkspaceIsolationError("an edge endpoint crossed the workspace boundary")
    bound_sources = []
    for source_id in source_ids:
        try:
            source = corpus_mod.read_source(store, source_id)
        except corpus_mod.CorpusInputError as error:
            raise GraphRevisionError("an edge source is absent in this store") from error
        bound_sources.append(
            GraphEdgeSource(
                source_id=source.source_id,
                source_revision=source.source_revision,
                content_digest=source.content_digest,
            ).validated()
        )
    if claim_set is not None and claim is not None:
        try:
            claim_set_doc = strength_mod.read_claim_set(store, claim_set)
        except ClaimInputError as error:
            raise GraphRevisionError("an edge claim set is absent") from error
        except ClaimRevisionError as error:
            raise GraphRevisionError("an edge claim set is stale") from error
        if claim_set_doc.workspace_id != workspace_id:
            raise WorkspaceIsolationError("an edge claim crossed the workspace boundary")
        found = False
        for item in claim_set_doc.claims:
            if item.claim_id == claim:
                found = True
                break
        if not found:
            raise GraphRevisionError("an edge claim is absent from its claim set")
    ordered = tuple(sorted(bound_sources, key=lambda item: str(item.source_id)))
    edge = GraphEdge(
        workspace_id=workspace_id,
        edge_id=edge_id_for(
            workspace_id,
            source_node.node_id,
            target_node.node_id,
            relationship,
            epistemic,
            ordered,
            DERIVATION_METHOD,
            DERIVATION_METHOD_VERSION,
            claim_set,
            claim,
        ),
        source_node=source_node.node_id,
        target_node=target_node.node_id,
        relationship=relationship,
        epistemic=epistemic,
        sources=ordered,
        derivation_method=DERIVATION_METHOD,
        derivation_version=DERIVATION_METHOD_VERSION,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
        claim_set_id=claim_set,
        claim_id=claim,
    ).validated()
    binding = edge_binding(workspace_id, edge.edge_id)
    payload = _canonical_bytes(edge.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    refs = tuple(
        SourceRef(
            kind=SourceKind.EVIDENCE_SOURCE,
            source_id=str(item.source_id),
            source_revision=item.source_revision,
            locator=None,
        )
        for item in edge.sources
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
        raise GraphConflictError("the graph edge identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_edge(store, edge_id):
    """Read and verify one stored graph edge with all sources still current."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(edge_id, UUID):
        raise GraphInputError("an edge id must be a UUID value")
    binding = edge_binding(store.workspace_id, edge_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise GraphInputError("the edge identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise GraphInputError("a stored edge is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphInputError("a stored edge is not JSON") from error
    edge = GraphEdge.from_document(document)
    if edge.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph edge crossed the workspace boundary")
    if edge.edge_id != edge_id:
        raise GraphInputError("a stored edge identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    try:
        read_node(store, edge.source_node)
    except GraphInputError as error:
        raise GraphStaleError("an edge endpoint node is no longer present") from error
    try:
        read_node(store, edge.target_node)
    except GraphInputError as error:
        raise GraphStaleError("an edge endpoint node is no longer present") from error
    for bound in edge.sources:
        try:
            source = corpus_mod.read_source(store, bound.source_id)
        except corpus_mod.CorpusInputError as error:
            raise GraphStaleError("an edge source is no longer present") from error
        if source.source_revision != bound.source_revision:
            raise GraphStaleError("an edge source revision no longer matches")
        if source.content_digest != bound.content_digest:
            raise GraphStaleError("an edge source digest no longer matches")
    if edge.claim_set_id is not None and edge.claim_id is not None:
        try:
            claim_set_doc = strength_mod.read_claim_set(store, edge.claim_set_id)
        except (ClaimInputError, ClaimRevisionError) as error:
            raise GraphStaleError("an edge claim set is no longer present") from error
        found = False
        for item in claim_set_doc.claims:
            if item.claim_id == edge.claim_id:
                found = True
                break
        if not found:
            raise GraphStaleError("an edge claim is no longer present")
    return edge.validated()


def rebuild_graph(store, trail, workspace_id, node_ids, edge_ids, actor_id, occurred_at):
    """Rebuild one frozen graph view from exact admitted members.

    Inputs are sorted deterministically, so reordered inputs yield the identical
    view identity. Identical rebuilds are idempotent: an existing view is
    returned instead of conflicting. Changed revisions yield different member
    identities and therefore a different view. Missing, malformed, foreign, or
    stale members fail closed.
    """
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise GraphInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise GraphInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph rebuild crossed the workspace boundary")
    if not isinstance(node_ids, tuple):
        raise GraphInputError("rebuild node ids must be a tuple")
    if not isinstance(edge_ids, tuple):
        raise GraphInputError("rebuild edge ids must be a tuple")
    for node_id in node_ids:
        if not isinstance(node_id, UUID):
            raise GraphInputError("a rebuild node id must be a UUID value")
    for edge_id in edge_ids:
        if not isinstance(edge_id, UUID):
            raise GraphInputError("a rebuild edge id must be a UUID value")
    if len(set(node_ids)) != len(node_ids):
        raise GraphInputError("a rebuild carries a duplicated node id")
    if len(set(edge_ids)) != len(edge_ids):
        raise GraphInputError("a rebuild carries a duplicated edge id")
    if len(node_ids) > MAXIMUM_NODES_PER_VIEW:
        raise GraphInputError("a rebuild carries an unadmitted node count")
    if len(edge_ids) > MAXIMUM_EDGES_PER_VIEW:
        raise GraphInputError("a rebuild carries an unadmitted edge count")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    verified_nodes = []
    for node_id in node_ids:
        try:
            node = read_node(store, node_id)
        except GraphStaleError as error:
            raise GraphStaleError("a rebuild node is stale") from error
        if node.workspace_id != workspace_id:
            raise WorkspaceIsolationError("a rebuild node crossed the workspace boundary")
        verified_nodes.append(node.node_id)
    verified_edges = []
    for edge_id in edge_ids:
        try:
            edge = read_edge(store, edge_id)
        except GraphStaleError as error:
            raise GraphStaleError("a rebuild edge is stale") from error
        if edge.workspace_id != workspace_id:
            raise WorkspaceIsolationError("a rebuild edge crossed the workspace boundary")
        verified_edges.append(edge.edge_id)
    ordered_nodes = tuple(sorted(verified_nodes, key=str))
    ordered_edges = tuple(sorted(verified_edges, key=str))
    member_nodes = set(ordered_nodes)
    for edge_id in ordered_edges:
        edge = read_edge(store, edge_id)
        if edge.source_node not in member_nodes or edge.target_node not in member_nodes:
            raise GraphRevisionError("a rebuild edge reaches outside its node set")
    view = GraphView(
        workspace_id=workspace_id,
        view_id=view_id_for(
            workspace_id,
            ordered_nodes,
            ordered_edges,
            DERIVATION_METHOD,
            DERIVATION_METHOD_VERSION,
        ),
        node_ids=ordered_nodes,
        edge_ids=ordered_edges,
        derivation_method=DERIVATION_METHOD,
        derivation_version=DERIVATION_METHOD_VERSION,
        graph_schema_version=GRAPH_SCHEMA_VERSION,
    ).validated()
    binding = view_binding(workspace_id, view.view_id)
    payload = _canonical_bytes(view.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError:
        return binding
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_view(store, view_id):
    """Read and verify one frozen graph view with all members still current."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(view_id, UUID):
        raise GraphInputError("a view id must be a UUID value")
    binding = view_binding(store.workspace_id, view_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise GraphInputError("the view identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise GraphInputError("a stored view is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphInputError("a stored view is not JSON") from error
    view = GraphView.from_document(document)
    if view.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a graph view crossed the workspace boundary")
    if view.view_id != view_id:
        raise GraphInputError("a stored view identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    for node_id in view.node_ids:
        try:
            read_node(store, node_id)
        except GraphInputError as error:
            raise GraphStaleError("a view node is no longer present") from error
    for edge_id in view.edge_ids:
        try:
            read_edge(store, edge_id)
        except GraphInputError as error:
            raise GraphStaleError("a view edge is no longer present") from error
        except GraphStaleError as error:
            raise GraphStaleError("a view edge is stale") from error
    return view.validated()


def explain_path(store, source_node_id, target_node_id, max_depth=8, view_id=None):
    """Explain one deterministic path with inspectable provenance.

    Breadth-first search over current edges (or over one frozen view when
    ``view_id`` is given). Neighbors are visited in string order so ties are
    deterministic. Every returned step carries source revisions, epistemic
    state, derivation identity, and the recorded provenance digest.
    """
    if not isinstance(store, WorkspaceStore):
        raise GraphPathError("a workspace store is required")
    if not isinstance(source_node_id, UUID):
        raise GraphPathError("a path source node must be a UUID value")
    if not isinstance(target_node_id, UUID):
        raise GraphPathError("a path target node must be a UUID value")
    if source_node_id == target_node_id:
        raise GraphPathError("a path needs two distinct endpoints")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int):
        raise GraphPathError("a path depth must be an integer")
    if max_depth < 1 or max_depth > MAXIMUM_PATH_DEPTH:
        raise GraphPathError("a path depth is not admitted here")
    if view_id is not None and not isinstance(view_id, UUID):
        raise GraphPathError("a view id must be a UUID value")
    try:
        source_node = read_node(store, source_node_id)
    except GraphInputError as error:
        raise GraphPathError("a path endpoint node is absent") from error
    except GraphStaleError as error:
        raise GraphPathError("a path endpoint node is stale") from error
    try:
        target_node = read_node(store, target_node_id)
    except GraphInputError as error:
        raise GraphPathError("a path endpoint node is absent") from error
    except GraphStaleError as error:
        raise GraphPathError("a path endpoint node is stale") from error
    if source_node.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a path endpoint crossed the workspace boundary")
    if target_node.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a path endpoint crossed the workspace boundary")
    if view_id is not None:
        try:
            view = read_view(store, view_id)
        except GraphInputError as error:
            raise GraphPathError("a path view is absent") from error
        if view.workspace_id != store.workspace_id:
            raise WorkspaceIsolationError("a path view crossed the workspace boundary")
        if source_node.node_id not in set(view.node_ids):
            raise GraphPathError("a path endpoint is outside its view")
        if target_node.node_id not in set(view.node_ids):
            raise GraphPathError("a path endpoint is outside its view")
        candidate_ids = view.edge_ids
    else:
        revisions = store.object_revisions(WorkspaceObjectType.GRAPH_EDGE)
        candidate_ids = tuple(object_id for object_id, _revision in revisions)
        candidate_ids = tuple(sorted(candidate_ids, key=str))
    adjacency: dict[str, list] = {}
    current_edges: dict[str, object] = {}
    for edge_id in candidate_ids:
        try:
            edge = read_edge(store, edge_id)
        except (GraphInputError, GraphStaleError):
            continue
        if edge.workspace_id != store.workspace_id:
            continue
        key = str(edge.source_node)
        if key not in adjacency:
            adjacency[key] = []
        adjacency[key].append(edge)
        current_edges[str(edge.edge_id)] = edge
    for key in adjacency:
        adjacency[key] = sorted(adjacency[key], key=lambda item: str(item.edge_id))
    start = str(source_node.node_id)
    goal = str(target_node.node_id)
    queue: list[tuple[str, tuple]] = [(start, ())]
    visited: set[str] = {start}
    found: tuple | None = None
    while queue:
        current, path = queue.pop(0)
        if len(path) > max_depth:
            continue
        if current == goal:
            found = path
            break
        for edge in adjacency.get(current, ()):
            nxt = str(edge.target_node)
            if nxt in visited:
                continue
            visited.add(nxt)
            queue.append((nxt, (*path, edge)))
    if found is None:
        raise GraphPathError("no graph path exists between the endpoints")
    node_ids = [source_node.node_id]
    steps = []
    for edge in found:
        node_ids.append(edge.target_node)
        binding = edge_binding(store.workspace_id, edge.edge_id)
        record = read_provenance(store, binding)
        steps.append(
            PathStep(
                edge_id=edge.edge_id,
                source_node=edge.source_node,
                target_node=edge.target_node,
                relationship=edge.relationship,
                epistemic=edge.epistemic,
                source_ids=tuple(item.source_id for item in edge.sources),
                source_revisions=tuple(item.source_revision for item in edge.sources),
                derivation_method=edge.derivation_method,
                derivation_version=edge.derivation_version,
                provenance_digest=record.content_digest,
            )
        )
    return PathExplanation(
        workspace_id=store.workspace_id,
        source_node=source_node.node_id,
        target_node=target_node.node_id,
        node_ids=tuple(node_ids),
        steps=tuple(steps),
    ).validated()


def edges_affected_by_source(store, source_id):
    """List current edge identities bound to one corpus source, in sorted order."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(source_id, UUID):
        raise GraphInputError("a source id must be a UUID value")
    revisions = store.object_revisions(WorkspaceObjectType.GRAPH_EDGE)
    affected = []
    for edge_id, _revision in sorted(revisions, key=lambda item: str(item[0])):
        try:
            edge = read_edge(store, edge_id)
        except (GraphInputError, GraphStaleError):
            continue
        for bound in edge.sources:
            if bound.source_id == source_id:
                affected.append(edge.edge_id)
                break
    return tuple(sorted(affected, key=str))


def nodes_affected_by_source(store, source_id):
    """List current node identities bound to one corpus source, in sorted order."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(source_id, UUID):
        raise GraphInputError("a source id must be a UUID value")
    revisions = store.object_revisions(WorkspaceObjectType.GRAPH_NODE)
    affected = []
    for node_id, _revision in sorted(revisions, key=lambda item: str(item[0])):
        try:
            node = read_node(store, node_id)
        except (GraphInputError, GraphStaleError):
            continue
        if node.source_id == source_id:
            affected.append(node.node_id)
    return tuple(sorted(affected, key=str))


def delete_edge(store, trail, edge_id, actor_id, occurred_at):
    """Delete one edge revision and its provenance while keeping audit events."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise GraphInputError("an audit trail is required")
    if not isinstance(edge_id, UUID):
        raise GraphInputError("an edge id must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    binding = edge_binding(store.workspace_id, edge_id)
    try:
        store.get_object(binding)
    except ObjectNotFoundError as error:
        raise GraphInputError("the edge identity is not present") from error
    removed = 0
    for target in (binding, provenance_binding_for(binding)):
        try:
            trail.record_object_deletion(binding=target, actor_id=actor, occurred_at=moment)
            removed += 1
        except ObjectNotFoundError:
            continue
    return removed


def delete_node(store, trail, node_id, actor_id, occurred_at):
    """Delete one node, its incident edges, and their provenance records."""
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise GraphInputError("an audit trail is required")
    if not isinstance(node_id, UUID):
        raise GraphInputError("a node id must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    binding = node_binding(store.workspace_id, node_id)
    try:
        store.get_object(binding)
    except ObjectNotFoundError as error:
        raise GraphInputError("the node identity is not present") from error
    incident = []
    revisions = store.object_revisions(WorkspaceObjectType.GRAPH_EDGE)
    for edge_id, _revision in revisions:
        edge_binding_local = edge_binding(store.workspace_id, edge_id)
        try:
            raw = store.get_object(edge_binding_local)
        except ObjectNotFoundError:
            continue
        try:
            document = json.loads(raw.decode("ascii"))
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(document, dict):
            continue
        if document.get("source_node") == str(node_id) or document.get("target_node") == str(
            node_id
        ):
            incident.append(edge_id)
    removed = 0
    for edge_id in sorted(incident, key=str):
        removed += delete_edge(store, trail, edge_id, actor, moment)
    for target in (binding, provenance_binding_for(binding)):
        try:
            trail.record_object_deletion(binding=target, actor_id=actor, occurred_at=moment)
            removed += 1
        except ObjectNotFoundError:
            continue
    return removed


def _check_duplicate_edge_sources(sources):
    seen = set()
    for item in sources:
        if item.source_id in seen:
            raise GraphInputError("an edge carries a duplicated source id")
        seen.add(item.source_id)


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise GraphInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise GraphInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise GraphInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise GraphInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise GraphInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_node_key(raw):
    if not isinstance(raw, str):
        raise GraphInputError("a node key must be a string")
    value = raw.strip()
    if not value:
        raise GraphInputError("a node key must be non-empty")
    if len(value) > MAXIMUM_NODE_KEY_CHARS:
        raise GraphInputError("a node key is longer than the admitted maximum")
    if not value.isascii():
        raise GraphInputError("a node key must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise GraphInputError("a node key must not contain whitespace or controls")
    return value


def _admit_label(raw):
    if not isinstance(raw, str):
        raise GraphInputError("a node label must be a string")
    value = raw.strip()
    if not value:
        raise GraphInputError("a node label must be non-empty")
    if len(value) > MAXIMUM_LABEL_CHARS:
        raise GraphInputError("a node label is longer than the admitted maximum")
    if not value.isascii():
        raise GraphInputError("a node label must be ASCII")
    for character in value:
        if character in ("\n", "\t"):
            continue
        if not character.isprintable():
            raise GraphInputError("a node label must not contain control characters")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise GraphInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise GraphInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise GraphInputError("a graph occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise GraphInputError("a graph occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise GraphInputError("a graph occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise GraphInputError("a graph occurrence time must be an ISO-8601 instant")
    if not value.isascii():
        raise GraphInputError("a graph occurrence time must be ASCII")
    return value


def _admit_optional_uuid(raw, label):
    if raw is None:
        return None
    if not isinstance(raw, UUID):
        raise GraphInputError(f"a {label} must be a UUID value or None")
    return raw


def _optional_uuid_member(document, name):
    value = document[name]
    if value == "":
        return None
    if not isinstance(value, str):
        raise GraphInputError(f"a stored {name} must be a string")
    try:
        return UUID(value)
    except ValueError as error:
        raise GraphInputError(f"a stored {name} is not admitted") from error


def _parse_uuid_member(value):
    if not isinstance(value, str):
        raise GraphInputError("a stored member identity must be a string")
    try:
        return UUID(value)
    except ValueError as error:
        raise GraphInputError("a stored member identity is not admitted") from error


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise GraphInputError(f"a stored {name} must be a string")
    return value


def timeline_for_view(store, view_id):
    """Return one deterministic timeline ordering of a view's nodes.

    Nodes are ordered by node key string order as the synthetic timeline proxy;
    edges are returned in view order. The timeline carries no clinical time
    claim: it is a deterministic projection of admitted view members.
    """
    if not isinstance(store, WorkspaceStore):
        raise GraphInputError("a workspace store is required")
    if not isinstance(view_id, UUID):
        raise GraphInputError("a view id must be a UUID value")
    view = read_view(store, view_id)
    nodes = []
    for node_id in view.node_ids:
        nodes.append(read_node(store, node_id))
    ordered = tuple(sorted(nodes, key=lambda item: item.node_key))
    edges = []
    for edge_id in view.edge_ids:
        edges.append(read_edge(store, edge_id))
    return (tuple(item.node_id for item in ordered), tuple(item.edge_id for item in edges))
