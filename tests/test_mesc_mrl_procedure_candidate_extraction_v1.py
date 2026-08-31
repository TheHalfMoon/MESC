"""MRL-0402 tests for governed procedure-candidate extraction."""

from __future__ import annotations

import pytest

import medscale.mesc._mrl_procedure_candidate_extraction_v1 as extraction_module
from medscale.mesc._mrl_procedure_candidate_extraction_v1 import (
    ProcedureCandidateExtraction,
    ProcedureCandidateExtractionError,
    ProcedureCandidateReference,
    extract_procedure_candidates,
)
from medscale.mesc._mrl_research_campaign_v1 import CampaignNodeKind, ResearchCampaign
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
from test_mesc_mrl_research_campaign_v1 import _base_nodes, _campaign, _node


def _candidate_campaign() -> ResearchCampaign:
    nodes = tuple(
        sorted(
            (
                *_base_nodes(),
                _node(
                    "procedure-a",
                    CampaignNodeKind.PROCEDURE_CANDIDATE,
                    "1" * 64,
                    ("decision-a",),
                ),
            ),
            key=lambda node: node.node_id,
        )
    )
    return _campaign(nodes=nodes, procedure_candidates=("procedure-a",))


def _untrusted_procedure_admission() -> ResearchInputAdmissionContract:
    permission = ResearchInputSourcePermission(
        permission_id="procedure-extraction-fixture",
        source_artifact_sha256="2" * 64,
        source_contract_sha256="3" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.PROCEDURE_EXTRACTION,),
    )
    return ResearchInputAdmissionContract(
        input_id="procedure-extraction-input",
        classification_policy_sha256="4" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="2" * 64,
        source_contract_sha256="3" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.PROCEDURE_EXTRACTION,),
        source_permission=permission,
    )


def test_current_empty_trust_registry_blocks_candidate_extraction() -> None:
    campaign = _candidate_campaign()
    admission = _untrusted_procedure_admission()

    with pytest.raises(ProcedureCandidateExtractionError, match="not canonically admitted"):
        extract_procedure_candidates(campaign, admission)


def test_extraction_uses_one_campaign_snapshot_if_live_campaign_drifts_mid_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    campaign = _candidate_campaign()
    admission = _untrusted_procedure_admission()
    original_build_history = extraction_module.build_campaign_history_projection
    mutation_performed = False

    def bypass_trust_for_fixture(
        self: ResearchInputAdmissionContract,
        surface: ResearchLearningSurface,
    ) -> None:
        assert self is admission
        assert surface is ResearchLearningSurface.PROCEDURE_EXTRACTION

    def mutate_live_campaign_then_build_snapshot(snapshot: ResearchCampaign):
        nonlocal mutation_performed
        if not mutation_performed:
            mutation_performed = True
            candidate_node = next(
                node for node in campaign.nodes if node.node_id == "procedure-a"
            )
            object.__setattr__(candidate_node, "artifact_sha256", "9" * 64)
        return original_build_history(snapshot)

    monkeypatch.setattr(
        ResearchInputAdmissionContract,
        "require_learning_admission",
        bypass_trust_for_fixture,
    )
    monkeypatch.setattr(
        extraction_module,
        "build_campaign_history_projection",
        mutate_live_campaign_then_build_snapshot,
    )

    extraction = extract_procedure_candidates(campaign, admission)

    assert mutation_performed is True
    assert extraction.candidates[0].artifact_sha256 == "1" * 64
    assert next(
        node for node in campaign.nodes if node.node_id == "procedure-a"
    ).artifact_sha256 == "9" * 64


def test_admission_identity_drift_between_trust_passes_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admission = _untrusted_procedure_admission()
    identities = iter(("a" * 64, "b" * 64))

    def bypass_trust_for_fixture(
        self: ResearchInputAdmissionContract,
        surface: ResearchLearningSurface,
    ) -> None:
        assert self is admission
        assert surface is ResearchLearningSurface.PROCEDURE_EXTRACTION

    def unstable_content_sha256(self: ResearchInputAdmissionContract) -> str:
        assert self is admission
        return next(identities)

    monkeypatch.setattr(
        ResearchInputAdmissionContract,
        "require_learning_admission",
        bypass_trust_for_fixture,
    )
    monkeypatch.setattr(
        ResearchInputAdmissionContract,
        "content_sha256",
        property(unstable_content_sha256),
    )

    with pytest.raises(ProcedureCandidateExtractionError, match="identity changed"):
        extraction_module._stable_learning_admission_sha256(admission)


def test_extraction_artifact_is_deterministic_and_non_authoritative() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )
    first = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )
    second = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.candidates[0].artifact_sha256 == "b" * 64
    assert first.can_review_procedure is False
    assert first.can_admit_procedure is False
    assert first.can_authorize is False
    assert b"ADMITTED" not in first.semantic_bytes
    assert b"PROMOTED" not in first.semantic_bytes


def test_duplicate_candidate_reference_fails_closed() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )

    with pytest.raises(ProcedureCandidateExtractionError, match="unique and sorted"):
        ProcedureCandidateExtraction(
            history_projection_sha256="c" * 64,
            input_admission_sha256="d" * 64,
            candidates=(reference, reference),
        )


def test_mutated_candidate_reference_fails_closed_on_semantic_and_hash_views() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )
    extraction = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )
    object.__setattr__(reference, "artifact_sha256", "invalid")

    with pytest.raises(ProcedureCandidateExtractionError, match="64 lowercase hex"):
        extraction.semantic_dict()
    with pytest.raises(ProcedureCandidateExtractionError, match="64 lowercase hex"):
        _ = extraction.content_sha256


def test_valid_candidate_reference_identity_mutation_fails_closed() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )
    extraction = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )
    object.__setattr__(reference, "artifact_sha256", "f" * 64)

    with pytest.raises(ProcedureCandidateExtractionError, match="identity changed"):
        reference.to_dict()
    with pytest.raises(ProcedureCandidateExtractionError, match="identity changed"):
        _ = extraction.content_sha256


def test_mutated_extraction_identity_fails_closed_on_semantic_and_hash_views() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )
    extraction = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )
    object.__setattr__(extraction, "history_projection_sha256", "invalid")

    with pytest.raises(ProcedureCandidateExtractionError, match="64 lowercase hex"):
        extraction.semantic_dict()
    with pytest.raises(ProcedureCandidateExtractionError, match="64 lowercase hex"):
        _ = extraction.content_sha256


def test_valid_extraction_identity_mutation_fails_closed() -> None:
    reference = ProcedureCandidateReference(
        sequence_index=0,
        campaign_sha256="a" * 64,
        node_id="procedure-a",
        artifact_sha256="b" * 64,
    )
    extraction = ProcedureCandidateExtraction(
        history_projection_sha256="c" * 64,
        input_admission_sha256="d" * 64,
        candidates=(reference,),
    )
    object.__setattr__(extraction, "history_projection_sha256", "f" * 64)

    with pytest.raises(ProcedureCandidateExtractionError, match="identity changed"):
        extraction.semantic_dict()
    with pytest.raises(ProcedureCandidateExtractionError, match="identity changed"):
        _ = extraction.content_sha256


def test_wrong_input_types_fail_closed_before_admission() -> None:
    admission = _untrusted_procedure_admission()
    campaign = _candidate_campaign()

    with pytest.raises(ProcedureCandidateExtractionError, match="exact ResearchCampaign"):
        extract_procedure_candidates(object(), admission)  # type: ignore[arg-type]
    with pytest.raises(
        ProcedureCandidateExtractionError,
        match="exact ResearchInputAdmissionContract",
    ):
        extract_procedure_candidates(campaign, object())  # type: ignore[arg-type]
