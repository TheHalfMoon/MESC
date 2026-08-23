"""Pure cross-item evidence-reference validation for Backbone Tournament fixtures.

This module implements only the cross-item evidence-reference validation frozen by
the parser contract for caller-supplied parsed fixture objects and item payload IDs.
It performs no filesystem, network, provider, model, prompt, corpus, scoring,
report-validation, ranking, or execution operation.
"""

from __future__ import annotations

from typing import Final, Literal

CrossItemFailureKind = Literal["cross_item_violation"]

NORMALIZED_OUTPUT_SCHEMA_ID: Final = "MESC-BT-NORMALIZED-OUTPUT-V1"
NORMALIZED_OUTPUT_SCHEMA_SHA256: Final = (
    "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
)


class CrossItemEvidenceError(ValueError):
    """One fail-closed cross-item evidence-reference violation."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.kind: CrossItemFailureKind = "cross_item_violation"
        self.path = path


def validate_cross_item_evidence_refs(
    value: dict[str, object],
    item_payload_ids: frozenset[str],
) -> None:
    """Validate that every evidence_refs value equals an evidence ID present in item payload.

    This function assumes that normalized-schema validation has already passed,
    so ``value`` is guaranteed to have the correct structure and types.
    """
    evidence_refs = value["evidence_refs"]
    # Type and basic validity already checked by schema validator
    # but we re-check for defense-in-depth and clear error paths
    if type(evidence_refs) is not list:
        raise CrossItemEvidenceError("$.evidence_refs", "must be an exact array")

    seen: set[str] = set()
    for index, evidence_ref in enumerate(evidence_refs):
        path = f"$.evidence_refs[{index}]"
        if type(evidence_ref) is not str:
            raise CrossItemEvidenceError(path, "must be an exact string")
        if len(evidence_ref) < 1:
            raise CrossItemEvidenceError(path, "must have minimum length 1")
        if evidence_ref in seen:
            raise CrossItemEvidenceError("$.evidence_refs", "items must be unique")
        if evidence_ref not in item_payload_ids:
            raise CrossItemEvidenceError(
                path, "must equal an evidence ID present in item payload"
            )
        seen.add(evidence_ref)
