"""CW-020 canonical closeout: mechanical binding of the closeout record.

Jev missed a single-line CW-021 authorization in the CW-020 packet, so the closeout's
critical claims are bound here instead: the exact implementation SHAs and workflow
runs, the PHI-readiness gaps and residual risks as recorded in the packet, the
NOT_READY verdict, the Workspace-only scope, the merge-authority gap, the preserved
Jev history, and the ledger state of CW-021.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SPECS = REPOSITORY_ROOT / "specs" / "medscale-clinical-workspace-v1"
CLOSEOUT = SPECS / "cw-020-closeout.md"
PACKET = SPECS / "cw-020-phi-readiness-evidence-packet.md"
LEDGER = SPECS / "tasks.md"

# Ground truth verified from git and the GitHub API when the closeout was written.
IMPLEMENTATION_HEAD = "141e4d46dc580ac077d204db1ef4dfb532a6db74"
IMPLEMENTATION_TREE = "30f5a753037fad7c6b280b3ecc70494c397ed3d0"
IMPLEMENTATION_MERGE = "548df35c94feaa1f180dce6252c45918960bbf45"
IMPLEMENTATION_BASE = "3b3efa1c02b641a9107060bc51788960a4256b7f"
EXACT_HEAD_RUNS = {"CI": "36692279884", "CodeQL": "36692279944"}
FRESH_MAIN_RUNS = {
    "CI": "36697110726",
    "CodeQL": "36697111063",
    "Optional Extras / Backends": "36697110881",
    "HF Publication": "36697110779",
}

GAP_IDS = tuple(f"G{number}" for number in range(1, 9))
RISK_IDS = tuple(f"R{number}" for number in range(1, 9))

FORBIDDEN_CLAIM = re.compile(
    r"\b(PHI|PRODUCTION)_(READINESS|AUTHORIZATION)\s*=\s*(READY|GRANTED|AUTHORIZED)\b"
    r"|\bCW-021\s*=\s*AUTHORIZED\b"
    r"|\bHUMAN_INDEPENDENT_SECURITY_REVIEW\s*=\s*PERFORMED\b"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    following = text.find("\n## ", start + len(heading))
    return text[start:] if following < 0 else text[start:following]


def _rows(section: str, ids: tuple[str, ...]) -> dict[str, list[str]]:
    rows: dict[str, list[str]] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] in ids:
            assert cells[0] not in rows, f"duplicate row {cells[0]}"
            rows[cells[0]] = cells
    return rows


def test_implementation_identities_are_bound_exactly() -> None:
    closeout = _read(CLOSEOUT)
    qualification = _section(closeout, "## 6. Exact-head qualification")
    assert f"EXACT HEAD  {IMPLEMENTATION_HEAD} (tree {IMPLEMENTATION_TREE})" in qualification
    assert f"on base {IMPLEMENTATION_BASE}" in qualification
    assert f"SHA       {IMPLEMENTATION_MERGE}" in qualification
    assert f"PARENTS   {IMPLEMENTATION_BASE}, {IMPLEMENTATION_HEAD}" in qualification
    assert f"TREE      {IMPLEMENTATION_TREE} (= qualified head tree" in qualification
    assert f"FRESH MAIN {IMPLEMENTATION_MERGE}" in qualification
    header = closeout[: closeout.index("\n## ")]
    assert f"`{IMPLEMENTATION_HEAD}` (tree `{IMPLEMENTATION_TREE}`)" in header
    assert f"`{IMPLEMENTATION_MERGE}` (tree `{IMPLEMENTATION_TREE}`)" in header
    for sha in re.findall(r"\b[0-9a-f]{40}\b", closeout):
        assert sha in {
            IMPLEMENTATION_HEAD,
            IMPLEMENTATION_TREE,
            IMPLEMENTATION_MERGE,
            IMPLEMENTATION_BASE,
        }, sha
    (evidence_revision,) = re.findall(r"^EVIDENCE_REVISION   ([0-9a-f]{40})$", _read(PACKET), re.M)
    assert evidence_revision == IMPLEMENTATION_BASE


def test_workflow_runs_are_bound_exactly() -> None:
    qualification = _section(_read(CLOSEOUT), "## 6. Exact-head qualification")
    exact, fresh = qualification.split("FRESH MAIN", 1)
    for lane, run in EXACT_HEAD_RUNS.items():
        assert re.search(rf"^  {re.escape(lane)} +{run} \(pull_request\): SUCCESS", exact, re.M), (
            lane
        )
    for lane, run in FRESH_MAIN_RUNS.items():
        assert re.search(rf"^  {re.escape(lane)} +{run} \(push\): SUCCESS$", fresh, re.M), lane
    runs = set(re.findall(r"\b\d{11}\b", qualification))
    assert runs == set(EXACT_HEAD_RUNS.values()) | set(FRESH_MAIN_RUNS.values())


def test_every_gap_is_preserved_open_with_the_packet_severity() -> None:
    packet = _rows(_section(_read(PACKET), "## 6. Unresolved risk register"), GAP_IDS)
    closeout = _rows(_section(_read(CLOSEOUT), "## 7. PHI-readiness gaps"), GAP_IDS)
    assert set(packet) == set(closeout) == set(GAP_IDS)
    for gap in GAP_IDS:
        assert closeout[gap][1] == packet[gap][1], gap
        assert closeout[gap][-1] == "OPEN", gap


def test_every_residual_risk_is_preserved_unprotected_with_the_packet_severity() -> None:
    packet = _rows(_section(_read(PACKET), "## 6. Unresolved risk register"), RISK_IDS)
    closeout = _rows(_section(_read(CLOSEOUT), "## 8. CW-019 residual risks"), RISK_IDS)
    assert set(packet) == set(closeout) == set(RISK_IDS)
    for risk in RISK_IDS:
        assert closeout[risk][1] == packet[risk][1], risk
        assert closeout[risk][-1] == packet[risk][-1], risk
    risks = _section(_read(CLOSEOUT), "## 8. CW-019 residual risks")
    assert "F11 = MITIGATED, NOT FIXED" in risks
    assert not re.search(r"\b(FIXED|CLOSED|RESOLVED|PROTECTED)\s*\|", risks)


def test_verdict_and_non_grants_stay_not_ready_and_not_granted() -> None:
    closeout = _read(CLOSEOUT)
    assert not FORBIDDEN_CLAIM.search(closeout)
    non_grants = _section(closeout, "## 11. Explicit non-grants")
    for line in (
        "MODEL_AUTHORITY = NONE",
        "PHI_AUTHORIZATION = NOT_GRANTED",
        "PRODUCTION_AUTHORIZATION = NOT_GRANTED",
        "REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED",
        "REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED",
        "NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED",
        "EHR_WRITE_AUTHORIZATION = NOT_GRANTED",
        "EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED",
        "TRAINING_AUTHORIZATION = NOT_GRANTED",
        "PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED",
        "RESEARCH_ADMISSION_OF_WORKSPACE_DATA = NOT_GRANTED",
        "CLINICAL_PILOT_AUTHORIZATION = NOT_GRANTED (CW-021 NOT AUTHORIZED)",
        "PHI_READINESS = NOT_READY",
        "PRODUCTION_READINESS = NOT_READY",
        "PHI_ASSESSMENT_SCOPE = CLINICAL_WORKSPACE_ONLY",
        "HUMAN_INDEPENDENT_SECURITY_REVIEW = NOT_PERFORMED (R7)",
    ):
        assert line in non_grants, line
    verdict = closeout[: closeout.index("\n## ")]
    for line in (
        "PHI_READINESS = NOT_READY",
        "PRODUCTION_READINESS = NOT_READY",
        "CW-021 = NOT AUTHORIZED",
    ):
        assert line in verdict, line


def test_closure_is_conditional_on_the_approved_closeout_merge() -> None:
    closeout = _read(CLOSEOUT)
    (status,) = re.findall(r"^- \*\*Status:\*\* (.+)$", closeout, re.M)
    assert status.startswith("`CLOSED_CANONICAL` only when"), status
    assert "explicit Founder exact-head approval" in status
    result = _section(closeout, "## 10. Result")
    assert "CW-020 = CLOSED_CANONICAL only on closeout merge" in result
    assert "(NOT AUTHORIZED)" in result


def test_the_merge_authority_gap_is_recorded_and_not_backfilled() -> None:
    closeout = _read(CLOSEOUT)
    authority = _section(closeout, "### 2.3 Merge authority")
    assert (
        f"No explicit exact-head merge approval for `{IMPLEMENTATION_HEAD}` is provable"
        in authority
    )
    assert "does not create or imply a retroactive pre-merge approval" in authority
    assert "APPROVAL    none provable before merge" in closeout
    assert "Approved: merge PR #527" not in closeout


def test_the_assessment_scope_stays_workspace_only() -> None:
    scope = _section(_read(CLOSEOUT), "## 9. Scope limitation")
    for component in (
        "Research Core",
        "MRL",
        "training/adapter paths",
        "publication paths",
        "separately governed external system",
    ):
        assert component in scope, component
    assert "must not be generalized into whole-MESC PHI readiness" in scope


def test_the_jev_history_is_preserved() -> None:
    jev = _section(_read(CLOSEOUT), "## 4. Jev record")
    for record in (
        "evidence_incomplete 0.66 YES",
        "sets 1-3: 17 NO / 0 YES",
        "All 11 completeness sub-probe YES signals",
        "cw021_authorized 0.12 NO (NOT detected by Jev)",
        "verdict_ready 0.82 YES (detected)",
        "r7_severity_changed 0.51 YES (detected)",
        "NOT A DEFECT",
    ):
        assert record in jev, record


def test_the_ledger_keeps_cw021_unauthorized() -> None:
    ledger = _read(LEDGER)
    cw021 = _section(ledger, "## CW-021")
    (state,) = re.findall(r"^\*\*State:\*\* `([A-Z_]+)`", cw021, re.M)
    assert state == "BLOCKED_DEPENDENCY"
    assert "No generic roadmap approval" in cw021
    assert not FORBIDDEN_CLAIM.search(ledger)
    cw020 = _section(ledger, "## CW-020")
    assert "**State:** `CLOSED_CANONICAL`" in cw020
    assert "PHI_READINESS = NOT_READY" in cw020


CORRUPTIONS = (
    (
        "No explicit exact-head merge approval for `",
        "An explicit exact-head merge approval for `",
        "test_the_merge_authority_gap_is_recorded_and_not_backfilled",
    ),
    (
        "EXACT HEAD  141e4d46dc580ac077d204db1ef4dfb532a6db74",
        "EXACT HEAD  141e4d46dc580ac077d204db1ef4dfb532a6db75",
        "test_implementation_identities_are_bound_exactly",
    ),
    (
        "PARENTS   3b3efa1c02b641a9107060bc51788960a4256b7f,",
        "PARENTS   ef1d6f7272eeb961af6ed65b537da99291f554fd,",
        "test_implementation_identities_are_bound_exactly",
    ),
    (
        "TREE      30f5a753037fad7c6b280b3ecc70494c397ed3d0",
        "TREE      fa685bd33c1e6a0ecbec9f2b34563a747699b649",
        "test_implementation_identities_are_bound_exactly",
    ),
    (
        "36697110726 (push): SUCCESS",
        "36697110727 (push): SUCCESS",
        "test_workflow_runs_are_bound_exactly",
    ),
    (
        "36692279944 (pull_request): SUCCESS",
        "36692279944 (pull_request): FAILURE",
        "test_workflow_runs_are_bound_exactly",
    ),
    (
        "| G1 | HIGH |",
        "| G1 | MEDIUM |",
        "test_every_gap_is_preserved_open_with_the_packet_severity",
    ),
    (
        "`LOGIN`, `WORKSPACE_OPEN` and `WORKSPACE_CLOSE` are declared but never emitted | OPEN |",
        "`LOGIN`, `WORKSPACE_OPEN` and `WORKSPACE_CLOSE` are declared but never emitted | CLOSED |",
        "test_every_gap_is_preserved_open_with_the_packet_severity",
    ),
    (
        "ADR-0038 keeps `PHI_INGESTION = NOT_AUTHORIZED` | OPEN |",
        "ADR-0041 scopes the PHI pilot | FIXED |",
        "test_every_gap_is_preserved_open_with_the_packet_severity",
    ),
    (
        "sealed copy remains undetected | OPEN, blocking |",
        "sealed copy is now detected | CLOSED |",
        "test_every_residual_risk_is_preserved_unprotected_with_the_packet_severity",
    ),
    (
        "| R7 | MEDIUM |",
        "| R7 | LOW |",
        "test_every_residual_risk_is_preserved_unprotected_with_the_packet_severity",
    ),
    (
        "F11 = MITIGATED, NOT FIXED",
        "F11 = FIXED",
        "test_every_residual_risk_is_preserved_unprotected_with_the_packet_severity",
    ),
    (
        "PHI_READINESS = NOT_READY\nPRODUCTION_READINESS = NOT_READY\nCW-021",
        "PHI_READINESS = READY\nPRODUCTION_READINESS = NOT_READY\nCW-021",
        "test_verdict_and_non_grants_stay_not_ready_and_not_granted",
    ),
    (
        "PRODUCTION_READINESS = NOT_READY\nQUALIFICATION_SCOPE",
        "PRODUCTION_READINESS = READY\nQUALIFICATION_SCOPE",
        "test_verdict_and_non_grants_stay_not_ready_and_not_granted",
    ),
    (
        "CW-021 = NOT AUTHORIZED\nPHI_READINESS_EVIDENCE",
        "CW-021 = AUTHORIZED\nPHI_READINESS_EVIDENCE",
        "test_verdict_and_non_grants_stay_not_ready_and_not_granted",
    ),
    (
        "HUMAN_INDEPENDENT_SECURITY_REVIEW = NOT_PERFORMED (R7)",
        "HUMAN_INDEPENDENT_SECURITY_REVIEW = PERFORMED",
        "test_verdict_and_non_grants_stay_not_ready_and_not_granted",
    ),
    (
        "- **Status:** `CLOSED_CANONICAL` only when",
        "- **Status:** `CLOSED_CANONICAL`; closed when",
        "test_closure_is_conditional_on_the_approved_closeout_merge",
    ),
    (
        "- Research Core;\n- MRL;\n",
        "",
        "test_the_assessment_scope_stays_workspace_only",
    ),
    (
        "cw021_authorized 0.12 NO (NOT detected by Jev)",
        "cw021_authorized 0.88 YES (detected)",
        "test_the_jev_history_is_preserved",
    ),
    (
        "evidence_incomplete 0.66 YES\n6",
        "evidence_incomplete 0.36 NO\n6",
        "test_the_jev_history_is_preserved",
    ),
    # Jev scored both of these single-line corruptions NO, even on section-scoped inputs.
    (
        "No explicit exact-head merge approval for `",
        "The Founder gave explicit exact-head merge approval before merge for `",
        "test_the_merge_authority_gap_is_recorded_and_not_backfilled",
    ),
    (
        "CW-021 = BLOCKED: its CW-020 dependency",
        "CW-021 = AUTHORIZED: its CW-020 dependency",
        "test_verdict_and_non_grants_stay_not_ready_and_not_granted",
    ),
)

LEDGER_CORRUPTIONS = (
    (
        "**State:** `BLOCKED_DEPENDENCY`\n\n**Depends on:** CW-020",
        "**State:** `ELIGIBLE`\n\n**Depends on:** CW-020",
    ),
    ("CW-021 is **NOT AUTHORIZED**: it requires", "CW-021 = AUTHORIZED: it requires"),
    (
        "**State:** `CLOSED_CANONICAL`\n\n**Depends on:** CW-019.",
        "**State:** `IN_PROGRESS`\n\n**Depends on:** CW-019.",
    ),
)


@pytest.mark.parametrize(("original", "corrupted", "check"), CORRUPTIONS)
def test_the_binding_rejects_a_corrupted_closeout(
    original: str,
    corrupted: str,
    check: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _read(CLOSEOUT)
    assert text.count(original) == 1, original
    copy = tmp_path / "closeout.md"
    copy.write_text(text.replace(original, corrupted), encoding="utf-8")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "CLOSEOUT", copy)
    with pytest.raises(AssertionError):
        getattr(module, check)()


@pytest.mark.parametrize(("original", "corrupted"), LEDGER_CORRUPTIONS)
def test_the_binding_rejects_a_corrupted_ledger(
    original: str,
    corrupted: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = _read(LEDGER)
    assert text.count(original) == 1, original
    copy = tmp_path / "tasks.md"
    copy.write_text(text.replace(original, corrupted), encoding="utf-8")
    module = sys.modules[__name__]
    monkeypatch.setattr(module, "LEDGER", copy)
    with pytest.raises(AssertionError):
        test_the_ledger_keeps_cw021_unauthorized()
