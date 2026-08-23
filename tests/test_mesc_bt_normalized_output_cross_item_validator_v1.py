"""Qualification for the Backbone Tournament cross-item evidence-reference validator."""

from __future__ import annotations

import pytest

from medscale.mesc._bt_normalized_output_parser_v1 import ExactJsonNumber
from medscale.mesc._bt_normalized_output_cross_item_validator_v1 import (
    CrossItemEvidenceError,
    validate_cross_item_evidence_refs,
)


_REQUIRED_FIELDS = (
    "answer_state",
    "answer",
    "evidence_refs",
    "uncertainty",
    "safety_action",
    "structured_output",
)
_ANSWER_STATES = (
    "ANSWER_SUPPORTED",
    "ANSWER_WITH_UNCERTAINTY",
    "REQUEST_MORE_INFORMATION",
    "VERIFY_EVIDENCE",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "ABSTAIN_CONFLICTED_EVIDENCE",
    "ESCALATE_SAFETY",
)


def _valid_output() -> dict[str, object]:
    return {
        "answer_state": "ANSWER_SUPPORTED",
        "answer": "Supported answer",
        "evidence_refs": ["EV-001", "EV-002"],
        "uncertainty": None,
        "safety_action": None,
        "structured_output": {
            "confidence": ExactJsonNumber("0.9500"),
            "nested": [True, None, "text"],
        },
    }


def _assert_cross_item_failure(
    value: dict[str, object],
    item_payload_ids: frozenset[str],
    expected_path: str,
) -> None:
    with pytest.raises(CrossItemEvidenceError) as captured:
        validate_cross_item_evidence_refs(value, item_payload_ids)
    assert captured.value.kind == "cross_item_violation"
    assert captured.value.path == expected_path


def test_valid_evidence_refs_passes() -> None:
    value = _valid_output()
    item_payload_ids = frozenset({"EV-001", "EV-002", "EV-003"})
    validate_cross_item_evidence_refs(value, item_payload_ids)


def test_empty_evidence_refs_is_valid() -> None:
    value = _valid_output()
    value["evidence_refs"] = []
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    validate_cross_item_evidence_refs(value, item_payload_ids)


def test_duplicate_evidence_refs_fails_closed() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", "EV-001"]
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs")


def test_evidence_refs_not_in_payload_fails_closed() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", "MISSING-EV"]
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs[1]")


def test_evidence_refs_wrong_type_fails_closed() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", 123]
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs[1]")


def test_evidence_refs_empty_string_fails_closed() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", ""]
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs[1]")


def test_evidence_refs_not_a_list_fails_closed() -> None:
    value = _valid_output()
    value["evidence_refs"] = "EV-001"
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs")


def test_cross_item_validation_defense_in_depth_for_non_string() -> None:
    # Even though schema validator should catch this first, we test defense-in-depth
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", ["nested"]]
    item_payload_ids = frozenset({"EV-001", "EV-002"})
    _assert_cross_item_failure(value, item_payload_ids, "$.evidence_refs[1]")


def test_cross_item_validation_preserves_order_independent() -> None:
    value = _valid_output()
    # Same evidence refs, different order
    value["evidence_refs"] = ["EV-002", "EV-001"]
    item_payload_ids = frozenset({"EV-001", "EV-002", "EV-003"})
    validate_cross_item_evidence_refs(value, item_payload_ids)
