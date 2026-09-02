"""ALIGN-20 tests for the deterministic fixture-only executable golden path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from medscale.cli import main as cli_main
from medscale.cli import mesc_fixture_smoke
from medscale.mesc._mrl_fixture_smoke_v1 import build_fixture_smoke_payload
from medscale.reproducibility import canonical_json

_HASH_FIELDS = (
    "proposal_sha256",
    "observation_sha256",
    "receipt_sha256",
    "decision_sha256",
    "result_sha256",
)


def test_fixture_smoke_payload_is_deterministic_reject_non_evidence() -> None:
    first = build_fixture_smoke_payload()
    second = build_fixture_smoke_payload()

    assert first == second
    assert canonical_json(first) == canonical_json(second)
    assert first["format"] == "MESC-FIXTURE-SMOKE-V1"
    assert first["decision_state"] == "REJECT"
    assert first["fixture_only"] is True
    assert first["non_evidence"] is True
    for field in _HASH_FIELDS:
        value = first[field]
        assert isinstance(value, str)
        assert len(value) == 64


def test_fixture_smoke_payload_denies_all_authority_flags() -> None:
    payload = build_fixture_smoke_payload()

    for field in (
        "filesystem_writes",
        "network_access",
        "model_execution",
        "training_authorized",
        "promotion_authorized",
        "release_authorized",
        "deployment_authorized",
        "clinical_authority",
    ):
        assert payload[field] is False


def test_fixture_smoke_cli_is_byte_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    assert mesc_fixture_smoke.main([]) == 0
    first = capsys.readouterr().out

    assert mesc_fixture_smoke.main([]) == 0
    second = capsys.readouterr().out

    assert first == second
    assert first.endswith("\n")
    assert first.count("\n") == 1
    assert json.loads(first)["decision_state"] == "REJECT"


def test_fixture_smoke_cli_writes_no_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    before = tuple(tmp_path.rglob("*"))

    assert mesc_fixture_smoke.main([]) == 0
    capsys.readouterr()

    assert tuple(tmp_path.rglob("*")) == before


def test_fixture_smoke_dispatcher_integration(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["mesc-fixture-smoke"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert payload["decision_state"] == "REJECT"


def test_fixture_smoke_help_is_explicitly_non_authoritative() -> None:
    text = mesc_fixture_smoke.DESCRIPTION.lower()
    assert "fixture-only" in text
    assert "non-evidence" in text
    assert "no model" in text
    assert "network" in text
    assert "gpu" in text
    assert "training" in text
