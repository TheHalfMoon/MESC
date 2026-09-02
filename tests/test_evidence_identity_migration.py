"""ADR-0018 persistence determinism and explicit legacy-id migration regressions."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from medscale.evidence import EvidenceObject, StudyType
from medscale.evidence_store import (
    evidence_from_dict,
    evidence_to_dict,
    load_evidence,
    migrate_legacy_evidence_file,
    write_evidence,
)
from medscale.provenance import Provenance, SourceAPI
from medscale.reproducibility import canonical_json, content_hash

_TS = "2026-07-10T00:00:00+00:00"


def _evidence(schema_version: str = "1") -> EvidenceObject:
    return EvidenceObject(
        claim="Identity migration claim.",
        study_type=StudyType.COHORT,
        provenance=Provenance(SourceAPI.PUBMED, "10.1000/identity-migration", _TS, "b" * 64),
        created_at=_TS,
        schema_version=schema_version,
    )


def _legacy_id(obj: EvidenceObject) -> str:
    return content_hash(
        {
            "claim": obj.claim,
            "study_type": obj.study_type.value,
            "population": obj.population,
            "intervention": obj.intervention,
            "comparator": obj.comparator,
            "outcome": obj.outcome,
            "effect_measure": obj.effect_measure,
            "effect_value": obj.effect_value,
            "source_api": obj.provenance.source_api.value,
            "source_identifier": obj.provenance.identifier,
            "schema_version": obj.schema_version,
        }
    )


def test_same_identity_with_different_persisted_payload_fails_closed(tmp_path: Path) -> None:
    first = _evidence("1")
    second = dataclasses.replace(first, schema_version="2")
    assert first.evidence_id == second.evidence_id

    for objects in ((first, second), (second, first)):
        with pytest.raises(ValueError, match="order-dependent dedupe"):
            write_evidence(tmp_path / "objects.jsonl", objects)


def test_reader_requires_explicit_migration_for_recognized_legacy_id() -> None:
    obj = _evidence()
    payload = evidence_to_dict(obj)
    payload["evidence_id"] = _legacy_id(obj)
    assert payload["evidence_id"] != obj.evidence_id

    with pytest.raises(ValueError, match="explicit migration"):
        evidence_from_dict(payload)


def test_legacy_migration_rewrites_to_new_id_and_returns_mapping(tmp_path: Path) -> None:
    obj = _evidence()
    payload = evidence_to_dict(obj)
    legacy_id = _legacy_id(obj)
    payload["evidence_id"] = legacy_id
    source = tmp_path / "legacy.jsonl"
    destination = tmp_path / "migrated.jsonl"
    source.write_text(canonical_json(payload) + "\n", encoding="utf-8")

    identity_map = migrate_legacy_evidence_file(source, destination)

    assert identity_map == {legacy_id: obj.evidence_id}
    assert json.loads(source.read_text(encoding="utf-8"))["evidence_id"] == legacy_id
    migrated_payload = json.loads(destination.read_text(encoding="utf-8"))
    assert migrated_payload["evidence_id"] == obj.evidence_id
    assert "identity_version" not in migrated_payload
    (migrated,) = load_evidence(destination)
    assert migrated.evidence_id == obj.evidence_id


def test_legacy_migration_refuses_in_place_rewrite(tmp_path: Path) -> None:
    path = tmp_path / "legacy.jsonl"
    path.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="distinct destination"):
        migrate_legacy_evidence_file(path, path)
