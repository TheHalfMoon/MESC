"""CW-010 acceptance tests: claims decompose, links bind, verdicts never collapse."""

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditEventType,
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import evidence_strength as es_mod  # noqa: E402 runtime import
from medscale_workspace import retrieval as retrieval_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    ClaimConflictError,
    ClaimInputError,
    LinkConflictError,
    StrengthInputError,
    StrengthVerdictError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"
T_ASSESS = "2026-09-24T12:00:00+03:00"
FRESH_LIMIT = 365

TEXT_ONE = "synthetic guideline: hydration monitoring for ward patients"
TEXT_TWO = "synthetic note: hydration protocol compliance audit"
TEXT_THREE = "synthetic memo: ward staffing rotation schedule"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit(
    store: WorkspaceStore,
    trail: AuditTrail,
    locator: str,
    text: str,
    date: str = "2026-09-01",
) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                CORPUS_KEY,
                locator,
                "Synthetic source",
                "rev-00000001",
                date,
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def stocked(store: WorkspaceStore, trail: AuditTrail) -> tuple[UUID, UUID, UUID]:
    first = admit(store, trail, "synthetic-corpus/doc-001", TEXT_ONE)
    second = admit(store, trail, "synthetic-corpus/doc-002", TEXT_TWO)
    snapshot_id = UUID(
        str(
            retrieval_mod.admit_snapshot(
                store, trail, WORKSPACE_ALPHA, CORPUS_KEY, (first, second), ACTOR, T1
            ).object_id
        )
    )
    return first, second, snapshot_id


def claim_fixture(
    store: WorkspaceStore,
    trail: AuditTrail,
    answer: str = "answer: hydration ward protocol",
    claims: tuple[str, ...] = ("hydration is monitored", "audits check compliance"),
    citations: tuple[tuple[str, ...], ...] = (("cite-one",), ("cite-two",)),
) -> UUID:
    return UUID(
        str(
            es_mod.admit_claim_set(
                store, trail, WORKSPACE_ALPHA, answer, claims, citations, ACTOR, T1
            ).object_id
        )
    )


def link_fixture(
    store: WorkspaceStore,
    trail: AuditTrail,
    set_id: UUID,
    claim_id: UUID,
    source_id: UUID,
    snapshot_id: UUID,
    stance: es_mod.LinkStance,
    citation: str = "",
) -> UUID:
    return UUID(
        str(
            es_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                set_id,
                claim_id,
                source_id,
                snapshot_id,
                stance,
                None,
                None,
                None,
                None,
                citation,
                ACTOR,
                T1,
            ).object_id
        )
    )


def assess_fixture(
    store: WorkspaceStore,
    trail: AuditTrail,
    set_id: UUID,
    claim_id: UUID,
    verdict: es_mod.StrengthVerdict,
    link_ids: tuple[UUID, ...],
    reason: str = "",
    assessed_at: str = T_ASSESS,
    limit: int = FRESH_LIMIT,
) -> UUID:
    return UUID(
        str(
            es_mod.assess_claim(
                store,
                trail,
                WORKSPACE_ALPHA,
                set_id,
                claim_id,
                verdict,
                link_ids,
                es_mod.EVIDENCE_METHOD,
                es_mod.EVIDENCE_METHOD_VERSION,
                assessed_at,
                limit,
                reason,
                ACTOR,
                T2,
            ).object_id
        )
    )


def test_answer_decomposes_into_claims_with_deterministic_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        assert len(claim_set.claims) == 2
        assert claim_set.claims[0].claim_index == 0
        assert claim_set.claims[1].claim_index == 1
        assert claim_set.set_id == es_mod.claim_set_id_for(
            WORKSPACE_ALPHA, "answer: hydration ward protocol"
        )
        with pytest.raises(ClaimConflictError):
            claim_fixture(store, trail)
        other = claim_fixture(store, trail, answer="answer: staffing rotation")
        assert other != set_id


def test_citation_present_and_source_linked_are_distinct_states(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        assert claim_set.claims[0].citations[0].state is es_mod.CitationState.CITATION_PRESENT
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            first,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
            citation="cite-one",
        )
        link = es_mod.read_link(store, link_id)
        assert link.citation_state is es_mod.CitationState.SOURCE_LINKED
        assert link.citation_state is not es_mod.CitationState.CITATION_PRESENT


def test_supported_verdict_needs_fresh_supporting_links(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            first,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
        )
        assessment_id = assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            es_mod.StrengthVerdict.SUPPORTED,
            (link_id,),
        )
        assessment = es_mod.read_assessment(store, assessment_id)
        assert assessment.verdict is es_mod.StrengthVerdict.SUPPORTED
        assert assessment.freshness[0].state is es_mod.FreshnessState.FRESH
        assert assessment.evidence_method == es_mod.EVIDENCE_METHOD
        assert assessment.evidence_method_version == es_mod.EVIDENCE_METHOD_VERSION


def test_partially_supported_verdict_for_partial_links(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _, second, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[1].claim_id,
            second,
            snapshot_id,
            es_mod.LinkStance.PARTIALLY_SUPPORTS,
        )
        assessment_id = assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[1].claim_id,
            es_mod.StrengthVerdict.PARTIALLY_SUPPORTED,
            (link_id,),
        )
        assert es_mod.read_assessment(store, assessment_id).verdict is (
            es_mod.StrengthVerdict.PARTIALLY_SUPPORTED
        )


def test_unknown_is_first_class_with_reasons(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            first,
            snapshot_id,
            es_mod.LinkStance.NO_RELATION,
        )
        assessment_id = assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            es_mod.StrengthVerdict.UNKNOWN,
            (link_id,),
            reason="inconclusive_evidence",
        )
        assert es_mod.read_assessment(store, assessment_id).verdict is (
            es_mod.StrengthVerdict.UNKNOWN
        )


def test_contradicted_verdict_dominates_support(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, second, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        claim_id = claim_set.claims[0].claim_id
        support = link_fixture(
            store, trail, set_id, claim_id, first, snapshot_id, es_mod.LinkStance.SUPPORTS
        )
        against = link_fixture(
            store,
            trail,
            set_id,
            claim_id,
            second,
            snapshot_id,
            es_mod.LinkStance.CONTRADICTS,
        )
        assessment_id = assess_fixture(
            store,
            trail,
            set_id,
            claim_id,
            es_mod.StrengthVerdict.CONTRADICTED,
            (support, against),
        )
        assert es_mod.read_assessment(store, assessment_id).verdict is (
            es_mod.StrengthVerdict.CONTRADICTED
        )
        with pytest.raises(StrengthVerdictError):
            assess_fixture(
                store,
                trail,
                set_id,
                claim_id,
                es_mod.StrengthVerdict.SUPPORTED,
                (support, against),
            )


def test_missing_evidence_abstained_and_failed_states(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        first_id, second_id = claim_set.claims[0].claim_id, claim_set.claims[1].claim_id
        missing = assess_fixture(
            store,
            trail,
            set_id,
            first_id,
            es_mod.StrengthVerdict.MISSING_EVIDENCE,
            (),
            reason="only_unresolved_citations",
        )
        assert es_mod.read_assessment(store, missing).verdict is (
            es_mod.StrengthVerdict.MISSING_EVIDENCE
        )
        abstained = assess_fixture(
            store,
            trail,
            set_id,
            second_id,
            es_mod.StrengthVerdict.ABSTAINED,
            (),
            reason="insufficient_evidence",
        )
        assert es_mod.read_assessment(store, abstained).verdict is (
            es_mod.StrengthVerdict.ABSTAINED
        )
        failed = es_mod.assess_claim(
            store,
            trail,
            WORKSPACE_ALPHA,
            set_id,
            second_id,
            es_mod.StrengthVerdict.FAILED,
            (),
            es_mod.EVIDENCE_METHOD,
            es_mod.EVIDENCE_METHOD_VERSION,
            T_ASSESS,
            FRESH_LIMIT,
            "evidence_validation_failed",
            ACTOR,
            T2,
        )
        assert es_mod.read_assessment(store, UUID(str(failed.object_id))).verdict is (
            es_mod.StrengthVerdict.FAILED
        )


def test_freshness_represents_stale_and_unknown_dates(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        stale = admit(store, trail, "synthetic-corpus/old", TEXT_THREE, date="2020-01-01")
        undated = admit(store, trail, "synthetic-corpus/nodate", TEXT_THREE, date="")
        snapshot_id = UUID(
            str(
                retrieval_mod.admit_snapshot(
                    store, trail, WORKSPACE_ALPHA, CORPUS_KEY, (stale, undated), ACTOR, T1
                ).object_id
            )
        )
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        stale_link = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            stale,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
        )
        undated_link = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[1].claim_id,
            undated,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
        )
        with pytest.raises(StrengthVerdictError):
            assess_fixture(
                store,
                trail,
                set_id,
                claim_set.claims[0].claim_id,
                es_mod.StrengthVerdict.SUPPORTED,
                (stale_link,),
            )
        with pytest.raises(StrengthVerdictError):
            assess_fixture(
                store,
                trail,
                set_id,
                claim_set.claims[1].claim_id,
                es_mod.StrengthVerdict.SUPPORTED,
                (undated_link,),
            )
        unknown = assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            es_mod.StrengthVerdict.UNKNOWN,
            (stale_link,),
            reason="evidence_too_stale",
        )
        stored = es_mod.read_assessment(store, unknown)
        assert stored.freshness[0].state is es_mod.FreshnessState.STALE
        assert es_mod.freshness_of("2020-01-01", "2026-09-24", 365) is (es_mod.FreshnessState.STALE)
        assert es_mod.freshness_of("", "2026-09-24", 365) is (es_mod.FreshnessState.UNKNOWN_DATE)
        assert es_mod.freshness_of("2026-09-01", "2026-09-24", 365) is (es_mod.FreshnessState.FRESH)


def test_link_with_query_result_context_and_char_range(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        query_id = retrieval_mod.query_id_for(
            WORKSPACE_ALPHA,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
        )
        result_binding = retrieval_mod.execute_query(
            store,
            trail,
            snapshot_id,
            "hydration monitoring",
            10,
            retrieval_mod.MatchMode.ANY,
            ACTOR,
            T2,
        )
        result_id = result_binding.object_id
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = UUID(
            str(
                es_mod.admit_link(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    set_id,
                    claim_set.claims[0].claim_id,
                    first,
                    snapshot_id,
                    es_mod.LinkStance.SUPPORTS,
                    query_id,
                    result_id,
                    0,
                    9,
                    "",
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        link = es_mod.read_link(store, link_id)
        assert link.query_id == query_id
        assert link.result_id == result_id
        assert (link.char_start, link.char_end) == (0, 9)
        assessment_id = assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            es_mod.StrengthVerdict.SUPPORTED,
            (link_id,),
        )
        assert es_mod.read_assessment(store, assessment_id).verdict is (
            es_mod.StrengthVerdict.SUPPORTED
        )


def test_assessment_emits_audit_event_without_claim_text(tmp_path: Path) -> None:
    marker = "marker-claim-phrase-zzz"
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(
            store,
            trail,
            answer="answer holding marker",
            claims=(f"claim holding {marker}",),
            citations=((),),
        )
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            first,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
        )
        assess_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            es_mod.StrengthVerdict.SUPPORTED,
            (link_id,),
        )
        kinds = [event.event_type for event in trail.events()]
        assert AuditEventType.EVIDENCE_ASSESSMENT in kinds
        for event in trail.events():
            assert marker.encode("ascii") not in event.canonical_bytes()


def test_evidence_method_mismatch_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        with pytest.raises(StrengthInputError):
            es_mod.assess_claim(
                store,
                trail,
                WORKSPACE_ALPHA,
                set_id,
                claim_set.claims[0].claim_id,
                es_mod.StrengthVerdict.MISSING_EVIDENCE,
                (),
                "other-method",
                "1",
                T_ASSESS,
                FRESH_LIMIT,
                "no_citations",
                ACTOR,
                T2,
            )
        with pytest.raises(StrengthInputError):
            es_mod.assess_claim(
                store,
                trail,
                WORKSPACE_ALPHA,
                set_id,
                claim_set.claims[0].claim_id,
                es_mod.StrengthVerdict.MISSING_EVIDENCE,
                (),
                es_mod.EVIDENCE_METHOD,
                "2",
                T_ASSESS,
                FRESH_LIMIT,
                "no_citations",
                ACTOR,
                T2,
            )


def test_duplicate_claim_set_and_link_replays_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first, _, snapshot_id = stocked(store, trail)
        set_id = claim_fixture(store, trail)
        claim_set = es_mod.read_claim_set(store, set_id)
        link_id = link_fixture(
            store,
            trail,
            set_id,
            claim_set.claims[0].claim_id,
            first,
            snapshot_id,
            es_mod.LinkStance.SUPPORTS,
        )
        with pytest.raises(LinkConflictError):
            link_fixture(
                store,
                trail,
                set_id,
                claim_set.claims[0].claim_id,
                first,
                snapshot_id,
                es_mod.LinkStance.SUPPORTS,
            )
        assert es_mod.read_link(store, link_id).link_id == link_id
        with pytest.raises(ClaimInputError):
            es_mod.admit_claim_set(
                store,
                trail,
                WORKSPACE_ALPHA,
                "short answer",
                ("only claim",),
                (("dup", "dup"),),
                ACTOR,
                T1,
            )
