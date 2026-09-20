from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import medscale.mesc._hf_publication_v2 as v2
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._hf_publication_v1 import HfPublicationArtifact, HfPublicationPlan

SHA = "a" * 40
TREE = "b" * 40
HASH = hashlib.sha256(b"abc").hexdigest()
BODY = "Founder authorization exact body"
BODY_SHA = hashlib.sha256(BODY.encode()).hexdigest()


def plan() -> HfPublicationPlan:
    return HfPublicationPlan(
        artifact_class="space",
        destination_owner="MedScaleAI",
        destination_repo="medscale",
        source_repository="TheHalfMoon/MESC",
        source_sha=SHA,
        source_tree=TREE,
        source_tag="-bad",
        artifacts=(HfPublicationArtifact(path="README.md", byte_count=3, sha256=HASH),),
        card_sha256=HASH,
        rights_sha256="d" * 64,
        provenance_sha256="e" * 64,
        license_id="Apache-2.0",
        external_upload_enabled=False,
    )


def active_authority(*, environment_policy_sha256: str = "f" * 64) -> v2.PublicationAuthority:
    p = plan()
    asset = v2.ReleaseAssetBinding(
        path="README.md", asset_name="README.md", byte_count=3, sha256=HASH
    )
    assets_sha = hashlib.sha256(canonical_json_bytes([asset.to_dict()])).hexdigest()
    plan_sha = hashlib.sha256(canonical_json_bytes(p.to_dict())).hexdigest()
    return v2.PublicationAuthority(
        state="ACTIVE",
        plan=p,
        plan_sha256=plan_sha,
        artifact_manifest_sha256=p.artifact_manifest_sha256,
        release_assets=(asset,),
        release_assets_sha256=assets_sha,
        authority_repository="TheHalfMoon/MESC",
        authority_issue_number=451,
        authority_comment_id=123,
        authority_actor="TheHalfMoon",
        authority_body_sha256=BODY_SHA,
        environment_name="huggingface-publication",
        environment_policy_sha256=environment_policy_sha256,
        destination_parent_commit="1" * 40,
        destination_parent_inventory_sha256="2" * 64,
        publication_mode="trusted-publisher-oidc-v1",
        transport_manifest_sha256="3" * 64,
    )


def test_disabled_authority_is_minimal_and_canonical() -> None:
    raw = canonical_json_bytes({"schema_version": v2.SCHEMA_AUTHORITY, "state": "DISABLED"})
    authority = v2.parse_authority(raw)
    assert authority.state == "DISABLED"
    with pytest.raises(v2.HfPublicationTransportError, match="not ACTIVE"):
        v2.verify_live_github_boundaries(
            authority,
            github_token="token",
            expected_repository="TheHalfMoon/MESC",
            expected_workflow_sha=SHA,
            expected_workflow_ref=v2.EXPECTED_WORKFLOW_REF,
        )


def test_disabled_authority_rejects_activation_data() -> None:
    raw = canonical_json_bytes(
        {
            "schema_version": v2.SCHEMA_AUTHORITY,
            "state": "DISABLED",
            "plan_sha256": HASH,
        }
    )
    with pytest.raises(v2.HfPublicationTransportError, match="keys drifted"):
        v2.parse_authority(raw)


def test_authority_requires_exact_release_asset_binding() -> None:
    authority = active_authority()
    assert authority.repo_id == "MedScaleAI/medscale"
    assert authority.oidc_resource == "spaces/MedScaleAI/medscale"
    bad_asset = v2.ReleaseAssetBinding(
        path="README.md",
        asset_name="README.md",
        byte_count=4,
        sha256=HASH,
    )
    with pytest.raises(v2.HfPublicationTransportError, match="identity"):
        replace(authority, release_assets=(bad_asset,))


def test_materialization_protects_leading_hyphen_tag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    authority = active_authority()
    seen: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        seen.append(command)
        target = Path(command[command.index("--output") + 1])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"abc")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    payload = tmp_path / "payload"
    v2.materialize_release_assets(tmp_path, authority, payload, github_token="gh")
    assert seen
    assert seen[0][-2:] == ["--", "-bad"]


def test_materialization_rejects_payload_root_symlink(tmp_path: Path) -> None:
    target = tmp_path / "real"
    target.mkdir()
    payload = tmp_path / "payload"
    payload.symlink_to(target, target_is_directory=True)
    with pytest.raises(v2.HfPublicationTransportError, match="symlink"):
        v2.materialize_release_assets(tmp_path, active_authority(), payload, github_token="gh")


def github_payloads(*, protected: bool = True, total_count: int = 1) -> dict[str, object]:
    environment = {
        "name": "huggingface-publication",
        "can_admins_bypass": False,
        "protection_rules": (
            [{"id": 7, "type": "wait_timer", "wait_timer": 1}] if protected else []
        ),
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }
    return {
        "branch": {"commit": {"sha": SHA}},
        "comment": {
            "id": 123,
            "user": {"login": "TheHalfMoon"},
            "body": BODY,
            "issue_url": "https://api.github.com/repos/TheHalfMoon/MESC/issues/451",
        },
        "environment": environment,
        "policies": {
            "total_count": total_count,
            "branch_policies": [{"id": 9, "name": "main", "type": "branch"}],
        },
    }


def install_github_stub(monkeypatch: pytest.MonkeyPatch, payloads: dict[str, object]) -> None:
    def fake(path: str, token: str) -> object:
        assert token == "gh"
        if path.endswith("/branches/main"):
            return payloads["branch"]
        if "/issues/comments/" in path:
            return payloads["comment"]
        if "deployment-branch-policies" in path:
            return payloads["policies"]
        if "/environments/" in path:
            return payloads["environment"]
        raise AssertionError(path)

    monkeypatch.setattr(v2, "_github_json", fake)


def test_live_boundary_binds_main_comment_and_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = github_payloads()
    install_github_stub(monkeypatch, payloads)
    policy_sha = v2._environment_policy_sha256("gh")
    authority = active_authority(environment_policy_sha256=policy_sha)
    assert (
        v2.verify_live_github_boundaries(
            authority,
            github_token="gh",
            expected_repository="TheHalfMoon/MESC",
            expected_workflow_sha=SHA,
            expected_workflow_ref=v2.EXPECTED_WORKFLOW_REF,
        )
        == policy_sha
    )


def test_live_boundary_rejects_noncanonical_main(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = github_payloads()
    install_github_stub(monkeypatch, payloads)
    policy_sha = v2._environment_policy_sha256("gh")
    authority = active_authority(environment_policy_sha256=policy_sha)
    with pytest.raises(v2.HfPublicationTransportError, match="exact live canonical main"):
        v2.verify_live_github_boundaries(
            authority,
            github_token="gh",
            expected_repository="TheHalfMoon/MESC",
            expected_workflow_sha="9" * 40,
            expected_workflow_ref=v2.EXPECTED_WORKFLOW_REF,
        )


def test_live_boundary_rejects_edited_authority_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = github_payloads()
    comment = payloads["comment"]
    assert type(comment) is dict
    comment["body"] = BODY + " edited"
    install_github_stub(monkeypatch, payloads)
    authority = active_authority()
    with pytest.raises(v2.HfPublicationTransportError, match="body drifted"):
        v2.verify_live_github_boundaries(
            authority,
            github_token="gh",
            expected_repository="TheHalfMoon/MESC",
            expected_workflow_sha=SHA,
            expected_workflow_ref=v2.EXPECTED_WORKFLOW_REF,
        )


def test_environment_requires_protection_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    install_github_stub(monkeypatch, github_payloads(protected=False))
    with pytest.raises(v2.HfPublicationTransportError, match="no protection rules"):
        v2._environment_policy_sha256("gh")


def test_environment_rejects_incomplete_custom_policy_page(monkeypatch: pytest.MonkeyPatch) -> None:
    install_github_stub(monkeypatch, github_payloads(total_count=2))
    with pytest.raises(v2.HfPublicationTransportError, match="inventory is incomplete"):
        v2._environment_policy_sha256("gh")


def test_transport_manifest_rejects_symlink(tmp_path: Path) -> None:
    for relative in v2.TRANSPORT_MANIFEST_PATHS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative)
    victim = tmp_path / "real"
    victim.write_text("x")
    path = tmp_path / v2.TRANSPORT_MANIFEST_PATHS[0]
    path.unlink()
    path.symlink_to(victim)
    with pytest.raises(v2.HfPublicationTransportError, match="symlink"):
        v2.transport_manifest(tmp_path)


def test_hf_parent_binds_exact_inventory() -> None:
    authority = active_authority()
    files = ["README.md", "app.py"]
    expected_sha = hashlib.sha256(canonical_json_bytes(sorted(files))).hexdigest()
    authority = replace(authority, destination_parent_inventory_sha256=expected_sha)

    class Api:
        def repo_info(self, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(sha="1" * 40)

        def list_repo_files(self, **kwargs: object) -> list[str]:
            return list(reversed(files))

    assert v2._verify_hf_parent(Api(), authority) == sorted(files)


def test_temporary_environment_restores_process_state() -> None:
    os.environ.pop("HF_OIDC_RESOURCE", None)
    with v2._temporary_environment({"HF_OIDC_RESOURCE": "spaces/x/y"}):
        assert os.environ["HF_OIDC_RESOURCE"] == "spaces/x/y"
    assert "HF_OIDC_RESOURCE" not in os.environ


def test_receipt_binds_authority_issue_and_verified_readback(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    v2._write_receipt(
        path,
        active_authority(),
        destination_commit="4" * 40,
        github_run_id="12345",
        github_run_attempt="1",
        github_actor="TheHalfMoon",
    )
    receipt = json.loads(path.read_text())
    assert receipt["authority_issue_number"] == 451
    assert receipt["authority_comment_id"] == 123
    assert receipt["destination_commit"] == "4" * 40
    assert receipt["readback_verified"] is True
    assert canonical_json_bytes(receipt) == path.read_bytes()


REPO_ROOT = Path(__file__).resolve().parents[1]


def _job_block(text: str, job: str) -> str:
    marker = f"  {job}:\n"
    start = text.index(marker)
    tail = text[start + len(marker) :]
    import re

    next_job = re.search(r"^  [a-z0-9-]+:\s*$", tail, flags=re.MULTILINE)
    end = len(text) if next_job is None else start + len(marker) + next_job.start()
    return text[start:end]


def test_workflow_preflight_has_no_environment_or_oidc_write() -> None:
    workflow = (REPO_ROOT / ".github/workflows/hf-publish.yml").read_text()
    preflight = _job_block(workflow, "preflight")
    publish = _job_block(workflow, "publish")
    admit = _job_block(workflow, "admit-receipt")
    assert "environment:" not in preflight
    assert "id-token:" not in preflight
    assert "contents: read" in preflight
    assert "issues: read" in preflight
    assert "actions: read" in preflight
    assert "needs: preflight" in publish
    assert "environment: huggingface-publication" in publish
    assert "id-token: write" in publish
    assert "needs: publish" in admit
    assert "environment:" not in admit
    assert "id-token:" not in admit
    assert "actions: read" in admit
    assert "issues: write" in admit
    assert "contents: write" not in admit
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in admit
    assert "gh issue comment" in admit


def test_workflow_is_dispatch_only_disabled_by_operator_guard() -> None:
    workflow = (REPO_ROOT / ".github/workflows/hf-publish.yml").read_text()
    assert "workflow_dispatch:" in workflow
    prefix = workflow.split("permissions:", maxsplit=1)[0]
    assert "push:" not in prefix
    assert "pull_request:" not in prefix
    assert workflow.count("vars.HF_PUBLISH_ENABLED == 'true'") == 2
    assert workflow.count("github.ref == 'refs/heads/main'") == 2
    assert workflow.count("issues: write") == 1
    assert "secrets." not in workflow
    assert "contents: write" not in workflow


def test_committed_authority_remains_disabled() -> None:
    raw = (REPO_ROOT / "specs/mesc-hf-publication-v2/authority.json").read_bytes()
    authority = v2.parse_authority(raw)
    assert authority.state == "DISABLED"


def test_script_lock_pins_exact_huggingface_hub() -> None:
    lock = (REPO_ROOT / "scripts/mesc_hf_publish.py.lock").read_text()
    assert 'requires-python = ">=3.11, <3.12"' in lock
    assert 'name = "huggingface-hub"' in lock
    assert 'version = "1.23.0"' in lock
    assert 'specifier = "==1.23.0"' in lock


def test_transport_surface_has_no_repo_creation_or_long_lived_secret_usage() -> None:
    paths = [
        REPO_ROOT / ".github/workflows/hf-publish.yml",
        REPO_ROOT / "scripts/mesc_hf_publish.py",
        REPO_ROOT / "src/medscale/mesc/_hf_publication_v2.py",
    ]
    combined = "\n".join(path.read_text() for path in paths)
    for forbidden in (
        "create_repo(",
        "delete_repo(",
        ".push_to_hub(",
        ".upload_file(",
        ".upload_folder(",
        "secrets.",
    ):
        assert forbidden not in combined


def test_environment_rejects_admin_bypass(monkeypatch: pytest.MonkeyPatch) -> None:
    payloads = github_payloads()
    environment = payloads["environment"]
    assert type(environment) is dict
    environment["can_admins_bypass"] = True
    install_github_stub(monkeypatch, payloads)
    with pytest.raises(v2.HfPublicationTransportError, match="administrator bypass"):
        v2._environment_policy_sha256("gh")


def test_environment_rejects_non_substantive_protection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = github_payloads()
    environment = payloads["environment"]
    assert type(environment) is dict
    environment["protection_rules"] = [{"id": 7, "type": "wait_timer", "wait_timer": 0}]
    install_github_stub(monkeypatch, payloads)
    with pytest.raises(v2.HfPublicationTransportError, match="not substantive"):
        v2._environment_policy_sha256("gh")


def test_environment_rejects_broad_custom_branch_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = github_payloads()
    policies = payloads["policies"]
    assert type(policies) is dict
    policies["branch_policies"] = [{"id": 9, "name": "*", "type": "branch"}]
    install_github_stub(monkeypatch, payloads)
    with pytest.raises(v2.HfPublicationTransportError, match="exactly branch main"):
        v2._environment_policy_sha256("gh")


def test_live_boundary_rejects_wrong_workflow_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payloads = github_payloads()
    install_github_stub(monkeypatch, payloads)
    policy_sha = v2._environment_policy_sha256("gh")
    authority = active_authority(environment_policy_sha256=policy_sha)
    with pytest.raises(v2.HfPublicationTransportError, match="workflow identity"):
        v2.verify_live_github_boundaries(
            authority,
            github_token="gh",
            expected_repository="TheHalfMoon/MESC",
            expected_workflow_sha=SHA,
            expected_workflow_ref=("TheHalfMoon/MESC/.github/workflows/other.yml@refs/heads/main"),
        )


def test_hf_inventory_rejects_malformed_remote_response() -> None:
    class Api:
        def list_repo_files(self, **kwargs: object) -> list[object]:
            return ["README.md", 7]

    with pytest.raises(v2.HfPublicationTransportError, match="inventory is malformed"):
        v2._hf_file_inventory(
            Api(),
            repo_id="MedScaleAI/medscale",
            repo_type="space",
            revision="1" * 40,
        )


def test_qualification_workflow_covers_v2_without_invoking_publish() -> None:
    workflow = (REPO_ROOT / ".github/workflows/hf-publication.yml").read_text()
    assert '".github/workflows/hf-publish.yml"' in workflow
    assert '"src/medscale/mesc/_hf_publication_v2.py"' in workflow
    assert '"tests/test_mesc_hf_publication_v2.py"' in workflow
    assert "validate-authority" in workflow
    assert "transport-manifest" in workflow
    assert " scripts/mesc_hf_publish.py publish" not in workflow
    assert not (REPO_ROOT / ".github/workflows/hf-p2-lock-bootstrap.yml").exists()
