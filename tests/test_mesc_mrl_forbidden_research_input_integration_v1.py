"""MRL-0212 integration tests for forbidden research-input admission."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchInputClassification,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_structured_fixture_observation_v1 import FixtureObservationError
from test_mesc_mrl_structured_fixture_observation_v1 import _success_observation

_FORBIDDEN_INPUTS = (
    ResearchInputClassification.CLINICAL_RUNTIME_STATE,
    ResearchInputClassification.PRODUCT_TELEMETRY,
    ResearchInputClassification.PHI_OR_PATIENT_DATA,
)
_PROTECTED_LEARNING_SURFACES = (
    ResearchLearningSurface.OBSERVATION,
    ResearchLearningSurface.CAMPAIGN_HISTORY,
    ResearchLearningSurface.PROCEDURE_EXTRACTION,
    ResearchLearningSurface.RESEARCH_SEARCH_INDEX,
)


def _rejected_admission(
    classification: ResearchInputClassification,
) -> ResearchInputAdmissionContract:
    return ResearchInputAdmissionContract(
        input_id=f"mrl-0212-{classification.value.lower()}",
        classification_policy_sha256="e" * 64,
        classification=classification,
        source_artifact_sha256=None,
        source_contract_sha256=None,
        allowed_learning_surfaces=(),
    )


@pytest.mark.parametrize(
    "classification",
    _FORBIDDEN_INPUTS,
    ids=lambda item: item.value.lower(),
)
def test_forbidden_input_cannot_enter_structured_observation(
    classification: ResearchInputClassification,
) -> None:
    with pytest.raises(
        FixtureObservationError,
        match="structurally learning-admitted",
    ):
        replace(
            _success_observation(),
            input_admission=_rejected_admission(classification),
        )


@pytest.mark.parametrize(
    "classification",
    _FORBIDDEN_INPUTS,
    ids=lambda item: item.value.lower(),
)
@pytest.mark.parametrize(
    "surface",
    _PROTECTED_LEARNING_SURFACES,
    ids=lambda item: item.value.lower(),
)
def test_forbidden_input_cannot_enter_any_protected_learning_surface(
    classification: ResearchInputClassification,
    surface: ResearchLearningSurface,
) -> None:
    admission = _rejected_admission(classification)

    with pytest.raises(
        ResearchInputAdmissionError,
        match="input is not admitted as an MRL learning signal",
    ):
        admission.require_learning_admission(surface)
