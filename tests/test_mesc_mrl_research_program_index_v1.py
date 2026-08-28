"""MRL-0701 tests for the non-authoritative research-program index projection."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._canonical_json_v1 import canonical_sha256
from medscale.mesc._mrl_research_program_index_v1 import (
    RepositoryBinding,
    ResearchProgramIndexError,
    ResearchProgramIndexProjection,
    ResearchProgramNamespace,
    ResearchQuestionIndexEntry,
    SourceBinding,
)

_REGISTRY_PATH = "docs/research/research_program_registry.md"
_QUESTIONS_PATH = "docs/research/research_questions.md"


class _StringSubclass(str):
    pass


def _repository() -> RepositoryBinding:
    return RepositoryBinding(commit_sha="a" * 40, tree_sha="b" * 40)


def _sources() -> tuple[SourceBinding, ...]:
    return (
        SourceBinding(
            path=_REGISTRY_PATH,
            git_blob_sha="c" * 40,
            sha256="d" * 64,
        ),
        SourceBinding(
            path=_QUESTIONS_PATH,
            git_blob_sha="e" * 40,
            sha256="f" * 64,
        ),
    )


def _foundational_questions() -> tuple[ResearchQuestionIndexEntry, ...]:
    return tuple(
        ResearchQuestionIndexEntry(
            question_id=f"RQ{index}",
            program="Foundational MESC research",
            status="OPEN",
            canonical_source_path=_QUESTIONS_PATH,
        )
        for index in range(1, 8)
    )


def _namespace() -> ResearchProgramNamespace:
    return ResearchProgramNamespace(
        program="MESC Research Loop",
        question_namespace="MRL-RQ-<NNNN>",
        program_status="GOVERNED PROGRAM — MRL V1",
        canonical_source_paths=(_REGISTRY_PATH,),
        question_catalog_status=(
            "RESERVED — individual meta-research questions require separate canonicalization"
        ),
    )


def _projection() -> ResearchProgramIndexProjection:
    return ResearchProgramIndexProjection(
        repository=_repository(),
        sources=_sources(),
        questions=_foundational_questions(),
        namespaces=(_namespace(),),
    )


def test_projection_is_deterministic_and_permanently_non_authoritative() -> None:
    first = _projection()
    second = _projection()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.semantic_bytes.endswith(b"\n")
    assert first.to_dict()["schema_version"] == "MRL-RESEARCH-PROGRAM-INDEX-V1"
    assert first.to_dict()["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
    assert first.to_dict()["can_authorize"] is False
    assert first.can_authorize is False
    assert b"generated_at" not in first.semantic_bytes
    assert b"timestamp" not in first.semantic_bytes


def test_projection_binds_exact_repository_and_source_identities() -> None:
    projection = _projection()
    payload = projection.to_dict()

    assert payload["repository"] == {
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
    }
    assert payload["sources"] == [source.to_dict() for source in _sources()]
    assert projection.source_set_sha256 == canonical_sha256(
        [source.to_dict() for source in _sources()]
    )

    changed_source = replace(_sources()[0], sha256="0" * 64)
    changed = ResearchProgramIndexProjection(
        repository=_repository(),
        sources=(changed_source, _sources()[1]),
        questions=_foundational_questions(),
        namespaces=(_namespace(),),
    )
    assert changed.source_set_sha256 != projection.source_set_sha256
    assert changed.semantic_bytes != projection.semantic_bytes


def test_projection_preserves_foundational_rq1_through_rq7_exactly() -> None:
    projection = _projection()
    questions = projection.to_dict()["questions"]

    assert isinstance(questions, list)
    assert [question["question_id"] for question in questions] == [
        "RQ1",
        "RQ2",
        "RQ3",
        "RQ4",
        "RQ5",
        "RQ6",
        "RQ7",
    ]
    assert all(question["is_foundational"] is True for question in questions)
    assert all(question["canonical_source_path"] == _QUESTIONS_PATH for question in questions)

    with pytest.raises(
        ResearchProgramIndexError,
        match="preserve foundational RQ1-RQ7 exactly",
    ):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=_sources(),
            questions=_foundational_questions()[:-1],
            namespaces=(_namespace(),),
        )

    changed_source = replace(
        _foundational_questions()[0],
        canonical_source_path=_REGISTRY_PATH,
    )
    with pytest.raises(
        ResearchProgramIndexError,
        match="must bind the canonical research question source",
    ):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=_sources(),
            questions=(changed_source, *_foundational_questions()[1:]),
            namespaces=(_namespace(),),
        )


def test_registered_namespace_admits_only_namespaced_question_shape() -> None:
    namespaced = ResearchQuestionIndexEntry(
        question_id="MRL-RQ-0001",
        program="MESC Research Loop",
        status="PROPOSED",
        canonical_source_path=_REGISTRY_PATH,
    )
    projection = ResearchProgramIndexProjection(
        repository=_repository(),
        sources=_sources(),
        questions=(namespaced, *_foundational_questions()),
        namespaces=(_namespace(),),
    )
    projected_questions = projection.to_dict()["questions"]

    assert isinstance(projected_questions, list)
    assert projected_questions[0] == namespaced.to_dict()
    assert namespaced.is_foundational is False

    with pytest.raises(
        ResearchProgramIndexError,
        match="not covered by a registered namespace",
    ):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=_sources(),
            questions=(
                ResearchQuestionIndexEntry(
                    question_id="OMNI-RQ-0001",
                    program="Medical Omni",
                    status="PROPOSED",
                    canonical_source_path=_REGISTRY_PATH,
                ),
                *_foundational_questions(),
            ),
            namespaces=(_namespace(),),
        )


@pytest.mark.parametrize("question_id", ("RQ8", "MRL-RQ-1", "mrl-RQ-0001", "PROMOTED"))
def test_invalid_question_identifiers_fail_closed(question_id: str) -> None:
    with pytest.raises(
        ResearchProgramIndexError,
        match="not a canonical MRL research identifier",
    ):
        ResearchQuestionIndexEntry(
            question_id=question_id,
            program="Invalid fixture",
            status="PROPOSED",
            canonical_source_path=_REGISTRY_PATH,
        )


def test_question_and_namespace_identity_text_require_exact_strings() -> None:
    with pytest.raises(ResearchProgramIndexError, match="question_id must be canonical"):
        ResearchQuestionIndexEntry(
            question_id=_StringSubclass("RQ1"),
            program="Foundational MESC research",
            status="OPEN",
            canonical_source_path=_QUESTIONS_PATH,
        )

    with pytest.raises(ResearchProgramIndexError, match="status must be canonical"):
        ResearchQuestionIndexEntry(
            question_id="RQ1",
            program="Foundational MESC research",
            status=_StringSubclass("OPEN"),
            canonical_source_path=_QUESTIONS_PATH,
        )

    with pytest.raises(ResearchProgramIndexError, match="question_namespace must be canonical"):
        ResearchProgramNamespace(
            program="MESC Research Loop",
            question_namespace=_StringSubclass("MRL-RQ-<NNNN>"),
            program_status="GOVERNED PROGRAM — MRL V1",
            canonical_source_paths=(_REGISTRY_PATH,),
            question_catalog_status="RESERVED",
        )


def test_unknown_question_status_fails_closed() -> None:
    with pytest.raises(
        ResearchProgramIndexError,
        match="outside the frozen vocabulary",
    ):
        ResearchQuestionIndexEntry(
            question_id="MRL-RQ-0001",
            program="MESC Research Loop",
            status="PROMOTED",
            canonical_source_path=_REGISTRY_PATH,
        )


def test_unsorted_or_duplicate_identity_arrays_fail_closed() -> None:
    first, second = _sources()
    with pytest.raises(ResearchProgramIndexError, match="sources must be sorted"):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=(second, first),
            questions=_foundational_questions(),
            namespaces=(_namespace(),),
        )

    duplicate = replace(first, sha256="0" * 64)
    with pytest.raises(ResearchProgramIndexError, match="sources must be sorted"):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=(first, duplicate, second),
            questions=_foundational_questions(),
            namespaces=(_namespace(),),
        )

    questions = _foundational_questions()
    with pytest.raises(ResearchProgramIndexError, match="questions must be sorted"):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=_sources(),
            questions=(questions[1], questions[0], *questions[2:]),
            namespaces=(_namespace(),),
        )


def test_projection_cannot_omit_a_referenced_canonical_source() -> None:
    with pytest.raises(
        ResearchProgramIndexError,
        match="omit referenced canonical source",
    ):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=(_sources()[0],),
            questions=_foundational_questions(),
            namespaces=(_namespace(),),
        )


@pytest.mark.parametrize(
    "path",
    (
        "/docs/research/research_questions.md",
        "docs//research/research_questions.md",
        "docs/./research/research_questions.md",
        "docs/../research/research_questions.md",
        "docs\\research\\research_questions.md",
        " docs/research/research_questions.md",
    ),
)
def test_ambiguous_source_paths_fail_closed(path: str) -> None:
    with pytest.raises(ResearchProgramIndexError, match="source path"):
        SourceBinding(path=path, git_blob_sha="a" * 40, sha256="b" * 64)


def test_hash_and_repository_bindings_are_exact_lowercase_hex() -> None:
    with pytest.raises(ResearchProgramIndexError, match="commit_sha"):
        RepositoryBinding(commit_sha="A" * 40, tree_sha="b" * 40)
    with pytest.raises(ResearchProgramIndexError, match="tree_sha"):
        RepositoryBinding(commit_sha="a" * 40, tree_sha="b" * 39)
    with pytest.raises(ResearchProgramIndexError, match="git_blob_sha"):
        SourceBinding(path=_REGISTRY_PATH, git_blob_sha="g" * 40, sha256="b" * 64)
    with pytest.raises(ResearchProgramIndexError, match="sha256"):
        SourceBinding(path=_REGISTRY_PATH, git_blob_sha="a" * 40, sha256="B" * 64)


def test_mutable_collection_substitutions_are_rejected() -> None:
    with pytest.raises(ResearchProgramIndexError, match="sources must be an exact tuple"):
        ResearchProgramIndexProjection(
            repository=_repository(),
            sources=cast(tuple[SourceBinding, ...], list(_sources())),
            questions=_foundational_questions(),
            namespaces=(_namespace(),),
        )

    with pytest.raises(
        ResearchProgramIndexError,
        match="canonical_source_paths must be an exact tuple",
    ):
        ResearchProgramNamespace(
            program="MESC Research Loop",
            question_namespace="MRL-RQ-<NNNN>",
            program_status="GOVERNED PROGRAM — MRL V1",
            canonical_source_paths=cast(
                tuple[str, ...],
                [_REGISTRY_PATH],
            ),
            question_catalog_status="RESERVED",
        )
