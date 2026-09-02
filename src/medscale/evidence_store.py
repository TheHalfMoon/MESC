"""Evidence Object persistence: canonical, content-addressed, self-describing.

Same contract as the corpus store: one canonical-JSON object per line, LF-terminated,
sorted by ``evidence_id``, deduplicated by construction on write, ``"format": 1``
markers with tolerant readers. Two evidence files built from the same objects are
byte-identical on any machine — the property every downstream consumer (benchmarks,
knowledge views, papers) will depend on for a decade.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from medscale.evidence import (
    EvidenceObject,
    ExtractionMethod,
    StudyType,
    VerificationState,
)
from medscale.provenance import Provenance, RetrievalStatus, SourceAPI
from medscale.reproducibility import canonical_json, content_hash

__all__ = [
    "evidence_from_dict",
    "evidence_to_dict",
    "load_evidence",
    "migrate_legacy_evidence_file",
    "write_evidence",
]

_FORMAT_1_IDENTITY_VERSION = 1


def evidence_to_dict(obj: EvidenceObject) -> dict[str, Any]:
    if obj.identity_version != _FORMAT_1_IDENTITY_VERSION:
        raise ValueError("format-1 evidence persistence supports only identity_version=1")
    return {
        "format": 1,
        "evidence_id": obj.evidence_id,
        "claim": obj.claim,
        "study_type": obj.study_type.value,
        "provenance": {
            "source_api": obj.provenance.source_api.value,
            "identifier": obj.provenance.identifier,
            "verified_at": obj.provenance.verified_at,
            "raw_response_sha256": obj.provenance.raw_response_sha256,
            "status": obj.provenance.status.value,
        },
        "created_at": obj.created_at,
        "source_record_id": obj.source_record_id,
        "population": obj.population,
        "intervention": obj.intervention,
        "comparator": obj.comparator,
        "outcome": obj.outcome,
        "effect_measure": obj.effect_measure,
        "effect_value": obj.effect_value,
        "grading_scheme": obj.grading_scheme,
        "evidence_level": obj.evidence_level,
        "extraction_method": obj.extraction_method.value,
        "verification": obj.verification.value,
        "schema_version": obj.schema_version,
    }


def _evidence_object_from_dict(data: dict[str, Any]) -> EvidenceObject:
    provenance = data["provenance"]
    obj = EvidenceObject(
        claim=data["claim"],
        study_type=StudyType(data["study_type"]),
        provenance=Provenance(
            source_api=SourceAPI(provenance["source_api"]),
            identifier=provenance["identifier"],
            verified_at=provenance["verified_at"],
            raw_response_sha256=provenance["raw_response_sha256"],
            status=RetrievalStatus(provenance["status"]),
        ),
        created_at=data["created_at"],
        source_record_id=data.get("source_record_id"),
        population=data.get("population"),
        intervention=data.get("intervention"),
        comparator=data.get("comparator"),
        outcome=data.get("outcome"),
        effect_measure=data.get("effect_measure"),
        effect_value=data.get("effect_value"),
        grading_scheme=data["grading_scheme"],
        evidence_level=data["evidence_level"],
        extraction_method=ExtractionMethod(data["extraction_method"]),
        verification=VerificationState(data["verification"]),
        identity_version=data.get("identity_version", _FORMAT_1_IDENTITY_VERSION),
        schema_version=data["schema_version"],
    )
    if obj.identity_version != _FORMAT_1_IDENTITY_VERSION:
        raise ValueError("format-1 evidence persistence supports only identity_version=1")
    return obj


def _legacy_evidence_id_v0(obj: EvidenceObject) -> str:
    """Return the pre-ADR-0018 identifier for explicit migration detection only."""
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


def evidence_from_dict(data: dict[str, Any]) -> EvidenceObject:
    """Load one format-1 object without silently reminting a recognized legacy id."""
    obj = _evidence_object_from_dict(data)
    persisted_id = data.get("evidence_id")
    if (
        isinstance(persisted_id, str)
        and persisted_id != obj.evidence_id
        and persisted_id == _legacy_evidence_id_v0(obj)
    ):
        raise ValueError(
            "legacy evidence_id requires explicit migration via migrate_legacy_evidence_file"
        )
    return obj


def write_evidence(path: Path, objects: Iterable[EvidenceObject]) -> int:
    """Write canonical unique evidence, rejecting same-id persisted-content conflicts."""
    serialized_by_id: dict[str, str] = {}
    for obj in objects:
        evidence_id = obj.evidence_id
        serialized = canonical_json(evidence_to_dict(obj))
        previous = serialized_by_id.get(evidence_id)
        if previous is not None and previous != serialized:
            raise ValueError(
                "conflicting persisted payloads share evidence_id; refusing order-dependent dedupe"
            )
        serialized_by_id.setdefault(evidence_id, serialized)

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [serialized_by_id[eid] for eid in sorted(serialized_by_id)]
    # Atomic replace: a crash mid-write must never leave a truncated evidence store.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
    tmp.replace(path)
    return len(serialized_by_id)


def migrate_legacy_evidence_file(source: Path, destination: Path) -> dict[str, str]:
    """Rewrite recognized pre-ADR-0018 format-1 ids into a distinct new artifact.

    The source is never modified. The returned mapping binds every persisted source id to
    the emitted ADR-0018 id so downstream references can be migrated explicitly.
    """
    if source.resolve() == destination.resolve():
        raise ValueError("legacy evidence migration requires a distinct destination path")

    objects: list[EvidenceObject] = []
    identity_map: dict[str, str] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("evidence line must be a JSON object")
        obj = _evidence_object_from_dict(data)
        persisted_id = data.get("evidence_id")
        if not isinstance(persisted_id, str):
            raise ValueError("legacy evidence migration requires a persisted evidence_id")
        if persisted_id not in {obj.evidence_id, _legacy_evidence_id_v0(obj)}:
            raise ValueError("unrecognized evidence_id cannot be migrated automatically")
        identity_map[persisted_id] = obj.evidence_id
        objects.append(obj)

    write_evidence(destination, objects)
    return dict(sorted(identity_map.items()))


def load_evidence(path: Path) -> tuple[EvidenceObject, ...]:
    """Load and validate evidence, rejecting order-dependent same-id conflicts."""
    if not path.exists():
        return ()

    objects: list[EvidenceObject] = []
    serialized_by_id: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError("evidence line must be a JSON object")
        obj = evidence_from_dict(data)
        serialized = canonical_json(evidence_to_dict(obj))
        previous = serialized_by_id.get(obj.evidence_id)
        if previous is not None and previous != serialized:
            raise ValueError(
                "conflicting persisted payloads share evidence_id; refusing order-dependent load"
            )
        serialized_by_id.setdefault(obj.evidence_id, serialized)
        objects.append(obj)
    return tuple(objects)
