from __future__ import annotations

import pytest

from medscale.mesc import _mrl_research_input_admission_v1 as admission
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
            permission.content_sha256,
        )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_consumer_module_rebinding_cannot_mint_admission_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning_permission = ResearchInputSourcePermission(
        permission_id="consumer-rebind-learning",
        source_artifact_sha256="6" * 64,
        source_contract_sha256="7" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    learning = ResearchInputAdmissionContract(
        input_id="consumer-rebind-learning-input",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="6" * 64,
        source_contract_sha256="7" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=learning_permission,
    )
    external_permission = ResearchInputSourcePermission(
        permission_id="consumer-rebind-external",
        source_artifact_sha256="8" * 64,
        source_contract_sha256="9" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        allowed_learning_surfaces=(),
    )
    external = ResearchInputAdmissionContract(
        input_id="consumer-rebind-external-input",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        source_artifact_sha256="8" * 64,
        source_contract_sha256="9" * 64,
        allowed_learning_surfaces=(),
        source_permission=external_permission,
    )
    forged = permission_trust.ResearchInputPermissionTrustSnapshot(
        registry_version=permission_trust.TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=frozenset(
            {
                learning_permission.content_sha256,
                external_permission.content_sha256,
            }
        ),
        registry_sha256="f" * 64,
    )

    assert not hasattr(admission, "_canonical_permission_trust_snapshot")
    assert not hasattr(admission, "_canonical_validate_permission_trust")
    monkeypatch.setattr(
        admission,
        "_canonical_permission_trust_snapshot",
        lambda: forged,
        raising=False,
    )
    monkeypatch.setattr(
        admission,
        "_canonical_validate_permission_trust",
        lambda _value: forged,
        raising=False,
    )

    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        learning.require_learning_admission(ResearchLearningSurface.OBSERVATION)
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        external.require_external_evaluation_use()


def test_mutating_trust_gate_defaults_cannot_mint_admission_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    learning_permission = ResearchInputSourcePermission(
        permission_id="default-mutation-learning",
        source_artifact_sha256="1" * 64,
        source_contract_sha256="2" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    learning = ResearchInputAdmissionContract(
        input_id="default-mutation-learning-input",
        classification_policy_sha256="c" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="1" * 64,
        source_contract_sha256="2" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=learning_permission,
    )
    external_permission = ResearchInputSourcePermission(
        permission_id="default-mutation-external",
        source_artifact_sha256="3" * 64,
        source_contract_sha256="4" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        allowed_learning_surfaces=(),
    )
    external = ResearchInputAdmissionContract(
        input_id="default-mutation-external-input",
        classification_policy_sha256="d" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        source_artifact_sha256="3" * 64,
        source_contract_sha256="4" * 64,
        allowed_learning_surfaces=(),
        source_permission=external_permission,
    )
    forged = permission_trust.ResearchInputPermissionTrustSnapshot(
        registry_version=permission_trust.TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=frozenset(
            {
                learning_permission.content_sha256,
                external_permission.content_sha256,
            }
        ),
        registry_sha256="e" * 64,
    )
    gate = admission._require_admission_graph_trust
    assert gate.__defaults__ is None
    monkeypatch.setattr(gate, "__defaults__", (lambda _value: forged,))

    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        learning.require_learning_admission(ResearchLearningSurface.OBSERVATION)
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        external.require_external_evaluation_use()
