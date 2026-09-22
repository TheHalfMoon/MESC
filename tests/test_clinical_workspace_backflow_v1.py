"""CW-004 focused acceptance tests for the no-backflow and classification guard.

Scope: synthetic fixtures only. This module creates no clinical, research,
publication or PHI authority. Every assertion below is an admission decision taken
by the guard, and no test claims that anything was stored, exported or executed.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open. These tests import it at runtime through
# sys.path; declaring the missing import here keeps that deferral explicit.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
GUARD = REPOSITORY_ROOT / "scripts" / "check_clinical_workspace_boundary.py"

sys.path.insert(0, str(WORKSPACE_SRC))

from medscale_workspace import (  # noqa: E402
    DATA_CLASS_ADMISSIONS,
    DOMAIN_FLOWS,
    OPERATIONAL_DATA_CLASSES,
    SYNTHETIC_DATA_CLASS,
    ClassifiedObject,
    DataClass,
    DataClassification,
    ExportEnvelope,
    FlowDisposition,
    ObjectBinding,
    TrustDomain,
    WorkspaceObjectType,
    admit_data_class,
    admit_export_path,
    admit_flow,
    admit_trust_domain,
    class_admission_of,
    classification_from_document,
    classify,
    classify_object,
    domain_of,
    evaluate_flow,
    evaluate_object_flow,
    guard_object_handoff,
    stage_export,
    synthetic_data_class_value,
    validate_admission_table,
)
from medscale_workspace.errors import (  # noqa: E402
    DataClassificationError,
    ExplicitExportRequestError,
    ExportAdmissionError,
    ExportBoundaryError,
    ResearchBackflowError,
    SecretEgressError,
    TelemetryBackflowError,
    UnavailableAuthorityError,
    UndeclaredFlowError,
    WorkspaceAdmissionError,
)
from medscale_workspace.nobackflow import validate_flow_table  # noqa: E402

WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
EXPORT_OBJECT = UUID("5c7d3e21-8b4a-4f60-9d2c-1e5a7b9c3d40")
SYNTHETIC_PAYLOAD = b'SYNTHETIC-NOT-REAL:{"note":"cw-004 boundary fixture"}'
QUARANTINE_ROOT = "C:\\medscale\\export-quarantine"
RESEARCH_CORE_ROOTS = ("C:\\medscale\\research-core", "C:\\medscale\\mrl-evidence")


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


def _exact_string_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


# ---------------------------------------------------------------------------
# Canonical classification vocabulary
# ---------------------------------------------------------------------------


def test_every_admitted_data_class_is_bound_to_exactly_one_domain() -> None:
    validate_admission_table()
    bound = [admission.data_class for admission in DATA_CLASS_ADMISSIONS]
    assert sorted(bound) == sorted(DataClass)
    assert len(bound) == len(set(bound))


def test_the_canonical_table_derives_the_documented_domains() -> None:
    assert domain_of(DataClass.SYNTHETIC) is TrustDomain.WORKSPACE
    assert domain_of(DataClass.SENSITIVE_CLINICAL) is TrustDomain.WORKSPACE
    assert domain_of(DataClass.AUDIO_CLINICAL) is TrustDomain.WORKSPACE
    assert domain_of(DataClass.AUDIT_METADATA) is TrustDomain.WORKSPACE
    assert domain_of(DataClass.OPERATIONAL_LOG) is TrustDomain.WORKSPACE
    assert domain_of(DataClass.RESEARCH_ARTIFACT) is TrustDomain.RESEARCH_CORE
    assert domain_of(DataClass.EXPORT_QUARANTINE) is TrustDomain.EXPORT_QUARANTINE
    assert set(OPERATIONAL_DATA_CLASSES) == {
        DataClass.OPERATIONAL_TELEMETRY,
        DataClass.OPERATIONAL_ANALYTICS,
        DataClass.OPERATIONAL_LOG,
    }


def test_the_synthetic_data_class_is_single_sourced() -> None:
    """Issue #464 item 3: the classification is one canonical value, not three literals."""

    assert SYNTHETIC_DATA_CLASS is DataClass.SYNTHETIC
    assert synthetic_data_class_value() == "SYNTHETIC"
    occurrences: list[str] = []
    for path in sorted((WORKSPACE_SRC / "medscale_workspace").rglob("*.py")):
        if "SYNTHETIC" in _exact_string_literals(path):
            occurrences.append(path.name)
    assert occurrences == ["data_class.py"]


def test_unknown_classification_state_fails_closed() -> None:
    with pytest.raises(DataClassificationError):
        admit_data_class("NOT_AN_ADMITTED_CLASS")
    with pytest.raises(DataClassificationError):
        admit_data_class(None)
    with pytest.raises(DataClassificationError):
        admit_trust_domain("NotAnAdmittedDomain")
    with pytest.raises(DataClassificationError):
        admit_trust_domain(7)
    with pytest.raises(DataClassificationError):
        class_admission_of(cast(DataClass, "SENSITIVE_CLINICAL"))


def test_a_raw_string_cannot_be_constructed_as_a_classification() -> None:
    with pytest.raises(DataClassificationError):
        DataClassification(data_class=cast(DataClass, "SENSITIVE_CLINICAL"))


def test_an_unsupported_classification_version_fails_closed() -> None:
    with pytest.raises(DataClassificationError):
        DataClassification(data_class=DataClass.SYNTHETIC, classification_version=2)
    with pytest.raises(DataClassificationError):
        DataClassification(
            data_class=DataClass.SYNTHETIC,
            classification_version=cast(int, "1"),
        )


def test_a_classification_round_trips_through_its_canonical_document() -> None:
    classification = classify(DataClass.AUDIO_CLINICAL)
    document = json.loads(classification.canonical_bytes().decode("ascii"))
    assert document == {
        "classification_version": 1,
        "data_class": "AUDIO_CLINICAL",
        "domain": "Workspace",
        "domain_source": "canonical_data_class_table",
    }
    assert classification_from_document(document) == classification


# ---------------------------------------------------------------------------
# API-level no-backflow decisions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("data_class", list(DataClass))
def test_research_core_is_not_a_reachable_destination_for_any_class(
    data_class: DataClass,
) -> None:
    evaluation = evaluate_flow(classify(data_class), TrustDomain.RESEARCH_CORE)
    assert evaluation.admitted is False
    refusal = evaluation.refusal
    assert refusal is not None
    with pytest.raises(refusal):
        admit_flow(classify(data_class), TrustDomain.RESEARCH_CORE)


def test_direct_workspace_to_research_core_write_fails_closed() -> None:
    with pytest.raises(ResearchBackflowError) as failure:
        admit_flow(classify(DataClass.SENSITIVE_CLINICAL), TrustDomain.RESEARCH_CORE)
    assert "Domain R is not a reachable destination" in str(failure.value)


def test_quarantine_export_cannot_be_automatically_admitted_to_research() -> None:
    with pytest.raises(ExportAdmissionError):
        admit_flow(classify(DataClass.EXPORT_QUARANTINE), TrustDomain.RESEARCH_CORE)


@pytest.mark.parametrize("data_class", list(OPERATIONAL_DATA_CLASSES))
def test_workspace_operational_data_cannot_become_research_core_data(
    data_class: DataClass,
) -> None:
    evaluation = evaluate_flow(classify(data_class), TrustDomain.RESEARCH_CORE)
    assert evaluation.refusal is TelemetryBackflowError
    assert evaluation.rule_id == "workspace-operational-data-to-research-core-forbidden"
    with pytest.raises(TelemetryBackflowError):
        admit_flow(classify(data_class), TrustDomain.RESEARCH_CORE)


def test_a_workspace_export_needs_an_explicit_user_request() -> None:
    classification = classify(DataClass.SENSITIVE_CLINICAL)
    with pytest.raises(ExplicitExportRequestError):
        admit_flow(classification, TrustDomain.EXPORT_QUARANTINE)
    decision = admit_flow(
        classification,
        TrustDomain.EXPORT_QUARANTINE,
        explicit_user_request=True,
    )
    assert decision.rule_id == "workspace-to-export-quarantine-explicit-export"
    assert decision.to_document()["destination_domain"] == "ExportQuarantine"


def test_a_quarantined_export_cannot_be_admitted_back_into_the_workspace() -> None:
    with pytest.raises(WorkspaceAdmissionError):
        admit_flow(classify(DataClass.EXPORT_QUARANTINE), TrustDomain.WORKSPACE)


def test_the_research_core_read_direction_into_the_workspace_is_admitted() -> None:
    decision = admit_flow(classify(DataClass.RESEARCH_ARTIFACT), TrustDomain.WORKSPACE)
    assert decision.rule_id == "research-core-to-workspace-versioned-interface"


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        (DataClass.SENSITIVE_CLINICAL, TrustDomain.EXTERNAL_CONNECTOR),
        (DataClass.SENSITIVE_CLINICAL, TrustDomain.PLUGIN_RUNTIME),
        (DataClass.SYNTHETIC, TrustDomain.EXTERNAL_CONNECTOR),
        (DataClass.SYNTHETIC, TrustDomain.PLUGIN_RUNTIME),
    ],
)
def test_declared_flows_without_granted_authority_fail_closed(
    source: DataClass,
    destination: TrustDomain,
) -> None:
    with pytest.raises(UnavailableAuthorityError):
        admit_flow(classify(source), destination)


@pytest.mark.parametrize(
    ("source", "destination"),
    [
        (DataClass.RESEARCH_ARTIFACT, TrustDomain.EXPORT_QUARANTINE),
        (DataClass.RESEARCH_ARTIFACT, TrustDomain.EXTERNAL_CONNECTOR),
        (DataClass.RESEARCH_ARTIFACT, TrustDomain.PLUGIN_RUNTIME),
        (DataClass.EXPORT_QUARANTINE, TrustDomain.EXTERNAL_CONNECTOR),
        (DataClass.EXPORT_QUARANTINE, TrustDomain.PLUGIN_RUNTIME),
    ],
)
def test_undeclared_flows_fail_closed(
    source: DataClass,
    destination: TrustDomain,
) -> None:
    with pytest.raises(UndeclaredFlowError):
        admit_flow(classify(source), destination)


@pytest.mark.parametrize("destination", list(TrustDomain))
def test_secret_class_material_never_leaves_the_workspace(destination: TrustDomain) -> None:
    with pytest.raises(SecretEgressError):
        admit_flow(classify(DataClass.SECRET), destination)


def test_a_same_domain_operation_is_not_a_boundary_crossing() -> None:
    decision = admit_flow(classify(DataClass.SENSITIVE_CLINICAL), TrustDomain.WORKSPACE)
    assert decision.rule_id == "same-domain-operation"


def test_a_refusal_carries_provenance_without_any_payload() -> None:
    evaluation = evaluate_flow(classify(DataClass.AUDIO_CLINICAL), TrustDomain.RESEARCH_CORE)
    document = evaluation.refusal_document()
    assert document["decision"] == "REFUSED"
    assert document["rule_id"] == "workspace-to-research-core-forbidden"
    assert document["refusal_error"] == "ResearchBackflowError"
    assert document["source_domain"] == "Workspace"
    source_classification = document["source_classification"]
    assert isinstance(source_classification, dict)
    assert source_classification["data_class"] == "AUDIO_CLINICAL"
    assert set(source_classification) == {
        "classification_version",
        "data_class",
        "domain",
        "domain_source",
    }
    assert "payload" not in json.dumps(document)


def test_the_declared_flow_table_cannot_reach_domain_r() -> None:
    validate_flow_table()
    for flow in DOMAIN_FLOWS:
        assert flow.destination is not TrustDomain.RESEARCH_CORE
        assert flow.source is not flow.destination
    dispositions = {flow.disposition for flow in DOMAIN_FLOWS}
    assert dispositions <= {
        FlowDisposition.ADMITTED,
        FlowDisposition.FORBIDDEN,
        FlowDisposition.AUTHORITY_NOT_GRANTED,
    }


# ---------------------------------------------------------------------------
# Object-level no-backflow decisions
# ---------------------------------------------------------------------------


def test_a_classified_object_handoff_to_research_is_refused_without_its_payload() -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SENSITIVE_CLINICAL),
        payload=SYNTHETIC_PAYLOAD,
    )
    evaluation = evaluate_object_flow(classified, TrustDomain.RESEARCH_CORE)
    assert evaluation.admitted is False
    document = evaluation.refusal_document()
    object_member = document["object"]
    assert isinstance(object_member, dict)
    assert object_member["object_id"] == str(EXPORT_OBJECT)
    assert object_member["object_revision"] == "rev-0001"
    assert "payload_digest" not in object_member
    serialized = json.dumps(document)
    assert "SYNTHETIC-NOT-REAL" not in serialized
    assert "payload" not in serialized
    with pytest.raises(ResearchBackflowError):
        guard_object_handoff(classified, TrustDomain.RESEARCH_CORE)


def test_a_classified_object_may_stay_inside_its_own_domain() -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SYNTHETIC),
        payload=SYNTHETIC_PAYLOAD,
    )
    decision = guard_object_handoff(classified, TrustDomain.WORKSPACE)
    assert decision.rule_id == "same-domain-operation"


def test_a_classified_object_round_trips_through_its_document() -> None:
    classified = classify_object(
        binding=export_binding(),
        classification=classify(DataClass.SYNTHETIC),
        payload=SYNTHETIC_PAYLOAD,
    )
    document = json.loads(json.dumps(classified.to_document()))
    assert ClassifiedObject.from_document(document) == classified


# ---------------------------------------------------------------------------
# File-level export containment (Domain X)
# ---------------------------------------------------------------------------


def test_an_export_path_below_the_quarantine_root_is_admitted() -> None:
    admission = admit_export_path(
        target_path=QUARANTINE_ROOT + "\\encounter-001\\export.json",
        quarantine_root=QUARANTINE_ROOT,
        research_core_roots=RESEARCH_CORE_ROOTS,
    )
    document = admission.to_document()
    assert document["destination_domain"] == "ExportQuarantine"
    containment_rule = document["containment_rule"]
    assert isinstance(containment_rule, str)
    assert containment_rule.startswith("strictly_below_quarantine_root")
    assert document["research_core_root_count"] == 2


@pytest.mark.parametrize(
    "target",
    [
        "C:\\medscale\\research-core\\export.json",
        "C:\\medscale\\research-core\\nested\\export.json",
        "C:\\medscale\\mrl-evidence\\export.json",
        "C:\\medscale\\export-quarantine\\..\\research-core\\export.json",
        "C:\\medscale\\export-quarantine-other\\export.json",
        "C:\\medscale\\export",
        "C:\\medscale",
    ],
)
def test_an_export_path_outside_the_quarantine_root_is_refused(target: str) -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=target,
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


def test_the_quarantine_root_itself_is_not_an_export_target() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=QUARANTINE_ROOT,
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=RESEARCH_CORE_ROOTS,
        )


def test_an_undeclared_research_root_set_fails_closed() -> None:
    with pytest.raises(ExportBoundaryError):
        admit_export_path(
            target_path=QUARANTINE_ROOT + "\\export.json",
            quarantine_root=QUARANTINE_ROOT,
            research_core_roots=(),
        )


# ---------------------------------------------------------------------------
# De-identified export stays in Domain X
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("deidentified", [False, True])
def test_a_staged_export_remains_domain_x_and_is_never_research_admitted(
    deidentified: bool,
) -> None:
    envelope = stage_export(
        binding=export_binding(),
        payload=SYNTHETIC_PAYLOAD,
        target_path=QUARANTINE_ROOT + "\\export.json",
        quarantine_root=QUARANTINE_ROOT,
        research_core_roots=RESEARCH_CORE_ROOTS,
        deidentified=deidentified,
    )
    assert isinstance(envelope, ExportEnvelope)
    assert envelope.classification.domain is TrustDomain.EXPORT_QUARANTINE
    assert envelope.deidentified is deidentified
    evaluation = envelope.research_admission_evaluation()
    assert evaluation.admitted is False
    assert evaluation.refusal is ExportAdmissionError
    assert "SYNTHETIC-NOT-REAL" not in json.dumps(envelope.to_document())


def test_de_identification_is_a_transformation_not_an_admission() -> None:
    envelope = stage_export(
        binding=export_binding(),
        payload=SYNTHETIC_PAYLOAD,
        target_path=QUARANTINE_ROOT + "\\deidentified.json",
        quarantine_root=QUARANTINE_ROOT,
        research_core_roots=RESEARCH_CORE_ROOTS,
        deidentified=True,
    )
    with pytest.raises(ExportAdmissionError):
        admit_flow(envelope.classification, TrustDomain.RESEARCH_CORE)


# ---------------------------------------------------------------------------
# Static guard rules for the CW-004 vocabulary and entry points
# ---------------------------------------------------------------------------


def test_the_boundary_guard_passes_the_current_workspace_sources() -> None:
    result = _run_guard(WORKSPACE_SRC)
    assert result.returncode == 0, result.stderr


def test_cw004_guard_requires_the_classification_module(tmp_path: Path) -> None:
    (tmp_path / "spare.py").write_text("VALUE = 1\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "CW-004 requires data_class.py" in result.stderr
    assert "CW-004 requires nobackflow.py" in result.stderr


def test_cw004_guard_rejects_a_repeated_classification_literal(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text('DATA_CLASS = "SYNTHETIC"\n', encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "the classification literal 'SYNTHETIC' must be declared only in data_class.py"
        in result.stderr
    )


def test_cw004_guard_rejects_a_classification_member_outside_the_two_modules(
    tmp_path: Path,
) -> None:
    (tmp_path / "app.py").write_text(
        "TARGET = TrustDomain.RESEARCH_CORE\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "TrustDomain/DataClass member 'RESEARCH_CORE' may be named only in data_class.py "
        "or nobackflow.py" in result.stderr
    )


def test_cw004_guard_rejects_a_second_flow_decision_entry_point(tmp_path: Path) -> None:
    (tmp_path / "shadow.py").write_text(
        "def admit_flow(*args: object) -> None:\n    return None\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "admit_flow must be defined exactly once in nobackflow.py (CW-004); "
        "observed: shadow.py" in result.stderr
    )


def test_cw004_guard_requires_import_time_table_validation(tmp_path: Path) -> None:
    (tmp_path / "data_class.py").write_text(
        "class TrustDomain:\n    pass\n"
        "\n"
        "\n"
        "class DataClass:\n    pass\n"
        "\n"
        "\n"
        "class DataClassification:\n    pass\n"
        "\n"
        "\n"
        "DATA_CLASS_ADMISSIONS = ()\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "must call validate_admission_table() at import time" in result.stderr
