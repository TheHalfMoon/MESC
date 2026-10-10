"""Kaggle environment candidates and offline custody; never launch a GPU.

Caller observations are untrusted evidence candidates. Contract validation is
neither independent attestation nor scientific admission. No provider mutation,
model import, credential access, training, or authority writer exists here.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Final, Never

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

CANDIDATES: Final = (
    ("Qwen/Qwen3-8B", "b968826d9c46dd6066d109eabc6255188de91218"),
    ("google/gemma-4-12B-it", "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7"),
)
DEPENDENCY_LOCK_SHA256: Final = "6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4"
PACKAGES: Final = {
    "accelerate": "1.14.0",
    "bitsandbytes": "0.50.2",
    "huggingface-hub": "1.23.0",
    "pillow": "12.3.0",
    "torch": "2.13.0",
    "torchvision": "0.28.0",
    "transformers": "5.16.1",
    "xgrammar": "0.2.7",
}
_SCHEMA: Final = "MESC-KAGGLE-ENVIRONMENT-CANDIDATE-V1"
_RESULT_SCHEMA: Final = "MESC-KAGGLE-VALIDATED-ENVIRONMENT-CANDIDATE-V1"
_CANDIDATE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "evidence_origin",
        "run_id",
        "source_revision",
        "source_tree",
        "source_manifest_sha256",
        "dependency_lock_sha256",
        "observation_sha256",
        "per_device_memory_bytes",
        "placement_policy",
        "quota_state",
        "max_session_seconds",
        "max_evidence_bytes",
        "scientific_execution_authorized",
        "runtime_feasibility_proven",
    }
)
_FLAGS: Final = (
    "cpu_offload",
    "disk_offload",
    "automatic_device_map",
    "training",
    "weight_mutation",
    "paid_compute",
)
_FIELDS: Final = frozenset(
    {
        "schema_version",
        "evidence_origin",
        "provider",
        "run_id",
        "source_revision",
        "source_tree",
        "source_manifest_sha256",
        "dependency_lock_sha256",
        "python_version",
        "platform",
        "packages",
        "cuda_available",
        "cuda_runtime",
        "driver_version",
        "devices",
        "placement_policy",
        "representation",
        "candidates",
        "input",
        "input_class",
        "quota_remaining_seconds",
        "max_session_seconds",
        "max_evidence_bytes",
        *_FLAGS,
    }
)
_RESULT_FILES: Final = frozenset({"qwen-result.json", "gemma-result.json"})


class KaggleAdapterError(ValueError):
    """The optional Kaggle path failed closed."""


def _fail(message: str) -> Never:
    raise KaggleAdapterError(message)


def _hex(value: object, size: int, label: str) -> str:
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{size}}}", value) is None:
        _fail(f"invalid {label}")
    return value


def _positive_int(value: object, maximum: int, label: str) -> int:
    if type(value) is not int or not 0 < value <= maximum:
        _fail(f"invalid {label}")
    return value


def validate_environment_candidate(
    document: dict[str, object],
    *,
    expected_revision: str,
    expected_tree: str,
    expected_manifest_sha256: str,
) -> bytes:
    """Validate declared identity, preserving UNKNOWN quota and untrusted origin.

    A T4 pair is permitted only as an inventory: the frozen workload must run
    sequentially on cuda:0. Actual tensor auditing, CUDA/BMM smoke, snapshot
    hashes, sandbox isolation, capacity and hosted retention remain independent
    runtime gates. This function cannot prove those facts from caller metadata.
    """
    if type(document) is not dict or set(document) != _FIELDS:
        _fail("environment field envelope drifted")
    if document["schema_version"] != _SCHEMA or document["provider"] != "KAGGLE":
        _fail("wrong schema or provider")
    origin = document["evidence_origin"]
    if origin not in ("OFFLINE_SIMULATION", "HOSTED_OBSERVATION"):
        _fail("untrusted evidence origin label")
    run_id = _hex(document["run_id"], 32, "run ID")
    for field, expected, size in (
        ("source_revision", expected_revision, 40),
        ("source_tree", expected_tree, 40),
        ("source_manifest_sha256", expected_manifest_sha256, 64),
        ("dependency_lock_sha256", DEPENDENCY_LOCK_SHA256, 64),
    ):
        if _hex(document[field], size, field) != _hex(expected, size, "expected identity"):
            _fail(f"{field} mismatch")
    version = document["python_version"]
    if type(version) is not str or re.fullmatch(r"3\.11\.\d+", version) is None:
        _fail("unsupported Python identity")
    if document["platform"] != "linux-x86_64" or document["packages"] != PACKAGES:
        _fail("platform or frozen package identities drifted")
    if document["cuda_available"] is not True:
        _fail("CUDA unavailable")
    for field in ("cuda_runtime", "driver_version"):
        value = document[field]
        if type(value) is not str or re.fullmatch(r"\d+(?:\.\d+){1,3}", value) is None:
            _fail(f"missing numeric {field} identity")
    devices = document["devices"]
    if type(devices) is not list or len(devices) not in (1, 2):
        _fail("one or two independently inventoried T4 devices required")
    memories: list[int] = []
    for index, item in enumerate(devices):
        if type(item) is not dict or set(item) != {
            "index",
            "name",
            "memory_bytes",
            "compute_capability",
        }:
            _fail("GPU inventory envelope drifted")
        if type(item["index"]) is not int or item["index"] != index or item["name"] != "Tesla T4":
            _fail("GPU identity drifted")
        if item["compute_capability"] != [7, 5]:
            _fail("T4 CUDA capability drifted")
        memory = _positive_int(item["memory_bytes"], 16 * 1024**3, "per-device memory")
        if memory < 12 * 1024**3:
            _fail("one device cannot satisfy the frozen 12-GiB peak ceiling")
        memories.append(memory)
    expected_candidates = [
        {"model_id": model, "revision": revision} for model, revision in CANDIDATES
    ]
    if document["candidates"] != expected_candidates:
        _fail("frozen candidate revisions drifted")
    for field, expected in (
        ("placement_policy", "SINGLE_CUDA0_SEQUENTIAL"),
        ("representation", "bitsandbytes-nf4-v1"),
        ("input_class", "SYNTHETIC_ONLY"),
        ("input", "Write one short sentence about a blue triangle."),
    ):
        if document[field] != expected:
            _fail(f"frozen {field} drifted")
    if any(document[field] is not False for field in _FLAGS):
        _fail("paid compute, offload, automatic placement, training or mutation forbidden")
    quota = document["quota_remaining_seconds"]
    if quota is not None and (type(quota) is not int or quota < 0):
        _fail("quota must be UNKNOWN or a nonnegative observed integer")
    seconds = _positive_int(document["max_session_seconds"], 14400, "session bound")
    budget = _positive_int(document["max_evidence_bytes"], 1048576, "evidence budget")
    return canonical_json_bytes(
        {
            "schema_version": _RESULT_SCHEMA,
            "evidence_origin": origin,
            "run_id": run_id,
            "source_revision": expected_revision,
            "source_tree": expected_tree,
            "source_manifest_sha256": expected_manifest_sha256,
            "dependency_lock_sha256": DEPENDENCY_LOCK_SHA256,
            "observation_sha256": hashlib.sha256(canonical_json_bytes(document)).hexdigest(),
            "per_device_memory_bytes": memories,
            "placement_policy": "SINGLE_CUDA0_SEQUENTIAL",
            "quota_state": "UNKNOWN" if quota is None else "UNTRUSTED_OBSERVED_VALUE",
            "max_session_seconds": seconds,
            "max_evidence_bytes": budget,
            "scientific_execution_authorized": False,
            "runtime_feasibility_proven": False,
        }
    )


def require_scientific_execution(_candidate: bytes) -> Never:
    """A candidate, successful test or caller-supplied approval cannot arm execution."""
    _fail(
        "Kaggle execution requires separate independent Founder authority and hosted qualification"
    )


def _safe_directory(path: Path) -> Path:
    absolute = path.absolute()
    for parent in (absolute, *absolute.parents):
        if parent.is_symlink():
            _fail("symlink custody/state directory forbidden")
        if parent.exists():
            attributes = getattr(parent.lstat(), "st_file_attributes", 0)
            if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                _fail("reparse custody/state directory forbidden")
    return absolute


def _write_new(path: Path, raw: bytes) -> None:
    _safe_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if os.name != "nt":
        descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class OfflineCustodySession:
    """One-shot MOCK state and immediate local preservation, never hosted transport.

    The explicit state directory is test-only. It is not a real provider grant
    store. A future real controller needs fixed OS-account/provider consumption,
    authenticated immutable authority and independently proven termination.
    """

    def __init__(self, *, state_dir: Path, custody: Path, environment_candidate: bytes) -> None:
        if type(environment_candidate) is not bytes or len(environment_candidate) > 8192:
            _fail("offline candidate byte bound exceeded")
        try:
            value = json.loads(environment_candidate)
        except (ValueError, UnicodeDecodeError) as exc:
            raise KaggleAdapterError("invalid offline candidate") from exc
        if type(value) is not dict or set(value) != _CANDIDATE_FIELDS:
            _fail("offline candidate field envelope drifted")
        for field, size in (
            ("source_revision", 40),
            ("source_tree", 40),
            ("source_manifest_sha256", 64),
            ("dependency_lock_sha256", 64),
            ("observation_sha256", 64),
        ):
            _hex(value[field], size, field)
        if value["dependency_lock_sha256"] != DEPENDENCY_LOCK_SHA256:
            _fail("offline frozen dependency identity drifted")
        memories = value["per_device_memory_bytes"]
        if type(memories) is not list or len(memories) not in (1, 2):
            _fail("offline per-device inventory drifted")
        for memory in memories:
            if _positive_int(memory, 16 * 1024**3, "offline GPU memory") < 12 * 1024**3:
                _fail("offline single-device memory drifted")
        if value["placement_policy"] != "SINGLE_CUDA0_SEQUENTIAL" or value["quota_state"] not in (
            "UNKNOWN",
            "UNTRUSTED_OBSERVED_VALUE",
        ):
            _fail("offline placement/quota envelope drifted")
        if canonical_json_bytes(value) != environment_candidate:
            _fail("offline candidate must be a canonical object")
        if (
            value.get("schema_version") != _RESULT_SCHEMA
            or value.get("evidence_origin") != "OFFLINE_SIMULATION"
            or value.get("scientific_execution_authorized") is not False
            or value.get("runtime_feasibility_proven") is not False
        ):
            _fail("only an offline non-authorizing candidate is accepted")
        self.run_id = _hex(value.get("run_id"), 32, "mock run ID")
        self.seconds = _positive_int(value.get("max_session_seconds"), 14400, "mock time budget")
        self.budget = _positive_int(
            value.get("max_evidence_bytes"), 1048576, "mock evidence budget"
        )
        self.state_dir = _safe_directory(state_dir)
        self.custody = _safe_directory(custody)
        self.candidate = environment_candidate
        self.records: dict[str, tuple[int, str]] = {}
        self.state = "NEW"
        self.elapsed = 0

    def start(self) -> None:
        if self.state != "NEW":
            _fail("mock session already consumed")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        try:
            _write_new(
                self.state_dir / f"{self.run_id}.json",
                canonical_json_bytes(
                    {
                        "schema_version": "MESC-KAGGLE-OFFLINE-CONSUMPTION-V1",
                        "run_id": self.run_id,
                        "evidence_origin": "OFFLINE_SIMULATION",
                        "candidate_sha256": hashlib.sha256(self.candidate).hexdigest(),
                        "consumed": True,
                        "scientific_execution_authorized": False,
                    }
                ),
            )
        except FileExistsError as exc:
            self.state = "FAILED"
            raise KaggleAdapterError("mock grant already consumed") from exc
        self.state = "ACTIVE"
        try:
            self.custody.mkdir(parents=True, exist_ok=False)
            self._retain("environment.json", self.candidate)
        except (OSError, KaggleAdapterError) as exc:
            self.state = "FAILED"
            try:
                _write_new(
                    self.state_dir / f"{self.run_id}.setup-failure.json",
                    canonical_json_bytes(
                        {
                            "schema_version": "MESC-KAGGLE-OFFLINE-SETUP-FAILURE-V1",
                            "run_id": self.run_id,
                            "evidence_origin": "OFFLINE_SIMULATION",
                            "reason": "CUSTODY_SETUP_FAILED",
                            "error_type": type(exc).__name__,
                            "consumed": True,
                            "automatic_retry_authorized": False,
                            "scientific_execution_authorized": False,
                        }
                    ),
                )
            except OSError:
                _fail("mock setup/failure retention incomplete; consumed; no retry")
            raise KaggleAdapterError("mock setup failed after consumption; no retry") from exc

    def _failure(self, reason: str) -> Never:
        self.state = "FAILED"
        raw = canonical_json_bytes(
            {
                "schema_version": "MESC-KAGGLE-OFFLINE-FAILURE-V1",
                "run_id": self.run_id,
                "evidence_origin": "OFFLINE_SIMULATION",
                "reason": reason,
                "consumed": True,
                "automatic_retry_authorized": False,
                "scientific_execution_authorized": False,
            }
        )
        try:
            _write_new(self.custody / "failure.json", raw)
        except OSError:
            _fail("mock failure retention incomplete; consumed; no retry")
        _fail(reason)

    def _check_active(self, elapsed_seconds: int) -> None:
        if self.state != "ACTIVE":
            _fail("mock session is not active; no retry")
        if type(elapsed_seconds) is not int or not self.elapsed <= elapsed_seconds <= self.seconds:
            self._failure("timeout or non-monotonic mock clock")
        self.elapsed = elapsed_seconds

    def _retain(self, name: str, raw: bytes) -> None:
        if (
            type(raw) is not bytes
            or len(raw) + sum(row[0] for row in self.records.values()) > self.budget
        ):
            self._failure("evidence budget exceeded")
        try:
            _write_new(self.custody / name, raw)
        except OSError:
            self._failure("exclusive artifact retention failed")
        self.records[name] = (len(raw), hashlib.sha256(raw).hexdigest())

    def retain(self, name: str, raw: bytes, *, elapsed_seconds: int) -> None:
        self._check_active(elapsed_seconds)
        if name not in _RESULT_FILES:
            self._failure("unapproved artifact name")
        self._retain(name, raw)

    def interrupt(self) -> Never:
        self._check_active(self.elapsed)
        self._failure("interrupted; no repeat execution")

    def verify(self) -> bytes:
        rows: list[dict[str, object]] = []
        for name, (size, digest) in sorted(self.records.items()):
            path = self.custody / name
            try:
                if path.is_symlink():
                    self._failure("artifact is not an exclusive regular file")
                descriptor = os.open(
                    path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                )
                with os.fdopen(descriptor, "rb") as handle:
                    info = os.fstat(handle.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        self._failure("artifact is not an exclusive regular file")
                    if info.st_size != size:
                        self._failure("artifact byte/hash verification failed")
                    raw = handle.read(size + 1)
            except OSError:
                self._failure("artifact verification unavailable")
            if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
                self._failure("artifact byte/hash verification failed")
            rows.append({"path": name, "byte_count": size, "sha256": digest})
        return canonical_json_bytes(
            {
                "schema_version": "MESC-KAGGLE-OFFLINE-LOCAL-MANIFEST-V1",
                "run_id": self.run_id,
                "evidence_origin": "OFFLINE_SIMULATION",
                "artifacts": rows,
                "scientific_execution_authorized": False,
            }
        )

    def finish(self, *, elapsed_seconds: int) -> tuple[bytes, bytes]:
        self._check_active(elapsed_seconds)
        if set(self.records) != {"environment.json", *_RESULT_FILES}:
            self._failure("incomplete evidence bundle")
        manifest = self.verify()
        ack = canonical_json_bytes(
            {
                "schema_version": "MESC-KAGGLE-OFFLINE-HOST-ACK-V1",
                "run_id": self.run_id,
                "evidence_origin": "OFFLINE_SIMULATION",
                "manifest_sha256": hashlib.sha256(manifest).hexdigest(),
                "scientific_execution_authorized": False,
            }
        )
        try:
            _write_new(self.custody / "local-manifest.json", manifest)
            _write_new(self.custody / "host-ack.json", ack)
        except OSError:
            self._failure("final local retention failed; no retry")
        self.state = "COMPLETE_OFFLINE_ONLY"
        return manifest, ack
