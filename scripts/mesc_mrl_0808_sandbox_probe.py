#!/usr/bin/env python3
"""Synthetic control-only MRL-0808 sandbox probe prototype.

This prototype is intentionally non-scientific. It loads no model/tokenizer, reads no
sealed Tier-3 content, performs no inference/training, and grants no authority. A later
canonical producer must bind these observed controls to live owner authority and an
independently attested hosted runtime instance.
"""

from __future__ import annotations

import contextlib
import json
import os
import pathlib
import re
import socket
import sys
from typing import Final

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_ROOT = pathlib.Path("/mesc-run")
_REPOSITORY = _ROOT / "repository"
_INPUTS = _ROOT / "inputs"
_WEIGHTS = _ROOT / "model-weights"
_SCRATCH = _ROOT / "scratch"
_OUTPUT = _ROOT / "output"
_CREDENTIAL_NAMES: Final = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "HF_TOKEN",
    "HUGGING_FACE_HUB_TOKEN",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
)
_CONTROL_SOCKETS: Final = (
    pathlib.Path("/var/run/docker.sock"),
    pathlib.Path("/run/docker.sock"),
    pathlib.Path("/run/containerd/containerd.sock"),
    pathlib.Path("/var/run/podman/podman.sock"),
)


def canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, allow_nan=False, separators=(",", ":"), sort_keys=True
    ).encode("ascii")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value or value != value.strip() or "\x00" in value:
        raise RuntimeError(f"missing/invalid required environment: {name}")
    return value


def sha_env(name: str) -> str:
    value = required_env(name)
    if _SHA256.fullmatch(value) is None:
        raise RuntimeError(f"{name} must be 64 lowercase hex")
    return value


def write_probe(path: pathlib.Path, payload: bytes) -> bool:
    try:
        path.write_bytes(payload)
    except OSError:
        return False
    else:
        with contextlib.suppress(OSError):
            path.unlink()
        return True


def socket_connect(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.5)
    try:
        return sock.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def dns_works() -> bool:
    try:
        socket.getaddrinfo("example.com", 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return True


def main() -> int:
    challenge = sha_env("MESC_MRL0808_CHALLENGE")
    policy_sha = sha_env("MESC_MRL0808_SANDBOX_POLICY_SHA256")
    network_sha = sha_env("MESC_MRL0808_NETWORK_POLICY_SHA256")
    mutation_sha = sha_env("MESC_MRL0808_MUTATION_PATHS_SHA256")
    output_sha = sha_env("MESC_MRL0808_OUTPUT_DESTINATIONS_SHA256")
    stop_sha = sha_env("MESC_MRL0808_STOP_CONDITIONS_SHA256")
    runtime_evidence_sha = sha_env("MESC_MRL0808_PREDECESSOR_RUNTIME_EVIDENCE_SHA256")
    runtime_identity_sha = sha_env("MESC_MRL0808_PREDECESSOR_RUNTIME_IDENTITY_SHA256")
    runtime_context_sha = sha_env("MESC_MRL0808_RUNTIME_CONTEXT_SHA256")

    for path in (_REPOSITORY, _INPUTS, _WEIGHTS, _SCRATCH, _OUTPUT):
        if not path.exists() or not path.is_dir() or path.is_symlink():
            raise RuntimeError(f"required sandbox path missing/unsafe: {path}")

    credential_env_empty = all(not os.environ.get(name) for name in _CREDENTIAL_NAMES)
    control_sockets_absent = all(not path.exists() for path in _CONTROL_SOCKETS)
    scratch_write_allowed = write_probe(_SCRATCH / ".mrl0808-write-probe", b"scratch")
    output_write_allowed = write_probe(_OUTPUT / ".mrl0808-write-probe", b"output")
    repository_write_denied = not write_probe(_REPOSITORY / ".mrl0808-write-probe", b"deny")
    inputs_write_denied = not write_probe(_INPUTS / ".mrl0808-write-probe", b"deny")
    weights_write_denied = not write_probe(_WEIGHTS / ".mrl0808-write-probe", b"deny")
    root_write_denied = not write_probe(pathlib.Path("/.mrl0808-write-probe"), b"deny")
    home_write_denied = not write_probe(pathlib.Path("/home/.mrl0808-write-probe"), b"deny")
    tmp_write_denied = not write_probe(pathlib.Path("/tmp/.mrl0808-write-probe"), b"deny")
    dns_unavailable = not dns_works()
    egress_denied = not socket_connect("1.1.1.1", 443)
    metadata_denied = not socket_connect("169.254.169.254", 80)

    controls = {
        "cloud_metadata_access_denied": metadata_denied,
        "control_sockets_absent": control_sockets_absent,
        "credential_environment_empty": credential_env_empty,
        "dns_unavailable": dns_unavailable,
        "inputs_read_only_enforced": inputs_write_denied,
        "model_weights_read_only_enforced": weights_write_denied,
        "network_egress_denied": egress_denied,
        "output_write_allowed": output_write_allowed,
        "repository_read_only_enforced": repository_write_denied,
        "root_write_denied": root_write_denied,
        "scratch_write_allowed": scratch_write_allowed,
        "tmp_write_denied": tmp_write_denied,
        "home_write_denied": home_write_denied,
    }
    if not all(controls.values()):
        failed = sorted(key for key, value in controls.items() if not value)
        raise RuntimeError("sandbox control probe failed: " + ",".join(failed))

    observation = {
        "challenge": challenge,
        "controls": controls,
        "monetary_cost_microunits": 0,
        "model_loaded": False,
        "mutation_paths_sha256": mutation_sha,
        "network_policy_sha256": network_sha,
        "output_destinations_sha256": output_sha,
        "predecessor_runtime_evidence_sha256": runtime_evidence_sha,
        "predecessor_runtime_identity_sha256": runtime_identity_sha,
        "runtime_context_sha256": runtime_context_sha,
        "sandbox_policy_sha256": policy_sha,
        "schema_version": "MESC-MRL-0808-RUNTIME-SANDBOX-OBSERVATION-V1",
        "sealed_tier3_item_content_accessed": False,
        "stop_conditions_sha256": stop_sha,
        "tokenizer_loaded": False,
        "training_performed": False,
        "weight_mutation_performed": False,
    }
    raw = canonical(observation)
    sys.stdout.buffer.write(raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
