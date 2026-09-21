"""Pure local application-shell projection for CW-001."""

from __future__ import annotations

from medscale_workspace.fixtures import synthetic_encounter, synthetic_patient


def workspace_snapshot() -> dict[str, object]:
    """Return a deterministic synthetic shell snapshot without I/O or network access."""

    patient = synthetic_patient()
    encounter = synthetic_encounter(patient)
    return {
        "workspace_id": str(patient.identity.workspace_id),
        "data_class": "SYNTHETIC",
        "patient": {
            "object_id": str(patient.identity.object_id),
            "object_type": patient.identity.object_type.value,
            "display_name": patient.display_name,
        },
        "encounter": {
            "object_id": str(encounter.identity.object_id),
            "object_type": encounter.identity.object_type.value,
            "patient_id": str(encounter.patient_id),
            "label": encounter.encounter_label,
        },
        "capabilities": {
            "network": False,
            "microphone": False,
            "ehr": False,
            "external_model": False,
            "persistent_write": True,
        },
        "storage": {
            "engine": "sqlite3",
            "payload_encryption": "AES-256-GCM",
            "key_derivation": "HKDF-SHA-256",
            "plaintext_fallback": False,
            "platform_key_provider": "unavailable-fail-closed",
        },
    }
