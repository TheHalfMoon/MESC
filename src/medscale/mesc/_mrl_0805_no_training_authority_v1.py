"""Deterministic MRL-0805 no-training evaluation authority qualification.

This module validates the exact Founder/operator authorization artifact, derives a
non-circular authorization subject, emits a deterministic execution-authority receipt,
and assembles an untrusted MRL-0805 real-preflight evidence candidate. It grants no
training authority and does not mutate any production trust registry.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_AUTHORIZATION_SHA256: Final = "482e1b03547c8c89e0b1db80c1446f31610035d0d00bff8a2456b7cb24568dd8"
_AUTH_SCHEMA: Final = "MESC-MRL-0805-NO-TRAINING-EVALUATION-AUTHORIZATION-V1"
_SUBJECT_SCHEMA: Final = "MESC-MRL-0805-NO-TRAINING-EVALUATION-SUBJECT-V1"
_RECEIPT_SCHEMA: Final = "MESC-MRL-0805-NO-TRAINING-EVALUATION-RECEIPT-V1"
_EXPECTED_TASK: Final = "MRL-0805"
_EXPECTED_KIND: Final = "mesc.mrl.real_preflight.no_training_evaluation_authority.v1"
_EXPECTED_SCOPE: Final = "NO_TRAINING_EVALUATION"
_EXPECTED_EXPERIMENT: Final = "mesc-experiment-0-foundation-tournament"
_EXPECTED_ISSUE = 415
_EXPECTED_ISSUE_NODE: Final = "I_kwDOTT9yMs8AAAABRG46tw"
_EXPECTED_ISSUE_BODY_SHA256: Final = (
    "83252dc19f6b6950aa0f3ce69eee5f461a164c0ea2affdcacfc1eaf80d4d5caf"
)
_EXPECTED_BASE_SHA: Final = "6edc6e83c214e1eb19b0bc513047cb31e24dbf9e"
_EXPECTED_BASE_TREE: Final = "392751a12f563523f906928e09aa8ef76444438e"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)

_EXPECTED_PROGRAM_BINDINGS: Final = {
    "candidate_roster_sha256": "2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489",
    "decision_contract_sha256": "71e00a6215e337b6a2980ac144d70839775300d886420d244040a0a9b37fd937",
    "evidence_contract_sha256": "779ec3ddc2d4d76f1d62fcfee876c5976a4c0a5f605330c8402a01987bf8697c",
    "strategy_decision_id": "ADR-0036",
    "tournament_contract_sha256": (
        "452af72a54de048b0bd96321b07be10e70535f0689f14de3340d85bb0b9365da"
    ),
}
_EXPECTED_PREDECESSOR_EVIDENCE: Final = {
    "MRL-0801": "c03792530e497857c700b64b1ee9950ede595006d35b577b7b8c573624c6c8b9",
    "MRL-0802": "1d6d14590a19c20bcd794e4c0ddbd2fa5e1c767b70e9d199fc169aeaaa86b762",
    "MRL-0803": "629d8d39a6ea44e753b6d83e07116b12213a74c14f395bea700224fc6781c8e2",
    "MRL-0804": "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0",
}
_POLICY_KEYS: Final = frozenset(
    {
        "authorization_scope",
        "clinical_authority_present",
        "distillation_authorized",
        "evaluation_execution_authorized",
        "lora_authorized",
        "preference_optimization_authorized",
        "promotion_authority_present",
        "qlora_authorized",
        "real_training_authorized",
        "release_authority_present",
        "rl_authorized",
        "scientific_execution_requires_remaining_mrl_gates",
        "sft_authorized",
        "teacher_data_generation_authorized",
        "training_prohibited",
        "unsloth_training_authorized",
        "weight_mutation_authorized",
    }
)


class MRL0805AuthorityError(ValueError):
    """Raised when MRL-0805 authority material fails closed."""


@dataclass(frozen=True, slots=True)
class MRL0805NoTrainingAuthorization:
    """Exact committed Founder/operator no-training authorization artifact."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)
    main_sha: str = field(init=False)
    main_tree: str = field(init=False)
    experiment_id: str = field(init=False)
    issue_number: int = field(init=False)
    policy: dict[str, object] = field(init=False, repr=False)
    predecessor_evidence: dict[str, object] = field(init=False, repr=False)
    program_bindings: dict[str, object] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="authorization")
        digest = hashlib.sha256(self.canonical_bytes).hexdigest()
        if digest != _AUTHORIZATION_SHA256:
            raise MRL0805AuthorityError(
                "authorization bytes do not match the committed MRL-0805 identity"
            )
        _validate_authorization(document)
        base = _require_object(document["authorized_base"], label="authorized_base")
        source = _require_object(document["authority_source"], label="authority_source")
        object.__setattr__(self, "authorization_sha256", digest)
        object.__setattr__(self, "main_sha", cast(str, base["main_sha"]))
        object.__setattr__(self, "main_tree", cast(str, base["main_tree"]))
        object.__setattr__(self, "experiment_id", cast(str, document["experiment_id"]))
        object.__setattr__(self, "issue_number", cast(int, source["issue_number"]))
        object.__setattr__(self, "policy", cast(dict[str, object], document["policy"]))
        object.__setattr__(
            self,
            "predecessor_evidence",
            cast(dict[str, object], document["predecessor_evidence"]),
        )
        object.__setattr__(
            self,
            "program_bindings",
            cast(dict[str, object], document["program_bindings"]),
        )


@dataclass(frozen=True, slots=True)
class MRL0805AuthorityQualification:
    """Deterministic untrusted MRL-0805 authority evidence bundle."""

    authorization_subject_bytes: bytes = field(repr=False)
    execution_authority_receipt_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    authorization_artifact_sha256: str
    authorization_subject_sha256: str
    execution_authority_receipt_sha256: str
    evidence_sha256: str


def parse_mrl_0805_no_training_authorization(raw: bytes) -> MRL0805NoTrainingAuthorization:
    """Parse and validate the exact committed MRL-0805 authorization artifact."""
    return MRL0805NoTrainingAuthorization(raw)


def qualify_mrl_0805_no_training_authority(
    authorization_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
) -> MRL0805AuthorityQualification:
    """Build deterministic no-training authority evidence without admitting trust."""
    authorization = parse_mrl_0805_no_training_authorization(authorization_raw)
    repository_sha = _require_git_sha(repository_sha, "repository_sha")
    repository_tree = _require_git_sha(repository_tree, "repository_tree")

    subject_bytes = canonical_json_bytes(
        {
            "authorized_base": {
                "main_sha": authorization.main_sha,
                "main_tree": authorization.main_tree,
            },
            "experiment_id": authorization.experiment_id,
            "kind": "mesc.mrl.no_training_evaluation_authorization_subject.v1",
            "policy": authorization.policy,
            "predecessor_evidence": authorization.predecessor_evidence,
            "program_bindings": authorization.program_bindings,
            "schema_version": _SUBJECT_SCHEMA,
            "task_id": _EXPECTED_TASK,
        }
    )
    subject_sha256 = hashlib.sha256(subject_bytes).hexdigest()

    receipt_bytes = canonical_json_bytes(
        {
            "authorization_artifact_sha256": authorization.authorization_sha256,
            "authorization_disposition": "AUTHORIZED",
            "authorization_scope": _EXPECTED_SCOPE,
            "authorization_subject_sha256": subject_sha256,
            "evaluation_execution_authorized": True,
            "experiment_id": authorization.experiment_id,
            "issue_number": authorization.issue_number,
            "real_training_authorized": False,
            "repository_sha": repository_sha,
            "repository_tree": repository_tree,
            "schema_version": _RECEIPT_SCHEMA,
            "training_prohibited": True,
        }
    )
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()

    evidence_bytes = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _EXPECTED_KIND,
            "payload": {
                "authorization_artifact_sha256": authorization.authorization_sha256,
                "authorization_disposition": "AUTHORIZED",
                "authorization_scope": _EXPECTED_SCOPE,
                "authorization_subject_sha256": subject_sha256,
                "evaluation_execution_authorized": True,
                "execution_authority_receipt_sha256": receipt_sha256,
                "real_training_authorized": False,
                "training_prohibited": True,
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": receipt_sha256,
            "task_id": _EXPECTED_TASK,
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != _EXPECTED_TASK or parsed.subject_sha256 != receipt_sha256:
        raise MRL0805AuthorityError("produced MRL-0805 evidence failed semantic self-check")
    return MRL0805AuthorityQualification(
        authorization_subject_bytes=subject_bytes,
        execution_authority_receipt_bytes=receipt_bytes,
        evidence_bytes=evidence_bytes,
        authorization_artifact_sha256=authorization.authorization_sha256,
        authorization_subject_sha256=subject_sha256,
        execution_authority_receipt_sha256=receipt_sha256,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )


def verify_mrl_0805_no_training_authority_bundle(
    authorization_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
    authorization_subject_bytes: bytes,
    execution_authority_receipt_bytes: bytes,
    evidence_bytes: bytes,
) -> MRL0805AuthorityQualification:
    """Recompute the deterministic bundle and require byte-identical supplied artifacts."""
    expected = qualify_mrl_0805_no_training_authority(
        authorization_raw,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
    )
    supplied = (
        (
            "authorization subject",
            authorization_subject_bytes,
            expected.authorization_subject_bytes,
        ),
        (
            "execution authority receipt",
            execution_authority_receipt_bytes,
            expected.execution_authority_receipt_bytes,
        ),
        ("real-preflight evidence", evidence_bytes, expected.evidence_bytes),
    )
    for label, actual, wanted in supplied:
        if type(actual) is not bytes or actual != wanted:
            raise MRL0805AuthorityError(f"supplied {label} does not match deterministic output")
    return expected


def _validate_authorization(document: dict[str, object]) -> None:
    _require_exact_keys(
        document,
        {
            "authority_source",
            "authorization_id",
            "authorization_state",
            "authorized_base",
            "experiment_id",
            "policy",
            "predecessor_evidence",
            "program_bindings",
            "schema_version",
            "scope",
            "task_id",
        },
        label="authorization",
    )
    if document["schema_version"] != _AUTH_SCHEMA:
        raise MRL0805AuthorityError("authorization schema_version is invalid")
    if document["authorization_state"] != "AUTHORIZED":
        raise MRL0805AuthorityError("authorization_state must be exactly AUTHORIZED")
    if document["task_id"] != _EXPECTED_TASK:
        raise MRL0805AuthorityError("authorization task_id is invalid")
    if document["scope"] != "MRL-0805_NO_TRAINING_EVALUATION_AUTHORITY_ONLY":
        raise MRL0805AuthorityError("authorization scope is invalid")
    if document["experiment_id"] != _EXPECTED_EXPERIMENT:
        raise MRL0805AuthorityError("authorization experiment_id is invalid")

    source = _require_object(document["authority_source"], label="authority_source")
    _require_exact_keys(
        source,
        {
            "author_association",
            "author_login",
            "body_sha256",
            "created_at",
            "issue_node_id",
            "issue_number",
        },
        label="authority_source",
    )
    if source["issue_number"] != _EXPECTED_ISSUE:
        raise MRL0805AuthorityError("authority source issue_number is invalid")
    if source["issue_node_id"] != _EXPECTED_ISSUE_NODE:
        raise MRL0805AuthorityError("authority source issue_node_id is invalid")
    if source["author_login"] != "TheHalfMoon" or source["author_association"] != "OWNER":
        raise MRL0805AuthorityError("authority source must be the repository owner")
    if source["body_sha256"] != _EXPECTED_ISSUE_BODY_SHA256:
        raise MRL0805AuthorityError("authority source body digest is invalid")
    if source["created_at"] != "2026-09-13T21:54:13Z":
        raise MRL0805AuthorityError("authority source created_at is invalid")

    base = _require_object(document["authorized_base"], label="authorized_base")
    _require_exact_keys(
        base,
        {
            "main_sha",
            "main_tree",
            "post_merge_ci_run",
            "post_merge_ci_success",
            "post_merge_codeql_run",
            "post_merge_codeql_success",
            "post_merge_optional_extras_run",
            "post_merge_optional_extras_success",
        },
        label="authorized_base",
    )
    if base["main_sha"] != _EXPECTED_BASE_SHA or base["main_tree"] != _EXPECTED_BASE_TREE:
        raise MRL0805AuthorityError("authorization canonical predecessor is invalid")
    for key in (
        "post_merge_ci_run",
        "post_merge_codeql_run",
        "post_merge_optional_extras_run",
    ):
        _require_positive_int(base[key], key)
    for key in (
        "post_merge_ci_success",
        "post_merge_codeql_success",
        "post_merge_optional_extras_success",
    ):
        if _require_bool(base[key], label=key) is not True:
            raise MRL0805AuthorityError(f"{key} must be true")

    program = _require_object(document["program_bindings"], label="program_bindings")
    if program != _EXPECTED_PROGRAM_BINDINGS:
        raise MRL0805AuthorityError("program bindings do not match the authorized Experiment-0")
    predecessor = _require_object(document["predecessor_evidence"], label="predecessor_evidence")
    if predecessor != _EXPECTED_PREDECESSOR_EVIDENCE:
        raise MRL0805AuthorityError("predecessor evidence does not match canonical MRL-0801..0804")

    policy = _require_object(document["policy"], label="policy")
    if set(policy) != _POLICY_KEYS:
        raise MRL0805AuthorityError("authorization policy must contain the exact canonical key set")
    if policy["authorization_scope"] != _EXPECTED_SCOPE:
        raise MRL0805AuthorityError("authorization_scope must be NO_TRAINING_EVALUATION")
    if (
        _require_bool(
            policy["evaluation_execution_authorized"], label="evaluation_execution_authorized"
        )
        is not True
    ):
        raise MRL0805AuthorityError("evaluation execution authority must be present")
    if _require_bool(policy["real_training_authorized"], label="real_training_authorized"):
        raise MRL0805AuthorityError("real training must remain unauthorized")
    if _require_bool(policy["training_prohibited"], label="training_prohibited") is not True:
        raise MRL0805AuthorityError("training must remain explicitly prohibited")
    if (
        _require_bool(
            policy["scientific_execution_requires_remaining_mrl_gates"],
            label="scientific_execution_requires_remaining_mrl_gates",
        )
        is not True
    ):
        raise MRL0805AuthorityError("remaining MRL gates must stay mandatory before execution")
    false_grants = _POLICY_KEYS - {
        "authorization_scope",
        "evaluation_execution_authorized",
        "scientific_execution_requires_remaining_mrl_gates",
        "training_prohibited",
    }
    for key in false_grants:
        if _require_bool(policy[key], label=key):
            raise MRL0805AuthorityError(f"authorization must not grant {key}")


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0805AuthorityError(f"{label} must be non-empty exact bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
        value = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, MRL0805AuthorityError):
            raise
        raise MRL0805AuthorityError(f"{label} is not valid strict JSON") from exc
    if type(value) is not dict:
        raise MRL0805AuthorityError(f"{label} must be one JSON object")
    document = cast(dict[str, object], value)
    try:
        canonical = canonical_json_bytes(document)
    except (TypeError, ValueError, RecursionError) as exc:
        raise MRL0805AuthorityError(f"{label} cannot be canonicalized") from exc
    if canonical != raw:
        raise MRL0805AuthorityError(f"{label} bytes are not canonical JSON")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0805AuthorityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise MRL0805AuthorityError(f"non-finite JSON constant is prohibited: {value}")


def _require_exact_keys(value: dict[str, object], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise MRL0805AuthorityError(f"{label} must contain the exact canonical key set")


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0805AuthorityError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _require_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise MRL0805AuthorityError(f"{label} must be an exact boolean")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0805AuthorityError(f"{label} must be a positive integer")
    return value


def _require_git_sha(value: object, label: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0805AuthorityError(f"{label} must be lowercase 40-hex Git identity")
    return value
