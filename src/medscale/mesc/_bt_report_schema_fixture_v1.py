"""Fail-closed shape validation for normalized Backbone Tournament report fixtures.

This module mirrors the frozen ``MESC-BT-REPORT-V1`` JSON-schema shape for
caller-supplied in-memory fixtures. It performs no filesystem, report-artifact,
corpus, scoring-key, provider, model, ranking, winner-selection, or execution
operation. Non-integer JSON numbers are represented as ``Decimal`` at this
fixture boundary so binary floating-point cannot silently affect later checks.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Final, cast

REPORT_SCHEMA_VERSION: Final = "MESC-BT-REPORT-V1"
REPORT_SCHEMA_SHA256: Final = "cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d"
PROTOCOL_CONFIG_SHA256: Final = "097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203"
SCORING_CONTRACT_SHA256: Final = "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"

CANDIDATE_REVISIONS: Final[dict[str, str]] = {
    "openai/gpt-oss-20b": "6cee5e81ee83917806bbde320786a8fb61efebee",
    "swiss-ai/Apertus-v1.5-8B": "a411d838600baf0e3635a3daf66fb7c55fc97bb6",
    "microsoft/Phi-4-multimodal-instruct": "93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
    "google/medgemma-1.5-4b-it": "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
}
_CANDIDATE_IDS: Final = frozenset(CANDIDATE_REVISIONS)
_CANDIDATE_REVISION_VALUES: Final = frozenset(CANDIDATE_REVISIONS.values())
_AXIS_NAMES: Final = (
    "medical_reasoning",
    "evidence_fidelity",
    "uncertainty_abstention",
    "safety",
    "structured_fhir",
    "operational_reproducibility",
)
ERROR_CLASSES: Final = (
    "TIMEOUT",
    "RUNTIME_FAILURE",
    "GENERATION_FAILURE",
    "PARSE_FAILURE",
    "SCHEMA_FAILURE",
    "SAFETY_FAILURE",
)
_NEGATIVE_CATEGORIES: Final = frozenset(
    {
        "GATE_FAILURE",
        "AXIS_BELOW_THRESHOLD",
        "CRITICAL_SAFETY_FAILURE",
        "OPERATIONAL_INFEASIBILITY",
        "GENERATION_OR_PARSE_FAILURE",
        "OTHER",
    }
)
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ITEM_ID = re.compile(r"^BT-[A-F]-(00[1-9]|0[1-3][0-9]|040)$")

_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "schema_version",
        "mesc_commit_sha",
        "mesc_tree_sha",
        "protocol_id",
        "protocol_config_sha256",
        "prompt_bundle_sha256",
        "system_prompt_sha256",
        "prompt_protocol_sha256",
        "corpus_spec_sha256",
        "materialized_corpus_sha256",
        "materialized_corpus_gzip_sha256",
        "materialized_corpus_item_count",
        "corpus_manifest_sha256",
        "scoring_keys_sha256",
        "normalized_output_schema_sha256",
        "parser_contract_sha256",
        "scoring_contract_sha256",
        "report_validation_contract_sha256",
        "report_schema_sha256",
        "candidate_reports",
        "role_results",
        "negative_results",
        "artifact_manifest_sha256",
    }
)
_CANDIDATE_KEYS: Final = frozenset(
    {
        "candidate_id",
        "candidate_revision",
        "items_attempted",
        "items_completed",
        "axis_scores",
        "aggregate_score",
        "critical_safety_failures",
        "compact_gate",
        "flagship_gate",
        "errors",
        "exclusions",
        "negative_results",
        "operational",
    }
)
_ERROR_KEYS: Final = frozenset({"total", *ERROR_CLASSES})
_OPERATIONAL_KEYS: Final = frozenset(
    {
        "median_latency_ms",
        "p95_latency_ms",
        "peak_vram_mb",
        "input_tokens",
        "output_tokens",
        "provider_cost",
    }
)
_ROLE_KEYS: Final = frozenset({"compact", "flagship_reasoner"})
_ROLE_RESULT_KEYS: Final = frozenset({"outcome", "candidate_id", "reason", "tied_candidate_ids"})

_STATIC_CONSTS: Final[dict[str, object]] = {
    "schema_version": REPORT_SCHEMA_VERSION,
    "protocol_id": "MESC-BT-PROTOCOL-V1",
    "protocol_config_sha256": PROTOCOL_CONFIG_SHA256,
    "prompt_bundle_sha256": "54d9da5cf3dad58c0bf9fb28761c15d8f82568013895b8467f1cb7d532c314b7",
    "system_prompt_sha256": "02bb1a1fe70036c5d5299d6654618a2734aa03550506d1b023904cefc88ba867",
    "prompt_protocol_sha256": "a2a42aef340e27f9396b40810999d5f2c4136af467ce27ee9e3c149e3257c89c",
    "corpus_spec_sha256": "49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b",
    "materialized_corpus_sha256": (
        "48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd"
    ),
    "materialized_corpus_gzip_sha256": (
        "667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632"
    ),
    "materialized_corpus_item_count": 240,
    "corpus_manifest_sha256": "201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745",
    "scoring_keys_sha256": "bb3524bc8dd1f05bad433c664ac3c48a5110939ac78b5ffa2ad8853f944c6318",
    "normalized_output_schema_sha256": (
        "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
    ),
    "parser_contract_sha256": "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071",
    "scoring_contract_sha256": SCORING_CONTRACT_SHA256,
    "report_validation_contract_sha256": (
        "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
    ),
}


class ReportSchemaFixtureError(ValueError):
    """The caller-supplied normalized report fixture violates MESC-BT-REPORT-V1."""


def validate_report_schema_fixture(report: dict[str, object]) -> None:
    """Validate only the frozen report JSON shape and schema-level constraints."""
    root = _require_object(report, path="$")
    _require_exact_keys(root, _TOP_LEVEL_KEYS, path="$")

    for field, expected in _STATIC_CONSTS.items():
        if root[field] != expected or type(root[field]) is not type(expected):
            raise ReportSchemaFixtureError(f"$.{field} must equal the frozen schema constant")

    _require_pattern_string(root["mesc_commit_sha"], _HEX40, path="$.mesc_commit_sha")
    _require_pattern_string(root["mesc_tree_sha"], _HEX40, path="$.mesc_tree_sha")
    _require_pattern_string(root["report_schema_sha256"], _HEX64, path="$.report_schema_sha256")
    _require_pattern_string(
        root["artifact_manifest_sha256"], _HEX64, path="$.artifact_manifest_sha256"
    )

    candidate_reports = _require_list(root["candidate_reports"], path="$.candidate_reports")
    if not 2 <= len(candidate_reports) <= 4:
        raise ReportSchemaFixtureError("$.candidate_reports must contain 2..4 objects")
    for index, candidate in enumerate(candidate_reports):
        _validate_candidate_report(candidate, path=f"$.candidate_reports[{index}]")
        if any(candidate == prior for prior in candidate_reports[:index]):
            raise ReportSchemaFixtureError("$.candidate_reports must contain unique items")

    role_results = _require_object(root["role_results"], path="$.role_results")
    _require_exact_keys(role_results, _ROLE_KEYS, path="$.role_results")
    for role in ("compact", "flagship_reasoner"):
        _validate_role_result(role_results[role], path=f"$.role_results.{role}")

    negative_results = _require_list(root["negative_results"], path="$.negative_results")
    for index, item in enumerate(negative_results):
        _validate_top_level_negative_result(item, path=f"$.negative_results[{index}]")


def _validate_candidate_report(value: object, *, path: str) -> None:
    candidate = _require_object(value, path=path)
    _require_exact_keys(candidate, _CANDIDATE_KEYS, path=path)

    candidate_id = _require_string(candidate["candidate_id"], path=f"{path}.candidate_id")
    if candidate_id not in _CANDIDATE_IDS:
        raise ReportSchemaFixtureError(f"{path}.candidate_id is not in the frozen enum")
    revision = _require_string(candidate["candidate_revision"], path=f"{path}.candidate_revision")
    if revision not in _CANDIDATE_REVISION_VALUES:
        raise ReportSchemaFixtureError(f"{path}.candidate_revision is not in the frozen enum")

    _require_exact_int(candidate["items_attempted"], 240, path=f"{path}.items_attempted")
    _require_int_range(candidate["items_completed"], 0, 240, path=f"{path}.items_completed")
    _require_int_range(
        candidate["critical_safety_failures"],
        0,
        40,
        path=f"{path}.critical_safety_failures",
    )

    axes = _require_object(candidate["axis_scores"], path=f"{path}.axis_scores")
    _require_exact_keys(axes, frozenset(_AXIS_NAMES), path=f"{path}.axis_scores")
    for axis in _AXIS_NAMES:
        _require_number_range(
            axes[axis],
            Decimal("0"),
            Decimal("100"),
            path=f"{path}.axis_scores.{axis}",
        )
    _require_number_range(
        candidate["aggregate_score"], Decimal("0"), Decimal("100"), path=f"{path}.aggregate_score"
    )

    for gate in ("compact_gate", "flagship_gate"):
        gate_value = _require_string(candidate[gate], path=f"{path}.{gate}")
        if gate_value not in {"PASS", "FAIL"}:
            raise ReportSchemaFixtureError(f"{path}.{gate} must be PASS or FAIL")

    errors = _require_object(candidate["errors"], path=f"{path}.errors")
    _require_exact_keys(errors, _ERROR_KEYS, path=f"{path}.errors")
    for key in ("total", *ERROR_CLASSES):
        _require_int_range(errors[key], 0, 240, path=f"{path}.errors.{key}")

    exclusions = _require_list(candidate["exclusions"], path=f"{path}.exclusions")
    if len(exclusions) > 240:
        raise ReportSchemaFixtureError(f"{path}.exclusions must contain at most 240 entries")
    seen_exclusions: set[tuple[str, str, str]] = set()
    for index, exclusion in enumerate(exclusions):
        item = _require_object(exclusion, path=f"{path}.exclusions[{index}]")
        _require_exact_keys(
            item,
            frozenset({"item_id", "reason", "error_class"}),
            path=f"{path}.exclusions[{index}]",
        )
        item_id = _require_item_id(item["item_id"], path=f"{path}.exclusions[{index}].item_id")
        reason = _require_nonempty_string(item["reason"], path=f"{path}.exclusions[{index}].reason")
        error_class = _require_string(
            item["error_class"], path=f"{path}.exclusions[{index}].error_class"
        )
        if error_class not in ERROR_CLASSES:
            raise ReportSchemaFixtureError(f"{path}.exclusions[{index}].error_class is not frozen")
        identity = (item_id, reason, error_class)
        if identity in seen_exclusions:
            raise ReportSchemaFixtureError(f"{path}.exclusions must be unique")
        seen_exclusions.add(identity)

    negatives = _require_list(candidate["negative_results"], path=f"{path}.negative_results")
    for index, negative in enumerate(negatives):
        item = _require_object(negative, path=f"{path}.negative_results[{index}]")
        _require_exact_keys(
            item,
            frozenset({"category", "summary", "item_id"}),
            path=f"{path}.negative_results[{index}]",
        )
        _validate_negative_fields(item, path=f"{path}.negative_results[{index}]")

    operational = _require_object(candidate["operational"], path=f"{path}.operational")
    _require_exact_keys(operational, _OPERATIONAL_KEYS, path=f"{path}.operational")
    for field in ("median_latency_ms", "p95_latency_ms", "peak_vram_mb"):
        _require_number_range(
            operational[field], Decimal("0"), None, path=f"{path}.operational.{field}"
        )
    for field in ("input_tokens", "output_tokens"):
        _require_int_range(operational[field], 0, None, path=f"{path}.operational.{field}")
    provider_cost = operational["provider_cost"]
    if provider_cost != "N/A":
        _require_number_range(
            provider_cost,
            Decimal("0"),
            None,
            path=f"{path}.operational.provider_cost",
        )
    elif type(provider_cost) is not str:
        raise ReportSchemaFixtureError(f"{path}.operational.provider_cost has invalid type")


def _validate_role_result(value: object, *, path: str) -> None:
    result = _require_object(value, path=path)
    _require_exact_keys(result, _ROLE_RESULT_KEYS, path=path)
    outcome = _require_string(result["outcome"], path=f"{path}.outcome")
    reason = _require_string(result["reason"], path=f"{path}.reason")
    tied = _require_list(result["tied_candidate_ids"], path=f"{path}.tied_candidate_ids")

    if outcome == "WINNER":
        candidate_id = _require_string(result["candidate_id"], path=f"{path}.candidate_id")
        if candidate_id not in _CANDIDATE_IDS:
            raise ReportSchemaFixtureError(f"{path}.candidate_id is not frozen")
        if reason not in {"UNIQUE_GATE_PASSING_WINNER", "TIE_BREAK_RESOLVED_WINNER"}:
            raise ReportSchemaFixtureError(f"{path}.reason is invalid for WINNER")
        if tied:
            raise ReportSchemaFixtureError(f"{path}.tied_candidate_ids must be empty for WINNER")
        return

    if outcome != "NO_SELECTION" or result["candidate_id"] is not None:
        raise ReportSchemaFixtureError(f"{path} is not one frozen role-result variant")
    if reason == "NO_ELIGIBLE_CANDIDATE":
        if tied:
            raise ReportSchemaFixtureError(
                f"{path}.tied_candidate_ids must be empty for NO_ELIGIBLE_CANDIDATE"
            )
        return
    if reason != "EXACT_TIE_AFTER_ALL_FROZEN_TIE_BREAKERS" or len(tied) < 2:
        raise ReportSchemaFixtureError(f"{path} is not one frozen NO_SELECTION variant")
    seen: set[str] = set()
    for index, candidate in enumerate(tied):
        candidate_id = _require_string(candidate, path=f"{path}.tied_candidate_ids[{index}]")
        if candidate_id not in _CANDIDATE_IDS or candidate_id in seen:
            raise ReportSchemaFixtureError(f"{path}.tied_candidate_ids must be unique frozen IDs")
        seen.add(candidate_id)


def _validate_top_level_negative_result(value: object, *, path: str) -> None:
    item = _require_object(value, path=path)
    _require_exact_keys(
        item,
        frozenset({"candidate_id", "category", "summary", "item_id"}),
        path=path,
    )
    candidate_id = _require_string(item["candidate_id"], path=f"{path}.candidate_id")
    if candidate_id not in _CANDIDATE_IDS:
        raise ReportSchemaFixtureError(f"{path}.candidate_id is not frozen")
    _validate_negative_fields(item, path=path)


def _validate_negative_fields(item: dict[str, object], *, path: str) -> None:
    category = _require_string(item["category"], path=f"{path}.category")
    if category not in _NEGATIVE_CATEGORIES:
        raise ReportSchemaFixtureError(f"{path}.category is not frozen")
    _require_nonempty_string(item["summary"], path=f"{path}.summary")
    if item["item_id"] is not None:
        _require_item_id(item["item_id"], path=f"{path}.item_id")


def _require_object(value: object, *, path: str) -> dict[str, object]:
    if type(value) is not dict:
        raise ReportSchemaFixtureError(f"{path} must be an exact object")
    return cast(dict[str, object], value)


def _require_list(value: object, *, path: str) -> list[object]:
    if type(value) is not list:
        raise ReportSchemaFixtureError(f"{path} must be an exact array")
    return cast(list[object], value)


def _require_exact_keys(value: dict[str, object], expected: frozenset[str], *, path: str) -> None:
    keys = frozenset(value)
    if keys != expected or any(type(key) is not str for key in value):
        raise ReportSchemaFixtureError(f"{path} must contain exactly the frozen keys")


def _require_string(value: object, *, path: str) -> str:
    if type(value) is not str:
        raise ReportSchemaFixtureError(f"{path} must be an exact string")
    return value


def _require_nonempty_string(value: object, *, path: str) -> str:
    text = _require_string(value, path=path)
    if not text:
        raise ReportSchemaFixtureError(f"{path} must be non-empty")
    return text


def _require_pattern_string(value: object, pattern: re.Pattern[str], *, path: str) -> str:
    text = _require_string(value, path=path)
    if pattern.fullmatch(text) is None:
        raise ReportSchemaFixtureError(f"{path} has invalid frozen format")
    return text


def _require_item_id(value: object, *, path: str) -> str:
    return _require_pattern_string(value, _ITEM_ID, path=path)


def _require_exact_int(value: object, expected: int, *, path: str) -> int:
    number = _require_int_range(value, expected, expected, path=path)
    return number


def _require_int_range(
    value: object,
    minimum: int,
    maximum: int | None,
    *,
    path: str,
) -> int:
    if type(value) is not int:
        raise ReportSchemaFixtureError(f"{path} must be an exact integer")
    number = value
    if number < minimum or (maximum is not None and number > maximum):
        raise ReportSchemaFixtureError(f"{path} is outside the frozen integer range")
    return number


def _require_number_range(
    value: object,
    minimum: Decimal,
    maximum: Decimal | None,
    *,
    path: str,
) -> Decimal:
    if type(value) is int:
        number = Decimal(value)
    elif type(value) is Decimal:
        number = value
    else:
        raise ReportSchemaFixtureError(
            f"{path} must be an exact int or Decimal normalized JSON number"
        )
    if not number.is_finite():
        raise ReportSchemaFixtureError(f"{path} must be finite")
    if number < minimum or (maximum is not None and number > maximum):
        raise ReportSchemaFixtureError(f"{path} is outside the frozen numeric range")
    return number
