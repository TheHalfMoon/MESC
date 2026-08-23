"""Pure normalized-output schema validation for Backbone Tournament fixtures.

This module implements only the constraints frozen by
``MESC-BT-NORMALIZED-OUTPUT-V1`` for caller-supplied parsed fixture objects. It
performs no filesystem, network, provider, model, prompt, corpus, scoring,
report-validation, ranking, or execution operation.
"""

from __future__ import annotations

from typing import Final, Literal

SchemaFailureKind = Literal["normalized_schema_violation"]

NORMALIZED_OUTPUT_SCHEMA_ID: Final = "MESC-BT-NORMALIZED-OUTPUT-V1"
NORMALIZED_OUTPUT_SCHEMA_SHA256: Final = (
    "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
)

_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "answer_state",
        "answer",
        "evidence_refs",
        "uncertainty",
        "safety_action",
        "structured_output",
    }
)
_ANSWER_STATES: Final[frozenset[str]] = frozenset(
    {
        "ANSWER_SUPPORTED",
        "ANSWER_WITH_UNCERTAINTY",
        "REQUEST_MORE_INFORMATION",
        "VERIFY_EVIDENCE",
        "ABSTAIN_INSUFFICIENT_EVIDENCE",
        "ABSTAIN_CONFLICTED_EVIDENCE",
        "ESCALATE_SAFETY",
    }
)


class NormalizedOutputSchemaError(ValueError):
    """One fail-closed normalized-schema violation."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.kind: SchemaFailureKind = "normalized_schema_violation"
        self.path = path


def validate_normalized_output_fixture(value: dict[str, object]) -> None:
    """Validate one parsed fixture object against the frozen normalized schema.

    Cross-item evidence-reference membership is intentionally excluded. The
    frozen parser contract classifies that as a separate cross-item validation
    step that also maps to ``SCHEMA_FAILURE``.
    """
    if type(value) is not dict:
        raise NormalizedOutputSchemaError("$", "instance must be an exact object")

    for key in value:
        if type(key) is not str:
            raise NormalizedOutputSchemaError("$", "object keys must be exact strings")

    fields = frozenset(value)
    if fields != _REQUIRED_FIELDS:
        missing = sorted(_REQUIRED_FIELDS - fields)
        extra = sorted(fields - _REQUIRED_FIELDS)
        raise NormalizedOutputSchemaError(
            "$",
            f"required/additional-properties mismatch; missing={missing!r}; extra={extra!r}",
        )

    answer_state = value["answer_state"]
    if type(answer_state) is not str:
        raise NormalizedOutputSchemaError("$.answer_state", "must be an exact string enum value")
    if answer_state not in _ANSWER_STATES:
        raise NormalizedOutputSchemaError("$.answer_state", "value is outside the frozen enum")

    _validate_nullable_string(value["answer"], "$.answer")
    _validate_evidence_refs(value["evidence_refs"])
    _validate_nullable_string(value["uncertainty"], "$.uncertainty")
    _validate_nullable_string(value["safety_action"], "$.safety_action")

    structured_output = value["structured_output"]
    if structured_output is not None and type(structured_output) is not dict:
        raise NormalizedOutputSchemaError(
            "$.structured_output",
            "must be an exact object or null",
        )


def _validate_nullable_string(value: object, path: str) -> None:
    if value is not None and type(value) is not str:
        raise NormalizedOutputSchemaError(path, "must be an exact string or null")


def _validate_evidence_refs(value: object) -> None:
    if type(value) is not list:
        raise NormalizedOutputSchemaError("$.evidence_refs", "must be an exact array")

    seen: set[str] = set()
    for index, evidence_ref in enumerate(value):
        path = f"$.evidence_refs[{index}]"
        if type(evidence_ref) is not str:
            raise NormalizedOutputSchemaError(path, "must be an exact string")
        if len(evidence_ref) < 1:
            raise NormalizedOutputSchemaError(path, "must have minimum length 1")
        if evidence_ref in seen:
            raise NormalizedOutputSchemaError("$.evidence_refs", "items must be unique")
        seen.add(evidence_ref)
