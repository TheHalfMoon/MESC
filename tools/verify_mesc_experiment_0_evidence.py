from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = "mesc-experiment-0-evidence"
MANIFEST_PATH = f"{ROOT}/manifests/bundle-manifest.json"
SNAPSHOT_PREFIX = f"{ROOT}/candidate-snapshots/"
RESULT_PREFIX = f"{ROOT}/lane-results/"

MAX_MEMBER_COUNT = 500
MAX_MEMBER_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

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

REQUIRED_AUTHORITY_KEYS = (
    "mrl_0801_evidence_id",
    "mrl_0802_evidence_id",
    "mrl_0803_evidence_id",
    "mrl_0804_evidence_id",
    "mrl_0805_authority_id",
    "mrl_0806_objective_id",
    "mrl_0807_evaluator_freeze_id",
    "mrl_0808_sandbox_id",
    "mrl_0809_preflight_id",
    "mrl_0899_readiness_id",
)

CANDIDATE_CLASSES = {"SELECTABLE_FOUNDATION", "REFERENCE_ONLY"}
CANDIDATE_RESULT_DISPOSITIONS = {
    "PASS_LANE",
    "FAIL_HARD_FLOOR",
    "BLOCKED_RUNTIME",
    "BLOCKED_RIGHTS",
    "BLOCKED_CONTAMINATION",
    "BLOCKED_EVALUATOR",
    "INVALID_RESULT",
    "NOT_SUPPORTED_BY_CANDIDATE",
}
SELECTION_DISPOSITIONS = {"RETAIN_PREFERRED_CANDIDATE", "SELECT_CHALLENGER"}
DECISION_DISPOSITIONS = SELECTION_DISPOSITIONS | {
    "INCONCLUSIVE_OR_BLOCKED",
    "INVALID_EXPERIMENT",
}
SUCCESSFUL_SNAPSHOT_DISPOSITION = "PASS_LOAD"

EVIDENCE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
LANE_KEY_RE = EVIDENCE_KEY_RE
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")

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

FORBIDDEN_SECRET_PATTERNS = (
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"https?://[^/\s:@]+:[^@\s/]+@"),
)

REQUIRED_DECISION_FIELDS = {
    "schema_version",
    "experiment_config_sha256",
    "candidate_result_sha256s",
    "hard_floor_summary",
    "metric_vector_summary",
    "resource_summary",
    "rights_summary",
    "contamination_summary",
    "sealed_evaluation_receipt_identity",
    "selected_candidate_id",
    "selected_candidate_revision",
    "rationale",
    "limitations",
    "decision_disposition",
}


class EvidenceError(ValueError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_json(data: bytes, path: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{path}: not UTF-8 JSON") from exc
    for pattern in FORBIDDEN_SECRET_PATTERNS:
        if pattern.search(text):
            raise EvidenceError(f"{path}: possible secret-bearing value detected")
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
    if "\x00" in name:
        raise EvidenceError("NUL byte in archive path")
    if "\\" in name:
        raise EvidenceError(f"invalid archive path separator: {name}")
    normalized_name = name.rstrip("/")
    parts = normalized_name.split("/")
    if not normalized_name or any(part in {"", ".", ".."} for part in parts):
        raise EvidenceError(f"invalid or ambiguous archive path: {name}")
    path = PurePosixPath(normalized_name)
    if path.is_absolute() or ".." in path.parts:
        raise EvidenceError(f"path traversal or absolute path: {name}")
    if not normalized_name.startswith(f"{ROOT}/"):
        raise EvidenceError(f"member outside evidence root: {name}")
    if not name.endswith("/") and not name.endswith(".json"):
        raise EvidenceError(f"unexpected non-JSON payload: {name}")


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise EvidenceError(f"{label}: expected lowercase SHA-256")
    return value


def require_git_sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX40_RE.fullmatch(value):
        raise EvidenceError(f"{label}: expected lowercase 40-hex Git SHA")
    return value


def _validate_candidate_roster(roster: Any) -> list[dict[str, Any]]:
    if not isinstance(roster, list) or not roster:
        raise EvidenceError("experiment-config.json: candidate_roster must be non-empty")

    candidates: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    evidence_keys: set[str] = set()
    for index, candidate in enumerate(roster):
        label = f"candidate_roster[{index}]"
        if not isinstance(candidate, dict):
            raise EvidenceError(f"{label}: expected object")
        candidate_id = candidate.get("candidate_id")
        revision = candidate.get("candidate_revision")
        candidate_class = candidate.get("candidate_class")
        evidence_key = candidate.get("evidence_key")
        modalities = candidate.get("supported_input_modalities")

        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise EvidenceError(f"{label}: candidate_id missing")
        require_git_sha(revision, f"{label}.candidate_revision")
        if candidate_class not in CANDIDATE_CLASSES:
            raise EvidenceError(f"{label}: invalid candidate_class {candidate_class!r}")
        if not isinstance(evidence_key, str) or not EVIDENCE_KEY_RE.fullmatch(evidence_key):
            raise EvidenceError(f"{label}: invalid evidence_key")
        if not isinstance(modalities, list) or not modalities:
            raise EvidenceError(f"{label}: supported_input_modalities must be non-empty")
        if any(not isinstance(modality, str) or not modality for modality in modalities):
            raise EvidenceError(f"{label}: invalid supported_input_modalities")
        if len(modalities) != len(set(modalities)):
            raise EvidenceError(f"{label}: duplicate supported_input_modalities")
        if "text" not in modalities:
            raise EvidenceError(f"{label}: text modality is required")
        if candidate_class == "SELECTABLE_FOUNDATION" and "vision" not in modalities:
            raise EvidenceError(f"{label}: selectable foundation requires vision modality")

        identity = (candidate_id, revision)
        if identity in identities:
            raise EvidenceError(f"{label}: duplicate candidate identity")
        if evidence_key in evidence_keys:
            raise EvidenceError(f"{label}: duplicate evidence_key")
        identities.add(identity)
        evidence_keys.add(evidence_key)
        candidates.append(candidate)
    return candidates


def validate_config(config: Any) -> list[dict[str, Any]]:
    if not isinstance(config, dict):
        raise EvidenceError("experiment-config.json: expected object")
    if config.get("schema_version") != "MESC-EXPERIMENT-0-CONFIG-V1":
        raise EvidenceError("experiment-config.json: schema mismatch")
    if config.get("status") != "FROZEN_EXECUTION_CONFIG":
        raise EvidenceError("experiment-config.json: config is not frozen")
    require_git_sha(config.get("repository_sha"), "experiment-config.repository_sha")
    require_git_sha(config.get("repository_tree"), "experiment-config.repository_tree")

    candidates = _validate_candidate_roster(config.get("candidate_roster"))

    bindings = config.get("authority_bindings")
    if not isinstance(bindings, dict):
        raise EvidenceError("experiment-config.json: authority_bindings missing")
    missing = [key for key in REQUIRED_AUTHORITY_KEYS if not bindings.get(key)]
    if missing:
        raise EvidenceError(
            "experiment-config.json: incomplete MRL authority/evidence bindings "
            f"{sorted(missing)}"
        )

    sealed_policy = config.get("sealed_evaluation_policy")
    if not isinstance(sealed_policy, dict):
        raise EvidenceError("experiment-config.json: sealed_evaluation_policy missing")
    if sealed_policy.get("tier3_item_access_by_research_process") is not False:
        raise EvidenceError(
            "experiment-config.json: Tier 3 research-process access must be false"
        )
    return candidates


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


def validate_snapshot_receipts(
    json_docs: dict[str, Any],
    members: dict[str, bytes],
    candidates: list[dict[str, Any]],
    config_sha256: str,
) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    expected_paths = {
        f"{SNAPSHOT_PREFIX}{candidate['evidence_key']}.json": candidate
        for candidate in candidates
    }
    observed_paths = {path for path in members if path.startswith(SNAPSHOT_PREFIX)}
    if observed_paths != set(expected_paths):
        missing = sorted(set(expected_paths) - observed_paths)
        extra = sorted(observed_paths - set(expected_paths))
        raise EvidenceError(f"candidate snapshot coverage mismatch missing={missing} extra={extra}")

    for path, candidate in expected_paths.items():
        receipt = json_docs[path]
        if not isinstance(receipt, dict):
            raise EvidenceError(f"{path}: expected object")
        if receipt.get("schema_version") != "MESC-EXPERIMENT-0-CANDIDATE-SNAPSHOT-V1":
            raise EvidenceError(f"{path}: snapshot schema mismatch")
        if receipt.get("experiment_config_sha256") != config_sha256:
            raise EvidenceError(f"{path}: config hash mismatch")
        for field in ("candidate_id", "candidate_revision", "candidate_class", "evidence_key"):
            if receipt.get(field) != candidate[field]:
                raise EvidenceError(f"{path}: roster identity mismatch for {field}")
        resolved_revision = receipt.get("resolved_revision")
        if resolved_revision is not None and resolved_revision != candidate["candidate_revision"]:
            raise EvidenceError(f"{path}: resolved revision differs from frozen revision")
        trust_remote_code = receipt.get("trust_remote_code")
        if not isinstance(trust_remote_code, bool):
            raise EvidenceError(f"{path}: trust_remote_code must be boolean")
        if trust_remote_code and not receipt.get("remote_code_exception_identity"):
            raise EvidenceError(f"{path}: remote-code exception identity missing")
        receipts[candidate["evidence_key"]] = {
            "record": receipt,
            "sha256": sha256_bytes(members[path]),
            "path": path,
        }
    return receipts


def _parse_result_path(path: str) -> tuple[str, str]:
    relative = path.removeprefix(RESULT_PREFIX)
    parts = relative.split("/")
    if len(parts) != 2 or not parts[1].endswith(".json"):
        raise EvidenceError(f"invalid candidate-result path: {path}")
    evidence_key = parts[0]
    lane = parts[1][:-5]
    if not EVIDENCE_KEY_RE.fullmatch(evidence_key) or not LANE_KEY_RE.fullmatch(lane):
        raise EvidenceError(f"invalid candidate-result path identity: {path}")
    return evidence_key, lane


def validate_candidate_results(
    json_docs: dict[str, Any],
    members: dict[str, bytes],
    candidates: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    config_sha256: str,
    runtime_sha256: str,
) -> list[dict[str, Any]]:
    by_key = {candidate["evidence_key"]: candidate for candidate in candidates}
    results: list[dict[str, Any]] = []
    for path in sorted(member for member in members if member.startswith(RESULT_PREFIX)):
        evidence_key, lane = _parse_result_path(path)
        if evidence_key not in by_key:
            raise EvidenceError(f"{path}: result candidate not in frozen roster")
        result = json_docs[path]
        if not isinstance(result, dict):
            raise EvidenceError(f"{path}: expected object")
        if result.get("schema_version") != "MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1":
            raise EvidenceError(f"{path}: candidate-result schema mismatch")
        if result.get("experiment_config_sha256") != config_sha256:
            raise EvidenceError(f"{path}: config hash mismatch")
        if result.get("runtime_receipt_sha256") != runtime_sha256:
            raise EvidenceError(f"{path}: runtime receipt hash mismatch")
        candidate = by_key[evidence_key]
        for field in ("candidate_id", "candidate_revision", "evidence_key"):
            if result.get(field) != candidate[field]:
                raise EvidenceError(f"{path}: roster identity mismatch for {field}")
        if result.get("lane") != lane:
            raise EvidenceError(f"{path}: lane field does not match path")
        if result.get("candidate_snapshot_receipt_sha256") != snapshots[evidence_key]["sha256"]:
            raise EvidenceError(f"{path}: candidate snapshot hash mismatch")
        if result.get("candidate_disposition") not in CANDIDATE_RESULT_DISPOSITIONS:
            raise EvidenceError(f"{path}: invalid candidate disposition")
        results.append(
            {
                "record": result,
                "sha256": sha256_bytes(members[path]),
                "path": path,
                "candidate": candidate,
            }
        )
    return results


def validate_decision(
    decision: Any,
    candidates: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
    config_sha256: str,
) -> None:
    if not isinstance(decision, dict):
        raise EvidenceError("foundation-decision.json: expected object")
    missing_fields = sorted(REQUIRED_DECISION_FIELDS - set(decision))
    if missing_fields:
        raise EvidenceError(f"foundation-decision.json: missing fields {missing_fields}")
    if decision.get("schema_version") != "MESC-EXPERIMENT-0-DECISION-V1":
        raise EvidenceError("foundation-decision.json: schema mismatch")
    if decision.get("experiment_config_sha256") != config_sha256:
        raise EvidenceError("foundation-decision.json: config hash mismatch")

    disposition = decision.get("decision_disposition")
    if disposition not in DECISION_DISPOSITIONS:
        raise EvidenceError(f"foundation-decision.json: invalid disposition {disposition!r}")

    declared_result_hashes = decision.get("candidate_result_sha256s")
    if not isinstance(declared_result_hashes, list):
        raise EvidenceError("foundation-decision.json: candidate_result_sha256s must be a list")
    for index, value in enumerate(declared_result_hashes):
        require_sha256(value, f"foundation-decision.candidate_result_sha256s[{index}]")
    if declared_result_hashes != sorted(set(declared_result_hashes)):
        raise EvidenceError(
            "foundation-decision.json: candidate_result_sha256s must be sorted and unique"
        )
    actual_result_hashes = sorted(result["sha256"] for result in results)
    if declared_result_hashes != actual_result_hashes:
        raise EvidenceError("foundation-decision.json: candidate result hash set mismatch")

    hard_floor_summary = decision.get("hard_floor_summary")
    if not isinstance(hard_floor_summary, dict):
        raise EvidenceError("foundation-decision.json: hard_floor_summary must be an object")
    all_mandatory_passed = hard_floor_summary.get("all_mandatory_passed")
    failed_floor_ids = hard_floor_summary.get("failed_floor_ids")
    if not isinstance(all_mandatory_passed, bool) or not isinstance(failed_floor_ids, list):
        raise EvidenceError("foundation-decision.json: malformed hard_floor_summary")
    if any(not isinstance(floor_id, str) or not floor_id for floor_id in failed_floor_ids):
        raise EvidenceError("foundation-decision.json: invalid failed_floor_ids")

    for summary_field in (
        "metric_vector_summary",
        "resource_summary",
        "rights_summary",
        "contamination_summary",
    ):
        if not isinstance(decision.get(summary_field), dict):
            raise EvidenceError(f"foundation-decision.json: {summary_field} must be an object")
    if not isinstance(decision.get("rationale"), str) or not decision["rationale"].strip():
        raise EvidenceError("foundation-decision.json: rationale must be non-empty")
    if not isinstance(decision.get("limitations"), list):
        raise EvidenceError("foundation-decision.json: limitations must be a list")

    selected_id = decision.get("selected_candidate_id")
    selected_revision = decision.get("selected_candidate_revision")
    if disposition in SELECTION_DISPOSITIONS:
        if not selected_id or not selected_revision:
            raise EvidenceError("foundation-decision.json: selected candidate identity missing")
        require_git_sha(selected_revision, "foundation-decision.selected_candidate_revision")
        matching = [
            candidate
            for candidate in candidates
            if candidate["candidate_id"] == selected_id
            and candidate["candidate_revision"] == selected_revision
        ]
        if len(matching) != 1:
            raise EvidenceError("foundation-decision.json: selected candidate is not in roster")
        selected = matching[0]
        if selected["candidate_class"] != "SELECTABLE_FOUNDATION":
            raise EvidenceError("foundation-decision.json: reference-only candidate cannot be selected")
        snapshot = snapshots[selected["evidence_key"]]["record"]
        if snapshot.get("load_disposition") != SUCCESSFUL_SNAPSHOT_DISPOSITION:
            raise EvidenceError("foundation-decision.json: selected candidate load did not pass")
        selected_results = [
            result
            for result in results
            if result["candidate"]["candidate_id"] == selected_id
            and result["candidate"]["candidate_revision"] == selected_revision
        ]
        if not selected_results:
            raise EvidenceError("foundation-decision.json: selected candidate has no result evidence")
        if decision.get("sealed_evaluation_receipt_identity") in {None, ""}:
            raise EvidenceError("foundation-decision.json: sealed evaluation receipt missing")
        if all_mandatory_passed is not True or failed_floor_ids:
            raise EvidenceError("foundation-decision.json: selection attempted with failed hard floors")
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


def read_archive(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBER_COUNT:
            raise EvidenceError("evidence archive exceeds member-count safety limit")

        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise EvidenceError("duplicate ZIP member paths")
        casefolded = [name.rstrip("/").casefold() for name in names]
        if len(casefolded) != len(set(casefolded)):
            raise EvidenceError("case-colliding ZIP member paths")

        total_size = 0
        for info in infos:
            validate_member_path(info.filename)
            if info.flag_bits & 0x1:
                raise EvidenceError(f"encrypted ZIP member is forbidden: {info.filename}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise EvidenceError(f"symbolic-link ZIP member is forbidden: {info.filename}")
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                raise EvidenceError(f"ZIP member exceeds size limit: {info.filename}")
            total_size += info.file_size
            if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise EvidenceError("evidence archive exceeds total uncompressed-size limit")

        return {info.filename: archive.read(info) for info in infos if not info.is_dir()}


def verify(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    members = read_archive(path_obj)

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

    candidates = validate_config(config)
    config_bytes = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    config_sha256 = sha256_bytes(config_bytes)

    validate_runtime(runtime, config)
    if runtime.get("experiment_config_sha256") != config_sha256:
        raise EvidenceError("runtime receipt does not bind canonical experiment config hash")
    runtime_sha256 = sha256_bytes(members[f"{ROOT}/runtime-receipt.json"])

    snapshots = validate_snapshot_receipts(
        json_docs,
        members,
        candidates,
        config_sha256,
    )
    results = validate_candidate_results(
        json_docs,
        members,
        candidates,
        snapshots,
        config_sha256,
        runtime_sha256,
    )
    validate_decision(decision, candidates, snapshots, results, config_sha256)
    validate_manifest(manifest, members)

    archive_sha256 = sha256_bytes(path_obj.read_bytes())
    return {
        "status": "VERIFIED_STRUCTURE_AND_IDENTITY",
        "archive_sha256": archive_sha256,
        "member_count": len(members),
        "candidate_count": len(candidates),
        "candidate_result_count": len(results),
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
