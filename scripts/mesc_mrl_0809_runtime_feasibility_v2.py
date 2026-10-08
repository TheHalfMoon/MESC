#!/usr/bin/env python3
"""MRL-0809 successor (v2) bounded Google Colab runtime-feasibility harness.

This is the separately versioned successor of ``mesc_mrl_0809_runtime_feasibility.py``,
which stays byte-identical as the historical v1 harness. It is authorized by
FD-MRL-0809-SUCCESSOR-V2-1 for exactly one Stage-4 attempt after canonical merge and
fresh-main qualification of the successor contract.

The harness is intentionally non-scientific. It never reads the MESC scientific corpus or
sealed Tier-3 items. Model snapshots are staged before the isolated probe. Each frozen
successor candidate is then loaded and given one fixed synthetic chat-template prompt
inside a no-network bubblewrap sandbox. The final receipt is self-validated by the
canonical v2 repository validator before it can be emitted.
"""

from __future__ import annotations

import argparse
import errno
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
import struct
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Never, cast

SCHEMA_STAGE: Final = "MESC-MRL-0809-SUCCESSOR-STAGE-RECEIPT-V1"
SCHEMA_WORKER: Final = "MESC-MRL-0809-CANDIDATE-WORKER-V2"
SCHEMA_OBSERVATION: Final = "MESC-MRL-0809-CANDIDATE-OBSERVATION-V2"
SCHEMA_PROBE_START: Final = "MESC-MRL-0809-SUCCESSOR-PROBE-START-V1"
SCHEMA_RECEIPT: Final = "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V2"
SCHEMA_VERIFY: Final = "MESC-MRL-0809-INDEPENDENT-RECEIPT-VERIFICATION-V2"
RUNTIME_REPRESENTATION: Final = "bitsandbytes-nf4-v1"
AUTO_PROCESSOR: Final = "AUTO_PROCESSOR_EXACT_REVISION"
TOKENIZER_ONLY: Final = "TOKENIZER_ONLY_TEXT_MODEL"
PROMPT_CONSTRUCTION: Final = "CHAT_TEMPLATE_ADD_GENERATION_PROMPT"
MAX_PEAK_GPU_MEMORY_BYTES: Final = 12 * 1024**3
SYNTHETIC_PROMPT: Final = "Write one short sentence about a blue triangle."
MAX_NEW_TOKENS: Final = 12
PROC_TMPFS_BYTES: Final = 4_096
CUDA_DRIVER_LIBRARY_PATH: Final = "/usr/lib64-nvidia"
NVIDIA_VISIBLE_DEVICES_VALUE: Final = "all"
NVIDIA_DRIVER_CAPABILITIES_VALUE: Final = "compute,utility"
SANDBOX_UNSHARE_FLAGS: Final[tuple[str, ...]] = (
    "--unshare-user",
    "--unshare-net",
    "--unshare-ipc",
    "--unshare-uts",
    "--unshare-cgroup",
)
AUDIT_ARCH_X86_64: Final = 0xC000003E
X32_SYSCALL_BIT: Final = 0x40000000
HOST_PROCESS_SYSCALLS_X86_64: Final[tuple[int, ...]] = (
    62,  # kill
    101,  # ptrace
    129,  # rt_sigqueueinfo
    200,  # tkill
    234,  # tgkill
    297,  # rt_tgsigqueueinfo
    310,  # process_vm_readv
    311,  # process_vm_writev
    312,  # kcmp
    424,  # pidfd_send_signal
    434,  # pidfd_open
    438,  # pidfd_getfd
    440,  # process_madvise
    448,  # process_mrelease
)
GPU_MODEL: Final = "Tesla T4"
SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
SHA64: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)

STATIC_MANIFEST = Path("specs/mesc-experiment-0/mrl-0809-static-prerequisites-v2.json")
LOCKFILE = Path("uv.lock")
HARNESS = Path("scripts/mesc_mrl_0809_runtime_feasibility_v2.py")
ROSTER = Path("specs/mesc-experiment-0/candidate-roster-v2.json")
SUCCESSOR_AUTHORIZATION = Path("specs/mesc-experiment-0/mrl-0809-successor-v2-authorization.json")
V1_RECORD = Path("specs/mesc-experiment-0/mrl-0809-v1-infeasibility-record.json")
STAGING_CONTROL_RESERVE_BYTES: Final = 1 * 1024 * 1024 * 1024
STAGING_MAX_WORKERS: Final = 1
STAGING_POLICY_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-STAGING-POLICY-V1"
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
STAGE_RECEIPT_KEYS: Final = frozenset(
    {
        "artifact_identity_sha256",
        "config_sha256",
        "model_id",
        "candidate_roster_sha256",
        "payload_manifest",
        "processor_config_sha256",
        "remote_selected_bytes",
        "remote_selected_files",
        "revision",
        "schema_version",
        "staging_policy",
        "snapshot_file_count",
        "snapshot_total_bytes",
        "tokenizer_config_sha256",
        "weight_files",
        "weights_sha256",
    }
)

EXPECTED_PACKAGES: Final[dict[str, str]] = {
    "accelerate": "1.14.0",
    "bitsandbytes": "0.50.2",
    "huggingface-hub": "1.23.0",
    "pillow": "12.3.0",
    "torch": "2.13.0",
    "torchvision": "0.28.0",
    "transformers": "5.16.1",
    "xgrammar": "0.2.7",
}
EXPECTED_CANDIDATES: Final[dict[str, dict[str, object]]] = {
    "Qwen/Qwen3-8B": {
        "architecture": "Qwen3ForCausalLM",
        "artifact_identity_sha256": (
            "d427ce5eeab11a278a80dcbfce0bbf523baf0cf41e3ba6d6da64492feffc719d"
        ),
        "config_sha256": "f7c4eadfbbf522470667b797a3c89be2524832d2d599797248dc304fff447c30",
        "processor_config_sha256": None,
        "processor_metadata_filename": None,
        "processor_policy": TOKENIZER_ONLY,
        "prompt_token_ids_sha256": (
            "dff106287fb0d1c188e5d1c10b9a58a824c00179af4d040150163d82f71c9f44"
        ),
        "revision": "b968826d9c46dd6066d109eabc6255188de91218",
        "text_vocab_size": 151936,
        "weights_sha256": "74ddc11aa1c5f0a1aec4758eff603adce262a8fa2d847f032092e518ddcbe14b",
        "tokenizer_config_sha256": (
            "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101"
        ),
    },
    "google/gemma-4-12B-it": {
        "architecture": "Gemma4UnifiedForConditionalGeneration",
        "artifact_identity_sha256": (
            "2100e96da837dcd2ad98fbfad310cbf87e964065d8dbc9b8538466bd0dab1b22"
        ),
        "config_sha256": "478c46e8d2c52d5c2d85bf67e3b3e8c90e7c9d91086cee27e3c267907e936bd9",
        "processor_config_sha256": (
            "6b938e76555b3e9946890770e1abcd442a4718f34041a58e8139dc8ad34545c9"
        ),
        "processor_metadata_filename": "processor_config.json",
        "processor_policy": AUTO_PROCESSOR,
        "prompt_token_ids_sha256": (
            "0969c3e2c1147307a557c910a95cea00005eafa76587e3225d43308d2126682d"
        ),
        "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        "text_vocab_size": 262144,
        "weights_sha256": "b2baeebd544de7d2f27b442111de54e953589395991ea20f3aeb0fdc7194ddf5",
        "tokenizer_config_sha256": (
            "a62f4e85a47c0c136edaaa3a4f591fd6783717299a9def47e5ad03a49f6a5eb9"
        ),
    },
}

EXPECTED_SELECTED_PAYLOAD_BYTES: Final[dict[str, int]] = {
    "Qwen/Qwen3-8B": 16_397_431_693,
    "google/gemma-4-12B-it": 23_951_746_871,
}

CANDIDATE_ROSTER_SHA256: Final = "61351863e82aa9108c6325304e26b7ea4cb92f84a9fbbb5ef761c13f0a882de2"
SUCCESSOR_AUTHORIZATION_SHA256: Final = (
    "114aebbefa64499c8855e28eca650e09c68f926cb7da9beacfa47d364091ade6"
)
V1_INFEASIBILITY_RECORD_SHA256: Final = (
    "933de39a27a37a9b62d68db3d3a388805572c720f3db136a829d22354bd13ebe"
)
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
    for relative in (
        STATIC_MANIFEST,
        LOCKFILE,
        HARNESS,
        ROSTER,
        SUCCESSOR_AUTHORIZATION,
        V1_RECORD,
    ):
        path = root / relative
        if not path.is_file():
            raise HarnessError(f"required repository file missing: {relative.as_posix()}")
        if path.read_bytes() != _git_bytes(root, "show", f"HEAD:{relative.as_posix()}"):
            raise HarnessError(f"required repository file differs from HEAD: {relative.as_posix()}")
    for relative, expected in (
        (ROSTER, CANDIDATE_ROSTER_SHA256),
        (SUCCESSOR_AUTHORIZATION, SUCCESSOR_AUTHORIZATION_SHA256),
        (V1_RECORD, V1_INFEASIBILITY_RECORD_SHA256),
    ):
        if sha256_file(root / relative) != expected:
            raise HarnessError(f"successor binding drifted: {relative.as_posix()}")
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


def _roster_weight_allowlist(root: Path, candidate: str) -> tuple[str, ...]:
    raw = (root / ROSTER).read_bytes()
    if sha256_bytes(raw) != CANDIDATE_ROSTER_SHA256:
        raise HarnessError("successor candidate roster identity drifted")
    roster = parse_canonical_object(raw, label="successor candidate roster")
    rows = roster.get("active_candidates")
    if type(rows) is not list:
        raise HarnessError("successor candidate roster is malformed")
    expected_revision = EXPECTED_CANDIDATES[candidate]["revision"]
    for item in cast(list[object], rows):
        if type(item) is not dict:
            raise HarnessError("successor candidate roster row is malformed")
        row = cast(dict[str, object], item)
        if row.get("candidate_id") != candidate:
            continue
        if row.get("candidate_revision") != expected_revision:
            raise HarnessError("successor roster revision drifted")
        allowed = row.get("allowed_weight_files")
        if type(allowed) is not list or not allowed:
            raise HarnessError("successor weight allowlist is missing")
        result = tuple(cast(str, item) for item in allowed)
        if any(
            type(item) is not str
            or not item
            or "/" in item
            or not (item.endswith(".safetensors") or item == "model.safetensors.index.json")
            for item in allowed
        ):
            raise HarnessError("successor weight allowlist contains an unsafe path")
        if len(result) != len(set(result)):
            raise HarnessError("successor weight allowlist contains duplicates")
        return result
    raise HarnessError("candidate is absent from the successor roster")


def _payload_files(snapshot: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(snapshot.rglob("*"))
        if path.is_file() and ".cache" not in path.relative_to(snapshot).parts
    )


def _payload_manifest(snapshot: Path) -> list[dict[str, object]]:
    snapshot = snapshot.resolve(strict=True)
    records: list[dict[str, object]] = []
    for path in _payload_files(snapshot):
        if path.is_symlink():
            raise HarnessError("staged snapshot payload files must not be symlinks")
        relative = path.relative_to(snapshot).as_posix()
        if not relative or "/" in relative:
            raise HarnessError("staged snapshot payload files must be root-level basenames")
        observed = path.stat()
        if not stat.S_ISREG(observed.st_mode) or observed.st_size <= 0:
            raise HarnessError("staged snapshot payload files must be non-empty regular files")
        records.append(
            {"byte_count": observed.st_size, "path": relative, "sha256": sha256_file(path)}
        )
    if not records:
        raise HarnessError("staged snapshot payload manifest is empty")
    return records


def _remote_selected_payload(
    *,
    hub: Any,
    root: Path,
    candidate: str,
) -> tuple[tuple[str, ...], int]:
    revision = cast(str, EXPECTED_CANDIDATES[candidate]["revision"])
    weight_files = _roster_weight_allowlist(root, candidate)
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
    processor_metadata = EXPECTED_CANDIDATES[candidate]["processor_metadata_filename"]
    required_metadata_files = ("config.json", "tokenizer_config.json") + (
        (cast(str, processor_metadata),) if processor_metadata is not None else ()
    )
    for required_metadata in required_metadata_files:
        if required_metadata not in selected:
            raise HarnessError(f"remote revision is missing required metadata: {required_metadata}")
    return tuple(sorted(selected)), sum(selected.values())


def _remote_capacity_preflight(
    *,
    hub: Any,
    root: Path,
    candidate: str,
    destination_parent: Path,
) -> tuple[tuple[str, ...], int, int]:
    selected, selected_total = _remote_selected_payload(hub=hub, root=root, candidate=candidate)
    required_free = _required_staging_free_bytes(selected_total)
    available = shutil.disk_usage(destination_parent).free
    if available < required_free:
        raise HarnessError(
            "insufficient free storage for bounded candidate staging: "
            f"available={available} required={required_free}"
        )
    return selected, selected_total, available


def _remote_roster_capacity_preflight(
    *,
    hub: Any,
    root: Path,
    candidate: str,
    destination_parent: Path,
) -> tuple[tuple[str, ...], int, int, int]:
    if candidate not in EXPECTED_CANDIDATES:
        raise HarnessError("candidate is outside the frozen roster")
    available = shutil.disk_usage(destination_parent).free
    selected_for_candidate: tuple[str, ...] | None = None
    selected_total_for_candidate: int | None = None
    for roster_candidate in EXPECTED_CANDIDATES:
        selected, selected_total = _remote_selected_payload(
            hub=hub, root=root, candidate=roster_candidate
        )
        expected_total = EXPECTED_SELECTED_PAYLOAD_BYTES[roster_candidate]
        if selected_total != expected_total:
            raise HarnessError(
                f"{roster_candidate} remote selected payload byte total drifted: "
                f"observed={selected_total} expected={expected_total}"
            )
        if roster_candidate == candidate:
            selected_for_candidate = selected
            selected_total_for_candidate = selected_total
    if selected_for_candidate is None or selected_total_for_candidate is None:
        raise HarnessError("candidate is absent from the frozen roster preflight")
    roster_required = _required_roster_staging_free_bytes()
    if available < roster_required:
        raise HarnessError(
            "insufficient free storage for bounded dual-candidate roster staging: "
            f"available={available} required={roster_required}"
        )
    return selected_for_candidate, selected_total_for_candidate, available, roster_required


def _required_staging_free_bytes(selected_total: int) -> int:
    if type(selected_total) is not int or selected_total <= 0:
        raise HarnessError("selected staging payload must be a positive integer byte count")
    return selected_total + STAGING_CONTROL_RESERVE_BYTES


def _required_roster_staging_free_bytes() -> int:
    if set(EXPECTED_SELECTED_PAYLOAD_BYTES) != set(EXPECTED_CANDIDATES):
        raise HarnessError("frozen selected-payload roster drifted")
    return max(
        _required_staging_free_bytes(selected_total)
        for selected_total in EXPECTED_SELECTED_PAYLOAD_BYTES.values()
    )


def _prepare_hub_download() -> Any:
    # Keep acquisition storage behavior deterministic and bounded. The committed
    # huggingface_hub local_dir path writes one process-unique temporary file on
    # the destination filesystem and atomically moves it into place. Serializing
    # downloads therefore bounds model-byte occupancy by the selected payload,
    # rather than N concurrent shards. Xet is disabled to avoid an additional
    # reconstruction/cache surface, and a caller-supplied empty cache_dir prevents
    # implicit reuse/copying from a pre-existing global Hub cache.
    os.environ["HF_HUB_DISABLE_XET"] = "1"
    os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] = "0"
    try:
        hub: Any = importlib.import_module("huggingface_hub")
        constants: Any = importlib.import_module("huggingface_hub.constants")
    except Exception as exc:
        raise HarnessError("huggingface_hub is unavailable") from exc
    if getattr(constants, "HF_HUB_DISABLE_XET", None) is not True:
        raise HarnessError("huggingface_hub Xet transport must be disabled before staging")
    if os.environ.get("HF_XET_CHUNK_CACHE_SIZE_BYTES") != "0":
        raise HarnessError("Hugging Face Xet chunk cache must remain disabled")
    return hub


def _staging_policy(*, selected_total: int, free_before: int, free_after: int) -> dict[str, object]:
    required = _required_staging_free_bytes(selected_total)
    roster_required = _required_roster_staging_free_bytes()
    if free_before < roster_required:
        raise HarnessError("dual-candidate staging preflight no longer satisfies the roster bound")
    if free_after < STAGING_CONTROL_RESERVE_BYTES:
        raise HarnessError("post-stage free storage fell below the control reserve")
    return {
        "control_reserve_bytes": STAGING_CONTROL_RESERVE_BYTES,
        "download_max_workers": STAGING_MAX_WORKERS,
        "global_cache_reuse": False,
        "observed_free_bytes_after": free_after,
        "observed_free_bytes_before": free_before,
        "required_free_bytes_before": required,
        "roster_preflight_candidates": sorted(EXPECTED_CANDIDATES),
        "roster_required_free_bytes_before": roster_required,
        "schema_version": STAGING_POLICY_SCHEMA,
        "selected_payload_bytes": selected_total,
        "xet_enabled": False,
    }


def _metadata_digests(candidate: str, snapshot: Path) -> dict[str, str | None]:
    expected = EXPECTED_CANDIDATES[candidate]
    processor_metadata = expected["processor_metadata_filename"]
    if (processor_metadata is None) != (expected["processor_policy"] == TOKENIZER_ONLY):
        raise HarnessError(f"{candidate} processor policy disagrees with its metadata file")
    digests: dict[str, str | None] = {}
    for field, name in (
        ("config_sha256", "config.json"),
        ("tokenizer_config_sha256", "tokenizer_config.json"),
    ):
        path = snapshot / name
        if not path.is_file():
            raise HarnessError(f"staged snapshot missing {name}")
        digests[field] = sha256_file(path)
    if processor_metadata is None:
        digests["processor_config_sha256"] = None
    else:
        path = snapshot / cast(str, processor_metadata)
        if not path.is_file():
            raise HarnessError(f"staged snapshot missing {path.name}")
        digests["processor_config_sha256"] = sha256_file(path)
    return digests


def _validate_snapshot(candidate: str, snapshot: Path) -> tuple[dict[str, str | None], int, int]:
    snapshot = snapshot.resolve(strict=True)
    expected = EXPECTED_CANDIDATES[candidate]
    digests = _metadata_digests(candidate, snapshot)
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
        raise HarnessError(f"{candidate} weights_sha256 drifted from the successor roster")
    if artifact_identity_sha256 != expected["artifact_identity_sha256"]:
        raise HarnessError(f"{candidate} artifact identity drifted from the successor roster")
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
    _package_versions()
    hub = _prepare_hub_download()
    revision = cast(str, EXPECTED_CANDIDATES[candidate]["revision"])
    (
        selected_files,
        remote_selected_bytes,
        free_before,
        roster_required_free,
    ) = _remote_roster_capacity_preflight(
        hub=hub,
        root=root,
        candidate=candidate,
        destination_parent=destination.parent,
    )
    if free_before < roster_required_free:
        raise HarnessError("dual-candidate roster preflight free-space bound was not preserved")
    controlled_cache = destination / ".cache" / "mesc-hub-cache"
    controlled_cache.mkdir(parents=True, exist_ok=False)
    try:
        hub.snapshot_download(
            repo_id=candidate,
            revision=revision,
            cache_dir=str(controlled_cache),
            local_dir=str(destination),
            allow_patterns=list(selected_files),
            max_workers=STAGING_MAX_WORKERS,
        )
    except Exception as exc:
        raise HarnessError(f"exact candidate staging failed for {candidate}") from exc
    cache_root = destination / ".cache"
    if cache_root.exists():
        shutil.rmtree(cache_root)
    free_after = shutil.disk_usage(destination.parent).free
    staging_policy = _staging_policy(
        selected_total=remote_selected_bytes,
        free_before=free_before,
        free_after=free_after,
    )
    payload_manifest = _payload_manifest(destination)
    local_selected_files = tuple(cast(str, item["path"]) for item in payload_manifest)
    local_selected_bytes = sum(cast(int, item["byte_count"]) for item in payload_manifest)
    if local_selected_files != selected_files:
        raise HarnessError("staged snapshot payload differs from remote selected files")
    if local_selected_bytes != remote_selected_bytes:
        raise HarnessError("staged snapshot byte total differs from remote manifest")
    digests, file_count, total_bytes = _validate_snapshot(candidate, destination)
    weights_sha256, artifact_identity_sha256, weight_files = _validate_weight_identity(
        candidate, destination
    )
    receipt = {
        "artifact_identity_sha256": artifact_identity_sha256,
        "config_sha256": digests["config_sha256"],
        "model_id": candidate,
        "processor_config_sha256": digests["processor_config_sha256"],
        "candidate_roster_sha256": CANDIDATE_ROSTER_SHA256,
        "payload_manifest": payload_manifest,
        "remote_selected_bytes": remote_selected_bytes,
        "remote_selected_files": list(selected_files),
        "revision": revision,
        "schema_version": SCHEMA_STAGE,
        "staging_policy": staging_policy,
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
    if set(receipt) != STAGE_RECEIPT_KEYS or receipt["schema_version"] != SCHEMA_STAGE:
        raise HarnessError("stage receipt schema drifted")
    _validate_staging_policy_envelope(receipt)
    expected = EXPECTED_CANDIDATES[candidate]
    if receipt["model_id"] != candidate or receipt["revision"] != expected["revision"]:
        raise HarnessError("stage receipt candidate identity drifted")
    _validate_frozen_selected_payload_bytes(receipt, candidate)
    if receipt["candidate_roster_sha256"] != CANDIDATE_ROSTER_SHA256:
        raise HarnessError("stage receipt successor roster identity drifted")
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
    if not set(_roster_weight_allowlist(root, candidate)) <= set(remote_file_names):
        raise HarnessError("stage receipt omitted a successor roster weight file")
    payload_manifest = receipt["payload_manifest"]
    if type(payload_manifest) is not list or not payload_manifest:
        raise HarnessError("stage receipt payload manifest is invalid")
    local_payload_manifest = _payload_manifest(snapshot)
    if payload_manifest != local_payload_manifest:
        raise HarnessError("stage receipt payload manifest drifted")
    local_payload_names = tuple(cast(str, item["path"]) for item in local_payload_manifest)
    if remote_file_names != local_payload_names:
        raise HarnessError("stage receipt remote/local payload file set drifted")
    local_payload_bytes = sum(cast(int, item["byte_count"]) for item in local_payload_manifest)
    if receipt["remote_selected_bytes"] != local_payload_bytes:
        raise HarnessError("stage receipt remote/local payload byte total drifted")
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


def _validate_staging_policy_envelope(receipt: dict[str, object]) -> None:
    staging_policy = receipt["staging_policy"]
    if type(staging_policy) is not dict or set(staging_policy) != {
        "control_reserve_bytes",
        "download_max_workers",
        "global_cache_reuse",
        "observed_free_bytes_after",
        "observed_free_bytes_before",
        "required_free_bytes_before",
        "roster_preflight_candidates",
        "roster_required_free_bytes_before",
        "schema_version",
        "selected_payload_bytes",
        "xet_enabled",
    }:
        raise HarnessError("stage receipt staging policy schema drifted")
    policy = cast(dict[str, object], staging_policy)
    if (
        policy["schema_version"] != STAGING_POLICY_SCHEMA
        or policy["control_reserve_bytes"] != STAGING_CONTROL_RESERVE_BYTES
        or policy["download_max_workers"] != STAGING_MAX_WORKERS
        or policy["global_cache_reuse"] is not False
        or policy["xet_enabled"] is not False
    ):
        raise HarnessError("stage receipt staging policy drifted")
    for field in (
        "observed_free_bytes_after",
        "observed_free_bytes_before",
        "required_free_bytes_before",
        "roster_required_free_bytes_before",
        "selected_payload_bytes",
    ):
        if type(policy[field]) is not int or cast(int, policy[field]) <= 0:
            raise HarnessError(f"stage receipt staging policy {field} must be positive")
    if policy["selected_payload_bytes"] != receipt["remote_selected_bytes"]:
        raise HarnessError("stage receipt staging payload byte count drifted")
    required_free = _required_staging_free_bytes(cast(int, policy["selected_payload_bytes"]))
    if policy["required_free_bytes_before"] != required_free:
        raise HarnessError("stage receipt required free-space bound drifted")
    roster_candidates = policy["roster_preflight_candidates"]
    if roster_candidates != sorted(EXPECTED_CANDIDATES):
        raise HarnessError("stage receipt roster preflight candidate set drifted")
    roster_required = _required_roster_staging_free_bytes()
    if policy["roster_required_free_bytes_before"] != roster_required:
        raise HarnessError("stage receipt roster free-space bound drifted")
    if cast(int, policy["observed_free_bytes_before"]) < roster_required:
        raise HarnessError("stage receipt dual-candidate preflight free storage was insufficient")
    if cast(int, policy["observed_free_bytes_after"]) < STAGING_CONTROL_RESERVE_BYTES:
        raise HarnessError("stage receipt post-stage control reserve was insufficient")


def _validate_frozen_selected_payload_bytes(receipt: dict[str, object], model_id: str) -> None:
    observed = receipt.get("remote_selected_bytes")
    expected = EXPECTED_SELECTED_PAYLOAD_BYTES[model_id]
    if observed != expected:
        raise HarnessError(
            "stage receipt selected payload byte total drifted from frozen identity: "
            f"observed={observed} expected={expected}"
        )


def _validate_stage_receipt_envelope(receipt: dict[str, object]) -> str:
    if set(receipt) != STAGE_RECEIPT_KEYS or receipt.get("schema_version") != SCHEMA_STAGE:
        raise HarnessError("stage receipt schema drifted")
    model_id = receipt.get("model_id")
    if type(model_id) is not str or model_id not in EXPECTED_CANDIDATES:
        raise HarnessError("stage receipt candidate is outside the frozen roster")
    expected = EXPECTED_CANDIDATES[model_id]
    _validate_frozen_selected_payload_bytes(receipt, model_id)
    fixed = {
        "artifact_identity_sha256": expected["artifact_identity_sha256"],
        "config_sha256": expected["config_sha256"],
        "candidate_roster_sha256": CANDIDATE_ROSTER_SHA256,
        "processor_config_sha256": expected["processor_config_sha256"],
        "revision": expected["revision"],
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "weights_sha256": expected["weights_sha256"],
    }
    for field, expected_value in fixed.items():
        if receipt[field] != expected_value:
            raise HarnessError(f"stage receipt {field} drifted from frozen identity")
    _validate_staging_policy_envelope(receipt)
    for field in ("remote_selected_bytes", "snapshot_file_count", "snapshot_total_bytes"):
        if type(receipt[field]) is not int or cast(int, receipt[field]) <= 0:
            raise HarnessError(f"stage receipt {field} must be a positive integer")
    remote = receipt["remote_selected_files"]
    if type(remote) is not list or not remote:
        raise HarnessError("stage receipt remote selected files are invalid")
    remote_names = tuple(cast(str, item) for item in cast(list[object], remote))
    if (
        any(type(item) is not str or not item or "/" in item for item in cast(list[object], remote))
        or remote_names != tuple(sorted(remote_names))
        or len(remote_names) != len(set(remote_names))
    ):
        raise HarnessError("stage receipt remote selected files are not canonical")
    payload = receipt["payload_manifest"]
    if type(payload) is not list or not payload:
        raise HarnessError("stage receipt payload manifest is invalid")
    payload_rows: list[dict[str, object]] = []
    for item in cast(list[object], payload):
        if type(item) is not dict:
            raise HarnessError("stage receipt payload manifest row is invalid")
        row = cast(dict[str, object], item)
        if set(row) != {"byte_count", "path", "sha256"}:
            raise HarnessError("stage receipt payload manifest row schema drifted")
        path = row["path"]
        digest = row["sha256"]
        byte_count = row["byte_count"]
        if type(path) is not str or not path or "/" in path:
            raise HarnessError("stage receipt payload path is unsafe")
        if type(digest) is not str or SHA64.fullmatch(digest) is None:
            raise HarnessError("stage receipt payload digest is invalid")
        if type(byte_count) is not int or byte_count <= 0:
            raise HarnessError("stage receipt payload byte count is invalid")
        payload_rows.append(row)
    payload_names = tuple(cast(str, row["path"]) for row in payload_rows)
    if payload_names != remote_names:
        raise HarnessError("stage receipt remote/local payload file set drifted")
    payload_bytes = sum(cast(int, row["byte_count"]) for row in payload_rows)
    if (
        receipt["remote_selected_bytes"] != payload_bytes
        or receipt["snapshot_total_bytes"] != payload_bytes
        or receipt["snapshot_file_count"] != len(payload_rows)
    ):
        raise HarnessError("stage receipt payload size/count drifted")
    payload_by_path = {cast(str, row["path"]): row for row in payload_rows}
    weight_files = receipt["weight_files"]
    if type(weight_files) is not list or not weight_files:
        raise HarnessError("stage receipt SafeTensors file manifest is invalid")
    weight_names: list[str] = []
    for item in cast(list[object], weight_files):
        if type(item) is not dict:
            raise HarnessError("stage receipt SafeTensors file row is invalid")
        row = cast(dict[str, object], item)
        if set(row) != {"byte_count", "kind", "path", "sha256"}:
            raise HarnessError("stage receipt SafeTensors file row schema drifted")
        path = row["path"]
        if type(path) is not str or path not in payload_by_path:
            raise HarnessError("stage receipt SafeTensors path is invalid")
        if row["kind"] not in ("index", "weight"):
            raise HarnessError("stage receipt SafeTensors kind is invalid")
        payload_row = payload_by_path[path]
        if row["byte_count"] != payload_row["byte_count"] or row["sha256"] != payload_row["sha256"]:
            raise HarnessError("stage receipt SafeTensors row disagrees with payload manifest")
        weight_names.append(path)
    if len(weight_names) != len(set(weight_names)):
        raise HarnessError("stage receipt SafeTensors paths are duplicated")
    try:
        identity_module: Any = importlib.import_module(
            "medscale.mesc._training_hf_safetensors_identity_v1"
        )
        files = tuple(
            identity_module.HfArtifactFileIdentity(
                path=cast(str, row["path"]),
                kind=cast(Any, row["kind"]),
                sha256=cast(str, row["sha256"]),
                byte_count=cast(int, row["byte_count"]),
            )
            for row in cast(list[dict[str, object]], weight_files)
        )
        layout = "sharded" if files[0].kind == "index" else "single"
        identity = identity_module.HfSafeTensorsArtifactIdentity(
            model_id=model_id,
            revision=cast(str, receipt["revision"]),
            layout=layout,
            files=files,
        )
    except Exception as exc:
        raise HarnessError("stage receipt SafeTensors identity cannot be reconstructed") from exc
    if identity.weights_sha256 != receipt["weights_sha256"]:
        raise HarnessError("stage receipt weight manifest does not derive weights_sha256")
    if identity.verifier_receipt_sha256 != receipt["artifact_identity_sha256"]:
        raise HarnessError("stage receipt weight manifest does not derive artifact identity")
    return model_id


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
        *SANDBOX_UNSHARE_FLAGS,
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
        "--size",
        str(PROC_TMPFS_BYTES),
        "--tmpfs",
        "/proc",
        "--dir",
        "/proc/sys",
        "--dir",
        "/proc/sys/vm",
        "--ro-bind",
        "/proc/sys/vm/mmap_min_addr",
        "/proc/sys/vm/mmap_min_addr",
        "--ro-bind",
        "/proc/cpuinfo",
        "/proc/cpuinfo",
        "--dir",
        "/proc/driver",
        "--ro-bind",
        "/proc/driver/nvidia",
        "/proc/driver/nvidia",
        "--bind",
        "/proc/self",
        "/proc/self",
        "--dev",
        "/dev",
    ]
    parent_dirs = sorted({node.parent for node in nvidia_nodes if node.parent != Path("/dev")})
    for parent in parent_dirs:
        args.extend(["--dir", str(parent)])
    for node in nvidia_nodes:
        args.extend(["--dev-bind", str(node), str(node)])
    args.extend(
        [
            "--remount-ro",
            "/proc",
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


def _host_process_seccomp_program() -> bytes:
    """Return a deterministic x86_64 filter denying host-process interaction syscalls."""
    bpf_ld_w_abs = 0x20
    bpf_jmp_jeq_k = 0x15
    bpf_ret_k = 0x06
    seccomp_ret_allow = 0x7FFF0000
    seccomp_ret_errno = 0x00050000

    instructions: list[tuple[int, int, int, int]] = [
        (bpf_ld_w_abs, 0, 0, 4),
        (bpf_jmp_jeq_k, 1, 0, AUDIT_ARCH_X86_64),
        (bpf_ret_k, 0, 0, seccomp_ret_errno | errno.EPERM),
        (bpf_ld_w_abs, 0, 0, 0),
    ]
    denied = tuple(
        sorted(
            {
                *HOST_PROCESS_SYSCALLS_X86_64,
                *(number | X32_SYSCALL_BIT for number in HOST_PROCESS_SYSCALLS_X86_64),
            }
        )
    )
    for number in denied:
        instructions.extend(
            (
                (bpf_jmp_jeq_k, 0, 1, number),
                (bpf_ret_k, 0, 0, seccomp_ret_errno | errno.EPERM),
            )
        )
    instructions.append((bpf_ret_k, 0, 0, seccomp_ret_allow))
    return b"".join(struct.pack("<HBBI", *instruction) for instruction in instructions)


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
        "LD_LIBRARY_PATH": CUDA_DRIVER_LIBRARY_PATH,
        "NVIDIA_VISIBLE_DEVICES": NVIDIA_VISIBLE_DEVICES_VALUE,
        "NVIDIA_DRIVER_CAPABILITIES": NVIDIA_DRIVER_CAPABILITIES_VALUE,
    }
    for key, value in environment.items():
        command.extend(["--setenv", key, value])
    with tempfile.TemporaryFile(mode="w+b") as seccomp:
        seccomp.write(_host_process_seccomp_program())
        seccomp.flush()
        seccomp.seek(0)
        command.extend(["--seccomp", str(seccomp.fileno())])
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
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            pass_fds=(seccomp.fileno(),),
        )
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


def _require_cuda_sandbox_support() -> None:
    if platform.machine() != "x86_64":
        raise HarnessError("MRL-0809 CUDA sandbox requires x86_64 for the frozen seccomp policy")
    support_paths = (
        Path(CUDA_DRIVER_LIBRARY_PATH),
        Path("/proc/self"),
        Path("/proc/cpuinfo"),
        Path("/proc/sys/vm/mmap_min_addr"),
        Path("/proc/driver/nvidia"),
    )
    missing_support = [str(path) for path in support_paths if not path.exists()]
    if missing_support:
        raise HarnessError(
            "CUDA sandbox runtime support path is unavailable: " + missing_support[0]
        )


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
    _require_cuda_sandbox_support()
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
    start_marker = observation_out.with_name(observation_out.name + ".probe-start.json")
    write_new(
        start_marker,
        canonical_json_bytes(
            {
                "candidate": candidate,
                "provider_execution_id": provider_execution_id,
                "repository_sha": head,
                "repository_tree": tree,
                "schema_version": SCHEMA_PROBE_START,
                "stage_receipt_sha256": stage_receipt_sha256,
            }
        ),
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
    uses_processor = expected["processor_policy"] == AUTO_PROCESSOR
    baseline_gpu = int(torch.cuda.memory_allocated())
    torch.cuda.reset_peak_memory_stats()
    tokenizer: Any = None
    processor: Any = None
    model: Any = None
    input_ids: Any = None
    output: Any = None
    generated_ids: list[int] = []
    prompt_token_ids: list[int] = []
    decoded_hash = ""
    logits_finite = False
    peak_gpu = 0
    peak_cpu = 0
    try:
        tokenizer = auto_tokenizer.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
        )
        if uses_processor:
            processor = auto_processor.from_pretrained(
                str(snapshot),
                local_files_only=True,
                trust_remote_code=False,
            )
        prompt_token_ids = [
            int(token)
            for token in tokenizer.apply_chat_template(
                [{"role": "user", "content": SYNTHETIC_PROMPT}],
                add_generation_prompt=True,
                tokenize=True,
                return_dict=False,
            )
        ]
        if (
            sha256_bytes(canonical_json_bytes(prompt_token_ids))
            != expected["prompt_token_ids_sha256"]
        ):
            raise HarnessError("chat-template prompt tokens drifted from the frozen identity")
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
        input_ids = torch.tensor([prompt_token_ids], device=torch.device("cuda:0"))
        with torch.inference_mode():
            output = model.generate(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                do_sample=False,
                num_beams=1,
                max_new_tokens=MAX_NEW_TOKENS,
                output_logits=True,
                return_dict_in_generate=True,
            )
        sequence = output.sequences[0]
        generated_ids = [int(token) for token in sequence[len(prompt_token_ids) :].tolist()]
        if not generated_ids:
            raise HarnessError("synthetic generation produced no new tokens")
        step_logits = tuple(output.logits)
        if len(step_logits) != len(generated_ids):
            raise HarnessError("generation logits do not cover every generated token")
        logits_finite = all(bool(torch.isfinite(step).all()) for step in step_logits)
        if not logits_finite:
            raise HarnessError("synthetic generation produced non-finite logits")
        decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
        if not decoded.strip():
            raise HarnessError("synthetic generation decoded to empty text")
        torch.cuda.synchronize()
        decoded_hash = sha256_bytes(decoded.encode("utf-8"))
        peak_gpu = int(torch.cuda.max_memory_allocated())
        peak_cpu = int(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss) * 1024
        if peak_gpu <= 0 or peak_cpu <= 0:
            raise HarnessError("candidate memory observations must be positive")
        if peak_gpu > MAX_PEAK_GPU_MEMORY_BYTES:
            raise HarnessError("peak GPU memory exceeded the successor headroom ceiling")
    finally:
        del output, input_ids, model, processor, tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    residual_gpu = int(torch.cuda.memory_allocated())
    unloaded = residual_gpu <= baseline_gpu + (64 * 1024 * 1024)
    if not unloaded:
        raise HarnessError("GPU allocations did not return to the bounded cleanup envelope")
    generation_evidence = {
        "all_generated_logits_finite": logits_finite,
        "decoded_text_sha256": decoded_hash,
        "generated_token_ids": generated_ids,
        "prompt_construction": PROMPT_CONSTRUCTION,
        "prompt_token_ids_sha256": sha256_bytes(canonical_json_bytes(prompt_token_ids)),
        "synthetic_prompt_sha256": sha256_bytes(SYNTHETIC_PROMPT.encode("utf-8")),
    }
    generation_sha256 = sha256_bytes(canonical_json_bytes(generation_evidence))
    candidate_receipt = {
        "all_modules_on_cuda_device_0": True,
        "architecture": architecture,
        "config_sha256": digests["config_sha256"],
        "load_completed": True,
        "model_id": candidate,
        "peak_cpu_memory_bytes": peak_cpu,
        "peak_gpu_memory_bytes": peak_gpu,
        "processor_config_sha256": digests["processor_config_sha256"],
        "processor_loaded": uses_processor,
        "processor_policy": expected["processor_policy"],
        "revision": expected["revision"],
        "runtime_representation": RUNTIME_REPRESENTATION,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": generation_sha256,
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": digests["tokenizer_config_sha256"],
        "tokenizer_loaded": True,
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
    candidate_value = document["candidate"]
    if type(candidate_value) is not dict:
        raise HarnessError("candidate observation candidate must be an object")
    candidate = cast(dict[str, object], candidate_value)
    model_id = cast(str, candidate.get("model_id"))
    expected = EXPECTED_CANDIDATES.get(model_id)
    if expected is None:
        raise HarnessError("candidate observation is outside the frozen roster")
    if document["stage_weights_sha256"] != expected["weights_sha256"]:
        raise HarnessError("candidate observation weights identity drifted")
    if document["stage_artifact_identity_sha256"] != expected["artifact_identity_sha256"]:
        raise HarnessError("candidate observation artifact identity drifted")
    generation_value = document["generation_evidence"]
    if type(generation_value) is not dict:
        raise HarnessError("candidate observation generation evidence must be an object")
    generation = cast(dict[str, object], generation_value)
    if candidate.get("synthetic_generation_sha256") != sha256_bytes(
        canonical_json_bytes(generation)
    ):
        raise HarnessError("candidate synthetic generation evidence digest drifted")
    if type(document["runtime_identity"]) is not dict:
        raise HarnessError("candidate observation runtime identity must be an object")
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
    candidates: list[dict[str, object]] = []
    for document in documents:
        candidate = dict(cast(dict[str, object], document["candidate"]))
        candidate["artifact_identity_sha256"] = document["stage_artifact_identity_sha256"]
        candidate["generation_evidence"] = document["generation_evidence"]
        candidate["stage_receipt_sha256"] = document["stage_receipt_sha256"]
        candidate["weights_sha256"] = document["stage_weights_sha256"]
        candidates.append(candidate)
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
        "candidate_roster_sha256": CANDIDATE_ROSTER_SHA256,
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
        "offload_performed": False,
        "optimizer_present": False,
        "persistent_weight_writeback": False,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": first["provider_execution_id"],
        "provider_owner": "GOOGLE",
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_identity": identity,
        "runtime_identity_sha256": first["runtime_identity_sha256"],
        "sandbox_policy_sha256": SANDBOX_POLICY,
        "schema_version": SCHEMA_RECEIPT,
        "static_prerequisite_manifest_sha256": first["static_prerequisite_manifest_sha256"],
        "successor_authorization_sha256": SUCCESSOR_AUTHORIZATION_SHA256,
        "training_performed": False,
        "trust_remote_code": False,
        "v1_infeasibility_record_sha256": V1_INFEASIBILITY_RECORD_SHA256,
        "weight_mutation_performed": False,
    }
    raw = canonical_json_bytes(receipt)
    sys.path.insert(0, str((root / "src").resolve()))
    validator = importlib.import_module("medscale.mesc._mrl_0809_runtime_feasibility_v2")
    validated = validator.validate_successor_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256=sha256_file(root / STATIC_MANIFEST),
        expected_dependency_lock_sha256=sha256_file(root / LOCKFILE),
        expected_repository_sha=head,
        expected_repository_tree=tree,
    )
    if validated.receipt_sha256 != sha256_bytes(raw):
        raise HarnessError("canonical validator receipt digest mismatch")
    write_new(output, raw)


def verify_receipt(
    root: Path,
    receipt_path: Path,
    stage_receipts: list[Path],
    verification_out: Path,
) -> None:
    root = root.resolve(strict=True)
    if len(stage_receipts) != 2:
        raise HarnessError("independent verification requires exactly two stage receipts")
    head, tree = _require_repository(root)
    receipt_path = _require_outside_repository(
        receipt_path, root, label="runtime-feasibility receipt"
    ).resolve(strict=True)
    verification_out = _require_outside_repository(
        verification_out, root, label="independent verification receipt"
    )
    raw = receipt_path.read_bytes()
    receipt_document = parse_canonical_object(raw, label="runtime-feasibility receipt")
    sys.path.insert(0, str((root / "src").resolve()))
    validator = importlib.import_module("medscale.mesc._mrl_0809_runtime_feasibility_v2")
    validated = validator.validate_successor_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256=sha256_file(root / STATIC_MANIFEST),
        expected_dependency_lock_sha256=sha256_file(root / LOCKFILE),
        expected_repository_sha=head,
        expected_repository_tree=tree,
    )
    harness_sha256 = sha256_file(root / HARNESS)
    if validated.runtime_identity.get("harness_sha256") != harness_sha256:
        raise HarnessError("runtime receipt does not bind the exact canonical harness bytes")
    candidates_value = receipt_document.get("candidates")
    if type(candidates_value) is not list:
        raise HarnessError("runtime receipt candidate roster is invalid")
    final_candidates: dict[str, dict[str, object]] = {}
    for item in cast(list[object], candidates_value):
        if type(item) is not dict:
            raise HarnessError("runtime receipt candidate row is invalid")
        row = cast(dict[str, object], item)
        model_id = row.get("model_id")
        if type(model_id) is not str or model_id in final_candidates:
            raise HarnessError("runtime receipt candidate roster is not unique")
        final_candidates[model_id] = row
    if set(final_candidates) != set(EXPECTED_CANDIDATES):
        raise HarnessError("runtime receipt candidate roster drifted")
    verified_stage: dict[str, str] = {}
    for path in stage_receipts:
        resolved = _require_outside_repository(path, root, label="stage receipt").resolve(
            strict=True
        )
        stage_raw = resolved.read_bytes()
        stage_document = parse_canonical_object(stage_raw, label="stage receipt")
        model_id = _validate_stage_receipt_envelope(stage_document)
        if model_id in verified_stage:
            raise HarnessError("duplicate stage receipt candidate")
        stage_sha256 = sha256_bytes(stage_raw)
        candidate = final_candidates[model_id]
        if candidate.get("stage_receipt_sha256") != stage_sha256:
            raise HarnessError("stage receipt digest does not match the final runtime receipt")
        for field in (
            "artifact_identity_sha256",
            "config_sha256",
            "processor_config_sha256",
            "revision",
            "tokenizer_config_sha256",
            "weights_sha256",
        ):
            if candidate.get(field) != stage_document[field]:
                raise HarnessError(f"stage receipt {field} disagrees with final candidate evidence")
        verified_stage[model_id] = stage_sha256
    if set(verified_stage) != set(EXPECTED_CANDIDATES):
        raise HarnessError("independent verification did not cover the exact frozen roster")
    verification = {
        "dependency_lock_sha256": validated.dependency_lock_sha256,
        "disposition": "PASS",
        "harness_sha256": harness_sha256,
        "provider_execution_id": validated.provider_execution_id,
        "repository_sha": validated.repository_sha,
        "repository_tree": validated.repository_tree,
        "runtime_feasibility_receipt_sha256": validated.receipt_sha256,
        "runtime_identity_sha256": validated.runtime_identity_sha256,
        "schema_version": SCHEMA_VERIFY,
        "stage_receipts": [
            {"model_id": model_id, "sha256": verified_stage[model_id]}
            for model_id in sorted(verified_stage)
        ],
        "static_prerequisite_manifest_sha256": validated.static_prerequisite_manifest_sha256,
    }
    write_new(verification_out, canonical_json_bytes(verification))


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

    verify = sub.add_parser("verify")
    verify.add_argument("--repository-root", type=Path, required=True)
    verify.add_argument("--receipt", type=Path, required=True)
    verify.add_argument("--stage-receipt", type=Path, action="append", required=True)
    verify.add_argument("--verification-out", type=Path, required=True)

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
    if args.command == "verify":
        verify_receipt(
            args.repository_root,
            args.receipt,
            args.stage_receipt,
            args.verification_out,
        )
        return
    if args.command == "_worker":
        _worker(args.candidate, args.snapshot)
        return
    raise HarnessError("unreachable command")


if __name__ == "__main__":
    main()
