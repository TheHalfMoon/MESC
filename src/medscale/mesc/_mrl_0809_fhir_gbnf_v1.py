"""Bounded FHIR R4 StructureDefinition-to-GBNF compiler for MESC RQ1."""

from __future__ import annotations

import hashlib
import json
from typing import Final, Never, cast

PATIENT_STRUCTUREDEFINITION_SHA256: Final = (
    "c60e7a581b7b311d37b4baf0edb87183f3f41242ee3ad8d7fffd3ce79f0a5458"
)
ADDRESS_STRUCTUREDEFINITION_SHA256: Final = (
    "4eae8dd9e4d3ea00d9cd4f6d99509a97a281a97355dfa74e90dd5be839644300"
)
RQ1_PATIENT_GBNF_SHA256: Final = "b63ff5003471f3af8c3624e508f08a418f7e9f7f6ed18ecf743d7f6ad8b7f16c"
FHIR_VERSION: Final = "4.0.1"
_GENDER_VALUESET: Final = "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1"

_GRAMMAR: Final = b"""root ::= "{" ws resource-type patient-tail ws "}"
resource-type ::= "\\\"resourceType\\\"" ws ":" ws "\\\"Patient\\\""
patient-tail ::= id-opt gender-opt birthdate-opt deceased-opt address-opt
id-opt ::= "" | comma "\\\"id\\\"" ws ":" ws fhir-string
gender-opt ::= "" | comma "\\\"gender\\\"" ws ":" ws gender
birthdate-opt ::= "" | comma "\\\"birthDate\\\"" ws ":" ws fhir-date
deceased-opt ::= "" | comma "\\\"deceasedBoolean\\\"" ws ":" ws boolean
address-opt ::= "" | comma "\\\"address\\\"" ws ":" ws address-array
address-array ::= "[" ws "]" | "[" ws address (comma address)* ws "]"
address ::= "{" ws "}" | "{" ws address-fields ws "}"
address-fields ::= address-city (comma address-state)? (comma address-postal)? (comma address-country)? | address-state (comma address-postal)? (comma address-country)? | address-postal (comma address-country)? | address-country
address-city ::= "\\\"city\\\"" ws ":" ws fhir-string
address-state ::= "\\\"state\\\"" ws ":" ws fhir-string
address-postal ::= "\\\"postalCode\\\"" ws ":" ws fhir-string
address-country ::= "\\\"country\\\"" ws ":" ws fhir-string
comma ::= ws "," ws
boolean ::= "true" | "false"
gender ::= "\\\"male\\\"" | "\\\"female\\\"" | "\\\"other\\\"" | "\\\"unknown\\\""
fhir-date ::= "\\\"" date-year ("-" date-month ("-" date-day)?)? "\\\""
date-year ::= [0-9] [0-9] [0-9] [0-9]
date-month ::= "0" [1-9] | "1" [0-2]
date-day ::= "0" [1-9] | [12] [0-9] | "3" [01]
fhir-string ::= "\\\"" json-char* "\\\""
json-char ::= [^"\\\\\\x00-\\x1f] | "\\\\" (["\\\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \\t\\n\\r]*
"""


class MRL0809FHIRGrammarError(ValueError):
    """Fail-closed error for the bounded RQ1 FHIR grammar compiler."""


def _reject_constant(value: str) -> Never:
    raise MRL0809FHIRGrammarError(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0809FHIRGrammarError(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _parse(raw: bytes, *, label: str, expected_sha256: str) -> dict[str, object]:
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise MRL0809FHIRGrammarError(f"{label} exact byte identity drifted")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except MRL0809FHIRGrammarError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise MRL0809FHIRGrammarError(f"{label} is not valid UTF-8 JSON") from exc
    if type(value) is not dict:
        raise MRL0809FHIRGrammarError(f"{label} must be one JSON object")
    return cast(dict[str, object], value)


def _require_header(
    document: dict[str, object], *, label: str, definition_id: str, kind: str, base: str
) -> None:
    expected = {
        "resourceType": "StructureDefinition",
        "id": definition_id,
        "url": f"http://hl7.org/fhir/StructureDefinition/{definition_id}",
        "version": FHIR_VERSION,
        "fhirVersion": FHIR_VERSION,
        "type": definition_id,
        "kind": kind,
        "derivation": "specialization",
        "baseDefinition": base,
    }
    for field, expected_value in expected.items():
        if document.get(field) != expected_value:
            raise MRL0809FHIRGrammarError(f"{label}.{field} drifted")


def _elements(document: dict[str, object], *, label: str) -> list[dict[str, object]]:
    snapshot = document.get("snapshot")
    if type(snapshot) is not dict:
        raise MRL0809FHIRGrammarError(f"{label}.snapshot missing")
    raw = cast(dict[str, object], snapshot).get("element")
    if type(raw) is not list:
        raise MRL0809FHIRGrammarError(f"{label}.snapshot.element missing")
    rows: list[dict[str, object]] = []
    for item in cast(list[object], raw):
        if type(item) is not dict:
            raise MRL0809FHIRGrammarError(f"{label}.snapshot.element contains non-object")
        rows.append(cast(dict[str, object], item))
    return rows


def _element(rows: list[dict[str, object]], element_id: str) -> dict[str, object]:
    matches = [item for item in rows if item.get("id") == element_id]
    if len(matches) != 1:
        raise MRL0809FHIRGrammarError(f"element {element_id} missing or duplicated")
    return matches[0]


def _type_codes(element: dict[str, object], *, label: str) -> tuple[str, ...]:
    raw = element.get("type", [])
    if type(raw) is not list:
        raise MRL0809FHIRGrammarError(f"{label}.type must be an array")
    result: list[str] = []
    for item in cast(list[object], raw):
        if type(item) is not dict or type(cast(dict[str, object], item).get("code")) is not str:
            raise MRL0809FHIRGrammarError(f"{label}.type entry invalid")
        result.append(cast(str, cast(dict[str, object], item)["code"]))
    return tuple(result)


def _require_element(
    rows: list[dict[str, object]],
    element_id: str,
    *,
    minimum: int,
    maximum: str,
    type_codes: tuple[str, ...],
    binding: str | None = None,
) -> None:
    element = _element(rows, element_id)
    if (
        element.get("path") != element_id
        or element.get("min") != minimum
        or element.get("max") != maximum
    ):
        raise MRL0809FHIRGrammarError(f"{element_id} cardinality/path drifted")
    if _type_codes(element, label=element_id) != type_codes:
        raise MRL0809FHIRGrammarError(f"{element_id} type set/order drifted")
    if binding is not None:
        raw_binding = element.get("binding")
        if type(raw_binding) is not dict:
            raise MRL0809FHIRGrammarError(f"{element_id} binding missing")
        binding_object = cast(dict[str, object], raw_binding)
        if (
            binding_object.get("strength") != "required"
            or binding_object.get("valueSet") != binding
        ):
            raise MRL0809FHIRGrammarError(f"{element_id} binding drifted")


def compile_rq1_patient_gbnf(*, patient_bytes: bytes, address_bytes: bytes) -> bytes:
    """Validate the frozen source surface and return canonical RQ1 GBNF bytes."""
    patient = _parse(
        patient_bytes,
        label="Patient StructureDefinition",
        expected_sha256=PATIENT_STRUCTUREDEFINITION_SHA256,
    )
    address = _parse(
        address_bytes,
        label="Address StructureDefinition",
        expected_sha256=ADDRESS_STRUCTUREDEFINITION_SHA256,
    )
    _require_header(
        patient,
        label="Patient StructureDefinition",
        definition_id="Patient",
        kind="resource",
        base="http://hl7.org/fhir/StructureDefinition/DomainResource",
    )
    _require_header(
        address,
        label="Address StructureDefinition",
        definition_id="Address",
        kind="complex-type",
        base="http://hl7.org/fhir/StructureDefinition/Element",
    )
    patient_rows = _elements(patient, label="Patient")
    address_rows = _elements(address, label="Address")
    _require_element(
        patient_rows,
        "Patient.id",
        minimum=0,
        maximum="1",
        type_codes=("http://hl7.org/fhirpath/System.String",),
    )
    _require_element(
        patient_rows,
        "Patient.gender",
        minimum=0,
        maximum="1",
        type_codes=("code",),
        binding=_GENDER_VALUESET,
    )
    _require_element(
        patient_rows, "Patient.birthDate", minimum=0, maximum="1", type_codes=("date",)
    )
    _require_element(
        patient_rows,
        "Patient.deceased[x]",
        minimum=0,
        maximum="1",
        type_codes=("boolean", "dateTime"),
    )
    _require_element(
        patient_rows, "Patient.address", minimum=0, maximum="*", type_codes=("Address",)
    )
    for field in ("city", "state", "postalCode", "country"):
        _require_element(
            address_rows,
            f"Address.{field}",
            minimum=0,
            maximum="1",
            type_codes=("string",),
        )
    if hashlib.sha256(_GRAMMAR).hexdigest() != RQ1_PATIENT_GBNF_SHA256:
        raise MRL0809FHIRGrammarError("internal frozen grammar identity drifted")
    return _GRAMMAR


__all__ = [
    "ADDRESS_STRUCTUREDEFINITION_SHA256",
    "FHIR_VERSION",
    "PATIENT_STRUCTUREDEFINITION_SHA256",
    "RQ1_PATIENT_GBNF_SHA256",
    "MRL0809FHIRGrammarError",
    "compile_rq1_patient_gbnf",
]
