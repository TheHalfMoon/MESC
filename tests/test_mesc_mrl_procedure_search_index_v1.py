"""MRL-0408 tests for rebuildable non-authoritative procedure search indexing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_procedure_registry_v1 import (
    ProcedureRegistry,
    invalidate_admitted_procedure,
    register_procedure_admission,
)
from medscale.mesc._mrl_procedure_search_index_v1 import (
    ProcedureSearchIndexError,
    build_procedure_search_index,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
from test_mesc_mrl_procedure_registry_v1 import _gate_result


def _admission_for_result(label: str, result: object) -> ResearchInputAdmissionContract:
    admitted = result.admitted_procedure  # type: ignore[attr-defined]
    assert admitted is not None
    source_sha256 = admitted.content_sha256
    permission = ResearchInputSourcePermission(
        permission_id=f"search-index-{label}",
        source_artifact_sha256=source_sha256,
        source_contract_sha256="a" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.RESEARCH_SEARCH_INDEX,),
    )
    return ResearchInputAdmissionContract(
        input_id=f"search-index-input-{label}",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256=source_sha256,
        source_contract_sha256="a" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.RESEARCH_SEARCH_INDEX,),
        source_permission=permission,
    )


def _allow_index_fixture_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fixture_gate(
        self: ResearchInputAdmissionContract,
        surface: ResearchLearningSurface,
    ) -> None:
        assert surface is ResearchLearningSurface.RESEARCH_SEARCH_INDEX
        assert surface in self.allowed_learning_surfaces

    monkeypatch.setattr(
        ResearchInputAdmissionContract,
        "require_learning_admission",
        fixture_gate,
    )


def test_production_empty_input_trust_blocks_active_procedure_indexing() -> None:
    admitted = _gate_result("index-untrusted")
    registry = register_procedure_admission(ProcedureRegistry(), admitted)
    admission = _admission_for_result("untrusted", admitted)

    with pytest.raises(ProcedureSearchIndexError, match="not canonically admitted"):
        build_procedure_search_index(registry, (admission,))


def test_rebuild_is_deterministic_and_non_authoritative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    first_result = _gate_result("index-alpha")
    second_result = _gate_result("index-beta")
    registry = register_procedure_admission(ProcedureRegistry(), first_result)
    registry = register_procedure_admission(registry, second_result)
    admissions = (
        _admission_for_result("alpha", first_result),
        _admission_for_result("beta", second_result),
    )

    first = build_procedure_search_index(registry, admissions)
    second = build_procedure_search_index(registry, tuple(reversed(admissions)))

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert len(first.entries) == 2
    assert first.can_admit_procedure is False
    assert first.can_authorize_model_promotion is False
    assert first.semantic_dict()["authoritative"] is False


def test_search_is_deterministic_and_uses_derived_procedure_terms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("search-target")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    admission = _admission_for_result("target", result)
    index = build_procedure_search_index(registry, (admission,))

    procedure = result.admitted_procedure
    assert procedure is not None
    query = procedure.applicability_bounds.task_types[0]
    matches = index.search(query)

    assert len(matches) == 1
    assert matches[0].procedure_sha256 == result.procedure_sha256
    assert matches[0].admitted_procedure_sha256 == procedure.content_sha256
    assert index.search(query) == matches


def test_invalidated_procedure_disappears_on_complete_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    active = _gate_result("index-active")
    invalidated_result = _gate_result("index-invalidated")
    registry = register_procedure_admission(ProcedureRegistry(), active)
    registry = register_procedure_admission(registry, invalidated_result)
    registry = invalidate_admitted_procedure(
        registry,
        invalidated_result.procedure_sha256,
        evidence_sha256s=("c" * 64,),
        reason="Later boundary evidence invalidated reuse.",
    )

    index = build_procedure_search_index(
        registry,
        (_admission_for_result("active", active),),
    )

    assert tuple(entry.procedure_sha256 for entry in index.entries) == (
        active.procedure_sha256,
    )
    assert invalidated_result.procedure_sha256 not in (
        entry.procedure_sha256 for entry in index.entries
    )


def test_every_active_procedure_requires_exact_input_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    first = _gate_result("index-missing-a")
    second = _gate_result("index-missing-b")
    registry = register_procedure_admission(ProcedureRegistry(), first)
    registry = register_procedure_admission(registry, second)

    with pytest.raises(ProcedureSearchIndexError, match="every active admitted"):
        build_procedure_search_index(
            registry,
            (_admission_for_result("only-a", first),),
        )


def test_extra_admission_for_non_active_procedure_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    active = _gate_result("index-extra-active")
    other = _gate_result("index-extra-other")
    registry = register_procedure_admission(ProcedureRegistry(), active)

    with pytest.raises(ProcedureSearchIndexError, match="non-active"):
        build_procedure_search_index(
            registry,
            (
                _admission_for_result("active", active),
                _admission_for_result("other", other),
            ),
        )


def test_admission_must_bind_exact_admitted_procedure_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("index-wrong-artifact")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    admission = _admission_for_result("wrong", result)
    permission = admission.source_permission
    assert permission is not None
    wrong_permission = replace(
        permission,
        source_artifact_sha256="d" * 64,
    )
    wrong_admission = replace(
        admission,
        source_artifact_sha256="d" * 64,
        source_permission=wrong_permission,
    )

    with pytest.raises(ProcedureSearchIndexError, match="every active admitted"):
        build_procedure_search_index(registry, (wrong_admission,))


def test_registry_mutation_invalidates_existing_index_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("index-registry-drift")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    admission = _admission_for_result("drift", result)
    index = build_procedure_search_index(registry, (admission,))
    object.__setattr__(registry.events[0], "reason", "Different valid registry reason.")

    with pytest.raises(ProcedureSearchIndexError, match="registry failed"):
        _ = index.content_sha256


def test_input_admission_mutation_invalidates_existing_index_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("index-admission-drift")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    admission = _admission_for_result("admission-drift", result)
    index = build_procedure_search_index(registry, (admission,))
    object.__setattr__(admission, "input_id", "different-valid-input-id")

    with pytest.raises(ProcedureSearchIndexError):
        _ = index.semantic_dict()


def test_index_entry_mutation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("index-entry-drift")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    index = build_procedure_search_index(
        registry,
        (_admission_for_result("entry-drift", result),),
    )
    object.__setattr__(index.entries[0], "procedure_sha256", "e" * 64)

    with pytest.raises(ProcedureSearchIndexError):
        _ = index.content_sha256
