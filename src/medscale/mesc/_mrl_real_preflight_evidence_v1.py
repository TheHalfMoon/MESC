"""Fail-closed semantic envelopes for MRL-8 real preflight evidence.

This module validates already-supplied canonical evidence bytes and requires an explicit
repository-controlled trust admission before an envelope can be admitted. It performs no
network, model, corpus, provider, GPU, sandbox, inference, or training work.

Parsing proves only byte/schema semantics. Admission additionally proves membership in the
current repository-controlled trust registry. Neither operation closes an MRL task by
itself; canonical task closure remains governed by the MRL ledger, exact-head
qualification, independent evidence review, and canonical merge evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Literal, cast

from medscale.mesc import _training_authorization_trust_v1 as authorization_trust
from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveQueryBudget,
    EvaluationTier,
    EvaluationTierPolicy,
    ResearchObjectiveContractError,
    ResourceBudget,
    TierResultExposure,
)

MRLRealPreflightTask = Literal[
    "MRL-0801",
    "MRL-0802",
    "MRL-0803",
    "MRL-0804",
    "MRL-0805",
    "MRL-0806",
    "MRL-0807",
    "MRL-0808",
]

_SCHEMA_VERSION: Final = "MRL-REAL-PREFLIGHT-EVIDENCE-V1"
_TRUST_REGISTRY_VERSION: Final = "MRL-REAL-PREFLIGHT-EVIDENCE-TRUST-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_COMMON_KEYS: Final = frozenset(
    {"disposition", "kind", "payload", "schema_version", "subject_sha256", "task_id"}
)
_TASK_KIND: Final[dict[str, str]] = {
    "MRL-0801": "mesc.mrl.real_preflight.model_weights.v1",
    "MRL-0802": "mesc.mrl.real_preflight.corpus_rights.v1",
    "MRL-0803": "mesc.mrl.real_preflight.isolation.v1",
    "MRL-0804": "mesc.mrl.real_preflight.runtime.v1",
    "MRL-0805": "mesc.mrl.real_preflight.training_authorization.v1",
    "MRL-0806": "mesc.mrl.real_preflight.objective_budgets.v1",
    "MRL-0807": "mesc.mrl.real_preflight.evaluators.v1",
    "MRL-0808": "mesc.mrl.real_preflight.sandbox.v1",
}

# Production trust root. Keep empty until a separately reviewed canonical governance
# mutation admits the digest of an exact, independently verified real-evidence envelope.
# Valid canonical JSON is never sufficient to manufacture real-world evidence.
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256: frozenset[str] = frozenset()


class MRLRealPreflightEvidenceError(ValueError):
    """Raised when real-preflight evidence cannot be validated fail-closed."""


@dataclass(frozen=True, slots=True)
class MRLRealPreflightTrustSnapshot:
    """One immutable view of the repository-controlled real-evidence trust registry."""

    registry_version: str
    trusted_evidence_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this snapshot admits one exact evidence digest."""
        return (
            type(value) is str
            and _SHA256.fullmatch(value) is not None
            and value in self.trusted_evidence_sha256
        )


@dataclass(frozen=True, slots=True)
class MRLRealPreflightEvidence:
    """Validated canonical bytes for one MRL-0801..MRL-0808 evidence role."""

    canonical_bytes: bytes = field(repr=False)
    task_id: MRLRealPreflightTask = field(init=False)
    kind: str = field(init=False)
    subject_sha256: str = field(init=False)
    evidence_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes)
        if frozenset(document) != _COMMON_KEYS:
            raise MRLRealPreflightEvidenceError(
                "real-preflight evidence must contain the exact canonical top-level key set"
            )
        if document["schema_version"] != _SCHEMA_VERSION:
            raise MRLRealPreflightEvidenceError("real-preflight evidence schema_version is invalid")
        task_id = _require_task_id(document["task_id"])
        kind = _require_text(document["kind"], field="kind")
        if kind != _TASK_KIND[task_id]:
            raise MRLRealPreflightEvidenceError(
                "real-preflight evidence kind does not match task_id"
            )
        if document["disposition"] != "PASS":
            raise MRLRealPreflightEvidenceError(
                "real-preflight evidence disposition must be exactly PASS"
            )
        subject_sha256 = _require_sha256(
            document["subject_sha256"],
            field="subject_sha256",
        )
        payload = document["payload"]
        if type(payload) is not dict:
            raise MRLRealPreflightEvidenceError("real-preflight evidence payload must be an object")
        _validate_payload(task_id, cast(dict[str, object], payload))

        object.__setattr__(self, "task_id", cast(MRLRealPreflightTask, task_id))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "subject_sha256", subject_sha256)
        object.__setattr__(
            self,
            "evidence_sha256",
            hashlib.sha256(self.canonical_bytes).hexdigest(),
        )


def mrl_real_preflight_trust_snapshot() -> MRLRealPreflightTrustSnapshot:
    """Return one validated deterministic trust-registry snapshot."""
    registry = TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
    if type(registry) is not frozenset:
        raise MRLRealPreflightEvidenceError(
            "MRL real-preflight trust registry must be an exact frozenset"
        )
    for value in registry:
        _require_sha256(value, field="trusted evidence digest")
    payload = {
        "registry_version": _TRUST_REGISTRY_VERSION,
        "trusted_evidence_sha256": sorted(registry),
    }
    registry_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return MRLRealPreflightTrustSnapshot(
        registry_version=_TRUST_REGISTRY_VERSION,
        trusted_evidence_sha256=registry,
        registry_sha256=registry_sha256,
    )


def parse_mrl_real_preflight_evidence(raw: bytes) -> MRLRealPreflightEvidence:
    """Parse canonical evidence bytes without granting trust or task closure."""
    return MRLRealPreflightEvidence(raw)


def admit_mrl_real_preflight_evidence(
    raw: bytes,
    *,
    expected_task_id: MRLRealPreflightTask,
) -> MRLRealPreflightEvidence:
    """Admit one exact evidence envelope only under the current trust snapshot."""
    if expected_task_id not in _TASK_KIND:
        raise MRLRealPreflightEvidenceError("expected_task_id is not an MRL-8 real-evidence task")
    evidence = MRLRealPreflightEvidence(raw)
    if evidence.task_id != expected_task_id:
        raise MRLRealPreflightEvidenceError(
            "real-preflight evidence task_id does not match the expected task"
        )
    snapshot = mrl_real_preflight_trust_snapshot()
    if not snapshot.admits(evidence.evidence_sha256):
        raise MRLRealPreflightEvidenceError(
            "real-preflight evidence digest is not trusted by the canonical registry"
        )
    if evidence.task_id == "MRL-0805":
        document = _parse_canonical_object(raw)
        payload = cast(dict[str, object], document["payload"])
        try:
            authorization_trust.validate_training_authorization_trust(
                expected_registry_sha256=cast(str, payload["authorization_trust_registry_sha256"]),
                artifact_sha256=cast(str, payload["authorization_artifact_sha256"]),
            )
        except authorization_trust.TrainingAuthorizationTrustError as exc:
            raise MRLRealPreflightEvidenceError(
                "MRL-0805 training authorization trust validation failed"
            ) from exc
    return evidence


def _parse_canonical_object(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRLRealPreflightEvidenceError("real-preflight evidence must be non-empty exact bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
        if type(parsed) is not dict:
            raise MRLRealPreflightEvidenceError("real-preflight evidence must be a JSON object")
        document = cast(dict[str, object], parsed)
        canonical = canonical_json_bytes(document)
    except MRLRealPreflightEvidenceError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError, CanonicalContractError) as exc:
        raise MRLRealPreflightEvidenceError(
            "real-preflight evidence must be valid canonical UTF-8 JSON"
        ) from exc
    if canonical != raw:
        raise MRLRealPreflightEvidenceError("real-preflight evidence bytes are not canonical JSON")
    return document


def _validate_payload(task_id: str, payload: dict[str, object]) -> None:
    if task_id == "MRL-0801":
        _validate_model_weights(payload)
    elif task_id == "MRL-0802":
        _validate_corpus_rights(payload)
    elif task_id == "MRL-0803":
        _validate_isolation(payload)
    elif task_id == "MRL-0804":
        _validate_runtime(payload)
    elif task_id == "MRL-0805":
        _validate_training_authorization(payload)
    elif task_id == "MRL-0806":
        _validate_objective_budgets(payload)
    elif task_id == "MRL-0807":
        _validate_evaluators(payload)
    elif task_id == "MRL-0808":
        _validate_sandbox(payload)
    else:  # pragma: no cover - _require_task_id closes this path
        raise MRLRealPreflightEvidenceError("unsupported MRL real-preflight task")


def _validate_model_weights(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "access_authorization_sha256",
            "artifact_identity_sha256",
            "asset_custody_sha256",
            "asset_present",
            "model_id",
            "revision",
            "weights_sha256",
        },
        label="MRL-0801 payload",
    )
    _require_true(payload["asset_present"], field="asset_present")
    _require_text(payload["model_id"], field="model_id")
    _require_git_sha(payload["revision"], field="revision")
    for field_name in (
        "weights_sha256",
        "artifact_identity_sha256",
        "asset_custody_sha256",
        "access_authorization_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_corpus_rights(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "access_authorization_sha256",
            "byte_count",
            "corpus_id",
            "corpus_present",
            "corpus_sha256",
            "provenance_sha256",
            "rights_disposition",
            "rights_evidence_sha256",
        },
        label="MRL-0802 payload",
    )
    _require_true(payload["corpus_present"], field="corpus_present")
    _require_text(payload["corpus_id"], field="corpus_id")
    _require_positive_int(payload["byte_count"], field="byte_count")
    if payload["rights_disposition"] != "PASS":
        raise MRLRealPreflightEvidenceError("rights_disposition must be exactly PASS")
    for field_name in (
        "corpus_sha256",
        "rights_evidence_sha256",
        "provenance_sha256",
        "access_authorization_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_isolation(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "contamination_disposition",
            "corpus_sha256",
            "decontamination_report_sha256",
            "heldout_evaluation_sha256",
            "lineage_report_sha256",
            "sealed_evaluation_excluded_from_training",
        },
        label="MRL-0803 payload",
    )
    if payload["contamination_disposition"] != "PASS":
        raise MRLRealPreflightEvidenceError("contamination_disposition must be exactly PASS")
    _require_true(
        payload["sealed_evaluation_excluded_from_training"],
        field="sealed_evaluation_excluded_from_training",
    )
    for field_name in (
        "corpus_sha256",
        "decontamination_report_sha256",
        "heldout_evaluation_sha256",
        "lineage_report_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_runtime(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "network_accessed",
            "platform_qualified",
            "remote_code_allowed",
            "runtime_identity_sha256",
            "runtime_qualification_receipt_sha256",
            "smoke_receipt_sha256",
        },
        label="MRL-0804 payload",
    )
    _require_true(payload["platform_qualified"], field="platform_qualified")
    _require_false(payload["network_accessed"], field="network_accessed")
    _require_false(payload["remote_code_allowed"], field="remote_code_allowed")
    for field_name in (
        "runtime_identity_sha256",
        "runtime_qualification_receipt_sha256",
        "smoke_receipt_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_training_authorization(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "authorization_artifact_sha256",
            "authorization_disposition",
            "authorization_subject_sha256",
            "authorization_trust_registry_sha256",
            "real_training_authorized",
            "training_authorization_receipt_sha256",
        },
        label="MRL-0805 payload",
    )
    if payload["authorization_disposition"] != "AUTHORIZED":
        raise MRLRealPreflightEvidenceError("authorization_disposition must be exactly AUTHORIZED")
    _require_true(payload["real_training_authorized"], field="real_training_authorized")
    for field_name in (
        "authorization_artifact_sha256",
        "authorization_subject_sha256",
        "authorization_trust_registry_sha256",
        "training_authorization_receipt_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_objective_budgets(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "adaptive_query_budget",
            "budget_exhaustion_disposition",
            "evaluation_tier_policy",
            "frozen_externally",
            "research_objective_sha256",
            "resource_budget",
            "tier_result_exposure_policy",
        },
        label="MRL-0806 payload",
    )
    _require_true(payload["frozen_externally"], field="frozen_externally")
    _require_sha256(
        payload["research_objective_sha256"],
        field="research_objective_sha256",
    )

    resource_budget = _require_object(payload["resource_budget"], field="resource_budget")
    _validate_resource_budget(resource_budget)

    evaluation_tier_policy = _require_object(
        payload["evaluation_tier_policy"],
        field="evaluation_tier_policy",
    )
    allowed_tiers = _validate_evaluation_tier_policy(evaluation_tier_policy)

    adaptive_query_budget = _require_object(
        payload["adaptive_query_budget"],
        field="adaptive_query_budget",
    )
    query_budget = _validate_adaptive_query_budget(adaptive_query_budget)

    exposure_policy = _require_list(
        payload["tier_result_exposure_policy"],
        field="tier_result_exposure_policy",
    )
    exposure_tiers = _validate_tier_result_exposure_policy(exposure_policy)
    if exposure_tiers != allowed_tiers:
        raise MRLRealPreflightEvidenceError(
            "tier_result_exposure_policy must define exactly every allowed evaluation tier"
        )

    if EvaluationTier.SEARCH not in allowed_tiers and query_budget.tier_1_queries:
        raise MRLRealPreflightEvidenceError(
            "tier_1_queries must be zero when Tier 1 SEARCH is not allowed"
        )
    if EvaluationTier.REPLICATION not in allowed_tiers and query_budget.tier_2_queries:
        raise MRLRealPreflightEvidenceError(
            "tier_2_queries must be zero when Tier 2 REPLICATION is not allowed"
        )

    if payload["budget_exhaustion_disposition"] != "BLOCKED":
        raise MRLRealPreflightEvidenceError("budget_exhaustion_disposition must be exactly BLOCKED")


def _validate_resource_budget(payload: dict[str, object]) -> ResourceBudget:
    _require_keys(
        payload,
        {
            "compute_seconds",
            "evaluator_invocations",
            "generated_tokens",
            "input_tokens",
            "known_failure_retries",
            "max_experiments",
            "monetary_cost_microunits",
            "retries",
            "storage_bytes",
            "wall_clock_seconds",
        },
        label="MRL-0806 resource_budget",
    )
    try:
        return ResourceBudget(
            wall_clock_seconds=cast(int, payload["wall_clock_seconds"]),
            compute_seconds=cast(int | None, payload["compute_seconds"]),
            input_tokens=cast(int | None, payload["input_tokens"]),
            generated_tokens=cast(int | None, payload["generated_tokens"]),
            storage_bytes=cast(int, payload["storage_bytes"]),
            monetary_cost_microunits=cast(int | None, payload["monetary_cost_microunits"]),
            max_experiments=cast(int, payload["max_experiments"]),
            retries=cast(int, payload["retries"]),
            known_failure_retries=cast(int, payload["known_failure_retries"]),
            evaluator_invocations=cast(int | None, payload["evaluator_invocations"]),
        )
    except ResearchObjectiveContractError as exc:
        raise MRLRealPreflightEvidenceError(
            "resource_budget does not match canonical ResearchObjectiveContract semantics"
        ) from exc


def _validate_evaluation_tier_policy(payload: dict[str, object]) -> tuple[EvaluationTier, ...]:
    _require_keys(
        payload,
        {"allowed_tiers"},
        label="MRL-0806 evaluation_tier_policy",
    )
    raw_tiers = _require_list(
        payload["allowed_tiers"],
        field="evaluation_tier_policy.allowed_tiers",
    )
    tiers = tuple(
        _require_evaluation_tier(value, field="evaluation_tier_policy.allowed_tiers")
        for value in raw_tiers
    )
    try:
        policy = EvaluationTierPolicy(allowed_tiers=tiers)
    except ResearchObjectiveContractError as exc:
        raise MRLRealPreflightEvidenceError(
            "evaluation_tier_policy does not match canonical ResearchObjectiveContract semantics"
        ) from exc
    return policy.allowed_tiers


def _validate_adaptive_query_budget(payload: dict[str, object]) -> AdaptiveQueryBudget:
    _require_keys(
        payload,
        {"tier_1_queries", "tier_2_queries"},
        label="MRL-0806 adaptive_query_budget",
    )
    try:
        return AdaptiveQueryBudget(
            tier_1_queries=cast(int, payload["tier_1_queries"]),
            tier_2_queries=cast(int, payload["tier_2_queries"]),
        )
    except ResearchObjectiveContractError as exc:
        raise MRLRealPreflightEvidenceError(
            "adaptive_query_budget does not match canonical ResearchObjectiveContract semantics"
        ) from exc


def _validate_tier_result_exposure_policy(
    payload: list[object],
) -> tuple[EvaluationTier, ...]:
    exposures: list[TierResultExposure] = []
    for index, raw_entry in enumerate(payload):
        entry = _require_object(
            raw_entry,
            field=f"tier_result_exposure_policy[{index}]",
        )
        _require_keys(
            entry,
            {"allowed_result_fields", "max_exposures", "tier"},
            label=f"MRL-0806 tier_result_exposure_policy[{index}]",
        )
        tier = _require_evaluation_tier(
            entry["tier"],
            field=f"tier_result_exposure_policy[{index}].tier",
        )
        raw_fields = _require_list(
            entry["allowed_result_fields"],
            field=f"tier_result_exposure_policy[{index}].allowed_result_fields",
        )
        allowed_result_fields = tuple(
            _require_text(
                value,
                field=f"tier_result_exposure_policy[{index}].allowed_result_fields",
            )
            for value in raw_fields
        )
        try:
            exposures.append(
                TierResultExposure(
                    tier=tier,
                    max_exposures=cast(int, entry["max_exposures"]),
                    allowed_result_fields=allowed_result_fields,
                )
            )
        except ResearchObjectiveContractError as exc:
            raise MRLRealPreflightEvidenceError(
                "tier_result_exposure_policy does not match canonical "
                "ResearchObjectiveContract semantics"
            ) from exc

    tiers = tuple(exposure.tier for exposure in exposures)
    numeric_tiers = tuple(int(tier) for tier in tiers)
    if numeric_tiers != tuple(sorted(set(numeric_tiers))):
        raise MRLRealPreflightEvidenceError(
            "tier_result_exposure_policy must be unique and strictly ascending by tier"
        )
    return tiers


def _validate_evaluators(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "evaluation_contract_sha256",
            "evaluator_identity_sha256",
            "non_promotional",
            "promotion_authority_present",
            "sealed_tier3_identity_sha256",
        },
        label="MRL-0807 payload",
    )
    _require_true(payload["non_promotional"], field="non_promotional")
    _require_false(
        payload["promotion_authority_present"],
        field="promotion_authority_present",
    )
    for field_name in (
        "evaluation_contract_sha256",
        "evaluator_identity_sha256",
        "sealed_tier3_identity_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _validate_sandbox(payload: dict[str, object]) -> None:
    _require_keys(
        payload,
        {
            "allowed_mutation_paths_sha256",
            "mutation_paths_frozen",
            "network_policy_enforced",
            "network_policy_sha256",
            "output_destinations_frozen",
            "output_destinations_sha256",
            "runtime_sandbox_evidence_sha256",
            "sandbox_policy_sha256",
            "sandbox_qualified",
            "stop_conditions_frozen",
            "stop_conditions_sha256",
        },
        label="MRL-0808 payload",
    )
    for field_name in (
        "mutation_paths_frozen",
        "network_policy_enforced",
        "output_destinations_frozen",
        "sandbox_qualified",
        "stop_conditions_frozen",
    ):
        _require_true(payload[field_name], field=field_name)
    for field_name in (
        "allowed_mutation_paths_sha256",
        "network_policy_sha256",
        "output_destinations_sha256",
        "runtime_sandbox_evidence_sha256",
        "sandbox_policy_sha256",
        "stop_conditions_sha256",
    ):
        _require_sha256(payload[field_name], field=field_name)


def _require_keys(payload: dict[str, object], expected: set[str], *, label: str) -> None:
    if set(payload) != expected:
        raise MRLRealPreflightEvidenceError(f"{label} must contain the exact canonical key set")


def _require_object(value: object, *, field: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRLRealPreflightEvidenceError(f"{field} must be an exact JSON object")
    return cast(dict[str, object], value)


def _require_list(value: object, *, field: str) -> list[object]:
    if type(value) is not list:
        raise MRLRealPreflightEvidenceError(f"{field} must be an exact JSON array")
    return cast(list[object], value)


def _require_evaluation_tier(value: object, *, field: str) -> EvaluationTier:
    if type(value) is not int:
        raise MRLRealPreflightEvidenceError(f"{field} must be an integer evaluation tier")
    try:
        return EvaluationTier(value)
    except ValueError as exc:
        raise MRLRealPreflightEvidenceError(
            f"{field} must be one of evaluation tiers 0 through 4"
        ) from exc


def _require_task_id(value: object) -> str:
    if type(value) is not str or value not in _TASK_KIND:
        raise MRLRealPreflightEvidenceError("task_id must be one of MRL-0801..MRL-0808")
    return value


def _require_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value.strip() or value != value.strip() or "\x00" in value:
        raise MRLRealPreflightEvidenceError(
            f"{field} must be non-empty NUL-free text without surrounding whitespace"
        )
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRLRealPreflightEvidenceError(f"{field} must be exactly 64 lowercase hex characters")
    return value


def _require_git_sha(value: object, *, field: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRLRealPreflightEvidenceError(f"{field} must be exactly 40 lowercase hex characters")
    return value


def _require_positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRLRealPreflightEvidenceError(f"{field} must be a positive int")
    return value


def _require_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise MRLRealPreflightEvidenceError(f"{field} must be a non-negative int")
    return value


def _require_true(value: object, *, field: str) -> None:
    if value is not True:
        raise MRLRealPreflightEvidenceError(f"{field} must be exact JSON true")


def _require_false(value: object, *, field: str) -> None:
    if value is not False:
        raise MRLRealPreflightEvidenceError(f"{field} must be exact JSON false")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRLRealPreflightEvidenceError(
                f"duplicate real-preflight evidence JSON member rejected: {key}"
            )
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> None:
    raise MRLRealPreflightEvidenceError(f"non-standard JSON constant is prohibited: {value}")


__all__ = [
    "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
    "MRLRealPreflightEvidence",
    "MRLRealPreflightEvidenceError",
    "MRLRealPreflightTask",
    "MRLRealPreflightTrustSnapshot",
    "admit_mrl_real_preflight_evidence",
    "mrl_real_preflight_trust_snapshot",
    "parse_mrl_real_preflight_evidence",
]
