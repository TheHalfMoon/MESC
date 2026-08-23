from __future__ import annotations

import hashlib

import pytest

from medscale.mesc._bt_normalized_output_parser_v1 import (
    MAX_RAW_OUTPUT_BYTES,
    NormalizedOutputParseError,
    parse_normalized_output_fixture,
)


def _assert_parse_failure(raw_output: bytes, expected_kind: str) -> None:
    with pytest.raises(NormalizedOutputParseError) as captured:
        parse_normalized_output_fixture(raw_output)
    assert captured.value.kind == expected_kind


def test_valid_object_is_normalized_to_compact_sorted_key_utf8() -> None:
    result = parse_normalized_output_fixture('{"z":2,"a":"é","nested":{"b":1,"a":true}}'.encode())

    expected = '{"a":"é","nested":{"a":true,"b":1},"z":2}'.encode()
    assert result.value == {"z": 2, "a": "é", "nested": {"b": 1, "a": True}}
    assert result.normalized_bytes == expected
    assert result.normalized_sha256 == hashlib.sha256(expected).hexdigest()
    assert b"\\u00e9" not in result.normalized_bytes
    assert not result.normalized_bytes.endswith(b"\n")


def test_leading_and_trailing_ascii_whitespace_are_allowed() -> None:
    result = parse_normalized_output_fixture(b" \t\r\n{\"b\":2,\"a\":1}\n\r\t ")
    assert result.normalized_bytes == b'{"a":1,"b":2}'


def test_exact_maximum_raw_output_size_is_allowed() -> None:
    raw_output = b" " * (MAX_RAW_OUTPUT_BYTES - 2) + b"{}"
    assert len(raw_output) == MAX_RAW_OUTPUT_BYTES
    assert parse_normalized_output_fixture(raw_output).normalized_bytes == b"{}"


def test_output_above_maximum_size_fails_closed() -> None:
    raw_output = b" " * (MAX_RAW_OUTPUT_BYTES - 1) + b"{}"
    assert len(raw_output) == MAX_RAW_OUTPUT_BYTES + 1
    _assert_parse_failure(raw_output, "oversize_output")


def test_input_requires_exact_builtin_bytes() -> None:
    class BytesSubclass(bytes):
        pass

    with pytest.raises(TypeError, match="exact built-in bytes"):
        parse_normalized_output_fixture(bytearray(b"{}"))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="exact built-in bytes"):
        parse_normalized_output_fixture(BytesSubclass(b"{}"))


def test_invalid_utf8_fails_closed() -> None:
    _assert_parse_failure(b'{"x":"\xff"}', "invalid_utf8")


@pytest.mark.parametrize(
    "raw_output",
    [
        b"```json\n{\"a\":1}\n```",
        b"```\n{\"a\":1}\n```",
        b'{"a":1}```',
    ],
)
def test_exterior_markdown_fences_are_rejected(raw_output: bytes) -> None:
    _assert_parse_failure(raw_output, "markdown_fence")


def test_backticks_inside_json_string_are_not_mistaken_for_markdown_fence() -> None:
    result = parse_normalized_output_fixture(b'{"text":"```"}')
    assert result.normalized_bytes == b'{"text":"```"}'


@pytest.mark.parametrize(
    "raw_output",
    [
        b"",
        b"   ",
        b"{'a':1}",
        b'{"a":1,}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b"\xc2\xa0{}",
    ],
)
def test_invalid_json_is_rejected_without_semantic_repair(raw_output: bytes) -> None:
    _assert_parse_failure(raw_output, "invalid_json")


@pytest.mark.parametrize(
    "raw_output",
    [
        b"[]",
        b"null",
        b'"text"',
        b"1",
        b"true",
    ],
)
def test_top_level_value_must_be_one_json_object(raw_output: bytes) -> None:
    _assert_parse_failure(raw_output, "invalid_json")


def test_duplicate_top_level_key_is_rejected() -> None:
    _assert_parse_failure(b'{"a":1,"a":2}', "duplicate_key")


def test_duplicate_nested_key_is_rejected() -> None:
    _assert_parse_failure(b'{"outer":{"x":1,"x":2}}', "duplicate_key")


@pytest.mark.parametrize(
    "raw_output",
    [
        b"{}{}",
        b"{} trailing",
        b"{}\xc2\xa0",
        b"{}\n[]",
    ],
)
def test_trailing_non_ascii_whitespace_or_content_is_rejected(raw_output: bytes) -> None:
    _assert_parse_failure(raw_output, "trailing_non_whitespace")


def test_parser_does_not_perform_normalized_schema_validation() -> None:
    result = parse_normalized_output_fixture(b'{"z":1}')
    assert result.value == {"z": 1}
    assert result.normalized_bytes == b'{"z":1}'


def test_schema_shaped_fixture_is_only_parsed_not_cross_item_validated() -> None:
    raw_output = (
        b'{"answer":null,"answer_state":"NOT_A_SCHEMA_ENUM","evidence_refs":["missing-id"],'
        b'"safety_action":null,"structured_output":null,"uncertainty":null}'
    )
    result = parse_normalized_output_fixture(raw_output)
    assert result.value["answer_state"] == "NOT_A_SCHEMA_ENUM"
    assert result.value["evidence_refs"] == ["missing-id"]


def test_large_exponent_that_cannot_be_normalized_as_finite_json_fails_closed() -> None:
    _assert_parse_failure(b'{"x":1e400}', "invalid_json")
