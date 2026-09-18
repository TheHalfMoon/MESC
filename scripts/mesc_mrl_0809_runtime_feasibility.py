#!/usr/bin/env python3
"""MRL-0809 bounded Google Colab runtime-feasibility qualification harness.

This harness is intentionally non-scientific. It never reads the MESC scientific
corpus or sealed Tier-3 items. Model snapshots are staged before the isolated
probe, then each frozen candidate is loaded and given one fixed synthetic prompt
inside a no-network bubblewrap sandbox. The final receipt is self-validated by
the canonical repository validator before it can be emitted.
"""

from __future__ import annotations

import argparse
import fnmatch
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Never, cast

SCHEMA_STAGE: Final = "MESC-MRL-0809-STAGE-RECEIPT-V1"
SCHEMA_WORKER: Final = "MESC-MRL-0809-CANDIDATE-WORKER-V1"
SCHEMA_OBSERVATION: Final = "MESC-MRL-0809-CANDIDATE-OBSERVATION-V1"
SCHEMA_RECEIPT: Final = "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V1"
RUNTIME_REPRESENTATION: Final = "bitsandbytes-nf4-v1"
PROCESSOR_POLICY: Final = "AUTO_PROCESSOR_EXACT_REVISION"
SYNTHETIC_PROMPT: Final = "Write one short sentence about a blue triangle."
MAX_NEW_TOKENS: Final = 12
GPU_MODEL: Final = "Tesla T4"
SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
SHA64: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)

STATIC_MANIFEST = Path("specs/mesc-experiment-0/mrl-0809-static-prerequisites-v1.json")
LOCKFILE = Path("uv.lock")
HARNESS = Path("scripts/mesc_mrl_0809_runtime_feasibility.py")
MRL0801_AUTH = Path("specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json")
STORAGE_MARGIN_BYTES: Final = 10 * 1024 * 1024 * 1024
METADATA_ALLOW_PATTERNS: Final[tuple[str, ...]] = (
    "config.json",
    "generation_config.json",
    "tokenizer*",
    "processor*",
    "preprocessor*",
    "special_tokens_map.json",
    "chat_template*",
    "merges.txt",
    "vocab.*",
    "*.tiktoken",
)

EXPECTED_PACKAGES: Final[dict[str, str]] = {
    "accelerate": "1.14.0",
    "bitsandbytes": "0.50.2",
    "huggingface-hub": "1.23.0",
    "torch": "2.13.0",
    "transformers": "5.16.1",
    "xgrammar": "0.2.7",
}
EXPECTED_CANDIDATES: Final[dict[str, dict[str, object]]] = {
    "Qwen/Qwen3.8-27B": {
        "architecture": "Qwen3_5ForConditionalGeneration",
        "artifact_identity_sha256": (
            "47fa40e84d8f5d5b3be87e40e2abe45ed8c6141f03c4c29b51dd2fbeffd4d227"
        ),
        "config_sha256": "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab",
        "processor_config_sha256": (
            "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
        ),
        "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
        "text_vocab_size": 248320,
        "weights_sha256": "27c470ae6cfe721b205e468b9449fe86cfbf8fd7777772b7011f419887e345c3",
        "tokenizer_config_sha256": (
            "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27"
        ),
    },
    "google/gemma-4-31B-it": {
        "architecture": "Gemma4ForConditionalGeneration",
        "artifact_identity_sha256": (
            "85b8e3fedd5423bdf1c01c9d451c8702ace1e42c447f1608e94c855e17d052f9"
        ),
        "config_sha256": "e967dd38bc5cfd38bd09a995a7bf4a754075df2b46aba68f7fbb5a791e6d8dd1",
        "processor_config_sha256": (
            "32bdf45d2ad4cc29a0822ddd157a182de76644f0419a6228d151495256e9813c"
        ),
        "revision": "842da3794eaa0b77d5f08bae87a17459d91ff475",
        "text_vocab_size": 262144,
        "weights_sha256": "bca2cd08fe0ba249c668a6ce576612c26c49f38b15b63c1774138dd6fc31d537",
        "tokenizer_config_sha256": (
            "9f4fec4b1dc6ecddf8f4a92e9caea5971c0e67d81309f3f9066a2bee8c362633"
        ),
    },
}

MRL0804_EVIDENCE: Final = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
MRL0804_RUNTIME: Final = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
MRL0808_EVIDENCE: Final = "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"
SANDBOX_POLICY: Final = "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"


class HarnessError(RuntimeError):
    """Fail-closed MRL-0809 harness error."""


def _reject_constant(value: str) -> Never:
    raise HarnessError(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise HarnessError(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _normalize_canonical(value: object) -> object:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is str:
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise HarnessError("canonical JSON string is not valid UTF-8") from exc
        return value
    if isinstance(value, float):
        raise HarnessError("floating-point values are prohibited in canonical JSON")
    if isinstance(value, Mapping):
        snapshot = list(value.items())
        if any(type(key) is not str for key, _ in snapshot):
            raise HarnessError("canonical JSON object keys must be exact strings")
        return {
            cast(str, key): _normalize_canonical(item)
            for key, item in sorted(snapshot, key=lambda pair: cast(str, pair[0]))
        }
    if isinstance(value, list | tuple):
        return [_normalize_canonical(item) for item in value]
    raise HarnessError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    normalized = _normalize_canonical(value)
    try:
        text = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise HarnessError("value is not canonical-JSON serializable") from exc
    return text.encode("utf-8") + b"\n"


def parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, HarnessError) as exc:
        raise HarnessError(f"{label} is invalid JSON") from exc
    if type(parsed) is not dict:
        raise HarnessError(f"{label} must be an object")
    document = cast(dict[str, object], parsed)
    if canonical_json_bytes(document) != raw:
        raise HarnessError(f"{label} is not canonical JSON")
    return document


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise HarnessError(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def _git_bytes(root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise HarnessError(f"git {' '.join(args)} failed")
    return completed.stdout


def _require_repository(root: Path) -> tuple[str, str]:
    root = root.resolve(strict=True)
    head = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}")
    origin = _git(root, "rev-parse", "origin/main")
    live = _git(root, "ls-remote", "origin", "refs/heads/main").split("\t")[0]
    if (
        SHA40.fullmatch(head) is None
        or SHA40.fullmatch(tree) is None
        or head != origin
        or head != live
    ):
        raise HarnessError("qualification requires exact live canonical main")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise HarnessError("repository must have no tracked or untracked changes")
    for relative in (STATIC_MANIFEST, LOCKFILE, HARNESS, MRL0801_AUTH):
        path = root / relative
        if not path.is_file():
            raise HarnessError(f"required repository file missing: {relative.as_posix()}")
        if path.read_bytes() != _git_bytes(root, "show", f"HEAD:{relative.as_posix()}"):
            raise HarnessError(f"required repository file differs from HEAD: {relative.as_posix()}")
    return head, tree


def _require_outside_repository(path: Path, root: Path, *, label: str) -> Path:
    root = root.resolve(strict=True)
    if path.exists():
        resolved = path.resolve(strict=True)
    else:
        resolved = path.parent.resolve(strict=True) / path.name
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise HarnessError(f"{label} must be outside the repository")


def _mrl0801_weight_allowlist(root: Path, candidate: str) -> tuple[str, ...]:
    raw = (root / MRL0801_AUTH).read_bytes()
    authorization = parse_canonical_object(raw, label="MRL-0801 acquisition authorization")
    rows = authorization.get("candidates")
    if type(rows) is not list:
        raise HarnessError("MRL-0801 candidate authorization is malformed")
    expected_revision = EXPECTED_CANDIDATES[candidate]["revision"]
    for item in cast(list[object], rows):
        if type(item) is not dict:
            raise HarnessError("MRL-0801 candidate authorization row is malformed")
        row = cast(dict[str, object], item)
        if row.get("model_id") != candidate:
            continue
        if row.get("revision") != expected_revision:
            raise HarnessError("MRL-0801 authorization revision drifted")
        allowed = row.get("allowed_files")
        if type(allowed) is not list or not allowed:
            raise HarnessError("MRL-0801 weight allowlist is missing")
        result = tuple(cast(str, item) for item in allowed)
        if any(
            type(item) is not str
            or not item
            or "/" in item
            or not (item.endswith(".safetensors") or item == "model.safetensors.index.json")
            for item in allowed
        ):
            raise HarnessError("MRL-0801 weight allowlist contains an unsafe path")
        if len(result) != len(set(result)):
            raise HarnessError("MRL-0801 weight allowlist contains duplicates")
        return result
    raise HarnessError("candidate is absent from MRL-0801 authorization")


def _payload_files(snapshot: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and ".cache" not in path.relative_to(snapshot).parts
    )


def _remote_capacity_preflight(
    *,
    hub: Any,
    root: Path,
    candidate: str,
    destination_parent: Path,
) -> tuple[tuple[str, ...], int]:
    revision = cast(str, EXPECTED_CANDIDATES[candidate]["revision"])
    weight_files = _mrl0801_weight_allowlist(root, candidate)
    patterns = tuple(sorted(set(weight_files) | set(METADATA_ALLOW_PATTERNS)))
    try:
        info: Any = hub.model_info(candidate, revision=revision, files_metadata=True)
    except Exception as exc:
        raise HarnessError(f"remote file manifest lookup failed for {candidate}") from exc
    siblings: Any = getattr(info, "siblings", None)
    if not isinstance(siblings, list):
        raise HarnessError("remote file manifest did not expose siblings")
    selected: dict[str, int] = {}
    for sibling in siblings:
        name = getattr(sibling, "rfilename", None)
        size = getattr(sibling, "size", None)
        if type(name) is not str:
            raise HarnessError("remote file manifest contains an invalid filename")
        if "/" in name or not any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns):
            continue
        if type(size) is not int or size <= 0:
            raise HarnessError(f"remote file size is unavailable for {name}")
        selected[name] = size
    missing_weights = sorted(set(weight_files) - set(selected))
    if missing_weights:
        raise HarnessError(f"remote revision is missing authorized weights: {missing_weights[0]}")
    for required in ("config.json", "tokenizer_config.json", "processor_config.json"):
        if required not in selected:
            raise HarnessError(f"remote revision is missing required metadata: {required}")
    selected_total = sum(selected.values())
    margin = max(STORAGE_MARGIN_BYTES, (selected_total + 9) // 10)
    available = shutil.disk_usage(destination_parent).free
    if available < selected_total + margin:
        raise HarnessError("insufficient free storage for bounded candidate staging")
    return tuple(sorted(selected)), selected_total


def _metadata_digests(snapshot: Path) -> dict[str, str]:
    expected_files = {
        "config_sha256": snapshot / "config.json",
        "tokenizer_config_sha256": snapshot / "tokenizer_config.json",
        "processor_config_sha256": snapshot / "processor_config.json",
    }
    digests: dict[str, str] = {}
    for field, path in expected_files.items():
        if not path.is_file():
            raise HarnessError(f"staged snapshot missing {path.name}")
        digests[field] = sha256_file(path)
    return digests


def _validate_snapshot(candidate: str, snapshot: Path) -> tuple[dict[str, str], int, int]:
    snapshot = snapshot.resolve(strict=True)
    expected = EXPECTED_CANDIDATES[candidate]
    digests = _metadata_digests(snapshot)
    for field, actual in digests.items():
        if actual != expected[field]:
            raise HarnessError(f"{candidate} {field} drifted")
    weights = tuple(sorted(snapshot.rglob("*.safetensors")))
    if not weights:
        raise HarnessError(f"{candidate} snapshot has no safetensors weights")
    payload_files = _payload_files(snapshot)
    file_count = len(payload_files)
    total_bytes = sum(path.stat().st_size for path in payload_files)
    if file_count <= 0 or total_bytes <= 0:
        raise HarnessError(f"{candidate} staged snapshot is empty")
    return digests, file_count, total_bytes


def _validate_weight_identity(
    candidate: str, snapshot: Path
) -> tuple[str, str, list[dict[str, object]]]:
    expected = EXPECTED_CANDIDATES[candidate]
    try:
        identity_module: Any = importlib.import_module(
            "medscale.mesc._training_hf_safetensors_identity_v1"
        )
        identity: Any = identity_module.identify_hf_safetensors_artifact(
            model_root=snapshot,
            model_id=candidate,
            revision=cast(str, expected["revision"]),
        )
    except Exception as exc:
        raise HarnessError(f"{candidate} SafeTensors identity verification failed") from exc
    weights_sha256 = cast(str, identity.weights_sha256)
    artifact_identity_sha256 = cast(str, identity.verifier_receipt_sha256)
    if weights_sha256 != expected["weights_sha256"]:
        raise HarnessError(f"{candidate} weights_sha256 drifted from MRL-0801")
    if artifact_identity_sha256 != expected["artifact_identity_sha256"]:
        raise HarnessError(f"{candidate} artifact identity drifted from MRL-0801")
    file_manifest = [cast(dict[str, object], item.to_dict()) for item in identity.files]
    return weights_sha256, artifact_identity_sha256, file_manifest


def stage_candidate(
    root: Path,
    candidate: str,
    destination: Path,
    receipt_path: Path,
) -> None:
    if candidate not in EXPECTED_CANDIDATES:
        raise HarnessError("candidate is outside the frozen roster")
    root = root.resolve(strict=True)
    _require_repository(root)
    _require_colab_identity()
    destination = _require_outside_repository(destination, root, label="staging destination")
    receipt_path = _require_outside_repository(receipt_path, root, label="stage receipt")
    if destination.exists():
        if not destination.is_dir():
            raise HarnessError("staging destination must be a directory")
        if any(destination.iterdir()):
            raise HarnessError("staging destination must be absent or empty")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        hub: Any = importlib.import_module("huggingface_hub")
    except Exception as exc:
        raise HarnessError("huggingface_hub is unavailable") from exc
    revision = cast(str, EXPECTED_CANDIDATES[candidate]["revision"])
    selected_files, remote_selected_bytes = _remote_capacity_preflight(
        hub=hub,
        root=root,
        candidate=candidate,
        destination_parent=destination.parent,
    )
    try:
        hub.snapshot_download(
            repo_id=candidate,
            revision=revision,
            local_dir=str(destination),
            allow_patterns=list(selected_files),
        )
    except Exception as exc:
        raise HarnessError(f"exact candidate staging failed for {candidate}") from exc
    digests, file_count, total_bytes = _validate_snapshot(candidate, destination)
    weights_sha256, artifact_identity_sha256, weight_files = _validate_weight_identity(
        candidate, destination
    )
    receipt = {
        "artifact_identity_sha256": artifact_identity_sha256,
        "config_sha256": digests["config_sha256"],
        "model_id": candidate,
        "processor_config_sha256": digests["processor_config_sha256"],
        "mrl_0801_authorization_sha256": sha256_file(root / MRL0801_AUTH),
        "remote_selected_bytes": remote_selected_bytes,
        "remote_selected_files": list(selected_files),
        "revision": revision,
        "schema_version": SCHEMA_STAGE,
        "snapshot_file_count": file_count,
        "snapshot_total_bytes": total_bytes,
        "tokenizer_config_sha256": digests["tokenizer_config_sha256"],
        "weight_files": weight_files,
        "weights_sha256": weights_sha256,
    }
    write_new(receipt_path, canonical_json_bytes(receipt))


def _read_stage_receipt(
    candidate: str, snapshot: Path, path: Path, *, root: Path
) -> tuple[dict[str, object], str]:
    raw = path.read_bytes()
    receipt = parse_canonical_object(raw, label="stage receipt")
    expected_keys = {
        "artifact_identity_sha256",
        "config_sha256",
        "model_id",
        "mrl_0801_authorization_sha256",
        "processor_config_sha256",
        "remote_selected_bytes",
        "remote_selected_files",
        "revision",
        "schema_version",
        "snapshot_file_count",
        "snapshot_total_bytes",
        "tokenizer_config_sha256",
        "weight_files",
        "weights_sha256",
    }
    if set(receipt) != expected_keys or receipt["schema_version"] != SCHEMA_STAGE:
        raise HarnessError("stage receipt schema drifted")
    expected = EXPECTED_CANDIDATES[candidate]
    if receipt["model_id"] != candidate or receipt["revision"] != expected["revision"]:
        raise HarnessError("stage receipt candidate identity drifted")
    if receipt["mrl_0801_authorization_sha256"] != sha256_file(root / MRL0801_AUTH):
        raise HarnessError("stage receipt MRL-0801 authorization identity drifted")
    if type(receipt["remote_selected_bytes"]) is not int or receipt["remote_selected_bytes"] <= 0:
        raise HarnessError("stage receipt remote byte total is invalid")
    remote_files = receipt["remote_selected_files"]
    if type(remote_files) is not list or not remote_files:
        raise HarnessError("stage receipt remote selected files are invalid")
    remote_file_names = tuple(cast(str, item) for item in cast(list[object], remote_files))
    if (
        any(
            type(item) is not str or not item or "/" in item
            for item in cast(list[object], remote_files)
        )
        or remote_file_names != tuple(sorted(remote_file_names))
        or len(remote_file_names) != len(set(remote_file_names))
    ):
        raise HarnessError("stage receipt remote selected files are not canonical")
    if not set(_mrl0801_weight_allowlist(root, candidate)) <= set(remote_file_names):
        raise HarnessError("stage receipt omitted an MRL-0801 weight file")
    digests, file_count, total_bytes = _validate_snapshot(candidate, snapshot)
    if (
        receipt["snapshot_file_count"] != file_count
        or receipt["snapshot_total_bytes"] != total_bytes
    ):
        raise HarnessError("stage receipt snapshot size/count drifted")
    for field, actual in digests.items():
        if receipt[field] != actual:
            raise HarnessError(f"stage receipt {field} drifted")
    weights_sha256, artifact_identity_sha256, weight_files = _validate_weight_identity(
        candidate, snapshot
    )
    if receipt["weights_sha256"] != weights_sha256:
        raise HarnessError("stage receipt weights_sha256 drifted")
    if receipt["artifact_identity_sha256"] != artifact_identity_sha256:
        raise HarnessError("stage receipt artifact identity drifted")
    if receipt["weight_files"] != weight_files:
        raise HarnessError("stage receipt SafeTensors file manifest drifted")
    return receipt, sha256_bytes(raw)


def _nvidia_nodes() -> tuple[Path, ...]:
    nodes: list[Path] = []
    for candidate in sorted(Path("/dev").glob("nvidia*")):
        candidates = candidate.rglob("*") if candidate.is_dir() else (candidate,)
        for path in candidates:
            try:
                mode = path.stat().st_mode
            except OSError:
                continue
            if stat.S_ISCHR(mode):
                nodes.append(path)
    unique = tuple(sorted(set(nodes), key=str))
    if not unique:
        raise HarnessError("no NVIDIA character devices are visible")
    return unique


def _python_layout(python_executable: Path) -> tuple[Path, Path, str]:
    completed = subprocess.run(
        [
            str(python_executable),
            "-c",
            (
                "import json,site,sys;"
                "print(json.dumps({'base_prefix':sys.base_prefix,"
                "'site':site.getsitepackages()[0],'version':sys.version.split()[0]}))"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise HarnessError("qualification Python introspection failed")
    document = json.loads(completed.stdout)
    base = Path(document["base_prefix"]).resolve(strict=True)
    site_packages = Path(document["site"]).resolve(strict=True)
    version = str(document["version"])
    if not version.startswith("3.11."):
        raise HarnessError("MRL-0809 qualification Python must be CPython 3.11.x")
    return base, site_packages, version


def _gpu_context() -> tuple[str, str, int]:
    completed = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=name,uuid,memory.total",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise HarnessError("nvidia-smi is unavailable")
    rows = [row.strip() for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise HarnessError("exactly one GPU is required")
    parts = [item.strip() for item in rows[0].split(",")]
    if len(parts) != 3:
        raise HarnessError("GPU observation is malformed")
    name, uuid, memory_mib_text = parts
    if name != GPU_MODEL:
        raise HarnessError(f"frozen hosted GPU must be exactly {GPU_MODEL}")
    try:
        memory_mib = int(memory_mib_text)
    except ValueError as exc:
        raise HarnessError("GPU VRAM observation is not an integer") from exc
    if memory_mib <= 0:
        raise HarnessError("GPU VRAM must be positive")
    return name, uuid, memory_mib * 1024 * 1024


def _require_colab_identity() -> tuple[str, str, str, str, int]:
    if platform.system() != "Linux":
        raise HarnessError("MRL-0809 hosted qualification requires Linux")
    if os.environ.get("MESC_MRL0809_ZERO_COST_ATTESTATION") != "1":
        raise HarnessError("zero-cost operator attestation is missing")
    provider_execution_id = os.environ.get("MESC_COLAB_RUNTIME_ID", "").strip()
    colab_release_tag = os.environ.get("COLAB_RELEASE_TAG", "").strip()
    if not provider_execution_id or "\x00" in provider_execution_id:
        raise HarnessError("independently obtained Colab runtime identity is missing")
    if not colab_release_tag or "\x00" in colab_release_tag:
        raise HarnessError("Colab release identity is missing")
    gpu_model, gpu_uuid, gpu_vram_bytes = _gpu_context()
    return (
        provider_execution_id,
        colab_release_tag,
        gpu_model,
        gpu_uuid,
        gpu_vram_bytes,
    )


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package, expected in EXPECTED_PACKAGES.items():
        try:
            actual = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise HarnessError(f"required package missing: {package}") from exc
        if actual != expected:
            raise HarnessError(f"{package} must be exactly {expected}, got {actual}")
        versions[package] = actual
    return versions


def _runtime_symlink_args() -> list[str]:
    args: list[str] = []
    for destination in (Path("/bin"), Path("/sbin"), Path("/lib"), Path("/lib64")):
        if destination.is_symlink():
            args.extend(["--symlink", str(destination.readlink()), str(destination)])
        elif destination.exists() and destination.is_dir():
            args.extend(["--ro-bind", str(destination), str(destination)])
    return args


def _sandbox_prefix(
    *,
    bwrap: Path,
    harness: Path,
    snapshot: Path,
    base_prefix: Path,
    site_packages: Path,
    nvidia_nodes: tuple[Path, ...],
) -> list[str]:
    runtime_links = _runtime_symlink_args()
    args = [
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        *runtime_links,
        "--ro-bind",
        "/sys",
        "/sys",
        "--dir",
        "/etc",
        "--ro-bind",
        "/etc/ld.so.cache",
        "/etc/ld.so.cache",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
    ]
    for node in nvidia_nodes:
        args.extend(["--dev-bind", str(node), str(node)])
    args.extend(
        [
            "--dir",
            "/mesc-run",
            "--ro-bind",
            str(harness),
            "/mesc-run/harness.py",
            "--ro-bind",
            str(snapshot),
            "/mesc-run/model-weights",
            "--ro-bind",
            str(base_prefix),
            "/mesc-run/python-base",
            "--ro-bind",
            str(site_packages),
            "/mesc-run/site-packages",
            "--tmpfs",
            "/tmp",
            "--remount-ro",
            "/dev",
            "--chdir",
            "/mesc-run",
        ]
    )
    return args


def _run_worker(
    *,
    candidate: str,
    prefix: list[str],
    python_version: str,
) -> dict[str, object]:
    python_binary = f"/mesc-run/python-base/bin/python{'.'.join(python_version.split('.')[:2])}"
    command = prefix.copy()
    environment = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HOME": "/tmp/hf",
        "XDG_CACHE_HOME": "/tmp",
        "PYTHONPATH": "/mesc-run/site-packages",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    for key, value in environment.items():
        command.extend(["--setenv", key, value])
    command.extend(
        [
            python_binary,
            "/mesc-run/harness.py",
            "_worker",
            "--candidate",
            candidate,
            "--snapshot",
            "/mesc-run/model-weights",
        ]
    )
    completed = subprocess.run(command, check=False, capture_output=True)
    if completed.returncode != 0:
        stderr = completed.stderr.decode("utf-8", "replace")[-6000:]
        raise HarnessError(f"isolated candidate probe failed: {stderr}")
    return parse_canonical_object(completed.stdout, label="isolated worker observation")


def _runtime_identity(
    *,
    bwrap_sha256: str,
    bwrap_version: str,
    colab_release_tag: str,
    gpu_model: str,
    gpu_uuid: str,
    gpu_vram_bytes: int,
    kernel_release: str,
    package_versions: dict[str, str],
    provider_execution_id: str,
    python_version: str,
    harness_sha256: str,
) -> tuple[dict[str, object], str]:
    identity = {
        "bubblewrap_sha256": bwrap_sha256,
        "bubblewrap_version": bwrap_version,
        "colab_release_tag": colab_release_tag,
        "compute_dtype": "float16",
        "gpu_model": gpu_model,
        "gpu_uuid": gpu_uuid,
        "gpu_vram_bytes": gpu_vram_bytes,
        "harness_sha256": harness_sha256,
        "kernel_release": kernel_release,
        "package_versions": package_versions,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": provider_execution_id,
        "provider_owner": "GOOGLE",
        "python_version": python_version,
        "runtime_representation": RUNTIME_REPRESENTATION,
    }
    return identity, sha256_bytes(canonical_json_bytes(identity))


def probe_candidate(
    *,
    root: Path,
    candidate: str,
    snapshot: Path,
    stage_receipt: Path,
    observation_out: Path,
    python_executable: Path,
) -> None:
    if candidate not in EXPECTED_CANDIDATES:
        raise HarnessError("candidate is outside the frozen roster")
    root = root.resolve(strict=True)
    (
        provider_execution_id,
        colab_release_tag,
        gpu_model,
        gpu_uuid,
        gpu_vram_bytes,
    ) = _require_colab_identity()
    head, tree = _require_repository(root)
    snapshot = _require_outside_repository(snapshot, root, label="candidate snapshot").resolve(
        strict=True
    )
    stage_receipt = _require_outside_repository(stage_receipt, root, label="stage receipt")
    observation_out = _require_outside_repository(
        observation_out, root, label="candidate observation"
    )
    stage_document, stage_receipt_sha256 = _read_stage_receipt(
        candidate, snapshot, stage_receipt, root=root
    )
    bwrap_raw = shutil.which("bwrap")
    if bwrap_raw is None:
        raise HarnessError("bubblewrap is required before Stage 4")
    bwrap = Path(bwrap_raw).resolve(strict=True)
    bwrap_version = subprocess.check_output([str(bwrap), "--version"], text=True).strip()
    base_prefix, site_packages, python_version = _python_layout(python_executable)
    package_versions = _package_versions()
    nodes = _nvidia_nodes()
    prefix = _sandbox_prefix(
        bwrap=bwrap,
        harness=(root / HARNESS).resolve(strict=True),
        snapshot=snapshot,
        base_prefix=base_prefix,
        site_packages=site_packages,
        nvidia_nodes=nodes,
    )
    worker = _run_worker(candidate=candidate, prefix=prefix, python_version=python_version)
    if worker.get("schema_version") != SCHEMA_WORKER or worker.get("model_id") != candidate:
        raise HarnessError("isolated worker identity drifted")
    identity, runtime_identity_sha256 = _runtime_identity(
        bwrap_sha256=sha256_file(bwrap),
        bwrap_version=bwrap_version,
        colab_release_tag=colab_release_tag,
        gpu_model=gpu_model,
        gpu_uuid=gpu_uuid,
        gpu_vram_bytes=gpu_vram_bytes,
        kernel_release=platform.release(),
        package_versions=package_versions,
        provider_execution_id=provider_execution_id,
        python_version=python_version,
        harness_sha256=sha256_file(root / HARNESS),
    )
    observation = {
        "candidate": worker["candidate"],
        "generation_evidence": worker["generation_evidence"],
        "provider_execution_id": provider_execution_id,
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_identity": identity,
        "runtime_identity_sha256": runtime_identity_sha256,
        "schema_version": SCHEMA_OBSERVATION,
        "stage_artifact_identity_sha256": stage_document["artifact_identity_sha256"],
        "stage_receipt_sha256": stage_receipt_sha256,
        "stage_weights_sha256": stage_document["weights_sha256"],
        "static_prerequisite_manifest_sha256": sha256_file(root / STATIC_MANIFEST),
        "dependency_lock_sha256": sha256_file(root / LOCKFILE),
    }
    write_new(observation_out, canonical_json_bytes(observation))


def _worker(candidate: str, snapshot: Path) -> None:
    if candidate not in EXPECTED_CANDIDATES:
        raise HarnessError("worker candidate is outside the frozen roster")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise HarnessError("worker offline policy is missing")
    expected = EXPECTED_CANDIDATES[candidate]
    digests, _, _ = _validate_snapshot(candidate, snapshot)
    versions = _package_versions()
    try:
        resource_module: Any = importlib.import_module("resource")
        torch: Any = importlib.import_module("torch")
        transformers: Any = importlib.import_module("transformers")
        auto_processor: Any = transformers.AutoProcessor
        auto_tokenizer: Any = transformers.AutoTokenizer
        bitsandbytes_config: Any = transformers.BitsAndBytesConfig
    except Exception as exc:
        raise HarnessError("frozen runtime packages failed to import") from exc
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise HarnessError("worker requires exactly one CUDA GPU")
    architecture = cast(str, expected["architecture"])
    model_class = getattr(transformers, architecture, None)
    if model_class is None:
        raise HarnessError(f"transformers does not expose {architecture}")
    baseline_gpu = int(torch.cuda.memory_allocated())
    torch.cuda.reset_peak_memory_stats()
    tokenizer: Any = None
    processor: Any = None
    model: Any = None
    encoded: Any = None
    output: Any = None
    generated_ids: list[int] = []
    decoded_hash = ""
    peak_gpu = 0
    peak_cpu = 0
    try:
        tokenizer = auto_tokenizer.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
        )
        processor = auto_processor.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
        )
        quantization = bitsandbytes_config(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        model = model_class.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            device_map={"": 0},
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
        torch.cuda.synchronize()
        device_map = getattr(model, "hf_device_map", None)
        if type(device_map) is not dict or not device_map:
            raise HarnessError("loaded model did not expose an auditable device map")
        for target in device_map.values():
            if target not in (0, "cuda", "cuda:0"):
                raise HarnessError("capacity fallback/offload is prohibited")
        if model.__class__.__name__ != architecture:
            raise HarnessError("loaded model architecture drifted from frozen identity")
        if model.training:
            raise HarnessError("runtime-feasibility model must remain in eval mode")
        encoded = tokenizer(SYNTHETIC_PROMPT, return_tensors="pt")
        encoded = {key: value.to(torch.device("cuda:0")) for key, value in encoded.items()}
        with torch.inference_mode():
            output = model.generate(
                **encoded,
                do_sample=False,
                num_beams=1,
                max_new_tokens=MAX_NEW_TOKENS,
            )
        input_length = int(encoded["input_ids"].shape[-1])
        generated_ids = [int(token) for token in output[0][input_length:].detach().cpu().tolist()]
        if not generated_ids:
            raise HarnessError("synthetic generation produced no new tokens")
        decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
        if not decoded.strip():
            raise HarnessError("synthetic generation decoded to empty text")
        torch.cuda.synchronize()
        decoded_hash = sha256_bytes(decoded.encode("utf-8"))
        peak_gpu = int(torch.cuda.max_memory_allocated())
        peak_cpu = int(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss) * 1024
        if peak_gpu <= 0 or peak_cpu <= 0:
            raise HarnessError("candidate memory observations must be positive")
    finally:
        del output, encoded, model, processor, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    residual_gpu = int(torch.cuda.memory_allocated())
    unloaded = residual_gpu <= baseline_gpu + (64 * 1024 * 1024)
    if not unloaded:
        raise HarnessError("GPU allocations did not return to the bounded cleanup envelope")
    generation_evidence = {
        "decoded_text_sha256": decoded_hash,
        "generated_token_ids": generated_ids,
        "synthetic_prompt_sha256": sha256_bytes(SYNTHETIC_PROMPT.encode("utf-8")),
    }
    generation_sha256 = sha256_bytes(canonical_json_bytes(generation_evidence))
    candidate_receipt = {
        "architecture": architecture,
        "config_sha256": digests["config_sha256"],
        "load_completed": True,
        "model_id": candidate,
        "peak_cpu_memory_bytes": peak_cpu,
        "peak_gpu_memory_bytes": peak_gpu,
        "processor_config_sha256": digests["processor_config_sha256"],
        "revision": expected["revision"],
        "runtime_representation": RUNTIME_REPRESENTATION,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": generation_sha256,
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": digests["tokenizer_config_sha256"],
        "unloaded_after_probe": True,
    }
    worker = {
        "candidate": candidate_receipt,
        "generation_evidence": generation_evidence,
        "model_id": candidate,
        "package_versions": versions,
        "schema_version": SCHEMA_WORKER,
    }
    sys.stdout.buffer.write(canonical_json_bytes(worker))
    sys.stdout.buffer.flush()


def _validated_observation(path: Path) -> dict[str, object]:
    document = parse_canonical_object(path.read_bytes(), label="candidate observation")
    expected_keys = {
        "candidate",
        "dependency_lock_sha256",
        "generation_evidence",
        "provider_execution_id",
        "repository_sha",
        "repository_tree",
        "runtime_identity",
        "runtime_identity_sha256",
        "schema_version",
        "stage_artifact_identity_sha256",
        "stage_receipt_sha256",
        "stage_weights_sha256",
        "static_prerequisite_manifest_sha256",
    }
    if set(document) != expected_keys or document["schema_version"] != SCHEMA_OBSERVATION:
        raise HarnessError("candidate observation schema drifted")
    stage_sha = document["stage_receipt_sha256"]
    if type(stage_sha) is not str or SHA64.fullmatch(stage_sha) is None:
        raise HarnessError("candidate observation stage receipt digest is invalid")
    candidate = cast(dict[str, object], document["candidate"])
    model_id = cast(str, candidate.get("model_id"))
    expected = EXPECTED_CANDIDATES.get(model_id)
    if expected is None:
        raise HarnessError("candidate observation is outside the frozen roster")
    if document["stage_weights_sha256"] != expected["weights_sha256"]:
        raise HarnessError("candidate observation weights identity drifted")
    if document["stage_artifact_identity_sha256"] != expected["artifact_identity_sha256"]:
        raise HarnessError("candidate observation artifact identity drifted")
    generation = cast(dict[str, object], document["generation_evidence"])
    if candidate["synthetic_generation_sha256"] != sha256_bytes(canonical_json_bytes(generation)):
        raise HarnessError("candidate synthetic generation evidence digest drifted")
    return document


def assemble_receipt(root: Path, observations: list[Path], output: Path) -> None:
    root = root.resolve(strict=True)
    if len(observations) != 2:
        raise HarnessError("exactly two candidate observations are required")
    head, tree = _require_repository(root)
    observation_paths = [
        _require_outside_repository(path, root, label="candidate observation")
        for path in observations
    ]
    output = _require_outside_repository(output, root, label="runtime-feasibility receipt")
    documents = [_validated_observation(path) for path in observation_paths]
    candidates = [cast(dict[str, object], document["candidate"]) for document in documents]
    model_ids = tuple(sorted(cast(str, row["model_id"]) for row in candidates))
    if model_ids != tuple(sorted(EXPECTED_CANDIDATES)):
        raise HarnessError("observations do not contain the exact frozen candidate roster")
    shared_fields = (
        "dependency_lock_sha256",
        "provider_execution_id",
        "repository_sha",
        "repository_tree",
        "runtime_identity_sha256",
        "static_prerequisite_manifest_sha256",
    )
    for field in shared_fields:
        values = {cast(str, document[field]) for document in documents}
        if len(values) != 1:
            raise HarnessError(f"candidate observations disagree on {field}")
    first = documents[0]
    if first["repository_sha"] != head or first["repository_tree"] != tree:
        raise HarnessError("candidate observations are stale relative to canonical main")
    if first["static_prerequisite_manifest_sha256"] != sha256_file(root / STATIC_MANIFEST):
        raise HarnessError("candidate observations bind a stale static prerequisite manifest")
    if first["dependency_lock_sha256"] != sha256_file(root / LOCKFILE):
        raise HarnessError("candidate observations bind a stale dependency lock")
    identities = [cast(dict[str, object], document["runtime_identity"]) for document in documents]
    if canonical_json_bytes(identities[0]) != canonical_json_bytes(identities[1]):
        raise HarnessError("candidate observations were not produced in one identical runtime")
    identity = identities[0]
    if sha256_bytes(canonical_json_bytes(identity)) != first["runtime_identity_sha256"]:
        raise HarnessError("runtime identity digest drifted")
    if identity["gpu_model"] != GPU_MODEL or identity["provider"] != "GOOGLE_COLAB":
        raise HarnessError("runtime identity is outside the frozen hosted class")
    receipt = {
        "candidate_substitution_performed": False,
        "candidates": sorted(candidates, key=lambda row: cast(str, row["model_id"])),
        "capacity_fallback_performed": False,
        "cleanup_completed": True,
        "compute_dtype": "float16",
        "dependency_lock_sha256": first["dependency_lock_sha256"],
        "disposition": "PASS",
        "gpu_model": identity["gpu_model"],
        "gpu_vram_bytes": identity["gpu_vram_bytes"],
        "local_files_only_during_isolated_execution": True,
        "monetary_cost_microunits": 0,
        "mrl_0804_evidence_sha256": MRL0804_EVIDENCE,
        "mrl_0804_runtime_identity_sha256": MRL0804_RUNTIME,
        "mrl_0808_evidence_sha256": MRL0808_EVIDENCE,
        "network_access_during_isolated_generation": False,
        "network_access_during_isolated_load": False,
        "optimizer_present": False,
        "persistent_weight_writeback": False,
        "processor_policy": PROCESSOR_POLICY,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": first["provider_execution_id"],
        "provider_owner": "GOOGLE",
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_identity_sha256": first["runtime_identity_sha256"],
        "sandbox_policy_sha256": SANDBOX_POLICY,
        "schema_version": SCHEMA_RECEIPT,
        "static_prerequisite_manifest_sha256": first["static_prerequisite_manifest_sha256"],
        "training_performed": False,
        "trust_remote_code": False,
        "weight_mutation_performed": False,
    }
    raw = canonical_json_bytes(receipt)
    sys.path.insert(0, str((root / "src").resolve()))
    validator = importlib.import_module("medscale.mesc._mrl_0809_runtime_feasibility_v1")
    validated = validator.validate_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256=sha256_file(root / STATIC_MANIFEST),
        expected_dependency_lock_sha256=sha256_file(root / LOCKFILE),
        expected_repository_sha=head,
        expected_repository_tree=tree,
    )
    if validated.receipt_sha256 != sha256_bytes(raw):
        raise HarnessError("canonical validator receipt digest mismatch")
    write_new(output, raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    stage = sub.add_parser("stage")
    stage.add_argument("--repository-root", type=Path, required=True)
    stage.add_argument("--candidate", choices=sorted(EXPECTED_CANDIDATES), required=True)
    stage.add_argument("--destination", type=Path, required=True)
    stage.add_argument("--receipt-out", type=Path, required=True)

    probe = sub.add_parser("probe")
    probe.add_argument("--repository-root", type=Path, required=True)
    probe.add_argument("--candidate", choices=sorted(EXPECTED_CANDIDATES), required=True)
    probe.add_argument("--snapshot", type=Path, required=True)
    probe.add_argument("--stage-receipt", type=Path, required=True)
    probe.add_argument("--observation-out", type=Path, required=True)
    probe.add_argument("--python-executable", type=Path, required=True)

    assemble = sub.add_parser("assemble")
    assemble.add_argument("--repository-root", type=Path, required=True)
    assemble.add_argument("--observation", type=Path, action="append", required=True)
    assemble.add_argument("--receipt-out", type=Path, required=True)

    worker = sub.add_parser("_worker")
    worker.add_argument("--candidate", choices=sorted(EXPECTED_CANDIDATES), required=True)
    worker.add_argument("--snapshot", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "stage":
        stage_candidate(
            args.repository_root,
            args.candidate,
            args.destination,
            args.receipt_out,
        )
        return
    if args.command == "probe":
        probe_candidate(
            root=args.repository_root,
            candidate=args.candidate,
            snapshot=args.snapshot,
            stage_receipt=args.stage_receipt,
            observation_out=args.observation_out,
            python_executable=args.python_executable,
        )
        return
    if args.command == "assemble":
        assemble_receipt(args.repository_root, args.observation, args.receipt_out)
        return
    if args.command == "_worker":
        _worker(args.candidate, args.snapshot)
        return
    raise HarnessError("unreachable command")


if __name__ == "__main__":
    main()
