"""Fixture-only Phi sandbox-qualification artifact conformance verification.

This module validates caller-supplied synthetic artifact bytes against the canonical
sandbox-qualification byte contract and binds them to canonical fixture runtime
binding bytes. It does not issue freshness challenges, maintain live verifier state,
configure or inspect a sandbox, invoke a producer, access real Phi source or models,
or grant execution authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Never, cast

import medscale.mesc._bt_activation_identity_fixture_v1 as activation_fixture

_VERSION: Final = "MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1"
_PASS: Final = "PASS"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_PRODUCER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_BOM: Final = b"\xef\xbb\xbf"
_TOP_LEVEL_KEYS: Final = (
    "artifact_version",
    "controls",
    "controls_active_before_model_load",
    "controls_active_before_remote_code_import",
    "dedicated_model_process",
    "producer_identity",
    "qualification_challenge",
    "qualification_disposition",
    "runtime_binding_sha256",
)
_CONTROL_VALUES: Final = {
    "cloud_metadata_access": "DENIED",
    "credential_environment": "EMPTY",
    "dns": "UNAVAILABLE_TO_MODEL_PROCESS",
    "frozen_gold_scoring_inputs_visible_to_model_process": "NO",
    "host_or_container_control_sockets": "NONE",
    "model_and_runtime_input_mounts": "READ_ONLY_ALLOWLIST_ONLY",
    "network_egress": "DENY_ALL",
    "network_ingress": "DENY_ALL",
    "remote_fetch_during_model_process": "PROHIBITED",
    "writable_paths": "ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY",
}
_CONTROL_KEYS: Final = tuple(_CONTROL_VALUES)


class PhiSandboxQualificationArtifactFixtureError(ValueError):
    """Fail-closed fixture sandbox-qualification artifact conformance error."""


@dataclass(frozen=True, slots=True)
class PhiSandboxQualificationArtifact:
    """Validated fixture artifact bytes plus detached values for outer fixture tests."""

    canonical_bytes: bytes
    sha256: str
    runtime_binding_sha256: str
    qualification_challenge: str
    producer_identity: str


def verify_phi_sandbox_qualification_artifact_fixture(
    payload: bytes,
    runtime_binding_bytes: bytes,
) -> PhiSandboxQualificationArtifact:
    """Validate one supplied V1 fixture artifact without performing qualification."""
    runtime_binding_sha256 = _runtime_binding_sha256(runtime_binding_bytes)
    document = _document(payload)

    if tuple(document) != _TOP_LEVEL_KEYS:
        raise PhiSandboxQualificationArtifactFixtureError(
            "artifact top-level member set/order mismatch"
        )

    _require_exact_string(
        document["artifact_version"],
        field="artifact_version",
        expected=_VERSION,
    )
    _controls(document["controls"])
    _require_exact_true(
        document["controls_active_before_model_load"],
        field="controls_active_before_model_load",
    )
    _require_exact_true(
        document["controls_active_before_remote_code_import"],
        field="controls_active_before_remote_code_import",
    )
    _require_exact_true(
        document["dedicated_model_process"],
        field="dedicated_model_process",
    )

    producer_identity = document["producer_identity"]
    if type(producer_identity) is not str or _PRODUCER.fullmatch(producer_identity) is None:
        raise PhiSandboxQualificationArtifactFixtureError(
            "producer_identity violates the frozen grammar"
        )

    challenge = _require_sha256(
        document["qualification_challenge"],
        field="qualification_challenge",
    )
    _require_exact_string(
        document["qualification_disposition"],
        field="qualification_disposition",
        expected=_PASS,
    )
    bound_runtime = _require_sha256(
        document["runtime_binding_sha256"],
        field="runtime_binding_sha256",
    )
    if bound_runtime != runtime_binding_sha256:
        raise PhiSandboxQualificationArtifactFixtureError(
            "runtime_binding_sha256 does not reproduce the canonical supplied runtime binding"
        )

    canonical = _canonical(document)
    if canonical != payload:
        raise PhiSandboxQualificationArtifactFixtureError(
            "artifact is not the exact canonical ASCII JSON serialization"
        )

    return PhiSandboxQualificationArtifact(
        canonical_bytes=canonical,
        sha256=hashlib.sha256(canonical).hexdigest(),
        runtime_binding_sha256=runtime_binding_sha256,
        qualification_challenge=challenge,
        producer_identity=producer_identity,
    )


def _runtime_binding_sha256(raw: bytes) -> str:
    try:
        activation_fixture._parse_runtime_binding(raw)
    except activation_fixture.FixtureActivationBlockedError as error:
        raise PhiSandboxQualificationArtifactFixtureError(
            "runtime binding is not canonical under the activation identity validator"
        ) from error
    return hashlib.sha256(raw).hexdigest()


def _document(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise PhiSandboxQualificationArtifactFixtureError(
            "artifact must be non-empty exact built-in bytes"
        )
    if raw.startswith(_BOM):
        raise PhiSandboxQualificationArtifactFixtureError("UTF-8 BOM is prohibited")
    if raw.endswith(b"\n") or raw.endswith(b"\r"):
        raise PhiSandboxQualificationArtifactFixtureError("trailing newline is prohibited")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise PhiSandboxQualificationArtifactFixtureError("artifact must be ASCII JSON") from error
    try:
        value: object = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_json_constant,
        )
    except json.JSONDecodeError as error:
        raise PhiSandboxQualificationArtifactFixtureError("artifact is not valid JSON") from error
    if type(value) is not dict:
        raise PhiSandboxQualificationArtifactFixtureError(
            "artifact top level must be exactly one JSON object"
        )
    return cast(dict[str, object], value)


def _controls(value: object) -> dict[str, str]:
    if type(value) is not dict:
        raise PhiSandboxQualificationArtifactFixtureError("controls must be exactly one object")
    controls = cast(dict[str, object], value)
    if tuple(controls) != _CONTROL_KEYS:
        raise PhiSandboxQualificationArtifactFixtureError("controls member set/order mismatch")

    validated: dict[str, str] = {}
    for key, expected in _CONTROL_VALUES.items():
        actual = controls[key]
        if type(actual) is not str or actual != expected:
            raise PhiSandboxQualificationArtifactFixtureError(f"control value mismatch: {key}")
        validated[key] = actual
    return validated


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise PhiSandboxQualificationArtifactFixtureError(
            "artifact cannot be canonically serialized"
        ) from error


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PhiSandboxQualificationArtifactFixtureError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _reject_json_constant(token: str) -> Never:
    raise PhiSandboxQualificationArtifactFixtureError(
        f"non-standard JSON constant prohibited: {token}"
    )


def _require_exact_true(value: object, *, field: str) -> None:
    if type(value) is not bool or value is not True:
        raise PhiSandboxQualificationArtifactFixtureError(f"{field} must be JSON boolean true")


def _require_exact_string(value: object, *, field: str, expected: str) -> None:
    if type(value) is not str or value != expected:
        raise PhiSandboxQualificationArtifactFixtureError(f"{field} must be exactly {expected}")


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise PhiSandboxQualificationArtifactFixtureError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value
