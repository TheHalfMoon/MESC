"""Normative pure parser for Backbone Tournament normalized-output fixture bytes.

This module implements only the parsing/normalization behavior frozen by
``MESC-BT-PARSER-V1`` for caller-supplied bytes. It performs no filesystem,
network, provider, model, prompt, corpus, scoring, report-validation, ranking,
or execution operation.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Final, Literal, Never, cast

ParseFailureKind = Literal[
    "invalid_utf8",
    "oversize_output",
    "markdown_fence",
    "invalid_json",
    "duplicate_key",
    "trailing_non_whitespace",
]

PARSER_CONTRACT_VERSION: Final = "MESC-BT-PARSER-V1"
PARSER_CONTRACT_SHA256: Final = (
    "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"
)
NORMALIZED_OUTPUT_SCHEMA_ID: Final = "MESC-BT-NORMALIZED-OUTPUT-V1"
NORMALIZED_OUTPUT_SCHEMA_SHA256: Final = (
    "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
)
MAX_RAW_OUTPUT_BYTES: Final = 262_144
_ASCII_WHITESPACE: Final = frozenset({" ", "\t", "\r", "\n"})
_MARKDOWN_FENCE: Final = "```"


class NormalizedOutputParseError(ValueError):
    """One fail-closed parser failure with the frozen failure-mapping key."""

    def __init__(self, kind: ParseFailureKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class _DuplicateObjectKeyError(ValueError):
    """Internal signal emitted by the duplicate-safe JSON object hook."""


class _NonStandardJsonConstantError(ValueError):
    """Internal signal for NaN/Infinity spellings rejected by strict JSON."""


@dataclass(frozen=True, slots=True)
class NormalizedOutputParseResult:
    """Parsed object plus exact compact sorted-key UTF-8 normalization bytes."""

    value: dict[str, object]
    normalized_bytes: bytes
    normalized_sha256: str


def parse_normalized_output_fixture(raw_output: bytes) -> NormalizedOutputParseResult:
    """Parse one caller-supplied output under the frozen MESC-BT-PARSER-V1 rules.

    This function intentionally stops before normalized-schema and cross-item
    validation. Those are separate ``SCHEMA_FAILURE`` stages in the frozen
    contract and must not be silently collapsed into parsing.
    """
    if type(raw_output) is not bytes:
        raise TypeError("raw_output must be exact built-in bytes")
    if len(raw_output) > MAX_RAW_OUTPUT_BYTES:
        raise NormalizedOutputParseError(
            "oversize_output",
            f"raw output exceeds {MAX_RAW_OUTPUT_BYTES} bytes",
        )

    try:
        text = raw_output.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise NormalizedOutputParseError(
            "invalid_utf8",
            "raw output is not valid UTF-8",
        ) from error

    start_index = _skip_ascii_whitespace(text, 0)
    candidate = text[start_index:]
    fence_probe = candidate.rstrip(" \t\r\n")
    if candidate.startswith(_MARKDOWN_FENCE) or fence_probe.endswith(_MARKDOWN_FENCE):
        raise NormalizedOutputParseError(
            "markdown_fence",
            "Markdown fences are prohibited by MESC-BT-PARSER-V1",
        )

    decoder = json.JSONDecoder(
        object_pairs_hook=_reject_duplicate_object_keys,
        parse_constant=_reject_nonstandard_constant,
    )
    try:
        decoded, end_index = decoder.raw_decode(candidate)
    except _DuplicateObjectKeyError as error:
        raise NormalizedOutputParseError("duplicate_key", str(error)) from error
    except _NonStandardJsonConstantError as error:
        raise NormalizedOutputParseError("invalid_json", str(error)) from error
    except (ValueError, RecursionError, OverflowError) as error:
        raise NormalizedOutputParseError(
            "invalid_json",
            "raw output is not one valid JSON value",
        ) from error

    remainder = candidate[end_index:]
    if any(character not in _ASCII_WHITESPACE for character in remainder):
        raise NormalizedOutputParseError(
            "trailing_non_whitespace",
            "only ASCII whitespace may follow the single JSON object",
        )

    if type(decoded) is not dict:
        raise NormalizedOutputParseError(
            "invalid_json",
            "top-level output must be exactly one JSON object",
        )
    parsed = cast(dict[str, object], decoded)

    try:
        normalized_text = json.dumps(
            parsed,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        normalized_bytes = normalized_text.encode("utf-8", errors="strict")
    except (TypeError, ValueError, OverflowError, RecursionError) as error:
        raise NormalizedOutputParseError(
            "invalid_json",
            "parsed JSON cannot be normalized as canonical UTF-8 JSON",
        ) from error

    return NormalizedOutputParseResult(
        value=parsed,
        normalized_bytes=normalized_bytes,
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
    )


def _skip_ascii_whitespace(text: str, start: int) -> int:
    index = start
    while index < len(text) and text[index] in _ASCII_WHITESPACE:
        index += 1
    return index


def _reject_duplicate_object_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateObjectKeyError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> Never:
    raise _NonStandardJsonConstantError(f"non-standard JSON constant is prohibited: {value}")
