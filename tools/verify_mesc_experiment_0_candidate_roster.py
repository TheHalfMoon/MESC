from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "MESC-EXPERIMENT-0-CANDIDATE-ROSTER-V1"
STATUS = "FROZEN_METADATA_ONLY"
GIT_RE = re.compile(r"^[0-9a-f]{40}$")
KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

TOP_LEVEL_FIELDS = {
    "schema_version",
    "status",
    "frozen_at_utc",
    "canonical_base_sha",
    "canonical_base_tree",
    "result_exposure_started",
    "mrl_0801_state",
    "real_model_execution_authorized",
    "training_authorized",
    "active_candidates",
    "deferred_controls",
}
ACTIVE_FIELDS = {
    "candidate_id",
    "candidate_revision",
    "candidate_class",
    "role",
    "evidence_key",
    "license_identity",
    "published_pipeline",
    "published_weight_size_label",
    "supported_input_modalities",
    "trust_remote_code",
    "remote_code_exception_required",
    "eligibility_disposition",
    "authoritative_sources",
}
DEFERRED_FIELDS = {
    "candidate_id",
    "observed_revision",
    "role",
    "license_identity",
    "published_pipeline",
    "published_weight_size_label",
    "trust_remote_code_required_by_published_path",
    "eligibility_disposition",
    "authoritative_sources",
}


class CandidateRosterError(ValueError):
    """Raised when the Experiment-0 Phase 0 roster fails closed."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build one JSON object while rejecting duplicate keys at every nesting level."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CandidateRosterError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _require_exact_fields(
    record: dict[str, Any],
    expected: set[str],
    label: str,
) -> None:
    """Reject missing or unexpected fields in a closed record."""
    observed = set(record)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise CandidateRosterError(
            f"{label}: closed-field mismatch missing={missing} extra={extra}"
        )


def _require_text(value: Any, label: str) -> str:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise CandidateRosterError(f"{label}: expected non-empty string")
    return value


def _require_git_sha(value: Any, label: str) -> str:
    """Require one immutable full Git-style revision."""
    text = _require_text(value, label)
    if not GIT_RE.fullmatch(text):
        raise CandidateRosterError(f"{label}: expected 40-character lowercase hex revision")
    return text


def _require_sources(value: Any, label: str) -> list[str]:
    """Require non-empty HTTPS authoritative-source URLs."""
    if not isinstance(value, list) or not value:
        raise CandidateRosterError(f"{label}: expected non-empty source list")
    sources: list[str] = []
    for index, item in enumerate(value):
        source = _require_text(item, f"{label}[{index}]")
        if not source.startswith("https://"):
            raise CandidateRosterError(f"{label}[{index}]: HTTPS source required")
        sources.append(source)
    return sources


def validate_roster(payload: Any) -> dict[str, Any]:
    """Validate the metadata-only Phase 0 roster without granting execution authority."""
    if not isinstance(payload, dict):
        raise CandidateRosterError("roster: expected object")
    _require_exact_fields(payload, TOP_LEVEL_FIELDS, "roster")
    if payload["schema_version"] != SCHEMA:
        raise CandidateRosterError("roster: schema mismatch")
    if payload["status"] != STATUS:
        raise CandidateRosterError("roster: status must remain metadata-only")
    _require_text(payload["frozen_at_utc"], "roster.frozen_at_utc")
    _require_git_sha(payload["canonical_base_sha"], "roster.canonical_base_sha")
    _require_git_sha(payload["canonical_base_tree"], "roster.canonical_base_tree")
    if payload["result_exposure_started"] is not False:
        raise CandidateRosterError("roster: result exposure must not have started")
    if payload["mrl_0801_state"] != "ABSENT":
        raise CandidateRosterError("roster: MRL-0801 must remain ABSENT")
    if payload["real_model_execution_authorized"] is not False:
        raise CandidateRosterError("roster: real model execution must remain unauthorized")
    if payload["training_authorized"] is not False:
        raise CandidateRosterError("roster: training must remain unauthorized")

    active = payload["active_candidates"]
    if not isinstance(active, list) or len(active) < 2:
        raise CandidateRosterError("roster.active_candidates: at least two candidates required")

    identities: set[tuple[str, str]] = set()
    roles: set[str] = set()
    keys: set[str] = set()
    for index, candidate in enumerate(active):
        label = f"roster.active_candidates[{index}]"
        if not isinstance(candidate, dict):
            raise CandidateRosterError(f"{label}: expected object")
        _require_exact_fields(candidate, ACTIVE_FIELDS, label)
        candidate_id = _require_text(
            candidate["candidate_id"],
            f"{label}.candidate_id",
        )
        revision = _require_git_sha(
            candidate["candidate_revision"],
            f"{label}.candidate_revision",
        )
        if candidate["candidate_class"] != "SELECTABLE_FOUNDATION":
            raise CandidateRosterError(f"{label}: active candidate must be selectable")
        role = _require_text(candidate["role"], f"{label}.role")
        key = _require_text(candidate["evidence_key"], f"{label}.evidence_key")
        if not KEY_RE.fullmatch(key):
            raise CandidateRosterError(f"{label}.evidence_key: invalid key")
        _require_text(candidate["license_identity"], f"{label}.license_identity")
        _require_text(candidate["published_pipeline"], f"{label}.published_pipeline")
        _require_text(
            candidate["published_weight_size_label"],
            f"{label}.published_weight_size_label",
        )
        modalities = candidate["supported_input_modalities"]
        if (
            not isinstance(modalities, list)
            or "text" not in modalities
            or "vision" not in modalities
        ):
            raise CandidateRosterError(f"{label}: active candidate must declare text and vision")
        if candidate["trust_remote_code"] is not False:
            raise CandidateRosterError(f"{label}: active candidate cannot require remote code")
        if candidate["remote_code_exception_required"] is not False:
            raise CandidateRosterError(
                f"{label}: active candidate cannot require a remote-code exception"
            )
        if (
            candidate["eligibility_disposition"]
            != "ACTIVE_FOR_MRL_0801_IDENTITY_CUSTODY_QUALIFICATION"
        ):
            raise CandidateRosterError(f"{label}: invalid eligibility disposition")
        _require_sources(
            candidate["authoritative_sources"],
            f"{label}.authoritative_sources",
        )
        identity = (candidate_id, revision)
        if identity in identities:
            raise CandidateRosterError(f"{label}: duplicate candidate identity")
        if role in roles:
            raise CandidateRosterError(f"{label}: duplicate candidate role")
        if key in keys:
            raise CandidateRosterError(f"{label}: duplicate evidence key")
        identities.add(identity)
        roles.add(role)
        keys.add(key)

    if "PREFERRED_FOUNDATION_CANDIDATE" not in roles or "PRIMARY_CHALLENGER" not in roles:
        raise CandidateRosterError(
            "roster.active_candidates: preferred and challenger roles are required"
        )

    deferred = payload["deferred_controls"]
    if not isinstance(deferred, list):
        raise CandidateRosterError("roster.deferred_controls: expected list")
    for index, candidate in enumerate(deferred):
        label = f"roster.deferred_controls[{index}]"
        if not isinstance(candidate, dict):
            raise CandidateRosterError(f"{label}: expected object")
        _require_exact_fields(candidate, DEFERRED_FIELDS, label)
        _require_text(candidate["candidate_id"], f"{label}.candidate_id")
        _require_git_sha(candidate["observed_revision"], f"{label}.observed_revision")
        if candidate["role"] != "DEFERRED_CONTROL":
            raise CandidateRosterError(f"{label}: invalid deferred role")
        _require_text(candidate["license_identity"], f"{label}.license_identity")
        _require_text(candidate["published_pipeline"], f"{label}.published_pipeline")
        _require_text(
            candidate["published_weight_size_label"],
            f"{label}.published_weight_size_label",
        )
        if candidate["trust_remote_code_required_by_published_path"] is not True:
            raise CandidateRosterError(f"{label}: deferred remote-code reason must remain explicit")
        if candidate["eligibility_disposition"] != "DEFERRED_REMOTE_CODE_EXCEPTION_REQUIRED":
            raise CandidateRosterError(f"{label}: invalid deferred disposition")
        _require_sources(
            candidate["authoritative_sources"],
            f"{label}.authoritative_sources",
        )

    return payload


def load_and_validate(path: Path) -> dict[str, Any]:
    """Read and validate one UTF-8 JSON roster."""
    try:
        payload: Any = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CandidateRosterError(f"{path}: invalid roster JSON") from exc
    return validate_roster(payload)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for deterministic Phase 0 roster validation."""
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        payload = load_and_validate(args.path)
    except CandidateRosterError as exc:
        print(f"INVALID: {exc}")
        return 1
    print(
        "VALID:",
        payload["schema_version"],
        f"active_candidates={len(payload['active_candidates'])}",
        f"mrl_0801_state={payload['mrl_0801_state']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
