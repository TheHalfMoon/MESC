"""Qualification for the Backbone Tournament cross-item evidence validator."""

from __future__ import annotations

import pytest

from medscale.mesc._bt_cross_item_evidence_validator_v1 import (
    CrossItemEvidenceValidationError,
    validate_cross_item_evidence_refs_fixture,
)


def _output(*evidence_refs: str) -> dict[str, object]:
    return {
        "answer_state": "ANSWER_SUPPORTED",
        "answer": "answer",
        "evidence_refs": list(evidence_refs),
        "uncertainty": None,
        "safety_action": None,
        "structured_output": None,
    }


def test_all_output_references_present_in_payload_ids_pass() -> None:
    validate_cross_item_evidence_refs_fixture(
        _output("EV-001", "EV-003"),
        ("EV-001", "EV-002", "EV-003"),
    )


def test_empty_output_reference_set_passes_even_when_payload_has_evidence() -> None:
    validate_cross_item_evidence_refs_fixture(_output(), ("EV-001", "EV-002"))


def test_empty_output_and_empty_payload_evidence_sets_pass() -> None:
    validate_cross_item_evidence_refs_fixture(_output(), ())


def test_payload_may_contain_unreferenced_ids() -> None:
    validate_cross_item_evidence_refs_fixture(
        _output("EV-001"),
        ("EV-001", "EV-002", "EV-003"),
    )


def test_payload_duplicate_ids_do_not_create_an_extra_cross_item_rule() -> None:
    validate_cross_item_evidence_refs_fixture(
        _output("EV-001"),
        ("EV-001", "EV-001"),
    )


def test_first_missing_reference_fails_with_frozen_cross_item_kind() -> None:
    with pytest.raises(CrossItemEvidenceValidationError) as captured:
        validate_cross_item_evidence_refs_fixture(
            _output("EV-001", "EV-MISSING"),
            ("EV-001", "EV-002"),
        )

    assert captured.value.kind == "cross_item_violation"
    assert captured.value.path == "$.evidence_refs[1]"
    assert captured.value.evidence_ref == "EV-MISSING"


def test_all_references_fail_when_payload_evidence_ids_are_empty() -> None:
    with pytest.raises(CrossItemEvidenceValidationError) as captured:
        validate_cross_item_evidence_refs_fixture(_output("EV-001"), ())

    assert captured.value.kind == "cross_item_violation"
    assert captured.value.path == "$.evidence_refs[0]"
    assert captured.value.evidence_ref == "EV-001"


def test_exact_string_membership_is_case_sensitive() -> None:
    with pytest.raises(CrossItemEvidenceValidationError):
        validate_cross_item_evidence_refs_fixture(_output("EV-001"), ("ev-001",))


def test_cross_item_stage_does_not_reimplement_normalized_schema_uniqueness() -> None:
    value = _output("EV-001", "EV-001")
    validate_cross_item_evidence_refs_fixture(value, ("EV-001",))


def test_cross_item_stage_ignores_unrelated_normalized_output_fields() -> None:
    value = _output("EV-001")
    value["answer_state"] = "NOT_A_SCHEMA_ENUM"
    value["unexpected"] = object()
    validate_cross_item_evidence_refs_fixture(value, ("EV-001",))


def test_normalized_output_requires_exact_dict() -> None:
    class DictSubclass(dict[str, object]):
        pass

    with pytest.raises(TypeError, match="exact built-in dict"):
        validate_cross_item_evidence_refs_fixture(DictSubclass(_output()), ())


def test_evidence_refs_shape_misuse_is_caller_error_not_cross_item_failure() -> None:
    value = _output("EV-001")
    value["evidence_refs"] = ("EV-001",)

    with pytest.raises(TypeError, match="exact built-in list"):
        validate_cross_item_evidence_refs_fixture(value, ("EV-001",))


def test_missing_evidence_refs_is_caller_error_not_cross_item_failure() -> None:
    value = _output("EV-001")
    del value["evidence_refs"]

    with pytest.raises(TypeError, match="must contain evidence_refs"):
        validate_cross_item_evidence_refs_fixture(value, ("EV-001",))


def test_output_reference_members_require_exact_strings() -> None:
    class StringSubclass(str):
        pass

    value = _output("EV-001")
    value["evidence_refs"] = [StringSubclass("EV-001")]

    with pytest.raises(TypeError, match="members must be exact strings"):
        validate_cross_item_evidence_refs_fixture(value, ("EV-001",))


def test_payload_ids_require_exact_tuple() -> None:
    with pytest.raises(TypeError, match="must be an exact tuple"):
        validate_cross_item_evidence_refs_fixture(
            _output("EV-001"),
            ["EV-001"],  # type: ignore[arg-type]
        )


def test_payload_id_members_require_exact_strings() -> None:
    class StringSubclass(str):
        pass

    with pytest.raises(TypeError, match="members must be exact strings"):
        validate_cross_item_evidence_refs_fixture(
            _output("EV-001"),
            (StringSubclass("EV-001"),),
        )


def test_validator_does_not_mutate_injected_inputs() -> None:
    value = _output("EV-001", "EV-002")
    payload_ids = ("EV-001", "EV-002", "EV-003")
    expected_value = {
        "answer_state": "ANSWER_SUPPORTED",
        "answer": "answer",
        "evidence_refs": ["EV-001", "EV-002"],
        "uncertainty": None,
        "safety_action": None,
        "structured_output": None,
    }

    validate_cross_item_evidence_refs_fixture(value, payload_ids)

    assert value == expected_value
    assert payload_ids == ("EV-001", "EV-002", "EV-003")
