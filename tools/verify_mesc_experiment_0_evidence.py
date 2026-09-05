from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = "mesc-experiment-0-evidence"
CONFIG = f"{ROOT}/experiment-config.json"
RUNTIME = f"{ROOT}/runtime-receipt.json"
ENVIRONMENT = f"{ROOT}/environment-manifest.json"
DECISION = f"{ROOT}/decision/foundation-decision.json"
MANIFEST = f"{ROOT}/manifests/bundle-manifest.json"
SNAPSHOTS = f"{ROOT}/candidate-snapshots/"
RESULTS = f"{ROOT}/lane-results/"

MAX_MEMBER_COUNT = 500
MAX_MEMBER_UNCOMPRESSED_BYTES = 10 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 50 * 1024 * 1024

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

CONFIG_FIELDS = {
    "schema_version",
    "experiment_id",
    "status",
    "objective_id",
    "repository_sha",
    "repository_tree",
    "strategy_decision_id",
    "candidate_roster",
    "dataset_identities",
    "evaluator_identities",
    "prompt_template_identities",
    "generation_configs",
    "runtime_policy",
    "network_policy",
    "filesystem_policy",
    "credential_policy",
    "resource_budget",
    "query_budget",
    "result_exposure_budget",
    "hard_floor_policy",
    "decision_rule",
    "sealed_evaluation_policy",
    "authority_bindings",
}
RUNTIME_FIELDS = {
    "schema_version",
    "experiment_config_sha256",
    "repository_sha",
    "repository_tree",
    "execution_started_at_utc",
    "execution_completed_at_utc",
    "runtime_provider",
    "runtime_class",
    "python_version",
    "platform_string",
    "torch_version",
    "transformers_version",
    "cuda_available",
    "cuda_version",
    "gpu_count",
    "gpu_models",
    "gpu_total_memory_bytes",
    "colab_release_tag_or_image_identity_if_observable",
    "installed_environment_manifest_sha256",
    "network_policy_observation",
    "credential_surface_observation",
    "final_runtime_disposition",
    "stop_reason",
}
SNAPSHOT_FIELDS = {
    "schema_version",
    "experiment_config_sha256",
    "candidate_id",
    "candidate_revision",
    "candidate_class",
    "evidence_key",
    "resolved_revision",
    "processor_or_tokenizer_identity",
    "model_config_sha256",
    "snapshot_manifest_sha256",
    "snapshot_file_count",
    "snapshot_total_bytes",
    "license_identity",
    "notice_identity",
    "usage_policy_identity",
    "trust_remote_code",
    "remote_code_exception_identity",
    "load_disposition",
    "failure_stage",
    "failure_class",
    "failure_message_sha256",
    "allocated_memory_after_load_bytes",
    "reserved_memory_after_load_bytes",
    "peak_allocated_memory_bytes",
    "peak_reserved_memory_bytes",
}
RESULT_FIELDS = {
    "schema_version",
    "experiment_config_sha256",
    "runtime_receipt_sha256",
    "candidate_snapshot_receipt_sha256",
    "candidate_id",
    "candidate_revision",
    "evidence_key",
    "lane",
    "metric_vector",
    "hard_floor_vector",
    "item_count",
    "invalid_item_count",
    "abstention_count",
    "resource_usage",
    "query_budget_used",
    "result_exposure_used",
    "result_manifest_sha256",
    "candidate_disposition",
    "limitations",
}
DECISION_FIELDS = {
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

SCHEMAS = {
    CONFIG: "MESC-EXPERIMENT-0-CONFIG-V1",
    RUNTIME: "MESC-EXPERIMENT-0-RUNTIME-V1",
    ENVIRONMENT: "MESC-EXPERIMENT-0-ENVIRONMENT-V1",
    DECISION: "MESC-EXPERIMENT-0-DECISION-V1",
    MANIFEST: "MESC-EXPERIMENT-0-BUNDLE-V1",
}
MANDATORY = set(SCHEMAS)
CANDIDATE_CLASSES = {"SELECTABLE_FOUNDATION", "REFERENCE_ONLY"}
SNAPSHOT_DISPOSITIONS = {
    "PASS_LOAD",
    "BLOCKED_ACQUISITION",
    "BLOCKED_RIGHTS",
    "BLOCKED_RUNTIME",
    "BLOCKED_REMOTE_CODE",
    "LOAD_FAILED",
}
RESULT_DISPOSITIONS = {
    "PASS_LANE",
    "FAIL_HARD_FLOOR",
    "BLOCKED_RUNTIME",
    "BLOCKED_RIGHTS",
    "BLOCKED_CONTAMINATION",
    "BLOCKED_EVALUATOR",
    "INVALID_RESULT",
    "NOT_SUPPORTED_BY_CANDIDATE",
}
RUNTIME_DISPOSITIONS = {
    "PASS_RUNTIME_PREFLIGHT",
    "BLOCKED_RUNTIME_IDENTITY",
    "BLOCKED_CUDA_UNAVAILABLE",
    "BLOCKED_RESOURCE_POLICY",
    "BLOCKED_DEPENDENCY_DRIFT",
    "BLOCKED_REPOSITORY_IDENTITY",
    "BLOCKED_OTHER",
}
SELECTION_DISPOSITIONS = {"RETAIN_PREFERRED_CANDIDATE", "SELECT_CHALLENGER"}
DECISION_DISPOSITIONS = SELECTION_DISPOSITIONS | {
    "INCONCLUSIVE_OR_BLOCKED",
    "INVALID_EXPERIMENT",
}
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_FIELDS = {
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
SECRET_PATTERNS = (
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+\S+"),
    re.compile(r"https?://[^/\s:@]+:[^@\s/]+@"),
)


class EvidenceError(ValueError):
    """Raised when Experiment-0 evidence fails closed."""


def digest(data: bytes) -> str:
    """Return SHA-256 for exact bytes."""
    return hashlib.sha256(data).hexdigest()


def require_fields(record: dict[str, Any], fields: set[str], label: str) -> None:
    """Require all contract fields."""
    missing = sorted(fields - set(record))
    if missing:
        raise EvidenceError(f"{label}: missing fields {missing}")


def require_text(value: Any, label: str) -> str:
    """Require a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{label}: expected non-empty string")
    return value


def require_hash(
    value: Any,
    label: str,
    pattern: re.Pattern[str] = SHA_RE,
) -> str:
    """Require an immutable lowercase hexadecimal identity."""
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise EvidenceError(f"{label}: invalid immutable digest")
    return value


def require_number(value: Any, label: str) -> None:
    """Require a non-negative finite numeric budget."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise EvidenceError(f"{label}: expected non-negative finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise EvidenceError(f"{label}: expected non-negative finite number")


def require_non_negative_int(value: Any, label: str) -> int:
    """Require an integer count or byte quantity that is zero or greater."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise EvidenceError(f"{label}: expected non-negative integer")
    return value


def load_json(data: bytes, path: str) -> Any:
    """Decode strict UTF-8 JSON after rejecting ambiguity and common serialized secrets."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceError(f"{path}: not UTF-8 JSON") from exc
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise EvidenceError(f"{path}: possible secret-bearing value detected")

    def reject_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, child in pairs:
            if key in value:
                raise EvidenceError(f"{path}: duplicate JSON key {key!r}")
            value[key] = child
        return value

    def reject_constant(value: str) -> None:
        raise EvidenceError(f"{path}: non-finite JSON constant {value!r}")

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_pairs,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"{path}: invalid JSON") from exc
    except RecursionError as exc:
        raise EvidenceError(f"{path}: JSON nesting exceeds safety limit") from exc


def scan_fields(value: Any, path: str) -> None:
    """Reject secret-like JSON field names recursively."""
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in SECRET_FIELDS:
                raise EvidenceError(f"{path}: forbidden secret-bearing field {key!r}")
            scan_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            scan_fields(child, f"{path}[{index}]")


def validate_path(name: str) -> None:
    """Reject unsafe, ambiguous, external, or non-JSON ZIP paths."""
    if "\x00" in name or "\\" in name:
        raise EvidenceError(f"invalid archive path: {name}")
    normalized = name.rstrip("/")
    parts = normalized.split("/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or any(part in {"", ".", ".."} for part in parts)
        or path.is_absolute()
        or not normalized.startswith(f"{ROOT}/")
    ):
        raise EvidenceError(f"path traversal or ambiguous archive path: {name}")
    if not name.endswith("/") and not name.endswith(".json"):
        raise EvidenceError(f"unexpected non-JSON payload: {name}")


def read_archive(path: Path) -> dict[str, bytes]:
    """Apply ZIP metadata and size checks before retaining member bytes."""
    with zipfile.ZipFile(path, "r") as archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBER_COUNT:
            raise EvidenceError("evidence archive exceeds member-count safety limit")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise EvidenceError("duplicate ZIP member paths")
        folded = [name.rstrip("/").casefold() for name in names]
        if len(folded) != len(set(folded)):
            raise EvidenceError("case-colliding ZIP member paths")
        total = 0
        readable = []
        for info in infos:
            validate_path(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if info.flag_bits & 0x1 or (mode and stat.S_ISLNK(mode)):
                raise EvidenceError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            if info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
                raise EvidenceError(f"ZIP member exceeds size limit: {info.filename}")
            total += info.file_size
            if total > MAX_TOTAL_UNCOMPRESSED_BYTES:
                raise EvidenceError("evidence archive exceeds total uncompressed-size limit")
            readable.append(info)
        return {info.filename: archive.read(info) for info in readable}


def validate_roster(roster: Any) -> list[dict[str, Any]]:
    """Validate candidate identity, class, key, revision, and modalities."""
    if not isinstance(roster, list) or not roster:
        raise EvidenceError("candidate_roster must be non-empty")
    identities: set[tuple[str, str]] = set()
    keys: set[str] = set()
    for index, candidate in enumerate(roster):
        label = f"candidate_roster[{index}]"
        if not isinstance(candidate, dict):
            raise EvidenceError(f"{label}: expected object")
        candidate_id = require_text(
            candidate.get("candidate_id"),
            f"{label}.candidate_id",
        )
        revision = require_hash(
            candidate.get("candidate_revision"),
            f"{label}.candidate_revision",
            GIT_RE,
        )
        candidate_class = candidate.get("candidate_class")
        key = candidate.get("evidence_key")
        modalities = candidate.get("supported_input_modalities")
        if candidate_class not in CANDIDATE_CLASSES:
            raise EvidenceError(f"{label}: invalid candidate_class")
        if not isinstance(key, str) or not KEY_RE.fullmatch(key):
            raise EvidenceError(f"{label}: invalid evidence_key")
        if not isinstance(modalities, list) or "text" not in modalities:
            raise EvidenceError(f"{label}: invalid supported_input_modalities")
        if candidate_class == "SELECTABLE_FOUNDATION" and "vision" not in modalities:
            raise EvidenceError(f"{label}: selectable foundation requires vision")
        if (candidate_id, revision) in identities or key in keys:
            raise EvidenceError(f"{label}: duplicate candidate identity")
        identities.add((candidate_id, revision))
        keys.add(key)
    return roster


def validate_config(config: Any) -> list[dict[str, Any]]:
    """Validate frozen policies, budgets, candidates, and MRL bindings."""
    if not isinstance(config, dict):
        raise EvidenceError("experiment-config.json: expected object")
    require_fields(config, CONFIG_FIELDS, "experiment-config.json")
    if config.get("schema_version") != SCHEMAS[CONFIG]:
        raise EvidenceError("experiment-config.json: schema mismatch")
    if config.get("status") != "FROZEN_EXECUTION_CONFIG":
        raise EvidenceError("experiment-config.json: config is not frozen")
    for field in ("experiment_id", "objective_id", "strategy_decision_id"):
        require_text(config.get(field), f"experiment-config.{field}")
    require_hash(config.get("repository_sha"), "repository_sha", GIT_RE)
    require_hash(config.get("repository_tree"), "repository_tree", GIT_RE)
    candidates = validate_roster(config.get("candidate_roster"))
    for field in (
        "dataset_identities",
        "evaluator_identities",
        "prompt_template_identities",
        "generation_configs",
    ):
        if not isinstance(config.get(field), list) or not config[field]:
            raise EvidenceError(f"experiment-config.{field}: must be non-empty")
    policy_fields = (
        "runtime_policy",
        "network_policy",
        "filesystem_policy",
        "credential_policy",
        "resource_budget",
        "query_budget",
        "result_exposure_budget",
        "hard_floor_policy",
        "decision_rule",
        "sealed_evaluation_policy",
        "authority_bindings",
    )
    for field in policy_fields:
        if not isinstance(config.get(field), dict) or not config[field]:
            raise EvidenceError(f"experiment-config.{field}: must be an object")
    runtime_policy = config["runtime_policy"]
    require_text(runtime_policy.get("provider"), "runtime_policy.provider")
    if runtime_policy.get("require_hosted_gpu") is not True:
        raise EvidenceError("runtime_policy.require_hosted_gpu must be true")
    allowed_gpu_count = require_non_negative_int(
        runtime_policy.get("allowed_gpu_count"),
        "runtime_policy.allowed_gpu_count",
    )
    if allowed_gpu_count < 1:
        raise EvidenceError("runtime_policy.allowed_gpu_count must be positive")
    allowed_gpu_models = runtime_policy.get("allowed_gpu_models")
    if not isinstance(allowed_gpu_models, list) or any(
        not isinstance(model, str) or not model.strip() for model in allowed_gpu_models
    ):
        raise EvidenceError("runtime_policy.allowed_gpu_models must be a list of model names")
    if len(allowed_gpu_models) != len(set(allowed_gpu_models)):
        raise EvidenceError("runtime_policy.allowed_gpu_models must be unique")
    allow_unlisted = runtime_policy.get("allow_unlisted_gpu_model")
    if not isinstance(allow_unlisted, bool):
        raise EvidenceError("runtime_policy.allow_unlisted_gpu_model must be boolean")
    if not allow_unlisted and not allowed_gpu_models:
        raise EvidenceError("runtime_policy.allowed_gpu_models cannot be empty when unlisted GPUs are blocked")
    for key in (
        "max_gpu_hours",
        "max_wall_hours",
        "max_storage_bytes",
        "max_retries",
    ):
        require_number(config["resource_budget"].get(key), f"resource_budget.{key}")
    require_number(
        config["query_budget"].get("max_adaptive_queries"),
        "query_budget.max_adaptive_queries",
    )
    for key in ("tier1_max_exposures", "tier2_max_exposures"):
        require_number(
            config["result_exposure_budget"].get(key),
            f"result_exposure_budget.{key}",
        )
    sealed = config["sealed_evaluation_policy"]
    if sealed.get("tier3_item_access_by_research_process") is not False:
        raise EvidenceError("Tier 3 research-process access must be false")
    bindings = config["authority_bindings"]
    missing = [key for key in REQUIRED_AUTHORITY_KEYS if not bindings.get(key)]
    if missing:
        raise EvidenceError(f"incomplete MRL authority/evidence bindings {sorted(missing)}")
    return candidates


def validate_environment(environment: Any) -> None:
    """Validate metadata-only environment evidence."""
    if (
        not isinstance(environment, dict)
        or environment.get("schema_version") != SCHEMAS[ENVIRONMENT]
    ):
        raise EvidenceError("environment-manifest.json: schema mismatch")
    require_text(environment.get("python_version"), "environment.python_version")
    require_text(environment.get("platform"), "environment.platform")
    packages = environment.get("packages")
    if not isinstance(packages, list):
        raise EvidenceError("environment.packages must be a list")
    for index, package in enumerate(packages):
        if not isinstance(package, dict):
            raise EvidenceError(f"environment.packages[{index}]: expected object")
        require_text(package.get("name"), f"environment.packages[{index}].name")
        require_text(package.get("version"), f"environment.packages[{index}].version")


def validate_runtime(
    runtime: Any,
    config: dict[str, Any],
    environment_hash: str,
) -> None:
    """Validate complete runtime identity, policy consistency, and environment binding."""
    if not isinstance(runtime, dict):
        raise EvidenceError("runtime-receipt.json: expected object")
    require_fields(runtime, RUNTIME_FIELDS, "runtime-receipt.json")
    if runtime.get("schema_version") != SCHEMAS[RUNTIME]:
        raise EvidenceError("runtime-receipt.json: schema mismatch")
    if runtime.get("repository_sha") != config.get("repository_sha"):
        raise EvidenceError("runtime/config repository_sha mismatch")
    if runtime.get("repository_tree") != config.get("repository_tree"):
        raise EvidenceError("runtime/config repository_tree mismatch")
    observed = require_hash(
        runtime.get("installed_environment_manifest_sha256"),
        "installed_environment_manifest_sha256",
    )
    if observed != environment_hash:
        raise EvidenceError("runtime receipt environment-manifest hash mismatch")
    disposition = runtime.get("final_runtime_disposition")
    if disposition not in RUNTIME_DISPOSITIONS:
        raise EvidenceError("invalid final_runtime_disposition")
    require_text(runtime.get("runtime_provider"), "runtime.runtime_provider")
    require_text(runtime.get("runtime_class"), "runtime.runtime_class")
    require_text(runtime.get("python_version"), "runtime.python_version")
    require_text(runtime.get("platform_string"), "runtime.platform_string")
    if not isinstance(runtime.get("cuda_available"), bool):
        raise EvidenceError("runtime.cuda_available must be boolean")
    gpu_count = require_non_negative_int(runtime.get("gpu_count"), "runtime.gpu_count")
    models = runtime.get("gpu_models")
    memory = runtime.get("gpu_total_memory_bytes")
    if not isinstance(models, list) or not isinstance(memory, list):
        raise EvidenceError("runtime GPU fields must be lists")
    if len(models) != gpu_count or len(memory) != gpu_count:
        raise EvidenceError("runtime GPU cardinality mismatch")
    for index, model in enumerate(models):
        require_text(model, f"runtime.gpu_models[{index}]")
    for index, total_bytes in enumerate(memory):
        require_non_negative_int(total_bytes, f"runtime.gpu_total_memory_bytes[{index}]")

    if disposition != "PASS_RUNTIME_PREFLIGHT":
        return

    policy = config["runtime_policy"]
    if runtime["runtime_provider"] != policy["provider"]:
        raise EvidenceError("PASS_RUNTIME_PREFLIGHT provider violates frozen runtime policy")
    if (
        policy["require_hosted_gpu"]
        and policy["provider"] == "GOOGLE_COLAB"
        and runtime["runtime_class"] != "GOOGLE_COLAB_HOSTED_GPU_RUNTIME"
    ):
        raise EvidenceError("PASS_RUNTIME_PREFLIGHT is not a Google Colab hosted GPU runtime")
    if runtime["cuda_available"] is not True:
        raise EvidenceError("PASS_RUNTIME_PREFLIGHT requires CUDA availability")
    if gpu_count != policy["allowed_gpu_count"]:
        raise EvidenceError("PASS_RUNTIME_PREFLIGHT GPU count violates frozen runtime policy")
    if not policy["allow_unlisted_gpu_model"]:
        disallowed = sorted(set(models) - set(policy["allowed_gpu_models"]))
        if disallowed:
            raise EvidenceError(
                f"PASS_RUNTIME_PREFLIGHT GPU model violates frozen runtime policy: {disallowed}"
            )
    if runtime.get("stop_reason") is not None:
        raise EvidenceError("PASS_RUNTIME_PREFLIGHT cannot carry a stop_reason")


def validate_snapshots(
    docs: dict[str, Any],
    members: dict[str, bytes],
    candidates: list[dict[str, Any]],
    config_hash: str,
) -> dict[str, dict[str, Any]]:
    """Require one complete snapshot receipt for every candidate."""
    expected = {
        f"{SNAPSHOTS}{candidate['evidence_key']}.json": candidate for candidate in candidates
    }
    if {path for path in members if path.startswith(SNAPSHOTS)} != set(expected):
        raise EvidenceError("candidate snapshot coverage mismatch")
    receipts: dict[str, dict[str, Any]] = {}
    for path, candidate in expected.items():
        receipt = docs[path]
        if not isinstance(receipt, dict):
            raise EvidenceError(f"{path}: expected object")
        require_fields(receipt, SNAPSHOT_FIELDS, path)
        expected_schema = "MESC-EXPERIMENT-0-CANDIDATE-SNAPSHOT-V1"
        if receipt.get("schema_version") != expected_schema:
            raise EvidenceError(f"{path}: schema mismatch")
        if receipt.get("experiment_config_sha256") != config_hash:
            raise EvidenceError(f"{path}: config hash mismatch")
        for field in (
            "candidate_id",
            "candidate_revision",
            "candidate_class",
            "evidence_key",
        ):
            if receipt.get(field) != candidate[field]:
                raise EvidenceError(f"{path}: roster identity mismatch")
        if receipt.get("resolved_revision") not in {
            None,
            candidate["candidate_revision"],
        }:
            raise EvidenceError(f"{path}: resolved revision mismatch")
        if receipt.get("load_disposition") not in SNAPSHOT_DISPOSITIONS:
            raise EvidenceError(f"{path}: invalid load disposition")
        if not isinstance(receipt.get("trust_remote_code"), bool):
            raise EvidenceError(f"{path}: trust_remote_code must be boolean")
        if receipt["trust_remote_code"] and not receipt.get("remote_code_exception_identity"):
            raise EvidenceError(f"{path}: remote-code exception missing")
        receipts[candidate["evidence_key"]] = {
            "record": receipt,
            "sha256": digest(members[path]),
        }
    return receipts


def validate_results(
    docs: dict[str, Any],
    members: dict[str, bytes],
    candidates: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    config_hash: str,
    runtime_hash: str,
) -> list[dict[str, Any]]:
    """Validate result contracts and immutable candidate/runtime bindings."""
    by_key = {candidate["evidence_key"]: candidate for candidate in candidates}
    results: list[dict[str, Any]] = []
    for path in sorted(name for name in members if name.startswith(RESULTS)):
        relative = path.removeprefix(RESULTS)
        parts = relative.split("/")
        if len(parts) != 2 or not parts[1].endswith(".json"):
            raise EvidenceError(f"invalid result path: {path}")
        key, lane = parts[0], parts[1][:-5]
        if key not in by_key or not KEY_RE.fullmatch(lane):
            raise EvidenceError(f"invalid result identity: {path}")
        result = docs[path]
        if not isinstance(result, dict):
            raise EvidenceError(f"{path}: expected object")
        require_fields(result, RESULT_FIELDS, path)
        candidate = by_key[key]
        expected_schema = "MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1"
        if result.get("schema_version") != expected_schema:
            raise EvidenceError(f"{path}: schema mismatch")
        if result.get("experiment_config_sha256") != config_hash:
            raise EvidenceError(f"{path}: config hash mismatch")
        if result.get("runtime_receipt_sha256") != runtime_hash:
            raise EvidenceError(f"{path}: runtime hash mismatch")
        if result.get("candidate_snapshot_receipt_sha256") != snapshots[key]["sha256"]:
            raise EvidenceError(f"{path}: snapshot hash mismatch")
        if result.get("candidate_id") != candidate["candidate_id"]:
            raise EvidenceError(f"{path}: candidate identity mismatch")
        if result.get("candidate_revision") != candidate["candidate_revision"]:
            raise EvidenceError(f"{path}: candidate revision mismatch")
        if result.get("evidence_key") != key:
            raise EvidenceError(f"{path}: evidence_key/path mismatch")
        if (
            result.get("lane") != lane
            or result.get("candidate_disposition") not in RESULT_DISPOSITIONS
        ):
            raise EvidenceError(f"{path}: lane/disposition mismatch")
        results.append(
            {
                "sha256": digest(members[path]),
                "candidate": candidate,
            }
        )
    return results


def validate_decision(
    decision: Any,
    candidates: list[dict[str, Any]],
    snapshots: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
    config_hash: str,
) -> None:
    """Validate complete decision evidence and safe foundation selection."""
    if not isinstance(decision, dict):
        raise EvidenceError("foundation-decision.json: expected object")
    require_fields(decision, DECISION_FIELDS, "foundation-decision.json")
    if decision.get("schema_version") != SCHEMAS[DECISION]:
        raise EvidenceError("foundation-decision.json: schema mismatch")
    if decision.get("experiment_config_sha256") != config_hash:
        raise EvidenceError("foundation-decision.json: config hash mismatch")
    disposition = decision.get("decision_disposition")
    if disposition not in DECISION_DISPOSITIONS:
        raise EvidenceError("foundation-decision.json: invalid disposition")
    declared = decision.get("candidate_result_sha256s")
    if not isinstance(declared, list) or declared != sorted(set(declared)):
        raise EvidenceError("candidate_result_sha256s must be sorted and unique")
    if any(not isinstance(value, str) or not SHA_RE.fullmatch(value) for value in declared):
        raise EvidenceError("candidate_result_sha256s contains invalid digest")
    if declared != sorted(result["sha256"] for result in results):
        raise EvidenceError("foundation-decision.json: candidate result hash set mismatch")
    hard = decision.get("hard_floor_summary")
    if not isinstance(hard, dict) or not isinstance(hard.get("all_mandatory_passed"), bool):
        raise EvidenceError("foundation-decision.json: malformed hard-floor summary")
    failed = hard.get("failed_floor_ids")
    if not isinstance(failed, list):
        raise EvidenceError("foundation-decision.json: failed_floor_ids must be a list")
    for field in (
        "metric_vector_summary",
        "resource_summary",
        "rights_summary",
        "contamination_summary",
    ):
        if not isinstance(decision.get(field), dict):
            raise EvidenceError(f"foundation-decision.json: {field} must be an object")
    require_text(decision.get("rationale"), "foundation-decision.rationale")
    if not isinstance(decision.get("limitations"), list):
        raise EvidenceError("foundation-decision.json: limitations must be a list")
    selected_id = decision.get("selected_candidate_id")
    selected_revision = decision.get("selected_candidate_revision")
    if disposition not in SELECTION_DISPOSITIONS:
        if selected_id is not None or selected_revision is not None:
            raise EvidenceError("blocked/invalid decision cannot select a candidate")
        return
    matching = [
        candidate
        for candidate in candidates
        if candidate["candidate_id"] == selected_id
        and candidate["candidate_revision"] == selected_revision
    ]
    if len(matching) != 1:
        raise EvidenceError("selected candidate is not in roster")
    selected = matching[0]
    if selected["candidate_class"] != "SELECTABLE_FOUNDATION":
        raise EvidenceError("reference-only candidate cannot be selected")
    snapshot = snapshots[selected["evidence_key"]]["record"]
    if snapshot.get("load_disposition") != "PASS_LOAD":
        raise EvidenceError("selected candidate load did not pass")
    if not any(result["candidate"] == selected for result in results):
        raise EvidenceError("selected candidate has no result evidence")
    if not decision.get("sealed_evaluation_receipt_identity"):
        raise EvidenceError("sealed evaluation receipt missing")
    if hard["all_mandatory_passed"] is not True or failed:
        raise EvidenceError("selection attempted with failed hard floors")


def validate_manifest(manifest: Any, members: dict[str, bytes]) -> None:
    """Validate exact bundle coverage, sizes, hashes, and media types."""
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMAS[MANIFEST]:
        raise EvidenceError("bundle-manifest.json: schema mismatch")
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        raise EvidenceError("bundle-manifest.json: entries must be a list")
    expected = set(members) - {MANIFEST}
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise EvidenceError("bundle-manifest.json: malformed entry")
        path = entry["path"]
        if path == MANIFEST:
            raise EvidenceError("bundle-manifest.json must not list/hash itself")
        if path in seen or path not in members:
            raise EvidenceError("bundle-manifest.json: duplicate or missing path")
        seen.add(path)
        data = members[path]
        if entry.get("size_bytes") != len(data) or entry.get("sha256") != digest(data):
            raise EvidenceError(f"bundle-manifest mismatch: {path}")
        if entry.get("media_type") != "application/json":
            raise EvidenceError(f"bundle-manifest media_type mismatch: {path}")
    if seen != expected:
        raise EvidenceError("bundle-manifest coverage mismatch")


def verify(path: str | Path) -> dict[str, Any]:
    """Verify Experiment-0 structure, identities, hashes, and decision integrity."""
    path_obj = Path(path)
    members = read_archive(path_obj)
    missing = sorted(MANDATORY - set(members))
    if missing:
        raise EvidenceError(f"missing mandatory evidence members: {missing}")
    docs = {name: load_json(data, name) for name, data in members.items()}
    for name, value in docs.items():
        scan_fields(value, name)
    for name, schema in SCHEMAS.items():
        if not isinstance(docs[name], dict) or docs[name].get("schema_version") != schema:
            raise EvidenceError(f"{name}: expected schema {schema}")
    config = docs[CONFIG]
    candidates = validate_config(config)
    config_hash = digest(
        json.dumps(
            config,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )
    validate_environment(docs[ENVIRONMENT])
    environment_hash = digest(members[ENVIRONMENT])
    runtime = docs[RUNTIME]
    validate_runtime(runtime, config, environment_hash)
    if runtime.get("experiment_config_sha256") != config_hash:
        raise EvidenceError("runtime receipt does not bind canonical config hash")
    runtime_hash = digest(members[RUNTIME])
    snapshots = validate_snapshots(docs, members, candidates, config_hash)
    results = validate_results(
        docs,
        members,
        candidates,
        snapshots,
        config_hash,
        runtime_hash,
    )
    decision = docs[DECISION]
    validate_decision(decision, candidates, snapshots, results, config_hash)
    validate_manifest(docs[MANIFEST], members)
    return {
        "status": "VERIFIED_STRUCTURE_AND_IDENTITY",
        "archive_sha256": digest(path_obj.read_bytes()),
        "member_count": len(members),
        "candidate_count": len(candidates),
        "candidate_result_count": len(results),
        "experiment_config_sha256": config_hash,
        "repository_sha": config["repository_sha"],
        "repository_tree": config["repository_tree"],
        "runtime_disposition": runtime["final_runtime_disposition"],
        "decision_disposition": decision["decision_disposition"],
    }


def main() -> int:
    """Run the verifier CLI and emit one JSON verdict."""
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
