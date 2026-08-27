from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchInputClassification,
    ResearchInputDisposition,
    ResearchInputParentRef,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)


def _source_permission(
    *,
    permission_id: str,
    source_artifact_sha256: str,
    source_contract_sha256: str,
    classification: ResearchInputClassification,
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...],
) -> ResearchInputSourcePermission:
    return ResearchInputSourcePermission(
        permission_id=permission_id,
        source_artifact_sha256=source_artifact_sha256,
        source_contract_sha256=source_contract_sha256,
        classification=classification,
        allowed_learning_surfaces=allowed_learning_surfaces,
    )


def _learning_contract(
    classification: ResearchInputClassification = ResearchInputClassification.RESEARCH_ARTIFACT,
) -> ResearchInputAdmissionContract:
    surfaces = (
        ResearchLearningSurface.CAMPAIGN_HISTORY,
        ResearchLearningSurface.OBSERVATION,
    )
    permission = _source_permission(
        permission_id=f"permission-{classification.value.lower()}",
        source_artifact_sha256="b" * 64,
        source_contract_sha256="c" * 64,
        classification=classification,
        allowed_learning_surfaces=surfaces,
    )
    return ResearchInputAdmissionContract(
        input_id="research-input-001",
        classification_policy_sha256="a" * 64,
        classification=classification,
        source_artifact_sha256="b" * 64,
        source_contract_sha256="c" * 64,
        allowed_learning_surfaces=surfaces,
        source_permission=permission,
    )


def _external_contract() -> ResearchInputAdmissionContract:
    permission = _source_permission(
        permission_id="permission-external-evidence",
        source_artifact_sha256="d" * 64,
        source_contract_sha256="e" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        allowed_learning_surfaces=(),
    )
    return ResearchInputAdmissionContract(
        input_id="external-evidence-001",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        source_artifact_sha256="d" * 64,
        source_contract_sha256="e" * 64,
        allowed_learning_surfaces=(),
        source_permission=permission,
    )


def _rejected_contract(
    classification: ResearchInputClassification,
) -> ResearchInputAdmissionContract:
    return ResearchInputAdmissionContract(
        input_id="rejected-input-001",
        classification_policy_sha256="a" * 64,
        classification=classification,
        source_artifact_sha256=None,
        source_contract_sha256=None,
        allowed_learning_surfaces=(),
    )


def _parent_ref(
    *,
    sha_char: str,
    classification: ResearchInputClassification,
    disposition: ResearchInputDisposition,
) -> ResearchInputParentRef:
    if disposition is ResearchInputDisposition.REJECTED:
        parent = ResearchInputAdmissionContract(
            input_id=f"parent-{sha_char}",
            classification_policy_sha256="a" * 64,
            classification=classification,
            source_artifact_sha256=None,
            source_contract_sha256=None,
            allowed_learning_surfaces=(),
        )
    else:
        surfaces = (
            (ResearchLearningSurface.OBSERVATION,)
            if disposition is ResearchInputDisposition.LEARNING_ADMITTED
            else ()
        )
        permission = _source_permission(
            permission_id=f"permission-parent-{sha_char}",
            source_artifact_sha256=sha_char * 64,
            source_contract_sha256="b" * 64,
            classification=classification,
            allowed_learning_surfaces=surfaces,
        )
        parent = ResearchInputAdmissionContract(
            input_id=f"parent-{sha_char}",
            classification_policy_sha256="a" * 64,
            classification=classification,
            source_artifact_sha256=sha_char * 64,
            source_contract_sha256="b" * 64,
            allowed_learning_surfaces=surfaces,
            source_permission=permission,
        )
    reference = ResearchInputParentRef(parent_admission=parent)
    assert reference.disposition is disposition
    return reference


def test_content_identity_is_outside_semantic_preimage() -> None:
    contract = _learning_contract()

    assert b"content_sha256" not in contract.semantic_bytes
    assert "content_sha256" not in contract.semantic_dict()
    assert contract.to_dict()["content_sha256"] == contract.content_sha256
    assert len(contract.content_sha256) == 64


def test_equivalent_admissions_have_byte_stable_identity() -> None:
    first = _learning_contract()
    second = _learning_contract()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256


def test_semantic_envelope_contains_exact_boundary_fields() -> None:
    payload = _learning_contract().semantic_dict()

    assert set(payload) == {
        "format",
        "input_id",
        "classification_policy_sha256",
        "classification",
        "disposition",
        "source_artifact_sha256",
        "source_contract_sha256",
        "allowed_learning_surfaces",
        "source_permission_sha256",
        "transformation_kind",
        "parent_inputs",
    }
    assert payload["format"] == "MRL-RESEARCH-INPUT-ADMISSION-V1"
    assert payload["disposition"] == "LEARNING_ADMITTED"


@pytest.mark.parametrize(
    "classification",
    [
        ResearchInputClassification.RESEARCH_ARTIFACT,
        ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
    ],
)
def test_authorized_research_classes_are_learning_admitted(
    classification: ResearchInputClassification,
) -> None:
    contract = _learning_contract(classification)

    assert contract.disposition is ResearchInputDisposition.LEARNING_ADMITTED
    for surface in (
        ResearchLearningSurface.CAMPAIGN_HISTORY,
        ResearchLearningSurface.OBSERVATION,
    ):
        with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
            contract.require_learning_admission(surface)


def test_learning_admission_is_surface_specific() -> None:
    contract = _learning_contract()

    with pytest.raises(ResearchInputAdmissionError, match="not admitted to learning surface"):
        contract.require_learning_admission(ResearchLearningSurface.PROCEDURE_EXTRACTION)
    with pytest.raises(ResearchInputAdmissionError, match="not admitted to learning surface"):
        contract.require_learning_admission(ResearchLearningSurface.RESEARCH_SEARCH_INDEX)


def test_external_evaluation_evidence_is_read_only_not_learning_state() -> None:
    contract = _external_contract()

    assert contract.disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_external_evaluation_use()
    for surface in ResearchLearningSurface:
        with pytest.raises(ResearchInputAdmissionError, match="not admitted as an MRL learning"):
            contract.require_learning_admission(surface)


@pytest.mark.parametrize(
    "classification",
    [
        ResearchInputClassification.CLINICAL_RUNTIME_STATE,
        ResearchInputClassification.PRODUCT_TELEMETRY,
        ResearchInputClassification.PHI_OR_PATIENT_DATA,
        ResearchInputClassification.CREDENTIAL_OR_PROVIDER_CONTROL_STATE,
        ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
        ResearchInputClassification.UNKNOWN,
    ],
)
def test_rejected_classes_fail_closed_at_every_learning_surface(
    classification: ResearchInputClassification,
) -> None:
    contract = _rejected_contract(classification)

    assert contract.disposition is ResearchInputDisposition.REJECTED
    for surface in ResearchLearningSurface:
        with pytest.raises(ResearchInputAdmissionError, match="not admitted as an MRL learning"):
            contract.require_learning_admission(surface)
    with pytest.raises(ResearchInputAdmissionError, match="not admitted as separately governed"):
        contract.require_external_evaluation_use()


@pytest.mark.parametrize(
    "classification",
    [
        ResearchInputClassification.RESEARCH_ARTIFACT,
        ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
    ],
)
def test_learning_classes_require_exact_source_and_contract_identities(
    classification: ResearchInputClassification,
) -> None:
    with pytest.raises(ResearchInputAdmissionError, match="source artifact and contract"):
        replace(_learning_contract(classification), source_artifact_sha256=None)
    with pytest.raises(ResearchInputAdmissionError, match="source artifact and contract"):
        replace(_learning_contract(classification), source_contract_sha256=None)


def test_learning_classes_require_an_explicit_learning_surface() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="at least one explicit learning surface"):
        replace(_learning_contract(), allowed_learning_surfaces=())


def test_external_evidence_requires_exact_source_and_governing_contract() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="artifact and governing contract"):
        replace(_external_contract(), source_artifact_sha256=None)
    with pytest.raises(ResearchInputAdmissionError, match="artifact and governing contract"):
        replace(_external_contract(), source_contract_sha256=None)


def test_external_evidence_cannot_declare_a_learning_surface() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="cannot enter an MRL learning surface"):
        replace(
            _external_contract(),
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        )


@pytest.mark.parametrize(
    "classification",
    [
        ResearchInputClassification.CLINICAL_RUNTIME_STATE,
        ResearchInputClassification.PRODUCT_TELEMETRY,
        ResearchInputClassification.PHI_OR_PATIENT_DATA,
        ResearchInputClassification.CREDENTIAL_OR_PROVIDER_CONTROL_STATE,
        ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
        ResearchInputClassification.UNKNOWN,
    ],
)
def test_rejected_input_does_not_carry_source_identity_into_mrl(
    classification: ResearchInputClassification,
) -> None:
    base = _rejected_contract(classification)

    with pytest.raises(ResearchInputAdmissionError, match="cannot carry source artifact"):
        replace(base, source_artifact_sha256="f" * 64)
    with pytest.raises(ResearchInputAdmissionError, match="cannot carry source artifact"):
        replace(base, source_contract_sha256="f" * 64)


def test_rejected_input_cannot_declare_a_learning_surface() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="cannot enter an MRL learning surface"):
        replace(
            _rejected_contract(ResearchInputClassification.PRODUCT_TELEMETRY),
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        )


def test_input_identity_and_sha_bindings_fail_closed() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="canonical token"):
        replace(_learning_contract(), input_id="bad input")
    with pytest.raises(ResearchInputAdmissionError, match="64 lowercase hex"):
        replace(_learning_contract(), classification_policy_sha256="A" * 64)
    with pytest.raises(ResearchInputAdmissionError, match="64 lowercase hex"):
        replace(_learning_contract(), source_artifact_sha256="b" * 63)


def test_classification_requires_exact_enum_type() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputClassification"):
        replace(
            _learning_contract(),
            classification="RESEARCH_ARTIFACT",  # type: ignore[arg-type]
        )


def test_learning_surface_requires_exact_enum_type() -> None:
    contract = _learning_contract()

    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchLearningSurface"):
        contract.require_learning_admission("OBSERVATION")  # type: ignore[arg-type]
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchLearningSurface"):
        replace(
            contract,
            allowed_learning_surfaces=("OBSERVATION",),  # type: ignore[arg-type]
        )


def test_learning_surfaces_require_canonical_unique_order() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="unique and strictly sorted"):
        replace(
            _learning_contract(),
            allowed_learning_surfaces=(
                ResearchLearningSurface.OBSERVATION,
                ResearchLearningSurface.CAMPAIGN_HISTORY,
            ),
        )
    with pytest.raises(ResearchInputAdmissionError, match="unique and strictly sorted"):
        replace(
            _learning_contract(),
            allowed_learning_surfaces=(
                ResearchLearningSurface.OBSERVATION,
                ResearchLearningSurface.OBSERVATION,
            ),
        )


def test_learning_surface_collection_requires_exact_tuple() -> None:
    with pytest.raises(ResearchInputAdmissionError, match="exact tuple"):
        replace(
            _learning_contract(),
            allowed_learning_surfaces=[ResearchLearningSurface.OBSERVATION],  # type: ignore[arg-type]
        )


def test_parent_ref_is_derived_from_actual_parent_admission() -> None:
    parent = _rejected_contract(ResearchInputClassification.PHI_OR_PATIENT_DATA)
    reference = ResearchInputParentRef(parent_admission=parent)

    assert reference.admission_sha256 == parent.content_sha256
    assert reference.classification is ResearchInputClassification.PHI_OR_PATIENT_DATA
    assert reference.disposition is ResearchInputDisposition.REJECTED

    with pytest.raises(TypeError):
        ResearchInputParentRef(  # type: ignore[call-arg]
            admission_sha256=parent.content_sha256,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            disposition=ResearchInputDisposition.LEARNING_ADMITTED,
        )


def test_transformation_requires_parent_lineage_and_parent_requires_transformation() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )

    with pytest.raises(ResearchInputAdmissionError, match="at least one parent"):
        replace(_learning_contract(), transformation_kind="summary")
    with pytest.raises(ResearchInputAdmissionError, match="explicit transformation_kind"):
        replace(_learning_contract(), parent_inputs=(parent,))


def test_learning_derivative_of_learning_parent_remains_admissible() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )
    transformed = replace(
        _learning_contract(),
        transformation_kind="deterministic-summary",
        parent_inputs=(parent,),
    )

    assert transformed.disposition is ResearchInputDisposition.LEARNING_ADMITTED
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        transformed.require_learning_admission(ResearchLearningSurface.OBSERVATION)
    assert transformed.content_sha256 != _learning_contract().content_sha256


def test_rejected_parent_cannot_be_laundered_into_learning_input() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.PHI_OR_PATIENT_DATA,
        disposition=ResearchInputDisposition.REJECTED,
    )

    with pytest.raises(ResearchInputAdmissionError, match="rejected parent cannot be transformed"):
        replace(
            _learning_contract(),
            transformation_kind="summary",
            parent_inputs=(parent,),
        )


def test_rejected_parent_cannot_be_laundered_into_external_evidence() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.PRODUCT_TELEMETRY,
        disposition=ResearchInputDisposition.REJECTED,
    )

    with pytest.raises(ResearchInputAdmissionError, match="rejected parent cannot be transformed"):
        replace(
            _external_contract(),
            transformation_kind="summary",
            parent_inputs=(parent,),
        )


def test_external_evidence_parent_cannot_be_laundered_into_learning_input() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        disposition=ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY,
    )

    with pytest.raises(
        ResearchInputAdmissionError,
        match="cannot be transformed into an MRL learning",
    ):
        replace(
            _learning_contract(),
            transformation_kind="summary",
            parent_inputs=(parent,),
        )


def test_external_evidence_derivative_remains_external_evidence_only() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        disposition=ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY,
    )
    transformed = replace(
        _external_contract(),
        transformation_kind="bounded-evaluation-summary",
        parent_inputs=(parent,),
    )

    assert transformed.disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        transformed.require_external_evaluation_use()


def test_parent_inputs_must_be_unique_and_sorted_by_admission_identity() -> None:
    first = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )
    second = _parent_ref(
        sha_char="2",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )
    first, second = sorted((first, second), key=lambda item: item.admission_sha256)

    with pytest.raises(ResearchInputAdmissionError, match="unique and strictly sorted"):
        replace(
            _learning_contract(),
            transformation_kind="merge",
            parent_inputs=(second, first),
        )
    with pytest.raises(ResearchInputAdmissionError, match="unique and strictly sorted"):
        replace(
            _learning_contract(),
            transformation_kind="merge",
            parent_inputs=(first, first),
        )


def test_parent_inputs_require_exact_tuple() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )

    with pytest.raises(ResearchInputAdmissionError, match="exact tuple"):
        replace(
            _learning_contract(),
            transformation_kind="summary",
            parent_inputs=[parent],  # type: ignore[arg-type]
        )


def test_contract_and_parent_ref_are_frozen() -> None:
    contract = _learning_contract()
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )

    with pytest.raises(FrozenInstanceError):
        contract.input_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        parent.parent_admission = _learning_contract()  # type: ignore[misc]


def test_post_construction_classification_mutation_fails_closed() -> None:
    contract = _learning_contract()
    object.__setattr__(contract, "classification", ResearchInputClassification.PHI_OR_PATIENT_DATA)

    with pytest.raises(ResearchInputAdmissionError, match="cannot carry a source permission"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="cannot carry a source permission"):
        _ = contract.content_sha256
    with pytest.raises(ResearchInputAdmissionError, match="cannot carry a source permission"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_post_construction_surface_type_confusion_fails_closed() -> None:
    contract = _learning_contract()
    object.__setattr__(contract, "allowed_learning_surfaces", [ResearchLearningSurface.OBSERVATION])

    with pytest.raises(ResearchInputAdmissionError, match="exact tuple"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="exact tuple"):
        contract.to_dict()


def test_post_construction_nested_parent_mutation_fails_closed() -> None:
    parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )
    contract = replace(
        _learning_contract(),
        transformation_kind="summary",
        parent_inputs=(parent,),
    )
    object.__setattr__(parent.parent_admission, "input_id", "changed-parent")

    with pytest.raises(ResearchInputAdmissionError, match="binding changed"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="binding changed"):
        _ = contract.content_sha256


class _SnapshotBypassAdmission(ResearchInputAdmissionContract):
    def _validated_snapshot(self) -> ResearchInputAdmissionContract:
        return _learning_contract()


def test_subclass_snapshot_override_fails_closed_for_all_public_views_and_gates() -> None:
    base = _learning_contract()
    forged = _SnapshotBypassAdmission(
        input_id=base.input_id,
        classification_policy_sha256=base.classification_policy_sha256,
        classification=base.classification,
        source_artifact_sha256=base.source_artifact_sha256,
        source_contract_sha256=base.source_contract_sha256,
        allowed_learning_surfaces=base.allowed_learning_surfaces,
        source_permission=base.source_permission,
    )

    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        forged.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        _ = forged.semantic_bytes
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        _ = forged.content_sha256
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        forged.to_dict()
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        _ = forged.disposition
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        forged.require_learning_admission(ResearchLearningSurface.OBSERVATION)
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputAdmissionContract"):
        forged.require_external_evaluation_use()


class _SnapshotBypassParentRef(ResearchInputParentRef):
    def _validated_snapshot(self) -> ResearchInputParentRef:
        return _parent_ref(
            sha_char="2",
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            disposition=ResearchInputDisposition.LEARNING_ADMITTED,
        )


def test_parent_ref_subclass_cannot_bypass_admission_snapshot_validation() -> None:
    exact_parent = _parent_ref(
        sha_char="1",
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        disposition=ResearchInputDisposition.LEARNING_ADMITTED,
    )
    contract = replace(
        _learning_contract(),
        transformation_kind="summary",
        parent_inputs=(exact_parent,),
    )
    forged_parent = _SnapshotBypassParentRef(parent_admission=exact_parent.parent_admission)
    object.__setattr__(contract, "parent_inputs", (forged_parent,))

    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputParentRef"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="exact ResearchInputParentRef"):
        _ = contract.content_sha256


def test_untrusted_source_permission_cannot_mint_learning_admission() -> None:
    permission = ResearchInputSourcePermission(
        permission_id="untrusted-permission",
        source_artifact_sha256="8" * 64,
        source_contract_sha256="6" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    contract = ResearchInputAdmissionContract(
        input_id="untrusted-input",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="8" * 64,
        source_contract_sha256="6" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_source_permission_semantics_must_match_admission() -> None:
    permission = _source_permission(
        permission_id="bounded-permission",
        source_artifact_sha256="9" * 64,
        source_contract_sha256="5" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="requested learning surfaces"):
        ResearchInputAdmissionContract(
            input_id="mismatched-input",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="9" * 64,
            source_contract_sha256="5" * 64,
            allowed_learning_surfaces=(ResearchLearningSurface.CAMPAIGN_HISTORY,),
            source_permission=permission,
        )


def test_source_permission_binds_governing_contract_identity() -> None:
    permission = _source_permission(
        permission_id="contract-bound-permission",
        source_artifact_sha256="7" * 64,
        source_contract_sha256="3" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="governing source contract"):
        ResearchInputAdmissionContract(
            input_id="wrong-contract-input",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="7" * 64,
            source_contract_sha256="4" * 64,
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
            source_permission=permission,
        )


def test_source_permission_allows_a_strict_surface_subset() -> None:
    permission = _source_permission(
        permission_id="subset-permission",
        source_artifact_sha256="6" * 64,
        source_contract_sha256="2" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(
            ResearchLearningSurface.CAMPAIGN_HISTORY,
            ResearchLearningSurface.OBSERVATION,
        ),
    )
    contract = ResearchInputAdmissionContract(
        input_id="subset-input",
        classification_policy_sha256="f" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="6" * 64,
        source_contract_sha256="2" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_caller_cannot_mint_canonical_source_permission_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    permission = _source_permission(
        permission_id="caller-minted-permission",
        source_artifact_sha256="4" * 64,
        source_contract_sha256="5" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    contract = ResearchInputAdmissionContract(
        input_id="caller-minted-input",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="4" * 64,
        source_contract_sha256="5" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )
    fake_snapshot = permission_trust.ResearchInputPermissionTrustSnapshot(
        registry_version=permission_trust.TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=frozenset({permission.content_sha256}),
        registry_sha256="f" * 64,
    )
    monkeypatch.setattr(
        permission_trust,
        "TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256",
        frozenset({permission.content_sha256}),
        raising=False,
    )
    monkeypatch.setattr(
        permission_trust,
        "research_input_permission_trust_snapshot",
        lambda: fake_snapshot,
    )
    monkeypatch.setattr(
        permission_trust,
        "validate_research_input_source_permission_trust",
        lambda _value: fake_snapshot,
    )

    assert not hasattr(
        permission_trust,
        "_replace_research_input_permission_trust_registry_for_tests",
    )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_rejected_input_cannot_carry_source_permission() -> None:
    permission = _source_permission(
        permission_id="rejected-mismatch-permission",
        source_artifact_sha256="7" * 64,
        source_contract_sha256="4" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="cannot carry a source permission"):
        ResearchInputAdmissionContract(
            input_id="rejected-with-permission",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.PHI_OR_PATIENT_DATA,
            source_artifact_sha256=None,
            source_contract_sha256=None,
            allowed_learning_surfaces=(),
            source_permission=permission,
        )


def test_permission_mutation_fails_closed_after_trust_admission() -> None:
    contract = _learning_contract()
    assert contract.source_permission is not None
    object.__setattr__(contract.source_permission, "source_contract_sha256", "1" * 64)
    with pytest.raises(ResearchInputAdmissionError, match="governing source contract"):
        contract.semantic_dict()


def test_self_referential_lineage_fails_closed_without_recursion_error() -> None:
    contract = _learning_contract()
    parent = ResearchInputParentRef(parent_admission=contract)
    object.__setattr__(contract, "transformation_kind", "summary")
    object.__setattr__(contract, "parent_inputs", (parent,))
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_mutually_cyclic_lineage_fails_closed_without_recursion_error() -> None:
    first = _learning_contract()
    second = _learning_contract()
    first_ref = ResearchInputParentRef(parent_admission=first)
    second_ref = ResearchInputParentRef(parent_admission=second)
    object.__setattr__(first, "transformation_kind", "summary")
    object.__setattr__(first, "parent_inputs", (second_ref,))
    object.__setattr__(second, "transformation_kind", "summary")
    object.__setattr__(second, "parent_inputs", (first_ref,))
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        first.to_dict()



def _deep_learning_chain(depth: int) -> ResearchInputAdmissionContract:
    """Build one valid linear ancestry for amplification-regression coverage."""
    current = _learning_contract()
    for index in range(depth):
        parent = ResearchInputParentRef(parent_admission=current)
        current = replace(
            _learning_contract(),
            input_id=f"research-input-depth-{index:03d}",
            transformation_kind="summary",
            parent_inputs=(parent,),
        )
    return current


def test_deep_acyclic_lineage_validation_is_bounded_and_deterministic() -> None:
    contract = _deep_learning_chain(96)

    first = contract.semantic_dict()
    second = contract.semantic_dict()
    assert first == second
    assert contract.content_sha256 == contract.to_dict()["content_sha256"]
    assert len(contract.content_sha256) == 64
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_parent_lineage_beyond_depth_limit_fails_closed() -> None:
    current = _deep_learning_chain(128)
    parent = ResearchInputParentRef(parent_admission=current)

    with pytest.raises(ResearchInputAdmissionError, match="depth limit"):
        replace(
            _learning_contract(),
            input_id="research-input-too-deep",
            transformation_kind="summary",
            parent_inputs=(parent,),
        )
