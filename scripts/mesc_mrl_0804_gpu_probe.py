#!/usr/bin/env python3
"""Emit bounded hosted-GPU observation and smoke evidence for MRL-0804."""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import platform
import re
from pathlib import Path
from typing import Any

_SCHEMA = "MESC-MRL-0804-RUNTIME-OBSERVATION-V1"
_SMOKE_KIND = "mesc.training_runtime_smoke.v1"
_PROBE_ID = "MESC-MRL-0804-CUDA-INTEGER-SMOKE"
_PROBE_VERSION = "v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)


def canonical_json_bytes(value: object) -> bytes:
    """Serialize the closed probe payload using the repository canonical JSON byte shape."""
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("GOOGLE_COLAB", "HUGGING_FACE_JOBS"), required=True)
    parser.add_argument("--provider-flavor", required=True)
    parser.add_argument("--runner-class", choices=("colab", "other"), required=True)
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--repository-tree", required=True)
    parser.add_argument("--dependency-lock-sha256", required=True)
    parser.add_argument("--probe-source-sha256", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser


def _require_digest(value: str, *, label: str) -> str:
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


def _require_git_sha(value: str, *, label: str) -> str:
    if _GIT_SHA.fullmatch(value) is None:
        raise ValueError(f"{label} must be lowercase 40-hex Git identity")
    return value


def _exact_source_digest() -> str:
    return hashlib.sha256(Path(__file__).resolve(strict=True).read_bytes()).hexdigest()


def build_probe_artifacts(
    *,
    torch_module: Any,
    provider: str,
    provider_flavor: str,
    runner_class: str,
    repository_sha: str,
    repository_tree: str,
    dependency_lock_sha256: str,
    probe_source_sha256: str,
) -> tuple[bytes, bytes]:
    """Run one bounded integer CUDA smoke and return canonical observation/smoke bytes."""
    if provider not in {"GOOGLE_COLAB", "HUGGING_FACE_JOBS"}:
        raise ValueError("provider is not supported by the MRL-0804 probe")
    if not provider_flavor.strip() or provider_flavor != provider_flavor.strip():
        raise ValueError("provider_flavor must be exact non-empty text")
    if runner_class not in {"colab", "other"}:
        raise ValueError("runner_class is invalid")
    repository_sha = _require_git_sha(repository_sha, label="repository_sha")
    repository_tree = _require_git_sha(repository_tree, label="repository_tree")
    dependency_lock_sha256 = _require_digest(dependency_lock_sha256, label="dependency_lock_sha256")
    probe_source_sha256 = _require_digest(probe_source_sha256, label="probe_source_sha256")

    if not bool(torch_module.cuda.is_available()):
        raise RuntimeError("CUDA is unavailable on the hosted runtime")
    gpu_count = int(torch_module.cuda.device_count())
    if gpu_count != 1:
        raise RuntimeError(f"MRL-0804 requires exactly one hosted GPU, observed {gpu_count}")
    gpu_models = [str(torch_module.cuda.get_device_name(index)) for index in range(gpu_count)]
    gpu_memory = [
        int(torch_module.cuda.get_device_properties(index).total_memory)
        for index in range(gpu_count)
    ]
    if any(not name.strip() for name in gpu_models) or any(value <= 0 for value in gpu_memory):
        raise RuntimeError("hosted GPU identity or memory observation is invalid")
    cuda_version_value = torch_module.version.cuda
    if not isinstance(cuda_version_value, str) or not cuda_version_value.strip():
        raise RuntimeError("PyTorch did not report an exact CUDA runtime version")

    source = torch_module.arange(1, 17, dtype=torch_module.int64, device="cuda")
    result = source * 3 + 7
    torch_module.cuda.synchronize()
    observed = [int(value) for value in result.cpu().tolist()]
    expected = [value * 3 + 7 for value in range(1, 17)]
    disposition = "PASS" if observed == expected else "FAIL"

    python_version = platform.python_version()
    os_name = platform.platform()
    torch_version = str(torch_module.__version__)
    common = {
        "dependency_lock_sha256": dependency_lock_sha256,
        "gpu_model": gpu_models[0],
        "network_accessed": False,
        "os_name": os_name,
        "probe_id": _PROBE_ID,
        "probe_version": _PROBE_VERSION,
        "python_version": python_version,
        "remote_code_allowed": False,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runner_class": runner_class,
    }
    smoke = canonical_json_bytes(
        {
            **common,
            "disposition": disposition,
            "kind": _SMOKE_KIND,
        }
    )
    observation = canonical_json_bytes(
        {
            "cuda_available": True,
            "cuda_version": cuda_version_value,
            "dependency_lock_sha256": dependency_lock_sha256,
            "gpu_count": gpu_count,
            "gpu_models": gpu_models,
            "gpu_total_memory_bytes": gpu_memory,
            "network_accessed": False,
            "os_name": os_name,
            "probe_id": _PROBE_ID,
            "probe_source_sha256": probe_source_sha256,
            "probe_version": _PROBE_VERSION,
            "provider": provider,
            "provider_flavor": provider_flavor,
            "python_version": python_version,
            "remote_code_allowed": False,
            "repository_sha": repository_sha,
            "repository_tree": repository_tree,
            "runner_class": runner_class,
            "schema_version": _SCHEMA,
            "torch_version": torch_version,
        }
    )
    if disposition != "PASS":
        raise RuntimeError("bounded CUDA integer smoke did not reproduce the expected vector")
    return observation, smoke


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def main() -> int:
    args = _parser().parse_args()
    repository_sha = _require_git_sha(args.repository_sha, label="repository_sha")
    repository_tree = _require_git_sha(args.repository_tree, label="repository_tree")
    lock_sha = _require_digest(args.dependency_lock_sha256, label="dependency_lock_sha256")
    expected_source = _require_digest(args.probe_source_sha256, label="probe_source_sha256")
    observed_source = _exact_source_digest()
    if observed_source != expected_source:
        raise RuntimeError("downloaded probe source does not match the authorized exact digest")

    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=False)

    torch_module = importlib.import_module("torch")

    observation, smoke = build_probe_artifacts(
        torch_module=torch_module,
        provider=args.provider,
        provider_flavor=args.provider_flavor,
        runner_class=args.runner_class,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        dependency_lock_sha256=lock_sha,
        probe_source_sha256=observed_source,
    )
    _write_new(output_root / "runtime-observation.json", observation)
    _write_new(output_root / "runtime-smoke.json", smoke)

    print(f"MESC_MRL_0804_OBSERVATION_SHA256={hashlib.sha256(observation).hexdigest()}")
    print(f"MESC_MRL_0804_SMOKE_SHA256={hashlib.sha256(smoke).hexdigest()}")
    print("MESC_MRL_0804_OBSERVATION_B64=" + base64.b64encode(observation).decode("ascii"))
    print("MESC_MRL_0804_SMOKE_B64=" + base64.b64encode(smoke).decode("ascii"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
