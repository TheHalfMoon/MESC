"""Pure cross-item evidence-reference validation for Backbone Tournament fixtures.

This module implements only the membership rule frozen by ``MESC-BT-PARSER-V1``:
every normalized-output evidence reference must equal an evidence ID supplied for
the corresponding fixture item payload. It performs no corpus read, payload
extraction, scoring, model access, or execution operation.
"""

from __future__ import annotations

from typing import Final, Literal, cast

CrossItemFailureKind = Literal["cross_item_violation"]

PARSER_CONTRACT_VERSION: Final = "MESC-BT-PARSER-V1"
PARSER_CONTRACT_SHA256: Final = "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"


class CrossItemEvidenceValidationError(ValueError):
    """One frozen cross-item evidence-reference membership violation."""

    def __init__(self, path: str, evidence_ref: str) -> None:
        super().__init__(f"{path}: evidence reference is absent from item payload evidence IDs")
        self.kind: CrossItemFailureKind = "cross_item_violation"
        self.path = path
        self.evidence_ref = evidence_ref


def validate_cross_item_evidence_refs_fixture(
    normalized_output: dict[str, object],
    item_payload_evidence_ids: tuple[str, ...],
) -> None:
    """Validate injected output references against injected fixture payload IDs.

    This function deliberately assumes normalized-schema qualification occurred
    upstream. Caller-shape misuse is a fixture contract error, not a tournament
    ``cross_item_violation``. The function also does not prove that the injected
    evidence-ID tuple was produced from any real corpus payload.
    """
    evidence_refs = _snapshot_output_evidence_refs(normalized_output)
    payload_ids = _snapshot_payload_evidence_ids(item_payload_evidence_ids)
    available = frozenset(payload_ids)

    for index, evidence_ref in enumerate(evidence_refs):
        if evidence_ref not in available:
            raise CrossItemEvidenceValidationError(
                f"$.evidence_refs[{index}]",
                evidence_ref,
            )


def _snapshot_output_evidence_refs(normalized_output: dict[str, object]) -> tuple[str, ...]:
    if type(normalized_output) is not dict:
        raise TypeError("normalized_output must be an exact built-in dict")
    if "evidence_refs" not in normalized_output:
        raise TypeError("normalized_output must contain evidence_refs after schema validation")

    raw_refs = normalized_output["evidence_refs"]
    if type(raw_refs) is not list:
        raise TypeError("normalized_output evidence_refs must be an exact built-in list")

    refs = cast(list[object], raw_refs)
    snapshot: list[str] = []
    for evidence_ref in refs:
        if type(evidence_ref) is not str:
            raise TypeError("normalized_output evidence_refs members must be exact strings")
        snapshot.append(evidence_ref)
    return tuple(snapshot)


def _snapshot_payload_evidence_ids(
    item_payload_evidence_ids: tuple[str, ...],
) -> tuple[str, ...]:
    if type(item_payload_evidence_ids) is not tuple:
        raise TypeError("item_payload_evidence_ids must be an exact tuple")

    snapshot: list[str] = []
    for evidence_id in item_payload_evidence_ids:
        if type(evidence_id) is not str:
            raise TypeError("item_payload_evidence_ids members must be exact strings")
        snapshot.append(evidence_id)
    return tuple(snapshot)
