"""Synthetic-only MedScale Clinical Workspace shell for CW-001."""

from __future__ import annotations

from medscale_workspace.app import workspace_snapshot
from medscale_workspace.fixtures import (
    SyntheticEncounter,
    SyntheticPatient,
    synthetic_encounter,
    synthetic_patient,
)
from medscale_workspace.identity import WorkspaceObjectIdentity, WorkspaceObjectType

__all__ = [
    "SyntheticEncounter",
    "SyntheticPatient",
    "WorkspaceObjectIdentity",
    "WorkspaceObjectType",
    "synthetic_encounter",
    "synthetic_patient",
    "workspace_snapshot",
]

__version__ = "0.1.0.dev1"
