"""Mechanical no-backflow and data-classification guard for CW-004.

Acceptance contract (Issue #474, canonical ledger):

* direct W -> R write/copy/import paths fail;
* X -> R automatic admission fails;
* Workspace telemetry cannot become Research Core data;
* de-identified export remains Domain X;
* tests cover file/API/object-level bypass attempts;
* guard failure is fail-closed.

How that is made mechanical rather than conventional:

* every decision is taken against one declared table of trust-domain edges, and
  every edge that the planning package does not declare is refused rather than
  permitted by omission;
* Domain R is not a reachable destination for *any* source, so no classification,
  no relabelling and no serialization trick can open it;
* the secret class is refused everywhere, including inside Domain W, because key
  material is not a payload, log or prompt class at all;
* classification is derived from the data class by the canonical table, so a
  caller can never assert the domain it wants;
* the export path check is pure path algebra over caller-supplied absolute paths.

Recorded limitation of this unit, deliberately visible: the Workspace package has
no filesystem capability at all (no ``os``, no ``pathlib`` and no ``open``; the
boundary guard forbids them). The file-level rule is therefore a lexical
containment proof over declared absolute roots and it does not resolve symlinks,
junctions or reparse points, because resolving them would require exactly the
capability this package is denied. Link-based escape is recorded as a limitation
owned by the first later unit that obtains a filesystem capability, and by the
independent security lane at CW-019. Likewise no path is created, read or written
here: this module decides, it does not perform I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from uuid import UUID

from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import (
    DERIVED_DOMAIN_SOURCE,
    OPERATIONAL_DATA_CLASSES,
    DataClass,
    DataClassification,
    TrustDomain,
    classification_from_document,
)
from medscale_workspace.errors import (
    BackflowError,
    DataClassificationError,
    ExplicitExportRequestError,
    ExportAdmissionError,
    ExportBoundaryError,
    ResearchBackflowError,
    SecretEgressError,
    TelemetryBackflowError,
    UnavailableAuthorityError,
    UndeclaredFlowError,
    WorkspaceAdmissionError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import content_digest_of

SAME_DOMAIN_RULE_ID = "same-domain-operation"
RESEARCH_DESTINATION_RULE_IDS = {
    TrustDomain.WORKSPACE: "workspace-to-research-core-forbidden",
    TrustDomain.EXPORT_QUARANTINE: "export-quarantine-to-research-core-forbidden",
    TrustDomain.EXTERNAL_CONNECTOR: "external-connector-to-research-core-forbidden",
    TrustDomain.PLUGIN_RUNTIME: "plugin-runtime-to-research-core-forbidden",
    TrustDomain.RESEARCH_CORE: "workspace-write-to-research-core-forbidden",
}
TELEMETRY_DESTINATION_RULE_ID = "workspace-operational-data-to-research-core-forbidden"
SECRET_EGRESS_RULE_ID = "secret-class-flow-forbidden"
UNDECLARED_FLOW_RULE_ID = "undeclared-domain-flow-forbidden"

RESEARCH_DESTINATION_AUTHORITY = (
    "Admitting data into Domain R is not available to the Workspace package at all: "
    "Research Core capabilities flow to the Workspace only as versioned interfaces, and "
    "any later research admission is separately governed (RESEARCH_ADMISSION_FROM_WORKSPACE "
    "= NOT_AUTHORIZED)"
)
SECRET_EGRESS_AUTHORITY = (
    "Key material and connector tokens live in declared platform secret storage, never in "
    "Workspace payloads, logs, diagnostics, prompts or exports"
)


class FlowDisposition(StrEnum):
    """How a declared trust-domain edge is dispositioned in this unit."""

    ADMITTED = "ADMITTED"
    FORBIDDEN = "FORBIDDEN"
    AUTHORITY_NOT_GRANTED = "AUTHORITY_NOT_GRANTED"


@dataclass(frozen=True, slots=True)
class DomainFlow:
    """One declared trust-domain edge, its authority and its refusal class."""

    rule_id: str
    source: TrustDomain
    destination: TrustDomain
    disposition: FlowDisposition
    authority: str
    refusal: type[BackflowError]
    explicit_user_request_required: bool = False


DOMAIN_FLOWS: tuple[DomainFlow, ...] = (
    DomainFlow(
        rule_id="research-core-to-workspace-versioned-interface",
        source=TrustDomain.RESEARCH_CORE,
        destination=TrustDomain.WORKSPACE,
        disposition=FlowDisposition.ADMITTED,
        authority=(
            "the only declared direction: versioned schemas, validators, evidence "
            "primitives and released artifacts"
        ),
        refusal=UndeclaredFlowError,
    ),
    DomainFlow(
        rule_id="workspace-to-export-quarantine-explicit-export",
        source=TrustDomain.WORKSPACE,
        destination=TrustDomain.EXPORT_QUARANTINE,
        disposition=FlowDisposition.ADMITTED,
        authority="an explicit user export request; the result is Domain X, never Domain R",
        refusal=ExplicitExportRequestError,
        explicit_user_request_required=True,
    ),
    DomainFlow(
        rule_id="export-quarantine-to-workspace-forbidden",
        source=TrustDomain.EXPORT_QUARANTINE,
        destination=TrustDomain.WORKSPACE,
        disposition=FlowDisposition.FORBIDDEN,
        authority=(
            "the declared data-flow rules allow W -> X and declare no X -> W edge; a "
            "quarantined export is never re-admitted as Workspace clinical state"
        ),
        refusal=WorkspaceAdmissionError,
    ),
    DomainFlow(
        rule_id="external-connector-to-workspace-connector-policy",
        source=TrustDomain.EXTERNAL_CONNECTOR,
        destination=TrustDomain.WORKSPACE,
        disposition=FlowDisposition.AUTHORITY_NOT_GRANTED,
        authority=(
            "an explicitly configured connector policy and least-privilege capability "
            "manifest; CW-014 owns that authority and CW-004 does not hold it"
        ),
        refusal=UnavailableAuthorityError,
    ),
    DomainFlow(
        rule_id="workspace-to-external-connector-write-authority",
        source=TrustDomain.WORKSPACE,
        destination=TrustDomain.EXTERNAL_CONNECTOR,
        disposition=FlowDisposition.AUTHORITY_NOT_GRANTED,
        authority=(
            "separate external write authority; EHR_WRITE, remote model egress and the "
            "network core path are all NOT_AUTHORIZED"
        ),
        refusal=UnavailableAuthorityError,
    ),
    DomainFlow(
        rule_id="plugin-runtime-to-workspace-capability-scoped",
        source=TrustDomain.PLUGIN_RUNTIME,
        destination=TrustDomain.WORKSPACE,
        disposition=FlowDisposition.AUTHORITY_NOT_GRANTED,
        authority=(
            "capability-scoped plugin/model runtime authority; no model execution "
            "authority exists in the Clinical Workspace program yet"
        ),
        refusal=UnavailableAuthorityError,
    ),
    DomainFlow(
        rule_id="workspace-to-plugin-runtime-capability-scoped",
        source=TrustDomain.WORKSPACE,
        destination=TrustDomain.PLUGIN_RUNTIME,
        disposition=FlowDisposition.AUTHORITY_NOT_GRANTED,
        authority=(
            "capability-scoped plugin/model runtime authority; no model execution "
            "authority exists in the Clinical Workspace program yet"
        ),
        refusal=UnavailableAuthorityError,
    ),
)

_DECLARED_FLOWS = {(flow.source, flow.destination): flow for flow in DOMAIN_FLOWS}


def validate_flow_table() -> None:
    """Fail closed unless the declared flow table is unambiguous and cannot reach Domain R."""

    if len(DOMAIN_FLOWS) != len(_DECLARED_FLOWS):
        raise DataClassificationError("the declared flow table contains a duplicate edge")
    missing_rule_ids = sorted(
        domain.value for domain in TrustDomain if domain not in RESEARCH_DESTINATION_RULE_IDS
    )
    if missing_rule_ids:
        raise DataClassificationError(
            "every trust domain needs a canonical Domain R refusal rule id: "
            + ", ".join(missing_rule_ids)
        )
    for flow in DOMAIN_FLOWS:
        if flow.destination is TrustDomain.RESEARCH_CORE:
            raise DataClassificationError(
                "Domain R must not appear as a declared destination edge; it is refused "
                "unconditionally for every source"
            )
        if flow.source is flow.destination:
            raise DataClassificationError(
                "the declared flow table must not encode same-domain operations as edges"
            )


validate_flow_table()


def _require_classification(raw: object) -> DataClassification:
    if not isinstance(raw, DataClassification):
        raise DataClassificationError(
            "a flow decision requires a validated DataClassification instance; a raw "
            "string or a duck-typed object is refused so no caller can assert a domain"
        )
    return raw.validated()


def _require_domain_member(raw: object) -> TrustDomain:
    if not isinstance(raw, TrustDomain):
        raise DataClassificationError(
            "a destination must be an admitted TrustDomain member; a raw string is "
            "refused here so a mistyped destination cannot be interpreted"
        )
    return raw


@dataclass(frozen=True, slots=True)
class FlowDecision:
    """An admitted trust-domain flow."""

    source: DataClassification
    destination: TrustDomain
    rule_id: str
    authority: str

    def __post_init__(self) -> None:
        # Fail closed at construction: an "admitted" decision can never be forged for
        # Domain R, and it can never be built from an unvalidated classification.
        if not isinstance(self.source, DataClassification):
            raise DataClassificationError(
                "an admitted decision requires a validated DataClassification instance"
            )
        self.source.validated()
        if not isinstance(self.destination, TrustDomain):
            raise DataClassificationError(
                "an admitted decision requires an admitted TrustDomain member"
            )
        if self.destination is TrustDomain.RESEARCH_CORE:
            raise ResearchBackflowError(
                "an admitted decision can never name Domain R as its destination"
            )
        if not isinstance(self.rule_id, str) or not self.rule_id:
            raise DataClassificationError("an admitted decision requires a rule id")

    def to_document(self) -> dict[str, object]:
        """Return the admitted decision as metadata carrying no payload."""

        return {
            "authority": self.authority,
            "decision": "ADMITTED",
            "destination_domain": self.destination.value,
            "rule_id": self.rule_id,
            "source_domain": self.source.domain.value,
            "source_domain_source": DERIVED_DOMAIN_SOURCE,
        }


@dataclass(frozen=True, slots=True)
class FlowEvaluation:
    """The outcome of evaluating one flow, admitted or refused."""

    source: DataClassification
    destination: TrustDomain
    admitted: bool
    rule_id: str
    authority: str
    reason: str
    explicit_user_request: bool
    refusal: type[BackflowError] | None = None
    object_ref: ClassifiedObject | None = None

    def __post_init__(self) -> None:
        # An evaluation is either a real admission or a real refusal. Without this
        # invariant a hand-built ``admitted=False`` value with no refusal class would
        # pass :meth:`require`, which is exactly the fail-open shape this guard exists
        # to prevent.
        if not isinstance(self.source, DataClassification):
            raise DataClassificationError(
                "a flow evaluation requires a validated DataClassification instance"
            )
        if not isinstance(self.destination, TrustDomain):
            raise DataClassificationError(
                "a flow evaluation requires an admitted TrustDomain member"
            )
        if not isinstance(self.admitted, bool):
            raise DataClassificationError("a flow evaluation requires a boolean outcome")
        if self.admitted:
            if self.refusal is not None:
                raise DataClassificationError(
                    "an admitted evaluation must not carry a refusal class"
                )
            if self.destination is TrustDomain.RESEARCH_CORE:
                raise DataClassificationError(
                    "an admitted evaluation can never name Domain R as its destination"
                )
        else:
            if not isinstance(self.refusal, type) or not issubclass(self.refusal, BackflowError):
                raise DataClassificationError(
                    "a refused evaluation must name a BackflowError refusal class"
                )

    def require(self) -> FlowDecision:
        """Return the admitted decision, or raise the refusal this evaluation names."""

        if self.admitted:
            return FlowDecision(
                source=self.source,
                destination=self.destination,
                rule_id=self.rule_id,
                authority=self.authority,
            )
        refusal = self.refusal
        if refusal is None:
            # Not reachable through __post_init__, which requires a refusal class for a
            # refused evaluation; kept explicit so the outcome is still a refusal.
            raise UndeclaredFlowError("the flow was refused without a declared refusal class")
        raise refusal(self.reason)

    def refusal_document(self) -> dict[str, object]:
        """Return refusal provenance: rule, domains and object identity, never payload.

        This record is produced from the same declared table that produced the
        refusal, so a refused flow still leaves auditable provenance without any
        Workspace payload content entering a Research Core path.
        """

        document: dict[str, object] = {
            "authority": self.authority,
            "decision": "ADMITTED" if self.admitted else "REFUSED",
            "destination_domain": self.destination.value,
            "explicit_user_request": self.explicit_user_request,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "source_classification": self.source.to_document(),
            "source_domain": self.source.domain.value,
            "source_domain_source": DERIVED_DOMAIN_SOURCE,
        }
        if self.refusal is not None:
            document["refusal_error"] = self.refusal.__name__
        if self.object_ref is not None:
            document["object"] = self.object_ref.identity_document()
        return document


def _admitted(
    source: DataClassification,
    destination: TrustDomain,
    *,
    rule_id: str,
    authority: str,
    explicit_user_request: bool,
) -> FlowEvaluation:
    return FlowEvaluation(
        source=source,
        destination=destination,
        admitted=True,
        rule_id=rule_id,
        authority=authority,
        reason="the declared flow is admitted",
        explicit_user_request=explicit_user_request,
    )


def _refused(
    source: DataClassification,
    destination: TrustDomain,
    *,
    rule_id: str,
    refusal: type[BackflowError],
    authority: str,
    reason: str,
    explicit_user_request: bool,
) -> FlowEvaluation:
    return FlowEvaluation(
        source=source,
        destination=destination,
        admitted=False,
        rule_id=rule_id,
        authority=authority,
        reason=reason,
        explicit_user_request=explicit_user_request,
        refusal=refusal,
    )


def _research_destination_refusal(source: DataClassification) -> type[BackflowError]:
    if source.data_class in OPERATIONAL_DATA_CLASSES:
        return TelemetryBackflowError
    if source.domain is TrustDomain.EXPORT_QUARANTINE:
        return ExportAdmissionError
    return ResearchBackflowError


def evaluate_flow(
    classification: DataClassification,
    destination: TrustDomain,
    *,
    explicit_user_request: bool = False,
) -> FlowEvaluation:
    """Evaluate one trust-domain flow against the declared table, failing closed."""

    source = _require_classification(classification)
    target = _require_domain_member(destination)
    if not isinstance(explicit_user_request, bool):
        raise DataClassificationError("the explicit export request flag must be a boolean")

    if source.data_class is DataClass.SECRET:
        return _refused(
            source,
            target,
            rule_id=SECRET_EGRESS_RULE_ID,
            refusal=SecretEgressError,
            authority=SECRET_EGRESS_AUTHORITY,
            reason=(
                "secret-class material is refused even inside Domain W: it is not a "
                "payload, log, diagnostic, prompt or export class"
            ),
            explicit_user_request=explicit_user_request,
        )

    if target is TrustDomain.RESEARCH_CORE:
        if source.data_class in OPERATIONAL_DATA_CLASSES:
            return _refused(
                source,
                target,
                rule_id=TELEMETRY_DESTINATION_RULE_ID,
                refusal=TelemetryBackflowError,
                authority=RESEARCH_DESTINATION_AUTHORITY,
                reason=(
                    "Workspace operational telemetry, analytics and logs are not "
                    "evidence, not an MRL result and not a research corpus"
                ),
                explicit_user_request=explicit_user_request,
            )
        return _refused(
            source,
            target,
            rule_id=RESEARCH_DESTINATION_RULE_IDS[source.domain],
            refusal=_research_destination_refusal(source),
            authority=RESEARCH_DESTINATION_AUTHORITY,
            reason=(
                "Domain R is not a reachable destination from the Workspace package, so "
                "no write, copy, import or automatic admission into Research Core exists"
            ),
            explicit_user_request=explicit_user_request,
        )

    if source.domain is target:
        return _admitted(
            source,
            target,
            rule_id=SAME_DOMAIN_RULE_ID,
            authority="an operation that does not cross a trust-domain boundary",
            explicit_user_request=explicit_user_request,
        )

    declared = _DECLARED_FLOWS.get((source.domain, target))
    if declared is None:
        return _refused(
            source,
            target,
            rule_id=UNDECLARED_FLOW_RULE_ID,
            refusal=UndeclaredFlowError,
            authority=(
                "only the flows declared by the canonically effective planning package "
                "exist; an undeclared edge is refused rather than permitted by omission"
            ),
            reason=(f"the flow {source.domain.value} -> {target.value} is not declared"),
            explicit_user_request=explicit_user_request,
        )
    if declared.disposition in {
        FlowDisposition.FORBIDDEN,
        FlowDisposition.AUTHORITY_NOT_GRANTED,
    }:
        return _refused(
            source,
            target,
            rule_id=declared.rule_id,
            refusal=declared.refusal,
            authority=declared.authority,
            reason=(
                f"the flow {source.domain.value} -> {target.value} is declared but "
                + (
                    "forbidden"
                    if declared.disposition is FlowDisposition.FORBIDDEN
                    else "its authority is not granted in this unit"
                )
            ),
            explicit_user_request=explicit_user_request,
        )
    if declared.explicit_user_request_required and not explicit_user_request:
        return _refused(
            source,
            target,
            rule_id=declared.rule_id,
            refusal=declared.refusal,
            authority=declared.authority,
            reason=(
                "an export is admitted only under an explicit user export request; "
                "automatic export is refused"
            ),
            explicit_user_request=explicit_user_request,
        )
    return _admitted(
        source,
        target,
        rule_id=declared.rule_id,
        authority=declared.authority,
        explicit_user_request=explicit_user_request,
    )


def admit_flow(
    classification: DataClassification,
    destination: TrustDomain,
    *,
    explicit_user_request: bool = False,
) -> FlowDecision:
    """Return the admitted decision, or raise the named refusal class."""

    return evaluate_flow(
        classification,
        destination,
        explicit_user_request=explicit_user_request,
    ).require()


# ---------------------------------------------------------------------------
# Object-level guard
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClassifiedObject:
    """A Workspace object revision with its classification and payload digest.

    The payload itself is never retained here: only its recorded digest travels with
    the object, so a refused handoff can name the object without carrying content.
    """

    binding: ObjectBinding
    classification: DataClassification
    payload_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ObjectBinding):
            raise DataClassificationError("a classified object requires an ObjectBinding")
        self.binding.validated()
        if not isinstance(self.classification, DataClassification):
            raise DataClassificationError(
                "a classified object requires a validated DataClassification instance"
            )
        self.classification.validated()
        if not isinstance(self.payload_digest, str) or not self.payload_digest:
            raise DataClassificationError("a classified object requires a payload digest")
        if not self.payload_digest.isascii():
            raise DataClassificationError("the payload digest must be ASCII")

    def validated(self) -> ClassifiedObject:
        """Re-check this instance and return it."""

        self.__post_init__()
        return self

    def identity_document(self) -> dict[str, object]:
        """Return object identity only: no payload and no payload digest."""

        return {
            "object_id": str(self.binding.object_id),
            "object_revision": self.binding.object_revision,
            "object_type": self.binding.object_type.value,
            "workspace_id": str(self.binding.workspace_id),
        }

    def to_document(self) -> dict[str, object]:
        """Return the canonical serialization of this classified object."""

        return {
            "classification": self.classification.to_document(),
            "payload_digest": self.payload_digest,
            **self.identity_document(),
        }

    @staticmethod
    def from_document(document: object) -> ClassifiedObject:
        """Re-admit a serialized classified object, refusing a forged classification."""

        if not isinstance(document, dict):
            raise DataClassificationError("a stored classified object must be a JSON object")
        expected = {
            "classification",
            "object_id",
            "object_revision",
            "object_type",
            "payload_digest",
            "workspace_id",
        }
        if set(document) != expected:
            raise DataClassificationError(
                "a stored classified object must contain exactly the admitted members"
            )
        try:
            binding = ObjectBinding(
                workspace_id=_uuid_member(document, "workspace_id"),
                object_id=_uuid_member(document, "object_id"),
                object_type=WorkspaceObjectType(_string_member(document, "object_type")),
                object_revision=_string_member(document, "object_revision"),
            )
        except ValueError as error:
            raise DataClassificationError(
                "a stored classified object carries an unadmitted identity member"
            ) from error
        return ClassifiedObject(
            binding=binding,
            classification=classification_from_document(document["classification"]),
            payload_digest=_string_member(document, "payload_digest"),
        )


def _string_member(document: dict[str, object], name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str):
        raise DataClassificationError(f"stored member {name!r} must be a string")
    return value


def _uuid_member(document: dict[str, object], name: str) -> UUID:
    try:
        return UUID(_string_member(document, name))
    except ValueError as error:
        raise DataClassificationError(f"stored member {name!r} must be a UUID") from error


def classify_object(
    *,
    binding: ObjectBinding,
    classification: DataClassification,
    payload: bytes,
) -> ClassifiedObject:
    """Bind one Workspace object revision to its classification and payload digest."""

    if not isinstance(payload, bytes) or not payload:
        raise DataClassificationError("an object payload must be non-empty bytes")
    return ClassifiedObject(
        binding=binding,
        classification=classification,
        payload_digest=content_digest_of(payload),
    )


def evaluate_object_flow(
    classified: ClassifiedObject,
    destination: TrustDomain,
    *,
    explicit_user_request: bool = False,
) -> FlowEvaluation:
    """Evaluate one classified object's handoff, keeping its identity in the refusal."""

    admitted_object = classified.validated()
    evaluation = evaluate_flow(
        admitted_object.classification,
        destination,
        explicit_user_request=explicit_user_request,
    )
    return replace(evaluation, object_ref=admitted_object)


def guard_object_handoff(
    classified: ClassifiedObject,
    destination: TrustDomain,
    *,
    explicit_user_request: bool = False,
) -> FlowDecision:
    """Admit one classified object handoff, or raise the named refusal class."""

    return evaluate_object_flow(
        classified,
        destination,
        explicit_user_request=explicit_user_request,
    ).require()


# ---------------------------------------------------------------------------
# File-level export guard (Domain X containment)
# ---------------------------------------------------------------------------

_POSIX_SEPARATOR = "/"
_WINDOWS_SEPARATOR = "\\"
_STRICT_CONTAINMENT_RULE = (
    "strictly_below_quarantine_root_and_outside_every_declared_research_core_root"
)
_WINDOWS_RESERVED_NAMES = frozenset(
    {
        "AUX",
        "CLOCK$",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "CON",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
        "NUL",
        "PRN",
    }
)


@dataclass(frozen=True, slots=True)
class _AdmittedPath:
    """A lexically admitted absolute path and the containment data derived from it."""

    original: str
    # The volume/root identity. Containment is only meaningful inside one volume, so
    # the drive letter or UNC server/share is compared as well as the components: a
    # target on another volume must never be read as "below" a quarantine root that
    # merely happens to share its directory names.
    root_key: str
    components: tuple[str, ...]
    case_insensitive: bool
    unc_form: bool


def _is_absolute_path(path: str) -> bool:
    if path.startswith("\\\\") or path.startswith("//"):
        return True
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
        return True
    return path.startswith("/")


def _admitted_path(raw: object, *, label: str) -> _AdmittedPath:
    """Admit one absolute path lexically, refusing every normalization shape."""

    if not isinstance(raw, str):
        raise ExportBoundaryError(f"{label} must be a string")
    path = raw
    if not path or not path.strip():
        raise ExportBoundaryError(f"{label} must be a non-empty absolute path")
    if "\x00" in path:
        raise ExportBoundaryError(f"{label} must not contain NUL")
    if any(character.isspace() and character != " " for character in path):
        raise ExportBoundaryError(f"{label} must not contain control whitespace")
    has_posix = _POSIX_SEPARATOR in path
    has_windows = _WINDOWS_SEPARATOR in path
    if has_posix and has_windows:
        raise ExportBoundaryError(f"{label} must not mix path separators")
    separator = _WINDOWS_SEPARATOR if has_windows else _POSIX_SEPARATOR
    if not _is_absolute_path(path):
        raise ExportBoundaryError(f"{label} must be absolute")
    unc_form = path.startswith("\\\\") or path.startswith("//")
    drive_form = len(path) >= 2 and path[1] == ":" and path[0].isalpha()
    if unc_form:
        body = path[2:]
    elif drive_form:
        body = path[2:]
        if not body.startswith(separator):
            raise ExportBoundaryError(
                f"{label} must not be drive-relative; a drive path must be anchored at its root"
            )
        body = body[len(separator) :]
    else:
        body = path[1:]
    if not body:
        raise ExportBoundaryError(f"{label} must name at least one path component")
    components = tuple(body.split(separator))
    for component in components:
        if not component:
            raise ExportBoundaryError(
                f"{label} must not contain an empty component or a trailing separator"
            )
        if component in {".", ".."}:
            raise ExportBoundaryError(f"{label} must not contain traversal components")
        if component.endswith(".") or component.endswith(" "):
            raise ExportBoundaryError(
                f"{label} component must not end with a dot or a space, because a host "
                "that normalizes it would relocate the path"
            )
        if ":" in component:
            raise ExportBoundaryError(
                f"{label} component must not contain a colon, which is an alternate data "
                "stream on a host that supports one"
            )
        if component.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES:
            raise ExportBoundaryError(f"{label} component is a reserved device name")
    if unc_form and len(components) < 2:
        raise ExportBoundaryError(f"{label} must name a UNC server and share")
    if unc_form:
        root_key = f"//{components[0].lower()}/{components[1].lower()}"
    elif drive_form:
        root_key = path[0].upper()
    else:
        root_key = _POSIX_SEPARATOR
    return _AdmittedPath(
        original=path,
        root_key=root_key,
        components=components,
        case_insensitive=has_windows or drive_form,
        unc_form=unc_form,
    )


def _normalized_components(path: _AdmittedPath) -> tuple[str, ...]:
    if path.case_insensitive:
        return tuple(component.lower() for component in path.components)
    return path.components


def _contains(outer: _AdmittedPath, inner: _AdmittedPath) -> bool:
    """Return True when ``inner`` is ``outer`` or lies strictly below it."""

    if outer.unc_form is not inner.unc_form:
        return False
    if outer.root_key != inner.root_key:
        return False
    outer_components = _normalized_components(outer)
    inner_components = _normalized_components(inner)
    if len(inner_components) < len(outer_components):
        return False
    return inner_components[: len(outer_components)] == outer_components


@dataclass(frozen=True, slots=True)
class ExportPathAdmission:
    """A proven Domain X export destination."""

    target_path: str
    quarantine_root: str
    research_core_roots: tuple[str, ...]

    def to_document(self) -> dict[str, object]:
        """Return the containment proof as metadata carrying no payload."""

        return {
            "containment_rule": _STRICT_CONTAINMENT_RULE,
            "destination_domain": TrustDomain.EXPORT_QUARANTINE.value,
            "quarantine_root": self.quarantine_root,
            "research_core_root_count": len(self.research_core_roots),
            "target_path": self.target_path,
        }


def admit_export_path(
    *,
    target_path: str,
    quarantine_root: str,
    research_core_roots: tuple[str, ...],
) -> ExportPathAdmission:
    """Prove that an export target stays in Domain X and outside every Domain R root."""

    if not isinstance(research_core_roots, tuple) or not research_core_roots:
        raise ExportBoundaryError(
            "at least one Research Core root must be declared; without it containment "
            "outside Domain R cannot be proven, so the export is refused"
        )
    admitted_root = _admitted_path(quarantine_root, label="quarantine root")
    admitted_target = _admitted_path(target_path, label="export target")
    if admitted_root.unc_form is not admitted_target.unc_form:
        raise ExportBoundaryError(
            "the export target and the quarantine root must use the same path form"
        )
    if not _contains(admitted_root, admitted_target):
        raise ExportBoundaryError("the export target is outside the quarantine root")
    if _normalized_components(admitted_root) == _normalized_components(admitted_target):
        raise ExportBoundaryError(
            "the export target must be a path below the quarantine root, not the root itself"
        )
    for declared_root in research_core_roots:
        admitted_research_root = _admitted_path(declared_root, label="Research Core root")
        if _contains(admitted_research_root, admitted_target):
            raise ExportBoundaryError(
                "the export target is inside a declared Research Core root, so it is "
                "refused: Domain X is not Domain R"
            )
    return ExportPathAdmission(
        target_path=admitted_target.original,
        quarantine_root=admitted_root.original,
        research_core_roots=tuple(str(root) for root in research_core_roots),
    )


@dataclass(frozen=True, slots=True)
class ExportEnvelope:
    """One export staged in Domain X: de-identification never changes its domain."""

    binding: ObjectBinding
    admission: ExportPathAdmission
    payload_digest: str
    deidentified: bool
    classification: DataClassification

    def __post_init__(self) -> None:
        if not isinstance(self.binding, ObjectBinding):
            raise ExportBoundaryError("an export envelope requires an ObjectBinding")
        self.binding.validated()
        if not isinstance(self.admission, ExportPathAdmission):
            raise ExportBoundaryError("an export envelope requires an admitted export path")
        if not isinstance(self.deidentified, bool):
            raise ExportBoundaryError("the de-identification flag must be a boolean")
        if not isinstance(self.classification, DataClassification):
            raise ExportBoundaryError(
                "an export envelope requires a validated DataClassification instance"
            )
        classification = self.classification.validated()
        if classification.domain is not TrustDomain.EXPORT_QUARANTINE:
            raise ExportBoundaryError(
                "an export envelope must stay in Domain X; de-identification does not "
                "create Research Core admission"
            )
        if (
            not isinstance(self.payload_digest, str)
            or not self.payload_digest
            or not self.payload_digest.isascii()
        ):
            raise ExportBoundaryError("an export envelope requires an ASCII payload digest")

    def research_admission_evaluation(self) -> FlowEvaluation:
        """Ask the guard whether this export may become Research Core data."""

        return evaluate_flow(self.classification, TrustDomain.RESEARCH_CORE)

    def to_document(self) -> dict[str, object]:
        """Return the export record as metadata carrying no payload."""

        return {
            "classification": self.classification.to_document(),
            "deidentified": self.deidentified,
            "export_path": self.admission.to_document(),
            "object_id": str(self.binding.object_id),
            "object_revision": self.binding.object_revision,
            "object_type": self.binding.object_type.value,
            "payload_digest": self.payload_digest,
            "workspace_id": str(self.binding.workspace_id),
        }


def stage_export(
    *,
    binding: ObjectBinding,
    payload: bytes,
    target_path: str,
    quarantine_root: str,
    research_core_roots: tuple[str, ...],
    deidentified: bool,
) -> ExportEnvelope:
    """Stage one explicit export in Domain X, whether or not it was de-identified.

    This function performs no I/O: it decides containment, records the export
    classification and refuses anything that would leave Domain X. De-identification
    is recorded as a transformation of an export, never as an admission.
    """

    if not isinstance(payload, bytes) or not payload:
        raise ExportBoundaryError("an exported payload must be non-empty bytes")
    if not isinstance(deidentified, bool):
        raise ExportBoundaryError("the de-identification flag must be a boolean")
    admission = admit_export_path(
        target_path=target_path,
        quarantine_root=quarantine_root,
        research_core_roots=research_core_roots,
    )
    classification = DataClassification(data_class=DataClass.EXPORT_QUARANTINE)
    decision = admit_flow(classification, TrustDomain.EXPORT_QUARANTINE)
    if decision.rule_id != SAME_DOMAIN_RULE_ID:
        raise ExportBoundaryError("the export classification did not resolve to Domain X")
    return ExportEnvelope(
        binding=binding,
        admission=admission,
        payload_digest=content_digest_of(payload),
        deidentified=deidentified,
        classification=classification,
    )
