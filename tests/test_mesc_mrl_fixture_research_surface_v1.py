from __future__ import annotations

import pytest

from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureCandidate,
    FixtureEvaluator,
    FixtureParameterDomain,
    FixtureParameterValue,
    FixtureResearchSurface,
    FixtureResearchSurfaceError,
    build_fixture_candidate,
    evaluate_fixture_candidate,
)


def _evaluator(
    *,
    targets: tuple[FixtureParameterValue, ...] | None = None,
) -> FixtureEvaluator:
    if targets is None:
        targets = (
            FixtureParameterValue(parameter_id="alpha", value=2),
            FixtureParameterValue(parameter_id="beta", value=10),
        )
    return FixtureEvaluator(
        evaluator_id="toy-evaluator",
        metric_id="exact-target-matches",
        target_values=targets,
    )


def _surface(
    evaluator: FixtureEvaluator,
    *,
    domains: tuple[FixtureParameterDomain, ...] | None = None,
) -> FixtureResearchSurface:
    if domains is None:
        domains = (
            FixtureParameterDomain(parameter_id="alpha", allowed_values=(1, 2, 3)),
            FixtureParameterDomain(parameter_id="beta", allowed_values=(10, 20)),
        )
    return FixtureResearchSurface(
        surface_id="toy-surface",
        parameter_domains=domains,
        evaluator_sha256=evaluator.content_sha256,
    )


def _values(alpha: int = 2, beta: int = 20) -> tuple[FixtureParameterValue, ...]:
    return (
        FixtureParameterValue(parameter_id="alpha", value=alpha),
        FixtureParameterValue(parameter_id="beta", value=beta),
    )


def test_surface_and_evaluator_are_deterministic_and_non_authoritative() -> None:
    evaluator_a = _evaluator()
    evaluator_b = _evaluator()
    surface_a = _surface(evaluator_a)
    surface_b = _surface(evaluator_b)

    assert evaluator_a.semantic_bytes == evaluator_b.semantic_bytes
    assert evaluator_a.content_sha256 == evaluator_b.content_sha256
    assert surface_a.semantic_bytes == surface_b.semantic_bytes
    assert surface_a.content_sha256 == surface_b.content_sha256

    surface_data = surface_a.to_dict()
    evaluator_data = evaluator_a.to_dict()
    assert surface_data["fixture_only"] is True
    assert surface_data["non_evidence"] is True
    assert surface_data["execution_mode"] == "PURE_IN_MEMORY"
    assert surface_data["can_authorize_real_execution"] is False
    assert surface_data["can_authorize_training"] is False
    assert surface_data["can_authorize_model_promotion"] is False
    assert evaluator_data["can_authorize_real_execution"] is False
    assert evaluator_data["can_authorize_training"] is False
    assert evaluator_data["can_authorize_model_promotion"] is False


def test_candidate_build_and_evaluation_are_deterministic() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)

    candidate_a = build_fixture_candidate(surface, _values())
    candidate_b = build_fixture_candidate(surface, _values())
    result_a = evaluate_fixture_candidate(surface, evaluator, candidate_a)
    result_b = evaluate_fixture_candidate(surface, evaluator, candidate_b)

    assert candidate_a.content_sha256 == candidate_b.content_sha256
    assert result_a.content_sha256 == result_b.content_sha256
    assert result_a.score == 1
    assert result_a.max_score == 2
    assert result_a.surface_sha256 == surface.content_sha256
    assert result_a.evaluator_sha256 == evaluator.content_sha256
    assert result_a.candidate_sha256 == candidate_a.content_sha256
    assert result_a.metric_id == "exact-target-matches"
    assert result_a.to_dict()["non_evidence"] is True


def test_perfect_candidate_scores_every_parameter() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    candidate = build_fixture_candidate(surface, _values(alpha=2, beta=10))

    result = evaluate_fixture_candidate(surface, evaluator, candidate)

    assert result.score == result.max_score == 2


def test_candidate_rejects_out_of_domain_value() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="candidate value falls outside",
    ):
        build_fixture_candidate(surface, _values(alpha=99))


def test_candidate_requires_exact_sorted_parameter_coverage() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="candidate values must cover exactly",
    ):
        build_fixture_candidate(
            surface,
            (FixtureParameterValue(parameter_id="alpha", value=2),),
        )

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="strictly sorted",
    ):
        build_fixture_candidate(
            surface,
            (
                FixtureParameterValue(parameter_id="beta", value=10),
                FixtureParameterValue(parameter_id="alpha", value=2),
            ),
        )


def test_parameter_domains_require_exact_sorted_finite_integer_values() -> None:
    with pytest.raises(
        FixtureResearchSurfaceError,
        match="allowed_values must be unique and strictly sorted",
    ):
        FixtureParameterDomain(
            parameter_id="alpha",
            allowed_values=(2, 1),
        )

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="exact integers",
    ):
        FixtureParameterDomain(
            parameter_id="alpha",
            allowed_values=(1, True),
        )

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="bounded fixture range",
    ):
        FixtureParameterDomain(
            parameter_id="alpha",
            allowed_values=(1001,),
        )


def test_surface_rejects_non_fixture_or_evidence_claims() -> None:
    evaluator = _evaluator()
    domains = (
        FixtureParameterDomain(parameter_id="alpha", allowed_values=(1, 2, 3)),
    )

    with pytest.raises(FixtureResearchSurfaceError, match="fixture_only"):
        FixtureResearchSurface(
            surface_id="toy-surface",
            parameter_domains=domains,
            evaluator_sha256=evaluator.content_sha256,
            fixture_only=False,
        )

    with pytest.raises(FixtureResearchSurfaceError, match="non_evidence"):
        FixtureResearchSurface(
            surface_id="toy-surface",
            parameter_domains=domains,
            evaluator_sha256=evaluator.content_sha256,
            non_evidence=False,
        )


def test_surface_requires_sorted_unique_domains() -> None:
    evaluator = _evaluator()

    with pytest.raises(FixtureResearchSurfaceError, match="strictly sorted"):
        _surface(
            evaluator,
            domains=(
                FixtureParameterDomain(parameter_id="beta", allowed_values=(10,)),
                FixtureParameterDomain(parameter_id="alpha", allowed_values=(1,)),
            ),
        )


def test_evaluator_binding_must_match_exact_surface_identity() -> None:
    evaluator = _evaluator()
    other_evaluator = FixtureEvaluator(
        evaluator_id="other-evaluator",
        metric_id="exact-target-matches",
        target_values=evaluator.target_values,
    )
    surface = _surface(evaluator)
    candidate = build_fixture_candidate(surface, _values())

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="does not bind the supplied evaluator",
    ):
        evaluate_fixture_candidate(surface, other_evaluator, candidate)


def test_evaluator_targets_must_cover_exact_surface_domains() -> None:
    evaluator = _evaluator(
        targets=(FixtureParameterValue(parameter_id="alpha", value=2),)
    )
    surface = _surface(evaluator)
    candidate = build_fixture_candidate(surface, _values())

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="target values must cover exactly",
    ):
        evaluate_fixture_candidate(surface, evaluator, candidate)


def test_evaluator_target_must_be_inside_surface_domain() -> None:
    evaluator = _evaluator(
        targets=(
            FixtureParameterValue(parameter_id="alpha", value=99),
            FixtureParameterValue(parameter_id="beta", value=10),
        )
    )
    surface = _surface(evaluator)
    candidate = build_fixture_candidate(surface, _values())

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="target value falls outside",
    ):
        evaluate_fixture_candidate(surface, evaluator, candidate)


def test_candidate_bound_to_another_surface_is_rejected() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    candidate = FixtureCandidate(
        surface_sha256="0" * 64,
        parameter_values=_values(),
    )

    with pytest.raises(
        FixtureResearchSurfaceError,
        match="candidate does not bind",
    ):
        evaluate_fixture_candidate(surface, evaluator, candidate)


def test_semantic_hash_changes_when_material_surface_semantics_change() -> None:
    evaluator = _evaluator()
    surface_a = _surface(evaluator)
    surface_b = _surface(
        evaluator,
        domains=(
            FixtureParameterDomain(parameter_id="alpha", allowed_values=(1, 2, 3, 4)),
            FixtureParameterDomain(parameter_id="beta", allowed_values=(10, 20)),
        ),
    )

    assert surface_a.content_sha256 != surface_b.content_sha256


def test_post_construction_surface_tampering_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    object.__setattr__(surface, "fixture_only", False)

    with pytest.raises(FixtureResearchSurfaceError, match="fixture_only"):
        _ = surface.content_sha256


def test_post_construction_nested_domain_tampering_fails_closed() -> None:
    evaluator = _evaluator()
    surface = _surface(evaluator)
    domain = surface.parameter_domains[0]
    object.__setattr__(domain, "allowed_values", (2, 1))

    with pytest.raises(FixtureResearchSurfaceError, match="strictly sorted"):
        _ = surface.semantic_bytes


def test_post_construction_evaluator_tampering_fails_closed() -> None:
    evaluator = _evaluator()
    object.__setattr__(evaluator, "non_evidence", False)

    with pytest.raises(FixtureResearchSurfaceError, match="non_evidence"):
        _ = evaluator.content_sha256


def test_subclass_cannot_supply_trust_bearing_semantic_view() -> None:
    class DerivedSurface(FixtureResearchSurface):
        pass

    evaluator = _evaluator()
    derived = DerivedSurface(
        surface_id="toy-surface",
        parameter_domains=(
            FixtureParameterDomain(parameter_id="alpha", allowed_values=(1, 2)),
        ),
        evaluator_sha256=evaluator.content_sha256,
    )

    with pytest.raises(FixtureResearchSurfaceError, match="invalid exact type"):
        _ = derived.content_sha256
