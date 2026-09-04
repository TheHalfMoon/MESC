"""Strict canonical JSON and JSONL serialization for P01-04B2A (FD-B2A-2, FD-B2A-3).

This private module is deliberately independent of the B1 serializer in
``medscale.mesc._split_v1``.  B1's ``canonical_json_bytes`` is a compatibility
byte contract: it emits no terminal LF and it admits finite floats, booleans
where integers are required, and coercible object keys.  B2A requires the exact
opposite on all four counts, and requires the terminal LF to be *inside* the
hashed bytes.  Delegating to B1 would silently violate the B2A contract while
still passing structural tests, so nothing here calls into B1.

Serializers accept caller-supplied objects, return ``bytes``, and perform no
filesystem I/O.  No runtime, host, locale, timezone, OS, interpreter, path,
username, timestamp, or environment value is ever read or emitted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import ClassVar, TypeAlias

#: The closed canonical value domain ratified by FD-B2A-2.
CanonicalJsonValue: TypeAlias = (
    "bool | int | str | Sequence[CanonicalJsonValue] | Mapping[str, CanonicalJsonValue] | None"
)

#: LF is the only permitted line terminator, and the only permitted terminator byte.
LINE_FEED = 0x0A


class CanonicalContractError(Exception):
    """Base class for every private B2A fail-closed contract failure.

    These are library-internal contract failures.  CLI exit-code semantics are
    deliberately not reused inside the library (FD-B2A-7).
    """

    #: Stable taxonomy code from the ratified contracts.
    code: ClassVar[str] = "canonical_contract_error"


class UnsupportedValueTypeError(CanonicalContractError):
    """A value outside the canonical domain, or a boolean where an integer is required."""

    code: ClassVar[str] = "unsupported_value_type"


class FloatingPointValueProhibitedError(CanonicalContractError):
    """A binary floating-point value, including NaN and the infinities."""

    code: ClassVar[str] = "floating_point_value_prohibited"


class NonStringObjectKeyError(CanonicalContractError):
    """An object key that is not a string."""

    code: ClassVar[str] = "non_string_object_key"


class CanonicalizationFailureError(CanonicalContractError):
    """A string that cannot be encoded as valid UTF-8, such as a lone surrogate."""

    code: ClassVar[str] = "canonicalization_failure"


def canonical_json_bytes(value: object) -> bytes:
    """Return the canonical UTF-8 bytes of one JSON value, with exactly one terminal LF.

    The terminal LF is part of the returned bytes and therefore part of every
    authoritative SHA-256 computed over them (FD-B2A-5).
    """
    normalized = _normalize(value)
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        indent=None,
        sort_keys=True,
    )
    return _encode_utf8(text) + bytes((LINE_FEED,))


def canonical_jsonl_bytes(records: Iterable[object]) -> bytes:
    """Return canonical JSONL bytes, preserving the caller's record order.

    Each record is canonicalized independently and already carries its own
    terminal LF, so every line — including the last — ends in exactly one LF and
    no blank line can appear.  Zero records produce exactly zero bytes.
    """
    chunks: list[bytes] = []
    for index, record in enumerate(records):
        if not isinstance(record, Mapping):
            raise UnsupportedValueTypeError(
                f"JSONL record {index} must be a string-keyed object, got {type(record).__name__}"
            )
        chunks.append(canonical_json_bytes(record))
    return b"".join(chunks)


def canonical_sha256(value: object) -> str:
    """Return the lowercase 64-hex SHA-256 over a value's canonical bytes."""
    return sha256_of_bytes(canonical_json_bytes(value))


def sha256_of_bytes(payload: bytes) -> str:
    """Return the lowercase 64-hex SHA-256 of exact bytes."""
    return hashlib.sha256(payload).hexdigest()


def _normalize(value: object) -> object:
    """Validate against the canonical domain and return a JSON-encodable mirror.

    Validation order is fixed so that a value violating several rules always
    fails with the same error:

    1. the current node's type, classified in the order
       null, boolean, integer, string, float, mapping, array, otherwise;
    2. inside a mapping, every key of the single snapshot is checked for exact
       ``str`` before any value is visited, and the reported offender is the
       lowest by ``repr`` so the outcome does not depend on insertion order;
    3. mapping entries are then visited in ascending canonical key order,
       never insertion order;
    4. array elements are visited in index order.

    Primitive classification uses **exact** types.  ``isinstance`` would admit
    ``IntEnum``, ``StrEnum`` and arbitrary ``int``/``str`` subclasses, which the
    closed canonical domain prohibits; an enum member must have its primitive
    value extracted explicitly by the caller rather than silently unwrapped
    here.  ``bool`` is still classified before ``int`` because Python makes
    ``bool`` a subclass of ``int`` and FD-B2A-2 forbids relying on that.
    """
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is str:
        _encode_utf8(value)
        return value
    if isinstance(value, float):
        raise FloatingPointValueProhibitedError(
            f"binary floating-point values are prohibited, got {value!r}"
        )
    if isinstance(value, Mapping):
        return _normalize_mapping(value)
    if isinstance(value, list | tuple):
        return [_normalize(item) for item in value]
    raise UnsupportedValueTypeError(f"unsupported value type: {type(value).__name__}")


def _normalize_mapping(mapping: Mapping[object, object]) -> dict[str, object]:
    """Normalize a mapping from one snapshot taken exactly once.

    The caller mapping is iterated a single time.  Every key of that snapshot is
    validated before any value is visited, so a mapping that mutates between
    iterations can never inject a key that was not validated, and no key is ever
    stringified into existence.
    """
    snapshot: list[tuple[object, object]] = list(mapping.items())
    invalid = sorted(repr(key) for key, _ in snapshot if type(key) is not str)
    if invalid:
        raise NonStringObjectKeyError(f"object keys must be strings, got {invalid[0]}")
    validated = [(_exact_string_key(key), value) for key, value in snapshot]
    for key, _ in validated:
        _encode_utf8(key)
    validated.sort(key=lambda item: item[0])
    return {key: _normalize(value) for key, value in validated}


def _exact_string_key(key: object) -> str:
    # ``isinstance`` narrows the type for the checker; ``type(...) is str``
    # enforces the contract by rejecting ``str`` subclasses and ``StrEnum``.
    if not isinstance(key, str) or type(key) is not str:  # pragma: no cover - snapshot pre-checked
        raise NonStringObjectKeyError(f"object keys must be strings, got {key!r}")
    return key


def _encode_utf8(text: str) -> bytes:
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as error:
        raise CanonicalizationFailureError("string is not encodable as valid UTF-8") from error
