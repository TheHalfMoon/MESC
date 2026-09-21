"""Synthetic patient and encounter fixtures for CW-001."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from medscale_workspace.identity import (
    WorkspaceObjectIdentity,
    WorkspaceObjectType,
    synthetic_identity,
)

SYNTHETIC_WORKSPACE_ID = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")


@dataclass(frozen=True, slots=True)
class SyntheticPatient:
    """Non-PHI patient fixture used only for boundary and UI-shell tests."""

    identity: WorkspaceObjectIdentity
    display_name: str = "Synthetic Patient Alpha"
    data_class: str = "SYNTHETIC"


@dataclass(frozen=True, slots=True)
class SyntheticEncounter:
    """Non-PHI encounter fixture linked to the synthetic patient."""

    identity: WorkspaceObjectIdentity
    patient_id: UUID
    encounter_label: str = "Synthetic Encounter 001"
    data_class: str = "SYNTHETIC"


def synthetic_patient() -> SyntheticPatient:
    identity = synthetic_identity(
        SYNTHETIC_WORKSPACE_ID,
        WorkspaceObjectType.PATIENT,
        "patient-alpha",
    )
    return SyntheticPatient(identity=identity)


def synthetic_encounter(patient: SyntheticPatient | None = None) -> SyntheticEncounter:
    fixture_patient = patient or synthetic_patient()
    if fixture_patient.identity.workspace_id != SYNTHETIC_WORKSPACE_ID:
        raise ValueError("patient must belong to the synthetic workspace")
    identity = synthetic_identity(
        SYNTHETIC_WORKSPACE_ID,
        WorkspaceObjectType.ENCOUNTER,
        "encounter-001",
    )
    return SyntheticEncounter(
        identity=identity,
        patient_id=fixture_patient.identity.object_id,
    )
