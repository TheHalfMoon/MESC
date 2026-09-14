"Regression tests for the MRL-0805 no-training evaluation authority producer."

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medscale.mesc import _mrl_0805_no_training_authority_v1 as authority
from medscale.mesc import _mrl_real_preflight_evidence_v1 as preflight
from medscale.mesc import _training_authorization_trust_v1 as training_trust
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_ROOT = Path(__file__).resolve().parents[1]
_AUTH = _ROOT / "specs/mesc-experiment-0/mrl-0805-no-training-evaluation-authorization-v1.json"
_QUALIFIER = _ROOT / "scripts/mesc_mrl_0805_authority_qualify.py"
_BASE_SHA = "6edc6e83c214e1eb19b0bc513047cb31e24dbf9e"
_BASE_TREE = "392751a12f563523f906928e09aa8ef76444438e"


def _load_qualifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0805_qualifier_test", _QUALIFIER)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load MRL-0805 authority qualifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _authorization() -> authority.MRL0805NoTrainingAuthorization:
    return authority.parse_mrl_0805_no_training_authorization(_AUTH.read_bytes())


def _qualify() -> authority.MRL0805AuthorityQualification:
    return authority.qualify_mrl_0805_no_training_authority(
        _AUTH.read_bytes(),
        repository_sha=_BASE_SHA,
        repository_tree=_BASE_TREE,
    )


def _mutated_authorization(
    monkeypatch: pytest.MonkeyPatch,
    mutate: Any,
) -> bytes:
    document = json.loads(_AUTH.read_text(encoding="utf-8"))
    mutate(document)
    raw = canonical_json_bytes(document)
    monkeypatch.setattr(authority, "_AUTHORIZATION_SHA256", hashlib.sha256(raw).hexdigest())
    return raw


def test_committed_authorization_is_exact_owner_bounded_and_no_training() -> None:
    parsed = _authorization()
    assert parsed.authorization_sha256 == hashlib.sha256(_AUTH.read_bytes()).hexdigest()
    assert parsed.main_sha == _BASE_SHA
    assert parsed.main_tree == _BASE_TREE
    assert parsed.experiment_id == "mesc-experiment-0-foundation-tournament"
    assert parsed.issue_number == 415
    assert parsed.policy["authorization_scope"] == "NO_TRAINING_EVALUATION"
    assert parsed.policy["evaluation_execution_authorized"] is True
    assert parsed.policy["real_training_authorized"] is False
    assert parsed.policy["training_prohibited"] is True
    assert parsed.policy["weight_mutation_authorized"] is False
    assert parsed.policy["promotion_authority_present"] is False


def test_program_bindings_match_exact_repository_bytes() -> None:
    parsed = _authorization()
    paths = {
        "candidate_roster_sha256": "specs/mesc-experiment-0/candidate-roster-v1.json",
        "decision_contract_sha256": "specs/mesc-experiment-0/decision-contract.md",
        "evidence_contract_sha256": "specs/mesc-experiment-0/evidence-contract.md",
        "tournament_contract_sha256": "specs/mesc-experiment-0/tournament-contract.md",
    }
    for key, relative in paths.items():
        assert (
            parsed.program_bindings[key]
            == hashlib.sha256((_ROOT / relative).read_bytes()).hexdigest()
        )
    assert parsed.program_bindings["strategy_decision_id"] == "ADR-0036"


def test_predecessor_evidence_bindings_match_exact_slots() -> None:
    parsed = _authorization()
    for task_id, digest in parsed.predecessor_evidence.items():
        path = _ROOT / f"specs/mesc-research-loop-v1/real-preflight-evidence/{task_id}.json"
        assert digest == hashlib.sha256(path.read_bytes()).hexdigest()


def test_qualification_is_deterministic_path_free_and_untrusted() -> None:
    first = _qualify()
    second = _qualify()
    assert first == second
    assert b"\\" not in first.evidence_bytes
    assert b"C:/" not in first.evidence_bytes
    parsed = preflight.parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0805"
    assert parsed.kind == "mesc.mrl.real_preflight.no_training_evaluation_authority.v1"
    assert parsed.subject_sha256 == first.execution_authority_receipt_sha256
    with pytest.raises(preflight.MRLRealPreflightEvidenceError, match="not trusted"):
        preflight.admit_mrl_real_preflight_evidence(
            first.evidence_bytes,
            expected_task_id="MRL-0805",
        )


def test_subject_receipt_and_evidence_bind_exact_hash_chain() -> None:
    result = _qualify()
    subject = json.loads(result.authorization_subject_bytes)
    receipt = json.loads(result.execution_authority_receipt_bytes)
    evidence = json.loads(result.evidence_bytes)
    assert (
        hashlib.sha256(result.authorization_subject_bytes).hexdigest()
        == result.authorization_subject_sha256
    )
    assert (
        hashlib.sha256(result.execution_authority_receipt_bytes).hexdigest()
        == result.execution_authority_receipt_sha256
    )
    assert hashlib.sha256(result.evidence_bytes).hexdigest() == result.evidence_sha256
    assert subject["policy"]["real_training_authorized"] is False
    assert receipt["authorization_subject_sha256"] == result.authorization_subject_sha256
    assert receipt["authorization_artifact_sha256"] == result.authorization_artifact_sha256
    assert receipt["real_training_authorized"] is False
    assert receipt["training_prohibited"] is True
    assert evidence["subject_sha256"] == result.execution_authority_receipt_sha256
    assert (
        evidence["payload"]["execution_authority_receipt_sha256"]
        == result.execution_authority_receipt_sha256
    )


def test_bundle_verifier_recomputes_exact_bytes_and_rejects_tampering() -> None:
    result = _qualify()
    verified = authority.verify_mrl_0805_no_training_authority_bundle(
        _AUTH.read_bytes(),
        repository_sha=_BASE_SHA,
        repository_tree=_BASE_TREE,
        authorization_subject_bytes=result.authorization_subject_bytes,
        execution_authority_receipt_bytes=result.execution_authority_receipt_bytes,
        evidence_bytes=result.evidence_bytes,
    )
    assert verified == result
    with pytest.raises(authority.MRL0805AuthorityError, match="execution authority receipt"):
        authority.verify_mrl_0805_no_training_authority_bundle(
            _AUTH.read_bytes(),
            repository_sha=_BASE_SHA,
            repository_tree=_BASE_TREE,
            authorization_subject_bytes=result.authorization_subject_bytes,
            execution_authority_receipt_bytes=result.execution_authority_receipt_bytes + b" ",
            evidence_bytes=result.evidence_bytes,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda d: d["authorized_base"].__setitem__("main_sha", "0" * 40), "canonical predecessor"),
        (
            lambda d: d["program_bindings"].__setitem__("strategy_decision_id", "ADR-9999"),
            "program bindings",
        ),
        (
            lambda d: d["predecessor_evidence"].__setitem__("MRL-0804", "0" * 64),
            "predecessor evidence",
        ),
        (
            lambda d: d["policy"].__setitem__("authorization_scope", "TRAINING"),
            "authorization_scope",
        ),
        (lambda d: d["policy"].__setitem__("real_training_authorized", True), "real training"),
        (lambda d: d["policy"].__setitem__("training_prohibited", False), "training must remain"),
        (
            lambda d: d["policy"].__setitem__("weight_mutation_authorized", True),
            "weight_mutation_authorized",
        ),
        (
            lambda d: d["policy"].__setitem__("promotion_authority_present", True),
            "promotion_authority_present",
        ),
        (
            lambda d: d["policy"].__setitem__(
                "scientific_execution_requires_remaining_mrl_gates",
                False,
            ),
            "remaining MRL gates",
        ),
    ],
)
def test_authorization_semantic_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: Any,
    message: str,
) -> None:
    raw = _mutated_authorization(monkeypatch, mutation)
    with pytest.raises(authority.MRL0805AuthorityError, match=message):
        authority.parse_mrl_0805_no_training_authorization(raw)


def test_authority_source_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def mutate(document: dict[str, object]) -> None:
        source = document["authority_source"]
        assert isinstance(source, dict)
        source["author_association"] = "CONTRIBUTOR"

    raw = _mutated_authorization(monkeypatch, mutate)
    with pytest.raises(authority.MRL0805AuthorityError, match="repository owner"):
        authority.parse_mrl_0805_no_training_authorization(raw)


def test_no_training_output_never_invokes_training_authorization_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _qualify()
    monkeypatch.setattr(
        preflight,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({result.evidence_sha256}),
    )

    def unexpected_training_trust(
        *,
        expected_registry_sha256: str,
        artifact_sha256: str,
    ) -> None:
        del expected_registry_sha256, artifact_sha256
        raise AssertionError("training authorization trust is not applicable")

    monkeypatch.setattr(
        training_trust,
        "validate_training_authorization_trust",
        unexpected_training_trust,
    )
    admitted = preflight.admit_mrl_real_preflight_evidence(
        result.evidence_bytes,
        expected_task_id="MRL-0805",
    )
    assert admitted.subject_sha256 == result.execution_authority_receipt_sha256


def test_producer_sources_do_not_import_training_authorization_trust() -> None:
    for path in (
        _ROOT / "src/medscale/mesc/_mrl_0805_no_training_authority_v1.py",
        _QUALIFIER,
    ):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)
        assert all("_training_authorization_trust_v1" not in name for name in imports)


def test_live_issue_validator_requires_exact_owner_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualifier = _load_qualifier()
    body = "bounded no-training owner authority"
    monkeypatch.setattr(
        qualifier,
        "_EXPECTED_ISSUE_BODY_SHA256",
        hashlib.sha256(body.encode()).hexdigest(),
    )
    payload = {
        "number": 415,
        "node_id": "I_kwDOTT9yMs8AAAABRG46tw",
        "author_association": "OWNER",
        "created_at": "2026-09-13T21:54:13Z",
        "body": body,
        "user": {"login": "TheHalfMoon"},
    }

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        assert arguments[:2] == ["gh", "api"]
        return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(qualifier, "_run", fake_run)
    qualifier._require_live_issue()
    payload["author_association"] = "CONTRIBUTOR"
    with pytest.raises(qualifier.EntrypointError, match="repository owner"):
        qualifier._require_live_issue()


def test_live_issue_validator_rejects_body_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    qualifier = _load_qualifier()
    payload = {
        "number": 415,
        "node_id": "I_kwDOTT9yMs8AAAABRG46tw",
        "author_association": "OWNER",
        "created_at": "2026-09-13T21:54:13Z",
        "body": "drifted",
        "user": {"login": "TheHalfMoon"},
    }

    def fake_run(arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(qualifier, "_run", fake_run)
    with pytest.raises(qualifier.EntrypointError, match="body digest"):
        qualifier._require_live_issue()
