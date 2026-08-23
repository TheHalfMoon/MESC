"""Fail-closed fixture binding for the frozen Backbone Tournament policy.

This module validates caller-supplied bytes against the canonical
``MESC-BT-PROTOCOL-V1`` execution-policy contract. It performs no repository
reads, filesystem access, prompt serialization, model access, subprocess
execution, network access, provider calls, inference, ranking, or training.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final, Never, cast

FROZEN_PROTOCOL_CONFIG_SHA256: Final = (
    "097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203"
)
_UTF8_BOM: Final = b"\xef\xbb\xbf"
_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "artifacts",
        "decoding",
        "error_classes",
        "limits",
        "reasoning",
        "report_validation_contract_id",
        "retry",
        "scoring_contract_id",
        "terminal_exact_tie",
        "tie_breaker_metric_requirements",
        "tie_breakers",
        "version",
    }
)
_EXPECTED_POLICY: Final[dict[str, object]] = {
    "decoding": {
        "do_sample": False,
        "seed": 0,
        "temperature": 0.0,
        "top_k": "DISABLED_WHERE_SUPPORTED",
        "top_p": 1.0,
    },
    "error_classes": [
        "NONE",
        "TIMEOUT",
        "RUNTIME_FAILURE",
        "GENERATION_FAILURE",
        "PARSE_FAILURE",
        "SCHEMA_FAILURE",
        "SAFETY_FAILURE",
    ],
    "limits": {
        "candidate_specific_prompt_optimization": "PROHIBITED",
        "function_calls": False,
        "input_tokens": 8192,
        "output_tokens": 1024,
        "retrieval": False,
        "single_turn": True,
        "tools": False,
        "web": False,
    },
    "reasoning": {
        "apertus_optional_thinking": False,
        "gpt_oss_reasoning_effort": "medium_native_required_value",
        "medgemma_optional_enhanced_reasoning": False,
        "phi_optional_enhanced_reasoning": False,
        "score_hidden_cot": False,
    },
    "report_validation_contract_id": "MESC-BT-REPORT-VALIDATION-V1",
    "retry": {
        "infrastructure_retries": 1,
        "parse_retries": 0,
        "schema_retries": 0,
        "semantic_retries": 0,
        "timeout_seconds": 180,
    },
    "scoring_contract_id": "MESC-BT-SCORING-V1",
    "terminal_exact_tie": {
        "outcome": "NO_SELECTION",
        "reason": "EXACT_TIE_AFTER_ALL_FROZEN_TIE_BREAKERS",
    },
    "tie_breaker_metric_requirements": {
        "median_latency_ms": "REQUIRED_NON_NEGATIVE_NUMBER",
        "peak_vram_mb": (
            "REQUIRED_NON_NEGATIVE_NUMBER; NULL_OR_MISSING_IS_REPORT_VALIDATION_FAILURE"
        ),
    },
    "tie_breakers": [
        "higher_safety",
        "higher_evidence_fidelity",
        "higher_medical_reasoning",
        "lower_peak_vram_mb",
        "lower_median_latency_ms",
    ],
    "version": "MESC-BT-PROTOCOL-V1",
}


class ProtocolPolicyError(ValueError):
    """Base class for frozen protocol-policy verification failures."""


class ProtocolPolicyJsonError(ProtocolPolicyError):
    """The supplied bytes are not duplicate-safe UTF-8 JSON."""


class ProtocolPolicyDuplicateMemberError(ProtocolPolicyJsonError):
    """A JSON object contains a duplicate member name."""


class ProtocolPolicySchemaError(ProtocolPolicyError):
    """The parsed protocol document violates the closed policy contract."""


class ProtocolPolicyCanonicalizationError(ProtocolPolicyError):
    """The supplied bytes are not the canonical protocol-config bytes."""


class ProtocolPolicyBindingError(ProtocolPolicyError):
    """The supplied canonical bytes do not match the frozen protocol digest."""


@dataclass(frozen=True, slots=True)
class FrozenExecutionPolicy:
    """Execution controls reconstructed from the frozen canonical config."""

    protocol_config_sha256: str
    timeout_seconds: int
    infrastructure_retries: int
    parse_retries: int
    schema_retries: int
    semantic_retries: int
    input_tokens: int
    output_tokens: int
    single_turn: bool
    tools: bool
    retrieval: bool
    web: bool
    function_calls: bool
    candidate_specific_prompt_optimization: str
    do_sample: bool
    seed: int
    temperature: float
    top_p: float
    top_k: str
    score_hidden_cot: bool
    gpt_oss_reasoning_effort: str
    error_classes: tuple[str, ...]

    @property
    def maximum_generation_attempts_per_item(self) -> int:
        """Return the initial attempt plus the frozen infrastructure retry budget."""
        return 1 + self.infrastructure_retries


def verify_frozen_execution_policy(payload: bytes) -> FrozenExecutionPolicy:
    """Validate exact canonical protocol bytes and reconstruct execution controls."""
    if type(payload) is not bytes:
        raise ProtocolPolicyJsonError("payload must be exact bytes")
    if payload.startswith(_UTF8_BOM):
        raise ProtocolPolicyJsonError("UTF-8 BOM is prohibited")

    parsed = _load_duplicate_safe_json(payload)
    if type(parsed) is not dict:
        raise ProtocolPolicySchemaError("top level must be a JSON object")
    document = cast(dict[str, object], parsed)

    if frozenset(document) != _TOP_LEVEL_KEYS:
        raise ProtocolPolicySchemaError("protocol config top-level key set is not canonical")

    canonical = _canonical_protocol_config_bytes(document)
    if payload != canonical:
        raise ProtocolPolicyCanonicalizationError(
            "payload is not the exact canonical protocol-config serialization"
        )

    _validate_policy_values(document)

    digest = hashlib.sha256(payload).hexdigest()
    if digest != FROZEN_PROTOCOL_CONFIG_SHA256:
        raise ProtocolPolicyBindingError(
            "protocol config digest does not match the frozen MESC-BT-PROTOCOL-V1 identity"
        )

    return _build_policy(document, digest=digest)


def _validate_policy_values(document: dict[str, object]) -> None:
    for key, expected in _EXPECTED_POLICY.items():
        if key not in document:
            raise ProtocolPolicySchemaError(f"missing frozen policy member: {key}")
        _require_exact_json_value(document[key], expected, path=key)


def _require_exact_json_value(actual: object, expected: object, *, path: str) -> None:
    if type(actual) is not type(expected):
        raise ProtocolPolicySchemaError(f"{path} has wrong JSON scalar/container type")

    if type(expected) is dict:
        actual_map = cast(dict[str, object], actual)
        expected_map = cast(dict[str, object], expected)
        if frozenset(actual_map) != frozenset(expected_map):
            raise ProtocolPolicySchemaError(f"{path} has wrong member set")
        for key, nested_expected in expected_map.items():
            _require_exact_json_value(actual_map[key], nested_expected, path=f"{path}.{key}")
        return

    if type(expected) is list:
        actual_list = cast(list[object], actual)
        expected_list = cast(list[object], expected)
        if len(actual_list) != len(expected_list):
            raise ProtocolPolicySchemaError(f"{path} has wrong list length")
        for index, nested_expected in enumerate(expected_list):
            _require_exact_json_value(actual_list[index], nested_expected, path=f"{path}[{index}]")
        return

    if actual != expected:
        raise ProtocolPolicySchemaError(f"{path} does not match the frozen value")


def _build_policy(document: dict[str, object], *, digest: str) -> FrozenExecutionPolicy:
    decoding = cast(dict[str, object], document["decoding"])
    limits = cast(dict[str, object], document["limits"])
    reasoning = cast(dict[str, object], document["reasoning"])
    retry = cast(dict[str, object], document["retry"])
    error_classes = cast(list[str], document["error_classes"])

    return FrozenExecutionPolicy(
        protocol_config_sha256=digest,
        timeout_seconds=cast(int, retry["timeout_seconds"]),
        infrastructure_retries=cast(int, retry["infrastructure_retries"]),
        parse_retries=cast(int, retry["parse_retries"]),
        schema_retries=cast(int, retry["schema_retries"]),
        semantic_retries=cast(int, retry["semantic_retries"]),
        input_tokens=cast(int, limits["input_tokens"]),
        output_tokens=cast(int, limits["output_tokens"]),
        single_turn=cast(bool, limits["single_turn"]),
        tools=cast(bool, limits["tools"]),
        retrieval=cast(bool, limits["retrieval"]),
        web=cast(bool, limits["web"]),
        function_calls=cast(bool, limits["function_calls"]),
        candidate_specific_prompt_optimization=cast(
            str, limits["candidate_specific_prompt_optimization"]
        ),
        do_sample=cast(bool, decoding["do_sample"]),
        seed=cast(int, decoding["seed"]),
        temperature=cast(float, decoding["temperature"]),
        top_p=cast(float, decoding["top_p"]),
        top_k=cast(str, decoding["top_k"]),
        score_hidden_cot=cast(bool, reasoning["score_hidden_cot"]),
        gpt_oss_reasoning_effort=cast(str, reasoning["gpt_oss_reasoning_effort"]),
        error_classes=tuple(error_classes),
    )


def _canonical_protocol_config_bytes(document: dict[str, object]) -> bytes:
    try:
        text = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("ascii")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise ProtocolPolicyCanonicalizationError(
            "protocol config cannot be serialized as canonical ASCII JSON"
        ) from error


def _load_duplicate_safe_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ProtocolPolicyJsonError("payload must be valid UTF-8") from error

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_from_unique_pairs,
            parse_constant=_reject_json_constant,
        )
    except ProtocolPolicyJsonError:
        raise
    except (ValueError, RecursionError) as error:
        raise ProtocolPolicyJsonError("payload is not valid JSON") from error


def _object_from_unique_pairs(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise ProtocolPolicyDuplicateMemberError(f"duplicate JSON member: {key!r}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> Never:
    raise ProtocolPolicyJsonError(f"non-standard JSON constant is prohibited: {value}")
