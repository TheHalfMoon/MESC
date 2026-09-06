from __future__ import annotations

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
ROSTER_PATH = ROOT / "specs" / "mesc-experiment-0" / "candidate-roster-v1.json"


def _load_verifier() -> ModuleType:
    """Load the Phase 0 roster verifier from the repository tree."""
    path = ROOT / "tools" / "verify_mesc_experiment_0_candidate_roster.py"
    spec = importlib.util.spec_from_file_location("mesc_exp0_candidate_roster", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()


def _roster() -> dict[str, Any]:
    """Return a mutable copy of the committed Phase 0 roster."""
    value = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_committed_phase0_roster_is_valid_and_metadata_only() -> None:
    """The committed roster freezes identity without granting execution or training."""
    roster = VERIFIER.load_and_validate(ROSTER_PATH)
    assert roster["status"] == "FROZEN_METADATA_ONLY"
    assert roster["result_exposure_started"] is False
    assert roster["mrl_0801_state"] == "ABSENT"
    assert roster["real_model_execution_authorized"] is False
    assert roster["training_authorized"] is False


def test_active_roster_freezes_expected_exact_candidate_revisions() -> None:
    """Active candidates use exact full upstream revisions and closed roles."""
    roster = VERIFIER.load_and_validate(ROSTER_PATH)
    observed = {
        (item["candidate_id"], item["candidate_revision"], item["role"])
        for item in roster["active_candidates"]
    }
    assert observed == {
        (
            "Qwen/Qwen3.8-27B",
            "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
            "PREFERRED_FOUNDATION_CANDIDATE",
        ),
        (
            "google/gemma-4-31B-it",
            "842da3794eaa0b77d5f08bae87a17459d91ff475",
            "PRIMARY_CHALLENGER",
        ),
    }


def test_active_roster_cannot_use_floating_revision() -> None:
    """Floating aliases cannot become Experiment-0 candidate identities."""
    roster = _roster()
    roster["active_candidates"][0]["candidate_revision"] = "main"
    with pytest.raises(VERIFIER.CandidateRosterError, match="40-character"):
        VERIFIER.validate_roster(roster)


def test_active_roster_cannot_enable_remote_code() -> None:
    """An active candidate cannot silently broaden the remote-code boundary."""
    roster = _roster()
    roster["active_candidates"][0]["trust_remote_code"] = True
    with pytest.raises(VERIFIER.CandidateRosterError, match="cannot require remote code"):
        VERIFIER.validate_roster(roster)


def test_active_roster_cannot_claim_mrl_0801_or_execution_authority() -> None:
    """Phase 0 metadata cannot manufacture MRL evidence or execution authority."""
    for key, value in (
        ("mrl_0801_state", "QUALIFIED"),
        ("real_model_execution_authorized", True),
        ("training_authorized", True),
    ):
        roster = _roster()
        roster[key] = value
        with pytest.raises(VERIFIER.CandidateRosterError):
            VERIFIER.validate_roster(roster)


def test_duplicate_active_identity_fails_closed() -> None:
    """Candidate identity duplication is rejected before any later execution config."""
    roster = _roster()
    duplicate = deepcopy(roster["active_candidates"][0])
    duplicate["role"] = "SECONDARY_CHALLENGER"
    duplicate["evidence_key"] = "duplicate-qwen"
    roster["active_candidates"].append(duplicate)
    with pytest.raises(VERIFIER.CandidateRosterError, match="duplicate candidate identity"):
        VERIFIER.validate_roster(roster)


def test_phi4_control_remains_deferred_for_remote_code() -> None:
    """Phi-4 stays outside the active roster until a separate exception exists."""
    roster = VERIFIER.load_and_validate(ROSTER_PATH)
    deferred = roster["deferred_controls"]
    assert len(deferred) == 1
    phi = deferred[0]
    assert phi["candidate_id"] == "microsoft/Phi-4-multimodal-instruct"
    assert phi["trust_remote_code_required_by_published_path"] is True
    assert phi["eligibility_disposition"] == "DEFERRED_REMOTE_CODE_EXCEPTION_REQUIRED"
