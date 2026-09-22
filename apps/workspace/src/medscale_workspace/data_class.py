"""Canonical typed data classification for the Clinical Workspace (CW-004).

The canonically effective CW-000 planning package declares the trust domains `R`
(Research Core), `W` (Workspace clinical state), `X` (explicit export/admission
staging), `E` (external connector) and `P` (plugin/model runtime), together with a
minimum data classification and the data-flow rules between them.

CW-004 makes that declaration mechanical rather than conventional:

* one typed representation, declared once, instead of the same classification
  written as a repeated string literal in several modules;
* one canonical table binding every admitted data class to exactly one trust
  domain, so a domain is always *derived* and never supplied by the caller that
  wants to cross a boundary;
* no fail-open default: an unknown or malformed class raises
  :class:`DataClassificationError` instead of resolving to Workspace or Research
  Core handling.

Issue #464 item 3 records that the repeated ``"SYNTHETIC"`` literal becomes
load-bearing at CW-004. The Workspace modules therefore consume
:func:`synthetic_data_class_value` from this module, and the boundary guard refuses
a repeated classification literal anywhere else in the package.

Domain readings used below, quoted from the ratified planning package: Domain W
holds local clinical workspace state, Domain X is explicit export/admission
staging that "is **not** Research Core", Domain R holds synthetic research
artifacts and MRL evidence, and Workspace access to Domain R is read-only through
versioned interfaces. A `PUBLIC` object held by the Workspace is therefore still
Workspace-held data: its distribution rights are a separate concern, and holding
it does not make it admissible to Domain R.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum

from medscale_workspace.errors import DataClassificationError
from medscale_workspace.versions import DATA_CLASSIFICATION_VERSION


class TrustDomain(StrEnum):
    """One trust domain of the canonically effective clinical workspace planning."""

    RESEARCH_CORE = "ResearchCore"
    WORKSPACE = "Workspace"
    EXPORT_QUARANTINE = "ExportQuarantine"
    EXTERNAL_CONNECTOR = "ExternalConnector"
    PLUGIN_RUNTIME = "PluginRuntime"


class DataClass(StrEnum):
    """Every data class this package may reason about, declared exactly once.

    The first ten members are the ratified classification of the planning package.
    ``OPERATIONAL_TELEMETRY``, ``OPERATIONAL_ANALYTICS`` and ``OPERATIONAL_LOG`` are
    explicit Workspace-domain specializations of the ratified operational-state
    class, declared here so that the telemetry/analytics/log non-evidence boundary
    is typed instead of being decided by string comparison at each call site.
    """

    SYNTHETIC = "SYNTHETIC"
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE_CLINICAL = "SENSITIVE_CLINICAL"
    AUDIO_CLINICAL = "AUDIO_CLINICAL"
    SECRET = "SECRET"
    AUDIT_METADATA = "AUDIT_METADATA"
    OPERATIONAL_TELEMETRY = "OPERATIONAL_TELEMETRY"
    OPERATIONAL_ANALYTICS = "OPERATIONAL_ANALYTICS"
    OPERATIONAL_LOG = "OPERATIONAL_LOG"
    RESEARCH_ARTIFACT = "RESEARCH_ARTIFACT"
    EXPORT_QUARANTINE = "EXPORT_QUARANTINE"


@dataclass(frozen=True, slots=True)
class DataClassAdmission:
    """The canonical binding of one admitted data class to exactly one domain."""

    data_class: DataClass
    domain: TrustDomain
    description: str


DATA_CLASS_ADMISSIONS: tuple[DataClassAdmission, ...] = (
    DataClassAdmission(
        data_class=DataClass.SYNTHETIC,
        domain=TrustDomain.WORKSPACE,
        description="non-PHI synthetic workspace fixture admitted by the CW-001 boundary",
    ),
    DataClassAdmission(
        data_class=DataClass.PUBLIC,
        domain=TrustDomain.WORKSPACE,
        description="public research metadata and public schemas held by the Workspace",
    ),
    DataClassAdmission(
        data_class=DataClass.INTERNAL,
        domain=TrustDomain.WORKSPACE,
        description="application configuration and non-sensitive operational state",
    ),
    DataClassAdmission(
        data_class=DataClass.SENSITIVE_CLINICAL,
        domain=TrustDomain.WORKSPACE,
        description="patient, encounter, note, transcript and FHIR-derived content",
    ),
    DataClassAdmission(
        data_class=DataClass.AUDIO_CLINICAL,
        domain=TrustDomain.WORKSPACE,
        description="encounter recordings and audio chunks",
    ),
    DataClassAdmission(
        data_class=DataClass.SECRET,
        domain=TrustDomain.WORKSPACE,
        description="key material and connector tokens: never a payload, log or prompt class",
    ),
    DataClassAdmission(
        data_class=DataClass.AUDIT_METADATA,
        domain=TrustDomain.WORKSPACE,
        description="append-only logical audit metadata carrying no payload body",
    ),
    DataClassAdmission(
        data_class=DataClass.OPERATIONAL_TELEMETRY,
        domain=TrustDomain.WORKSPACE,
        description="local operational telemetry: not evidence and not research data",
    ),
    DataClassAdmission(
        data_class=DataClass.OPERATIONAL_ANALYTICS,
        domain=TrustDomain.WORKSPACE,
        description="local workspace analytics: not MRL evidence and not a claim",
    ),
    DataClassAdmission(
        data_class=DataClass.OPERATIONAL_LOG,
        domain=TrustDomain.WORKSPACE,
        description="local diagnostics and logs: never a research corpus",
    ),
    DataClassAdmission(
        data_class=DataClass.RESEARCH_ARTIFACT,
        domain=TrustDomain.RESEARCH_CORE,
        description="synthetic or evidence-governed Research Core artifact",
    ),
    DataClassAdmission(
        data_class=DataClass.EXPORT_QUARANTINE,
        domain=TrustDomain.EXPORT_QUARANTINE,
        description="explicit user export awaiting a separate admission decision",
    ),
)

OPERATIONAL_DATA_CLASSES: tuple[DataClass, ...] = (
    DataClass.OPERATIONAL_TELEMETRY,
    DataClass.OPERATIONAL_ANALYTICS,
    DataClass.OPERATIONAL_LOG,
)

SYNTHETIC_DATA_CLASS = DataClass.SYNTHETIC

# A classification document records the domain it *derived*, never a domain the
# document author *chose*. The marker below is required on re-admission so a forged
# document cannot present a caller-supplied domain as canonical state.
DERIVED_DOMAIN_SOURCE = "canonical_data_class_table"

_ADMISSIONS_BY_CLASS = {admission.data_class: admission for admission in DATA_CLASS_ADMISSIONS}
_ADMITTED_DATA_CLASSES = frozenset(DataClass)


def validate_admission_table() -> None:
    """Fail closed unless every admitted data class is bound to exactly one domain."""

    missing = sorted(
        member.value for member in _ADMITTED_DATA_CLASSES if member not in _ADMISSIONS_BY_CLASS
    )
    if missing:
        raise DataClassificationError(
            "the canonical classification table does not bind every admitted data class: "
            + ", ".join(missing)
        )
    if len(DATA_CLASS_ADMISSIONS) != len(_ADMITTED_DATA_CLASSES):
        raise DataClassificationError(
            "the canonical classification table declares a duplicate data-class binding"
        )


validate_admission_table()


def admit_data_class(raw: object) -> DataClass:
    """Return the admitted data class named by ``raw``, or fail closed.

    A raw string is accepted here so a stored classification document can be parsed;
    constructing :class:`DataClassification` directly still requires the typed member.
    """

    if isinstance(raw, DataClass):
        return raw
    if isinstance(raw, str):
        try:
            return DataClass(raw)
        except ValueError as error:
            raise DataClassificationError(f"unknown data class: {raw!r}") from error
    raise DataClassificationError("a data class must be a string or a DataClass member")


def admit_trust_domain(raw: object) -> TrustDomain:
    """Return the admitted trust domain named by ``raw``, or fail closed."""

    if isinstance(raw, TrustDomain):
        return raw
    if isinstance(raw, str):
        try:
            return TrustDomain(raw)
        except ValueError as error:
            raise DataClassificationError(f"unknown trust domain: {raw!r}") from error
    raise DataClassificationError("a trust domain must be a string or a TrustDomain member")


def class_admission_of(data_class: DataClass) -> DataClassAdmission:
    """Return the canonical admission of one data class, failing closed if absent."""

    # A raw string must not be accepted here even though ``DataClass`` is a ``str``
    # enum: ``"SENSITIVE_CLINICAL"`` would otherwise hash and compare equal to the
    # member and silently resolve to a domain without being an admitted member.
    admission = _ADMISSIONS_BY_CLASS.get(_require_data_class_member(data_class))
    if admission is None:
        raise DataClassificationError(
            "the data class is not bound to a trust domain by the canonical table"
        )
    return admission


def domain_of(data_class: DataClass) -> TrustDomain:
    """Return the canonical trust domain of one data class."""

    return class_admission_of(data_class).domain


def _require_data_class_member(raw: object) -> DataClass:
    if not isinstance(raw, DataClass):
        raise DataClassificationError(
            "a data class must be an admitted DataClass member; a raw string is not "
            "accepted here, so a mistyped class cannot resolve to a domain"
        )
    return raw


def _admit_classification_fields(data_class: object, classification_version: object) -> None:
    """Fail closed unless both classification fields are admitted as given."""

    admitted = _require_data_class_member(data_class)
    domain_of(admitted)
    if not isinstance(classification_version, int) or isinstance(classification_version, bool):
        raise DataClassificationError("classification version must be an integer")
    if classification_version != DATA_CLASSIFICATION_VERSION:
        raise DataClassificationError("classification version is not supported here")


@dataclass(frozen=True, slots=True)
class DataClassification:
    """One validated data classification with its derived trust domain."""

    data_class: DataClass
    classification_version: int = DATA_CLASSIFICATION_VERSION

    def __post_init__(self) -> None:
        _admit_classification_fields(self.data_class, self.classification_version)

    @property
    def domain(self) -> TrustDomain:
        """Return the derived trust domain; the caller never supplies this."""

        return domain_of(self.data_class)

    def validated(self) -> DataClassification:
        """Re-check this instance and return it; its fields are normalized on construction."""

        _admit_classification_fields(self.data_class, self.classification_version)
        return self

    def to_document(self) -> dict[str, object]:
        """Return the canonical serialization, including the derived domain."""

        return {
            "classification_version": self.classification_version,
            "data_class": self.data_class.value,
            "domain": self.domain.value,
            "domain_source": DERIVED_DOMAIN_SOURCE,
        }

    def canonical_bytes(self) -> bytes:
        """Return the deterministic ASCII encoding of this classification."""

        encoded = json.dumps(
            self.to_document(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return encoded.encode("ascii")


def classify(data_class: DataClass) -> DataClassification:
    """Build the validated classification of one admitted data class."""

    return DataClassification(data_class=data_class)


def classification_from_document(document: object) -> DataClassification:
    """Re-admit a serialized classification, refusing any caller-supplied domain.

    A document is accepted only when it names the canonical derived-domain marker and
    its recorded domain equals the domain the canonical table derives. A forged or
    hand-edited domain therefore fails closed instead of travelling with the object.
    """

    if not isinstance(document, dict):
        raise DataClassificationError("a stored classification must be a JSON object")
    expected = {"classification_version", "data_class", "domain", "domain_source"}
    if set(document) != expected:
        raise DataClassificationError(
            "a stored classification must contain exactly the four admitted members"
        )
    if document["domain_source"] != DERIVED_DOMAIN_SOURCE:
        raise DataClassificationError(
            "a stored classification must record the canonical derived-domain source"
        )
    raw_data_class = document["data_class"]
    if not isinstance(raw_data_class, str):
        raise DataClassificationError("the stored data class must be a string")
    admitted_class = admit_data_class(raw_data_class)
    classification = DataClassification(
        data_class=admitted_class,
        classification_version=_admitted_version(document["classification_version"]),
    )
    recorded_domain = document["domain"]
    if not isinstance(recorded_domain, str):
        raise DataClassificationError("the stored derived domain must be a string")
    if admit_trust_domain(recorded_domain) is not classification.domain:
        raise DataClassificationError(
            "the stored derived domain contradicts the canonical classification table"
        )
    return classification


def _admitted_version(raw: object) -> int:
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise DataClassificationError("the stored classification version must be an integer")
    return raw


def synthetic_data_class_value() -> str:
    """Return the one canonical wire value of the synthetic data class (Issue #464 item 3)."""

    return SYNTHETIC_DATA_CLASS.value
