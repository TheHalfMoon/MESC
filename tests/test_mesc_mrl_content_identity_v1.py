"""MRL-0100 tests for canonical semantic content identity."""

from __future__ import annotations

import hashlib

import pytest

from medscale.mesc._mrl_content_identity_v1 import (
    MrlContentIdentityError,
    canonical_semantic_bytes,
    derive_content_sha256,
)


def test_canonical_semantic_bytes_are_byte_stable_across_key_order() -> None:
    left = {
        "version": "MRL-ARTIFACT-V1",
        "objective": "evidence fidelity",
        "limits": {"queries": 3, "tiers": [1, 2]},
        "label": "café",
    }
    right = {
        "label": "café",
        "limits": {"tiers": [1, 2], "queries": 3},
        "objective": "evidence fidelity",
        "version": "MRL-ARTIFACT-V1",
    }

    expected = (
        '{"label":"café","limits":{"queries":3,"tiers":[1,2]},'
        '"objective":"evidence fidelity","version":"MRL-ARTIFACT-V1"}'
    ).encode()
    assert canonical_semantic_bytes(left) == canonical_semantic_bytes(right) == expected


def test_content_sha256_is_derived_from_semantic_bytes() -> None:
    payload = {"artifact_type": "fixture", "value": 7}
    semantic_bytes = canonical_semantic_bytes(payload)

    assert derive_content_sha256(payload) == hashlib.sha256(semantic_bytes).hexdigest()
    assert "content_sha256" not in payload


def test_content_sha256_changes_when_material_semantics_change() -> None:
    first = {"artifact_type": "fixture", "value": 7}
    second = {"artifact_type": "fixture", "value": 8}

    assert derive_content_sha256(first) != derive_content_sha256(second)


def test_top_level_content_sha256_cannot_enter_its_own_preimage() -> None:
    payload = {
        "artifact_type": "fixture",
        "value": 7,
        "content_sha256": "0" * 64,
    }

    with pytest.raises(MrlContentIdentityError, match="excluded from its semantic preimage"):
        derive_content_sha256(payload)


def test_nested_referenced_content_sha256_remains_material_semantics() -> None:
    first = {
        "artifact_type": "fixture",
        "source": {"content_sha256": "a" * 64},
    }
    second = {
        "artifact_type": "fixture",
        "source": {"content_sha256": "b" * 64},
    }

    assert derive_content_sha256(first) != derive_content_sha256(second)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"bad": (1, 2)},
        {"bad": {1, 2}},
        {"bad": b"bytes"},
        {"bad": float("nan")},
        {"bad": float("inf")},
        {1: "non-string-key"},
    ],
)
def test_noncanonical_or_non_json_semantics_fail_closed(payload: object) -> None:
    with pytest.raises(MrlContentIdentityError):
        canonical_semantic_bytes(payload)


def test_semantic_serialization_does_not_mutate_input() -> None:
    payload = {"z": 1, "nested": {"b": 2, "a": 1}}
    original = {"z": 1, "nested": {"b": 2, "a": 1}}

    canonical_semantic_bytes(payload)

    assert payload == original
