"""Deterministic Experiment-0 contamination and held-out isolation evidence for MRL-0803.

The producer operates only on the exact MRL-0802 admitted structural Patient corpus. It
partitions synthetic patients by indivisible normalized household groups into SEARCH,
REPLICATION, and SEALED tiers, proves cross-tier exact/household isolation, performs a
frozen near-structural Jaccard check, and emits an untrusted MRL-0803 evidence candidate.

This module does not inspect upstream model pretraining corpora, load models/tokenizers,
execute inference/GPU work, authorize training, or mutate the production trust registry.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import (
    CanonicalContractError,
    canonical_json_bytes,
    canonical_jsonl_bytes,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_AUTHORIZATION_SHA256: Final = "bf22c52995e9b55d35eab0ddc610a9d73d5af91803456b49942d2d4341cf2e75"
_SCHEMA_VERSION: Final = "MESC-MRL-0803-ISOLATION-AUTHORIZATION-V1"
_POLICY_ID: Final = "MESC-MRL-0803-HOUSEHOLD-SPLIT-V1"
_EXPECTED_TASK: Final = "MRL-0803"
_EXPECTED_KIND: Final = "mesc.mrl.real_preflight.isolation.v1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_ALLOWED_PATIENT_KEYS: Final = frozenset(
    {"address", "birthDate", "deceasedBoolean", "gender", "id", "resourceType"}
)
_ADDRESS_KEYS: Final = ("city", "country", "postalCode", "state")
_TIERS: Final = ("TIER_1_SEARCH", "TIER_2_REPLICATION", "TIER_3_SEALED")


class MRL0803IsolationError(ValueError):
    """Raised when MRL-0803 isolation evidence cannot be produced fail-closed."""


@dataclass(frozen=True, slots=True)
class MRL0803IsolationAuthorization:
    """Exact committed authorization for MRL-0803 evidence production."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)
    corpus_sha256: str = field(init=False)
    corpus_byte_count: int = field(init=False)
    corpus_record_count: int = field(init=False)
    mrl_0802_evidence_sha256: str = field(init=False)
    near_threshold: Fraction = field(init=False)
    tier_counts: tuple[int, int, int] = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="authorization")
        digest = hashlib.sha256(self.canonical_bytes).hexdigest()
        if digest != _AUTHORIZATION_SHA256:
            raise MRL0803IsolationError("authorization does not match the exact committed scope")
        values = _validate_authorization(document)
        object.__setattr__(self, "authorization_sha256", digest)
        object.__setattr__(self, "corpus_sha256", values[0])
        object.__setattr__(self, "corpus_byte_count", values[1])
        object.__setattr__(self, "corpus_record_count", values[2])
        object.__setattr__(self, "mrl_0802_evidence_sha256", values[3])
        object.__setattr__(self, "near_threshold", values[4])
        object.__setattr__(self, "tier_counts", values[5])


@dataclass(frozen=True, slots=True)
class MRL0803IsolationQualification:
    """Deterministic untrusted evidence candidate and its external supporting artifacts."""

    split_manifest_bytes: bytes = field(repr=False)
    lineage_report_bytes: bytes = field(repr=False)
    decontamination_report_bytes: bytes = field(repr=False)
    tier1_bytes: bytes = field(repr=False)
    tier2_bytes: bytes = field(repr=False)
    tier3_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    split_manifest_sha256: str
    lineage_report_sha256: str
    decontamination_report_sha256: str
    heldout_evaluation_sha256: str
    evidence_sha256: str
    tier_counts: tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class _HouseholdGroup:
    identity: str
    patient_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ParsedCorpus:
    records: tuple[dict[str, object], ...]
    by_id: dict[str, dict[str, object]] = field(repr=False)
    household_by_id: dict[str, str] = field(repr=False)


def parse_mrl_0803_isolation_authorization(raw: bytes) -> MRL0803IsolationAuthorization:
    """Parse the exact committed MRL-0803 producer authorization."""
    return MRL0803IsolationAuthorization(raw)


def qualify_mrl_0803_isolation(
    corpus_bytes: bytes,
    *,
    authorization: MRL0803IsolationAuthorization,
    repository_commit: str,
    repository_tree: str,
) -> MRL0803IsolationQualification:
    """Produce deterministic isolation artifacts for one exact admitted corpus."""
    if type(authorization) is not MRL0803IsolationAuthorization:
        raise MRL0803IsolationError("authorization type is invalid")
    _require_git_sha(repository_commit, "repository_commit")
    _require_git_sha(repository_tree, "repository_tree")
    if len(corpus_bytes) != authorization.corpus_byte_count:
        raise MRL0803IsolationError("corpus byte count does not match authorization")
    corpus_sha256 = hashlib.sha256(corpus_bytes).hexdigest()
    if corpus_sha256 != authorization.corpus_sha256:
        raise MRL0803IsolationError("corpus SHA-256 does not match authorization")

    parsed = _parse_corpus(corpus_bytes)
    if len(parsed.records) != authorization.corpus_record_count:
        raise MRL0803IsolationError("corpus record count does not match authorization")
    assignments = _assign_tiers(parsed, authorization)
    tier_records = {
        tier: tuple(parsed.by_id[patient_id] for patient_id in assignments[tier]) for tier in _TIERS
    }
    tier_bytes = {tier: canonical_jsonl_bytes(records) for tier, records in tier_records.items()}
    tier_sha256 = {
        tier: hashlib.sha256(payload).hexdigest() for tier, payload in tier_bytes.items()
    }

    split_manifest_bytes = canonical_json_bytes(
        {
            "authorization_sha256": authorization.authorization_sha256,
            "corpus_sha256": corpus_sha256,
            "policy_id": _POLICY_ID,
            "schema_version": "MESC-MRL-0803-SPLIT-MANIFEST-V1",
            "tiers": [
                {
                    "patient_ids": list(assignments[tier]),
                    "record_count": len(assignments[tier]),
                    "tier": tier,
                    "tier_sha256": tier_sha256[tier],
                }
                for tier in _TIERS
            ],
        }
    )
    split_manifest_sha256 = hashlib.sha256(split_manifest_bytes).hexdigest()

    exact_overlap_count = _exact_cross_tier_overlap_count(tier_bytes)
    household_overlap_count = _household_cross_tier_overlap_count(assignments, parsed)
    max_near = _max_cross_tier_jaccard(tier_records)
    if exact_overlap_count:
        raise MRL0803IsolationError("exact records overlap across evaluation tiers")
    if household_overlap_count:
        raise MRL0803IsolationError("synthetic household groups overlap across evaluation tiers")
    if max_near >= authorization.near_threshold:
        raise MRL0803IsolationError(
            "near-structural cross-tier similarity reaches frozen threshold"
        )

    decontamination_report_bytes = canonical_json_bytes(
        {
            "authorization_sha256": authorization.authorization_sha256,
            "contamination_disposition": "PASS",
            "contamination_scope": "MESC_CONTROLLED_SURFACES_ONLY",
            "corpus_sha256": corpus_sha256,
            "exact_cross_tier_duplicate_count": exact_overlap_count,
            "max_cross_tier_jaccard": {
                "denominator": max_near.denominator,
                "numerator": max_near.numerator,
            },
            "near_structural_threshold": {
                "denominator": authorization.near_threshold.denominator,
                "numerator": authorization.near_threshold.numerator,
            },
            "schema_version": "MESC-MRL-0803-DECONTAMINATION-REPORT-V1",
            "semantic_detector_disposition": "NOT_APPLICABLE_STRUCTURAL_PATIENT_PROJECTION",
            "synthetic_household_cross_tier_overlap_count": household_overlap_count,
            "upstream_pretraining_overlap_assessed": False,
            "upstream_pretraining_overlap_claimed": False,
        }
    )
    decontamination_report_sha256 = hashlib.sha256(decontamination_report_bytes).hexdigest()

    lineage_report_bytes = canonical_json_bytes(
        {
            "authorization_sha256": authorization.authorization_sha256,
            "corpus_sha256": corpus_sha256,
            "experiment_id": "mesc-experiment-0-foundation-tournament",
            "mesc_executor": {
                "commit": repository_commit,
                "repository": "TheHalfMoon/MESC",
                "tree": repository_tree,
            },
            "mrl_0802_evidence_sha256": authorization.mrl_0802_evidence_sha256,
            "schema_version": "MESC-MRL-0803-LINEAGE-REPORT-V1",
            "split_manifest_sha256": split_manifest_sha256,
            "training_surface_present": False,
            "tier3_allowed_in_adaptive_search": False,
            "tier3_allowed_in_training": False,
            "tier3_item_access_by_research_process": False,
            "tiers": [
                {
                    "record_count": len(assignments[tier]),
                    "tier": tier,
                    "tier_sha256": tier_sha256[tier],
                }
                for tier in _TIERS
            ],
        }
    )
    lineage_report_sha256 = hashlib.sha256(lineage_report_bytes).hexdigest()
    heldout_evaluation_sha256 = tier_sha256["TIER_3_SEALED"]

    evidence_bytes = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _EXPECTED_KIND,
            "payload": {
                "contamination_disposition": "PASS",
                "corpus_sha256": corpus_sha256,
                "decontamination_report_sha256": decontamination_report_sha256,
                "heldout_evaluation_sha256": heldout_evaluation_sha256,
                "lineage_report_sha256": lineage_report_sha256,
                "sealed_evaluation_excluded_from_training": True,
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": corpus_sha256,
            "task_id": _EXPECTED_TASK,
        }
    )
    parsed_evidence = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed_evidence.task_id != _EXPECTED_TASK or parsed_evidence.subject_sha256 != corpus_sha256:
        raise MRL0803IsolationError("generated MRL-0803 evidence failed semantic binding")

    return MRL0803IsolationQualification(
        split_manifest_bytes=split_manifest_bytes,
        lineage_report_bytes=lineage_report_bytes,
        decontamination_report_bytes=decontamination_report_bytes,
        tier1_bytes=tier_bytes["TIER_1_SEARCH"],
        tier2_bytes=tier_bytes["TIER_2_REPLICATION"],
        tier3_bytes=tier_bytes["TIER_3_SEALED"],
        evidence_bytes=evidence_bytes,
        split_manifest_sha256=split_manifest_sha256,
        lineage_report_sha256=lineage_report_sha256,
        decontamination_report_sha256=decontamination_report_sha256,
        heldout_evaluation_sha256=heldout_evaluation_sha256,
        evidence_sha256=parsed_evidence.evidence_sha256,
        tier_counts=cast(tuple[int, int, int], tuple(len(assignments[tier]) for tier in _TIERS)),
    )


def verify_mrl_0803_isolation_bundle(
    corpus_bytes: bytes,
    *,
    authorization: MRL0803IsolationAuthorization,
    repository_commit: str,
    repository_tree: str,
    split_manifest_bytes: bytes,
    lineage_report_bytes: bytes,
    decontamination_report_bytes: bytes,
    tier1_bytes: bytes,
    tier2_bytes: bytes,
    tier3_bytes: bytes,
    evidence_bytes: bytes,
) -> MRL0803IsolationQualification:
    """Independently recompute and require byte-identical MRL-0803 artifacts."""
    expected = qualify_mrl_0803_isolation(
        corpus_bytes,
        authorization=authorization,
        repository_commit=repository_commit,
        repository_tree=repository_tree,
    )
    supplied = (
        ("split manifest", split_manifest_bytes, expected.split_manifest_bytes),
        ("lineage report", lineage_report_bytes, expected.lineage_report_bytes),
        (
            "decontamination report",
            decontamination_report_bytes,
            expected.decontamination_report_bytes,
        ),
        ("Tier 1 bytes", tier1_bytes, expected.tier1_bytes),
        ("Tier 2 bytes", tier2_bytes, expected.tier2_bytes),
        ("Tier 3 bytes", tier3_bytes, expected.tier3_bytes),
        ("evidence", evidence_bytes, expected.evidence_bytes),
    )
    for label, actual, wanted in supplied:
        if actual != wanted:
            raise MRL0803IsolationError(
                f"{label} is not byte-identical to deterministic recomputation"
            )
    return expected


def _parse_corpus(raw: bytes) -> _ParsedCorpus:
    if not raw or not raw.endswith(b"\n"):
        raise MRL0803IsolationError("corpus must be non-empty canonical JSONL ending in LF")
    records: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    household_by_id: dict[str, str] = {}
    for index, line in enumerate(raw.splitlines(keepends=True)):
        if line in {b"", b"\n"}:
            raise MRL0803IsolationError("corpus cannot contain blank JSONL records")
        record = _parse_canonical_object(line, label=f"corpus record {index}")
        _validate_patient_record(record)
        patient_id = cast(str, record["id"])
        if patient_id in by_id:
            raise MRL0803IsolationError("Patient ids must be unique")
        records.append(record)
        by_id[patient_id] = record
        household_by_id[patient_id] = _household_identity(record)
    ordered = tuple(sorted(records, key=lambda item: cast(str, item["id"])))
    if canonical_jsonl_bytes(ordered) != raw:
        raise MRL0803IsolationError("corpus records must be canonically ordered by Patient id")
    return _ParsedCorpus(records=ordered, by_id=by_id, household_by_id=household_by_id)


def _validate_patient_record(record: dict[str, object]) -> None:
    if set(record) - _ALLOWED_PATIENT_KEYS:
        raise MRL0803IsolationError(
            "corpus contains fields outside the authorized Patient projection"
        )
    if record.get("resourceType") != "Patient":
        raise MRL0803IsolationError("every corpus record must be a Patient")
    patient_id = record.get("id")
    if type(patient_id) is not str or not patient_id.strip() or patient_id != patient_id.strip():
        raise MRL0803IsolationError("Patient id must be canonical non-blank text")
    gender = record.get("gender")
    if gender is not None and (
        type(gender) is not str or not gender.strip() or gender != gender.strip()
    ):
        raise MRL0803IsolationError("Patient gender must be canonical non-blank text")
    birth_date = record.get("birthDate")
    if birth_date is not None and (
        type(birth_date) is not str or not birth_date.strip() or birth_date != birth_date.strip()
    ):
        raise MRL0803IsolationError("Patient birthDate must be canonical non-blank text")
    deceased = record.get("deceasedBoolean")
    if deceased is not None and type(deceased) is not bool:
        raise MRL0803IsolationError("Patient deceasedBoolean must be an exact boolean")
    addresses = record.get("address")
    if addresses is not None:
        if type(addresses) is not list:
            raise MRL0803IsolationError("Patient address must be an array when present")
        for address in addresses:
            if type(address) is not dict or not address:
                raise MRL0803IsolationError("Patient address entries must be non-empty objects")
            if set(address) - set(_ADDRESS_KEYS):
                raise MRL0803IsolationError(
                    "Patient address contains fields outside the projection"
                )
            if any(
                type(value) is not str or not value.strip() or value != value.strip()
                for value in address.values()
            ):
                raise MRL0803IsolationError(
                    "Patient address values must be canonical non-blank text"
                )


def _household_identity(record: dict[str, object]) -> str:
    patient_id = cast(str, record["id"])
    raw_addresses = record.get("address")
    normalized: list[dict[str, str]] = []
    if type(raw_addresses) is list:
        for raw in raw_addresses:
            if type(raw) is dict:
                normalized.append(
                    {key: cast(str, raw[key]) for key in _ADDRESS_KEYS if type(raw.get(key)) is str}
                )
    normalized.sort(key=lambda value: canonical_json_bytes(value))
    payload: dict[str, object]
    if normalized:
        payload = {"addresses": normalized, "policy_id": _POLICY_ID}
    else:
        payload = {"no_address_patient_id": patient_id, "policy_id": _POLICY_ID}
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _assign_tiers(
    parsed: _ParsedCorpus, authorization: MRL0803IsolationAuthorization
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for patient_id, household in parsed.household_by_id.items():
        grouped.setdefault(household, []).append(patient_id)
    groups = tuple(
        _HouseholdGroup(identity=identity, patient_ids=tuple(sorted(patient_ids)))
        for identity, patient_ids in sorted(grouped.items())
    )
    tier1_count, tier2_count, tier3_count = authorization.tier_counts
    tier3_groups = _choose_group_subset(groups, tier3_count, "TIER_3_SEALED")
    remaining = tuple(group for group in groups if group not in tier3_groups)
    tier2_groups = _choose_group_subset(remaining, tier2_count, "TIER_2_REPLICATION")
    tier1_groups = tuple(group for group in remaining if group not in tier2_groups)
    assignments = {
        "TIER_1_SEARCH": _group_patient_ids(tier1_groups),
        "TIER_2_REPLICATION": _group_patient_ids(tier2_groups),
        "TIER_3_SEALED": _group_patient_ids(tier3_groups),
    }
    actual = tuple(len(assignments[tier]) for tier in _TIERS)
    if actual != (tier1_count, tier2_count, tier3_count):
        raise MRL0803IsolationError(
            "deterministic household split does not match authorized counts"
        )
    all_ids = tuple(patient_id for tier in _TIERS for patient_id in assignments[tier])
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(parsed.by_id):
        raise MRL0803IsolationError(
            "deterministic household split is not an exact corpus partition"
        )
    return assignments


def _choose_group_subset(
    groups: tuple[_HouseholdGroup, ...], target_count: int, tier: str
) -> tuple[_HouseholdGroup, ...]:
    candidates: list[tuple[str, tuple[str, ...], tuple[_HouseholdGroup, ...]]] = []
    for size in range(1, len(groups) + 1):
        for subset in itertools.combinations(groups, size):
            if sum(len(group.patient_ids) for group in subset) != target_count:
                continue
            identities = tuple(sorted(group.identity for group in subset))
            score = hashlib.sha256(
                canonical_json_bytes(
                    {"groups": list(identities), "policy_id": _POLICY_ID, "tier": tier}
                )
            ).hexdigest()
            candidates.append((score, identities, subset))
    if not candidates:
        raise MRL0803IsolationError(
            f"household grouping cannot satisfy authorized count for {tier}"
        )
    return min(candidates, key=lambda item: (item[0], item[1]))[2]


def _group_patient_ids(groups: tuple[_HouseholdGroup, ...]) -> tuple[str, ...]:
    return tuple(sorted(patient_id for group in groups for patient_id in group.patient_ids))


def _exact_cross_tier_overlap_count(tier_bytes: dict[str, bytes]) -> int:
    lines = {tier: set(payload.splitlines()) for tier, payload in tier_bytes.items()}
    return sum(
        len(lines[left] & lines[right])
        for index, left in enumerate(_TIERS)
        for right in _TIERS[index + 1 :]
    )


def _household_cross_tier_overlap_count(
    assignments: dict[str, tuple[str, ...]], parsed: _ParsedCorpus
) -> int:
    households = {
        tier: {parsed.household_by_id[patient_id] for patient_id in patient_ids}
        for tier, patient_ids in assignments.items()
    }
    return sum(
        len(households[left] & households[right])
        for index, left in enumerate(_TIERS)
        for right in _TIERS[index + 1 :]
    )


def _max_cross_tier_jaccard(tier_records: dict[str, tuple[dict[str, object], ...]]) -> Fraction:
    maximum = Fraction(0, 1)
    for index, left in enumerate(_TIERS):
        for right in _TIERS[index + 1 :]:
            for first in tier_records[left]:
                first_features = _structural_features(first)
                for second in tier_records[right]:
                    second_features = _structural_features(second)
                    union = first_features | second_features
                    similarity = Fraction(len(first_features & second_features), len(union))
                    maximum = max(maximum, similarity)
    return maximum


def _structural_features(record: dict[str, object]) -> frozenset[str]:
    features: set[str] = {"resourceType=Patient"}
    for key in ("birthDate", "deceasedBoolean", "gender"):
        value = record.get(key)
        if type(value) in (str, bool):
            features.add(f"{key}={value}")
    raw_addresses = record.get("address")
    if type(raw_addresses) is list:
        for address in raw_addresses:
            if type(address) is dict:
                for key in _ADDRESS_KEYS:
                    value = address.get(key)
                    if type(value) is str:
                        features.add(f"address.{key}={value}")
    return frozenset(features)


def _validate_authorization(
    document: dict[str, object],
) -> tuple[str, int, int, str, Fraction, tuple[int, int, int]]:
    if document.get("schema_version") != _SCHEMA_VERSION:
        raise MRL0803IsolationError("authorization schema_version is invalid")
    if document.get("authorization_state") != "AUTHORIZED":
        raise MRL0803IsolationError("authorization_state must be exactly AUTHORIZED")
    if document.get("task_id") != _EXPECTED_TASK or document.get("issue_number") != 407:
        raise MRL0803IsolationError("authorization task/issue binding is invalid")
    if document.get("experiment_id") != "mesc-experiment-0-foundation-tournament":
        raise MRL0803IsolationError("authorization experiment binding is invalid")
    corpus = _require_object(document.get("corpus"), label="authorization corpus")
    corpus_sha256 = _require_sha256(corpus.get("corpus_sha256"), "corpus_sha256")
    byte_count = _require_positive_int(corpus.get("byte_count"), "byte_count")
    record_count = _require_positive_int(corpus.get("record_count"), "record_count")
    evidence_sha256 = _require_sha256(
        corpus.get("mrl_0802_evidence_sha256"), "mrl_0802_evidence_sha256"
    )
    split = _require_object(document.get("split_policy"), label="split_policy")
    if split.get("policy_id") != _POLICY_ID:
        raise MRL0803IsolationError("split policy identity is invalid")
    if split.get("tier3_item_access_by_research_process") is not False:
        raise MRL0803IsolationError("Tier 3 item access must remain prohibited")
    if split.get("tier3_allowed_in_training") is not False:
        raise MRL0803IsolationError("Tier 3 training use must remain prohibited")
    if split.get("tier3_allowed_in_adaptive_search") is not False:
        raise MRL0803IsolationError("Tier 3 adaptive-search use must remain prohibited")
    counts = _require_object(split.get("tier_record_counts"), label="tier_record_counts")
    tier_counts = tuple(_require_positive_int(counts.get(tier), tier) for tier in _TIERS)
    if sum(tier_counts) != record_count:
        raise MRL0803IsolationError("authorized tier counts must exactly partition the corpus")
    contamination = _require_object(
        document.get("contamination_policy"), label="contamination_policy"
    )
    if contamination.get("scope") != "MESC_CONTROLLED_SURFACES_ONLY":
        raise MRL0803IsolationError("contamination scope is invalid")
    if contamination.get("upstream_pretraining_overlap_claimed") is not False:
        raise MRL0803IsolationError("upstream pretraining overlap claims are prohibited")
    threshold = _require_object(
        contamination.get("near_structural_jaccard_threshold"), label="near threshold"
    )
    numerator = _require_nonnegative_int(threshold.get("numerator"), "near threshold numerator")
    denominator = _require_positive_int(threshold.get("denominator"), "near threshold denominator")
    near_threshold = Fraction(numerator, denominator)
    if near_threshold <= 0 or near_threshold > 1:
        raise MRL0803IsolationError("near structural threshold must be within (0,1]")
    policy = _require_object(document.get("policy"), label="authorization policy")
    for field_name in (
        "experiment_execution_authorized",
        "gpu_execution_authorized",
        "inference_authorized",
        "model_loading_authorized",
        "production_trust_registry_mutation_authorized",
        "tokenizer_loading_authorized",
        "training_authorized",
    ):
        if policy.get(field_name) is not False:
            raise MRL0803IsolationError(f"{field_name} must remain false")
    return (
        corpus_sha256,
        byte_count,
        record_count,
        evidence_sha256,
        near_threshold,
        cast(tuple[int, int, int], tier_counts),
    )


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, ValueError, CanonicalContractError) as exc:
        raise MRL0803IsolationError(f"{label} is not strict canonical JSON") from exc
    if type(document) is not dict:
        raise MRL0803IsolationError(f"{label} must be a JSON object")
    typed = cast(dict[str, object], document)
    try:
        canonical = canonical_json_bytes(typed)
    except CanonicalContractError as exc:
        raise MRL0803IsolationError(f"{label} contains noncanonical values") from exc
    if raw != canonical:
        raise MRL0803IsolationError(f"{label} bytes are not canonical")
    return typed


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON object key")
        output[key] = value
    return output


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON constant is prohibited: {value}")


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0803IsolationError(f"{label} must be an exact JSON object")
    return cast(dict[str, object], value)


def _require_sha256(value: object, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0803IsolationError(f"{label} must be 64 lowercase hex")
    return value


def _require_git_sha(value: object, label: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0803IsolationError(f"{label} must be 40 lowercase hex")
    return value


def _require_positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0803IsolationError(f"{label} must be a positive integer")
    return value


def _require_nonnegative_int(value: object, label: str) -> int:
    if type(value) is not int or value < 0:
        raise MRL0803IsolationError(f"{label} must be a non-negative integer")
    return value
