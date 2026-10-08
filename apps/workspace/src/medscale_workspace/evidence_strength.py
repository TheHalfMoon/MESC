"""Claim-source and evidence-strength layer for CW-010.

An answer decomposes into claims. Each claim carries unresolved citation strings
and, separately, explicit claim-source links. A citation string alone proves
nothing: ``CITATION_PRESENT`` means a citation string was recorded while
``SOURCE_LINKED`` means a stored link object binds the claim to one admitted
corpus source revision inside one frozen snapshot. Only ``SOURCE_LINKED``
evidence may decide a strength verdict, and even linked evidence decides nothing
automatically.

A strength assessment records one verdict per claim from an admitted vocabulary
that is never collapsed:

* ``SUPPORTED`` needs at least one fresh supporting link and no contradiction;
* ``PARTIALLY_SUPPORTED`` needs fresh partial support, no full support, and no
  contradiction;
* ``CONTRADICTED`` records at least one contradicting link and dominates every
  positive verdict;
* ``UNKNOWN`` is a first-class decided state for inconclusive or stale evidence;
* ``MISSING_EVIDENCE`` records that no linked source exists;
* ``ABSTAINED`` records an explicit refusal to decide;
* ``FAILED`` records an explicit assessment failure.

Every verdict rule is checked mechanically at assessment time and re-checked at
read time. A ``SUPPORTED`` verdict refused for stale, undated, partial-only,
contradicted, unlinked, or citation-only evidence fails closed instead of
promoting the claim.

Source freshness is represented per link from the corpus source date and the
assessment date with an explicit freshness limit in days. The evidence method
and method version are bound into every assessment identity; an unadmitted
method or version is refused.

Corpus content is untrusted data. Evidence text is stored and returned verbatim
and is never evaluated, never executed, and never consulted for capability,
policy, or governance decisions. Link stances are explicit caller-supplied
parameters validated against admitted identities, never text judgments. No
network, retrieval-connector, model, or execution capability exists in this
module, and none may be added under this unit.

Research Core machinery belongs to a different trust domain and is deliberately
not imported here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace import corpus as corpus_mod
from medscale_workspace import retrieval as retrieval_mod
from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    ClaimConflictError,
    ClaimInputError,
    ClaimRevisionError,
    LinkConflictError,
    LinkInputError,
    LinkRevisionError,
    ObjectNotFoundError,
    StoreConflictError,
    StrengthConflictError,
    StrengthInputError,
    StrengthReplayError,
    StrengthVerdictError,
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

CLAIM_SET_NAMESPACE = UUID("db63e1a6-e1c8-44e4-8f00-ad6a361c88a3")
LINK_NAMESPACE = UUID("9812f653-35cd-4382-8bf6-3524eb38bed1")
ASSESSMENT_NAMESPACE = UUID("69979fa1-7804-482e-8ee6-944d3cfb4db7")
CLAIM_SET_REVISION = "claim-set-00000001"
LINK_REVISION = "claim-link-00000001"
ASSESSMENT_REVISION = "assessment-00000001"
PRODUCER_VERSION = "cw010-v1"
EVIDENCE_METHOD = "cw010-deterministic-link-verdict"
EVIDENCE_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw010-evidence-strength/1"
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_ANSWER_CHARS = 4096
MAXIMUM_CLAIM_CHARS = 1024
MAXIMUM_CITATION_CHARS = 256
MAXIMUM_CLAIMS_PER_SET = 64
MAXIMUM_CITATIONS_PER_CLAIM = 16
MAXIMUM_LINKS_PER_ASSESSMENT = 64
MAXIMUM_REASON_CHARS = 128
MAXIMUM_OCCURRED_AT_CHARS = 64
MAXIMUM_FRESHNESS_LIMIT_DAYS = 3650


class CitationState(StrEnum):
    """Resolution state of one recorded citation. Never collapsed."""

    CITATION_PRESENT = "citation_present"
    SOURCE_LINKED = "source_linked"


class LinkStance(StrEnum):
    """Admitted relation between one linked source and one claim."""

    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    NO_RELATION = "no_relation"


class StrengthVerdict(StrEnum):
    """Admitted strength verdict of one assessed claim. Never collapsed."""

    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"
    MISSING_EVIDENCE = "missing_evidence"
    ABSTAINED = "abstained"
    FAILED = "failed"


class FreshnessState(StrEnum):
    """Admitted freshness state of one linked source at assessment time."""

    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN_DATE = "unknown_date"


class UnknownReason(StrEnum):
    """Admitted reasons for an UNKNOWN verdict. Distinct from abstention."""

    INCONCLUSIVE_EVIDENCE = "inconclusive_evidence"
    EVIDENCE_TOO_STALE = "evidence_too_stale"


class MissingReason(StrEnum):
    """Admitted reasons for a MISSING_EVIDENCE verdict."""

    NO_CITATIONS = "no_citations"
    ONLY_UNRESOLVED_CITATIONS = "only_unresolved_citations"
    NO_LINKED_SOURCES = "no_linked_sources"


class AbstainReason(StrEnum):
    """Admitted reasons for an ABSTAINED verdict. Distinct from unknown."""

    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    OUT_OF_SCOPE = "out_of_scope"
    OPERATOR_ABSTAIN = "operator_abstain"


class FailureReason(StrEnum):
    """Admitted reasons for a FAILED verdict. Distinct from abstention."""

    EVIDENCE_VALIDATION_FAILED = "evidence_validation_failed"
    SOURCE_READ_FAILED = "source_read_failed"


@dataclass(frozen=True, slots=True)
class ClaimCitation:
    """One unresolved citation string recorded on a claim.

    A citation stored here is CITATION_PRESENT by construction: it names a
    source without binding one. Only a stored ClaimSourceLink object counts as
    SOURCE_LINKED evidence, and citation strings never decide a verdict.
    """

    citation_text: str
    state: CitationState

    def validated(self):
        citation_text = _admit_citation_text(self.citation_text)
        if not isinstance(self.state, CitationState):
            raise ClaimInputError("a citation state is not admitted here")
        if self.state is not CitationState.CITATION_PRESENT:
            raise ClaimInputError("a stored claim citation is never a resolved link")
        return ClaimCitation(citation_text=citation_text, state=self.state)

    def to_document(self):
        admitted = self.validated()
        return {
            "citation_text": admitted.citation_text,
            "state": admitted.state.value,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ClaimInputError("a stored citation must be a JSON object")
        expected = {"citation_text", "state"}
        if set(document) != expected:
            raise ClaimInputError("a stored citation carries unadmitted members")
        try:
            state = CitationState(str(document["state"]))
        except ValueError as error:
            raise ClaimInputError("a stored citation state is not admitted") from error
        return ClaimCitation(
            citation_text=_string_member(document, "citation_text"),
            state=state,
        ).validated()


@dataclass(frozen=True, slots=True)
class Claim:
    """One atomic claim decomposed from an answer, with unresolved citations."""

    claim_id: UUID
    claim_index: int
    claim_text: str
    citations: tuple

    def validated(self):
        if not isinstance(self.claim_id, UUID):
            raise ClaimInputError("a claim id must be a UUID value")
        claim_index = _admit_claim_index(self.claim_index)
        claim_text = _admit_claim_text(self.claim_text)
        if not isinstance(self.citations, tuple):
            raise ClaimInputError("claim citations must be a tuple")
        if len(self.citations) > MAXIMUM_CITATIONS_PER_CLAIM:
            raise ClaimInputError("a claim carries an unadmitted citation count")
        checked = tuple(
            item.validated() if isinstance(item, ClaimCitation) else None for item in self.citations
        )
        if any(item is None for item in checked):
            raise ClaimInputError("claim citations need ClaimCitation instances")
        _check_duplicate_citation_texts(checked)
        return Claim(
            claim_id=self.claim_id,
            claim_index=claim_index,
            claim_text=claim_text,
            citations=checked,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "citations": [item.to_document() for item in admitted.citations],
            "claim_id": str(admitted.claim_id),
            "claim_index": admitted.claim_index,
            "claim_text": admitted.claim_text,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ClaimInputError("a stored claim must be a JSON object")
        expected = {"citations", "claim_id", "claim_index", "claim_text"}
        if set(document) != expected:
            raise ClaimInputError("a stored claim carries unadmitted members")
        try:
            claim_id = UUID(str(document["claim_id"]))
        except ValueError as error:
            raise ClaimInputError("a stored claim id is not admitted") from error
        claim_index = document["claim_index"]
        if isinstance(claim_index, bool) or not isinstance(claim_index, int):
            raise ClaimInputError("a stored claim index must be an integer")
        raw_citations = document["citations"]
        if not isinstance(raw_citations, list):
            raise ClaimInputError("stored claim citations must be a JSON array")
        citations = tuple(ClaimCitation.from_document(item) for item in raw_citations)
        return Claim(
            claim_id=claim_id,
            claim_index=claim_index,
            claim_text=_string_member(document, "claim_text"),
            citations=citations,
        ).validated()


@dataclass(frozen=True, slots=True)
class ClaimSet:
    """One deterministic decomposition of an answer into claims."""

    workspace_id: UUID
    set_id: UUID
    answer_text: str
    claims: tuple

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise ClaimInputError("a workspace id must be a UUID value")
        if not isinstance(self.set_id, UUID):
            raise ClaimInputError("a claim-set id must be a UUID value")
        answer_text = _admit_answer_text(self.answer_text)
        if not isinstance(self.claims, tuple):
            raise ClaimInputError("claim-set claims must be a tuple")
        if len(self.claims) < 1 or len(self.claims) > MAXIMUM_CLAIMS_PER_SET:
            raise ClaimInputError("a claim set carries an unadmitted claim count")
        checked = tuple(
            item.validated() if isinstance(item, Claim) else None for item in self.claims
        )
        if any(item is None for item in checked):
            raise ClaimInputError("claim-set claims need Claim instances")
        expected_ids = tuple(
            claim_id_for(self.workspace_id, self.set_id, position, item.claim_text)
            for position, item in enumerate(checked)
        )
        for position, item in enumerate(checked):
            if item.claim_index != position:
                raise ClaimInputError("claim indexes must be dense from zero")
            if item.claim_id != expected_ids[position]:
                raise ClaimRevisionError("a claim identity does not match its lineage")
        expected_set = claim_set_id_for(self.workspace_id, answer_text)
        if self.set_id != expected_set:
            raise ClaimRevisionError("a claim-set identity does not match its answer")
        return ClaimSet(
            workspace_id=self.workspace_id,
            set_id=self.set_id,
            answer_text=answer_text,
            claims=checked,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "answer_text": admitted.answer_text,
            "claims": [item.to_document() for item in admitted.claims],
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
            "schema_version": SCHEMA_VERSION,
            "set_id": str(admitted.set_id),
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ClaimInputError("a stored claim set must be a JSON object")
        expected = {
            "answer_text",
            "claims",
            "data_class",
            "policy_version",
            "schema_version",
            "set_id",
            "workspace_id",
        }
        if set(document) != expected:
            raise ClaimInputError("a stored claim set carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise ClaimInputError("a stored claim-set data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise ClaimInputError("a stored claim-set policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise ClaimInputError("a stored claim-set schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            set_id = UUID(str(document["set_id"]))
        except ValueError as error:
            raise ClaimInputError("a stored claim-set identity is not admitted") from error
        raw_claims = document["claims"]
        if not isinstance(raw_claims, list):
            raise ClaimInputError("stored claim-set claims must be a JSON array")
        claims = tuple(Claim.from_document(item) for item in raw_claims)
        return ClaimSet(
            workspace_id=workspace_id,
            set_id=set_id,
            answer_text=_string_member(document, "answer_text"),
            claims=claims,
        ).validated()


@dataclass(frozen=True, slots=True)
class ClaimSourceLink:
    """One explicit SOURCE_LINKED binding between a claim and an evidence source.

    The link binds the claim to one corpus source revision inside one frozen
    snapshot, with an optional query/result context and an optional character
    range. The stance is an explicit caller-supplied parameter validated against
    admitted identities; evidence text is never read to decide it.
    """

    workspace_id: UUID
    set_id: UUID
    link_id: UUID
    claim_id: UUID
    source_id: UUID
    source_revision: str
    content_digest: str
    source_date: str
    snapshot_id: UUID
    query_id: UUID | None
    result_id: UUID | None
    stance: LinkStance
    citation_state: CitationState
    citation_text: str
    char_start: int
    char_end: int

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise LinkInputError("a workspace id must be a UUID value")
        if not isinstance(self.set_id, UUID):
            raise LinkInputError("a claim-set id must be a UUID value")
        if not isinstance(self.link_id, UUID):
            raise LinkInputError("a link id must be a UUID value")
        if not isinstance(self.claim_id, UUID):
            raise LinkInputError("a claim id must be a UUID value")
        if not isinstance(self.source_id, UUID):
            raise LinkInputError("a link source id must be a UUID value")
        revision = _admit_identifier(self.source_revision, "source revision", LinkInputError)
        digest = _admit_digest(self.content_digest)
        source_date = _admit_source_date(self.source_date, LinkInputError)
        if not isinstance(self.snapshot_id, UUID):
            raise LinkInputError("a link snapshot id must be a UUID value")
        query_id = _admit_optional_uuid(self.query_id, "query id")
        result_id = _admit_optional_uuid(self.result_id, "result id")
        if (query_id is None) != (result_id is None):
            raise LinkInputError("a link query context needs both query and result")
        if not isinstance(self.stance, LinkStance):
            raise LinkInputError("a link stance is not admitted here")
        if not isinstance(self.citation_state, CitationState):
            raise LinkInputError("a link citation state is not admitted here")
        if self.citation_state is not CitationState.SOURCE_LINKED:
            raise LinkInputError("a stored link is always a resolved source binding")
        citation_text = _admit_optional_citation(self.citation_text)
        char_start = _admit_range_bound(self.char_start, "char start")
        char_end = _admit_range_bound(self.char_end, "char end")
        if (char_start < 0) != (char_end < 0):
            raise LinkInputError("a link range needs both bounds or neither")
        if char_start >= 0 and char_end <= char_start:
            raise LinkInputError("a link range end must be after its start")
        expected = link_id_for(
            self.workspace_id,
            self.set_id,
            self.claim_id,
            self.source_id,
            revision,
            self.snapshot_id,
            query_id,
            result_id,
            self.stance,
            citation_text,
            char_start,
            char_end,
        )
        if self.link_id != expected:
            raise LinkRevisionError("a link identity does not match its bindings")
        return ClaimSourceLink(
            workspace_id=self.workspace_id,
            set_id=self.set_id,
            link_id=self.link_id,
            claim_id=self.claim_id,
            source_id=self.source_id,
            source_revision=revision,
            content_digest=digest,
            source_date=source_date,
            snapshot_id=self.snapshot_id,
            query_id=query_id,
            result_id=result_id,
            stance=self.stance,
            citation_state=self.citation_state,
            citation_text=citation_text,
            char_start=char_start,
            char_end=char_end,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "char_end": admitted.char_end,
            "char_start": admitted.char_start,
            "citation_state": admitted.citation_state.value,
            "citation_text": admitted.citation_text,
            "claim_id": str(admitted.claim_id),
            "content_digest": admitted.content_digest,
            "data_class": synthetic_data_class_value(),
            "link_id": str(admitted.link_id),
            "policy_version": POLICY_VERSION,
            "query_id": "" if admitted.query_id is None else str(admitted.query_id),
            "result_id": "" if admitted.result_id is None else str(admitted.result_id),
            "schema_version": SCHEMA_VERSION,
            "set_id": str(admitted.set_id),
            "snapshot_id": str(admitted.snapshot_id),
            "source_date": admitted.source_date,
            "source_id": str(admitted.source_id),
            "source_revision": admitted.source_revision,
            "stance": admitted.stance.value,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise LinkInputError("a stored link must be a JSON object")
        expected = {
            "char_end",
            "char_start",
            "citation_state",
            "citation_text",
            "claim_id",
            "content_digest",
            "data_class",
            "link_id",
            "policy_version",
            "query_id",
            "result_id",
            "schema_version",
            "set_id",
            "snapshot_id",
            "source_date",
            "source_id",
            "source_revision",
            "stance",
            "workspace_id",
        }
        if set(document) != expected:
            raise LinkInputError("a stored link carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise LinkInputError("a stored link data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise LinkInputError("a stored link policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise LinkInputError("a stored link schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            set_id = UUID(str(document["set_id"]))
            link_id = UUID(str(document["link_id"]))
            claim_id = UUID(str(document["claim_id"]))
            source_id = UUID(str(document["source_id"]))
            snapshot_id = UUID(str(document["snapshot_id"]))
            stance = LinkStance(str(document["stance"]))
            citation_state = CitationState(str(document["citation_state"]))
        except ValueError as error:
            raise LinkInputError("a stored link identity is not admitted") from error
        query_id = _optional_uuid_member(document, "query_id")
        result_id = _optional_uuid_member(document, "result_id")
        char_start = _integer_member(document, "char_start")
        char_end = _integer_member(document, "char_end")
        return ClaimSourceLink(
            workspace_id=workspace_id,
            set_id=set_id,
            link_id=link_id,
            claim_id=claim_id,
            source_id=source_id,
            source_revision=_string_member(document, "source_revision"),
            content_digest=_string_member(document, "content_digest"),
            source_date=_string_member(document, "source_date"),
            snapshot_id=snapshot_id,
            query_id=query_id,
            result_id=result_id,
            stance=stance,
            citation_state=citation_state,
            citation_text=_string_member(document, "citation_text"),
            char_start=char_start,
            char_end=char_end,
        ).validated()


@dataclass(frozen=True, slots=True)
class LinkFreshness:
    """The represented freshness of one linked source at assessment time."""

    link_id: UUID
    state: FreshnessState

    def validated(self):
        if not isinstance(self.link_id, UUID):
            raise StrengthInputError("a freshness link id must be a UUID value")
        if not isinstance(self.state, FreshnessState):
            raise StrengthInputError("a freshness state is not admitted here")
        return LinkFreshness(link_id=self.link_id, state=self.state)

    def to_document(self):
        admitted = self.validated()
        return {"link_id": str(admitted.link_id), "state": admitted.state.value}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise StrengthInputError("stored freshness must be a JSON object")
        expected = {"link_id", "state"}
        if set(document) != expected:
            raise StrengthInputError("stored freshness carries unadmitted members")
        try:
            link_id = UUID(str(document["link_id"]))
            state = FreshnessState(str(document["state"]))
        except ValueError as error:
            raise StrengthInputError("stored freshness is not admitted") from error
        return LinkFreshness(link_id=link_id, state=state).validated()


@dataclass(frozen=True, slots=True)
class Assessment:
    """One deterministic strength verdict for one claim over explicit links."""

    workspace_id: UUID
    set_id: UUID
    claim_id: UUID
    assessment_id: UUID
    verdict: StrengthVerdict
    evidence_method: str
    evidence_method_version: str
    assessed_at: str
    assessed_date: str
    freshness_limit_days: int
    link_ids: tuple
    freshness: tuple
    reason: str

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise StrengthInputError("a workspace id must be a UUID value")
        if not isinstance(self.set_id, UUID):
            raise StrengthInputError("a claim-set id must be a UUID value")
        if not isinstance(self.claim_id, UUID):
            raise StrengthInputError("a claim id must be a UUID value")
        if not isinstance(self.assessment_id, UUID):
            raise StrengthInputError("an assessment id must be a UUID value")
        if not isinstance(self.verdict, StrengthVerdict):
            raise StrengthInputError("an assessment verdict is not admitted here")
        evidence_method = _admit_identifier(
            self.evidence_method, "evidence method", StrengthInputError
        )
        if evidence_method != EVIDENCE_METHOD:
            raise StrengthInputError("an evidence method is not admitted here")
        method_version = _admit_identifier(
            self.evidence_method_version, "evidence method version", StrengthInputError
        )
        if method_version != EVIDENCE_METHOD_VERSION:
            raise StrengthInputError("an evidence method version is not admitted here")
        assessed_at = _admit_occurred_at(self.assessed_at, StrengthInputError)
        assessed_date = _admit_assessment_date(self.assessed_date)
        if assessed_date != assessed_at[:10]:
            raise StrengthInputError("an assessed date must match its instant")
        freshness_limit_days = _admit_freshness_limit(self.freshness_limit_days)
        if not isinstance(self.link_ids, tuple):
            raise StrengthInputError("assessment link ids must be a tuple")
        if len(self.link_ids) > MAXIMUM_LINKS_PER_ASSESSMENT:
            raise StrengthInputError("an assessment carries an unadmitted link count")
        for link_id in self.link_ids:
            if not isinstance(link_id, UUID):
                raise StrengthInputError("an assessment link id must be a UUID value")
        if len(set(self.link_ids)) != len(self.link_ids):
            raise StrengthInputError("an assessment carries a duplicated link id")
        if not isinstance(self.freshness, tuple):
            raise StrengthInputError("assessment freshness must be a tuple")
        checked_freshness = tuple(
            item.validated() if isinstance(item, LinkFreshness) else None for item in self.freshness
        )
        if any(item is None for item in checked_freshness):
            raise StrengthInputError("assessment freshness needs LinkFreshness instances")
        if tuple(item.link_id for item in checked_freshness) != self.link_ids:
            raise StrengthInputError("assessment freshness must cover every link in order")
        reason = _admit_reason(self.verdict, self.reason)
        expected = assessment_id_for(
            self.workspace_id,
            self.claim_id,
            self.verdict,
            evidence_method,
            method_version,
            assessed_date,
            freshness_limit_days,
            self.link_ids,
            reason,
        )
        if self.assessment_id != expected:
            raise StrengthInputError("an assessment identity does not match its verdict")
        return Assessment(
            workspace_id=self.workspace_id,
            set_id=self.set_id,
            claim_id=self.claim_id,
            assessment_id=self.assessment_id,
            verdict=self.verdict,
            evidence_method=evidence_method,
            evidence_method_version=method_version,
            assessed_at=assessed_at,
            assessed_date=assessed_date,
            freshness_limit_days=freshness_limit_days,
            link_ids=self.link_ids,
            freshness=checked_freshness,
            reason=reason,
        )

    def to_document(self):
        admitted = self.validated()
        return {
            "assessed_at": admitted.assessed_at,
            "assessed_date": admitted.assessed_date,
            "assessment_id": str(admitted.assessment_id),
            "claim_id": str(admitted.claim_id),
            "data_class": synthetic_data_class_value(),
            "evidence_method": admitted.evidence_method,
            "evidence_method_version": admitted.evidence_method_version,
            "freshness": [item.to_document() for item in admitted.freshness],
            "freshness_limit_days": admitted.freshness_limit_days,
            "link_ids": [str(link_id) for link_id in admitted.link_ids],
            "policy_version": POLICY_VERSION,
            "reason": admitted.reason,
            "schema_version": SCHEMA_VERSION,
            "set_id": str(admitted.set_id),
            "verdict": admitted.verdict.value,
            "workspace_id": str(admitted.workspace_id),
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise StrengthInputError("a stored assessment must be a JSON object")
        expected = {
            "assessed_at",
            "assessed_date",
            "assessment_id",
            "claim_id",
            "data_class",
            "evidence_method",
            "evidence_method_version",
            "freshness",
            "freshness_limit_days",
            "link_ids",
            "policy_version",
            "reason",
            "schema_version",
            "set_id",
            "verdict",
            "workspace_id",
        }
        if set(document) != expected:
            raise StrengthInputError("a stored assessment carries unadmitted members")
        if document["data_class"] != synthetic_data_class_value():
            raise StrengthInputError("a stored assessment data class is not admitted")
        if document["policy_version"] != POLICY_VERSION:
            raise StrengthInputError("a stored assessment policy version is not supported")
        if document["schema_version"] != SCHEMA_VERSION:
            raise StrengthInputError("a stored assessment schema version is not supported")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
            set_id = UUID(str(document["set_id"]))
            claim_id = UUID(str(document["claim_id"]))
            assessment_id = UUID(str(document["assessment_id"]))
            verdict = StrengthVerdict(str(document["verdict"]))
        except ValueError as error:
            raise StrengthInputError("a stored assessment identity is not admitted") from error
        raw_link_ids = document["link_ids"]
        if not isinstance(raw_link_ids, list):
            raise StrengthInputError("stored assessment link ids must be a JSON array")
        link_ids = tuple(_parse_uuid_member(value) for value in raw_link_ids)
        raw_freshness = document["freshness"]
        if not isinstance(raw_freshness, list):
            raise StrengthInputError("stored assessment freshness must be a JSON array")
        freshness = tuple(LinkFreshness.from_document(item) for item in raw_freshness)
        freshness_limit_days = document["freshness_limit_days"]
        if isinstance(freshness_limit_days, bool) or not isinstance(freshness_limit_days, int):
            raise StrengthInputError("a stored freshness limit must be an integer")
        return Assessment(
            workspace_id=workspace_id,
            set_id=set_id,
            claim_id=claim_id,
            assessment_id=assessment_id,
            verdict=verdict,
            evidence_method=_string_member(document, "evidence_method"),
            evidence_method_version=_string_member(document, "evidence_method_version"),
            assessed_at=_string_member(document, "assessed_at"),
            assessed_date=_string_member(document, "assessed_date"),
            freshness_limit_days=freshness_limit_days,
            link_ids=link_ids,
            freshness=freshness,
            reason=_string_member(document, "reason"),
        ).validated()


def claim_set_id_for(workspace_id, answer_text):
    """Return the deterministic identity of one answer decomposition."""
    if not isinstance(workspace_id, UUID):
        raise ClaimInputError("a workspace id must be a UUID value")
    admitted = _admit_answer_text(answer_text)
    return uuid5(CLAIM_SET_NAMESPACE, ":".join((str(workspace_id), admitted)))


def claim_id_for(workspace_id, set_id, claim_index, claim_text):
    """Return the deterministic identity of one claim inside a claim set."""
    if not isinstance(workspace_id, UUID):
        raise ClaimInputError("a workspace id must be a UUID value")
    if not isinstance(set_id, UUID):
        raise ClaimInputError("a claim-set id must be a UUID value")
    index = _admit_claim_index(claim_index)
    admitted = _admit_claim_text(claim_text)
    return uuid5(
        CLAIM_SET_NAMESPACE,
        ":".join((str(workspace_id), str(set_id), str(index), admitted)),
    )


def link_id_for(
    workspace_id,
    set_id,
    claim_id,
    source_id,
    source_revision,
    snapshot_id,
    query_id,
    result_id,
    stance,
    citation_text,
    char_start,
    char_end,
):
    """Return the deterministic identity of one claim-source link."""
    if not isinstance(workspace_id, UUID):
        raise LinkInputError("a workspace id must be a UUID value")
    if not isinstance(set_id, UUID):
        raise LinkInputError("a claim-set id must be a UUID value")
    if not isinstance(claim_id, UUID):
        raise LinkInputError("a claim id must be a UUID value")
    if not isinstance(source_id, UUID):
        raise LinkInputError("a link source id must be a UUID value")
    revision = _admit_identifier(source_revision, "source revision", LinkInputError)
    if not isinstance(snapshot_id, UUID):
        raise LinkInputError("a link snapshot id must be a UUID value")
    query_id = _admit_optional_uuid(query_id, "query id")
    result_id = _admit_optional_uuid(result_id, "result id")
    if not isinstance(stance, LinkStance):
        raise LinkInputError("a link stance is not admitted here")
    citation_text = _admit_optional_citation(citation_text)
    char_start = _admit_range_bound(char_start, "char start")
    char_end = _admit_range_bound(char_end, "char end")
    query_part = "" if query_id is None else str(query_id)
    result_part = "" if result_id is None else str(result_id)
    return uuid5(
        LINK_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(set_id),
                str(claim_id),
                str(source_id),
                revision,
                str(snapshot_id),
                query_part,
                result_part,
                stance.value,
                citation_text,
                str(char_start),
                str(char_end),
            )
        ),
    )


def assessment_id_for(
    workspace_id,
    claim_id,
    verdict,
    evidence_method,
    evidence_method_version,
    assessed_date,
    freshness_limit_days,
    link_ids,
    reason,
):
    """Return the deterministic identity of one strength assessment."""
    if not isinstance(workspace_id, UUID):
        raise StrengthInputError("a workspace id must be a UUID value")
    if not isinstance(claim_id, UUID):
        raise StrengthInputError("a claim id must be a UUID value")
    if not isinstance(verdict, StrengthVerdict):
        raise StrengthInputError("an assessment verdict is not admitted here")
    method = _admit_identifier(evidence_method, "evidence method", StrengthInputError)
    version = _admit_identifier(
        evidence_method_version, "evidence method version", StrengthInputError
    )
    assessed_date = _admit_assessment_date(assessed_date)
    freshness_limit_days = _admit_freshness_limit(freshness_limit_days)
    if not isinstance(link_ids, tuple):
        raise StrengthInputError("assessment link ids must be a tuple")
    for link_id in link_ids:
        if not isinstance(link_id, UUID):
            raise StrengthInputError("an assessment link id must be a UUID value")
    reason = _admit_reason(verdict, reason)
    link_lines = "\n".join(str(link_id) for link_id in link_ids)
    return uuid5(
        ASSESSMENT_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(claim_id),
                verdict.value,
                method,
                version,
                assessed_date,
                str(freshness_limit_days),
                link_lines,
                reason,
            )
        ),
    )


def claim_set_binding(workspace_id, set_id):
    """Return the store binding of one claim set."""
    if not isinstance(workspace_id, UUID):
        raise ClaimInputError("a workspace id must be a UUID value")
    if not isinstance(set_id, UUID):
        raise ClaimInputError("a claim-set id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=set_id,
        object_type=WorkspaceObjectType.EVIDENCE_CLAIM_SET,
        object_revision=CLAIM_SET_REVISION,
    )


def link_binding(workspace_id, link_id):
    """Return the store binding of one claim-source link."""
    if not isinstance(workspace_id, UUID):
        raise LinkInputError("a workspace id must be a UUID value")
    if not isinstance(link_id, UUID):
        raise LinkInputError("a link id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=link_id,
        object_type=WorkspaceObjectType.EVIDENCE_CLAIM_LINK,
        object_revision=LINK_REVISION,
    )


def assessment_binding(workspace_id, assessment_id):
    """Return the store binding of one strength assessment."""
    if not isinstance(workspace_id, UUID):
        raise StrengthInputError("a workspace id must be a UUID value")
    if not isinstance(assessment_id, UUID):
        raise StrengthInputError("an assessment id must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=assessment_id,
        object_type=WorkspaceObjectType.EVIDENCE_ASSESSMENT,
        object_revision=ASSESSMENT_REVISION,
    )


def freshness_of(source_date, assessed_date, freshness_limit_days):
    """Return the represented freshness of one source at assessment time."""
    source_date = _admit_source_date(source_date, StrengthInputError)
    assessed_date = _admit_assessment_date(assessed_date)
    freshness_limit_days = _admit_freshness_limit(freshness_limit_days)
    if source_date == "":
        return FreshnessState.UNKNOWN_DATE
    age_days = _days_from_civil_tuple(_split_date(assessed_date)) - _days_from_civil_tuple(
        _split_date(source_date)
    )
    if age_days < 0:
        raise StrengthInputError("a source date is in the future of the assessment")
    return FreshnessState.FRESH if age_days <= freshness_limit_days else FreshnessState.STALE


def admit_claim_set(
    store, trail, workspace_id, answer_text, claim_texts, citations_per_claim, actor_id, occurred_at
):
    """Decompose one answer into claims with unresolved citations, failing closed."""
    if not isinstance(store, WorkspaceStore):
        raise ClaimInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ClaimInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise ClaimInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a claim set crossed the workspace boundary")
    admitted_answer = _admit_answer_text(answer_text)
    if not isinstance(claim_texts, tuple) or not claim_texts:
        raise ClaimInputError("a claim set needs a non-empty tuple of claim texts")
    if len(claim_texts) > MAXIMUM_CLAIMS_PER_SET:
        raise ClaimInputError("a claim set carries an unadmitted claim count")
    if not isinstance(citations_per_claim, tuple) or len(citations_per_claim) != len(claim_texts):
        raise ClaimInputError("citations must parallel the claim texts one to one")
    actor = _admit_identifier(actor_id, "actor id", ClaimInputError)
    moment = _admit_occurred_at(occurred_at, ClaimInputError)
    set_id = claim_set_id_for(workspace_id, admitted_answer)
    claims = []
    for position, claim_text in enumerate(claim_texts):
        admitted_text = _admit_claim_text(claim_text)
        raw_citations = citations_per_claim[position]
        if not isinstance(raw_citations, tuple):
            raise ClaimInputError("claim citations must be a tuple")
        if len(raw_citations) > MAXIMUM_CITATIONS_PER_CLAIM:
            raise ClaimInputError("a claim carries an unadmitted citation count")
        citations = tuple(
            ClaimCitation(
                citation_text=_admit_citation_text(item), state=CitationState.CITATION_PRESENT
            ).validated()
            for item in raw_citations
        )
        claims.append(
            Claim(
                claim_id=claim_id_for(workspace_id, set_id, position, admitted_text),
                claim_index=position,
                claim_text=admitted_text,
                citations=citations,
            )
        )
    claim_set = ClaimSet(
        workspace_id=workspace_id,
        set_id=set_id,
        answer_text=admitted_answer,
        claims=tuple(claims),
    ).validated()
    binding = claim_set_binding(workspace_id, claim_set.set_id)
    payload = _canonical_bytes(claim_set.to_document())
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
        raise ClaimConflictError("the claim-set identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_claim_set(store, set_id):
    """Read and verify one stored claim set."""
    if not isinstance(store, WorkspaceStore):
        raise ClaimInputError("a workspace store is required")
    if not isinstance(set_id, UUID):
        raise ClaimInputError("a claim-set id must be a UUID value")
    binding = claim_set_binding(store.workspace_id, set_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ClaimInputError("the claim-set identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ClaimInputError("a stored claim set is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise ClaimInputError("a stored claim set is not JSON") from error
    claim_set = ClaimSet.from_document(document)
    if claim_set.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a claim set crossed the workspace boundary")
    if claim_set.set_id != set_id:
        raise ClaimInputError("a stored claim-set identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return claim_set.validated()


def admit_link(
    store,
    trail,
    workspace_id,
    claim_set_id,
    claim_id,
    source_id,
    snapshot_id,
    stance,
    query_id,
    result_id,
    char_start,
    char_end,
    citation_text,
    actor_id,
    occurred_at,
):
    """Bind one claim to one admitted evidence source revision, failing closed."""
    if not isinstance(store, WorkspaceStore):
        raise LinkInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise LinkInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise LinkInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a claim-source link crossed the workspace boundary")
    if not isinstance(claim_set_id, UUID):
        raise LinkInputError("a claim-set id must be a UUID value")
    if not isinstance(claim_id, UUID):
        raise LinkInputError("a claim id must be a UUID value")
    if not isinstance(stance, LinkStance):
        raise LinkInputError("a link stance is not admitted here")
    query_id = _admit_optional_uuid(query_id, "query id")
    result_id = _admit_optional_uuid(result_id, "result id")
    char_start = _admit_range_bound(char_start, "char start")
    char_end = _admit_range_bound(char_end, "char end")
    citation_text = _admit_optional_citation(citation_text)
    actor = _admit_identifier(actor_id, "actor id", LinkInputError)
    moment = _admit_occurred_at(occurred_at, LinkInputError)
    claim_set = _read_claim_set_for_link(store, claim_set_id)
    claim = _find_claim(claim_set, claim_id)
    if citation_text != "" and not any(
        item.citation_text == citation_text for item in claim.citations
    ):
        raise LinkInputError("a link citation does not match a recorded citation")
    try:
        source = corpus_mod.read_source(store, source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkRevisionError("the linked source is absent in this store") from error
    if not isinstance(snapshot_id, UUID):
        raise LinkInputError("a link snapshot id must be a UUID value")
    try:
        manifest = retrieval_mod.read_snapshot(store, snapshot_id)
    except retrieval_mod.SnapshotInputError as error:
        raise LinkRevisionError("the linked snapshot is absent in this store") from error
    _require_snapshot_membership(manifest, source)
    if query_id is not None or result_id is not None:
        if query_id is None or result_id is None:
            raise LinkInputError("a link query context needs both query and result")
        try:
            query = retrieval_mod.read_query(store, query_id)
        except retrieval_mod.RetrievalInputError as error:
            raise LinkRevisionError("the linked query is absent in this store") from error
        if query.snapshot_id != manifest.snapshot_id:
            raise LinkRevisionError("the linked query belongs to another snapshot")
        try:
            result = retrieval_mod.read_result(store, result_id)
        except retrieval_mod.RetrievalInputError as error:
            raise LinkRevisionError("the linked result is absent in this store") from error
        if result.query_id != query.query_id:
            raise LinkRevisionError("the linked result belongs to another query")
        if result.snapshot_id != manifest.snapshot_id:
            raise LinkRevisionError("the linked result belongs to another snapshot")
    if char_start >= 0 or char_end >= 0:
        if char_start < 0 or char_end < 0:
            raise LinkInputError("a link range needs both bounds or neither")
        if char_end > len(source.text):
            raise LinkInputError("a link range reaches past the source text")
    link = ClaimSourceLink(
        workspace_id=workspace_id,
        set_id=claim_set.set_id,
        link_id=link_id_for(
            workspace_id,
            claim_set.set_id,
            claim.claim_id,
            source.source_id,
            source.source_revision,
            manifest.snapshot_id,
            query_id,
            result_id,
            stance,
            citation_text,
            char_start,
            char_end,
        ),
        claim_id=claim.claim_id,
        source_id=source.source_id,
        source_revision=source.source_revision,
        content_digest=source.content_digest,
        source_date=source.source_date,
        snapshot_id=manifest.snapshot_id,
        query_id=query_id,
        result_id=result_id,
        stance=stance,
        citation_state=CitationState.SOURCE_LINKED,
        citation_text=citation_text,
        char_start=char_start,
        char_end=char_end,
    ).validated()
    binding = link_binding(workspace_id, link.link_id)
    payload = _canonical_bytes(link.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    locator = (
        None
        if link.char_start < 0
        else ":".join(("chars", str(link.char_start), str(link.char_end)))
    )
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(link.source_id),
                source_revision=link.source_revision,
                locator=locator,
            ),
        ),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise LinkConflictError("the claim-source link identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    return binding


def read_link(store, link_id):
    """Read and verify one stored claim-source link."""
    if not isinstance(store, WorkspaceStore):
        raise LinkInputError("a workspace store is required")
    if not isinstance(link_id, UUID):
        raise LinkInputError("a link id must be a UUID value")
    binding = link_binding(store.workspace_id, link_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise LinkInputError("the link identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise LinkInputError("a stored link is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise LinkInputError("a stored link is not JSON") from error
    link = ClaimSourceLink.from_document(document)
    if link.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a claim-source link crossed the workspace boundary")
    if link.link_id != link_id:
        raise LinkInputError("a stored link identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    return link.validated()


def assess_claim(
    store,
    trail,
    workspace_id,
    claim_set_id,
    claim_id,
    verdict,
    link_ids,
    evidence_method,
    evidence_method_version,
    assessed_at,
    freshness_limit_days,
    reason,
    actor_id,
    occurred_at,
):
    """Record one deterministic strength verdict over explicit links, failing closed.

    The verdict is checked mechanically against the stances and the freshness of
    the admitted links. A citation string without a stored link never counts as
    support, and no promotion from UNKNOWN, CONTRADICTED, MISSING_EVIDENCE,
    PARTIALLY_SUPPORTED, or citation-only evidence to SUPPORTED is admitted.
    """
    if not isinstance(store, WorkspaceStore):
        raise StrengthInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise StrengthInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise StrengthInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("an assessment crossed the workspace boundary")
    if not isinstance(claim_set_id, UUID):
        raise StrengthInputError("a claim-set id must be a UUID value")
    if not isinstance(claim_id, UUID):
        raise StrengthInputError("a claim id must be a UUID value")
    if not isinstance(verdict, StrengthVerdict):
        raise StrengthInputError("an assessment verdict is not admitted here")
    if not isinstance(link_ids, tuple):
        raise StrengthInputError("assessment link ids must be a tuple")
    if len(link_ids) > MAXIMUM_LINKS_PER_ASSESSMENT:
        raise StrengthInputError("an assessment carries an unadmitted link count")
    for link_id in link_ids:
        if not isinstance(link_id, UUID):
            raise StrengthInputError("an assessment link id must be a UUID value")
    if len(set(link_ids)) != len(link_ids):
        raise StrengthInputError("an assessment carries a duplicated link id")
    method = _admit_identifier(evidence_method, "evidence method", StrengthInputError)
    if method != EVIDENCE_METHOD:
        raise StrengthInputError("an evidence method is not admitted here")
    version = _admit_identifier(
        evidence_method_version, "evidence method version", StrengthInputError
    )
    if version != EVIDENCE_METHOD_VERSION:
        raise StrengthInputError("an evidence method version is not admitted here")
    assessed_at = _admit_occurred_at(assessed_at, StrengthInputError)
    assessed_date = assessed_at[:10]
    _admit_assessment_date(assessed_date)
    freshness_limit_days = _admit_freshness_limit(freshness_limit_days)
    reason = _admit_reason(verdict, reason)
    actor = _admit_identifier(actor_id, "actor id", StrengthInputError)
    moment = _admit_occurred_at(occurred_at, StrengthInputError)
    try:
        claim_set = read_claim_set(store, claim_set_id)
    except (ClaimInputError, ClaimRevisionError) as error:
        raise StrengthInputError("the assessed claim set is absent in this store") from error
    _find_claim_for_assessment(claim_set, claim_id)
    try:
        links = tuple(read_link(store, link_id) for link_id in link_ids)
    except (LinkInputError, LinkRevisionError) as error:
        raise StrengthInputError("an assessed link is absent in this store") from error
    for link in links:
        if link.claim_id != claim_id or link.set_id != claim_set.set_id:
            raise StrengthInputError("an assessed link belongs to another claim")
    try:
        for link in links:
            _verify_link_bindings(store, link)
    except (LinkInputError, LinkRevisionError) as error:
        raise StrengthInputError("an assessed link binding no longer verifies") from error
    freshness = tuple(
        LinkFreshness(
            link_id=link.link_id,
            state=freshness_of(link.source_date, assessed_date, freshness_limit_days),
        ).validated()
        for link in links
    )
    _check_verdict_rule(verdict, links, freshness, reason)
    assessment = Assessment(
        workspace_id=workspace_id,
        set_id=claim_set.set_id,
        claim_id=claim_id,
        assessment_id=assessment_id_for(
            workspace_id,
            claim_id,
            verdict,
            method,
            version,
            assessed_date,
            freshness_limit_days,
            link_ids,
            reason,
        ),
        verdict=verdict,
        evidence_method=method,
        evidence_method_version=version,
        assessed_at=assessed_at,
        assessed_date=assessed_date,
        freshness_limit_days=freshness_limit_days,
        link_ids=link_ids,
        freshness=freshness,
        reason=reason,
    ).validated()
    binding = assessment_binding(workspace_id, assessment.assessment_id)
    payload = _canonical_bytes(assessment.to_document())
    producer = ProducerIdentity(kind=ProducerKind.HUMAN, identifier=actor, version=PRODUCER_VERSION)
    record = describe_revision(
        binding=binding,
        payload=payload,
        producer=producer,
        source_refs=_assessment_source_refs(links),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, payload)
    except StoreConflictError as error:
        raise StrengthConflictError("the assessment identity already exists") from error
    trail.record_object_write(
        binding=binding,
        payload=payload,
        actor_id=actor,
        occurred_at=moment,
    )
    trail.append(
        event_type=AuditEventType.EVIDENCE_ASSESSMENT,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=assessment.assessment_id,
                object_type=WorkspaceObjectType.EVIDENCE_ASSESSMENT,
                object_revision=ASSESSMENT_REVISION,
                content_digest=content_digest_of(payload),
            ),
        ),
        metadata=(
            ("verdict", verdict.value),
            ("evidence_method", method),
        ),
    )
    return binding


def read_assessment(store, assessment_id):
    """Read one stored assessment and re-verify it against its linked evidence."""
    if not isinstance(store, WorkspaceStore):
        raise StrengthInputError("a workspace store is required")
    if not isinstance(assessment_id, UUID):
        raise StrengthInputError("an assessment id must be a UUID value")
    binding = assessment_binding(store.workspace_id, assessment_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise StrengthInputError("the assessment identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise StrengthInputError("a stored assessment is not ASCII JSON") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise StrengthInputError("a stored assessment is not JSON") from error
    try:
        assessment = Assessment.from_document(document)
    except StrengthInputError as error:
        raise StrengthReplayError("a stored assessment document no longer verifies") from error
    if assessment.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("an assessment crossed the workspace boundary")
    if assessment.assessment_id != assessment_id:
        raise StrengthReplayError("a stored assessment identity does not match its binding")
    record = read_provenance(store, binding)
    try:
        record.verify_payload(raw)
    except Exception as error:
        raise StrengthReplayError("a stored assessment digest no longer verifies") from error
    try:
        claim_set = read_claim_set(store, assessment.set_id)
        _find_claim_for_assessment(claim_set, assessment.claim_id)
        links = tuple(read_link(store, link_id) for link_id in assessment.link_ids)
        for link in links:
            if link.claim_id != assessment.claim_id or link.set_id != assessment.set_id:
                raise StrengthInputError("an assessed link belongs to another claim")
            _verify_link_bindings(store, link)
        recomputed = tuple(
            LinkFreshness(
                link_id=link.link_id,
                state=freshness_of(
                    link.source_date,
                    assessment.assessed_date,
                    assessment.freshness_limit_days,
                ),
            ).validated()
            for link in links
        )
        if tuple(item.to_document() for item in recomputed) != tuple(
            item.to_document() for item in assessment.freshness
        ):
            raise StrengthReplayError("a stored assessment freshness no longer verifies")
        _check_verdict_rule(assessment.verdict, links, assessment.freshness, assessment.reason)
    except StrengthReplayError:
        raise
    except Exception as error:
        raise StrengthReplayError("a stored assessment no longer verifies") from error
    return assessment.validated()


def _verify_link_bindings(store, link):
    """Re-verify one link against the corpus, snapshot, query, and result stores."""
    try:
        source = corpus_mod.read_source(store, link.source_id)
    except corpus_mod.CorpusInputError as error:
        raise LinkRevisionError("the linked source is absent in this store") from error
    if source.source_revision != link.source_revision:
        raise LinkRevisionError("the linked source revision changed")
    if source.content_digest != link.content_digest:
        raise LinkRevisionError("the linked source content changed")
    try:
        manifest = retrieval_mod.read_snapshot(store, link.snapshot_id)
    except retrieval_mod.SnapshotInputError as error:
        raise LinkRevisionError("the linked snapshot is absent in this store") from error
    _require_snapshot_membership(manifest, source)
    if link.query_id is not None or link.result_id is not None:
        if link.query_id is None or link.result_id is None:
            raise LinkInputError("a link query context needs both query and result")
        try:
            query = retrieval_mod.read_query(store, link.query_id)
        except retrieval_mod.RetrievalInputError as error:
            raise LinkRevisionError("the linked query is absent in this store") from error
        if query.snapshot_id != manifest.snapshot_id:
            raise LinkRevisionError("the linked query belongs to another snapshot")
        try:
            result = retrieval_mod.read_result(store, link.result_id)
        except retrieval_mod.RetrievalInputError as error:
            raise LinkRevisionError("the linked result is absent in this store") from error
        if result.query_id != query.query_id:
            raise LinkRevisionError("the linked result belongs to another query")
        if result.snapshot_id != manifest.snapshot_id:
            raise LinkRevisionError("the linked result belongs to another snapshot")
    if link.char_start >= 0 and link.char_end > len(source.text):
        raise LinkRevisionError("a link range reaches past the source text")
    return link


def _require_snapshot_membership(manifest, source):
    for entry in manifest.entries:
        if entry.source_id == source.source_id:
            if entry.source_revision != source.source_revision:
                raise LinkRevisionError("the snapshot member source revision changed")
            if entry.content_digest != source.content_digest:
                raise LinkRevisionError("the snapshot member source content changed")
            return entry
    raise LinkRevisionError("the linked snapshot does not contain the source")


def _check_verdict_rule(verdict, links, freshness, reason):
    """Fail closed unless a verdict follows from its linked evidence stances."""
    if not isinstance(verdict, StrengthVerdict):
        raise StrengthVerdictError("an assessment verdict is not admitted here")
    fresh_support = 0
    fresh_partial = 0
    contradicts = 0
    for link, fresh in zip(links, freshness, strict=True):
        if not isinstance(link, ClaimSourceLink):
            raise StrengthVerdictError("a verdict needs ClaimSourceLink instances")
        if not isinstance(fresh, LinkFreshness):
            raise StrengthVerdictError("a verdict needs LinkFreshness instances")
        if fresh.link_id != link.link_id:
            raise StrengthVerdictError("freshness must cover every link in order")
        if link.citation_state is not CitationState.SOURCE_LINKED:
            raise StrengthVerdictError("only resolved source links decide a verdict")
        if link.stance is LinkStance.SUPPORTS and fresh.state is FreshnessState.FRESH:
            fresh_support += 1
        elif link.stance is LinkStance.PARTIALLY_SUPPORTS and fresh.state is FreshnessState.FRESH:
            fresh_partial += 1
        elif link.stance is LinkStance.CONTRADICTS:
            contradicts += 1
    if verdict is StrengthVerdict.SUPPORTED:
        if fresh_support < 1:
            raise StrengthVerdictError("a supported claim needs fresh supporting links")
        if contradicts > 0:
            raise StrengthVerdictError("a contradicted claim is never supported")
        if reason != "":
            raise StrengthVerdictError("a supported verdict must not carry a reason")
    elif verdict is StrengthVerdict.PARTIALLY_SUPPORTED:
        if fresh_support > 0:
            raise StrengthVerdictError("fully supported evidence needs a supported verdict")
        if fresh_partial < 1:
            raise StrengthVerdictError("a partial verdict needs fresh partial links")
        if contradicts > 0:
            raise StrengthVerdictError("a contradicted claim is never partially supported")
        if reason != "":
            raise StrengthVerdictError("a partial verdict must not carry a reason")
    elif verdict is StrengthVerdict.CONTRADICTED:
        if contradicts < 1:
            raise StrengthVerdictError("a contradiction verdict needs a contradicting link")
        if reason != "":
            raise StrengthVerdictError("a contradiction verdict must not carry a reason")
    elif verdict is StrengthVerdict.UNKNOWN:
        if fresh_support > 0 or fresh_partial > 0 or contradicts > 0:
            raise StrengthVerdictError("decisive evidence is never unknown")
        _require_reason_member(reason, UnknownReason)
    elif verdict is StrengthVerdict.MISSING_EVIDENCE:
        if len(links) > 0:
            raise StrengthVerdictError("missing evidence needs an empty link set")
        _require_reason_member(reason, MissingReason)
    elif verdict is StrengthVerdict.ABSTAINED:
        if fresh_support > 0 or contradicts > 0:
            raise StrengthVerdictError("decisive evidence is never abstained")
        _require_reason_member(reason, AbstainReason)
    else:
        if len(links) > 0:
            raise StrengthVerdictError("a failure verdict needs an empty link set")
        _require_reason_member(reason, FailureReason)
    return verdict


def _require_reason_member(reason, members):
    try:
        members(reason)
    except ValueError as error:
        raise StrengthVerdictError("a verdict reason is not admitted here") from error
    return reason


def _assessment_source_refs(links):
    refs = []
    seen = set()
    for link in links:
        key = (str(link.source_id), link.source_revision)
        if key in seen:
            continue
        seen.add(key)
        refs.append(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(link.source_id),
                source_revision=link.source_revision,
                locator=None,
            )
        )
    return tuple(refs)


def _read_claim_set_for_link(store, claim_set_id):
    try:
        return read_claim_set(store, claim_set_id)
    except (ClaimInputError, ClaimRevisionError) as error:
        raise LinkInputError("the linked claim set is absent in this store") from error


def _find_claim(claim_set, claim_id):
    for claim in claim_set.claims:
        if claim.claim_id == claim_id:
            return claim
    raise LinkInputError("the linked claim is absent in its claim set")


def _find_claim_for_assessment(claim_set, claim_id):
    for claim in claim_set.claims:
        if claim.claim_id == claim_id:
            return claim
    raise StrengthInputError("the assessed claim is absent in its claim set")


def _split_date(value):
    return (int(value[0:4]), int(value[5:7]), int(value[8:10]))


def _days_from_civil_tuple(parts):
    year, month, day = parts
    adjusted_year = year - 1 if month <= 2 else year
    era = adjusted_year // 400
    year_of_era = adjusted_year - era * 400
    month_part = (month + 9) % 12
    day_of_year = (153 * month_part + 2) // 5 + day - 1
    day_of_era = year_of_era * 365 + year_of_era // 4 - year_of_era // 100 + day_of_year
    return era * 146097 + day_of_era - 719468


def _admit_identifier(raw, label, error_cls):
    if not isinstance(raw, str):
        raise error_cls(f"a {label} must be a string")
    value = raw.strip()
    if not value:
        raise error_cls(f"a {label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise error_cls(f"a {label} is longer than the admitted maximum")
    if not value.isascii():
        raise error_cls(f"a {label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise error_cls(f"a {label} must not contain whitespace or controls")
    return value


def _admit_answer_text(raw):
    if not isinstance(raw, str):
        raise ClaimInputError("answer text must be a string")
    value = raw.strip()
    if not value:
        raise ClaimInputError("answer text must be non-empty")
    if len(value) > MAXIMUM_ANSWER_CHARS:
        raise ClaimInputError("answer text is longer than the admitted maximum")
    if not value.isascii():
        raise ClaimInputError("answer text must be ASCII")
    for character in value:
        if character in ("\n", "\t", " "):
            continue
        if not character.isprintable():
            raise ClaimInputError("answer text must not contain control characters")
    return value


def _admit_claim_text(raw):
    if not isinstance(raw, str):
        raise ClaimInputError("claim text must be a string")
    value = raw.strip()
    if not value:
        raise ClaimInputError("claim text must be non-empty")
    if len(value) > MAXIMUM_CLAIM_CHARS:
        raise ClaimInputError("claim text is longer than the admitted maximum")
    if not value.isascii():
        raise ClaimInputError("claim text must be ASCII")
    for character in value:
        if character in ("\n", "\t", " "):
            continue
        if not character.isprintable():
            raise ClaimInputError("claim text must not contain control characters")
    return value


def _admit_claim_index(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise ClaimInputError("a claim index must be an integer")
    if raw < 0:
        raise ClaimInputError("a claim index starts at zero")
    return raw


def _admit_citation_text(raw):
    if not isinstance(raw, str):
        raise ClaimInputError("citation text must be a string")
    value = raw.strip()
    if not value:
        raise ClaimInputError("citation text must be non-empty")
    if len(value) > MAXIMUM_CITATION_CHARS:
        raise ClaimInputError("citation text is longer than the admitted maximum")
    if not value.isascii():
        raise ClaimInputError("citation text must be ASCII")
    for character in value:
        if not character.isprintable():
            raise ClaimInputError("citation text must not contain control characters")
    return value


def _admit_optional_citation(raw):
    if not isinstance(raw, str):
        raise LinkInputError("a link citation must be a string")
    value = raw.strip()
    if value == "":
        return ""
    return _admit_link_citation_text(value)


def _admit_link_citation_text(value):
    if len(value) > MAXIMUM_CITATION_CHARS:
        raise LinkInputError("a link citation is longer than the admitted maximum")
    if not value.isascii():
        raise LinkInputError("a link citation must be ASCII")
    for character in value:
        if not character.isprintable():
            raise LinkInputError("a link citation must not contain control characters")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise LinkInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise LinkInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_source_date(raw, error_cls):
    if not isinstance(raw, str):
        raise error_cls("a source date must be a string")
    value = raw.strip()
    if value == "":
        return ""
    _require_calendar_date(value, "a source date", error_cls)
    return value


def _admit_assessment_date(raw):
    if not isinstance(raw, str):
        raise StrengthInputError("an assessed date must be a string")
    value = raw.strip()
    _require_calendar_date(value, "an assessed date", StrengthInputError)
    return value


def _require_calendar_date(value, label, error_cls):
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        raise error_cls(f"{label} must be empty or YYYY-MM-DD")
    for index in (0, 1, 2, 3, 5, 6, 8, 9):
        if value[index] not in "0123456789":
            raise error_cls(f"{label} must be empty or YYYY-MM-DD")
    year, month, day = _split_date(value)
    if month < 1 or month > 12:
        raise error_cls(f"{label} carries an impossible month")
    leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
    month_days = (31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
    if day < 1 or day > month_days[month - 1]:
        raise error_cls(f"{label} carries an impossible day")
    return value


def _admit_optional_uuid(raw, label):
    if raw is None:
        return None
    if not isinstance(raw, UUID):
        raise LinkInputError(f"a link {label} must be a UUID value or None")
    return raw


def _admit_range_bound(raw, label):
    if raw is None:
        return -1
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise LinkInputError(f"a {label} must be an integer or None")
    if raw < -1:
        raise LinkInputError(f"a {label} must not be negative")
    return raw


def _admit_freshness_limit(raw):
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise StrengthInputError("a freshness limit must be an integer")
    if raw < 0 or raw > MAXIMUM_FRESHNESS_LIMIT_DAYS:
        raise StrengthInputError("a freshness limit is outside the admitted range")
    return raw


def _admit_reason(verdict, raw):
    if not isinstance(raw, str):
        raise StrengthInputError("a verdict reason must be a string")
    if verdict in (
        StrengthVerdict.SUPPORTED,
        StrengthVerdict.PARTIALLY_SUPPORTED,
        StrengthVerdict.CONTRADICTED,
    ):
        if raw != "":
            raise StrengthInputError("a decisive verdict must not carry a reason")
        return ""
    if len(raw) > MAXIMUM_REASON_CHARS:
        raise StrengthInputError("a verdict reason is longer than the admitted maximum")
    if not raw.isascii() or not raw.isprintable():
        raise StrengthInputError("a verdict reason must be printable ASCII")
    members = (
        UnknownReason
        if verdict is StrengthVerdict.UNKNOWN
        else MissingReason
        if verdict is StrengthVerdict.MISSING_EVIDENCE
        else AbstainReason
        if verdict is StrengthVerdict.ABSTAINED
        else FailureReason
    )
    try:
        members(raw)
    except ValueError as error:
        raise StrengthInputError("a verdict reason is not admitted here") from error
    return raw


def _admit_occurred_at(raw, error_cls):
    if not isinstance(raw, str):
        raise error_cls("an occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise error_cls("an occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise error_cls("an occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise error_cls("an occurrence time must be an ISO-8601 instant with a zone")
    if not value.isascii():
        raise error_cls("an occurrence time must be ASCII")
    return value


def _check_duplicate_citation_texts(citations):
    seen = set()
    for item in citations:
        if item.citation_text in seen:
            raise ClaimInputError("duplicate citation strings are refused")
        seen.add(item.citation_text)


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )


def _string_member(document, name):
    value = document[name]
    if not isinstance(value, str):
        raise LinkInputError(f"a stored {name} must be a string")
    return value


def _integer_member(document, name):
    value = document[name]
    if isinstance(value, bool) or not isinstance(value, int):
        raise LinkInputError(f"a stored {name} must be an integer")
    return value


def _optional_uuid_member(document, name):
    value = document[name]
    if value == "":
        return None
    if not isinstance(value, str):
        raise LinkInputError(f"a stored {name} must be a string")
    try:
        return UUID(value)
    except ValueError as error:
        raise LinkInputError(f"a stored {name} is not admitted") from error


def _parse_uuid_member(value):
    if not isinstance(value, str):
        raise StrengthInputError("a stored assessment link id must be a string")
    try:
        return UUID(value)
    except ValueError as error:
        raise StrengthInputError("a stored assessment link id is not admitted") from error
