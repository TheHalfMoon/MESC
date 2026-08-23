"""Fixture-only Backbone Tournament telemetry measurement primitives.

This module validates synthetic telemetry observations and computes deterministic
measurement evidence. It performs no NVML calls, filesystem I/O, network access,
provider access, model access, prompt construction, inference, or credential work.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

GPU_MODEL_H100: Final = "NVIDIA H100 80GB HBM3"
MAX_SAMPLE_INTERVAL_MS: Final = 100
_MIB: Final = 1024 * 1024


class FixtureTelemetryError(ValueError):
    """Base class for fixture telemetry contract failures."""


class FixtureTelemetryBlockedError(FixtureTelemetryError):
    """A fail-closed telemetry condition that blocks qualification."""


@dataclass(frozen=True, slots=True)
class ProcessMemoryObservation:
    """One process observation in a synthetic NVML-style frame."""

    pid: int
    parent_pid: int | None
    used_memory_bytes: int
    is_compute_process: bool


@dataclass(frozen=True, slots=True)
class TelemetryFrame:
    """One synthetic GPU telemetry sampling frame."""

    monotonic_ns: int
    gpu_uuid: str
    gpu_model: str
    processes: tuple[ProcessMemoryObservation, ...]


@dataclass(frozen=True, slots=True)
class LatencyProbe:
    """Synthetic monotonic timing probe used by no-model qualification."""

    start_monotonic_ns: int
    end_monotonic_ns: int
    elapsed_ns: int


@dataclass(frozen=True, slots=True)
class FixtureTelemetryQualification:
    """Caller-supplied synthetic telemetry qualification evidence."""

    gpu_uuid: str
    gpu_model: str
    sampling_interval_ms: int
    controlled_root_pid: int
    monitor_start_ns: int
    model_load_or_probe_start_ns: int
    final_terminal_ns: int
    device_sync_completed_ns: int
    monitor_stop_ns: int
    latency_probe: LatencyProbe
    frames: tuple[TelemetryFrame, ...]


@dataclass(frozen=True, slots=True)
class FixtureTelemetryResult:
    """Deterministic result derived from validated synthetic telemetry."""

    peak_vram_mb: float
    controlled_process_peak_bytes: int
    frame_count: int
    latency_probe_ns: int
    evidence_bytes: bytes
    evidence_sha256: str


def qualify_fixture_telemetry(
    qualification: FixtureTelemetryQualification,
) -> FixtureTelemetryResult:
    """Validate synthetic telemetry and compute a deterministic qualification result."""
    _validate_ascii_identity(qualification.gpu_uuid, field="gpu_uuid")
    if qualification.gpu_model != GPU_MODEL_H100:
        raise FixtureTelemetryBlockedError(f"gpu_model must be exactly {GPU_MODEL_H100!r}")
    _require_exact_positive_int(qualification.sampling_interval_ms, field="sampling_interval_ms")
    if qualification.sampling_interval_ms > MAX_SAMPLE_INTERVAL_MS:
        raise FixtureTelemetryBlockedError("sampling_interval_ms must be no greater than 100")
    _require_exact_positive_int(qualification.controlled_root_pid, field="controlled_root_pid")
    for field, value in (
        ("monitor_start_ns", qualification.monitor_start_ns),
        ("model_load_or_probe_start_ns", qualification.model_load_or_probe_start_ns),
        ("final_terminal_ns", qualification.final_terminal_ns),
        ("device_sync_completed_ns", qualification.device_sync_completed_ns),
        ("monitor_stop_ns", qualification.monitor_stop_ns),
    ):
        _require_exact_nonnegative_int(value, field=field)

    if qualification.monitor_start_ns > qualification.model_load_or_probe_start_ns:
        raise FixtureTelemetryBlockedError("monitoring must start before model/probe start")
    if qualification.final_terminal_ns > qualification.device_sync_completed_ns:
        raise FixtureTelemetryBlockedError(
            "device synchronization must not precede terminal completion"
        )
    if qualification.device_sync_completed_ns > qualification.monitor_stop_ns:
        raise FixtureTelemetryBlockedError(
            "monitoring must not stop before device synchronization completes"
        )

    _validate_latency_probe(qualification.latency_probe)
    frames = qualification.frames
    if not frames:
        raise FixtureTelemetryBlockedError("at least one telemetry frame is required")

    max_gap_ns = MAX_SAMPLE_INTERVAL_MS * 1_000_000
    previous_ts: int | None = None
    peak_bytes = 0
    frame_documents: list[dict[str, object]] = []

    for frame in frames:
        _require_exact_nonnegative_int(frame.monotonic_ns, field="frame.monotonic_ns")
        if frame.gpu_uuid != qualification.gpu_uuid:
            raise FixtureTelemetryBlockedError("telemetry frame gpu_uuid mismatch")
        if frame.gpu_model != qualification.gpu_model:
            raise FixtureTelemetryBlockedError("telemetry frame gpu_model mismatch")
        if frame.monotonic_ns < qualification.monitor_start_ns:
            raise FixtureTelemetryBlockedError("telemetry frame predates monitor start")
        if frame.monotonic_ns > qualification.monitor_stop_ns:
            raise FixtureTelemetryBlockedError("telemetry frame exceeds monitor stop")
        if previous_ts is not None:
            if frame.monotonic_ns <= previous_ts:
                raise FixtureTelemetryBlockedError(
                    "telemetry frame timestamps must be strictly increasing"
                )
            if frame.monotonic_ns - previous_ts > max_gap_ns:
                raise FixtureTelemetryBlockedError("telemetry frame gap exceeds 100 ms")
        previous_ts = frame.monotonic_ns

        owned_pids = _controlled_process_tree(frame.processes, qualification.controlled_root_pid)
        unexpected = tuple(
            item.pid
            for item in frame.processes
            if item.is_compute_process and item.pid not in owned_pids
        )
        if unexpected:
            raise FixtureTelemetryBlockedError(
                f"unexpected GPU compute process detected: {unexpected[0]}"
            )
        aggregate_bytes = sum(
            item.used_memory_bytes for item in frame.processes if item.pid in owned_pids
        )
        peak_bytes = max(peak_bytes, aggregate_bytes)
        frame_documents.append(
            {
                "aggregate_controlled_memory_bytes": aggregate_bytes,
                "controlled_process_ids": sorted(owned_pids),
                "gpu_model": frame.gpu_model,
                "gpu_uuid": frame.gpu_uuid,
                "monotonic_ns": frame.monotonic_ns,
                "processes": [
                    {
                        "is_compute_process": item.is_compute_process,
                        "parent_pid": item.parent_pid,
                        "pid": item.pid,
                        "used_memory_bytes": item.used_memory_bytes,
                    }
                    for item in sorted(frame.processes, key=lambda item: item.pid)
                ],
            }
        )

    first_frame_ns = frames[0].monotonic_ns
    last_frame_ns = frames[-1].monotonic_ns
    if first_frame_ns > qualification.model_load_or_probe_start_ns:
        raise FixtureTelemetryBlockedError(
            "first telemetry frame must be at or before model/probe start"
        )
    if last_frame_ns < qualification.device_sync_completed_ns:
        raise FixtureTelemetryBlockedError(
            "terminal telemetry capture must occur after device synchronization"
        )

    peak_vram_mb = peak_bytes / _MIB
    if not math.isfinite(peak_vram_mb) or peak_vram_mb < 0:
        raise FixtureTelemetryBlockedError("peak_vram_mb must be finite and non-negative")

    document = {
        "controlled_process_peak_bytes": peak_bytes,
        "controlled_root_pid": qualification.controlled_root_pid,
        "device_sync_completed_ns": qualification.device_sync_completed_ns,
        "final_terminal_ns": qualification.final_terminal_ns,
        "frame_count": len(frames),
        "frames": frame_documents,
        "gpu_model": qualification.gpu_model,
        "gpu_uuid": qualification.gpu_uuid,
        "latency_probe": {
            "elapsed_ns": qualification.latency_probe.elapsed_ns,
            "end_monotonic_ns": qualification.latency_probe.end_monotonic_ns,
            "start_monotonic_ns": qualification.latency_probe.start_monotonic_ns,
        },
        "model_load_or_probe_start_ns": qualification.model_load_or_probe_start_ns,
        "monitor_start_ns": qualification.monitor_start_ns,
        "monitor_stop_ns": qualification.monitor_stop_ns,
        "peak_vram_mb": peak_vram_mb,
        "sampling_interval_ms": qualification.sampling_interval_ms,
    }
    evidence_bytes = _canonical_json(document)
    return FixtureTelemetryResult(
        peak_vram_mb=peak_vram_mb,
        controlled_process_peak_bytes=peak_bytes,
        frame_count=len(frames),
        latency_probe_ns=qualification.latency_probe.elapsed_ns,
        evidence_bytes=evidence_bytes,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )


def _controlled_process_tree(
    processes: Sequence[ProcessMemoryObservation],
    root_pid: int,
) -> frozenset[int]:
    by_pid: dict[int, ProcessMemoryObservation] = {}
    for item in processes:
        _validate_process_observation(item)
        if item.pid in by_pid:
            raise FixtureTelemetryBlockedError(f"duplicate process pid: {item.pid}")
        by_pid[item.pid] = item

    root = by_pid.get(root_pid)
    if root is None:
        raise FixtureTelemetryBlockedError("controlled root process is missing")
    if root.parent_pid is not None:
        raise FixtureTelemetryBlockedError(
            "controlled root process must have parent_pid=None in fixture evidence"
        )

    for item in processes:
        if item.parent_pid is not None and item.parent_pid not in by_pid:
            raise FixtureTelemetryBlockedError(
                f"process parent is missing from telemetry frame: {item.pid}"
            )

    owned: set[int] = set()
    for pid in by_pid:
        chain_seen: set[int] = set()
        cursor = pid
        while True:
            if cursor in chain_seen:
                raise FixtureTelemetryBlockedError("process parent graph contains a cycle")
            chain_seen.add(cursor)
            if cursor == root_pid:
                owned.add(pid)
                break
            parent = by_pid[cursor].parent_pid
            if parent is None:
                break
            cursor = parent
    return frozenset(owned)


def _validate_process_observation(item: ProcessMemoryObservation) -> None:
    _require_exact_positive_int(item.pid, field="process.pid")
    if item.parent_pid is not None:
        _require_exact_positive_int(item.parent_pid, field="process.parent_pid")
        if item.parent_pid == item.pid:
            raise FixtureTelemetryBlockedError("process may not parent itself")
    _require_exact_nonnegative_int(item.used_memory_bytes, field="process.used_memory_bytes")
    _require_exact_bool(item.is_compute_process, field="process.is_compute_process")


def _validate_latency_probe(probe: LatencyProbe) -> None:
    for field, value in (
        ("latency_probe.start_monotonic_ns", probe.start_monotonic_ns),
        ("latency_probe.end_monotonic_ns", probe.end_monotonic_ns),
        ("latency_probe.elapsed_ns", probe.elapsed_ns),
    ):
        _require_exact_nonnegative_int(value, field=field)
    if probe.end_monotonic_ns < probe.start_monotonic_ns:
        raise FixtureTelemetryBlockedError("latency probe end precedes start")
    if probe.elapsed_ns != probe.end_monotonic_ns - probe.start_monotonic_ns:
        raise FixtureTelemetryBlockedError("latency probe elapsed_ns does not match timestamps")


def _validate_ascii_identity(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise FixtureTelemetryBlockedError(f"{field} must be a non-empty string")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise FixtureTelemetryBlockedError(f"{field} must be ASCII") from error
    if any(byte < 0x20 or byte > 0x7E or byte in {0x22, 0x5C} for byte in encoded):
        raise FixtureTelemetryBlockedError(f"{field} contains a prohibited ASCII byte")
    return value


def _require_exact_bool(value: object, *, field: str) -> bool:
    if type(value) is not bool:
        raise FixtureTelemetryBlockedError(f"{field} must be boolean")
    return value


def _require_exact_positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise FixtureTelemetryBlockedError(f"{field} must be an integer >= 1")
    return value


def _require_exact_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise FixtureTelemetryBlockedError(f"{field} must be an integer >= 0")
    return value


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
