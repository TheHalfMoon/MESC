"""Regression tests for the MRL-0803 Experiment-0 isolation producer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0803_isolation_v1 as isolation
from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_jsonl_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import (
    MRLRealPreflightEvidenceError,
    admit_mrl_real_preflight_evidence,
    parse_mrl_real_preflight_evidence,
)

_ROOT = Path(__file__).resolve().parents[1]
_AUTH_PATH = _ROOT / "specs/mesc-experiment-0/mrl-0803-isolation-authorization-v1.json"


def _records() -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for index in range(16):
        household = index // 2 if index < 4 else index
        rows.append(
            {
                "address": [
                    {
                        "city": f"City-{household:02d}",
                        "country": "US",
                        "postalCode": f"{10000 + household}",
                        "state": "Massachusetts",
                    }
                ],
                "birthDate": f"19{60 + index:02d}-01-{index + 1:02d}",
                "gender": "female" if index % 2 == 0 else "male",
                "id": f"patient-{index:02d}",
                "resourceType": "Patient",
            }
        )
    return tuple(rows)


def _record_id(row: dict[str, object]) -> str:
    value = row["id"]
    assert isinstance(value, str)
    return value


def _corpus() -> bytes:
    records: list[dict[str, object]] = list(_records())
    records.sort(key=_record_id)
    return canonical_jsonl_bytes(records)


def _authorization_bytes(corpus: bytes, *, threshold: tuple[int, int] = (4, 5)) -> bytes:
    document = json.loads(_AUTH_PATH.read_bytes())
    document["corpus"]["corpus_sha256"] = hashlib.sha256(corpus).hexdigest()
    document["corpus"]["byte_count"] = len(corpus)
    document["corpus"]["record_count"] = 16
    document["contamination_policy"]["near_structural_jaccard_threshold"] = {
        "denominator": threshold[1],
        "numerator": threshold[0],
    }
    return canonical_json_bytes(document)


def _authorization(
    monkeypatch: pytest.MonkeyPatch,
    corpus: bytes,
    *,
    threshold: tuple[int, int] = (4, 5),
) -> isolation.MRL0803IsolationAuthorization:
    raw = _authorization_bytes(corpus, threshold=threshold)
    monkeypatch.setattr(isolation, "_AUTHORIZATION_SHA256", hashlib.sha256(raw).hexdigest())
    return isolation.parse_mrl_0803_isolation_authorization(raw)


def _qualify(
    monkeypatch: pytest.MonkeyPatch,
    *,
    threshold: tuple[int, int] = (4, 5),
) -> tuple[bytes, isolation.MRL0803IsolationAuthorization, isolation.MRL0803IsolationQualification]:
    corpus = _corpus()
    authorization = _authorization(monkeypatch, corpus, threshold=threshold)
    result = isolation.qualify_mrl_0803_isolation(
        corpus,
        authorization=authorization,
        repository_commit="a" * 40,
        repository_tree="b" * 40,
    )
    return corpus, authorization, result


def test_committed_authorization_is_exact_and_non_authoritative() -> None:
    raw = _AUTH_PATH.read_bytes()
    authorization = isolation.parse_mrl_0803_isolation_authorization(raw)

    assert authorization.authorization_sha256 == hashlib.sha256(raw).hexdigest()
    assert authorization.corpus_sha256 == (
        "977f5faa543f479276ad3742af797435e2ee732d8b9e8e594fabbf99e916b16e"
    )
    assert authorization.corpus_byte_count == 3281
    assert authorization.corpus_record_count == 16
    assert authorization.tier_counts == (8, 4, 4)
    assert authorization.near_threshold.numerator == 4
    assert authorization.near_threshold.denominator == 5


def test_isolation_output_is_deterministic_and_untrusted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus, authorization, first = _qualify(monkeypatch)
    second = isolation.qualify_mrl_0803_isolation(
        corpus,
        authorization=authorization,
        repository_commit="a" * 40,
        repository_tree="b" * 40,
    )

    assert first == second
    assert first.tier_counts == (8, 4, 4)
    parsed = parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0803"
    assert parsed.subject_sha256 == hashlib.sha256(corpus).hexdigest()
    with pytest.raises(MRLRealPreflightEvidenceError, match="not trusted"):
        admit_mrl_real_preflight_evidence(first.evidence_bytes, expected_task_id="MRL-0803")


def test_household_groups_never_cross_tiers(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, result = _qualify(monkeypatch)
    manifest = json.loads(result.split_manifest_bytes)
    tier_by_patient = {
        patient_id: tier["tier"] for tier in manifest["tiers"] for patient_id in tier["patient_ids"]
    }

    assert tier_by_patient["patient-00"] == tier_by_patient["patient-01"]
    assert tier_by_patient["patient-02"] == tier_by_patient["patient-03"]
    assert len(tier_by_patient) == 16


def test_decontamination_report_is_scoped_and_does_not_claim_pretraining(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, result = _qualify(monkeypatch)
    report = json.loads(result.decontamination_report_bytes)

    assert report["contamination_disposition"] == "PASS"
    assert report["contamination_scope"] == "MESC_CONTROLLED_SURFACES_ONLY"
    assert report["exact_cross_tier_duplicate_count"] == 0
    assert report["synthetic_household_cross_tier_overlap_count"] == 0
    assert report["semantic_detector_disposition"] == (
        "NOT_APPLICABLE_STRUCTURAL_PATIENT_PROJECTION"
    )
    assert report["upstream_pretraining_overlap_assessed"] is False
    assert report["upstream_pretraining_overlap_claimed"] is False


def test_lineage_report_keeps_tier3_out_of_training_and_adaptive_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, result = _qualify(monkeypatch)
    lineage = json.loads(result.lineage_report_bytes)

    assert lineage["training_surface_present"] is False
    assert lineage["tier3_allowed_in_training"] is False
    assert lineage["tier3_allowed_in_adaptive_search"] is False
    assert lineage["tier3_item_access_by_research_process"] is False
    tier3 = next(row for row in lineage["tiers"] if row["tier"] == "TIER_3_SEALED")
    assert tier3["tier_sha256"] == result.heldout_evaluation_sha256
    assert "patient_ids" not in tier3


def test_wrong_or_noncanonical_corpus_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = _corpus()
    authorization = _authorization(monkeypatch, corpus)

    with pytest.raises(isolation.MRL0803IsolationError, match="SHA-256"):
        isolation.qualify_mrl_0803_isolation(
            corpus.replace(b"City-00", b"City-XX", 1),
            authorization=authorization,
            repository_commit="a" * 40,
            repository_tree="b" * 40,
        )

    document = json.loads(corpus.splitlines()[0])
    noncanonical = (
        json.dumps(document, indent=2).encode()
        + b"\n"
        + b"".join(corpus.splitlines(keepends=True)[1:])
    )
    raw = _authorization_bytes(noncanonical)
    monkeypatch.setattr(isolation, "_AUTHORIZATION_SHA256", hashlib.sha256(raw).hexdigest())
    bad_authorization = isolation.parse_mrl_0803_isolation_authorization(raw)
    with pytest.raises(isolation.MRL0803IsolationError, match="canonical"):
        isolation.qualify_mrl_0803_isolation(
            noncanonical,
            authorization=bad_authorization,
            repository_commit="a" * 40,
            repository_tree="b" * 40,
        )


def test_near_structural_threshold_blocks_when_frozen_bound_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus = _corpus()
    authorization = _authorization(monkeypatch, corpus, threshold=(1, 10))

    with pytest.raises(isolation.MRL0803IsolationError, match="near-structural"):
        isolation.qualify_mrl_0803_isolation(
            corpus,
            authorization=authorization,
            repository_commit="a" * 40,
            repository_tree="b" * 40,
        )


def test_bundle_verification_recomputes_every_byte(monkeypatch: pytest.MonkeyPatch) -> None:
    corpus, authorization, result = _qualify(monkeypatch)
    verified = isolation.verify_mrl_0803_isolation_bundle(
        corpus,
        authorization=authorization,
        repository_commit="a" * 40,
        repository_tree="b" * 40,
        split_manifest_bytes=result.split_manifest_bytes,
        lineage_report_bytes=result.lineage_report_bytes,
        decontamination_report_bytes=result.decontamination_report_bytes,
        tier1_bytes=result.tier1_bytes,
        tier2_bytes=result.tier2_bytes,
        tier3_bytes=result.tier3_bytes,
        evidence_bytes=result.evidence_bytes,
    )
    assert verified.evidence_sha256 == result.evidence_sha256

    with pytest.raises(isolation.MRL0803IsolationError, match="evidence"):
        isolation.verify_mrl_0803_isolation_bundle(
            corpus,
            authorization=authorization,
            repository_commit="a" * 40,
            repository_tree="b" * 40,
            split_manifest_bytes=result.split_manifest_bytes,
            lineage_report_bytes=result.lineage_report_bytes,
            decontamination_report_bytes=result.decontamination_report_bytes,
            tier1_bytes=result.tier1_bytes,
            tier2_bytes=result.tier2_bytes,
            tier3_bytes=result.tier3_bytes,
            evidence_bytes=result.evidence_bytes + b" ",
        )
