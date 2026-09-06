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
    first = roster["active_candidates"][0]
    second = roster["active_candidates"][1]
    second["candidate_id"] = first["candidate_id"]
    second["candidate_revision"] = first["candidate_revision"]
    with pytest.raises(VERIFIER.CandidateRosterError, match="duplicate candidate identity"):
        VERIFIER.validate_roster(roster)


def test_extra_active_candidate_fails_closed() -> None:
    """The frozen active roster cannot be widened with a third candidate."""
    roster = _roster()
    extra = deepcopy(roster["active_candidates"][0])
    extra["candidate_id"] = "example/third-candidate"
    extra["candidate_revision"] = "a" * 40
    extra["role"] = "SECONDARY_CHALLENGER"
    extra["evidence_key"] = "third-candidate"
    roster["active_candidates"].append(extra)
    with pytest.raises(VERIFIER.CandidateRosterError, match="exactly two frozen candidates"):
        VERIFIER.validate_roster(roster)


def test_active_candidate_binding_cannot_be_substituted() -> None:
    """A different candidate cannot inherit one of the two frozen active roles."""
    roster = _roster()
    roster["active_candidates"][0]["candidate_id"] = "example/substitute"
    with pytest.raises(VERIFIER.CandidateRosterError, match="exact frozen roster binding mismatch"):
        VERIFIER.validate_roster(roster)


def test_active_modalities_cannot_be_widened() -> None:
    """Phase 0 multimodal scope remains exactly text and vision."""
    roster = _roster()
    roster["active_candidates"][0]["supported_input_modalities"].append("audio")
    with pytest.raises(VERIFIER.CandidateRosterError, match="exactly text and vision"):
        VERIFIER.validate_roster(roster)


@pytest.mark.parametrize("field", ["canonical_base_sha", "canonical_base_tree"])
def test_frozen_repository_binding_cannot_drift(field: str) -> None:
    """The roster remains bound to the exact canonical base commit and tree."""
    roster = _roster()
    roster[field] = "a" * 40
    with pytest.raises(VERIFIER.CandidateRosterError, match="does not match the frozen roster"):
        VERIFIER.validate_roster(roster)


def test_freeze_timestamp_cannot_drift() -> None:
    """The frozen roster timestamp is part of the immutable Phase 0 record."""
    roster = _roster()
    roster["frozen_at_utc"] = "2026-09-06T21:19:58Z"
    with pytest.raises(VERIFIER.CandidateRosterError, match="freeze timestamp"):
        VERIFIER.validate_roster(roster)


@pytest.mark.parametrize(
    ("needle", "replacement", "duplicate_key"),
    [
        (
            '"training_authorized": false,',
            '"training_authorized": true,\n  "training_authorized": false,',
            "training_authorized",
        ),
        (
            '"trust_remote_code": false,',
            '"trust_remote_code": true,\n      "trust_remote_code": false,',
            "trust_remote_code",
        ),
    ],
)
def test_duplicate_security_or_authority_json_key_fails_closed(
    tmp_path: Path,
    needle: str,
    replacement: str,
    duplicate_key: str,
) -> None:
    """Duplicate JSON keys cannot conceal an earlier security or authority value."""
    original = ROSTER_PATH.read_text(encoding="utf-8")
    tampered = original.replace(needle, replacement, 1)
    assert tampered != original
    path = tmp_path / "duplicate-key-roster.json"
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(
        VERIFIER.CandidateRosterError,
        match=rf"duplicate JSON key: {duplicate_key}",
    ):
        VERIFIER.load_and_validate(path)


def test_nonstandard_json_constant_fails_closed(tmp_path: Path) -> None:
    """NaN and Infinity cannot enter the roster through Python JSON extensions."""
    original = ROSTER_PATH.read_text(encoding="utf-8")
    tampered = original.replace(
        '"published_weight_size_label": "55.6 GB"',
        '"published_weight_size_label": NaN',
        1,
    )
    assert tampered != original
    path = tmp_path / "nonstandard-json-roster.json"
    path.write_text(tampered, encoding="utf-8")
    with pytest.raises(VERIFIER.CandidateRosterError, match="non-standard JSON constant: NaN"):
        VERIFIER.load_and_validate(path)


def test_duplicate_authoritative_source_fails_closed() -> None:
    """Source provenance cannot contain duplicate entries."""
    roster = _roster()
    sources = roster["active_candidates"][0]["authoritative_sources"]
    sources.append(sources[0])
    with pytest.raises(VERIFIER.CandidateRosterError, match="duplicate authoritative source"):
        VERIFIER.validate_roster(roster)


def test_duplicate_deferred_control_fails_closed() -> None:
    """A deferred control cannot be repeated under the closed roster roles."""
    roster = _roster()
    roster["deferred_controls"].append(deepcopy(roster["deferred_controls"][0]))
    with pytest.raises(VERIFIER.CandidateRosterError, match="exactly one frozen control"):
        VERIFIER.validate_roster(roster)


def test_deferred_control_cannot_be_removed() -> None:
    """The frozen Phi-4 control cannot disappear from Phase 0 metadata."""
    roster = _roster()
    roster["deferred_controls"] = []
    with pytest.raises(VERIFIER.CandidateRosterError, match="exactly one frozen control"):
        VERIFIER.validate_roster(roster)


def test_deferred_control_binding_cannot_be_substituted() -> None:
    """A different remote-code model cannot inherit the frozen control role."""
    roster = _roster()
    roster["deferred_controls"][0]["candidate_id"] = "example/other-remote-code-model"
    with pytest.raises(
        VERIFIER.CandidateRosterError,
        match="exact frozen deferred-control binding mismatch",
    ):
        VERIFIER.validate_roster(roster)


def test_active_candidate_cannot_reappear_as_deferred_control() -> None:
    """Candidate identity is unique across active and deferred roster sections."""
    roster = _roster()
    roster["deferred_controls"][0]["candidate_id"] = roster["active_candidates"][0]["candidate_id"]
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
