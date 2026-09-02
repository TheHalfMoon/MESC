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
from medscale.reproducibility import canonical_json

__all__ = ["evidence_from_dict", "evidence_to_dict", "load_evidence", "write_evidence"]


def evidence_to_dict(obj: EvidenceObject) -> dict[str, Any]:
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
        "identity_version": obj.identity_version,
        "schema_version": obj.schema_version,
    }


def evidence_from_dict(data: dict[str, Any]) -> EvidenceObject:
    provenance = data["provenance"]
    return EvidenceObject(
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
        identity_version=data.get("identity_version", 1),
        schema_version=data["schema_version"],
    )


def write_evidence(path: Path, objects: Iterable[EvidenceObject]) -> int:
    """Write objects deduplicated by ``evidence_id``, sorted, LF. Returns unique count.

    First occurrence wins on duplicate ids; identity is the claim's content, so a
    duplicate means the same claim from the same source was extracted twice.
    """
    unique: dict[str, EvidenceObject] = {}
    for obj in objects:
        unique.setdefault(obj.evidence_id, obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [canonical_json(evidence_to_dict(unique[eid])) for eid in sorted(unique)]
    # Atomic replace: a crash mid-write must never leave a truncated evidence store.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8", newline="\n")
    tmp.replace(path)
    return len(unique)


def load_evidence(path: Path) -> tuple[EvidenceObject, ...]:
    """Load an evidence file, re-running every object validation. Missing file -> ()."""
    if not path.exists():
        return ()
    return tuple(
        evidence_from_dict(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
