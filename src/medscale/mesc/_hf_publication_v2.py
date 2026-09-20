"""Fail-closed Hugging Face Trusted Publisher transport."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._hf_publication_v1 import HfPublicationPlan, parse_publication_plan

SCHEMA_AUTHORITY = "MESC-HF-PUBLICATION-AUTHORITY-V1"
SCHEMA_RECEIPT = "MESC-HF-PUBLICATION-RECEIPT-V1"
CANONICAL_REPOSITORY = "TheHalfMoon/MESC"
CANONICAL_OWNER = "TheHalfMoon"
CANONICAL_HF_OWNER = "MedScaleAI"
CANONICAL_ENVIRONMENT = "huggingface-publication"
CANONICAL_WORKFLOW = ".github/workflows/hf-publish.yml"
PUBLICATION_MODE = "trusted-publisher-oidc-v1"
EXPECTED_WORKFLOW_REF = (
    f"{CANONICAL_REPOSITORY}/{CANONICAL_WORKFLOW}@refs/heads/main"
)

TRANSPORT_MANIFEST_PATHS = (
    ".github/workflows/hf-publish.yml",
    "scripts/mesc_hf_publish.py",
    "scripts/mesc_hf_publish.py.lock",
    "src/medscale/mesc/_canonical_json_v1.py",
    "src/medscale/mesc/_hf_publication_v1.py",
    "src/medscale/mesc/_hf_publication_v2.py",
    "pyproject.toml",
    "uv.lock",
)

AuthorityState = Literal["DISABLED", "ACTIVE"]
_SHA40 = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA64 = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_ASSET_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$", re.ASCII)
_DISABLED_KEYS = frozenset({"schema_version", "state"})
_ACTIVE_KEYS = frozenset(
    {
        "artifact_manifest_sha256",
        "authority_actor",
        "authority_body_sha256",
        "authority_comment_id",
        "authority_issue_number",
        "authority_repository",
        "destination_parent_commit",
        "destination_parent_inventory_sha256",
        "environment_name",
        "environment_policy_sha256",
        "plan",
        "plan_sha256",
        "publication_mode",
        "release_assets",
        "release_assets_sha256",
        "schema_version",
        "state",
        "transport_manifest_sha256",
    }
)
_ASSET_KEYS = frozenset({"asset_name", "byte_count", "path", "sha256"})


class HfPublicationTransportError(RuntimeError):
    """Raised when the publication transport cannot prove its exact contract."""


@dataclass(frozen=True, slots=True)
class ReleaseAssetBinding:
    path: str
    asset_name: str
    byte_count: int
    sha256: str

    def __post_init__(self) -> None:
        _validate_relative_path(self.path, field="release asset path")
        if _ASSET_NAME.fullmatch(self.asset_name) is None or any(
            char in self.asset_name for char in "*?[]"
        ):
            raise HfPublicationTransportError("release asset_name is unsafe")
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise HfPublicationTransportError("release asset byte_count must be positive")
        _require_sha256(self.sha256, field="release asset sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_name": self.asset_name,
            "byte_count": self.byte_count,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class PublicationAuthority:
    state: AuthorityState
    plan: HfPublicationPlan | None = None
    plan_sha256: str | None = None
    artifact_manifest_sha256: str | None = None
    release_assets: tuple[ReleaseAssetBinding, ...] = ()
    release_assets_sha256: str | None = None
    authority_repository: str | None = None
    authority_issue_number: int | None = None
    authority_comment_id: int | None = None
    authority_actor: str | None = None
    authority_body_sha256: str | None = None
    environment_name: str | None = None
    environment_policy_sha256: str | None = None
    destination_parent_commit: str | None = None
    destination_parent_inventory_sha256: str | None = None
    publication_mode: str | None = None
    transport_manifest_sha256: str | None = None
    schema_version: str = SCHEMA_AUTHORITY

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_AUTHORITY:
            raise HfPublicationTransportError("authority schema drifted")
        if self.state == "DISABLED":
            optional = (
                self.plan,
                self.plan_sha256,
                self.artifact_manifest_sha256,
                self.release_assets_sha256,
                self.authority_repository,
                self.authority_issue_number,
                self.authority_comment_id,
                self.authority_actor,
                self.authority_body_sha256,
                self.environment_name,
                self.environment_policy_sha256,
                self.destination_parent_commit,
                self.destination_parent_inventory_sha256,
                self.publication_mode,
                self.transport_manifest_sha256,
            )
            if any(value is not None for value in optional) or self.release_assets:
                raise HfPublicationTransportError(
                    "DISABLED authority must not carry activation data"
                )
            return
        if self.state != "ACTIVE":
            raise HfPublicationTransportError("authority state is invalid")
        self._validate_active()

    def _validate_active(self) -> None:
        plan = self.plan
        if plan is None:
            raise HfPublicationTransportError(
                "ACTIVE authority requires a publication plan"
            )
        if plan.source_repository != CANONICAL_REPOSITORY:
            raise HfPublicationTransportError(
                "publication plan source repository drifted"
            )
        if plan.destination_owner != CANONICAL_HF_OWNER:
            raise HfPublicationTransportError(
                "publication plan destination owner drifted"
            )
        if plan.external_upload_enabled:
            raise HfPublicationTransportError(
                "P1 publication plan must remain nonpublishing"
            )
        expected_plan_sha = hashlib.sha256(
            canonical_json_bytes(plan.to_dict())
        ).hexdigest()
        if self.plan_sha256 != expected_plan_sha:
            raise HfPublicationTransportError(
                "authority plan_sha256 does not bind the plan"
            )
        if self.artifact_manifest_sha256 != plan.artifact_manifest_sha256:
            raise HfPublicationTransportError(
                "authority artifact manifest does not bind the plan"
            )
        self._validate_assets()
        if self.authority_repository != CANONICAL_REPOSITORY:
            raise HfPublicationTransportError("authority repository drifted")
        if type(self.authority_issue_number) is not int or self.authority_issue_number <= 0:
            raise HfPublicationTransportError("authority issue number is invalid")
        if type(self.authority_comment_id) is not int or self.authority_comment_id <= 0:
            raise HfPublicationTransportError("authority comment id is invalid")
        if self.authority_actor != CANONICAL_OWNER:
            raise HfPublicationTransportError("authority actor drifted")
        _require_sha256(self.authority_body_sha256, field="authority body sha256")
        if self.environment_name != CANONICAL_ENVIRONMENT:
            raise HfPublicationTransportError("authority environment drifted")
        _require_sha256(self.environment_policy_sha256, field="environment policy sha256")
        if self.destination_parent_commit is None or _SHA40.fullmatch(
            self.destination_parent_commit
        ) is None:
            raise HfPublicationTransportError("destination parent commit must be SHA-1")
        _require_sha256(
            self.destination_parent_inventory_sha256,
            field="destination parent inventory sha256",
        )
        if self.publication_mode != PUBLICATION_MODE:
            raise HfPublicationTransportError("publication mode drifted")
        _require_sha256(self.transport_manifest_sha256, field="transport manifest sha256")

    def _validate_assets(self) -> None:
        plan = self.plan
        if plan is None:
            raise HfPublicationTransportError("authority plan is absent")
        if not self.release_assets:
            raise HfPublicationTransportError("ACTIVE authority requires release assets")
        paths = tuple(item.path for item in self.release_assets)
        names = tuple(item.asset_name for item in self.release_assets)
        if len(paths) != len(set(paths)) or len(names) != len(set(names)):
            raise HfPublicationTransportError("release asset bindings must be unique")
        artifacts = {item.path: item for item in plan.artifacts}
        bindings = {item.path: item for item in self.release_assets}
        if set(bindings) != set(artifacts):
            raise HfPublicationTransportError("release asset paths do not match plan artifacts")
        for path, binding in bindings.items():
            artifact = artifacts[path]
            if (
                binding.byte_count != artifact.byte_count
                or binding.sha256 != artifact.sha256
            ):
                raise HfPublicationTransportError(
                    "release asset identity does not match plan artifact"
                )
        ordered_assets = sorted(self.release_assets, key=lambda item: item.path)
        expected = hashlib.sha256(
            canonical_json_bytes([item.to_dict() for item in ordered_assets])
        ).hexdigest()
        if self.release_assets_sha256 != expected:
            raise HfPublicationTransportError("release_assets_sha256 does not bind mappings")

    @property
    def repo_id(self) -> str:
        if self.plan is None:
            raise HfPublicationTransportError("authority is not active")
        return f"{self.plan.destination_owner}/{self.plan.destination_repo}"

    @property
    def repo_type(self) -> str:
        if self.plan is None:
            raise HfPublicationTransportError("authority is not active")
        return self.plan.destination_repo_type

    @property
    def oidc_resource(self) -> str:
        prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[self.repo_type]
        return f"{prefix}{self.repo_id}"


def parse_authority(raw: bytes) -> PublicationAuthority:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HfPublicationTransportError("authority is invalid JSON") from exc
    if type(payload) is not dict:
        raise HfPublicationTransportError("authority must be an object")
    if canonical_json_bytes(payload) != raw:
        raise HfPublicationTransportError("authority must be canonical JSON")
    state = payload.get("state")
    if state == "DISABLED":
        if set(payload) != _DISABLED_KEYS:
            raise HfPublicationTransportError("DISABLED authority keys drifted")
        return PublicationAuthority(state="DISABLED", schema_version=payload["schema_version"])
    if state != "ACTIVE" or set(payload) != _ACTIVE_KEYS:
        raise HfPublicationTransportError("ACTIVE authority keys drifted")
    rows = payload["release_assets"]
    if type(rows) is not list or not rows:
        raise HfPublicationTransportError("release_assets must be a non-empty list")
    assets: list[ReleaseAssetBinding] = []
    for row in rows:
        if type(row) is not dict or set(row) != _ASSET_KEYS:
            raise HfPublicationTransportError("release asset keys drifted")
        assets.append(
            ReleaseAssetBinding(
                path=row["path"],
                asset_name=row["asset_name"],
                byte_count=row["byte_count"],
                sha256=row["sha256"],
            )
        )
    plan_payload = payload["plan"]
    if type(plan_payload) is not dict:
        raise HfPublicationTransportError("authority plan must be an object")
    plan = parse_publication_plan(canonical_json_bytes(plan_payload))
    return PublicationAuthority(
        state="ACTIVE",
        plan=plan,
        plan_sha256=payload["plan_sha256"],
        artifact_manifest_sha256=payload["artifact_manifest_sha256"],
        release_assets=tuple(assets),
        release_assets_sha256=payload["release_assets_sha256"],
        authority_repository=payload["authority_repository"],
        authority_issue_number=payload["authority_issue_number"],
        authority_comment_id=payload["authority_comment_id"],
        authority_actor=payload["authority_actor"],
        authority_body_sha256=payload["authority_body_sha256"],
        environment_name=payload["environment_name"],
        environment_policy_sha256=payload["environment_policy_sha256"],
        destination_parent_commit=payload["destination_parent_commit"],
        destination_parent_inventory_sha256=payload["destination_parent_inventory_sha256"],
        publication_mode=payload["publication_mode"],
        transport_manifest_sha256=payload["transport_manifest_sha256"],
        schema_version=payload["schema_version"],
    )


def transport_manifest(root: Path) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    if root.is_symlink():
        raise HfPublicationTransportError("repository root must not be a symlink")
    resolved_root = root.resolve(strict=True)
    for relative in TRANSPORT_MANIFEST_PATHS:
        path = root
        for part in PurePosixPath(relative).parts:
            path = path / part
            if path.is_symlink():
                raise HfPublicationTransportError(
                    f"transport path contains a symlink: {relative}"
                )
        resolved = path.resolve(strict=True)
        if resolved_root not in resolved.parents:
            raise HfPublicationTransportError(f"transport path escaped repository: {relative}")
        if not resolved.is_file():
            raise HfPublicationTransportError(f"transport path is not a file: {relative}")
        payload = resolved.read_bytes()
        rows.append(
            {
                "byte_count": len(payload),
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return tuple(rows)


def transport_manifest_sha256(root: Path) -> str:
    return hashlib.sha256(canonical_json_bytes(list(transport_manifest(root)))).hexdigest()


def verify_transport_manifest(root: Path, expected_sha256: str) -> None:
    _require_sha256(expected_sha256, field="expected transport manifest sha256")
    if transport_manifest_sha256(root) != expected_sha256:
        raise HfPublicationTransportError("transport manifest drifted")


def verify_source_tag(root: Path, authority: PublicationAuthority) -> None:
    _require_active(authority)
    plan = authority.plan
    if plan is None:
        raise HfPublicationTransportError("authority plan is absent")
    commit_ref = f"refs/tags/{plan.source_tag}^{{commit}}"
    tree_ref = f"refs/tags/{plan.source_tag}^{{tree}}"
    commit = _git(root, "rev-parse", "--verify", commit_ref)
    tree = _git(root, "rev-parse", "--verify", tree_ref)
    if commit != plan.source_sha or tree != plan.source_tree:
        raise HfPublicationTransportError("source tag does not bind the authorized source")


def verify_live_github_boundaries(
    authority: PublicationAuthority,
    *,
    github_token: str,
    expected_repository: str,
    expected_workflow_sha: str,
    expected_workflow_ref: str,
) -> str:
    _require_active(authority)
    if expected_repository != CANONICAL_REPOSITORY:
        raise HfPublicationTransportError("workflow repository is not canonical")
    if _SHA40.fullmatch(expected_workflow_sha) is None:
        raise HfPublicationTransportError("workflow SHA is invalid")
    if expected_workflow_ref != EXPECTED_WORKFLOW_REF:
        raise HfPublicationTransportError("workflow identity is not canonical")
    branch = _github_json(f"/repos/{CANONICAL_REPOSITORY}/branches/main", github_token)
    commit = branch.get("commit") if type(branch) is dict else None
    live_sha = commit.get("sha") if type(commit) is dict else None
    if live_sha != expected_workflow_sha:
        raise HfPublicationTransportError("workflow SHA is not exact live canonical main")
    _verify_authority_comment(authority, github_token)
    policy_sha = _environment_policy_sha256(github_token)
    if policy_sha != authority.environment_policy_sha256:
        raise HfPublicationTransportError("GitHub Environment policy drifted")
    return policy_sha


def _verify_authority_comment(authority: PublicationAuthority, github_token: str) -> None:
    comment_id = authority.authority_comment_id
    issue_number = authority.authority_issue_number
    body_sha256 = authority.authority_body_sha256
    if comment_id is None or issue_number is None or body_sha256 is None:
        raise HfPublicationTransportError("authority comment binding is incomplete")
    comment = _github_json(
        f"/repos/{CANONICAL_REPOSITORY}/issues/comments/{comment_id}",
        github_token,
    )
    if type(comment) is not dict or comment.get("id") != comment_id:
        raise HfPublicationTransportError("authority comment identity drifted")
    user = comment.get("user")
    if type(user) is not dict or user.get("login") != authority.authority_actor:
        raise HfPublicationTransportError("authority comment actor drifted")
    body = comment.get("body")
    if type(body) is not str:
        raise HfPublicationTransportError("authority comment body is absent")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != body_sha256:
        raise HfPublicationTransportError("authority comment body drifted")
    issue_url = comment.get("issue_url")
    expected = (
        f"https://api.github.com/repos/{CANONICAL_REPOSITORY}/issues/"
        f"{issue_number}"
    )
    if issue_url != expected:
        raise HfPublicationTransportError("authority comment issue binding drifted")


def _environment_policy_sha256(github_token: str) -> str:
    name = urllib.parse.quote(CANONICAL_ENVIRONMENT, safe="")
    environment = _github_json(
        f"/repos/{CANONICAL_REPOSITORY}/environments/{name}", github_token
    )
    if type(environment) is not dict or environment.get("name") != CANONICAL_ENVIRONMENT:
        raise HfPublicationTransportError(
            "publication Environment is absent or malformed"
        )
    if environment.get("can_admins_bypass") is not False:
        raise HfPublicationTransportError(
            "publication Environment must prohibit administrator bypass"
        )
    protection_rules = environment.get("protection_rules")
    if type(protection_rules) is not list or not protection_rules:
        raise HfPublicationTransportError(
            "publication Environment has no protection rules"
        )
    normalized_rules, substantive_protection = _normalize_protection_rules(
        protection_rules
    )
    if not substantive_protection:
        raise HfPublicationTransportError(
            "publication Environment protection is not substantive"
        )
    deployment = environment.get("deployment_branch_policy")
    if type(deployment) is not dict:
        raise HfPublicationTransportError(
            "publication Environment has no deployment policy"
        )
    protected = deployment.get("protected_branches")
    custom = deployment.get("custom_branch_policies")
    if type(protected) is not bool or type(custom) is not bool or protected == custom:
        raise HfPublicationTransportError(
            "publication Environment deployment policy is not bounded"
        )
    branch_policies: list[dict[str, object]] = []
    if custom:
        response = _github_json(
            f"/repos/{CANONICAL_REPOSITORY}/environments/{name}/"
            "deployment-branch-policies?per_page=100",
            github_token,
        )
        if type(response) is not dict:
            raise HfPublicationTransportError(
                "deployment branch policy response is malformed"
            )
        total = response.get("total_count")
        rows = response.get("branch_policies")
        if (
            type(total) is not int
            or type(rows) is not list
            or total != len(rows)
            or total > 100
        ):
            raise HfPublicationTransportError(
                "deployment branch policy inventory is incomplete"
            )
        for row in rows:
            if type(row) is not dict:
                raise HfPublicationTransportError(
                    "deployment branch policy is malformed"
                )
            policy_id = row.get("id")
            policy_name = row.get("name")
            policy_type = row.get("type")
            if (
                type(policy_id) is not int
                or type(policy_name) is not str
                or type(policy_type) is not str
            ):
                raise HfPublicationTransportError(
                    "deployment branch policy identity is malformed"
                )
            branch_policies.append(
                {"id": policy_id, "name": policy_name, "type": policy_type}
            )
        if len(branch_policies) != 1 or (
            branch_policies[0]["type"], branch_policies[0]["name"]
        ) != ("branch", "main"):
            raise HfPublicationTransportError(
                "custom deployment policy must bind exactly branch main"
            )
    branch_policies.sort(
        key=lambda item: (
            cast(str, item["type"]),
            cast(str, item["name"]),
            cast(int, item["id"]),
        )
    )
    snapshot = {
        "can_admins_bypass": False,
        "deployment_branch_policies": branch_policies,
        "deployment_branch_policy": {
            "custom_branch_policies": custom,
            "protected_branches": protected,
        },
        "name": CANONICAL_ENVIRONMENT,
        "protection_rules": normalized_rules,
    }
    return hashlib.sha256(canonical_json_bytes(snapshot)).hexdigest()


def _normalize_protection_rules(
    rows: list[object],
) -> tuple[list[dict[str, object]], bool]:
    normalized: list[dict[str, object]] = []
    substantive = False
    for raw in rows:
        if (
            type(raw) is not dict
            or type(raw.get("id")) is not int
            or type(raw.get("type")) is not str
        ):
            raise HfPublicationTransportError(
                "Environment protection rule is malformed"
            )
        rule_type = raw["type"]
        item: dict[str, object] = {"id": raw["id"], "type": rule_type}
        if "wait_timer" in raw:
            wait_timer = raw["wait_timer"]
            if type(wait_timer) is not int:
                raise HfPublicationTransportError(
                    "Environment wait timer is malformed"
                )
            item["wait_timer"] = wait_timer
            if rule_type == "wait_timer" and wait_timer > 0:
                substantive = True
        if "prevent_self_review" in raw:
            prevent_self_review = raw["prevent_self_review"]
            if type(prevent_self_review) is not bool:
                raise HfPublicationTransportError(
                    "Environment self-review policy is malformed"
                )
            item["prevent_self_review"] = prevent_self_review
        if "reviewers" in raw:
            reviewers = raw["reviewers"]
            if type(reviewers) is not list:
                raise HfPublicationTransportError(
                    "Environment reviewers are malformed"
                )
            clean_reviewers: list[dict[str, object]] = []
            for reviewer in reviewers:
                if (
                    type(reviewer) is not dict
                    or type(reviewer.get("type")) is not str
                ):
                    raise HfPublicationTransportError(
                        "Environment reviewer is malformed"
                    )
                identity = reviewer.get("reviewer")
                if type(identity) is not dict or type(identity.get("id")) is not int:
                    raise HfPublicationTransportError(
                        "Environment reviewer identity is malformed"
                    )
                label = identity.get("login", identity.get("slug"))
                if type(label) is not str:
                    raise HfPublicationTransportError(
                        "Environment reviewer label is malformed"
                    )
                clean_reviewers.append(
                    {
                        "id": identity["id"],
                        "label": label,
                        "type": reviewer["type"],
                    }
                )
            clean_reviewers.sort(
                key=lambda row: (
                    cast(str, row["type"]),
                    cast(str, row["label"]),
                    cast(int, row["id"]),
                )
            )
            item["reviewers"] = clean_reviewers
            if rule_type == "required_reviewers" and clean_reviewers:
                substantive = True
        normalized.append(item)
    normalized.sort(key=lambda item: (cast(str, item["type"]), cast(int, item["id"])))
    return normalized, substantive


def materialize_release_assets(
    root: Path,
    authority: PublicationAuthority,
    payload_dir: Path,
    *,
    github_token: str,
) -> None:
    _require_active(authority)
    plan = authority.plan
    if plan is None:
        raise HfPublicationTransportError("authority plan is absent")
    if payload_dir.is_symlink():
        raise HfPublicationTransportError("payload root must not be a symlink")
    if payload_dir.exists():
        raise HfPublicationTransportError("payload root must not exist before materialization")
    payload_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["GH_TOKEN"] = github_token
    for binding in sorted(authority.release_assets, key=lambda item: item.path):
        target = payload_dir / binding.path
        target.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "gh",
            "release",
            "download",
            "--repo",
            CANONICAL_REPOSITORY,
            "--pattern",
            binding.asset_name,
            "--output",
            str(target),
            "--",
            plan.source_tag,
        ]
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise HfPublicationTransportError("GitHub Release asset download failed")
        _verify_file_identity(target, binding.byte_count, binding.sha256)
    observed = sorted(
        path.relative_to(payload_dir).as_posix()
        for path in payload_dir.rglob("*")
        if path.is_file()
    )
    expected = sorted(item.path for item in authority.release_assets)
    if observed != expected:
        raise HfPublicationTransportError("materialized payload inventory drifted")


def publish_with_trusted_publisher(
    root: Path,
    authority: PublicationAuthority,
    *,
    github_token: str,
    expected_repository: str,
    expected_workflow_sha: str,
    expected_workflow_ref: str,
    receipt_out: Path,
    github_run_id: str,
    github_run_attempt: str,
    github_actor: str,
) -> str:
    _require_active(authority)
    transport_sha256 = authority.transport_manifest_sha256
    if transport_sha256 is None:
        raise HfPublicationTransportError("transport manifest binding is absent")
    verify_transport_manifest(root, transport_sha256)
    verify_source_tag(root, authority)
    verify_live_github_boundaries(
        authority,
        github_token=github_token,
        expected_repository=expected_repository,
        expected_workflow_sha=expected_workflow_sha,
        expected_workflow_ref=expected_workflow_ref,
    )
    with tempfile.TemporaryDirectory(prefix="mesc-hf-publish-") as temp_dir:
        temporary = Path(temp_dir)
        payload_dir = temporary / "payload"
        materialize_release_assets(root, authority, payload_dir, github_token=github_token)
        verify_live_github_boundaries(
            authority,
            github_token=github_token,
            expected_repository=expected_repository,
            expected_workflow_sha=expected_workflow_sha,
            expected_workflow_ref=expected_workflow_ref,
        )
        for variable in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
            if os.environ.get(variable):
                raise HfPublicationTransportError(f"inherited {variable} is prohibited")
        hf_home = temporary / "hf-home"
        hf_home.mkdir()
        with _temporary_environment(
            {
                "HF_HOME": str(hf_home),
                "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
                "HF_OIDC_RESOURCE": authority.oidc_resource,
            }
        ):
            from huggingface_hub import (
                CommitOperationAdd,
                HfApi,
                get_token,
                hf_hub_download,
            )
            from huggingface_hub import __version__ as hub_version

            if hub_version != "1.23.0":
                raise HfPublicationTransportError("huggingface-hub version drifted")
            token = get_token()
            if not token:
                raise HfPublicationTransportError(
                    "Trusted Publisher OIDC exchange returned no token"
                )
            verify_live_github_boundaries(
                authority,
                github_token=github_token,
                expected_repository=expected_repository,
                expected_workflow_sha=expected_workflow_sha,
                expected_workflow_ref=expected_workflow_ref,
            )
            api = HfApi(token=token)
            parent_files = _verify_hf_parent(api, authority)
            operations = [
                CommitOperationAdd(
                    path_in_repo=binding.path,
                    path_or_fileobj=str(payload_dir / binding.path),
                )
                for binding in sorted(authority.release_assets, key=lambda item: item.path)
            ]
            commit = api.create_commit(
                repo_id=authority.repo_id,
                repo_type=authority.repo_type,
                operations=operations,
                commit_message="Publish governed MESC artifact",
                revision="main",
                parent_commit=authority.destination_parent_commit,
            )
            destination_commit = getattr(commit, "oid", None)
            if type(destination_commit) is not str or _SHA40.fullmatch(destination_commit) is None:
                raise HfPublicationTransportError("Hugging Face commit identity is invalid")
            info = api.repo_info(
                repo_id=authority.repo_id,
                repo_type=authority.repo_type,
                revision=destination_commit,
            )
            if getattr(info, "sha", None) != destination_commit:
                raise HfPublicationTransportError("Hugging Face commit readback drifted")
            governed_paths = {item.path for item in authority.release_assets}
            expected_files = sorted(set(parent_files) | governed_paths)
            actual_files = _hf_file_inventory(
                api,
                repo_id=authority.repo_id,
                repo_type=authority.repo_type,
                revision=destination_commit,
            )
            if actual_files != expected_files:
                raise HfPublicationTransportError("Hugging Face post-commit inventory drifted")
            for binding in authority.release_assets:
                downloaded = Path(
                    hf_hub_download(
                        repo_id=authority.repo_id,
                        filename=binding.path,
                        repo_type=authority.repo_type,
                        revision=destination_commit,
                        token=token,
                        force_download=True,
                    )
                )
                _verify_file_identity(downloaded, binding.byte_count, binding.sha256)
            verify_live_github_boundaries(
                authority,
                github_token=github_token,
                expected_repository=expected_repository,
                expected_workflow_sha=expected_workflow_sha,
                expected_workflow_ref=expected_workflow_ref,
            )
            _write_receipt(
                receipt_out,
                authority,
                destination_commit=destination_commit,
                github_run_id=github_run_id,
                github_run_attempt=github_run_attempt,
                github_actor=github_actor,
            )
            return destination_commit


def _hf_file_inventory(
    api: Any,
    *,
    repo_id: str,
    repo_type: str,
    revision: str,
) -> list[str]:
    raw = cast(
        object,
        api.list_repo_files(
            repo_id=repo_id,
            repo_type=repo_type,
            revision=revision,
        ),
    )
    if type(raw) is not list or any(type(item) is not str for item in raw):
        raise HfPublicationTransportError("Hugging Face file inventory is malformed")
    return sorted(cast(list[str], raw))


def _verify_hf_parent(api: Any, authority: PublicationAuthority) -> list[str]:
    parent_commit = authority.destination_parent_commit
    inventory_binding = authority.destination_parent_inventory_sha256
    if parent_commit is None or inventory_binding is None:
        raise HfPublicationTransportError("destination parent binding is incomplete")
    info = cast(
        object,
        api.repo_info(
            repo_id=authority.repo_id,
            repo_type=authority.repo_type,
            revision="main",
        ),
    )
    if getattr(info, "sha", None) != parent_commit:
        raise HfPublicationTransportError("Hugging Face destination parent drifted")
    files = _hf_file_inventory(
        api,
        repo_id=authority.repo_id,
        repo_type=authority.repo_type,
        revision=parent_commit,
    )
    inventory_sha = hashlib.sha256(canonical_json_bytes(files)).hexdigest()
    if inventory_sha != inventory_binding:
        raise HfPublicationTransportError("Hugging Face destination inventory drifted")
    return files


def _write_receipt(
    path: Path,
    authority: PublicationAuthority,
    *,
    destination_commit: str,
    github_run_id: str,
    github_run_attempt: str,
    github_actor: str,
) -> None:
    plan = authority.plan
    plan_sha256 = authority.plan_sha256
    artifact_manifest_sha256 = authority.artifact_manifest_sha256
    comment_id = authority.authority_comment_id
    body_sha256 = authority.authority_body_sha256
    environment_policy_sha256 = authority.environment_policy_sha256
    if (
        plan is None
        or plan_sha256 is None
        or artifact_manifest_sha256 is None
        or comment_id is None
        or body_sha256 is None
        or environment_policy_sha256 is None
    ):
        raise HfPublicationTransportError("publication receipt binding is incomplete")
    if path.exists() or path.is_symlink():
        raise HfPublicationTransportError(
            "publication receipt output must not pre-exist"
        )
    if path.parent.is_symlink():
        raise HfPublicationTransportError("publication receipt parent must not be a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "artifact_manifest_sha256": artifact_manifest_sha256,
        "authority_body_sha256": body_sha256,
        "authority_comment_id": comment_id,
        "destination_commit": destination_commit,
        "destination_owner": plan.destination_owner,
        "destination_repo": plan.destination_repo,
        "destination_repo_type": authority.repo_type,
        "environment_policy_sha256": environment_policy_sha256,
        "github_actor": github_actor,
        "github_run_attempt": github_run_attempt,
        "github_run_id": github_run_id,
        "plan_sha256": plan_sha256,
        "publication_mode": PUBLICATION_MODE,
        "readback_verified": True,
        "schema_version": SCHEMA_RECEIPT,
        "source_repository": plan.source_repository,
        "source_sha": plan.source_sha,
        "source_tag": plan.source_tag,
        "source_tree": plan.source_tree,
    }
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(receipt))


def _github_json(path: str, token: str) -> object:
    if not token:
        raise HfPublicationTransportError("GitHub read token is required")
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise HfPublicationTransportError("GitHub live verification request failed") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HfPublicationTransportError("GitHub live verification response is invalid") from exc


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise HfPublicationTransportError("git source binding verification failed")
    return completed.stdout.strip()


def _verify_file_identity(path: Path, byte_count: int, sha256: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise HfPublicationTransportError("governed payload is not a regular file")
    payload = path.read_bytes()
    if len(payload) != byte_count or hashlib.sha256(payload).hexdigest() != sha256:
        raise HfPublicationTransportError("governed payload byte identity drifted")


def _validate_relative_path(value: str, *, field: str) -> None:
    pure = PurePosixPath(value)
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or pure.as_posix() != value
        or any(part in {"", ".", ".."} for part in pure.parts)
    ):
        raise HfPublicationTransportError(f"{field} must be safe and relative")


def _require_sha256(value: object, *, field: str) -> None:
    if type(value) is not str or _SHA64.fullmatch(value) is None:
        raise HfPublicationTransportError(f"{field} must be exactly 64 lowercase hex characters")


def _require_active(authority: PublicationAuthority) -> None:
    if type(authority) is not PublicationAuthority or authority.state != "ACTIVE":
        raise HfPublicationTransportError("publication authority is not ACTIVE")


@contextmanager
def _temporary_environment(updates: dict[str, str]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


__all__ = [
    "CANONICAL_ENVIRONMENT",
    "CANONICAL_REPOSITORY",
    "CANONICAL_WORKFLOW",
    "EXPECTED_WORKFLOW_REF",
    "PUBLICATION_MODE",
    "SCHEMA_AUTHORITY",
    "SCHEMA_RECEIPT",
    "TRANSPORT_MANIFEST_PATHS",
    "HfPublicationTransportError",
    "PublicationAuthority",
    "ReleaseAssetBinding",
    "materialize_release_assets",
    "parse_authority",
    "publish_with_trusted_publisher",
    "transport_manifest",
    "transport_manifest_sha256",
    "verify_live_github_boundaries",
    "verify_source_tag",
    "verify_transport_manifest",
]
