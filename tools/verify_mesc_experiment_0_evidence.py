from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import PurePosixPath
from typing import Any

ROOT = "mesc-experiment-0-evidence"
MANIFEST_PATH = f"{ROOT}/manifests/bundle-manifest.json"

MANDATORY_PATHS = {
    f"{ROOT}/experiment-config.json",
    f"{ROOT}/runtime-receipt.json",
    f"{ROOT}/environment-manifest.json",
    f"{ROOT}/decision/foundation-decision.json",
    MANIFEST_PATH,
}

EXPECTED_SCHEMAS = {
    f"{ROOT}/experiment-config.json": "MESC-EXPERIMENT-0-CONFIG-V1",
    f"{ROOT}/runtime-receipt.json": "MESC-EXPERIMENT-0-RUNTIME-V1",
    f"{ROOT}/decision/foundation-decision.json": "MESC-EXPERIMENT-0-DECISION-V1",
    MANIFEST_PATH: "MESC-EXPERIMENT-0-BUNDLE-V1",
}

FORBIDDEN_FIELD_NAMES = {
    "token",
    "hf_token",
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "authorization_header",
}

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")


class EvidenceError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(data: bytes, path: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{path}: not UTF-8 JSON") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"{path}: invalid JSON: {exc}") from exc


def walk_forbidden_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_FIELD_NAMES:
                raise EvidenceError(f"{path}: forbidden secret-bearing field {key!r}")
            walk_forbidden_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            walk_forbidden_fields(child, f"{path}[{index}]")


def validate_member_path(name: str) -> None:
    if "\\" in name:
        raise EvidenceError(f"invalid archive path separator: {name}")
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise EvidenceError(f"path traversal or absolute path: {name}")
    if not name.startswith(f"{ROOT}/"):
        raise EvidenceError(f"member outside evidence root: {name}")
    if name.endswith("/"):
        return
    if not name.endswith(".json"):
        raise EvidenceError(f"unexpected non-JSON payload: {name}")


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvidenceError(f"{label}: expected lowercase SHA-256")
    return value


def require_git_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value):
        raise EvidenceError(f"{label}: expected lowercase 40-hex Git SHA")
    return value


def validate_config(config: Any) -> None:
    if not isinstance(config, dict):
        raise EvidenceError("experiment-config.json: expected object")
    if config.get("schema_version") != "MESC-EXPERIMENT-0-CONFIG-V1":
        raise EvidenceError("experiment-config.json: schema mismatch")
    if config.get("status") != "FROZEN_EXECUTION_CONFIG":
        raise EvidenceError("experiment-config.json: config is not frozen")
    require_git_sha(config.get("repository_sha"), "experiment-config.repository_sha")
    require_git_sha(config.get("repository_tree"), "experiment-config.repository_tree")
    roster = config.get("candidate_roster")
    if not isinstance(roster, list) or not roster:
        raise EvidenceError("experiment-config.json: candidate_roster must be non-empty")


def validate_runtime(runtime: Any, config: dict[str, Any]) -> None:
    if not isinstance(runtime, dict):
        raise EvidenceError("runtime-receipt.json: expected object")
    if runtime.get("schema_version") != "MESC-EXPERIMENT-0-RUNTIME-V1":
        raise EvidenceError("runtime-receipt.json: schema mismatch")
    if runtime.get("repository_sha") != config.get("repository_sha"):
        raise EvidenceError("runtime/config repository_sha mismatch")
    if runtime.get("repository_tree") != config.get("repository_tree"):
        raise EvidenceError("runtime/config repository_tree mismatch")
    require_sha256(
        runtime.get("experiment_config_sha256"),
        "runtime-receipt.experiment_config_sha256",
    )


def validate_decision(decision: Any) -> None:
    if not isinstance(decision, dict):
        raise EvidenceError("foundation-decision.json: expected object")
    if decision.get("schema_version") != "MESC-EXPERIMENT-0-DECISION-V1":
        raise EvidenceError("foundation-decision.json: schema mismatch")
    disposition = decision.get("decision_disposition")
    allowed = {
        "RETAIN_PREFERRED_CANDIDATE",
        "SELECT_CHALLENGER",
        "INCONCLUSIVE_OR_BLOCKED",
        "INVALID_EXPERIMENT",
    }
    if disposition not in allowed:
        raise EvidenceError(f"foundation-decision.json: invalid disposition {disposition!r}")
    selected_id = decision.get("selected_candidate_id")
    selected_revision = decision.get("selected_candidate_revision")
    selection_dispositions = {"RETAIN_PREFERRED_CANDIDATE", "SELECT_CHALLENGER"}
    if disposition in selection_dispositions:
        if not selected_id or not selected_revision:
            raise EvidenceError("foundation-decision.json: selected candidate identity missing")
    elif selected_id is not None or selected_revision is not None:
        raise EvidenceError(
            "foundation-decision.json: blocked/invalid decision cannot select a candidate"
        )


def validate_manifest(manifest: Any, members: dict[str, bytes]) -> None:
    if not isinstance(manifest, dict):
        raise EvidenceError("bundle-manifest.json: expected object")
    if manifest.get("schema_version") != "MESC-EXPERIMENT-0-BUNDLE-V1":
        raise EvidenceError("bundle-manifest.json: schema mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise EvidenceError("bundle-manifest.json: entries must be a list")

    seen: set[str] = set()
    expected_paths = set(members) - {MANIFEST_PATH}
    declared_paths: set[str] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise EvidenceError(f"bundle-manifest entry {index}: expected object")
        path = entry.get("path")
        if not isinstance(path, str):
            raise EvidenceError(f"bundle-manifest entry {index}: missing path")
        if path == MANIFEST_PATH:
            raise EvidenceError("bundle-manifest.json must not list/hash itself")
        if path in seen:
            raise EvidenceError(f"bundle-manifest duplicate entry: {path}")
        seen.add(path)
        declared_paths.add(path)
        if path not in members:
            raise EvidenceError(f"bundle-manifest references missing member: {path}")
        observed = members[path]
        if entry.get("size_bytes") != len(observed):
            raise EvidenceError(f"bundle-manifest size mismatch: {path}")
        expected_sha = require_sha256(entry.get("sha256"), f"manifest sha256 for {path}")
        if expected_sha != sha256_bytes(observed):
            raise EvidenceError(f"bundle-manifest hash mismatch: {path}")
        if entry.get("media_type") != "application/json":
            raise EvidenceError(f"bundle-manifest media_type mismatch: {path}")

    if declared_paths != expected_paths:
        missing = sorted(expected_paths - declared_paths)
        extra = sorted(declared_paths - expected_paths)
        raise EvidenceError(f"bundle-manifest coverage mismatch missing={missing} extra={extra}")


def verify(path: str) -> dict[str, Any]:
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise EvidenceError("duplicate ZIP member paths")
        for name in names:
            validate_member_path(name)

        members = {
            info.filename: archive.read(info)
            for info in infos
            if not info.is_dir()
        }

    missing = sorted(MANDATORY_PATHS - set(members))
    if missing:
        raise EvidenceError(f"missing mandatory evidence members: {missing}")

    json_docs = {name: load_json(data, name) for name, data in members.items()}
    for name, value in json_docs.items():
        walk_forbidden_fields(value, name)

    for path_name, expected_schema in EXPECTED_SCHEMAS.items():
        value = json_docs[path_name]
        if not isinstance(value, dict) or value.get("schema_version") != expected_schema:
            raise EvidenceError(f"{path_name}: expected schema {expected_schema}")

    config = json_docs[f"{ROOT}/experiment-config.json"]
    runtime = json_docs[f"{ROOT}/runtime-receipt.json"]
    decision = json_docs[f"{ROOT}/decision/foundation-decision.json"]
    manifest = json_docs[MANIFEST_PATH]

    validate_config(config)
    validate_runtime(runtime, config)
    validate_decision(decision)
    validate_manifest(manifest, members)

    config_bytes = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    config_sha256 = sha256_bytes(config_bytes)
    if runtime.get("experiment_config_sha256") != config_sha256:
        raise EvidenceError("runtime receipt does not bind canonical experiment config hash")
    if decision.get("experiment_config_sha256") != config_sha256:
        raise EvidenceError("decision does not bind canonical experiment config hash")

    with open(path, "rb") as handle:
        archive_sha256 = sha256_bytes(handle.read())

    return {
        "status": "VERIFIED_STRUCTURE_AND_IDENTITY",
        "archive_sha256": archive_sha256,
        "member_count": len(members),
        "experiment_config_sha256": config_sha256,
        "repository_sha": config["repository_sha"],
        "repository_tree": config["repository_tree"],
        "decision_disposition": decision["decision_disposition"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the MESC Experiment-0 metadata evidence bundle."
    )
    parser.add_argument("evidence_zip")
    args = parser.parse_args()
    try:
        result = verify(args.evidence_zip)
    except (EvidenceError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
