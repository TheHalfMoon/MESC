from __future__ import annotations

import pytest

from medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)


def test_mutating_returned_trust_snapshot_cannot_mint_admission_authority() -> None:
    permission = ResearchInputSourcePermission(
        permission_id="snapshot-mutation-probe",
        source_artifact_sha256="4" * 64,
        source_contract_sha256="5" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    contract = ResearchInputAdmissionContract(
        input_id="snapshot-mutation-input",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="4" * 64,
        source_contract_sha256="5" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )

    exposed = permission_trust.research_input_permission_trust_snapshot()
    object.__setattr__(
        exposed,
        "trusted_source_permission_sha256",
        frozenset({permission.content_sha256}),
    )
    assert exposed.admits(permission.content_sha256)

    fresh = permission_trust.research_input_permission_trust_snapshot()
    assert fresh is not exposed
    assert not fresh.admits(permission.content_sha256)
    with pytest.raises(
        permission_trust.ResearchInputPermissionTrustError,
        match="not trusted",
    ):
        permission_trust.validate_research_input_source_permission_trust(
            permission.content_sha256
        )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)
