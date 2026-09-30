"""CW-020 PHI-readiness evidence packet: mechanical binding of the packet to the code.

The packet is an assessment, not a grant. These cases keep it honest: every cited test
and path must exist, every gate and acceptance item must be assessed, residual-risk
severities must match the CW-019 review record, identities must equal the code
constants, the audit-coverage gaps must match what the package actually emits, and
no document may claim PHI or production readiness or authorization.
"""

# mypy: disable-error-code="import-not-found"

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_MODULES = WORKSPACE_SRC / "medscale_workspace"
SPECS = REPOSITORY_ROOT / "specs" / "medscale-clinical-workspace-v1"
PACKET = SPECS / "cw-020-phi-readiness-evidence-packet.md"
INCIDENT = SPECS / "incident_response.md"

sys.path.insert(0, str(WORKSPACE_SRC))

from medscale_workspace import asr, errors, versions  # noqa: E402 runtime import
from medscale_workspace.audit import AuditEventType  # noqa: E402 runtime import

ADMITTED_STATUSES = frozenset({"EVIDENCED_SYNTHETIC", "PARTIAL", "NOT_MET", "ARCHITECTURE_BLOCKED"})

# Declared audit event types the packet records as never emitted (section 5.2).
PACKET_UNEMITTED_EVENT_TYPES = frozenset(
    {
        "PATIENT_READ",
        "ENCOUNTER_READ",
        "LOGIN",
        "WORKSPACE_OPEN",
        "WORKSPACE_CLOSE",
        "SECURITY_FAILURE",
        "TRANSCRIPT_EDIT",
        "TRANSCRIPT_DELETE",
        "CONNECTOR_WRITE",
    }
)

# Every raised security signal the incident procedure must cover.
REQUIRED_INCIDENT_SIGNALS = frozenset(
    {
        "StoreSealError",
        "EnvelopeAuthenticationError",
        "AuditChainError",
        "BackupIntegrityError",
        "KeyProviderUnavailableError",
        "KeyMaterialUnavailableError",
        "ResearchBackflowError",
        "TelemetryBackflowError",
        "SecretEgressError",
        "UndeclaredFlowError",
        "StoreMigrationRequiredError",
        "MigrationValidationError",
        "StoreRoleError",
        "AsrRevisionError",
    }
)

FORBIDDEN_CLAIM = re.compile(
    r"\b(PHI|PRODUCTION)_(READINESS|AUTHORIZATION)\s*=\s*(READY|GRANTED|AUTHORIZED)\b"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    following = text.find("\n## ", start + len(heading))
    return text[start:] if following < 0 else text[start:following]


def _table_rows(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        if not line.startswith("|") or set(line) <= {"|", "-", " "}:
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows[1:]


def _bullets(section: str) -> list[str]:
    return [
        line[2:].strip().rstrip(";.").strip()
        for line in section.splitlines()
        if line.startswith("- ")
    ]


def _defined_test_functions() -> set[str]:
    names: set[str] = set()
    for path in (REPOSITORY_ROOT / "tests").glob("*.py"):
        for node in ast.walk(ast.parse(_read(path))):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                names.add(node.name)
    return names


def test_every_cited_test_function_exists() -> None:
    defined = _defined_test_functions()
    assert len(set(re.findall(r"`(test_[a-z0-9_]+)`", _read(PACKET)))) >= 50
    for document in (PACKET, INCIDENT):
        cited = set(re.findall(r"`(test_[a-z0-9_]+)`", _read(document)))
        missing = sorted(cited - defined)
        assert not missing, f"{document.name} cites missing tests: {missing}"


def test_every_cited_repository_path_and_link_exists() -> None:
    for document in (PACKET, INCIDENT):
        text = _read(document)
        for cited in re.findall(r"`((?:apps|specs|docs|tests)/[^`\s]+)`", text):
            assert (REPOSITORY_ROOT / cited).exists(), f"{document.name}: {cited}"
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if target.startswith("http"):
                continue
            assert (document.parent / target).resolve().exists(), f"{document.name}: {target}"


def test_gate_rows_assess_every_section_20_item() -> None:
    gate = _section(_read(SPECS / "data_security.md"), "## 20. PHI-readiness gate")
    required = set(_bullets(gate.split("`PHI_READY`")[0]))
    assert len(required) == 16
    rows = _table_rows(_section(_read(PACKET), "## 4. PHI-readiness gate"))
    assessed = [row[0] for row in rows]
    assert sorted(assessed) == sorted(required)
    for row in rows:
        assert row[1] in ADMITTED_STATUSES, row


def test_acceptance_rows_assess_every_cw020_acceptance_item() -> None:
    ledger = _section(_read(SPECS / "tasks.md"), "## CW-020")
    acceptance = ledger.split("**Acceptance**")[1].split("**Important**")[0]
    required = set(_bullets(acceptance))
    assert len(required) == 7
    rows = _table_rows(_section(_read(PACKET), "## 3. Acceptance mapping"))
    assert sorted(row[0] for row in rows) == sorted(required)
    for row in rows:
        assert row[1] in ADMITTED_STATUSES, row


def test_independent_review_is_not_met_while_no_human_review_exists() -> None:
    review = _read(SPECS / "cw-019-security-review.md")
    assert "No human independent security review has been performed" in review
    packet = _read(PACKET)
    acceptance = {
        row[0]: row[1] for row in _table_rows(_section(packet, "## 3. Acceptance mapping"))
    }
    gate = {row[0]: row[1] for row in _table_rows(_section(packet, "## 4. PHI-readiness"))}
    assert acceptance["independent review"] == "NOT_MET"
    assert gate["security review / penetration assessment appropriate to deployment"] == "NOT_MET"
    assert gate["threat-model review"] != "EVIDENCED_SYNTHETIC"


def test_residual_risk_severities_match_the_cw019_review_record() -> None:
    def severities(text: str) -> dict[str, str]:
        return dict(re.findall(r"^\| (R[1-8]) \| (LOW|MEDIUM|HIGH|CRITICAL) \|", text, re.M))

    recorded = severities(_read(SPECS / "cw-019-security-review.md"))
    packet = severities(_read(PACKET))
    assert sorted(recorded) == [f"R{index}" for index in range(1, 9)]
    assert packet == recorded
    assert "R2 | MEDIUM" in _read(PACKET) and "ARCHITECTURE_BLOCKED" in _read(PACKET)


def test_declared_but_unemitted_audit_event_types_match_the_packet() -> None:
    referenced: set[str] = set()
    for path in WORKSPACE_MODULES.glob("*.py"):
        for node in ast.walk(ast.parse(_read(path))):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "AuditEventType"
            ):
                referenced.add(node.attr)
    declared = {member.name for member in AuditEventType}
    assert declared - referenced == PACKET_UNEMITTED_EVENT_TYPES
    packet = _read(PACKET)
    for name in PACKET_UNEMITTED_EVENT_TYPES:
        assert f"`{name}`" in packet or f"`AuditEventType.{name}`" in packet, name


def test_identities_equal_the_code_constants() -> None:
    packet = _read(PACKET)
    assert f"ASR MODEL_ID          {asr.MODEL_ID}" in packet
    assert f"ASR MODEL_REVISION    {asr.MODEL_REVISION}" in packet
    assert f"transformers {asr.RUNTIME_VERSION}, torch {asr.TORCH_VERSION}" in packet
    assert f"WORKSPACE_SCHEMA_VERSION = {versions.WORKSPACE_SCHEMA_VERSION}" in packet
    assert f"ENCRYPTION_FORMAT_VERSION = {versions.ENCRYPTION_FORMAT_VERSION}" in packet
    assert f"POLICY_VERSION = {versions.POLICY_VERSION}" in packet
    project = tomllib.loads(_read(REPOSITORY_ROOT / "apps" / "workspace" / "pyproject.toml"))
    (pin,) = project["project"]["dependencies"]
    assert f"AEAD dependency {pin}" in packet
    assert f"AEAD                  {pin}" in packet


def test_incident_response_names_only_real_error_classes_and_covers_every_signal() -> None:
    named = set(re.findall(r"`([A-Z][A-Za-z]*Error)`", _read(INCIDENT)))
    for name in named:
        signal = getattr(errors, name, None)
        assert isinstance(signal, type) and issubclass(signal, Exception), name
    missing = sorted(REQUIRED_INCIDENT_SIGNALS - named)
    assert not missing, f"incident procedure misses signals: {missing}"


def test_no_document_claims_phi_or_production_readiness_or_authorization() -> None:
    for document in (PACKET, INCIDENT):
        text = _read(document)
        assert not FORBIDDEN_CLAIM.search(text), document.name
        assert "PHI_AUTHORIZATION = NOT_GRANTED" in text
        assert "PRODUCTION_AUTHORIZATION = NOT_GRANTED" in text
    packet = _read(PACKET)
    for line in (
        "PHI_READINESS = NOT_READY",
        "PRODUCTION_READINESS = NOT_READY",
        "QUALIFICATION_SCOPE = SYNTHETIC_ONLY",
        "CW-021 = NOT AUTHORIZED",
        "PHI_READINESS_EVIDENCE = NOT PHI AUTHORITY",
        "MODEL_AUTHORITY = NONE",
        "REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED",
        "REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED",
        "NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED",
        "EHR_WRITE_AUTHORIZATION = NOT_GRANTED",
        "EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED",
        "TRAINING_AUTHORIZATION = NOT_GRANTED",
        "PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED",
        "RESEARCH_ADMISSION_OF_WORKSPACE_DATA = NOT_GRANTED",
    ):
        assert line in packet, line


def test_evidence_revision_is_bound_and_prerequisites_cover_every_blocker() -> None:
    packet = _read(PACKET)
    (revision,) = re.findall(r"^EVIDENCE_REVISION   ([0-9a-f]{40})$", packet, re.M)
    assert f"`{revision}`" in packet
    assert len(re.findall(r"fresh-main [A-Za-z /]+ +\d{11} \(push\): SUCCESS", packet)) == 4
    prerequisites = _section(packet, "## 8. Prerequisites")
    for blocker in ("G1", "G2", "G3", "G4", "G5", "G6", "G7", "R1", "R2", "R7"):
        assert f"{blocker})" in prerequisites or f"{blocker}," in prerequisites, blocker


CORRUPTIONS = (
    (
        "| R1 | MEDIUM | whole-store rollback",
        "| R1 | LOW | whole-store rollback",
        "test_residual_risk_severities_match_the_cw019_review_record",
    ),
    (
        "PHI_READINESS = NOT_READY\nPHI_AUTHORIZATION",
        "PHI_READINESS = READY\nPHI_AUTHORIZATION",
        "test_no_document_claims_phi_or_production_readiness_or_authorization",
    ),
    (
        "| independent review | NOT_MET |",
        "| independent review | EVIDENCED_SYNTHETIC |",
        "test_independent_review_is_not_met_while_no_human_review_exists",
    ),
    (
        "| privacy/retention policy | NOT_MET |",
        "| privacy/retention policy | READY |",
        "test_gate_rows_assess_every_section_20_item",
    ),
    (
        "| model isolation |",
        "| model sandboxing |",
        "test_gate_rows_assess_every_section_20_item",
    ),
    (
        "`test_missing_optional_deps_fail_cleanly`",
        "`test_missing_optional_deps_fail_quietly`",
        "test_every_cited_test_function_exists",
    ),
    (
        "41f01f3fe87f28c78e2fbf8b568835947dd65ed9 (immutable",
        "41f01f3fe87f28c78e2fbf8b568835947dd65ed0 (immutable",
        "test_identities_equal_the_code_constants",
    ),
    (
        "| G2 | HIGH | reads are never audited. `AuditEventType.PATIENT_READ` and ",
        "| G2 | HIGH | reads are never audited. ",
        "test_declared_but_unemitted_audit_event_types_match_the_packet",
    ),
    (
        "(R7).\n6.",
        "(none).\n6.",
        "test_evidence_revision_is_bound_and_prerequisites_cover_every_blocker",
    ),
)


@pytest.mark.parametrize(("original", "corrupted", "check"), CORRUPTIONS)
def test_the_binding_rejects_a_corrupted_packet(
    original: str,
    corrupted: str,
    check: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _read(PACKET)
    assert text.count(original) == 1, original
    copy = tmp_path / "packet.md"
    copy.write_text(text.replace(original, corrupted), encoding="utf-8")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "PACKET", copy)
    with pytest.raises(AssertionError):
        getattr(module, check)()
