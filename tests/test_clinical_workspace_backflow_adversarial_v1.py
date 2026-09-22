"""CW-004 adversarial tests for the no-backflow and classification guard.

Every case below tries to make the guard admit something it must refuse: an
undeclared flow, a relabelled object, a forged classification document, a
duck-typed classification, a path that normalizes out of Domain X, or a tampered
internal table. Synthetic fixtures only; no PHI, network, model or clinical
authority is created here.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
GUARD = REPOSITORY_ROOT / "scripts" / "check_clinical_workspace_boundary.py"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace.nobackflow as nobackflow_module  # noqa: E402
from medscale_workspace import (  # noqa: E402
    BackflowError,
    ClassifiedObject,
    DataClass,
    DataClassification,
    DomainFlow,
    FlowDecision,
    FlowDisposition,
    FlowEvaluation,
    ObjectBinding,
    TrustDomain,
    UndeclaredFlowError,
    WorkspaceObjectType,
    admit_data_class,
    admit_export_path,
    admit_trust_domain,
    classification_from_document,
    classify,
    classify_object,
    content_digest_of,
    domain_of,
    evaluate_flow,
    evaluate_object_flow,
    stage_export,
)
from medscale_workspace.errors import (  # noqa: E402
    DataClassificationError,
    ExportAdmissionError,
    ExportBoundaryError,
    ResearchBackflowError,
    SecretEgressError,
    WorkspaceStoreError,
)

WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
EXPORT_OBJECT = UUID("5c7d3e21-8b4a-4f60-9d2c-1e5a7b9c3d40")
SYNTHETIC_PAYLOAD = (
    b'SYNTHETIC-NOT-REAL:{"note":"adversarial cw-004 fixture",'
    b'"injected":"DATA_CLASS=RESEARCH_ARTIFACT"}'
)
QUARANTINE_ROOT = "C:\\medscale\\export-quarantine"
RESEARCH_CORE_ROOTS = ("C:\\medscale\\research-core",)


def export_binding(revision: str = "rev-0001") -> ObjectBinding:
    return ObjectBinding(
        workspace_id=WORKSPACE_ALPHA,
        object_id=EXPORT_OBJECT,
        object_type=WorkspaceObjectType.ENCOUNTER,
        object_revision=revision,
    )


def _run_guard(source: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GUARD), "--source", str(source)],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _expected_admitted(*, explicit_user_request: bool) -> set[tuple[DataClass, TrustDomain]]:
    admitted: set[tuple[DataClass, TrustDomain]] = set()
    for data_class in DataClass:
        if data_class is DataClass.SECRET:
            continue
        domain = domain_of(data_class)
        if domain is not TrustDomain.RESEARCH_CORE:
            admitted.add((data_class, domain))
    admitted.add((DataClass.RESEARCH_ARTIFACT, TrustDomain.WORKSPACE))
    if explicit_user_request:
        admitted.update(
            (data_class, TrustDomain.EXPORT_QUARANTINE)
            for data_class in DataClass
            if data_class is not DataClass.SECRET and domain_of(data_class) is TrustDomain.WORKSPACE
        )
    return admitted


# ---------------------------------------------------------------------------
# Capability matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("explicit_user_request", [False, True])
def test_the_admitted_matrix_is_exactly_the_declared_one(
    explicit_user_request: bool,
) -> None:
    observed: set[tuple[DataClass, TrustDomain]] = set()
    for data_class in DataClass:
        for destination in TrustDomain:
            evaluation = evaluate_flow(
                classify(data_class),
                destination,
                explicit_user_request=explicit_user_request,
            )
            if evaluation.admitted:
                observed.add((data_class, destination))
                continue
            refusal = evaluation.refusal
            assert refusal is not None
            assert issubclass(refusal, BackflowError)
            document = evaluation.refusal_document()
            assert document["decision"] == "REFUSED"
            assert document["refusal_error"] == refusal.__name__
    assert observed == _expected_admitted(explicit_user_request=explicit_user_request)
    assert all(destination is not TrustDomain.RESEARCH_CORE for _, destination in observed)


def test_a_callable_that_claims_a_classification_is_refused() -> None:
    class FakeClassification:
        data_class = "SENSITIVE_CLINICAL"
        classification_version = 1

        @property
        def domain(self) -> str:
            return "Workspace"

        def validated(self) -> FakeClassification:
            return self

    class StringLike(str):
        pass

    with pytest.raises(DataClassificationError):
        evaluate_flow(
            cast(DataClassification, FakeClassification()),
            TrustDomain.WORKSPACE,
        )
    with pytest.raises(DataClassificationError):
        evaluate_flow(
            cast(DataClassification, StringLike("SENSITIVE_CLINICAL")),
            TrustDomain.WORKSPACE,
        )
    with pytest.raises(DataClassificationError):
        evaluate_flow(cast(DataClassification, None), TrustDomain.WORKSPACE)
    with pytest.raises(DataClassificationError):
        evaluate_flow(classify(DataClass.SYNTHETIC), cast(TrustDomain, "ResearchCore"))
    with pytest.raises(DataClassificationError):
        evaluate_flow(classify(DataClass.SYNTHETIC), cast(TrustDomain, 7))
    with pytest.raises(DataClassificationError):
        evaluate_flow(
            classify(DataClass.SYNTHETIC),
            TrustDomain.WORKSPACE,
            explicit_user_request=cast(bool, 1),
        )
    with pytest.raises(DataClassificationError):
        evaluate_flow(
            classify(DataClass.SYNTHETIC),
            TrustDomain.WORKSPACE,
            explicit_user_request=cast(bool, None),
        )


def test_a_lookalike_classification_string_is_not_parsed() -> None:
    for shape in (
        "sensitive_clinical",
        "SENSITIVE_CLINICAL ",
        " SENSITIVE_CLINICAL",
        "SENSITIVE_CLINICAL\n",
        "SENSITIVE-CLINICAL",
        "",
    ):
        with pytest.raises(DataClassificationError):
            admit_data_class(shape)
    for shape in ("researchcore", "ResearchCore ", "RESEARCH_CORE", ""):
        with pytest.raises(DataClassificationError):
            admit_trust_domain(shape)


def test_secret_egress_is_refused_before_any_other_rule() -> None:
    evaluation = evaluate_flow(classify(DataClass.SECRET), TrustDomain.RESEARCH_CORE)
    assert evaluation.refusal is SecretEgressError
    assert evaluation.rule_id == "secret-class-flow-forbidden"
    for destination in TrustDomain:
        assert evaluate_flow(classify(DataClass.SECRET), destination).admitted is False


def test_injecting_an_allow_rule_cannot_open_domain_r(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forged = DomainFlow(
        rule_id="forged-workspace-to-research-core",
        source=TrustDomain.WORKSPACE,
        destination=TrustDomain.RESEARCH_CORE,
        disposition=FlowDisposition.ADMITTED,
        authority="forged authority",
        refusal=UndeclaredFlowError,
    )
    monkeypatch.setitem(
        nobackflow_module._DECLARED_FLOWS,
        (TrustDomain.WORKSPACE, TrustDomain.RESEARCH_CORE),
        forged,
    )
    evaluation = evaluate_flow(
        classify(DataClass.SENSITIVE_CLINICAL),
        TrustDomain.RESEARCH_CORE,
    )
    assert evaluation.admitted is False
    assert evaluation.refusal is ResearchBackflowError


def test_evaluation_is_deterministic_and_stateless() -> None:
    first = evaluate_flow(classify(DataClass.SENSITIVE_CLINICAL), TrustDomain.RESEARCH_CORE)
    second = evaluate_flow(classify(DataClass.SENSITIVE_CLINICAL), TrustDomain.RESEARCH_CORE)
    assert first.refusal_document() == second.refusal_document()
    admitted = evaluate_flow(classify(DataClass.SYNTHETIC), TrustDomain.WORKSPACE)
    assert admitted.require().to_document() == admitted.require().to_document()


def test_a_hand_built_admission_cannot_name_domain_r() -> None:
    with pytest.raises(BackflowError):
        FlowDecision(
            source=classify(DataClass.SENSITIVE_CLINICAL),
            destination=TrustDomain.RESEARCH_CORE,
            rule_id="forged-admission",
            authority="forged authority",
        )


def test_an_inconsistent_evaluation_cannot_be_constructed() -> None:
    classification = classify(DataClass.SENSITIVE_CLINICAL)
    with pytest.raises(DataClassificationError):
        FlowEvaluation(
            source=classification,
            destination=TrustDomain.WORKSPACE,
            admitted=False,
            rule_id="forged-refusal-without-class",
            authority="forged authority",
            reason="forged",
            explicit_user_request=False,
        )
    with pytest.raises(DataClassificationError):
        FlowEvaluation(
            source=classification,
            destination=TrustDomain.WORKSPACE,
            admitted=True,
            rule_id="forged-admission-with-refusal",
            authority="forged authority",
            reason="forged",
            explicit_user_request=False,
            refusal=ResearchBackflowError,
        )
    with pytest.raises(DataClassificationError):
        FlowEvaluation(
            source=classification,
            destination=TrustDomain.RESEARCH_CORE,
            admitted=True,
            rule_id="forged-admission-to-domain-r",
            authority="forged authority",
            reason="forged",
            explicit_user_request=False,
        )


# ---------------------------------------------------------------------------
# Serialization confusion
# ---------------------------------------------------------------------------


def test_a_forged_domain_in_a_classification_document_is_refused() -> None:
    document = dict(classify(DataClass.SENSITIVE_CLINICAL).to_document())
    document["domain"] = "ResearchCore"
    with pytest.raises(DataClassificationError):
        classification_from_document(document)


def test_a_tampered_domain_source_is_refused() -> None:
    document = dict(classify(DataClass.SENSITIVE_CLINICAL).to_document())
    document["domain_source"] = "caller_declared_domain"
    with pytest.raises(DataClassificationError):
        classification_from_document(document)
    del document["domain_source"]
    with pytest.raises(DataClassificationError):
        classification_from_document(document)


def test_extra_or_missing_or_malformed_document_members_are_refused() -> None:
    baseline = dict(classify(DataClass.SYNTHETIC).to_document())
    with_extra = {**baseline, "research_admissible": True}
    with pytest.raises(DataClassificationError):
        classification_from_document(with_extra)
    unknown_class = {**baseline, "data_class": "NOT_A_CLASS"}
    with pytest.raises(DataClassificationError):
        classification_from_document(unknown_class)
    bool_version = {**baseline, "classification_version": True}
    with pytest.raises(DataClassificationError):
        classification_from_document(bool_version)
    string_version = {**baseline, "classification_version": "1"}
    with pytest.raises(DataClassificationError):
        classification_from_document(string_version)
    unsupported_version = {**baseline, "classification_version": 2}
    with pytest.raises(DataClassificationError):
        classification_from_document(unsupported_version)
    shapes: tuple[object, ...] = ([], "SYNTHETIC", 1, None)
    for shape in shapes:
        with pytest.raises(DataClassificationError):
            classification_from_document(shape)


def test_relabelling_an_object_as_a_research_artifact_cannot_open_domain_r() -> None:
    document: dict[str, object] = {
        "classification": {
            "classification_version": 1,
            "data_class": "RESEARCH_ARTIFACT",
            "domain": "ResearchCore",
            "domain_source": "canonical_data_class_table",
        },
        "object_id": str(EXPORT_OBJECT),
        "object_revision": "rev-0001",
        "object_type": "Encounter",
        "payload_digest": content_digest_of(SYNTHETIC_PAYLOAD),
        "workspace_id": str(WORKSPACE_ALPHA),
    }
    relabelled = ClassifiedObject.from_document(document)
    assert relabelled.classification.domain is TrustDomain.RESEARCH_CORE
    evaluation = evaluate_object_flow(relabelled, TrustDomain.RESEARCH_CORE)
    assert evaluation.admitted is False
    assert evaluation.refusal is ResearchBackflowError


def test_mutating_a_returned_object_document_cannot_reclassify_the_object() -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SYNTHETIC),
        payload=SYNTHETIC_PAYLOAD,
    )
    document = classified.to_document()
    classification_document = document["classification"]
    assert isinstance(classification_document, dict)
    classification_document["data_class"] = "RESEARCH_ARTIFACT"
    assert classified.classification.data_class is DataClass.SYNTHETIC
    with pytest.raises(DataClassificationError):
        ClassifiedObject.from_document(document)
    assert {
        "classification",
        "object_id",
        "object_revision",
        "object_type",
        "payload_digest",
        "workspace_id",
    } == set(classified.to_document())


def test_a_classified_object_document_with_a_bad_member_is_refused() -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SYNTHETIC),
        payload=SYNTHETIC_PAYLOAD,
    )
    baseline = classified.to_document()
    for member, replacement in (
        ("object_id", "not-a-uuid"),
        ("object_type", "NotAnObjectType"),
        ("object_revision", ""),
        ("payload_digest", 7),
    ):
        with pytest.raises(WorkspaceStoreError):
            ClassifiedObject.from_document({**baseline, member: replacement})
    with pytest.raises(DataClassificationError):
        ClassifiedObject.from_document({**baseline, "extra": 1})


@pytest.mark.parametrize("destination", list(TrustDomain))
def test_no_guard_document_ever_carries_payload_bytes(destination: TrustDomain) -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SENSITIVE_CLINICAL),
        payload=SYNTHETIC_PAYLOAD,
    )
    evaluation = evaluate_object_flow(classified, destination)
    rendered = json.dumps(evaluation.refusal_document())
    assert "SYNTHETIC-NOT-REAL" not in rendered
    assert "adversarial cw-004 fixture" not in rendered
    if evaluation.admitted:
        assert "SYNTHETIC-NOT-REAL" not in json.dumps(evaluation.require().to_document())


# ---------------------------------------------------------------------------
# File-level bypass attempts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target",
    [
        "C:\\medscale\\export-quarantine\\..\\research-core\\export.json",
        "C:\\medscale\\export-quarantine\\sub\\..\\..\\research-core\\export.json",
        "C:\\medscale\\export-quarantine\\..\\export.json",
        "C:/medscale/research-core/export.json",
        "C:\\medscale/export-quarantine\\mixed\\export.json",
        "C:\\medscale\\export-quarantine\\\\export.json",
        "C:\\medscale\\export-quarantine\\export.json\\",
        "C:\\medscale\\export-quarantine\\export.json ",
        "C:\\medscale\\export-quarantine\\export.json.",
        "C:\\medscale\\export-quarantine\\export.json:stream",
        "C:\\medscale\\export-quarantine\\CON",
        "C:\\medscale\\export-quarantine\\con.txt",
        "C:\\medscale\\export-quarantine\\NUL",
        "C:\\medscale\\export-quarantine\\COM1.json",
        "C:\\medscale\\export-quarantine\\LPT9",
        "C:export.json",
        "C:research\\core\\export.json",
        "export.json",
        "\\export.json",
        "/export.json",
        "\\\\server\\share\\export.json",
        "\\\\?\\C:\\medscale\\export-quarantine\\export.json",
        "C:\\medscale\\EXPORT-QUARANTINE\\..\\RESEARCH-CORE\\export.json",
        "c:\\medscale\\RESEARCH-CORE\\export.json",
        "C:\\medscale\\research-core\\export.json",
        "D:\\medscale\\export-quarantine\\export.json",
        "C:\\medscale\\export-quarantine\\export.json\x00",
        "C:\\medscale\\export-quarantine\t\\export.json",
        "",
        "   ",
    ],
)
def test_hostile_export_paths_are_refused(target: str) -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=target,
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


@pytest.mark.parametrize("target", [None, 7, b"C:\\x", ("C:\\x",)])
def test_non_string_export_targets_are_refused(target: object) -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=cast(str, target),
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


def test_a_research_root_declared_as_a_non_tuple_fails_closed() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=QUARANTINE_ROOT + "\\export.json",
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=cast(tuple[str, ...], ["C:\\medscale\\research-core"]),
        )


def test_a_sibling_directory_sharing_a_name_prefix_is_not_inside_domain_r() -> None:
    admission = admit_export_path(
        target_path="C:\\medscale\\research-core-backup\\export.json",
        quarantine_root="C:\\medscale",
        research_core_roots=RESEARCH_CORE_ROOTS,
    )
    assert admission.target_path.endswith("research-core-backup\\export.json")


def test_windows_path_comparison_is_case_insensitive_and_posix_is_not() -> None:
    admission = admit_export_path(
        target_path="c:\\MEDSCALE\\Export-Quarantine\\export.json",
        quarantine_root=QUARANTINE_ROOT,
        research_core_roots=RESEARCH_CORE_ROOTS,
    )
    assert admission.target_path == "c:\\MEDSCALE\\Export-Quarantine\\export.json"
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path="/srv/QUARANTINE/export.json",
            quarantine_root="/srv/quarantine",
            research_core_roots=("/srv/research-core",),
        )


def test_a_relative_quarantine_root_is_refused() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path="quarantine\\export.json",
            quarantine_root="quarantine",
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


def test_a_target_on_another_volume_is_not_inside_the_quarantine_root() -> None:
    """Regression: containment must compare the volume root, not only the components."""

    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path="D:\\medscale\\export-quarantine\\export.json",
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


def test_a_target_in_another_path_form_is_not_inside_a_posix_quarantine_root() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path="C:\\srv\\quarantine\\export.json",
            quarantine_root="/srv/quarantine",
            research_core_roots=("/srv/research-core",),
        )


def test_a_unc_target_on_another_server_is_not_inside_the_quarantine_share() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path="\\\\other-server\\share\\export.json",
            quarantine_root="\\\\server\\share",
            research_core_roots=("\\\\server\\research",),
        )
    admission = admit_export_path(
        target_path="\\\\server\\share\\export.json",
        quarantine_root="\\\\server\\share",
        research_core_roots=("\\\\server\\research",),
    )
    assert admission.target_path == "\\\\server\\share\\export.json"


def test_staging_an_export_into_a_research_root_is_refused_even_when_deidentified() -> None:
    with pytest.raises(ExportBoundaryError):
        stage_export(
            binding=export_binding(),
            payload=SYNTHETIC_PAYLOAD,
            target_path="C:\\medscale\\research-core\\deidentified.json",
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
            deidentified=True,
        )


def test_a_staged_export_cannot_be_relabelled_into_research_admission() -> None:
    envelope = stage_export(
        binding=export_binding(),
        payload=SYNTHETIC_PAYLOAD,
        target_path=QUARANTINE_ROOT + "\\export.json",
        quarantine_root=QUARANTINE_ROOT,
        research_core_roots=RESEARCH_CORE_ROOTS,
        deidentified=True,
    )
    evaluation = envelope.research_admission_evaluation()
    assert evaluation.refusal is ExportAdmissionError
    with pytest.raises(ExportAdmissionError):
        evaluation.require()
    assert envelope.classification.domain is TrustDomain.EXPORT_QUARANTINE


# ---------------------------------------------------------------------------
# Static guard bypass attempts
# ---------------------------------------------------------------------------


def test_cw004_guard_rejects_a_second_flow_table(tmp_path: Path) -> None:
    (tmp_path / "shadow.py").write_text("DOMAIN_FLOWS = ()\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "DOMAIN_FLOWS must be defined exactly once in nobackflow.py (CW-004); "
        "observed: shadow.py" in result.stderr
    )


def test_cw004_guard_rejects_a_second_typed_definition(tmp_path: Path) -> None:
    (tmp_path / "shadow.py").write_text(
        "class TrustDomain:\n    pass\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "TrustDomain must be defined exactly once in data_class.py (CW-004); "
        "observed: shadow.py" in result.stderr
    )


def test_cw004_guard_rejects_a_foreign_domain_literal(tmp_path: Path) -> None:
    (tmp_path / "helper.py").write_text(
        'DESTINATION = "ExportQuarantine"\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "the classification literal 'ExportQuarantine' must be declared only in "
        "data_class.py" in result.stderr
    )


def test_cw004_guard_requires_the_import_time_flow_validation(tmp_path: Path) -> None:
    (tmp_path / "nobackflow.py").write_text(
        "DOMAIN_FLOWS = ()\n"
        "\n"
        "\n"
        "def admit_flow() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def evaluate_flow() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def evaluate_object_flow() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def guard_object_handoff() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def admit_export_path() -> None:\n"
        "    return None\n"
        "\n"
        "\n"
        "def stage_export() -> None:\n"
        "    return None\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "must call validate_flow_table() at import time" in result.stderr
