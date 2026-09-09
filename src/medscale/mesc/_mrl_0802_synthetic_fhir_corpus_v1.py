"""Bounded synthetic-first FHIR corpus qualification for MRL-0802.

This module admits only the exact repository-owned fixture source authorized for Issue #391.
The pinned Synthea source is recorded as a candidate but remains non-admitted until its
terminology-bearing output receives separate exact rights qualification. No network,
credentials, PHI, model loading, inference, GPU execution, or training occurs here.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from typing import Final, cast

from medscale.dataset.builder.contracts import PipelineContext, StageResult
from medscale.dataset.builder.fingerprint import context_fingerprint
from medscale.dataset.builder.freeze import SplitAssignmentFreeze
from medscale.dataset.split import SplitStrategy
from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_jsonl_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_SCHEMA_VERSION: Final = "MESC-MRL-0802-SYNTHETIC-FHIR-AUTHORIZATION-V1"
_AUTHORIZATION_ID: Final = "MESC-MRL-0802-SYNTHETIC-FHIR-20260909-V1"
_AUTHORIZED_BASE_SHA: Final = "ef5a70e86ff829efe52e042aaa37ce4bb8c418fe"
_AUTHORIZED_BASE_TREE: Final = "0f93d3ead71a3b0c069e2c86550af00d0aa55964"
_ISSUE_BODY_SHA256: Final = "cc44934712f38e3663f38e689c8f3a735dc94ef78d946459a0b7ca96fb7647d9"
_ISSUE_CREATED_AT: Final = "2026-09-08T22:58:48Z"
_FIXTURE_PATH: Final = "data/mesc-mrl-0802-fhir-v1/source-fixtures.jsonl"
_FIXTURE_SHA256: Final = "042e5107b05f2383b04981a5bf0199610febdf3b01e3f66da8ef5e15d45db380"
_LICENSE_PATH: Final = "data/mesc-mrl-0802-fhir-v1/LICENSE.md"
_LICENSE_SHA256: Final = "594a0bb176594fa05559093c38b705524ac0863864415aa9553c58afb91c9f55"
_SYNTHEA_REVISION: Final = "0185c09ea9d10a822c6f5f3ef9bdcbcbe960c813"
_FHIR_VERSION: Final = "4.0.1"
_SEED: Final = 20260909
_ALLOWED_SYSTEM_PREFIXES: Final = ("urn:mesc:", "http://hl7.org/fhir/")
_PROHIBITED_TERMINOLOGY_MARKERS: Final = ("snomed", "loinc", "rxnorm")


class MRL0802SyntheticFHIRCorpusError(ValueError):
    """Raised when synthetic FHIR corpus qualification fails closed."""


@dataclass(frozen=True, slots=True)
class MRL0802CorpusAuthorization:
    """Validated exact source authorization bytes."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.canonical_bytes != canonical_mrl_0802_authorization_bytes():
            raise MRL0802SyntheticFHIRCorpusError(
                "MRL-0802 source authorization does not match the exact authorized scope"
            )
        object.__setattr__(
            self,
            "authorization_sha256",
            hashlib.sha256(self.canonical_bytes).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class MRL0802CorpusQualification:
    """Deterministic evidence candidate for one exact admitted corpus."""

    corpus_bytes: bytes = field(repr=False)
    rights_bytes: bytes = field(repr=False)
    provenance_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    corpus_sha256: str
    rights_evidence_sha256: str
    provenance_sha256: str
    evidence_sha256: str
    dataset_fingerprint: str
    split_freeze_fingerprint: str
    record_ids: tuple[str, ...]


def canonical_mrl_0802_authorization_bytes() -> bytes:
    """Return exact canonical Issue #391 source authorization bytes."""
    return canonical_json_bytes(_authorization_document())


def parse_mrl_0802_authorization(raw: bytes) -> MRL0802CorpusAuthorization:
    """Parse only the exact authorization bytes committed for Issue #391."""
    if type(raw) is not bytes or not raw:
        raise MRL0802SyntheticFHIRCorpusError("MRL-0802 authorization must be non-empty bytes")
    return MRL0802CorpusAuthorization(raw)


def build_mrl_0802_fixture_corpus(
    *,
    source_bytes: bytes,
    authorization: MRL0802CorpusAuthorization,
) -> MRL0802CorpusQualification:
    """Validate and bind the exact repository-owned FHIR fixture corpus."""
    if type(authorization) is not MRL0802CorpusAuthorization:
        raise MRL0802SyntheticFHIRCorpusError("authorization type is invalid")
    if hashlib.sha256(source_bytes).hexdigest() != _FIXTURE_SHA256:
        raise MRL0802SyntheticFHIRCorpusError("fixture source bytes are outside authorization")

    records = _parse_jsonl(source_bytes)
    if not records:
        raise MRL0802SyntheticFHIRCorpusError("fixture corpus must contain records")
    record_ids: list[str] = []
    for record in records:
        record_ids.append(_validate_bundle(record))
    if len(record_ids) != len(set(record_ids)):
        raise MRL0802SyntheticFHIRCorpusError("fixture bundle ids must be unique")
    if tuple(record_ids) != tuple(sorted(record_ids)):
        raise MRL0802SyntheticFHIRCorpusError("fixture bundles must be ordered by id")

    corpus_bytes = canonical_jsonl_bytes(records)
    if corpus_bytes != source_bytes:
        raise MRL0802SyntheticFHIRCorpusError("fixture source must already be canonical JSONL")
    corpus_sha256 = hashlib.sha256(corpus_bytes).hexdigest()

    stage = StageResult(
        stage_name="mrl_0802_synthetic_fhir_qualification",
        input_count=len(records),
        accepted=len(records),
        rejected=0,
        artifacts=(corpus_sha256,),
    )
    context = PipelineContext(
        root=".",
        config={
            "fhir_version": _FHIR_VERSION,
            "seed": _SEED,
            "source_sha256": _FIXTURE_SHA256,
        },
        results=(stage,),
        bundle_references=tuple(record_ids),
        validation_statuses=dict.fromkeys(record_ids, "PASS"),
    )
    dataset_fingerprint = context_fingerprint(context)
    split_freeze = SplitAssignmentFreeze(
        source_dataset_fingerprint=dataset_fingerprint,
        strategy=SplitStrategy.DETERMINISTIC_HASH_SPLIT,
        seed=_SEED,
        train=(),
        validation=(),
        test=tuple(record_ids),
    )

    rights_bytes = canonical_json_bytes(
        {
            "schema_version": "MESC-MRL-0802-RIGHTS-EVIDENCE-V1",
            "corpus_sha256": corpus_sha256,
            "source_kind": "repository_owned_hand_authored_synthetic_fhir",
            "source_license": "Apache-2.0",
            "license_path": _LICENSE_PATH,
            "license_sha256": _LICENSE_SHA256,
            "derivative_model_use": True,
            "commercial_use": True,
            "dua_required": False,
            "phi_present": False,
            "real_patient_data_present": False,
            "credentialed_source_used": False,
            "snomed_vendored": False,
            "loinc_present": False,
            "rxnorm_present": False,
            "rights_disposition": "PASS",
        }
    )
    rights_sha256 = hashlib.sha256(rights_bytes).hexdigest()
    provenance_bytes = canonical_json_bytes(
        {
            "schema_version": "MESC-MRL-0802-PROVENANCE-V1",
            "authorization_sha256": authorization.authorization_sha256,
            "source_path": _FIXTURE_PATH,
            "source_sha256": _FIXTURE_SHA256,
            "source_revision": _AUTHORIZED_BASE_SHA,
            "fhir_version": _FHIR_VERSION,
            "seed": _SEED,
            "record_ids": record_ids,
            "record_count": len(record_ids),
            "byte_count": len(corpus_bytes),
            "corpus_sha256": corpus_sha256,
            "dataset_fingerprint": dataset_fingerprint,
            "split_freeze_fingerprint": split_freeze.freeze_fingerprint,
            "split_role": "TIER_0_1_EVALUATION_ONLY",
            "transformation": "IDENTITY_CANONICAL_JSONL_VALIDATION_ONLY",
        }
    )
    provenance_sha256 = hashlib.sha256(provenance_bytes).hexdigest()
    evidence_bytes = canonical_json_bytes(
        {
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "task_id": "MRL-0802",
            "kind": "mesc.mrl.real_preflight.corpus_rights.v1",
            "disposition": "PASS",
            "subject_sha256": corpus_sha256,
            "payload": {
                "corpus_present": True,
                "corpus_id": "mesc-mrl-0802-fhir-v1",
                "byte_count": len(corpus_bytes),
                "corpus_sha256": corpus_sha256,
                "rights_disposition": "PASS",
                "rights_evidence_sha256": rights_sha256,
                "provenance_sha256": provenance_sha256,
                "access_authorization_sha256": authorization.authorization_sha256,
            },
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != "MRL-0802" or parsed.subject_sha256 != corpus_sha256:
        raise MRL0802SyntheticFHIRCorpusError("generated MRL-0802 evidence failed semantic binding")
    return MRL0802CorpusQualification(
        corpus_bytes=corpus_bytes,
        rights_bytes=rights_bytes,
        provenance_bytes=provenance_bytes,
        evidence_bytes=evidence_bytes,
        corpus_sha256=corpus_sha256,
        rights_evidence_sha256=rights_sha256,
        provenance_sha256=provenance_sha256,
        evidence_sha256=parsed.evidence_sha256,
        dataset_fingerprint=dataset_fingerprint,
        split_freeze_fingerprint=split_freeze.freeze_fingerprint,
        record_ids=tuple(record_ids),
    )


def _authorization_document() -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "authorization_id": _AUTHORIZATION_ID,
        "issue_number": 391,
        "issue_url": "https://github.com/TheHalfMoon/MESC/issues/391",
        "issue_created_at": _ISSUE_CREATED_AT,
        "issue_body_sha256": _ISSUE_BODY_SHA256,
        "authorized_base": {"main_sha": _AUTHORIZED_BASE_SHA, "main_tree": _AUTHORIZED_BASE_TREE},
        "fhir": {"release": "R4", "version": _FHIR_VERSION, "export_mode": "JSON"},
        "fixture_source": {
            "path": _FIXTURE_PATH,
            "sha256": _FIXTURE_SHA256,
            "license_path": _LICENSE_PATH,
            "license_sha256": _LICENSE_SHA256,
            "record_count": 3,
            "admission": "AUTHORIZED",
        },
        "synthea": {
            "repository": "synthetichealth/synthea",
            "version": "v4.0.0",
            "tag_object": _SYNTHEA_REVISION,
            "software_license": "Apache-2.0",
            "admission": "NOT_ADMITTED_PENDING_TERMINOLOGY_RIGHTS",
        },
        "generation": {"seed": _SEED, "population_bound": 3, "output": "canonical_fhir_jsonl"},
        "rights_policy": {
            "synthetic_only": True,
            "repository_owned_fixtures_allowed": True,
            "real_patient_data_allowed": False,
            "phi_allowed": False,
            "credentialed_sources_allowed": False,
            "snomed_vendoring_allowed": False,
            "unknown_rights_allowed": False,
            "derivative_model_use_required": True,
            "commercial_use_required": True,
        },
        "authority": {
            "model_loading_authorized": False,
            "inference_authorized": False,
            "gpu_execution_authorized": False,
            "training_authorized": False,
            "weight_mutation_authorized": False,
            "trust_registry_mutation_authorized": False,
        },
    }


def _parse_jsonl(raw: bytes) -> list[dict[str, object]]:
    if type(raw) is not bytes:
        raise MRL0802SyntheticFHIRCorpusError("fixture source must be exact bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MRL0802SyntheticFHIRCorpusError("fixture source must be UTF-8") from exc
    if not text.endswith("\n") or "\r" in text:
        raise MRL0802SyntheticFHIRCorpusError("fixture source requires LF-terminated JSONL")
    records: list[dict[str, object]] = []
    for index, line in enumerate(text.splitlines()):
        try:
            value = json.loads(line)
        except ValueError as exc:
            raise MRL0802SyntheticFHIRCorpusError(
                f"fixture record {index} is invalid JSON"
            ) from exc
        if type(value) is not dict:
            raise MRL0802SyntheticFHIRCorpusError(f"fixture record {index} must be an object")
        records.append(cast(dict[str, object], value))
    return records


def _validate_bundle(bundle: dict[str, object]) -> str:
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection":
        raise MRL0802SyntheticFHIRCorpusError(
            "every admitted record must be a FHIR collection Bundle"
        )
    bundle_id = bundle.get("id")
    if type(bundle_id) is not str or not bundle_id.startswith("fixture-"):
        raise MRL0802SyntheticFHIRCorpusError(
            "bundle id must be an authorized synthetic fixture id"
        )
    _require_synthetic_tag(bundle, label=f"Bundle/{bundle_id}")
    entries = bundle.get("entry")
    if type(entries) is not list or not entries:
        raise MRL0802SyntheticFHIRCorpusError("bundle entry must be non-empty")
    for entry in entries:
        if type(entry) is not dict or type(entry.get("resource")) is not dict:
            raise MRL0802SyntheticFHIRCorpusError("bundle entries must contain resources")
        full_url = entry.get("fullUrl")
        if type(full_url) is not str or not full_url.startswith("urn:uuid:"):
            raise MRL0802SyntheticFHIRCorpusError("bundle entry fullUrl must be a UUID URN")
        try:
            uuid.UUID(full_url.removeprefix("urn:uuid:"))
        except ValueError as exc:
            raise MRL0802SyntheticFHIRCorpusError(
                "bundle entry fullUrl must contain a valid UUID"
            ) from exc
        resource = cast(dict[str, object], entry["resource"])
        _require_synthetic_tag(resource, label=str(resource.get("resourceType", "resource")))
        _reject_prohibited_fields(resource)
        _validate_terminology(resource)
    return bundle_id


def _require_synthetic_tag(resource: dict[str, object], *, label: str) -> None:
    meta = resource.get("meta")
    tags = meta.get("tag") if type(meta) is dict else None
    if (
        type(tags) is not list
        or {
            "system": "urn:mesc:provenance",
            "code": "synthetic-fixture",
        }
        not in tags
    ):
        raise MRL0802SyntheticFHIRCorpusError(f"{label} lacks exact synthetic provenance tag")


def _reject_prohibited_fields(resource: dict[str, object]) -> None:
    prohibited = {"address", "telecom", "contact", "photo"}
    if prohibited.intersection(resource):
        raise MRL0802SyntheticFHIRCorpusError(
            "identity-bearing patient contact fields are prohibited"
        )
    serialized = json.dumps(resource, sort_keys=True).lower()
    for marker in ("mimic", "real-patient", "credential", "patient@example", "@example.com"):
        if marker in serialized:
            raise MRL0802SyntheticFHIRCorpusError(
                "real/credentialed/identity-bearing source marker prohibited"
            )


def _validate_terminology(value: object) -> None:
    if type(value) is dict:
        mapping = cast(dict[str, object], value)
        for key, item in mapping.items():
            if key == "system" and type(item) is str:
                lowered = item.lower()
                if any(marker in lowered for marker in _PROHIBITED_TERMINOLOGY_MARKERS):
                    raise MRL0802SyntheticFHIRCorpusError(
                        "unqualified external terminology is prohibited"
                    )
                if not item.startswith(_ALLOWED_SYSTEM_PREFIXES):
                    raise MRL0802SyntheticFHIRCorpusError(
                        "unknown terminology system is prohibited"
                    )
            _validate_terminology(item)
    elif type(value) is list:
        for item in cast(list[object], value):
            _validate_terminology(item)
