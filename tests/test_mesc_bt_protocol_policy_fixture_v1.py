"""Fixture-only qualification for the frozen Backbone Tournament policy binder."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, cast

import pytest

from medscale.mesc._bt_protocol_policy_fixture_v1 import (
    FROZEN_PROTOCOL_CONFIG_SHA256,
    ProtocolPolicyBindingError,
    ProtocolPolicyCanonicalizationError,
    ProtocolPolicyDuplicateMemberError,
    ProtocolPolicyJsonError,
    ProtocolPolicySchemaError,
    verify_frozen_execution_policy,
)

_FROZEN_PROTOCOL_CONFIG_PATH: Final = Path(
    "specs/mesc-backbone-tournament/readiness-repair-2-result/protocol-config.json"
)


def _frozen_protocol_config() -> bytes:
    return _FROZEN_PROTOCOL_CONFIG_PATH.read_bytes()


def _mutated_payload(path: tuple[str, ...], value: object) -> bytes:
    document = cast(dict[str, object], json.loads(_frozen_protocol_config()))
    cursor = document
    for key in path[:-1]:
        cursor = cast(dict[str, object], cursor[key])
    cursor[path[-1]] = value
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def test_frozen_protocol_config_identity_is_exact() -> None:
    payload = _frozen_protocol_config()

    assert len(payload) == 2430
    assert hashlib.sha256(payload).hexdigest() == FROZEN_PROTOCOL_CONFIG_SHA256


def test_valid_frozen_policy_reconstructs_execution_controls() -> None:
    policy = verify_frozen_execution_policy(_frozen_protocol_config())

    assert policy.protocol_config_sha256 == FROZEN_PROTOCOL_CONFIG_SHA256
    assert policy.timeout_seconds == 180
    assert policy.infrastructure_retries == 1
    assert policy.parse_retries == 0
    assert policy.schema_retries == 0
    assert policy.semantic_retries == 0
    assert policy.maximum_generation_attempts_per_item == 2
    assert policy.input_tokens == 8192
    assert policy.output_tokens == 1024
    assert policy.single_turn is True
    assert policy.tools is False
    assert policy.retrieval is False
    assert policy.web is False
    assert policy.function_calls is False
    assert policy.candidate_specific_prompt_optimization == "PROHIBITED"
    assert policy.do_sample is False
    assert policy.seed == 0
    assert policy.temperature == 0.0
    assert policy.top_p == 1.0
    assert policy.top_k == "DISABLED_WHERE_SUPPORTED"
    assert policy.score_hidden_cot is False
    assert policy.gpt_oss_reasoning_effort == "medium_native_required_value"
    assert policy.error_classes == (
        "NONE",
        "TIMEOUT",
        "RUNTIME_FAILURE",
        "GENERATION_FAILURE",
        "PARSE_FAILURE",
        "SCHEMA_FAILURE",
        "SAFETY_FAILURE",
    )


def test_payload_must_be_exact_bytes() -> None:
    with pytest.raises(ProtocolPolicyJsonError, match="exact bytes"):
        verify_frozen_execution_policy(
            _frozen_protocol_config().decode("ascii")  # type: ignore[arg-type]
        )


def test_utf8_bom_is_rejected() -> None:
    with pytest.raises(ProtocolPolicyJsonError, match="BOM"):
        verify_frozen_execution_policy(b"\xef\xbb\xbf" + _frozen_protocol_config())


def test_duplicate_json_members_are_rejected() -> None:
    with pytest.raises(ProtocolPolicyDuplicateMemberError, match="version"):
        verify_frozen_execution_policy(b'{"version":"a","version":"b"}')


def test_nonstandard_json_constant_is_rejected() -> None:
    with pytest.raises(ProtocolPolicyJsonError, match="constant"):
        verify_frozen_execution_policy(b'{"version":NaN}')


def test_oversized_integer_json_failure_is_fail_closed() -> None:
    with pytest.raises(ProtocolPolicyJsonError, match="valid JSON"):
        verify_frozen_execution_policy(b"[" + b"9" * 5000 + b"]")


def test_deep_json_nesting_is_fail_closed() -> None:
    payload = b"[" * 20000 + b"]" * 20000

    with pytest.raises(ProtocolPolicyJsonError, match="valid JSON"):
        verify_frozen_execution_policy(payload)


def test_top_level_must_be_object() -> None:
    with pytest.raises(ProtocolPolicySchemaError, match="top level"):
        verify_frozen_execution_policy(b"[]")


@pytest.mark.parametrize("key", ["artifacts", "retry", "version"])
def test_top_level_key_set_is_closed(key: str) -> None:
    document = cast(dict[str, object], json.loads(_frozen_protocol_config()))
    del document[key]
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("ascii")

    with pytest.raises(ProtocolPolicySchemaError, match="key set"):
        verify_frozen_execution_policy(payload)


def test_extra_top_level_member_is_rejected() -> None:
    document = cast(dict[str, object], json.loads(_frozen_protocol_config()))
    document["extra"] = False
    payload = json.dumps(document, separators=(",", ":"), sort_keys=True).encode("ascii")

    with pytest.raises(ProtocolPolicySchemaError, match="key set"):
        verify_frozen_execution_policy(payload)


def test_noncanonical_serialization_is_rejected() -> None:
    with pytest.raises(ProtocolPolicyCanonicalizationError, match="canonical"):
        verify_frozen_execution_policy(_frozen_protocol_config() + b"\n")


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("retry", "timeout_seconds"), 181, "retry.timeout_seconds"),
        (("retry", "infrastructure_retries"), 0, "retry.infrastructure_retries"),
        (("retry", "parse_retries"), 1, "retry.parse_retries"),
        (("retry", "schema_retries"), 1, "retry.schema_retries"),
        (("retry", "semantic_retries"), 1, "retry.semantic_retries"),
        (("limits", "single_turn"), False, "limits.single_turn"),
        (("limits", "tools"), True, "limits.tools"),
        (("limits", "retrieval"), True, "limits.retrieval"),
        (("limits", "web"), True, "limits.web"),
        (("limits", "function_calls"), True, "limits.function_calls"),
        (
            ("limits", "candidate_specific_prompt_optimization"),
            "ALLOWED",
            "candidate_specific_prompt_optimization",
        ),
        (("decoding", "do_sample"), True, "decoding.do_sample"),
        (("decoding", "seed"), True, "decoding.seed"),
        (("decoding", "temperature"), 0.1, "decoding.temperature"),
        (("decoding", "top_p"), 0.9, "decoding.top_p"),
        (
            ("reasoning", "score_hidden_cot"),
            True,
            "reasoning.score_hidden_cot",
        ),
        (
            ("reasoning", "phi_optional_enhanced_reasoning"),
            True,
            "phi_optional_enhanced_reasoning",
        ),
        (("version",), "MESC-BT-PROTOCOL-V2", "version"),
    ],
)
def test_execution_policy_mutations_are_fail_closed(
    path: tuple[str, ...],
    value: object,
    match: str,
) -> None:
    with pytest.raises(ProtocolPolicySchemaError, match=match):
        verify_frozen_execution_policy(_mutated_payload(path, value))


def test_non_policy_artifact_mutation_fails_frozen_digest_binding() -> None:
    payload = _mutated_payload(("artifacts", "materialized_corpus_item_count"), 241)

    with pytest.raises(ProtocolPolicyBindingError, match="digest"):
        verify_frozen_execution_policy(payload)
