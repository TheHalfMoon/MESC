"""Append-only governed procedure registry for MRL-0407.

The registry records trusted MRL-0406 admission outcomes and later invalidation or
supersession events without deleting the original admission evidence. A replacement
procedure cannot become authoritative through the registry: it must already have its own
independently admitted MRL-0406 result before another procedure can point to it as a
superseding procedure.

The registry is procedure-memory state only. It grants no model, data, network, GPU,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_admission_gate_v1 import (
    ProcedureAdmissionGateError,
    ProcedureAdmissionGateResult,
)
from medscale.mesc._mrl_research_procedure_v1 import ProcedureAdmissionDecision

__all__ = [
    "ProcedureRegistry",
    "ProcedureRegistryDisposition",
    "ProcedureRegistryError",
    "ProcedureRegistryEvent",
    "invalidate_admitted_procedure",
    "register_procedure_admission",
    "supersede_admitted_procedure",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)


class ProcedureRegistryError(ValueError):
    """Fail-closed validation error for governed procedure-registry history."""


class ProcedureRegistryDisposition(enum.Enum):
    """Closed current-state dispositions represented by append-only events."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"
    INVALIDATED = "INVALIDATED"


def _make_identity_registry() -> tuple[
    Callable[[object, str], None],
    Callable[[object, str], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: object, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureRegistryError("registry construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureRegistryError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureRegistryEvent:
    """One append-only disposition event bound to the exact MRL-0406 result."""

    sequence: int
    procedure_sha256: str
    disposition: ProcedureRegistryDisposition
    admission_result: ProcedureAdmissionGateResult
    evidence_sha256s: tuple[str, ...]
    reason: str
    replacement_procedure_sha256: str | None = None
    previous_event_sha256: str | None = None

    def __post_init__(self) -> None:
        _validate_event(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureRegistryEvent:
        if type(self) is not ProcedureRegistryEvent:
            raise ProcedureRegistryError("event must be an exact ProcedureRegistryEvent")
        bound = _load_identity(self, "procedure registry event")
        _require_sha256(bound, "bound event content_sha256")
        _validate_event(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureRegistryError("procedure registry event changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        result = _validated_gate_result(self.admission_result)
        admitted_procedure_sha256 = (
            None
            if result.admitted_procedure is None
            else result.admitted_procedure.content_sha256
        )
        admission_report_sha256 = (
            result.reviewed_report.content_sha256
            if result.admitted_report is None
            else result.admitted_report.content_sha256
        )
        return {
            "format": "MRL-PROCEDURE-REGISTRY-EVENT-V1",
            "sequence": self.sequence,
            "procedure_sha256": self.procedure_sha256,
            "disposition": self.disposition.value,
            "admission_gate_result_sha256": result.content_sha256,
            "admission_report_sha256": admission_report_sha256,
            "admitted_procedure_sha256": admitted_procedure_sha256,
            "evidence_sha256s": list(self.evidence_sha256s),
            "reason": self.reason,
            "replacement_procedure_sha256": self.replacement_procedure_sha256,
            "previous_event_sha256": self.previous_event_sha256,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureRegistry:
    """One immutable append-only registry snapshot."""

    events: tuple[ProcedureRegistryEvent, ...] = ()

    def __post_init__(self) -> None:
        _validate_registry(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureRegistry:
        if type(self) is not ProcedureRegistry:
            raise ProcedureRegistryError("registry must be an exact ProcedureRegistry")
        bound = _load_identity(self, "procedure registry")
        _require_sha256(bound, "bound registry content_sha256")
        _validate_registry(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureRegistryError("procedure registry changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-PROCEDURE-REGISTRY-V1",
            "events": [event._semantic_dict_validated() for event in self.events],
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data

    def current_event(self, procedure_sha256: str) -> ProcedureRegistryEvent:
        """Return the latest event for one known procedure subject."""
        snapshot = self._validated_snapshot()
        _require_sha256(procedure_sha256, "procedure_sha256")
        for event in reversed(snapshot.events):
            if event.procedure_sha256 == procedure_sha256:
                return event._validated_snapshot()
        raise ProcedureRegistryError("procedure is not present in the registry")

    @property
    def active_admitted_procedure_sha256s(self) -> tuple[str, ...]:
        """Return currently active admitted procedure-subject identities."""
        snapshot = self._validated_snapshot()
        latest = _latest_events(snapshot.events)
        return tuple(
            sorted(
                subject
                for subject, event in latest.items()
                if event.disposition is ProcedureRegistryDisposition.ADMITTED
            )
        )

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False


def register_procedure_admission(
    registry: ProcedureRegistry,
    admission_result: ProcedureAdmissionGateResult,
) -> ProcedureRegistry:
    """Append one first-time ADMITTED or REJECTED outcome from canonical MRL-0406."""
    snapshot = _validated_registry(registry)
    result = _validated_gate_result(admission_result)
    subject = result.procedure_sha256
    if any(event.procedure_sha256 == subject for event in snapshot.events):
        raise ProcedureRegistryError("procedure already has registry history")
    if result.decision is ProcedureAdmissionDecision.ADMIT:
        disposition = ProcedureRegistryDisposition.ADMITTED
        reason = "Registered independently admitted procedure evidence."
    elif result.decision is ProcedureAdmissionDecision.REJECT:
        disposition = ProcedureRegistryDisposition.REJECTED
        reason = "Registered independently reviewed procedure rejection evidence."
    else:
        raise ProcedureRegistryError("registry accepts only final ADMIT or REJECT gate results")
    return _append_event(
        snapshot,
        procedure_sha256=subject,
        disposition=disposition,
        admission_result=admission_result,
        evidence_sha256s=(),
        reason=reason,
        replacement_procedure_sha256=None,
    )


def invalidate_admitted_procedure(
    registry: ProcedureRegistry,
    procedure_sha256: str,
    *,
    evidence_sha256s: tuple[str, ...],
    reason: str,
) -> ProcedureRegistry:
    """Invalidate one active admitted procedure without deleting admission history."""
    snapshot = _validated_registry(registry)
    current = snapshot.current_event(procedure_sha256)
    if current.disposition is not ProcedureRegistryDisposition.ADMITTED:
        raise ProcedureRegistryError("only an active admitted procedure can be invalidated")
    _require_sorted_sha256s(evidence_sha256s, "evidence_sha256s", required=True)
    _require_text(reason, "reason")
    return _append_event(
        snapshot,
        procedure_sha256=procedure_sha256,
        disposition=ProcedureRegistryDisposition.INVALIDATED,
        admission_result=current.admission_result,
        evidence_sha256s=evidence_sha256s,
        reason=reason,
        replacement_procedure_sha256=None,
    )


def supersede_admitted_procedure(
    registry: ProcedureRegistry,
    procedure_sha256: str,
    *,
    replacement_procedure_sha256: str,
    evidence_sha256s: tuple[str, ...],
    reason: str,
) -> ProcedureRegistry:
    """Supersede an admitted procedure only with another independently admitted procedure."""
    snapshot = _validated_registry(registry)
    if procedure_sha256 == replacement_procedure_sha256:
        raise ProcedureRegistryError("procedure cannot supersede itself")
    current = snapshot.current_event(procedure_sha256)
    replacement = snapshot.current_event(replacement_procedure_sha256)
    if current.disposition is not ProcedureRegistryDisposition.ADMITTED:
        raise ProcedureRegistryError("only an active admitted procedure can be superseded")
    if replacement.disposition is not ProcedureRegistryDisposition.ADMITTED:
        raise ProcedureRegistryError(
            "replacement procedure must already be independently ADMITTED"
        )
    _require_sorted_sha256s(evidence_sha256s, "evidence_sha256s", required=True)
    _require_text(reason, "reason")
    return _append_event(
        snapshot,
        procedure_sha256=procedure_sha256,
        disposition=ProcedureRegistryDisposition.SUPERSEDED,
        admission_result=current.admission_result,
        evidence_sha256s=evidence_sha256s,
        reason=reason,
        replacement_procedure_sha256=replacement_procedure_sha256,
    )


def _append_event(
    registry: ProcedureRegistry,
    *,
    procedure_sha256: str,
    disposition: ProcedureRegistryDisposition,
    admission_result: ProcedureAdmissionGateResult,
    evidence_sha256s: tuple[str, ...],
    reason: str,
    replacement_procedure_sha256: str | None,
) -> ProcedureRegistry:
    previous = registry.events[-1].content_sha256 if registry.events else None
    event = ProcedureRegistryEvent(
        sequence=len(registry.events) + 1,
        procedure_sha256=procedure_sha256,
        disposition=disposition,
        admission_result=admission_result,
        evidence_sha256s=evidence_sha256s,
        reason=reason,
        replacement_procedure_sha256=replacement_procedure_sha256,
        previous_event_sha256=previous,
    )
    return ProcedureRegistry(events=registry.events + (event,))


def _validated_registry(registry: ProcedureRegistry) -> ProcedureRegistry:
    if type(registry) is not ProcedureRegistry:
        raise ProcedureRegistryError("registry must be an exact ProcedureRegistry")
    return registry._validated_snapshot()


def _validated_gate_result(
    result: ProcedureAdmissionGateResult,
) -> ProcedureAdmissionGateResult:
    if type(result) is not ProcedureAdmissionGateResult:
        raise ProcedureRegistryError(
            "admission_result must be an exact ProcedureAdmissionGateResult"
        )
    try:
        return result._validated_snapshot()
    except ProcedureAdmissionGateError as exc:
        raise ProcedureRegistryError(
            "procedure admission result failed canonical revalidation"
        ) from exc


def _validate_event(event: ProcedureRegistryEvent) -> None:
    if type(event.sequence) is not int or event.sequence < 1:
        raise ProcedureRegistryError("sequence must be an exact positive integer")
    _require_sha256(event.procedure_sha256, "procedure_sha256")
    if type(event.disposition) is not ProcedureRegistryDisposition:
        raise ProcedureRegistryError("disposition has an invalid type")
    result = _validated_gate_result(event.admission_result)
    if result.procedure_sha256 != event.procedure_sha256:
        raise ProcedureRegistryError("event does not bind its admission result procedure")
    _require_sorted_sha256s(event.evidence_sha256s, "evidence_sha256s", required=False)
    _require_text(event.reason, "reason")
    if event.previous_event_sha256 is not None:
        _require_sha256(event.previous_event_sha256, "previous_event_sha256")

    if event.disposition is ProcedureRegistryDisposition.ADMITTED:
        if result.decision is not ProcedureAdmissionDecision.ADMIT:
            raise ProcedureRegistryError("ADMITTED event requires an ADMIT gate result")
        if event.replacement_procedure_sha256 is not None:
            raise ProcedureRegistryError("ADMITTED event cannot name a replacement procedure")
        return
    if event.disposition is ProcedureRegistryDisposition.REJECTED:
        if result.decision is not ProcedureAdmissionDecision.REJECT:
            raise ProcedureRegistryError("REJECTED event requires a REJECT gate result")
        if event.replacement_procedure_sha256 is not None:
            raise ProcedureRegistryError("REJECTED event cannot name a replacement procedure")
        return

    if result.decision is not ProcedureAdmissionDecision.ADMIT:
        raise ProcedureRegistryError(
            "INVALIDATED/SUPERSEDED events require original ADMIT evidence"
        )
    if not event.evidence_sha256s:
        raise ProcedureRegistryError(
            "INVALIDATED/SUPERSEDED events require independent evidence"
        )
    if event.disposition is ProcedureRegistryDisposition.INVALIDATED:
        if event.replacement_procedure_sha256 is not None:
            raise ProcedureRegistryError("INVALIDATED event cannot name a replacement procedure")
        return
    if event.disposition is ProcedureRegistryDisposition.SUPERSEDED:
        if event.replacement_procedure_sha256 is None:
            raise ProcedureRegistryError("SUPERSEDED event requires a replacement procedure")
        _require_sha256(
            event.replacement_procedure_sha256,
            "replacement_procedure_sha256",
        )
        if event.replacement_procedure_sha256 == event.procedure_sha256:
            raise ProcedureRegistryError("procedure cannot supersede itself")
        return
    raise ProcedureRegistryError("unsupported procedure registry disposition")


def _validate_registry(registry: ProcedureRegistry) -> None:
    if type(registry.events) is not tuple:
        raise ProcedureRegistryError("events must be an exact tuple")
    latest: dict[str, ProcedureRegistryEvent] = {}
    first_result_sha256: dict[str, str] = {}
    previous_event_sha256: str | None = None

    for expected_sequence, event in enumerate(registry.events, start=1):
        if type(event) is not ProcedureRegistryEvent:
            raise ProcedureRegistryError("events contains an invalid item type")
        event._validated_snapshot()
        if event.sequence != expected_sequence:
            raise ProcedureRegistryError("registry event sequence must be contiguous")
        if event.previous_event_sha256 != previous_event_sha256:
            raise ProcedureRegistryError("registry event previous identity chain is invalid")

        subject = event.procedure_sha256
        current = latest.get(subject)
        result_sha256 = event.admission_result.content_sha256
        if current is None:
            if event.disposition not in (
                ProcedureRegistryDisposition.ADMITTED,
                ProcedureRegistryDisposition.REJECTED,
            ):
                raise ProcedureRegistryError(
                    "first procedure event must be ADMITTED or REJECTED"
                )
            first_result_sha256[subject] = result_sha256
        else:
            if current.disposition is not ProcedureRegistryDisposition.ADMITTED:
                raise ProcedureRegistryError(
                    "terminal procedure disposition cannot be rewritten"
                )
            if event.disposition not in (
                ProcedureRegistryDisposition.INVALIDATED,
                ProcedureRegistryDisposition.SUPERSEDED,
            ):
                raise ProcedureRegistryError(
                    "later procedure event must invalidate or supersede admission"
                )
            if first_result_sha256[subject] != result_sha256:
                raise ProcedureRegistryError(
                    "later disposition must preserve original admission evidence"
                )

        if event.disposition is ProcedureRegistryDisposition.SUPERSEDED:
            replacement_subject = event.replacement_procedure_sha256
            if replacement_subject is None:
                raise ProcedureRegistryError("supersession requires replacement identity")
            replacement = latest.get(replacement_subject)
            if (
                replacement is None
                or replacement.disposition is not ProcedureRegistryDisposition.ADMITTED
            ):
                raise ProcedureRegistryError(
                    "superseding procedure must already be independently admitted"
                )

        latest[subject] = event
        previous_event_sha256 = event.content_sha256


def _latest_events(
    events: tuple[ProcedureRegistryEvent, ...],
) -> dict[str, ProcedureRegistryEvent]:
    latest: dict[str, ProcedureRegistryEvent] = {}
    for event in events:
        latest[event.procedure_sha256] = event
    return latest


def _require_sorted_sha256s(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ProcedureRegistryError(f"{label} must be an exact tuple")
    if required and not values:
        raise ProcedureRegistryError(f"{label} cannot be empty")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise ProcedureRegistryError(f"{label} must be unique and strictly sorted")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureRegistryError(f"{label} must be 64 lowercase hex")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ProcedureRegistryError(f"{label} must be canonical non-empty text")
    if any(character in value for character in "\x00\r\n\t"):
        raise ProcedureRegistryError(f"{label} cannot contain control characters")
