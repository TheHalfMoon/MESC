"""Deterministic MRL-0807 evaluator and sealed Tier-3 freeze for bounded RQ1/FHIR.

This module freezes evaluator identities and deterministic metric semantics only. It does
not execute a model, disclose sealed Tier-3 items, mutate trust, train, promote, or release.
External HL7 validator custody is proven by the control-plane qualifier after producer merge.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_AUTHORIZATION_SHA256: Final = "018e095c6623c6c1fd5ac90c69824472c4a29c8100873b3a6a25540e0b587f9d"
_AUTH_SCHEMA: Final = "MESC-MRL-0807-EVALUATOR-FREEZE-AUTHORIZATION-V1"
_EVALUATOR_SCHEMA: Final = "MESC-MRL-0807-EVALUATOR-IDENTITY-V1"
_CONTRACT_SCHEMA: Final = "MESC-MRL-0807-RQ1-EVALUATION-CONTRACT-V1"
_SEALED_SCHEMA: Final = "MESC-MRL-0807-SEALED-TIER3-IDENTITY-V1"
_RECEIPT_SCHEMA: Final = "MESC-MRL-0807-EVALUATOR-FREEZE-RECEIPT-V1"
_TASK: Final = "MRL-0807"
_KIND: Final = "mesc.mrl.real_preflight.evaluators.v1"
_CANDIDATE: Final = "mrl-rq1-fhir-grammar-decoupling-v1"
_CORPUS_SHA256: Final = "977f5faa543f479276ad3742af797435e2ee732d8b9e8e594fabbf99e916b16e"
_HELDOUT_SHA256: Final = "a74ca84315459622b38a437fd31b9b82058701c5a28798ced3c8deac5a5f9247"
_HL7_SHA256: Final = "1106b9d58f9e363e47bea7c4fc065841e5fc91fe9d062775c3bfdd212bd653cc"
_HL7_SIZE: Final = 200_928_617
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_PROJECTION_FIELDS: Final = (
    "address.city",
    "address.country",
    "address.postalCode",
    "address.state",
    "birthDate",
    "deceasedBoolean",
    "gender",
    "id",
    "resourceType",
)


class MRL0807EvaluatorFreezeError(ValueError):
    """Raised when MRL-0807 evaluator-freeze material fails closed."""


@dataclass(frozen=True, slots=True)
class SetF1Score:
    """Exact rational set-F1 counts without binary floating point."""

    true_positive_count: int
    predicted_count: int
    reference_count: int
    numerator: int
    denominator: int

    @property
    def is_perfect(self) -> bool:
        return self.numerator == self.denominator


@dataclass(frozen=True, slots=True)
class StructuralValidationSummary:
    """Normalized machine-readable HL7 OperationOutcome severity counts."""

    valid: bool
    fatal_count: int
    error_count: int
    warning_count: int
    information_count: int


@dataclass(frozen=True, slots=True)
class MRL0807EvaluatorQualification:
    """Deterministic untrusted MRL-0807 freeze receipt and evidence candidate."""

    freeze_receipt_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    evaluator_identity_sha256: str
    evaluation_contract_sha256: str
    sealed_tier3_identity_sha256: str
    freeze_receipt_sha256: str
    evidence_sha256: str


def patient_projection_triples(resource: dict[str, object]) -> tuple[tuple[str, str, str], ...]:
    """Project one Patient to the exact admitted RQ1 `(type, field, value)` surface."""
    if type(resource) is not dict or resource.get("resourceType") != "Patient":
        raise MRL0807EvaluatorFreezeError("content-retention scorer requires one Patient object")
    triples: set[tuple[str, str, str]] = {("Patient", "resourceType", "Patient")}
    for field_name in ("id", "birthDate", "gender"):
        value = resource.get(field_name)
        if value is None:
            continue
        if type(value) is not str or not value:
            raise MRL0807EvaluatorFreezeError(f"Patient.{field_name} must be non-empty text")
        triples.add(("Patient", field_name, value))
    deceased = resource.get("deceasedBoolean")
    if deceased is not None:
        if type(deceased) is not bool:
            raise MRL0807EvaluatorFreezeError("Patient.deceasedBoolean must be an exact boolean")
        triples.add(("Patient", "deceasedBoolean", "true" if deceased else "false"))
    addresses = resource.get("address")
    if addresses is not None:
        if type(addresses) is not list:
            raise MRL0807EvaluatorFreezeError("Patient.address must be an exact list")
        for index, address in enumerate(addresses):
            if type(address) is not dict:
                raise MRL0807EvaluatorFreezeError(f"Patient.address[{index}] must be an object")
            for key in ("city", "country", "postalCode", "state"):
                value = address.get(key)
                if value is None:
                    continue
                if type(value) is not str or not value:
                    raise MRL0807EvaluatorFreezeError(
                        f"Patient.address[{index}].{key} must be non-empty text"
                    )
                triples.add(("Patient", f"address.{key}", value))
    return tuple(sorted(triples))


def score_patient_projection(
    reference: dict[str, object], candidate: dict[str, object]
) -> SetF1Score:
    """Return exact set-F1 counts for the admitted Patient projection only."""
    reference_set = set(patient_projection_triples(reference))
    predicted_set = set(patient_projection_triples(candidate))
    if not reference_set and not predicted_set:  # defensive; resourceType normally prevents this
        return SetF1Score(0, 0, 0, 1, 1)
    true_positive = len(reference_set & predicted_set)
    denominator = len(reference_set) + len(predicted_set)
    return SetF1Score(
        true_positive_count=true_positive,
        predicted_count=len(predicted_set),
        reference_count=len(reference_set),
        numerator=2 * true_positive,
        denominator=denominator,
    )


def normalize_hl7_validation_output(raw: bytes) -> StructuralValidationSummary:
    """Normalize HL7 validator JSON output represented as one FHIR OperationOutcome."""
    document = _parse_json_object(raw, label="HL7 validator output", require_canonical=False)
    if document.get("resourceType") != "OperationOutcome":
        raise MRL0807EvaluatorFreezeError("HL7 validator JSON must be an OperationOutcome")
    issues = document.get("issue")
    if type(issues) is not list or not issues:
        raise MRL0807EvaluatorFreezeError("HL7 validator OperationOutcome.issue must be non-empty")
    counts = {"fatal": 0, "error": 0, "warning": 0, "information": 0}
    for index, issue in enumerate(issues):
        if type(issue) is not dict:
            raise MRL0807EvaluatorFreezeError(f"OperationOutcome.issue[{index}] must be an object")
        severity = issue.get("severity")
        if severity not in counts:
            raise MRL0807EvaluatorFreezeError(
                f"OperationOutcome.issue[{index}].severity is unsupported"
            )
        counts[cast(str, severity)] += 1
    return StructuralValidationSummary(
        valid=counts["fatal"] == 0 and counts["error"] == 0,
        fatal_count=counts["fatal"],
        error_count=counts["error"],
        warning_count=counts["warning"],
        information_count=counts["information"],
    )


def qualify_mrl_0807_evaluators(
    authorization_raw: bytes,
    evaluator_identity_raw: bytes,
    evaluation_contract_raw: bytes,
    sealed_tier3_identity_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
    external_validator_sha256: str,
    external_validator_size: int,
) -> MRL0807EvaluatorQualification:
    """Assemble deterministic untrusted MRL-0807 evidence after exact artifact custody."""
    authorization = _validate_authorization(authorization_raw)
    repository_sha = _require_git_sha(repository_sha, "repository_sha")
    repository_tree = _require_git_sha(repository_tree, "repository_tree")
    if external_validator_sha256 != _HL7_SHA256 or external_validator_size != _HL7_SIZE:
        raise MRL0807EvaluatorFreezeError("external HL7 validator custody does not match freeze")

    evaluator_identity = _validate_evaluator_identity(evaluator_identity_raw)
    evaluator_identity_sha256 = hashlib.sha256(evaluator_identity_raw).hexdigest()
    sealed_identity = _validate_sealed_identity(sealed_tier3_identity_raw)
    sealed_identity_sha256 = hashlib.sha256(sealed_tier3_identity_raw).hexdigest()
    evaluation_contract = _validate_evaluation_contract(
        evaluation_contract_raw,
        evaluator_identity_sha256=evaluator_identity_sha256,
        sealed_tier3_identity_sha256=sealed_identity_sha256,
    )
    evaluation_contract_sha256 = hashlib.sha256(evaluation_contract_raw).hexdigest()

    receipt_bytes = canonical_json_bytes(
        {
            "authorization_sha256": hashlib.sha256(authorization_raw).hexdigest(),
            "candidate_id": _CANDIDATE,
            "evaluation_contract_sha256": evaluation_contract_sha256,
            "evaluator_identity_sha256": evaluator_identity_sha256,
            "external_validator_sha256": external_validator_sha256,
            "external_validator_size": external_validator_size,
            "non_promotional": True,
            "promotion_authority_present": False,
            "repository_sha": repository_sha,
            "repository_tree": repository_tree,
            "schema_version": _RECEIPT_SCHEMA,
            "sealed_tier3_identity_sha256": sealed_identity_sha256,
            "task_id": _TASK,
        }
    )
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    evidence_bytes = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _KIND,
            "payload": {
                "evaluation_contract_sha256": evaluation_contract_sha256,
                "evaluator_identity_sha256": evaluator_identity_sha256,
                "non_promotional": True,
                "promotion_authority_present": False,
                "sealed_tier3_identity_sha256": sealed_identity_sha256,
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": receipt_sha256,
            "task_id": _TASK,
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != _TASK or parsed.subject_sha256 != receipt_sha256:
        raise MRL0807EvaluatorFreezeError("produced MRL-0807 evidence failed semantic self-check")
    if authorization["candidate_id"] != evaluation_contract["candidate_id"]:
        raise MRL0807EvaluatorFreezeError("authorization and evaluation contract candidate differ")
    if evaluator_identity["candidate_id"] != sealed_identity["candidate_id"]:
        raise MRL0807EvaluatorFreezeError("frozen evaluator and sealed identity candidate differ")
    return MRL0807EvaluatorQualification(
        freeze_receipt_bytes=receipt_bytes,
        evidence_bytes=evidence_bytes,
        evaluator_identity_sha256=evaluator_identity_sha256,
        evaluation_contract_sha256=evaluation_contract_sha256,
        sealed_tier3_identity_sha256=sealed_identity_sha256,
        freeze_receipt_sha256=receipt_sha256,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )


def verify_mrl_0807_bundle(
    authorization_raw: bytes,
    evaluator_identity_raw: bytes,
    evaluation_contract_raw: bytes,
    sealed_tier3_identity_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
    external_validator_sha256: str,
    external_validator_size: int,
    freeze_receipt_bytes: bytes,
    evidence_bytes: bytes,
) -> MRL0807EvaluatorQualification:
    """Recompute and require byte-identical supplied MRL-0807 receipt/evidence bytes."""
    expected = qualify_mrl_0807_evaluators(
        authorization_raw,
        evaluator_identity_raw,
        evaluation_contract_raw,
        sealed_tier3_identity_raw,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        external_validator_sha256=external_validator_sha256,
        external_validator_size=external_validator_size,
    )
    if freeze_receipt_bytes != expected.freeze_receipt_bytes:
        raise MRL0807EvaluatorFreezeError("supplied evaluator freeze receipt is not deterministic")
    if evidence_bytes != expected.evidence_bytes:
        raise MRL0807EvaluatorFreezeError("supplied MRL-0807 evidence is not deterministic")
    return expected


def _validate_authorization(raw: bytes) -> dict[str, object]:
    document = _parse_json_object(raw, label="MRL-0807 authorization", require_canonical=True)
    if hashlib.sha256(raw).hexdigest() != _AUTHORIZATION_SHA256:
        raise MRL0807EvaluatorFreezeError("MRL-0807 authorization bytes do not match authority")
    if document.get("schema_version") != _AUTH_SCHEMA or document.get("task_id") != _TASK:
        raise MRL0807EvaluatorFreezeError("MRL-0807 authorization identity is invalid")
    if document.get("authorization_state") != "AUTHORIZED":
        raise MRL0807EvaluatorFreezeError("MRL-0807 authorization is not active")
    if document.get("candidate_id") != _CANDIDATE:
        raise MRL0807EvaluatorFreezeError("MRL-0807 authorization candidate is invalid")
    return document


def _validate_evaluator_identity(raw: bytes) -> dict[str, object]:
    document = _parse_json_object(raw, label="evaluator identity", require_canonical=True)
    if document.get("schema_version") != _EVALUATOR_SCHEMA or document.get("task_id") != _TASK:
        raise MRL0807EvaluatorFreezeError("evaluator identity schema/task is invalid")
    if document.get("candidate_id") != _CANDIDATE or document.get("non_promotional") is not True:
        raise MRL0807EvaluatorFreezeError("evaluator identity scope is invalid")
    if document.get("promotion_authority_present") is not False:
        raise MRL0807EvaluatorFreezeError("evaluator identity must remain non-promotional")
    evaluators = document.get("evaluators")
    if type(evaluators) is not list or len(evaluators) != 2:
        raise MRL0807EvaluatorFreezeError("evaluator identity must freeze exactly two evaluators")
    by_id: dict[str, dict[str, object]] = {}
    for entry in evaluators:
        if type(entry) is not dict or type(entry.get("evaluator_id")) is not str:
            raise MRL0807EvaluatorFreezeError("evaluator identity entry is malformed")
        by_id[cast(str, entry["evaluator_id"])] = cast(dict[str, object], entry)
    structural = by_id.get("hl7-fhir-r4-structural-validator-6.10.4")
    content = by_id.get("medscale-patient-projection-set-f1-v1")
    if structural is None or content is None or len(by_id) != 2:
        raise MRL0807EvaluatorFreezeError("required evaluator identities are missing")
    artifact = structural.get("artifact")
    if type(artifact) is not dict:
        raise MRL0807EvaluatorFreezeError("HL7 evaluator artifact identity is malformed")
    if artifact.get("sha256") != _HL7_SHA256 or artifact.get("size_bytes") != _HL7_SIZE:
        raise MRL0807EvaluatorFreezeError("HL7 evaluator artifact identity drifted")
    if structural.get("output_style") != "json" or structural.get("fhir_version") != "4.0.1":
        raise MRL0807EvaluatorFreezeError("HL7 evaluator invocation scope drifted")
    if structural.get("invocation_template") != [
        "java",
        "-jar",
        "{validator_cli.jar}",
        "{resource.json}",
        "-version",
        "4.0",
        "-output-style",
        "json",
    ]:
        raise MRL0807EvaluatorFreezeError("HL7 evaluator invocation template drifted")
    if (
        structural.get("allowed_tiers") != [1, 2, 3]
        or structural.get("network_policy") != "NO_NETWORK_DURING_VALIDATION"
    ):
        raise MRL0807EvaluatorFreezeError("HL7 evaluator tier/network policy drifted")
    for field_name in ("adapter_source_sha256", "implementation_sha256"):
        value = (
            structural.get(field_name)
            if field_name == "adapter_source_sha256"
            else content.get(field_name)
        )
        _require_sha256(value, field_name)
    if content.get("projection_fields") != list(_PROJECTION_FIELDS):
        raise MRL0807EvaluatorFreezeError("content-retention projection fields drifted")
    if content.get("score_representation") != "EXACT_RATIONAL_COUNTS":
        raise MRL0807EvaluatorFreezeError("content-retention score representation drifted")
    if (
        content.get("allowed_tiers") != [1, 2, 3]
        or content.get("fuzzy_matching") is not False
        or content.get("llm_as_judge") is not False
    ):
        raise MRL0807EvaluatorFreezeError("content-retention evaluator policy drifted")
    return document


def _validate_evaluation_contract(
    raw: bytes, *, evaluator_identity_sha256: str, sealed_tier3_identity_sha256: str
) -> dict[str, object]:
    document = _parse_json_object(raw, label="evaluation contract", require_canonical=True)
    if document.get("schema_version") != _CONTRACT_SCHEMA or document.get("task_id") != _TASK:
        raise MRL0807EvaluatorFreezeError("evaluation contract schema/task is invalid")
    if document.get("candidate_id") != _CANDIDATE:
        raise MRL0807EvaluatorFreezeError("evaluation contract candidate is invalid")
    if document.get("corpus_sha256") != _CORPUS_SHA256:
        raise MRL0807EvaluatorFreezeError("evaluation contract corpus identity drifted")
    if document.get("heldout_evaluation_sha256") != _HELDOUT_SHA256:
        raise MRL0807EvaluatorFreezeError("evaluation contract held-out identity drifted")
    if document.get("evaluator_identity_sha256") != evaluator_identity_sha256:
        raise MRL0807EvaluatorFreezeError("evaluation contract evaluator binding drifted")
    if document.get("sealed_tier3_identity_sha256") != sealed_tier3_identity_sha256:
        raise MRL0807EvaluatorFreezeError("evaluation contract sealed Tier-3 binding drifted")
    if document.get("metric_ids") != [
        "fhir-structural-validity-v1",
        "patient-projection-set-f1-v1",
    ]:
        raise MRL0807EvaluatorFreezeError("evaluation contract metric bundle drifted")
    if document.get("projection_fields") != list(_PROJECTION_FIELDS):
        raise MRL0807EvaluatorFreezeError("evaluation contract projection fields drifted")
    if (
        document.get("collapse_falsification_guard")
        != "STRUCTURAL_VALIDITY_WITH_CONTENT_COLLAPSE_FALSIFIES_RQ1"
    ):
        raise MRL0807EvaluatorFreezeError("RQ1 collapse falsification guard drifted")
    if document.get("structural_validity_rule") != "NO_FATAL_OR_ERROR_OPERATIONOUTCOME_ISSUES":
        raise MRL0807EvaluatorFreezeError("structural-validity rule drifted")
    if document.get("content_retention_rule") != "EXACT_SET_F1_OVER_ADMITTED_PATIENT_PROJECTION":
        raise MRL0807EvaluatorFreezeError("content-retention rule drifted")
    if document.get("llm_as_judge_primary_metric") is not False:
        raise MRL0807EvaluatorFreezeError("LLM-as-judge is prohibited for the primary metric")
    if document.get("tier_policy") != {
        "tier_1": "DETAILED_ALLOWED",
        "tier_2": "AGGREGATE_AND_FAILURE_CLASS_ALLOWED",
        "tier_3": "AGGREGATE_ONLY",
    }:
        raise MRL0807EvaluatorFreezeError("evaluation tier policy drifted")
    if (
        document.get("non_promotional") is not True
        or document.get("promotion_authority_present") is not False
    ):
        raise MRL0807EvaluatorFreezeError("evaluation contract must remain non-promotional")
    return document


def _validate_sealed_identity(raw: bytes) -> dict[str, object]:
    document = _parse_json_object(raw, label="sealed Tier-3 identity", require_canonical=True)
    if document.get("schema_version") != _SEALED_SCHEMA or document.get("task_id") != _TASK:
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 identity schema/task is invalid")
    if document.get("candidate_id") != _CANDIDATE:
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 candidate is invalid")
    if (
        document.get("sealed_bytes_sha256") != _HELDOUT_SHA256
        or document.get("sealed_byte_count") != 815
    ):
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 byte identity drifted")
    if (
        document.get("source_task_id") != "MRL-0803"
        or document.get("source_evidence_sha256")
        != "629d8d39a6ea44e753b6d83e07116b12213a74c14f395bea700224fc6781c8e2"
    ):
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 predecessor binding drifted")
    if (
        document.get("item_content_embedded") is not False
        or document.get("patient_identifiers_embedded") is not False
    ):
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 identity must not disclose items")
    if (
        document.get("adaptive_search_access_allowed") is not False
        or document.get("training_access_allowed") is not False
        or document.get("aggregate_outputs_only") is not True
    ):
        raise MRL0807EvaluatorFreezeError("sealed Tier-3 access policy drifted")
    return document


def _parse_json_object(raw: bytes, *, label: str, require_canonical: bool) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0807EvaluatorFreezeError(f"{label} must be non-empty exact bytes")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, MRL0807EvaluatorFreezeError):
            raise
        raise MRL0807EvaluatorFreezeError(f"{label} is not strict JSON") from exc
    if type(value) is not dict:
        raise MRL0807EvaluatorFreezeError(f"{label} must be one JSON object")
    document = cast(dict[str, object], value)
    if require_canonical:
        try:
            canonical = canonical_json_bytes(document)
        except (CanonicalContractError, TypeError, ValueError, RecursionError) as exc:
            raise MRL0807EvaluatorFreezeError(f"{label} cannot be canonicalized") from exc
        if canonical != raw:
            raise MRL0807EvaluatorFreezeError(f"{label} bytes are not canonical JSON")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0807EvaluatorFreezeError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0807EvaluatorFreezeError(f"{label} must be lowercase 64-hex SHA-256")
    return value


def _require_git_sha(value: object, label: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0807EvaluatorFreezeError(f"{label} must be lowercase 40-hex Git identity")
    return value
