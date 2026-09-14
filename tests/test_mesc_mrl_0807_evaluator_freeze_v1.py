"""Regression tests for the bounded MRL-0807 RQ1/FHIR evaluator freeze producer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medscale.mesc import _mrl_0807_evaluator_freeze_v1 as freeze
from medscale.mesc import _mrl_real_preflight_evidence_v1 as preflight
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_ROOT = Path(__file__).resolve().parents[1]
_AUTH = _ROOT / "specs/mesc-experiment-0/mrl-0807-evaluator-freeze-authorization-v1.json"
_EVALUATOR = _ROOT / "specs/mesc-experiment-0/mrl-0807-evaluator-identity-v1.json"
_CONTRACT = _ROOT / "specs/mesc-experiment-0/mrl-0807-rq1-evaluation-contract-v1.json"
_SEALED = _ROOT / "specs/mesc-experiment-0/mrl-0807-sealed-tier3-identity-v1.json"
_MODULE = _ROOT / "src/medscale/mesc/_mrl_0807_evaluator_freeze_v1.py"
_QUALIFIER = _ROOT / "scripts/mesc_mrl_0807_evaluator_qualify.py"
_BASE_SHA = "99356b6db1501c87a22e4466cdd7d49d96e2d5d9"
_BASE_TREE = "6abeaf3a9467d562c68aa0f84a0a7a2b5b0d5129"
_HL7_SHA = "1106b9d58f9e363e47bea7c4fc065841e5fc91fe9d062775c3bfdd212bd653cc"
_HL7_SIZE = 200_928_617


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _qualify() -> freeze.MRL0807EvaluatorQualification:
    return freeze.qualify_mrl_0807_evaluators(
        _AUTH.read_bytes(),
        _EVALUATOR.read_bytes(),
        _CONTRACT.read_bytes(),
        _SEALED.read_bytes(),
        repository_sha=_BASE_SHA,
        repository_tree=_BASE_TREE,
        external_validator_sha256=_HL7_SHA,
        external_validator_size=_HL7_SIZE,
    )


def _mutated(path: Path, mutate: Any) -> bytes:
    document = _json(path)
    mutate(document)
    return canonical_json_bytes(document)


def _load_qualifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mrl0807_qualifier_test", _QUALIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_authorization_is_exact_owner_bounded_and_non_training() -> None:
    document = _json(_AUTH)
    assert hashlib.sha256(_AUTH.read_bytes()).hexdigest() == freeze._AUTHORIZATION_SHA256
    assert document["authority_source"]["issue_number"] == 418
    assert document["authority_source"]["author_association"] == "OWNER"
    assert document["authorized_base"]["main_sha"] == _BASE_SHA
    assert document["authorized_base"]["main_tree"] == _BASE_TREE
    assert document["candidate_id"] == "mrl-rq1-fhir-grammar-decoupling-v1"
    assert document["policy"]["scientific_model_execution_authorized"] is False
    assert document["policy"]["training_authorized"] is False
    assert document["policy"]["weight_mutation_authorized"] is False
    assert document["policy"]["sealed_tier3_item_disclosure_authorized"] is False


def test_frozen_artifact_hash_chain_binds_exact_implementation() -> None:
    evaluator = _json(_EVALUATOR)
    contract = _json(_CONTRACT)
    sealed = _json(_SEALED)
    implementation_sha = hashlib.sha256(_MODULE.read_bytes()).hexdigest()
    assert evaluator["evaluators"][0]["adapter_source_sha256"] == implementation_sha
    assert evaluator["evaluators"][1]["implementation_sha256"] == implementation_sha
    assert (
        contract["evaluator_identity_sha256"] == hashlib.sha256(_EVALUATOR.read_bytes()).hexdigest()
    )
    assert (
        contract["sealed_tier3_identity_sha256"] == hashlib.sha256(_SEALED.read_bytes()).hexdigest()
    )
    assert (
        sealed["sealed_bytes_sha256"]
        == "a74ca84315459622b38a437fd31b9b82058701c5a28798ced3c8deac5a5f9247"
    )
    assert sealed["item_content_embedded"] is False
    assert sealed["patient_identifiers_embedded"] is False


def test_patient_projection_set_f1_is_exact_and_ignores_out_of_projection_fields() -> None:
    reference = {
        "resourceType": "Patient",
        "id": "p1",
        "gender": "female",
        "birthDate": "1980-01-01",
        "address": [{"city": "Boston", "state": "Massachusetts"}],
    }
    exact = dict(reference)
    exact["meta"] = {"profile": ["ignored"]}
    perfect = freeze.score_patient_projection(reference, exact)
    assert perfect.is_perfect
    assert perfect.numerator == perfect.denominator

    partial = freeze.score_patient_projection(reference, {"resourceType": "Patient", "id": "p1"})
    assert partial.true_positive_count == 2
    assert partial.reference_count == 6
    assert partial.predicted_count == 2
    assert partial.numerator == 4
    assert partial.denominator == 8
    assert not partial.is_perfect

    degenerate = freeze.score_patient_projection(reference, {"resourceType": "Patient"})
    assert not degenerate.is_perfect
    assert degenerate.predicted_count == 1


def test_patient_projection_rejects_malformed_or_non_patient_input() -> None:
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="Patient object"):
        freeze.patient_projection_triples({"resourceType": "Observation"})
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="address must be"):
        freeze.patient_projection_triples({"resourceType": "Patient", "address": {}})
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="deceasedBoolean"):
        freeze.patient_projection_triples({"resourceType": "Patient", "deceasedBoolean": 1})


def test_hl7_operationoutcome_normalization_is_fail_closed() -> None:
    valid = json.dumps(
        {"resourceType": "OperationOutcome", "issue": [{"severity": "warning"}]}
    ).encode()
    summary = freeze.normalize_hl7_validation_output(valid)
    assert summary.valid is True
    assert summary.warning_count == 1
    invalid = json.dumps(
        {"resourceType": "OperationOutcome", "issue": [{"severity": "error"}]}
    ).encode()
    assert freeze.normalize_hl7_validation_output(invalid).valid is False
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="severity"):
        freeze.normalize_hl7_validation_output(
            json.dumps(
                {"resourceType": "OperationOutcome", "issue": [{"severity": "success"}]}
            ).encode()
        )


def test_qualification_is_deterministic_and_untrusted() -> None:
    first = _qualify()
    second = _qualify()
    assert first == second
    parsed = preflight.parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0807"
    assert parsed.kind == "mesc.mrl.real_preflight.evaluators.v1"
    assert parsed.subject_sha256 == first.freeze_receipt_sha256
    with pytest.raises(preflight.MRLRealPreflightEvidenceError, match="not trusted"):
        preflight.admit_mrl_real_preflight_evidence(
            first.evidence_bytes, expected_task_id="MRL-0807"
        )


def test_bundle_verifier_requires_byte_identical_outputs() -> None:
    result = _qualify()
    assert (
        freeze.verify_mrl_0807_bundle(
            _AUTH.read_bytes(),
            _EVALUATOR.read_bytes(),
            _CONTRACT.read_bytes(),
            _SEALED.read_bytes(),
            repository_sha=_BASE_SHA,
            repository_tree=_BASE_TREE,
            external_validator_sha256=_HL7_SHA,
            external_validator_size=_HL7_SIZE,
            freeze_receipt_bytes=result.freeze_receipt_bytes,
            evidence_bytes=result.evidence_bytes,
        )
        == result
    )
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="receipt"):
        freeze.verify_mrl_0807_bundle(
            _AUTH.read_bytes(),
            _EVALUATOR.read_bytes(),
            _CONTRACT.read_bytes(),
            _SEALED.read_bytes(),
            repository_sha=_BASE_SHA,
            repository_tree=_BASE_TREE,
            external_validator_sha256=_HL7_SHA,
            external_validator_size=_HL7_SIZE,
            freeze_receipt_bytes=result.freeze_receipt_bytes + b" ",
            evidence_bytes=result.evidence_bytes,
        )


@pytest.mark.parametrize(
    ("path", "mutation", "message"),
    [
        (
            _AUTH,
            lambda d: d["authorized_base"].__setitem__("main_sha", "0" * 40),
            "authorization bytes",
        ),
        (
            _EVALUATOR,
            lambda d: d["evaluators"][0]["artifact"].__setitem__("sha256", "0" * 64),
            "HL7 evaluator artifact",
        ),
        (
            _EVALUATOR,
            lambda d: d["evaluators"][1].__setitem__("projection_fields", ["resourceType"]),
            "projection fields",
        ),
        (_CONTRACT, lambda d: d.__setitem__("corpus_sha256", "0" * 64), "corpus identity"),
        (
            _CONTRACT,
            lambda d: d.__setitem__("heldout_evaluation_sha256", "0" * 64),
            "held-out identity",
        ),
        (
            _CONTRACT,
            lambda d: d.__setitem__("promotion_authority_present", True),
            "non-promotional",
        ),
        (_SEALED, lambda d: d.__setitem__("item_content_embedded", True), "must not disclose"),
    ],
)
def test_material_drift_fails_closed(path: Path, mutation: Any, message: str) -> None:
    kwargs = {
        "authorization_raw": _AUTH.read_bytes(),
        "evaluator_identity_raw": _EVALUATOR.read_bytes(),
        "evaluation_contract_raw": _CONTRACT.read_bytes(),
        "sealed_tier3_identity_raw": _SEALED.read_bytes(),
    }
    key = {
        _AUTH: "authorization_raw",
        _EVALUATOR: "evaluator_identity_raw",
        _CONTRACT: "evaluation_contract_raw",
        _SEALED: "sealed_tier3_identity_raw",
    }[path]
    kwargs[key] = _mutated(path, mutation)
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match=message):
        freeze.qualify_mrl_0807_evaluators(
            **kwargs,
            repository_sha=_BASE_SHA,
            repository_tree=_BASE_TREE,
            external_validator_sha256=_HL7_SHA,
            external_validator_size=_HL7_SIZE,
        )


def test_external_validator_custody_identity_is_exact() -> None:
    with pytest.raises(freeze.MRL0807EvaluatorFreezeError, match="custody"):
        freeze.qualify_mrl_0807_evaluators(
            _AUTH.read_bytes(),
            _EVALUATOR.read_bytes(),
            _CONTRACT.read_bytes(),
            _SEALED.read_bytes(),
            repository_sha=_BASE_SHA,
            repository_tree=_BASE_TREE,
            external_validator_sha256="0" * 64,
            external_validator_size=_HL7_SIZE,
        )


def test_producer_does_not_admit_trust_or_close_task() -> None:
    result = _qualify()
    assert result.evidence_sha256 not in preflight.TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
    slot = (_ROOT / "specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0807.json").read_text()
    assert '"state":"ABSENT"' in slot
    tasks = (_ROOT / "specs/mesc-research-loop-v1/tasks.md").read_text()
    assert "- [ ] **MRL-0807 — Freeze evaluator and sealed Tier 3 identities**" in tasks


def test_control_plane_qualifier_binds_actual_module_source() -> None:
    qualifier = _load_qualifier()
    qualifier._require_committed_bindings(_ROOT)
