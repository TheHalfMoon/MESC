"""Canonical semantic content identity for MESC Research Loop V1.

MRL canonical artifacts are content-addressed from validated semantic JSON bytes. The
artifact's own ``content_sha256`` is deliberately excluded from that preimage: callers
validate/build their semantic payload first, then derive the digest with this module.

This module is deterministic and side-effect free. It performs no filesystem, network,
model, dataset, inference, GPU, or training access.
"""

from __future__ import annotations

import hashlib
import math
from typing import cast

from medscale.reproducibility import canonical_json

__all__ = [
    "MrlContentIdentityError",
    "canonical_semantic_bytes",
    "derive_content_sha256",
]


class MrlContentIdentityError(ValueError):
    """Fail-closed semantic-preimage validation error."""


def canonical_semantic_bytes(payload: object) -> bytes:
    """Return deterministic UTF-8 bytes for one validated MRL semantic payload.

    The top-level payload must be an exact JSON object and must not contain its own
    ``content_sha256`` field. Nested objects may contain a field with that name when it
    is material semantic data about another referenced artifact.

    Only exact JSON value types are accepted. In particular, tuples, sets, bytes,
    mapping/list subclasses, non-string object keys, and non-finite floats are rejected
    rather than silently normalized into a different semantic representation.
    """
    if type(payload) is not dict:
        raise MrlContentIdentityError("semantic payload must be an exact JSON object")

    semantic = cast(dict[object, object], payload)
    if "content_sha256" in semantic:
        raise MrlContentIdentityError(
            "content_sha256 is derived identity and must be excluded from its semantic preimage"
        )

    _validate_json_value(semantic, path="$")
    return canonical_json(semantic).encode("utf-8")


def derive_content_sha256(payload: object) -> str:
    """Derive SHA-256 from canonical semantic bytes outside the payload preimage."""
    return hashlib.sha256(canonical_semantic_bytes(payload)).hexdigest()


def _validate_json_value(value: object, *, path: str) -> None:
    if value is None or type(value) in (bool, int, str):
        return

    if type(value) is float:
        if not math.isfinite(value):
            raise MrlContentIdentityError(f"{path} contains a non-finite float")
        return

    if type(value) is list:
        items = cast(list[object], value)
        for index, item in enumerate(items):
            _validate_json_value(item, path=f"{path}[{index}]")
        return

    if type(value) is dict:
        mapping = cast(dict[object, object], value)
        for key, item in mapping.items():
            if type(key) is not str:
                raise MrlContentIdentityError(f"{path} contains a non-string object key")
            _validate_json_value(item, path=f"{path}.{key}")
        return

    raise MrlContentIdentityError(
        f"{path} contains unsupported semantic value type {type(value).__name__!r}"
    )
