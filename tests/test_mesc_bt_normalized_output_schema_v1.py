"""Qualification for the Backbone Tournament normalized-output schema validator."""

from __future__ import annotations

import pytest

from medscale.mesc._bt_normalized_output_parser_v1 import ExactJsonNumber
from medscale.mesc._bt_normalized_output_schema_v1 import (
    NormalizedOutputSchemaError,
    validate_normalized_output_fixture,
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


def _assert_schema_failure(value: dict[str, object], expected_path: str) -> None:
    with pytest.raises(NormalizedOutputSchemaError) as captured:
        validate_normalized_output_fixture(value)
    assert captured.value.kind == "normalized_schema_violation"
    assert captured.value.path == expected_path


def test_valid_normalized_output_passes() -> None:
    validate_normalized_output_fixture(_valid_output())


@pytest.mark.parametrize("answer_state", _ANSWER_STATES)
def test_every_frozen_answer_state_passes(answer_state: str) -> None:
    value = _valid_output()
    value["answer_state"] = answer_state
    validate_normalized_output_fixture(value)


@pytest.mark.parametrize("field", _REQUIRED_FIELDS)
def test_missing_required_field_fails_closed(field: str) -> None:
    value = _valid_output()
    del value[field]
    _assert_schema_failure(value, "$")


def test_additional_property_fails_closed() -> None:
    value = _valid_output()
    value["unexpected"] = None
    _assert_schema_failure(value, "$")


def test_outer_object_requires_exact_builtin_dict() -> None:
    class DictSubclass(dict[str, object]):
        pass

    _assert_schema_failure(DictSubclass(_valid_output()), "$")


def test_object_keys_require_exact_builtin_strings() -> None:
    class StringSubclass(str):
        pass

    value = _valid_output()
    value[StringSubclass("unexpected")] = None
    _assert_schema_failure(value, "$")


@pytest.mark.parametrize("invalid_state", ["", "SUPPORTED", "answer_supported", None, 1])
def test_answer_state_must_be_exact_frozen_enum(invalid_state: object) -> None:
    value = _valid_output()
    value["answer_state"] = invalid_state
    _assert_schema_failure(value, "$.answer_state")


def test_answer_state_rejects_string_subclass() -> None:
    class StringSubclass(str):
        pass

    value = _valid_output()
    value["answer_state"] = StringSubclass("ANSWER_SUPPORTED")
    _assert_schema_failure(value, "$.answer_state")


@pytest.mark.parametrize("field", ["answer", "uncertainty", "safety_action"])
def test_nullable_string_fields_accept_string_and_null(field: str) -> None:
    value = _valid_output()
    value[field] = "text"
    validate_normalized_output_fixture(value)

    value[field] = None
    validate_normalized_output_fixture(value)


@pytest.mark.parametrize("field", ["answer", "uncertainty", "safety_action"])
@pytest.mark.parametrize("invalid_value", [1, True, [], {}])
def test_nullable_string_fields_reject_other_types(field: str, invalid_value: object) -> None:
    value = _valid_output()
    value[field] = invalid_value
    _assert_schema_failure(value, f"$.{field}")


def test_nullable_string_fields_reject_string_subclass() -> None:
    class StringSubclass(str):
        pass

    value = _valid_output()
    value["answer"] = StringSubclass("text")
    _assert_schema_failure(value, "$.answer")


def test_evidence_refs_require_exact_builtin_list() -> None:
    class ListSubclass(list[str]):
        pass

    value = _valid_output()
    value["evidence_refs"] = ("EV-001",)
    _assert_schema_failure(value, "$.evidence_refs")

    value["evidence_refs"] = ListSubclass(["EV-001"])
    _assert_schema_failure(value, "$.evidence_refs")


def test_evidence_refs_members_must_be_nonempty_exact_strings() -> None:
    class StringSubclass(str):
        pass

    value = _valid_output()
    value["evidence_refs"] = [""]
    _assert_schema_failure(value, "$.evidence_refs[0]")

    value["evidence_refs"] = [1]
    _assert_schema_failure(value, "$.evidence_refs[0]")

    value["evidence_refs"] = [StringSubclass("EV-001")]
    _assert_schema_failure(value, "$.evidence_refs[0]")


def test_evidence_refs_must_be_unique() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["EV-001", "EV-001"]
    _assert_schema_failure(value, "$.evidence_refs")


def test_empty_evidence_refs_array_is_schema_valid() -> None:
    value = _valid_output()
    value["evidence_refs"] = []
    validate_normalized_output_fixture(value)


def test_cross_item_evidence_membership_is_not_performed_by_this_stage() -> None:
    value = _valid_output()
    value["evidence_refs"] = ["NOT-PRESENT-IN-ANY-ITEM-PAYLOAD"]
    validate_normalized_output_fixture(value)


def test_structured_output_accepts_exact_object_or_null() -> None:
    value = _valid_output()
    value["structured_output"] = {"value": ExactJsonNumber("1e999999999999")}
    validate_normalized_output_fixture(value)

    value["structured_output"] = None
    validate_normalized_output_fixture(value)


@pytest.mark.parametrize("invalid_value", [[], "text", 1, True])
def test_structured_output_rejects_non_object_non_null(invalid_value: object) -> None:
    value = _valid_output()
    value["structured_output"] = invalid_value
    _assert_schema_failure(value, "$.structured_output")


def test_structured_output_rejects_dict_subclass() -> None:
    class DictSubclass(dict[str, object]):
        pass

    value = _valid_output()
    value["structured_output"] = DictSubclass({"value": "x"})
    _assert_schema_failure(value, "$.structured_output")
