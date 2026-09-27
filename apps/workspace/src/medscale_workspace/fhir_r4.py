"""Bounded FHIR R4 import/export for CW-013.

A small declared subset of FHIR R4 resources is admitted as immutable synthetic
workspace objects with deterministic identities. Validation states are kept
separate: parse, structure, profile, reference, and provenance are checked in
order and each refusal names the stage that failed.

References between resources are local only: a reference is the string
``ResourceType/id`` and must resolve to an admitted resource in the same
workspace. Every non-Patient resource binds to an admitted Patient resource in
the same workspace. Security labels in ``meta.security`` are retained verbatim
and surfaced on every read.

Export is a computed manifest staged for an explicit Domain X quarantine path:
the target is proven by pure string algebra to sit strictly below the declared
quarantine root and outside every declared Research Core root. This module
performs no filesystem I/O, no network I/O, and no model execution; it holds
no filesystem capability by design.

Resource content is data, not authority. Resource text is stored verbatim,
never evaluated, never executed, and never consulted for capability, policy,
or governance decisions. Malicious strings remain inert.

No donor schema is vendored. The admitted field allowlists below are
MedScale-owned and minimal; they describe the bounded subset only and grant
no conformance claim beyond mechanical validation of synthetic fixtures.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace import corpus as corpus_mod
from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    FhirConflictError,
    FhirInputError,
    FhirRevisionError,
    FhirStaleError,
    ObjectNotFoundError,
    StoreConflictError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    SourceKind,
    SourceRef,
    content_digest_of,
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

FHIR_NAMESPACE = UUID("f0131a40-0004-4000-8000-000000000013")
FHIR_REVISION = "fhir-resource-00000001"
PRODUCER_VERSION = "cw013-v1"
DERIVATION_METHOD = "cw013-deterministic-fhir"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw013-fhir-r4/1"
FHIR_SCHEMA_VERSION = 1
FHIR_VERSION = "4.0.1"
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_RESOURCE_BYTES = 32768
MAXIMUM_VALUE_CHARS = 1024
MAXIMUM_VALUES_PER_LIST = 128
MAXIMUM_VALUE_DEPTH = 8
MAXIMUM_SECURITY_LABELS = 8
MAXIMUM_CODING_CHARS = 128
MAXIMUM_REFERENCES = 16
MAXIMUM_OCCURRED_AT_CHARS = 64
MAXIMUM_PATH_CHARS = 512


class FhirResourceType(StrEnum):
    """The bounded FHIR R4 resource subset admitted by this unit."""

    PATIENT = "Patient"
    ENCOUNTER = "Encounter"
    OBSERVATION = "Observation"
    CONDITION = "Condition"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"
    MEDICATION_REQUEST = "MedicationRequest"
    PROCEDURE = "Procedure"
    DIAGNOSTIC_REPORT = "DiagnosticReport"


_REQUIRED_KEYS = {
    FhirResourceType.PATIENT: ("id",),
    FhirResourceType.ENCOUNTER: ("id", "status", "class", "subject"),
    FhirResourceType.OBSERVATION: ("id", "status", "code"),
    FhirResourceType.CONDITION: ("id", "code", "subject"),
    FhirResourceType.ALLERGY_INTOLERANCE: ("id", "code", "patient"),
    FhirResourceType.MEDICATION_REQUEST: ("id", "status", "intent", "subject"),
    FhirResourceType.PROCEDURE: ("id", "status", "subject"),
    FhirResourceType.DIAGNOSTIC_REPORT: ("id", "status", "code", "subject"),
}

_ALLOWED_KEYS = {
    FhirResourceType.PATIENT: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "active",
        "name",
        "gender",
        "birthDate",
        "address",
        "telecom",
    ),
    FhirResourceType.ENCOUNTER: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "status",
        "class",
        "subject",
        "period",
        "reasonCode",
        "partOf",
    ),
    FhirResourceType.OBSERVATION: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "status",
        "code",
        "subject",
        "encounter",
        "effectiveDateTime",
        "valueString",
        "valueQuantity",
        "component",
        "interpretation",
    ),
    FhirResourceType.CONDITION: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "clinicalStatus",
        "verificationStatus",
        "category",
        "severity",
        "code",
        "subject",
        "encounter",
        "onsetDateTime",
        "recordedDate",
    ),
    FhirResourceType.ALLERGY_INTOLERANCE: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "clinicalStatus",
        "verificationStatus",
        "type",
        "category",
        "criticality",
        "code",
        "patient",
        "onsetDateTime",
        "recordedDate",
    ),
    FhirResourceType.MEDICATION_REQUEST: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "status",
        "intent",
        "medicationCodeableConcept",
        "subject",
        "encounter",
        "authoredOn",
        "dosageInstruction",
    ),
    FhirResourceType.PROCEDURE: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "status",
        "code",
        "subject",
        "encounter",
        "performedDateTime",
        "reasonReference",
    ),
    FhirResourceType.DIAGNOSTIC_REPORT: (
        "resourceType",
        "id",
        "meta",
        "identifier",
        "status",
        "category",
        "code",
        "subject",
        "encounter",
        "effectiveDateTime",
        "issued",
        "conclusion",
        "result",
    ),
}

_ALLOWED_META_KEYS = ("versionId", "lastUpdated", "security")

_SINGLE_REFERENCE_KEYS = ("subject", "patient", "encounter")

_LIST_REFERENCE_KEYS = ("result", "reasonReference")

_SUBJECT_KEYS = ("subject", "patient")

_REFERENCE_TARGETS = {
    "subject": (FhirResourceType.PATIENT, FhirResourceType.ENCOUNTER),
    "patient": (FhirResourceType.PATIENT,),
    "encounter": (FhirResourceType.ENCOUNTER,),
    "result": (FhirResourceType.OBSERVATION,),
    "reasonReference": (
        FhirResourceType.CONDITION,
        FhirResourceType.PROCEDURE,
        FhirResourceType.OBSERVATION,
    ),
}


@dataclass(frozen=True, slots=True)
class SecurityLabel:
    """One retained ``meta.security`` coding, stored verbatim."""

    system: str
    code: str
    display: str

    def validated(self):
        system = _admit_coding(self.system, "security label system")
        code = _admit_coding(self.code, "security label code")
        display = _admit_coding(self.display, "security label display")
        return SecurityLabel(system=system, code=code, display=display)

    def to_document(self):
        return {"system": self.system, "code": self.code, "display": self.display}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise FhirInputError("a stored security label must be a JSON object")
        for name in ("system", "code", "display"):
            if name not in document:
                raise FhirInputError("a stored security label is missing a member")
            if not isinstance(document[name], str):
                raise FhirInputError("a stored security label member must be a string")
        return SecurityLabel(
            system=document["system"], code=document["code"], display=document["display"]
        ).validated()


@dataclass(frozen=True, slots=True)
class ResourceReference:
    """One local ``ResourceType/id`` reference to an admitted resource."""

    resource_type: FhirResourceType
    resource_id: str

    def validated(self):
        if not isinstance(self.resource_type, FhirResourceType):
            raise FhirInputError("a reference resource type is not admitted here")
        resource_id = _admit_identifier(self.resource_id, "reference resource id")
        return ResourceReference(resource_type=self.resource_type, resource_id=resource_id)

    def to_document(self):
        return {"resource_type": self.resource_type.value, "resource_id": self.resource_id}

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise FhirInputError("a stored resource reference must be a JSON object")
        raw_type = document.get("resource_type")
        raw_id = document.get("resource_id")
        try:
            resource_type = FhirResourceType(raw_type)
        except ValueError as error:
            raise FhirInputError("a stored reference resource type is not admitted") from error
        if not isinstance(raw_id, str):
            raise FhirInputError("a stored reference resource id must be a string")
        return ResourceReference(resource_type=resource_type, resource_id=raw_id).validated()


@dataclass(frozen=True, slots=True)
class FhirResource:
    """One admitted synthetic FHIR R4 resource revision."""

    workspace_id: UUID
    resource_id: UUID
    resource_type: FhirResourceType
    fhir_id: str
    resource_version: str
    content: tuple
    security_labels: tuple
    references: tuple
    patient_id: str | None
    source_id: UUID | None
    source_revision: str | None
    content_digest: str | None

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise FhirInputError("a FHIR workspace id must be a UUID value")
        if not isinstance(self.resource_id, UUID):
            raise FhirInputError("a FHIR resource identity must be a UUID value")
        if not isinstance(self.resource_type, FhirResourceType):
            raise FhirInputError("a FHIR resource type is not admitted here")
        fhir_id = _admit_identifier(self.fhir_id, "FHIR resource id")
        resource_version = _admit_identifier(self.resource_version, "FHIR resource version")
        if not isinstance(self.content, tuple):
            raise FhirInputError("FHIR resource content must be a tuple of entries")
        content = tuple(_validated_content_entry(item) for item in self.content)
        if not isinstance(self.security_labels, tuple):
            raise FhirInputError("FHIR security labels must be a tuple")
        if len(self.security_labels) > MAXIMUM_SECURITY_LABELS:
            raise FhirInputError("a FHIR resource carries too many security labels")
        labels = tuple(
            item.validated() if isinstance(item, SecurityLabel) else None
            for item in self.security_labels
        )
        if any(item is None for item in labels):
            raise FhirInputError("FHIR security labels need SecurityLabel instances")
        if not isinstance(self.references, tuple):
            raise FhirInputError("FHIR references must be a tuple")
        if len(self.references) > MAXIMUM_REFERENCES:
            raise FhirInputError("a FHIR resource carries too many references")
        references = tuple(
            item.validated() if isinstance(item, ResourceReference) else None
            for item in self.references
        )
        if any(item is None for item in references):
            raise FhirInputError("FHIR references need ResourceReference instances")
        patient_id = None
        if self.patient_id is not None:
            patient_id = _admit_identifier(self.patient_id, "FHIR patient binding")
        source_id = None
        if self.source_id is not None:
            if not isinstance(self.source_id, UUID):
                raise FhirInputError("a FHIR source id must be a UUID value")
            source_id = self.source_id
        source_revision = None
        if self.source_revision is not None:
            source_revision = _admit_identifier(self.source_revision, "FHIR source revision")
        content_digest = None
        if self.content_digest is not None:
            content_digest = _admit_digest(self.content_digest)
        return FhirResource(
            workspace_id=self.workspace_id,
            resource_id=self.resource_id,
            resource_type=self.resource_type,
            fhir_id=fhir_id,
            resource_version=resource_version,
            content=content,
            security_labels=labels,
            references=references,
            patient_id=patient_id,
            source_id=source_id,
            source_revision=source_revision,
            content_digest=content_digest,
        )

    def to_document(self):
        document = {
            "workspace_id": str(self.workspace_id),
            "resource_id": str(self.resource_id),
            "resource_type": self.resource_type.value,
            "fhir_id": self.fhir_id,
            "resource_version": self.resource_version,
            "content": [_content_entry_to_document(item) for item in self.content],
            "security_labels": [item.to_document() for item in self.security_labels],
            "references": [item.to_document() for item in self.references],
            "patient_id": self.patient_id,
            "source_id": None if self.source_id is None else str(self.source_id),
            "source_revision": self.source_revision,
            "content_digest": self.content_digest,
            "fhir_version": FHIR_VERSION,
            "derivation_method": DERIVATION_METHOD,
            "derivation_version": DERIVATION_METHOD_VERSION,
            "fhir_schema_version": FHIR_SCHEMA_VERSION,
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
        }
        return document

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise FhirInputError("a stored FHIR resource must be a JSON object")
        expected = (
            "workspace_id",
            "resource_id",
            "resource_type",
            "fhir_id",
            "resource_version",
            "content",
            "security_labels",
            "references",
            "patient_id",
            "source_id",
            "source_revision",
            "content_digest",
            "fhir_version",
            "derivation_method",
            "derivation_version",
            "fhir_schema_version",
            "data_class",
            "policy_version",
        )
        for name in expected:
            if name not in document:
                raise FhirInputError("a stored FHIR resource is missing a member")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
        except ValueError as error:
            raise FhirInputError("a stored FHIR workspace id is not a UUID") from error
        try:
            resource_id = UUID(str(document["resource_id"]))
        except ValueError as error:
            raise FhirInputError("a stored FHIR resource identity is not a UUID") from error
        try:
            resource_type = FhirResourceType(document["resource_type"])
        except ValueError as error:
            raise FhirInputError("a stored FHIR resource type is not admitted") from error
        raw_content = document["content"]
        if not isinstance(raw_content, list):
            raise FhirInputError("stored FHIR resource content must be a JSON array")
        raw_labels = document["security_labels"]
        if not isinstance(raw_labels, list):
            raise FhirInputError("stored FHIR security labels must be a JSON array")
        raw_references = document["references"]
        if not isinstance(raw_references, list):
            raise FhirInputError("stored FHIR references must be a JSON array")
        raw_patient = document["patient_id"]
        if raw_patient is not None and not isinstance(raw_patient, str):
            raise FhirInputError("a stored FHIR patient binding must be a string or null")
        raw_source = document["source_id"]
        source_id = None
        if raw_source is not None:
            try:
                source_id = UUID(str(raw_source))
            except ValueError as error:
                raise FhirInputError("a stored FHIR source id is not a UUID") from error
        for name in ("fhir_id", "resource_version"):
            if not isinstance(document[name], str):
                raise FhirInputError(f"a stored {name} must be a string")
        for name in ("source_revision", "content_digest"):
            if document[name] is not None and not isinstance(document[name], str):
                raise FhirInputError(f"a stored {name} must be a string or null")
        if document["fhir_version"] != FHIR_VERSION:
            raise FhirInputError("a stored FHIR version is not admitted here")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise FhirInputError("a stored FHIR derivation method is not admitted here")
        if document["derivation_version"] != DERIVATION_METHOD_VERSION:
            raise FhirInputError("a stored FHIR derivation version is not admitted here")
        schema = document["fhir_schema_version"]
        if isinstance(schema, bool) or schema != FHIR_SCHEMA_VERSION:
            raise FhirInputError("a stored FHIR schema version is not admitted here")
        if document["data_class"] != synthetic_data_class_value():
            raise FhirInputError("a stored FHIR data class is not admitted here")
        if document["policy_version"] != POLICY_VERSION:
            raise FhirInputError("a stored FHIR policy version is not admitted here")
        return FhirResource(
            workspace_id=workspace_id,
            resource_id=resource_id,
            resource_type=resource_type,
            fhir_id=document["fhir_id"],
            resource_version=document["resource_version"],
            content=tuple(_content_entry_from_document(item) for item in raw_content),
            security_labels=tuple(SecurityLabel.from_document(item) for item in raw_labels),
            references=tuple(ResourceReference.from_document(item) for item in raw_references),
            patient_id=raw_patient,
            source_id=source_id,
            source_revision=document["source_revision"],
            content_digest=document["content_digest"],
        ).validated()


@dataclass(frozen=True, slots=True)
class ValidationStage:
    """One named validation stage and whether it passed."""

    stage: str
    passed: bool
    evaluated: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The separated parse/structure/profile/reference/provenance states."""

    resource_type: FhirResourceType
    fhir_id: str
    stages: tuple

    def passed(self):
        return all(item.passed for item in self.stages if item.evaluated)

    def stage(self, name):
        for item in self.stages:
            if item.stage == name:
                return item
        raise FhirInputError("a validation stage name is not admitted here")


@dataclass(frozen=True, slots=True)
class FhirExport:
    """One staged Domain X export envelope for admitted FHIR resources."""

    workspace_id: UUID
    target_path: str
    quarantine_root: str
    resource_ids: tuple
    manifest_digest: str
    entry_count: int

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise FhirInputError("a FHIR export workspace id must be a UUID value")
        if not isinstance(self.resource_ids, tuple) or not self.resource_ids:
            raise FhirInputError("a FHIR export needs a non-empty tuple of resources")
        for item in self.resource_ids:
            if not isinstance(item, UUID):
                raise FhirInputError("a FHIR export resource id must be a UUID value")
        manifest_digest = _admit_digest(self.manifest_digest)
        if not isinstance(self.entry_count, int) or isinstance(self.entry_count, bool):
            raise FhirInputError("a FHIR export entry count must be an integer")
        if self.entry_count != len(self.resource_ids):
            raise FhirInputError("a FHIR export entry count does not match its members")
        return FhirExport(
            workspace_id=self.workspace_id,
            target_path=self.target_path,
            quarantine_root=self.quarantine_root,
            resource_ids=self.resource_ids,
            manifest_digest=manifest_digest,
            entry_count=self.entry_count,
        )


def resource_id_for(workspace_id, resource_type, fhir_id, resource_version):
    """Return the deterministic identity of one admitted FHIR resource."""
    if not isinstance(workspace_id, UUID):
        raise FhirInputError("a workspace id must be a UUID value")
    if not isinstance(resource_type, FhirResourceType):
        raise FhirInputError("a FHIR resource type is not admitted here")
    admitted_id = _admit_identifier(fhir_id, "FHIR resource id")
    version = _admit_identifier(resource_version, "FHIR resource version")
    return uuid5(
        FHIR_NAMESPACE,
        ":".join((str(workspace_id), resource_type.value, admitted_id, version)),
    )


def resource_binding(workspace_id, resource_id):
    """Return the store binding of one admitted FHIR resource."""
    if not isinstance(workspace_id, UUID):
        raise FhirInputError("a workspace id must be a UUID value")
    if not isinstance(resource_id, UUID):
        raise FhirInputError("a FHIR resource identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=resource_id,
        object_type=WorkspaceObjectType.FHIR_RESOURCE,
        object_revision=FHIR_REVISION,
    )


def validate_payload(resource_type, fhir_id, payload_text):
    """Validate the parse, structure, and profile stages of a FHIR payload.

    Reference and provenance stages need a workspace store, so they are
    reported as not evaluated here and are enforced by admit and read.
    """
    if not isinstance(resource_type, FhirResourceType):
        raise FhirInputError("a FHIR resource type is not admitted here")
    admitted_id = _admit_identifier(fhir_id, "FHIR resource id")
    if isinstance(payload_text, str) and len(payload_text.encode("utf-8")) > MAXIMUM_RESOURCE_BYTES:
        return _parse_failed_report(
            resource_type, admitted_id, "the payload exceeds the admitted resource size"
        )
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError):
        return _parse_failed_report(resource_type, admitted_id, "the payload is not JSON")
    return _validate_parsed_payload(resource_type, admitted_id, payload)


def _parse_failed_report(resource_type, fhir_id, detail):
    """Return a parse-stage refusal with later stages unevaluated."""
    return ValidationReport(
        resource_type=resource_type,
        fhir_id=fhir_id,
        stages=(
            ValidationStage(
                stage="parse",
                passed=False,
                evaluated=True,
                detail=detail,
            ),
            ValidationStage(
                stage="structure",
                passed=False,
                evaluated=False,
                detail="structure was not evaluated because parsing failed",
            ),
            ValidationStage(
                stage="profile",
                passed=False,
                evaluated=False,
                detail="profile was not evaluated because parsing failed",
            ),
            ValidationStage(
                stage="reference",
                passed=False,
                evaluated=False,
                detail="reference needs a workspace store",
            ),
            ValidationStage(
                stage="provenance",
                passed=False,
                evaluated=False,
                detail="provenance needs a workspace store",
            ),
        ),
    )


def _validate_parsed_payload(resource_type, admitted_id, payload):
    """Validate the structure and profile stages of an already-parsed payload."""
    try:
        _check_structure(resource_type, admitted_id, payload)
    except FhirInputError as error:
        return ValidationReport(
            resource_type=resource_type,
            fhir_id=admitted_id,
            stages=(
                ValidationStage(
                    stage="parse", passed=True, evaluated=True, detail="the payload parses as JSON"
                ),
                ValidationStage(stage="structure", passed=False, evaluated=True, detail=str(error)),
                ValidationStage(
                    stage="profile",
                    passed=False,
                    evaluated=False,
                    detail="profile was not evaluated",
                ),
                ValidationStage(
                    stage="reference",
                    passed=False,
                    evaluated=False,
                    detail="reference needs a workspace store",
                ),
                ValidationStage(
                    stage="provenance",
                    passed=False,
                    evaluated=False,
                    detail="provenance needs a workspace store",
                ),
            ),
        )
    try:
        _check_profile(resource_type, payload)
    except FhirInputError as error:
        return ValidationReport(
            resource_type=resource_type,
            fhir_id=admitted_id,
            stages=(
                ValidationStage(
                    stage="parse", passed=True, evaluated=True, detail="the payload parses as JSON"
                ),
                ValidationStage(
                    stage="structure",
                    passed=True,
                    evaluated=True,
                    detail="required members are present",
                ),
                ValidationStage(stage="profile", passed=False, evaluated=True, detail=str(error)),
                ValidationStage(
                    stage="reference",
                    passed=False,
                    evaluated=False,
                    detail="reference needs a workspace store",
                ),
                ValidationStage(
                    stage="provenance",
                    passed=False,
                    evaluated=False,
                    detail="provenance needs a workspace store",
                ),
            ),
        )
    return ValidationReport(
        resource_type=resource_type,
        fhir_id=admitted_id,
        stages=(
            ValidationStage(
                stage="parse", passed=True, evaluated=True, detail="the payload parses as JSON"
            ),
            ValidationStage(
                stage="structure",
                passed=True,
                evaluated=True,
                detail="required members are present",
            ),
            ValidationStage(
                stage="profile",
                passed=True,
                evaluated=True,
                detail="members fit the bounded subset",
            ),
            ValidationStage(
                stage="reference",
                passed=False,
                evaluated=False,
                detail="reference needs a workspace store",
            ),
            ValidationStage(
                stage="provenance",
                passed=False,
                evaluated=False,
                detail="provenance needs a workspace store",
            ),
        ),
    )


def admit_resource(
    store,
    trail,
    workspace_id,
    resource_type,
    fhir_id,
    payload_text,
    actor_id,
    occurred_at,
    source_id=None,
):
    """Admit one synthetic FHIR R4 resource with all five stages enforced."""
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise FhirInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise FhirInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a FHIR resource crossed the workspace boundary")
    if not isinstance(resource_type, FhirResourceType):
        raise FhirInputError("a FHIR resource type is not admitted here")
    admitted_id = _admit_identifier(fhir_id, "FHIR resource id")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    report = validate_payload(resource_type, admitted_id, payload_text)
    if not report.passed():
        failing = [item.stage for item in report.stages if item.evaluated and not item.passed]
        raise FhirInputError("the FHIR payload failed validation at stage: " + ",".join(failing))
    try:
        payload = json.loads(payload_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise FhirInputError("the FHIR payload is not JSON") from error
    version = _resource_version(payload)
    labels = _security_labels(payload)
    references = _resource_references(payload)
    patient_binding = _patient_binding(resource_type, payload)
    _check_references(store, workspace_id, references, "admit")
    _check_patient_binding(store, workspace_id, resource_type, patient_binding, "admit")
    source_revision = None
    source_digest = None
    if source_id is not None:
        if not isinstance(source_id, UUID):
            raise FhirInputError("a FHIR source id must be a UUID value")
        try:
            source = corpus_mod.read_source(store, source_id)
        except corpus_mod.CorpusInputError as error:
            raise FhirRevisionError("the FHIR source is absent in this store") from error
        source_revision = source.source_revision
        source_digest = source.content_digest
    resource = FhirResource(
        workspace_id=workspace_id,
        resource_id=resource_id_for(workspace_id, resource_type, admitted_id, version),
        resource_type=resource_type,
        fhir_id=admitted_id,
        resource_version=version,
        content=_content_entries(payload),
        security_labels=labels,
        references=references,
        patient_id=patient_binding,
        source_id=source_id,
        source_revision=source_revision,
        content_digest=source_digest,
    ).validated()
    binding = resource_binding(workspace_id, resource.resource_id)
    stored = _canonical_bytes(resource.to_document())
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=actor, version=PRODUCER_VERSION
    )
    source_refs = [
        SourceRef(
            kind=SourceKind.FHIR_RESOURCE,
            source_id=str(resource.resource_id),
            source_revision=resource.resource_version,
            locator=resource_type.value + "/" + admitted_id,
        )
    ]
    if source_id is not None:
        source_refs.append(
            SourceRef(
                kind=SourceKind.EVIDENCE_SOURCE,
                source_id=str(source_id),
                source_revision=source_revision,
                locator=None,
            )
        )
    record = describe_revision(
        binding=binding,
        payload=stored,
        producer=producer,
        source_refs=tuple(source_refs),
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, stored)
    except StoreConflictError as error:
        raise FhirConflictError("the FHIR resource identity already exists") from error
    trail.record_object_write(binding=binding, payload=stored, actor_id=actor, occurred_at=moment)
    return binding


def read_resource(store, resource_id):
    """Read and verify one stored FHIR resource with bindings still current."""
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    if not isinstance(resource_id, UUID):
        raise FhirInputError("a FHIR resource identity must be a UUID value")
    binding = resource_binding(store.workspace_id, resource_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise FhirInputError("the FHIR identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise FhirInputError("a stored FHIR resource is not ASCII JSON") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise FhirInputError("a stored FHIR resource is not JSON") from error
    resource = FhirResource.from_document(payload)
    if resource.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a FHIR resource crossed the workspace boundary")
    if resource.resource_id != resource_id:
        raise FhirInputError("a stored FHIR identity does not match its binding")
    record = read_provenance(store, binding)
    record.verify_payload(raw)
    if resource.source_id is not None:
        try:
            source = corpus_mod.read_source(store, resource.source_id)
        except corpus_mod.CorpusInputError as error:
            raise FhirStaleError("a FHIR source is no longer present") from error
        if source.source_revision != resource.source_revision:
            raise FhirStaleError("a FHIR source revision no longer matches")
        if source.content_digest != resource.content_digest:
            raise FhirStaleError("a FHIR source digest no longer matches")
    _check_references(store, store.workspace_id, resource.references, "read")
    _check_patient_binding(
        store, store.workspace_id, resource.resource_type, resource.patient_id, "read"
    )
    return resource.validated()


def delete_resource(store, trail, resource_id, actor_id, occurred_at):
    """Delete one admitted FHIR resource; dependents refuse the deletion."""
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise FhirInputError("an audit trail is required")
    if not isinstance(resource_id, UUID):
        raise FhirInputError("a FHIR resource identity must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    resource = read_resource(store, resource_id)
    dependents = dependents_for(store, resource_id)
    if dependents:
        raise FhirConflictError("a FHIR resource with dependents cannot be deleted")
    binding = resource_binding(store.workspace_id, resource.resource_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def dependents_for(store, resource_id):
    """Return the identities of admitted resources referencing this resource."""
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    if not isinstance(resource_id, UUID):
        raise FhirInputError("a FHIR resource identity must be a UUID value")
    target = read_resource(store, resource_id)
    found = []
    for object_id, _revision in store.object_revisions(WorkspaceObjectType.FHIR_RESOURCE):
        if object_id == resource_id:
            continue
        try:
            candidate = read_resource(store, object_id)
        except FhirStaleError:
            continue
        except FhirInputError:
            continue
        for reference in candidate.references:
            try:
                referenced = _reference_binding(store, store.workspace_id, reference)
            except FhirRevisionError:
                continue
            if referenced.object_id == target.resource_id:
                found.append(candidate.resource_id)
    return tuple(found)


def resources_for_patient(store, patient_fhir_id):
    """Return the identities of admitted resources bound to one patient."""
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    admitted = _admit_identifier(patient_fhir_id, "FHIR patient binding")
    found = []
    for object_id, _revision in store.object_revisions(WorkspaceObjectType.FHIR_RESOURCE):
        try:
            candidate = read_resource(store, object_id)
        except FhirStaleError:
            continue
        except FhirInputError:
            continue
        if candidate.resource_type is FhirResourceType.PATIENT:
            if candidate.fhir_id == admitted:
                found.append(candidate.resource_id)
        elif candidate.patient_id == admitted:
            found.append(candidate.resource_id)
    return tuple(found)


def stage_fhir_export(
    store,
    trail,
    workspace_id,
    resource_ids,
    target_path,
    quarantine_root,
    research_core_roots,
    actor_id,
    occurred_at,
):
    """Stage a Domain X export envelope for admitted FHIR resources.

    The target path is proven by string algebra to sit strictly below the
    quarantine root and outside every Research Core root. No file is written:
    this module holds no filesystem capability, so the envelope records the
    staged intent with its manifest digest and audit trail.
    """
    if not isinstance(store, WorkspaceStore):
        raise FhirInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise FhirInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise FhirInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a FHIR export crossed the workspace boundary")
    if not isinstance(resource_ids, tuple) or not resource_ids:
        raise FhirInputError("a FHIR export needs a non-empty tuple of resources")
    for item in resource_ids:
        if not isinstance(item, UUID):
            raise FhirInputError("a FHIR export resource id must be a UUID value")
    target = _admit_export_path(target_path, quarantine_root, research_core_roots)
    root = _admit_path(quarantine_root, "quarantine root")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    verified = tuple(read_resource(store, item) for item in resource_ids)
    entries = []
    refs = []
    for resource in verified:
        binding = resource_binding(workspace_id, resource.resource_id)
        record = read_provenance(store, binding)
        entries.append(
            {
                "fullUrl": resource.resource_type.value + "/" + resource.fhir_id,
                "resource": _stored_content(resource),
                "request": {
                    "method": "PUT",
                    "url": resource.resource_type.value + "/" + resource.fhir_id,
                },
            }
        )
        refs.append(
            AuditObjectRef(
                object_id=resource.resource_id,
                object_type=WorkspaceObjectType.FHIR_RESOURCE,
                object_revision=FHIR_REVISION,
                content_digest=record.content_digest,
            )
        )
    manifest = {
        "export_format": "cw013-fhir-export/1",
        "fhir_version": FHIR_VERSION,
        "derivation_method": DERIVATION_METHOD,
        "derivation_version": DERIVATION_METHOD_VERSION,
        "resource_type": "Bundle",
        "bundle_type": "transaction",
        "target_path": target,
        "quarantine_root": root,
        "entry_count": len(entries),
        "entries": entries,
    }
    manifest_bytes = _canonical_bytes(manifest)
    digest = content_digest_of(manifest_bytes)
    trail.append(
        event_type=AuditEventType.EXPORT,
        actor_id=actor,
        occurred_at=moment,
        object_refs=tuple(refs),
        metadata=(
            ("target_path", target),
            ("manifest_digest", digest),
            ("entry_count", str(len(entries))),
        ),
    )
    envelope = FhirExport(
        workspace_id=workspace_id,
        target_path=target,
        quarantine_root=root,
        resource_ids=tuple(item.resource_id for item in verified),
        manifest_digest=digest,
        entry_count=len(entries),
    ).validated()
    return (envelope, manifest_bytes)


def _stored_content(resource):
    document = {}
    for key, value in resource.content:
        document[key] = _content_value_to_json(value)
    return document


def _check_structure(resource_type, fhir_id, payload):
    if not isinstance(payload, dict):
        raise FhirInputError("the FHIR payload must be a JSON object")
    if payload.get("resourceType") != resource_type.value:
        raise FhirInputError("the FHIR resourceType does not match the declared type")
    if payload.get("id") != fhir_id:
        raise FhirInputError("the FHIR id does not match the declared id")
    for name in _REQUIRED_KEYS[resource_type]:
        if name not in payload:
            raise FhirInputError("the FHIR payload is missing a required member")


def _check_profile(resource_type, payload):
    allowed = _ALLOWED_KEYS[resource_type]
    for name in payload:
        if name not in allowed:
            raise FhirInputError("the FHIR payload carries an unadmitted member")
    meta = payload.get("meta")
    if meta is not None:
        if not isinstance(meta, dict):
            raise FhirInputError("FHIR meta must be a JSON object")
        for name in meta:
            if name not in _ALLOWED_META_KEYS:
                raise FhirInputError("FHIR meta carries an unadmitted member")
        version = meta.get("versionId")
        if version is not None and not isinstance(version, str):
            raise FhirInputError("FHIR meta.versionId must be a string")
        updated = meta.get("lastUpdated")
        if updated is not None and not isinstance(updated, str):
            raise FhirInputError("FHIR meta.lastUpdated must be a string")
        security = meta.get("security")
        if security is not None:
            if not isinstance(security, list):
                raise FhirInputError("FHIR meta.security must be a JSON array")
            if len(security) > MAXIMUM_SECURITY_LABELS:
                raise FhirInputError("a FHIR payload carries too many security labels")
    _admit_json_value(payload, 0)


def _resource_version(payload):
    meta = payload.get("meta")
    if isinstance(meta, dict):
        version = meta.get("versionId")
        if isinstance(version, str) and version.strip():
            return _admit_identifier(version.strip(), "FHIR resource version")
    return "1"


def _security_labels(payload):
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return ()
    security = meta.get("security")
    if security is None:
        return ()
    labels = []
    for entry in security:
        if not isinstance(entry, dict):
            raise FhirInputError("a FHIR security label must be a JSON object")
        system = entry.get("system")
        code = entry.get("code")
        display = entry.get("display")
        if not isinstance(system, str) or not isinstance(code, str) or not isinstance(display, str):
            raise FhirInputError("a FHIR security label needs system, code, and display")
        labels.append(
            SecurityLabel(system=system.strip(), code=code.strip(), display=display.strip())
        )
    return tuple(item.validated() for item in labels)


def _resource_references(payload):
    references = []
    for name in _SINGLE_REFERENCE_KEYS:
        raw = payload.get(name)
        if raw is not None:
            references.append(_parse_reference(raw))
    for name in _LIST_REFERENCE_KEYS:
        raw = payload.get(name)
        if raw is not None:
            if not isinstance(raw, list):
                raise FhirInputError("a FHIR reference list must be a JSON array")
            for entry in raw:
                references.append(_parse_reference(entry))
    if len(references) > MAXIMUM_REFERENCES:
        raise FhirInputError("a FHIR payload carries too many references")
    return tuple(item.validated() for item in references)


def _parse_reference(raw):
    if isinstance(raw, dict):
        raw = raw.get("reference")
    if not isinstance(raw, str):
        raise FhirInputError("a FHIR reference must be a ResourceType/id string")
    value = raw.strip()
    parts = value.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise FhirInputError("a FHIR reference must look like ResourceType/id")
    try:
        resource_type = FhirResourceType(parts[0])
    except ValueError as error:
        raise FhirInputError("a FHIR reference type is not admitted here") from error
    return ResourceReference(resource_type=resource_type, resource_id=parts[1].strip())


def _patient_binding(resource_type, payload):
    if resource_type is FhirResourceType.PATIENT:
        return None
    for name in _SUBJECT_KEYS:
        raw = payload.get(name)
        if raw is None:
            continue
        reference = _parse_reference(raw)
        if reference.resource_type is not FhirResourceType.PATIENT:
            raise FhirInputError("a FHIR subject binding must reference a Patient")
        return reference.validated().resource_id
    raise FhirInputError("a non-Patient resource needs a Patient subject binding")


def _check_references(store, workspace_id, references, operation):
    for reference in references:
        admitted = reference.validated()
        target = _find_resource_id(
            store, workspace_id, admitted.resource_type, admitted.resource_id
        )
        if target is None:
            if operation == "admit":
                raise FhirRevisionError("a FHIR reference is dangling in this store")
            raise FhirStaleError("a FHIR reference is no longer present")


def _check_patient_binding(store, workspace_id, resource_type, patient_id, operation):
    if resource_type is FhirResourceType.PATIENT:
        return
    if patient_id is None:
        raise FhirInputError("a non-Patient resource needs a Patient subject binding")
    target = _find_resource_id(store, workspace_id, FhirResourceType.PATIENT, patient_id)
    if target is None:
        if operation == "admit":
            raise FhirRevisionError("the FHIR patient binding is absent in this store")
        raise FhirStaleError("the FHIR patient binding is no longer present")


def _find_resource_id(store, workspace_id, resource_type, fhir_id):
    for object_id, _revision in store.object_revisions(WorkspaceObjectType.FHIR_RESOURCE):
        candidate = _scan_match(store, workspace_id, object_id, resource_type, fhir_id)
        if candidate is not None:
            return candidate
    return None


def _scan_match(store, workspace_id, object_id, resource_type, fhir_id):
    """Match one stored object by type and FHIR id without verifying references."""
    binding = ObjectBinding(
        workspace_id=workspace_id,
        object_id=object_id,
        object_type=WorkspaceObjectType.FHIR_RESOURCE,
        object_revision=FHIR_REVISION,
    )
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError:
        return None
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        resource = FhirResource.from_document(payload)
    except FhirInputError:
        return None
    if resource.workspace_id != workspace_id:
        return None
    if resource.resource_type is resource_type and resource.fhir_id == fhir_id:
        return resource.resource_id
    return None


def _reference_binding(store, workspace_id, reference):
    admitted = reference.validated()
    target = _find_resource_id(store, workspace_id, admitted.resource_type, admitted.resource_id)
    if target is None:
        raise FhirRevisionError("a FHIR reference target is absent in this store")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=target,
        object_type=WorkspaceObjectType.FHIR_RESOURCE,
        object_revision=FHIR_REVISION,
    )


def _content_entries(payload):
    entries = []
    for name in sorted(payload):
        entries.append((name, _freeze_value(payload[name], 0)))
    return tuple(entries)


def _freeze_value(value, depth):
    if depth > MAXIMUM_VALUE_DEPTH:
        raise FhirInputError("a FHIR value is nested too deeply")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAXIMUM_VALUE_CHARS:
            raise FhirInputError("a FHIR string value is too long")
        return value
    if isinstance(value, list):
        if len(value) > MAXIMUM_VALUES_PER_LIST:
            raise FhirInputError("a FHIR list value carries too many members")
        return tuple(_freeze_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        frozen = []
        for name in sorted(value):
            if not isinstance(name, str):
                raise FhirInputError("a FHIR object key must be a string")
            frozen.append((name, _freeze_value(value[name], depth + 1)))
        return tuple(frozen)
    raise FhirInputError("a FHIR value has an unadmitted JSON type")


def _admit_json_value(value, depth):
    if depth > MAXIMUM_VALUE_DEPTH:
        raise FhirInputError("a FHIR value is nested too deeply")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAXIMUM_VALUE_CHARS:
            raise FhirInputError("a FHIR string value is too long")
        for character in value:
            if character in ("\n", "\t"):
                continue
            if not character.isprintable():
                raise FhirInputError("a FHIR string value must not carry controls")
        return value
    if isinstance(value, list):
        if len(value) > MAXIMUM_VALUES_PER_LIST:
            raise FhirInputError("a FHIR list value carries too many members")
        for item in value:
            _admit_json_value(item, depth + 1)
        return value
    if isinstance(value, dict):
        for name in value:
            if not isinstance(name, str):
                raise FhirInputError("a FHIR object key must be a string")
            _admit_identifier(name, "FHIR object key")
            _admit_json_value(value[name], depth + 1)
        return value
    raise FhirInputError("a FHIR value has an unadmitted JSON type")


def _validated_content_entry(entry):
    if not isinstance(entry, tuple) or len(entry) != 2:
        raise FhirInputError("FHIR resource content needs key/value entries")
    name, value = entry
    _admit_identifier(name, "FHIR content key")
    return (name, _freeze_value(_thaw_value(value), 0))


def _thaw_value(value):
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {item[0]: _thaw_value(item[1]) for item in value}
        return [_thaw_value(item) for item in value]
    if isinstance(value, list):
        return [_thaw_value(item) for item in value]
    return value


def _content_entry_to_document(entry):
    name, value = entry
    return {"key": name, "value": _content_value_to_json(value)}


def _content_entry_from_document(document):
    if not isinstance(document, dict):
        raise FhirInputError("a stored FHIR content entry must be a JSON object")
    if "key" not in document or "value" not in document:
        raise FhirInputError("a stored FHIR content entry is missing a member")
    if not isinstance(document["key"], str):
        raise FhirInputError("a stored FHIR content key must be a string")
    return (document["key"], _content_value_from_json(document["value"]))


def _content_value_to_json(value):
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            document = {}
            for item in value:
                document[item[0]] = _content_value_to_json(item[1])
            return {"object": document}
        return [_content_value_to_json(item) for item in value]
    if isinstance(value, list):
        return [_content_value_to_json(item) for item in value]
    return value


def _content_value_from_json(document):
    if isinstance(document, dict) and set(document) == {"object"}:
        frozen = []
        for name in sorted(document["object"]):
            frozen.append((name, _content_value_from_json(document["object"][name])))
        return tuple(frozen)
    if isinstance(document, list):
        return tuple(_content_value_from_json(item) for item in document)
    return document


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise FhirInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise FhirInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise FhirInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise FhirInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise FhirInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_coding(raw, label):
    if not isinstance(raw, str):
        raise FhirInputError(f"a {label} must be a string")
    value = raw.strip()
    if not value:
        raise FhirInputError(f"a {label} must be non-empty")
    if len(value) > MAXIMUM_CODING_CHARS:
        raise FhirInputError(f"a {label} is longer than the admitted maximum")
    if not value.isascii():
        raise FhirInputError(f"a {label} must be ASCII")
    for character in value:
        if not character.isprintable():
            raise FhirInputError(f"a {label} must not contain control characters")
    return " ".join(value.split())


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise FhirInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise FhirInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise FhirInputError("a FHIR occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise FhirInputError("a FHIR occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise FhirInputError("a FHIR occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise FhirInputError("a FHIR occurrence time must be an ISO-8601 instant")
    if not value.isascii():
        raise FhirInputError("a FHIR occurrence time must be ASCII")
    return value


def _admit_path(raw, label):
    if not isinstance(raw, str):
        raise FhirInputError(f"a {label} must be a string")
    value = raw.strip()
    if not value:
        raise FhirInputError(f"a {label} must be non-empty")
    if len(value) > MAXIMUM_PATH_CHARS:
        raise FhirInputError(f"a {label} is longer than the admitted maximum")
    if not value.isascii():
        raise FhirInputError(f"a {label} must be ASCII")
    for character in value:
        if not character.isprintable() or character.isspace():
            raise FhirInputError(f"a {label} must not contain whitespace or controls")
    if "\\" in value:
        raise FhirInputError(f"a {label} must use forward slashes")
    return value


def _path_segments(path):
    return path.split("/")


def _admit_export_path(target_path, quarantine_root, research_core_roots):
    target = _admit_path(target_path, "export target path")
    root = _admit_path(quarantine_root, "quarantine root")
    if not isinstance(research_core_roots, tuple):
        raise FhirInputError("research core roots must be a tuple")
    roots = tuple(_admit_path(item, "research core root") for item in research_core_roots)
    for segment in _path_segments(target):
        if segment == "..":
            raise FhirInputError("an export target must not traverse upwards")
    if target == root or not target.startswith(root + "/"):
        raise FhirInputError("an export target must sit strictly below the quarantine root")
    for research_root in roots:
        if target == research_root or target.startswith(research_root + "/"):
            raise FhirInputError("an export target must stay outside Research Core roots")
    return target


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )
