"""CW-013 acceptance tests: bounded FHIR R4 import/export over synthetic fixtures."""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditTrail,
    DataClass,
    TrustDomain,
    WorkspaceStore,
    classify,
    classify_object,
    guard_object_handoff,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import fhir_r4 as fhir_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    FhirConflictError,
    FhirInputError,
    FhirRevisionError,
    ResearchBackflowError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    SourceKind,
    read_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"
QUARANTINE_ROOT = "/quarantine/domain-x"
RESEARCH_ROOTS = ("/research/core",)


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit_source(store: WorkspaceStore, trail: AuditTrail, locator: str, text: str) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                CORPUS_KEY,
                locator,
                "Synthetic source",
                "rev-00000001",
                "2026-09-01",
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def patient_payload(fhir_id: str = "pat-001") -> str:
    return json.dumps(
        {
            "resourceType": "Patient",
            "id": fhir_id,
            "meta": {"versionId": "1"},
            "active": True,
            "name": "synthetic patient",
            "gender": "unknown",
        }
    )


def observation_payload(patient_id: str = "pat-001", fhir_id: str = "obs-001") -> str:
    return json.dumps(
        {
            "resourceType": "Observation",
            "id": fhir_id,
            "meta": {
                "versionId": "1",
                "security": [
                    {"system": "synthetic-labels", "code": "restricted", "display": "Restricted"}
                ],
            },
            "status": "final",
            "code": "synthetic-panel",
            "subject": "Patient/" + patient_id,
            "valueString": "synthetic value",
        }
    )


def admit_patient(store: WorkspaceStore, trail: AuditTrail, fhir_id: str = "pat-001") -> UUID:
    return UUID(
        str(
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.PATIENT,
                fhir_id,
                patient_payload(fhir_id),
                ACTOR,
                T1,
            ).object_id
        )
    )


def test_supported_resource_set_admits_with_stable_ids(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        patient_id = admit_patient(store, trail)
        assert (
            fhir_mod.resource_id_for(
                WORKSPACE_ALPHA, fhir_mod.FhirResourceType.PATIENT, "pat-001", "1"
            )
            == patient_id
        )
        observation_id = UUID(
            str(
                fhir_mod.admit_resource(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    fhir_mod.FhirResourceType.OBSERVATION,
                    "obs-001",
                    observation_payload(),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        assert fhir_mod.read_resource(store, observation_id).patient_id == "pat-001"
        with pytest.raises(FhirConflictError):
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.PATIENT,
                "pat-001",
                patient_payload(),
                ACTOR,
                T1,
            )


def test_validation_states_stay_separate(tmp_path: Path) -> None:
    report = fhir_mod.validate_payload(
        fhir_mod.FhirResourceType.OBSERVATION, "obs-001", observation_payload()
    )
    assert report.stage("parse").passed is True
    assert report.stage("structure").passed is True
    assert report.stage("profile").passed is True
    assert report.stage("reference").evaluated is False
    assert report.stage("provenance").evaluated is False
    broken = fhir_mod.validate_payload(
        fhir_mod.FhirResourceType.OBSERVATION, "obs-001", "{not json"
    )
    assert broken.stage("parse").passed is False
    assert broken.stage("structure").evaluated is False
    missing = fhir_mod.validate_payload(
        fhir_mod.FhirResourceType.OBSERVATION,
        "obs-001",
        json.dumps({"resourceType": "Observation", "id": "obs-001"}),
    )
    assert missing.stage("parse").passed is True
    assert missing.stage("structure").passed is False
    assert missing.stage("profile").evaluated is False
    stray = json.loads(observation_payload())
    stray["unadmittedMember"] = "nope"
    profiled = fhir_mod.validate_payload(
        fhir_mod.FhirResourceType.OBSERVATION, "obs-001", json.dumps(stray)
    )
    assert profiled.stage("structure").passed is True
    assert profiled.stage("profile").passed is False


def test_workspace_patient_binding_checked(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(FhirInputError):
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.OBSERVATION,
                "obs-orphan",
                json.dumps(
                    {
                        "resourceType": "Observation",
                        "id": "obs-orphan",
                        "status": "final",
                        "code": "synthetic-panel",
                        "valueString": "no subject",
                    }
                ),
                ACTOR,
                T1,
            )
        with pytest.raises(FhirRevisionError):
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.OBSERVATION,
                "obs-ghost",
                observation_payload(patient_id="ghost-001", fhir_id="obs-ghost"),
                ACTOR,
                T1,
            )
        admit_patient(store, trail)
        binding = fhir_mod.admit_resource(
            store,
            trail,
            WORKSPACE_ALPHA,
            fhir_mod.FhirResourceType.OBSERVATION,
            "obs-001",
            observation_payload(),
            ACTOR,
            T1,
        )
        assert fhir_mod.read_resource(store, UUID(str(binding.object_id))).patient_id == "pat-001"


def test_security_labels_retained_where_present(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        admit_patient(store, trail)
        observation_id = UUID(
            str(
                fhir_mod.admit_resource(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    fhir_mod.FhirResourceType.OBSERVATION,
                    "obs-001",
                    observation_payload(),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        stored = fhir_mod.read_resource(store, observation_id)
        assert len(stored.security_labels) == 1
        assert stored.security_labels[0].system == "synthetic-labels"
        assert stored.security_labels[0].code == "restricted"
        assert stored.security_labels[0].display == "Restricted"


def test_fhir_provenance_mapping_where_applicable(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-fhir/origin", "synthetic origin")
        binding = fhir_mod.admit_resource(
            store,
            trail,
            WORKSPACE_ALPHA,
            fhir_mod.FhirResourceType.PATIENT,
            "pat-001",
            patient_payload(),
            ACTOR,
            T1,
            source_id=source_id,
        )
        record = read_provenance(store, binding)
        kinds = [item.kind for item in record.source_refs]
        assert SourceKind.FHIR_RESOURCE in kinds
        assert SourceKind.EVIDENCE_SOURCE in kinds
        locator = [item.locator for item in record.source_refs if item.locator is not None]
        assert "Patient/pat-001" in locator
        record.verify_payload(store.get_object(binding))


def test_malformed_and_unsupported_fail_explicitly(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(FhirInputError):
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.PATIENT,
                "pat-bad",
                "{not json",
                ACTOR,
                T1,
            )
        listed = fhir_mod.validate_payload(
            fhir_mod.FhirResourceType.PATIENT, "pat-x", json.dumps(["a list"])
        )
        assert listed.stage("parse").passed is True
        assert listed.stage("structure").passed is False
        with pytest.raises(ValueError):
            fhir_mod.FhirResourceType("Medication")
        with pytest.raises(FhirRevisionError):
            fhir_mod.admit_resource(
                store,
                trail,
                WORKSPACE_ALPHA,
                fhir_mod.FhirResourceType.CONDITION,
                "cond-001",
                json.dumps(
                    {
                        "resourceType": "Condition",
                        "id": "cond-001",
                        "code": "synthetic-condition",
                        "subject": "Patient/ghost-001",
                    }
                ),
                ACTOR,
                T1,
            )


def test_offline_persistence_across_reopen(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())
    with WorkspaceStore.open(
        store_root=str(tmp_path),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    ) as store:
        trail = AuditTrail(store)
        patient_id = admit_patient(store, trail)
    with WorkspaceStore.open(
        store_root=str(tmp_path),
        workspace_id=WORKSPACE_ALPHA,
        key_provider=provider,
        application_version=APPLICATION_VERSION,
    ) as store:
        stored = fhir_mod.read_resource(store, patient_id)
        assert stored.fhir_id == "pat-001"
        assert stored.resource_version == "1"


def test_export_stages_domain_x_envelope(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        patient_id = admit_patient(store, trail)
        observation_id = UUID(
            str(
                fhir_mod.admit_resource(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    fhir_mod.FhirResourceType.OBSERVATION,
                    "obs-001",
                    observation_payload(),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        envelope, manifest = fhir_mod.stage_fhir_export(
            store,
            trail,
            WORKSPACE_ALPHA,
            (patient_id, observation_id),
            QUARANTINE_ROOT + "/fhir-export-001.json",
            QUARANTINE_ROOT,
            RESEARCH_ROOTS,
            ACTOR,
            T2,
        )
        assert envelope.entry_count == 2
        assert envelope.manifest_digest.startswith("sha256:")
        document = json.loads(manifest.decode("ascii"))
        assert document["bundle_type"] == "transaction"
        assert document["entry_count"] == 2
        assert trail.head() is not None
        with pytest.raises(FhirInputError):
            fhir_mod.stage_fhir_export(
                store,
                trail,
                WORKSPACE_ALPHA,
                (patient_id,),
                "/research/core/fhir-export-001.json",
                QUARANTINE_ROOT,
                RESEARCH_ROOTS,
                ACTOR,
                T2,
            )
        classified = classify_object(
            binding=fhir_mod.resource_binding(WORKSPACE_ALPHA, patient_id),
            classification=classify(DataClass.SYNTHETIC),
            payload=b"synthetic-payload",
        )
        with pytest.raises(ResearchBackflowError):
            guard_object_handoff(classified, TrustDomain.RESEARCH_CORE)
