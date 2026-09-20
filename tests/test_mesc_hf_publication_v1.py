"""Tests for fail-closed Hugging Face publication dry-run qualification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._hf_publication_v1 import (
    HfPublicationArtifact,
    HfPublicationPlan,
    HfPublicationQualification,
    HfPublicationQualificationError,
    build_dry_run_receipt,
    parse_publication_plan,
    qualify_publication_plan,
)

_SHA = "a" * 40
_TREE = "b" * 40
_HASH = "c" * 64


def _artifact(path: str = "README.md", *, digest: str = _HASH) -> HfPublicationArtifact:
    return HfPublicationArtifact(path=path, byte_count=123, sha256=digest)


def _plan(**overrides: object) -> HfPublicationPlan:
    kwargs: dict[str, object] = {
        "artifact_class": "space",
        "destination_owner": "MedScaleAI",
        "destination_repo": "medscale",
        "source_repository": "TheHalfMoon/MESC",
        "source_sha": _SHA,
        "source_tree": _TREE,
        "source_tag": "v0.3.0",
        "artifacts": (_artifact(), _artifact("app.py", digest="d" * 64)),
        "card_sha256": _HASH,
        "rights_sha256": "f" * 64,
        "provenance_sha256": "1" * 64,
        "license_id": "Apache-2.0",
        "external_upload_enabled": False,
    }
    kwargs.update(overrides)
    return HfPublicationPlan(**kwargs)  # type: ignore[arg-type]


def _qualify(plan: HfPublicationPlan) -> HfPublicationQualification:
    return qualify_publication_plan(
        plan,
        expected_repository="TheHalfMoon/MESC",
        expected_sha=_SHA,
        expected_tree=_TREE,
    )


def test_valid_plan_is_dry_run_ready_and_receipt_is_nonpublishing() -> None:
    plan = _plan()
    report = _qualify(plan)
    assert report.disposition == "DRY_RUN_READY"
    assert report.blockers == ()
    receipt = json.loads(build_dry_run_receipt(plan, report))
    assert receipt["external_upload_performed"] is False
    assert receipt["destination_owner"] == "MedScaleAI"
    assert receipt["destination_repo_type"] == "space"


def test_wrong_owner_is_blocked() -> None:
    report = _qualify(_plan(destination_owner="OtherOrg"))
    assert report.disposition == "BLOCKED"
    assert "destination owner is outside the authorized allowlist" in report.blockers


def test_external_upload_true_is_blocked_during_repository_qualification() -> None:
    report = _qualify(_plan(external_upload_enabled=True))
    assert report.disposition == "BLOCKED"
    assert "external upload must remain disabled" in report.blockers[0]


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("source_repository", "OtherOrg/OtherRepo", "source repository"),
        ("source_sha", "c" * 40, "source SHA"),
        ("source_tree", "d" * 40, "source tree"),
    ],
)
def test_stale_or_wrong_source_identity_is_blocked(field: str, value: str, expected: str) -> None:
    report = _qualify(_plan(**{field: value}))
    assert report.disposition == "BLOCKED"
    assert any(expected in blocker for blocker in report.blockers)


def test_missing_readme_card_is_blocked() -> None:
    report = _qualify(_plan(artifacts=(_artifact("app.py"),)))
    assert report.disposition == "BLOCKED"
    assert "Hugging Face card README.md is absent" in report.blockers


def test_artifact_manifest_is_order_independent() -> None:
    a = _artifact()
    b = _artifact("app.py", digest="d" * 64)
    left = _plan(artifacts=(a, b))
    right = _plan(artifacts=(b, a))
    assert left.artifact_manifest_sha256 == right.artifact_manifest_sha256


@pytest.mark.parametrize(
    "path",
    ["/README.md", "../README.md", "a/../README.md", "a\\b", "a//b", "a/./b"],
)
def test_unsafe_artifact_paths_are_rejected(path: str) -> None:
    with pytest.raises(HfPublicationQualificationError, match="safe and relative"):
        _artifact(path)


def test_duplicate_artifact_paths_are_rejected() -> None:
    with pytest.raises(HfPublicationQualificationError, match="unique"):
        _plan(artifacts=(_artifact(), _artifact()))


@pytest.mark.parametrize("name", ["MedScale", "med_scale", "medscale-", "-medscale"])
def test_destination_repo_must_be_lowercase_kebab(name: str) -> None:
    with pytest.raises(HfPublicationQualificationError, match="lowercase kebab-case"):
        _plan(destination_repo=name)


def test_plan_parser_requires_canonical_json_and_exact_keys() -> None:
    plan = _plan()
    raw = canonical_json_bytes(plan.to_dict())
    parsed = parse_publication_plan(raw)
    assert parsed == plan

    noncanonical = json.dumps(plan.to_dict(), indent=2).encode()
    with pytest.raises(HfPublicationQualificationError, match="canonical JSON"):
        parse_publication_plan(noncanonical)

    payload = plan.to_dict()
    payload["token"] = "secret"
    with pytest.raises(HfPublicationQualificationError, match="keys drifted"):
        parse_publication_plan(canonical_json_bytes(payload))


def test_card_hash_must_bind_readme_artifact() -> None:
    plan = _plan(card_sha256="e" * 64)
    report = _qualify(plan)
    assert report.disposition == "BLOCKED"
    assert "card_sha256 does not bind README.md" in report.blockers


def test_cli_writes_exact_nonpublishing_receipt(tmp_path: Path) -> None:
    plan = _plan()
    plan_path = tmp_path / "plan.json"
    receipt_path = tmp_path / "receipt.json"
    plan_path.write_bytes(canonical_json_bytes(plan.to_dict()))
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/mesc_hf_publication.py",
            "--plan",
            str(plan_path),
            "--expected-repository",
            "TheHalfMoon/MESC",
            "--expected-sha",
            _SHA,
            "--expected-tree",
            _TREE,
            "--receipt-out",
            str(receipt_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["external_upload_performed"] is False
    assert receipt["source_sha"] == _SHA
    assert receipt["destination_owner"] == "MedScaleAI"


def test_dry_run_receipt_rejects_blocked_qualification() -> None:
    plan = _plan(destination_owner="OtherOrg")
    report = _qualify(plan)
    with pytest.raises(HfPublicationQualificationError, match="DRY_RUN_READY"):
        build_dry_run_receipt(plan, report)


def test_receipt_rejects_qualification_for_different_plan() -> None:
    plan = _plan()
    report = _qualify(plan)
    changed = replace(plan, source_tag="v0.3.1")
    with pytest.raises(HfPublicationQualificationError, match="does not bind"):
        build_dry_run_receipt(changed, report)


def test_plan_identity_is_deterministic() -> None:
    plan = _plan()
    report = _qualify(plan)
    expected = hashlib.sha256(canonical_json_bytes(plan.to_dict())).hexdigest()
    assert report.plan_sha256 == expected
