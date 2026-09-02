"""Evidence engine: store roundtrips, rule verification, extraction queue, CLI flow."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import cast

import pytest

from medscale import cli
from medscale.evidence import EvidenceObject, StudyType, VerificationState
from medscale.evidence_checks import (
    archived_payload_hashes,
    provenance_anchor_check,
    rule_verify_source,
    source_reference_check,
)
from medscale.evidence_store import (
    evidence_from_dict,
    evidence_to_dict,
    load_evidence,
    write_evidence,
)
from medscale.extraction import assemble_evidence, extraction_queue
from medscale.litdb import (
    EvidenceTier,
    Identifiers,
    LiteratureRecord,
    RawRetrieval,
    RunManifest,
    archive_retrieval,
    write_manifest,
)
from medscale.litdb.review import ReviewDecision, make_event
from medscale.litdb.review import append_events as append_review_events
from medscale.litdb.store import write_corpus
from medscale.provenance import Provenance, SourceAPI

_TS = "2026-07-10T00:00:00+00:00"
_HASH = "b" * 64


def _record(doi: str = "10.1/src") -> LiteratureRecord:
    return LiteratureRecord(
        identifiers=Identifiers(doi=doi),
        title="A randomized trial of grammar-constrained decoding",
        evidence_tier=EvidenceTier.PEER_REVIEWED,
        provenance=Provenance(SourceAPI.OPENALEX, doi, _TS, _HASH),
        year=2026,
        abstract="We compare constrained and unconstrained decoding.",
    )


def _evidence(record: LiteratureRecord | None = None) -> EvidenceObject:
    record = record or _record()
    return assemble_evidence(
        record,
        claim="Constrained decoding improves structural validity.",
        study_type=StudyType.RANDOMIZED_CONTROLLED_TRIAL,
        created_at=_TS,
        intervention="grammar-constrained decoding",
        outcome="structural validity rate",
    )


# ---------------------------------------------------------------- store contracts
def test_store_roundtrip_and_format_marker(tmp_path: Path) -> None:
    path = tmp_path / "objects.jsonl"
    obj = _evidence()
    assert write_evidence(path, [obj]) == 1
    serialized = path.read_text(encoding="utf-8")
    assert '"format":1' in serialized
    assert '"identity_version"' not in serialized
    (loaded,) = load_evidence(path)
    assert loaded == obj
    assert loaded.identity_version == 1
    assert loaded.evidence_id == obj.evidence_id


def test_store_dedupes_by_evidence_id_and_is_order_independent(tmp_path: Path) -> None:
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    obj = _evidence()
    other = assemble_evidence(
        _record(), claim="A different claim.", study_type=StudyType.COHORT, created_at=_TS
    )
    assert write_evidence(a, [obj, obj, other]) == 2
    write_evidence(b, [other, obj])
    assert a.read_bytes() == b.read_bytes()


def test_legacy_dict_without_format_loads_as_identity_version_one() -> None:
    legacy = evidence_to_dict(_evidence())
    del legacy["format"]
    restored = evidence_from_dict(legacy)
    assert restored.identity_version == 1
    assert restored.evidence_id == _evidence().evidence_id


def test_schema_version_change_does_not_remint_evidence_identity() -> None:
    obj = _evidence()
    changed = dataclasses.replace(obj, schema_version="2")
    assert changed.schema_version == "2"
    assert changed.evidence_id == obj.evidence_id


def test_identity_version_change_remints_evidence_identity_in_memory() -> None:
    obj = _evidence()
    changed = dataclasses.replace(obj, identity_version=2)
    assert changed.identity_version == 2
    assert changed.evidence_id != obj.evidence_id


def test_format_one_persistence_rejects_nondefault_identity_version() -> None:
    changed = dataclasses.replace(_evidence(), identity_version=2)
    with pytest.raises(ValueError, match="format-1 evidence persistence"):
        evidence_to_dict(changed)

    payload = evidence_to_dict(_evidence())
    payload["identity_version"] = 2
    with pytest.raises(ValueError, match="format-1 evidence persistence"):
        evidence_from_dict(payload)


@pytest.mark.parametrize("value", [0, -1, True, 1.0, "1"])
def test_identity_version_requires_positive_exact_int(value: object) -> None:
    with pytest.raises(ValueError, match="identity_version must be a positive int"):
        dataclasses.replace(_evidence(), identity_version=cast(int, value))


def test_missing_store_loads_empty(tmp_path: Path) -> None:
    assert load_evidence(tmp_path / "absent.jsonl") == ()


# ---------------------------------------------------------------- rule verification
def test_rule_verify_advances_when_all_checks_pass() -> None:
    record = _record()
    obj = _evidence(record)
    verified, results = rule_verify_source(obj, frozenset({record.record_id}), frozenset({_HASH}))
    assert all(result.passed for result in results)
    assert verified.verification is VerificationState.SOURCE_VERIFIED
    assert verified.evidence_id == obj.evidence_id  # identity survives verification


def test_rule_verify_fails_closed_on_missing_source() -> None:
    obj = _evidence()
    unverified, results = rule_verify_source(obj, frozenset(), frozenset({_HASH}))
    assert unverified.verification is VerificationState.UNVERIFIED
    assert source_reference_check(obj, frozenset()).passed is False
    assert any(not result.passed for result in results)


def test_rule_verify_fails_closed_on_unanchored_provenance() -> None:
    record = _record()
    obj = _evidence(record)
    unverified, _ = rule_verify_source(obj, frozenset({record.record_id}), frozenset())
    assert unverified.verification is VerificationState.UNVERIFIED
    assert provenance_anchor_check(obj, frozenset()).passed is False


def test_rule_verify_is_idempotent_past_unverified() -> None:
    record = _record()
    obj, _ = rule_verify_source(
        _evidence(record), frozenset({record.record_id}), frozenset({_HASH})
    )
    again, results = rule_verify_source(obj, frozenset(), frozenset())  # checks now fail
    assert again.verification is VerificationState.SOURCE_VERIFIED  # state not regressed
    assert any(not result.passed for result in results)  # but failures still reported


def test_archived_payload_hashes_reads_manifests(tmp_path: Path) -> None:
    retrieval = RawRetrieval(SourceAPI.OPENALEX, "q", _TS, payload='{"x": 1}')
    entry = archive_retrieval(tmp_path, "r1", "Q1", retrieval)
    write_manifest(tmp_path, RunManifest("r1", "abcdef1", (entry,)))
    hashes = archived_payload_hashes(tmp_path)
    assert retrieval.payload_sha256() in hashes


# ---------------------------------------------------------------- extraction queue
def test_extraction_queue_filters_included_without_evidence() -> None:
    first, second = _record("10.1/a"), _record("10.1/b")
    queue = extraction_queue(
        (first, second),
        included_ids=frozenset({first.record_id, second.record_id}),
        extracted_source_ids=frozenset({first.record_id}),
    )
    assert queue == (second,)


def test_extraction_queue_ignores_non_included() -> None:
    record = _record()
    assert extraction_queue((record,), frozenset(), frozenset()) == ()


# ---------------------------------------------------------------- CLI end-to-end
def _seed_included(root: Path) -> LiteratureRecord:
    # archive a payload first, then build the record whose provenance points at it,
    # so the anchor check passes against the on-disk corpus
    retrieval = RawRetrieval(SourceAPI.OPENALEX, "q", _TS, payload="anchored")
    entry = archive_retrieval(root, "r1", "Q1", retrieval)
    write_manifest(root, RunManifest("r1", "abcdef1", (entry,)))
    record = LiteratureRecord(
        identifiers=Identifiers(doi="10.1/src"),
        title="A randomized trial of grammar-constrained decoding",
        evidence_tier=EvidenceTier.PEER_REVIEWED,
        provenance=Provenance(SourceAPI.OPENALEX, "10.1/src", _TS, retrieval.payload_sha256()),
        year=2026,
        abstract="We compare constrained and unconstrained decoding.",
    )
    write_corpus(root / "corpus" / "records.jsonl", [record])
    event = make_event(
        record.record_id,
        ReviewDecision.INCLUDE,
        reviewer="tester",
        decided_at=_TS,
        software_version="0.0.0",
        git_sha="abcdef1",
    )
    append_review_events(root / "screening" / "review_log.jsonl", (event,))
    return record


def test_cli_extract_creates_verified_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_included(tmp_path)
    answers = iter(
        [
            "Constrained decoding improves validity.",  # claim
            "3",  # study type -> randomized_controlled_trial (3rd member)
            "",  # population
            "constrained decoding",  # intervention
            "",  # comparator
            "validity",  # outcome
            "",  # effect measure
            "",  # effect value
            "",  # next claim -> move on
        ]
    )
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))
    rc = cli.main(["extract", "--root", str(tmp_path)])
    assert rc == 0
    (obj,) = load_evidence(tmp_path / "evidence" / "objects.jsonl")
    assert obj.claim == "Constrained decoding improves validity."
    assert obj.study_type is StudyType.RANDOMIZED_CONTROLLED_TRIAL
    assert obj.verification is VerificationState.SOURCE_VERIFIED  # rule-verified live
    assert obj.source_record_id is not None


def test_cli_extract_without_includes_says_screen_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_corpus(tmp_path / "corpus" / "records.jsonl", [_record()])
    assert cli.main(["extract", "--root", str(tmp_path)]) == 0
    assert "screening comes first" in capsys.readouterr().out


# ---------------------------------------------------------------- integrity extension
def test_integrity_flags_orphaned_evidence(tmp_path: Path) -> None:
    from medscale.litdb.integrity import check_litdb

    record = _record()
    write_corpus(tmp_path / "corpus" / "records.jsonl", [record])
    ghost = evidence_to_dict(_evidence(record))
    ghost["source_record_id"] = "0" * 64
    evidence_path = tmp_path / "evidence" / "objects.jsonl"
    evidence_path.parent.mkdir(parents=True)
    evidence_path.write_text(json.dumps(ghost) + "\n", encoding="utf-8")
    report = check_litdb(tmp_path)
    assert not report.is_clean
    assert any(issue.kind == "orphaned_evidence_ref" for issue in report.issues)
    assert report.evidence_refs == 1
