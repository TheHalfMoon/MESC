"""Deterministic offline retrieval over synthetic evidence corpora for CW-009.

A retrieval snapshot freezes the exact retrieval-relevant state of one corpus:
the member source identities with their revisions and content digests, the
index identity, the deterministic ordering rules, and the schema version. Any
change to retrieval-relevant state yields a different snapshot identity; a
frozen snapshot is never mutated, and stale or mismatched snapshots fail
closed instead of returning silently wrong results.

A query binds its normalized text, its snapshot, its retrieval parameters, and
its ranking contract into a deterministic identity. Executing an admitted query
against an unchanged snapshot always reproduces the same governed result set;
replay recomputes from the frozen snapshot and refuses divergence.

Ranking is deliberately lexical and deterministic (shared-token overlap with
source-identity tie-breaking). No model, embedding, reranker, network
connector, or remote call exists in this module, and none may be added under
this unit. Retrieved passages are returned verbatim as inert evidence data.

Research Core retrieval machinery (``litdb`` queries, dataset snapshots)
belongs to a different trust domain and is deliberately not imported here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace import corpus as corpus_mod
from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    ObjectNotFoundError,
    RetrievalConflictError,
    RetrievalInputError,
    RetrievalReplayError,
    SnapshotConflictError,
    SnapshotError,
    SnapshotInputError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    content_digest_of,
    describe_revision,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

SNAPSHOT_NAMESPACE = UUID("f22a3b44-5c6d-4e7f-8a9b-0c1d2e3f4a5b")
QUERY_NAMESPACE = UUID("a33b4c55-6d7e-4f8a-9b0c-1d2e3f4a5b6c")
RESULT_NAMESPACE = UUID("b44c5d66-7e8f-4a9b-0c1d-2e3f4a5b6c7d")
SNAPSHOT_REVISION = "snapshot-00000001"
QUERY_REVISION = "query-00000001"
RESULT_REVISION = "result-00000001"
PRODUCER_VERSION = "cw009-v1"
INDEX_IDENTITY = "cw009-lexical-overlap/1"
RANKING_IDENTITY = "overlap-desc-source-asc/1"
SCHEMA_VERSION = "cw009-retrieval/1"
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_QUERY_CHARS = 512
MAXIMUM_SOURCES_PER_SNAPSHOT = 256
MAXIMUM_RESULTS = 64
MAXIMUM_OCCURRED_AT_CHARS = 64


class MatchMode(StrEnum):
    """Admitted lexical match semantics. Part of the query identity."""

    ANY = "any"
    ALL = "all"


@dataclass(frozen=True, slots=True)
class SnapshotEntry:
    """One frozen corpus member bound by identity, revision, and digest."""

    source_id: UUID
    source_revision: str
    content_digest: str

    def validated(self):
        if not isinstance(self.source_id, UUID):
            raise SnapshotInputError("a snapshot source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "snapshot source revision")
        digest = _admit_digest(self.content_digest)
        return SnapshotEntry(
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
            raise SnapshotInputError("a stored snapshot entry must be a JSON object")
        expected = {"content_digest", "source_id", "source_revision"}
        if set(document) != expected:
            raise SnapshotInputError("a stored snapshot entry carries unadmitted members")
        try:
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise SnapshotInputError("a stored snapshot source id is not admitted") from error
        return SnapshotEntry(
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
        ).validated()


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """One immutable frozen retrieval snapshot over a corpus."""

    workspace_id: UUID
    corpus_id: UUID
    corpus_key: str
    snapshot_id: UUID
    entries: tuple
    index_identity: str
    ranking_identity: str
    schema_version: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise SnapshotInputError("a workspace id must be a UUID value")
        if not isinstance(self.corpus_id, UUID):
            raise SnapshotInputError("a corpus id must be a UUID value")
        corpus_key = _admit_identifier(self.corpus_key, "corpus key")
        if not isinstance(self.snapshot_id, UUID):
            raise SnapshotInputError("a snapshot id must be a UUID value")
        if not isinstance(self.entries, tuple):
            raise SnapshotInputError("snapshot entries must be a tuple")
        if len(self.entries) < 1 or len(self.entries) > MAXIMUM_SOURCES_PER_SNAPSHOT:
            raise SnapshotInputError("a snapshot carries an unadmitted entry count")
        checked = tuple(
            item.validated() if isinstance(item, SnapshotEntry) else None for item in self.entries
        )
        if any(item is None for item in checked):
            raise SnapshotInputError("snapshot entries need SnapshotEntry instances")
        _check_duplicate_source_ids(checked)
        index_identity = _admit_identifier(self.index_identity, "index identity")
        if index_identity != INDEX_IDENTITY:
            raise SnapshotInputError("a snapshot index identity is not admitted here")
        ranking_identity = _admit_identifier(self.ranking_identity, "ranking identity")
        if ranking_identity != RANKING_IDENTITY:
            raise SnapshotInputError("a snapshot ranking identity is not admitted here")
        schema_version = _admit_identifier(self.schema_version, "schema version")
        if schema_version != SCHEMA_VERSION:
            raise SnapshotInputError("a snapshot schema version is not supported here")
        expected_corpus = corpus_mod.corpus_id_for(self.workspace_id, corpus_key)
        if self.corpus_id != expected_corpus:
            raise SnapshotInputError("a snapshot corpus identity does not match its key")
        expected_snapshot = snapshot_id_for(self.workspace_id, self.corpus_id, checked)
        if self.snapshot_id != expected_snapshot:
            raise SnapshotInputError("a snapshot identity does not match its members")
        return SnapshotManifest(
            workspace_id=self.workspace_id,
            corpus_id=self.corpus_id,
            corpus_key=corpus_key,
            snapshot_id=self.snapshot_id,
            entries=checked,
            index_identity=index_identity,
            ranking_identity=ranking_identity,
            schema_version=schema_version,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "corpus_id": str(admitted.corpus_id),
            "corpus_key": admitted.corpus_key,
            "data_class": synthetic_data_class_value(),
            "entries": [item.to_document() for item in admitted.entries],
            "index_identity": admitted.index_identity,
            "policy_version": POLICY_VERSION,
            "ranking_identity": admitted.ranking_identity,
            "schema_version": admitted.schema_version,
            "snapshot_id": str(admitted.snapshot_id),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise SnapshotInputError("a stored snapshot must be a JSON object")
        expected = {
            "corpus_id",
            "corpus_key",
            "data_class",
            "entries",
            "index_identity",
            "policy_version",
            "ranking_identity",
            "schema_version",
            "snapshot_id",
            "workspace_id",
        }
        if set(document) != expected:
            raise SnapshotInputError("a stored snapshot carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise SnapshotInputError("a stored snapshot data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise SnapshotInputError("a stored snapshot policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            corpus_id = UUID(str(document["corpus_id"]))
            snapshot_id = UUID(str(document["snapshot_id"]))
        except ValueError as error:
            raise SnapshotInputError("a stored snapshot identity is not admitted") from error
        raw_entries = document["entries"]
        if not isinstance(raw_entries, list):
            raise SnapshotInputError("stored snapshot entries must be a JSON array")
        entries = tuple(SnapshotEntry.from_document(item) for item in raw_entries)
        return SnapshotManifest(
            workspace_id=workspace_id,
            corpus_id=corpus_id,
            corpus_key=_string_member(document, "corpus_key"),
            snapshot_id=snapshot_id,
            entries=entries,
            index_identity=_string_member(document, "index_identity"),
            ranking_identity=_string_member(document, "ranking_identity"),
            schema_version=_string_member(document, "schema_version"),
        ).validated()


@dataclass(frozen=True, slots=True)
class QuerySpec:
    """One deterministic evidence query bound to a frozen snapshot."""

    workspace_id: UUID
    snapshot_id: UUID
    query_id: UUID
    query_text: str
    normalized_query: str
    result_limit: int
    match_mode: MatchMode
    schema_version: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise RetrievalInputError("a workspace id must be a UUID value")
        if not isinstance(self.snapshot_id, UUID):
            raise RetrievalInputError("a snapshot id must be a UUID value")
        if not isinstance(self.query_id, UUID):
            raise RetrievalInputError("a query id must be a UUID value")
        query_text = _admit_query_text(self.query_text)
        normalized = normalize_query_text(query_text)
        if self.normalized_query != normalized:
            raise RetrievalInputError("a normalized query does not match its text")
        limit = _admit_result_limit(self.result_limit)
        if not isinstance(self.match_mode, MatchMode):
            raise RetrievalInputError("a match mode is not admitted here")
        schema_version = _admit_identifier(self.schema_version, "schema version")
        if schema_version != SCHEMA_VERSION:
            raise RetrievalInputError("a query schema version is not supported here")
        expected = query_id_for(
            self.workspace_id, self.snapshot_id, normalized, limit, self.match_mode
        )
        if self.query_id != expected:
            raise RetrievalInputError("a query identity does not match its semantics")
        return QuerySpec(
            workspace_id=self.workspace_id,
            snapshot_id=self.snapshot_id,
            query_id=self.query_id,
            query_text=query_text,
            normalized_query=normalized,
            result_limit=limit,
            match_mode=self.match_mode,
            schema_version=schema_version,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "match_mode": admitted.match_mode.value,
            "normalized_query": admitted.normalized_query,
            "policy_version": POLICY_VERSION,
            "query_id": str(admitted.query_id),
            "query_text": admitted.query_text,
            "result_limit": admitted.result_limit,
            "schema_version": admitted.schema_version,
            "snapshot_id": str(admitted.snapshot_id),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise RetrievalInputError("a stored query must be a JSON object")
        expected = {
            "data_class",
            "match_mode",
            "normalized_query",
            "policy_version",
            "query_id",
            "query_text",
            "result_limit",
            "schema_version",
            "snapshot_id",
            "workspace_id",
        }
        if set(document) != expected:
            raise RetrievalInputError("a stored query carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise RetrievalInputError("a stored query data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise RetrievalInputError("a stored query policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            snapshot_id = UUID(str(document["snapshot_id"]))
            query_id = UUID(str(document["query_id"]))
            match_mode = MatchMode(str(document["match_mode"]))
        except ValueError as error:
            raise RetrievalInputError("a stored query identity is not admitted") from error
        limit = document["result_limit"]
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise RetrievalInputError("a stored result limit must be an integer")
        return QuerySpec(
            workspace_id=workspace_id,
            snapshot_id=snapshot_id,
            query_id=query_id,
            query_text=_string_member(document, "query_text"),
            normalized_query=_string_member(document, "normalized_query"),
            result_limit=limit,
            match_mode=match_mode,
            schema_version=_string_member(document, "schema_version"),
        ).validated()


@dataclass(frozen=True, slots=True)
class ScoredResult:
    """One ranked retrieval hit with preserved source identity."""

    source_id: UUID
    source_revision: str
    source_date: str
    rank: int
    score: int
    text: str

    def validated(self):
        if not isinstance(self.source_id, UUID):
            raise RetrievalInputError("a result source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "result source revision")
        date = _admit_result_date(self.source_date)
        rank = _admit_rank(self.rank)
        score = _admit_score(self.score)
        text = _admit_evidence_text(self.text)
        return ScoredResult(
            source_id=self.source_id,
            source_revision=revision,
            source_date=date,
            rank=rank,
            score=score,
            text=text,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "rank": admitted.rank,
            "score": admitted.score,
            "source_date": admitted.source_date,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "text": admitted.text,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise RetrievalInputError("a stored result hit must be a JSON object")
        expected = {"rank", "score", "source_date", "source_id", "source_revision", "text"}
        if set(document) != expected:
            raise RetrievalInputError("a stored result hit carries unadmitted members")
        try:
            source_id = UUID(str(document["source_id"]))
        except ValueError as error:
            raise RetrievalInputError("a stored result source id is not admitted") from error
        for name in ("rank", "score"):
            value = document[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise RetrievalInputError(f"a stored result {name} must be an integer")
        return ScoredResult(
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            source_date=_string_member(document, "source_date"),
            rank=document["rank"],
            score=document["score"],
            text=_string_member(document, "text"),
        ).validated()


@dataclass(frozen=True, slots=True)
class ResultSet:
    """One immutable governed retrieval result bound to a query identity."""

    workspace_id: UUID
    query_id: UUID
    snapshot_id: UUID
    result_id: UUID
    results: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise RetrievalInputError("a workspace id must be a UUID value")
        if not isinstance(self.query_id, UUID):
            raise RetrievalInputError("a query id must be a UUID value")
        if not isinstance(self.snapshot_id, UUID):
            raise RetrievalInputError("a snapshot id must be a UUID value")
        if not isinstance(self.result_id, UUID):
            raise RetrievalInputError("a result id must be a UUID value")
        expected = result_id_for(self.query_id)
        if self.result_id != expected:
            raise RetrievalInputError("a result identity does not match its query")
        if not isinstance(self.results, tuple):
            raise RetrievalInputError("result hits must be a tuple")
        if len(self.results) > MAXIMUM_RESULTS:
            raise RetrievalInputError("a result set carries an unadmitted hit count")
        checked = tuple(
            item.validated() if isinstance(item, ScoredResult) else None for item in self.results
        )
        if any(item is None for item in checked):
            raise RetrievalInputError("result hits need ScoredResult instances")
        _check_result_order(checked)
        return ResultSet(
            workspace_id=self.workspace_id,
            query_id=self.query_id,
            snapshot_id=self.snapshot_id,
            result_id=self.result_id,
            results=checked,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
            "query_id": str(admitted.query_id),
            "result_id": str(admitted.result_id),
            "results": [item.to_document() for item in admitted.results],
            "snapshot_id": str(admitted.snapshot_id),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise RetrievalInputError("a stored result set must be a JSON object")
        expected = {
            "data_class",
            "policy_version",
            "query_id",
            "result_id",
            "results",
            "snapshot_id",
            "workspace_id",
        }
        if set(document) != expected:
            raise RetrievalInputError("a stored result set carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise RetrievalInputError("a stored result set data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise RetrievalInputError("a stored result set policy version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            query_id = UUID(str(document["query_id"]))
            snapshot_id = UUID(str(document["snapshot_id"]))
            result_id = UUID(str(document["result_id"]))
        except ValueError as error:
            raise RetrievalInputError("a stored result set identity is not admitted") from error
        raw_results = document["results"]
        if not isinstance(raw_results, list):
            raise RetrievalInputError("stored result hits must be a JSON array")
        results = tuple(ScoredResult.from_document(item) for item in raw_results)
        return ResultSet(
            workspace_id=workspace_id,
            query_id=query_id,
            snapshot_id=snapshot_id,
            result_id=result_id,
            results=results,
        ).validated()


def snapshot_id_for(workspace_id, corpus_id, entries):
    """Return the deterministic identity of one frozen snapshot member set."""
    if not isinstance(workspace_id, UUID):
        raise SnapshotInputError("a workspace id must be a UUID value")
    if not isinstance(corpus_id, UUID):
        raise SnapshotInputError("a corpus id must be a UUID value")
    member_lines = []
    for entry in entries:
        if not isinstance(entry, SnapshotEntry):
            raise SnapshotInputError("snapshot members need SnapshotEntry instances")
        checked = entry.validated()
        member_lines.append(
            ":".join((str(checked.source_id), checked.source_revision, checked.content_digest))
        )
    member_lines.sort()
    return uuid5(
        SNAPSHOT_NAMESPACE,
        ":".join((str(workspace_id), str(corpus_id), INDEX_IDENTITY, "\n".join(member_lines))),
    )


def query_id_for(workspace_id, snapshot_id, normalized_query, result_limit, match_mode):
    """Return the deterministic identity of one query semantics."""
    if not isinstance(workspace_id, UUID):
        raise RetrievalInputError("a workspace id must be a UUID value")
    if not isinstance(snapshot_id, UUID):
        raise RetrievalInputError("a snapshot id must be a UUID value")
    normalized = _admit_normalized_query(normalized_query)
    limit = _admit_result_limit(result_limit)
    if not isinstance(match_mode, MatchMode):
        raise RetrievalInputError("a match mode is not admitted here")
    return uuid5(
        QUERY_NAMESPACE,
        ":".join((str(workspace_id), str(snapshot_id), normalized, str(limit), match_mode.value)),
    )


def result_id_for(query_id):
    """Return the deterministic identity of one query result set."""
    if not isinstance(query_id, UUID):
        raise RetrievalInputError("a query id must be a UUID value")
    return uuid5(RESULT_NAMESPACE, str(query_id))


def snapshot_binding(workspace_id, snapshot_id):
    """Return the store binding of one snapshot manifest."""
    if not isinstance(workspace_id, UUID):
        raise SnapshotInputError("a workspace id must be a UUID value")
    if not isinstance(snapshot_id, UUID):
        raise SnapshotInputError("a snapshot id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=snapshot_id,
        object_type=WorkspaceObjectType.EVIDENCE_SNAPSHOT,
        object_revision=SNAPSHOT_REVISION,
    )


def query_binding(workspace_id, query_id):
    """Return the store binding of one query record."""
    if not isinstance(workspace_id, UUID):
        raise RetrievalInputError("a workspace id must be a UUID value")
    if not isinstance(query_id, UUID):
        raise RetrievalInputError("a query id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=query_id,
        object_type=WorkspaceObjectType.EVIDENCE_QUERY,
        object_revision=QUERY_REVISION,
    )


def result_binding(workspace_id, result_id):
    """Return the store binding of one result set."""
    if not isinstance(workspace_id, UUID):
        raise RetrievalInputError("a workspace id must be a UUID value")
    if not isinstance(result_id, UUID):
        raise RetrievalInputError("a result id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=result_id,
        object_type=WorkspaceObjectType.EVIDENCE_RESULT,
        object_revision=RESULT_REVISION,
    )


def normalize_query_text(query_text):
    """Return the deterministic normalized form of one query text."""
    admitted = _admit_query_text(query_text)
    tokens = _tokenize(admitted.lower())
    if not tokens:
        raise RetrievalInputError("a query must carry at least one token")
    return " ".join(tokens)


def admit_snapshot(store, trail, workspace_id, corpus_key, source_ids, actor_id, occurred_at):
    """Freeze one retrieval snapshot over admitted corpus sources."""
    if not isinstance(store, WorkspaceStore):
        raise SnapshotInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise SnapshotInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise SnapshotInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a snapshot crossed the workspace boundary")
    if not isinstance(source_ids, tuple) or not source_ids:
        raise SnapshotInputError("a snapshot needs a non-empty tuple of source ids")
    if len(source_ids) > MAXIMUM_SOURCES_PER_SNAPSHOT:
        raise SnapshotInputError("a snapshot carries an unadmitted source count")
    for source_id in source_ids:
        if not isinstance(source_id, UUID):
            raise SnapshotInputError("a snapshot source id must be a UUID value")
    if len(set(source_ids)) != len(source_ids):
        raise SnapshotInputError("a snapshot carries a duplicated source id")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    key = _admit_identifier(corpus_key, "corpus key")
    corpus_id = corpus_mod.corpus_id_for(workspace_id, key)
    entries = []
    for source_id in source_ids:
        try:
            source = corpus_mod.read_source(store, source_id)
        except corpus_mod.CorpusInputError as error:
            raise SnapshotError("a snapshot member source is absent in this store") from error
        if source.corpus_key != key:
            raise SnapshotError("a snapshot member belongs to another corpus")
        entries.append(
            SnapshotEntry(
                source_id=source.source_id,
                source_revision=source.source_revision,
                content_digest=source.content_digest,
            )
        )
    manifest = SnapshotManifest(
        workspace_id=workspace_id,
        corpus_id=corpus_id,
        corpus_key=key,
        snapshot_id=snapshot_id_for(workspace_id, corpus_id, entries),
        entries=tuple(entries),
        index_identity=INDEX_IDENTITY,
        ranking_identity=RANKING_IDENTITY,
        schema_version=SCHEMA_VERSION,
    ).validated()
    binding = snapshot_binding(workspace_id, manifest.snapshot_id)
    payload = _canonical_bytes(manifest.to_document())
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
    except StoreConflictError as error:
        raise SnapshotConflictError("the snapshot identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def execute_query(
    store, trail, snapshot_id, query_text, result_limit, match_mode, actor_id, occurred_at
):
    """Execute one admitted query against a frozen snapshot and store the result."""
    if not isinstance(store, WorkspaceStore):
        raise RetrievalInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise RetrievalInputError("an audit trail is required")
    if not isinstance(snapshot_id, UUID):
        raise RetrievalInputError("a snapshot id must be a UUID value")
    if not isinstance(match_mode, MatchMode):
        raise RetrievalInputError("a match mode is not admitted here")
    actor = _admit_actor(actor_id)
    moment = _admit_occurred_at(occurred_at)
    manifest = read_snapshot(store, snapshot_id)
    normalized = normalize_query_text(query_text)
    limit = _admit_result_limit(result_limit)
    query = QuerySpec(
        workspace_id=store.workspace_id,
        snapshot_id=manifest.snapshot_id,
        query_id=query_id_for(
            store.workspace_id, manifest.snapshot_id, normalized, limit, match_mode
        ),
        query_text=query_text,
        normalized_query=normalized,
        result_limit=limit,
        match_mode=match_mode,
        schema_version=SCHEMA_VERSION,
    ).validated()
    hits = _rank_sources(store, manifest, normalized, limit, match_mode)
    result = ResultSet(
        workspace_id=store.workspace_id,
        query_id=query.query_id,
        snapshot_id=manifest.snapshot_id,
        result_id=result_id_for(query.query_id),
        results=hits,
    ).validated()
    query_binding_value = query_binding(store.workspace_id, query.query_id)
    query_payload = _canonical_bytes(query.to_document())
    query_producer = ProducerIdentity(
        kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION
    )
    query_record = describe_revision(
        binding=query_binding_value,
        payload=query_payload,
        producer=query_producer,
        source_refs=(),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, query_record, query_payload)
    except StoreConflictError as error:
        raise RetrievalConflictError("the query identity already exists") from error
    result_binding_value = result_binding(store.workspace_id, result.result_id)
    result_payload = _canonical_bytes(result.to_document())
    result_record = describe_revision(
        binding=result_binding_value,
        payload=result_payload,
        producer=query_producer,
        source_refs=(),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, result_record, result_payload)
    except StoreConflictError as error:
        raise RetrievalConflictError("the result identity already exists") from error
    trail.record_object_write(
        binding=result_binding_value,
        payload=result_payload,
        actor_id=actor,
        occurred_at=moment,
    )
    trail.append(
        event_type=AuditEventType.EVIDENCE_QUERY,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=query.query_id,
                object_type=WorkspaceObjectType.EVIDENCE_QUERY,
                object_revision=QUERY_REVISION,
                content_digest=content_digest_of(query_payload),
            ),
            AuditObjectRef(
                object_id=result.result_id,
                object_type=WorkspaceObjectType.EVIDENCE_RESULT,
                object_revision=RESULT_REVISION,
                content_digest=content_digest_of(result_payload),
            ),
        ),
        metadata=(
            ("snapshot_id", str(manifest.snapshot_id)),
            ("match_mode", match_mode.value),
        ),
    )
    return result_binding_value


def replay_query(store, query_id):
    """Recompute one stored query result and refuse any divergence."""
    if not isinstance(store, WorkspaceStore):
        raise RetrievalInputError("a workspace store is required")
    if not isinstance(query_id, UUID):
        raise RetrievalInputError("a query id must be a UUID value")
    query = read_query(store, query_id)
    manifest = read_snapshot(store, query.snapshot_id)
    hits = _rank_sources(
        store, manifest, query.normalized_query, query.result_limit, query.match_mode
    )
    expected = ResultSet(
        workspace_id=store.workspace_id,
        query_id=query.query_id,
        snapshot_id=manifest.snapshot_id,
        result_id=result_id_for(query.query_id),
        results=hits,
    ).validated()
    stored = read_result(store, expected.result_id)
    if stored.to_document() != expected.to_document():
        raise RetrievalReplayError("a replayed result diverged from the stored result")
    return stored


def read_snapshot(store, snapshot_id):
    """Read and verify one stored snapshot manifest."""
    if not isinstance(store, WorkspaceStore):
        raise SnapshotInputError("a workspace store is required")
    if not isinstance(snapshot_id, UUID):
        raise SnapshotInputError("a snapshot id must be a UUID value")
    binding = snapshot_binding(store.workspace_id, snapshot_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise SnapshotInputError("the snapshot identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise SnapshotInputError("a stored snapshot is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise SnapshotInputError("a stored snapshot is not JSON") from error
    manifest = SnapshotManifest.from_document(document)
    if manifest.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a snapshot crossed the workspace boundary")
    if manifest.snapshot_id != snapshot_id:
        raise SnapshotInputError("a stored snapshot identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return manifest.validated()


def read_query(store, query_id):
    """Read and verify one stored query record."""
    if not isinstance(store, WorkspaceStore):
        raise RetrievalInputError("a workspace store is required")
    if not isinstance(query_id, UUID):
        raise RetrievalInputError("a query id must be a UUID value")
    binding = query_binding(store.workspace_id, query_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise RetrievalInputError("the query identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise RetrievalInputError("a stored query is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise RetrievalInputError("a stored query is not JSON") from error
    query = QuerySpec.from_document(document)
    if query.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a query crossed the workspace boundary")
    if query.query_id != query_id:
        raise RetrievalInputError("a stored query identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return query.validated()


def read_result(store, result_id):
    """Read and verify one stored result set."""
    if not isinstance(store, WorkspaceStore):
        raise RetrievalInputError("a workspace store is required")
    if not isinstance(result_id, UUID):
        raise RetrievalInputError("a result id must be a UUID value")
    binding = result_binding(store.workspace_id, result_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise RetrievalInputError("the result identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise RetrievalInputError("a stored result is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise RetrievalInputError("a stored result is not JSON") from error
    result = ResultSet.from_document(document)
    if result.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a result crossed the workspace boundary")
    if result.result_id != result_id:
        raise RetrievalInputError("a stored result identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return result.validated()


def _rank_sources(store, manifest, normalized_query, result_limit, match_mode):
    query_tokens = normalized_query.split(" ")
    scored = []
    for entry in manifest.entries:
        try:
            source = corpus_mod.read_source(store, entry.source_id)
        except corpus_mod.CorpusInputError as error:
            raise RetrievalReplayError(
                "a snapshot member source is absent in this store"
            ) from error
        if source.source_revision != entry.source_revision:
            raise RetrievalReplayError("a snapshot member source revision changed")
        if source.content_digest != entry.content_digest:
            raise RetrievalReplayError("a snapshot member source content changed")
        source_tokens = _tokenize(source.text.lower())
        overlap = 0
        for token in query_tokens:
            if token in source_tokens:
                overlap += 1
        if match_mode is MatchMode.ALL and overlap != len(query_tokens):
            continue
        if match_mode is MatchMode.ANY and overlap == 0:
            continue
        scored.append((overlap, str(source.source_id), source))
    scored.sort(key=lambda item: (-item[0], item[1]))
    hits = []
    for position, (overlap, _, source) in enumerate(scored[:result_limit], start=1):
        hits.append(
            ScoredResult(
                source_id=source.source_id,
                source_revision=source.source_revision,
                source_date=source.source_date,
                rank=position,
                score=overlap,
                text=source.text,
            )
        )
    return tuple(hits)


def _tokenize(text):
    tokens = []
    current = []
    for character in text:
        if "a" <= character <= "z" or "0" <= character <= "9":
            current.append(character)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _check_duplicate_source_ids(entries):
    seen = set()
    for item in entries:
        if item.source_id in seen:
            raise SnapshotInputError("a snapshot carries a duplicated source id")
        seen.add(item.source_id)


def _check_result_order(results):
    for position, item in enumerate(results, start=1):
        if item.rank != position:
            raise RetrievalInputError("result ranks must be dense from one")
    for index in range(1, len(results)):
        first = results[index - 1]
        second = results[index]
        if (-first.score, str(first.source_id)) > (-second.score, str(second.source_id)):
            raise RetrievalInputError("result hits must be ordered by score then source")


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise RetrievalInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise RetrievalInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise RetrievalInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise RetrievalInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise RetrievalInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise SnapshotInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise SnapshotInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_query_text(raw):
    if not isinstance(raw, str):
        raise RetrievalInputError("query text must be a string")
    value = raw.strip()
    if not value:
        raise RetrievalInputError("query text must be non-empty")
    if len(value) > MAXIMUM_QUERY_CHARS:
        raise RetrievalInputError("query text is longer than the admitted maximum")
    if not value.isascii():
        raise RetrievalInputError("query text must be ASCII")
    for character in value:
        if character in ("\n", "\t", " "):
            continue
        if not character.isprintable():
            raise RetrievalInputError("query text must not contain control characters")
    return value


def _admit_normalized_query(raw):
    if not isinstance(raw, str):
        raise RetrievalInputError("a normalized query must be a string")
    value = raw.strip()
    if not value:
        raise RetrievalInputError("a normalized query must be non-empty")
    if not value.isascii():
        raise RetrievalInputError("a normalized query must be ASCII")
    for character in value:
        if character == " " or "a" <= character <= "z" or "0" <= character <= "9":
            continue
        raise RetrievalInputError("a normalized query carries unadmitted characters")
    return value


def _admit_result_limit(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RetrievalInputError("a result limit must be an integer")
    if raw < 1 or raw > MAXIMUM_RESULTS:
        raise RetrievalInputError("a result limit is outside the admitted range")
    return raw


def _admit_rank(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RetrievalInputError("a result rank must be an integer")
    if raw < 1:
        raise RetrievalInputError("a result rank starts at one")
    return raw


def _admit_score(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RetrievalInputError("a result score must be an integer")
    if raw < 0:
        raise RetrievalInputError("a result score must not be negative")
    return raw


def _admit_result_date(raw):
    if not isinstance(raw, str):
        raise RetrievalInputError("a result source date must be a string")
    value = raw.strip()
    if value == "":
        return ""
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        raise RetrievalInputError("a result source date must be empty or YYYY-MM-DD")
    for index in (0, 1, 2, 3, 5, 6, 8, 9):
        if value[index] not in "0123456789":
            raise RetrievalInputError("a result source date must be empty or YYYY-MM-DD")
    return value


def _admit_evidence_text(raw):
    if not isinstance(raw, str):
        raise RetrievalInputError("evidence text must be a string")
    value = raw.strip()
    if not value:
        raise RetrievalInputError("evidence text must be non-empty")
    if len(value) > 4096:
        raise RetrievalInputError("evidence text is longer than the admitted maximum")
    if not value.isascii():
        raise RetrievalInputError("evidence text must be ASCII")
    for character in value:
        if character in ("\n", "\t"):
            continue
        if not character.isprintable():
            raise RetrievalInputError("evidence text must not contain control characters")
    return value


def _admit_actor(raw):
    return _admit_identifier(raw, "actor id")


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise RetrievalInputError("a retrieval occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise RetrievalInputError("a retrieval occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise RetrievalInputError("a retrieval occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise RetrievalInputError(
            "a retrieval occurrence time must be an ISO-8601 instant with a zone"
        )
    if not value.isascii():
        raise RetrievalInputError("a retrieval occurrence time must be ASCII")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise RetrievalInputError(f"a stored {name} must be a string")
    return value
