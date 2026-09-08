from __future__ import annotations

import json
from pathlib import Path

import pytest

from medscale.mesc._mrl_0802_synthetic_fhir_corpus_v1 import (
    MRL0802SyntheticFHIRCorpusError,
    build_mrl_0802_fixture_corpus,
    canonical_mrl_0802_authorization_bytes,
    parse_mrl_0802_authorization,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data/mesc-mrl-0802-fhir-v1/source-fixtures.jsonl"
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-authorization-v1.json"


def _qualification():
    authorization = parse_mrl_0802_authorization(AUTH.read_bytes())
    return build_mrl_0802_fixture_corpus(
        source_bytes=FIXTURES.read_bytes(), authorization=authorization
    )


def test_authorization_artifact_is_exact_canonical_bytes() -> None:
    assert AUTH.read_bytes() == canonical_mrl_0802_authorization_bytes()


def test_fixture_corpus_produces_valid_real_preflight_evidence() -> None:
    result = _qualification()
    parsed = parse_mrl_real_preflight_evidence(result.evidence_bytes)
    assert parsed.task_id == "MRL-0802"
    assert parsed.kind == "mesc.mrl.real_preflight.corpus_rights.v1"
    assert parsed.subject_sha256 == result.corpus_sha256
    assert result.record_ids == ("fixture-001", "fixture-002", "fixture-003")


def test_rights_and_provenance_bind_actual_corpus() -> None:
    result = _qualification()
    rights = json.loads(result.rights_bytes)
    provenance = json.loads(result.provenance_bytes)
    assert rights["rights_disposition"] == "PASS"
    assert rights["phi_present"] is False
    assert rights["snomed_vendored"] is False
    assert provenance["corpus_sha256"] == result.corpus_sha256
    assert provenance["byte_count"] == len(result.corpus_bytes)
    assert provenance["split_role"] == "TIER_0_1_EVALUATION_ONLY"


def test_fixture_bytes_fail_closed_on_mutation() -> None:
    authorization = parse_mrl_0802_authorization(AUTH.read_bytes())
    with pytest.raises(MRL0802SyntheticFHIRCorpusError, match="outside authorization"):
        build_mrl_0802_fixture_corpus(
            source_bytes=FIXTURES.read_bytes() + b"\n", authorization=authorization
        )


def test_authorization_bytes_fail_closed_on_mutation() -> None:
    with pytest.raises(MRL0802SyntheticFHIRCorpusError, match="exact authorized scope"):
        parse_mrl_0802_authorization(canonical_mrl_0802_authorization_bytes() + b"\n")
