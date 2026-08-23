from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._bt_telemetry_fixture_v1 import (
    CLOCK_SOURCE_MONOTONIC_NS,
    GPU_MODEL_H100,
    FixtureTelemetryBlockedError,
    FixtureTelemetryQualification,
    LatencyProbe,
    ProcessMemoryObservation,
    TelemetryFrame,
    qualify_fixture_telemetry,
)

MIB = 1024 * 1024


def _process(
    pid: int,
    parent_pid: int | None,
    memory_mib: int,
    *,
    compute: bool = True,
) -> ProcessMemoryObservation:
    return ProcessMemoryObservation(
        pid=pid,
        parent_pid=parent_pid,
        used_memory_bytes=memory_mib * MIB,
        is_compute_process=compute,
    )


def _frame(
    timestamp_ns: int,
    *processes: ProcessMemoryObservation,
    gpu_uuid: str = "GPU-fixture-001",
    gpu_model: str = GPU_MODEL_H100,
) -> TelemetryFrame:
    return TelemetryFrame(
        monotonic_ns=timestamp_ns,
        gpu_uuid=gpu_uuid,
        gpu_model=gpu_model,
        processes=tuple(processes),
    )


def _qualification() -> FixtureTelemetryQualification:
    root = _process(100, None, 1000)
    child = _process(101, 100, 250)
    system = _process(900, None, 0, compute=False)
    return FixtureTelemetryQualification(
        gpu_uuid="GPU-fixture-001",
        gpu_model=GPU_MODEL_H100,
        clock_source=CLOCK_SOURCE_MONOTONIC_NS,
        sampling_interval_ms=100,
        controlled_root_pid=100,
        monitor_start_ns=0,
        model_load_or_probe_start_ns=25_000_000,
        final_terminal_ns=150_000_000,
        device_sync_completed_ns=175_000_000,
        monitor_stop_ns=200_000_000,
        latency_probe=LatencyProbe(
            start_monotonic_ns=10,
            end_monotonic_ns=30,
            elapsed_ns=20,
        ),
        frames=(
            _frame(0, root, system),
            _frame(100_000_000, root, child, system),
            _frame(
                176_000_000,
                replace(root, used_memory_bytes=1200 * MIB),
                child,
                system,
            ),
        ),
    )


def test_qualification_computes_aggregate_peak_and_hash() -> None:
    result = qualify_fixture_telemetry(_qualification())
    assert result.controlled_process_peak_bytes == 1450 * MIB
    assert result.peak_vram_mb == 1450.0
    assert result.frame_count == 3
    assert result.latency_probe_ns == 20
    assert len(result.evidence_sha256) == 64
    assert b'"clock_source":"monotonic_ns"' in result.evidence_bytes
    assert not result.evidence_bytes.endswith(b"\n")


def test_deterministic_process_input_order() -> None:
    qualification = _qualification()
    reversed_frames = tuple(
        replace(frame, processes=tuple(reversed(frame.processes))) for frame in qualification.frames
    )
    first = qualify_fixture_telemetry(qualification)
    second = qualify_fixture_telemetry(replace(qualification, frames=reversed_frames))
    assert first == second


def test_sampling_interval_over_100_ms_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="no greater than 100"):
        qualify_fixture_telemetry(replace(_qualification(), sampling_interval_ms=101))


def test_boolean_sampling_interval_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="integer"):
        qualify_fixture_telemetry(replace(_qualification(), sampling_interval_ms=True))


def test_wrong_gpu_model_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="gpu_model"):
        qualify_fixture_telemetry(replace(_qualification(), gpu_model="NVIDIA H100"))


def test_wrong_clock_source_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="clock_source"):
        qualify_fixture_telemetry(replace(_qualification(), clock_source="wall_clock_ns"))


def test_frame_gpu_uuid_mismatch_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = replace(frames[1], gpu_uuid="GPU-other")
    with pytest.raises(FixtureTelemetryBlockedError, match="gpu_uuid mismatch"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_duplicate_pid_blocks() -> None:
    qualification = _qualification()
    root = _process(100, None, 1000)
    frames = list(qualification.frames)
    frames[1] = _frame(100_000_000, root, root)
    with pytest.raises(FixtureTelemetryBlockedError, match="duplicate process pid"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_missing_root_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(100_000_000, _process(900, None, 0, compute=False))
    with pytest.raises(FixtureTelemetryBlockedError, match="root process is missing"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_root_parent_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        _process(99, None, 0, compute=False),
        _process(100, 99, 1000),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="parent_pid=None"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_missing_parent_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        _process(100, None, 1000),
        _process(101, 999, 100),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="parent is missing"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_parent_cycle_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        _process(100, None, 1000),
        _process(101, 102, 100),
        _process(102, 101, 100),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="contains a cycle"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_unexpected_compute_process_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        _process(100, None, 1000),
        _process(700, None, 1, compute=True),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="unexpected GPU compute process"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_noncompute_unrelated_process_is_allowed() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        _process(100, None, 1000),
        _process(700, None, 300, compute=False),
    )
    result = qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))
    assert result.controlled_process_peak_bytes == 1450 * MIB


def test_non_monotonic_frame_timestamps_block() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = replace(frames[1], monotonic_ns=0)
    with pytest.raises(FixtureTelemetryBlockedError, match="strictly increasing"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_frame_gap_over_100_ms_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = replace(frames[1], monotonic_ns=100_000_001)
    with pytest.raises(FixtureTelemetryBlockedError, match="gap exceeds 100 ms"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_first_frame_after_probe_start_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[0] = replace(frames[0], monotonic_ns=10)
    with pytest.raises(FixtureTelemetryBlockedError, match="first telemetry frame"):
        qualify_fixture_telemetry(
            replace(
                qualification,
                model_load_or_probe_start_ns=5,
                frames=tuple(frames),
            )
        )


def test_monitor_start_equal_probe_start_blocks() -> None:
    qualification = _qualification()
    with pytest.raises(FixtureTelemetryBlockedError, match="start before"):
        qualify_fixture_telemetry(
            replace(
                qualification,
                monitor_start_ns=qualification.model_load_or_probe_start_ns,
            )
        )


def test_sync_before_terminal_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="synchronization"):
        qualify_fixture_telemetry(replace(_qualification(), device_sync_completed_ns=149_999_999))


def test_terminal_equal_sync_blocks() -> None:
    qualification = _qualification()
    with pytest.raises(FixtureTelemetryBlockedError, match="precede"):
        qualify_fixture_telemetry(
            replace(
                qualification,
                final_terminal_ns=qualification.device_sync_completed_ns,
            )
        )


def test_stop_before_sync_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="stop before"):
        qualify_fixture_telemetry(replace(_qualification(), monitor_stop_ns=174_999_999))


def test_last_frame_before_sync_blocks() -> None:
    qualification = _qualification()
    frames = (
        *qualification.frames[:-1],
        replace(qualification.frames[-1], monotonic_ns=174_999_999),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="after device synchronization"):
        qualify_fixture_telemetry(replace(qualification, frames=frames))


def test_last_frame_equal_sync_blocks() -> None:
    qualification = _qualification()
    frames = (
        *qualification.frames[:-1],
        replace(
            qualification.frames[-1],
            monotonic_ns=qualification.device_sync_completed_ns,
        ),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="after device synchronization"):
        qualify_fixture_telemetry(replace(qualification, frames=frames))


def test_latency_elapsed_mismatch_blocks() -> None:
    probe = replace(_qualification().latency_probe, elapsed_ns=21)
    with pytest.raises(FixtureTelemetryBlockedError, match="elapsed_ns"):
        qualify_fixture_telemetry(replace(_qualification(), latency_probe=probe))


def test_negative_memory_blocks() -> None:
    qualification = _qualification()
    frames = list(qualification.frames)
    frames[1] = _frame(
        100_000_000,
        ProcessMemoryObservation(
            pid=100,
            parent_pid=None,
            used_memory_bytes=-1,
            is_compute_process=True,
        ),
    )
    with pytest.raises(FixtureTelemetryBlockedError, match="used_memory_bytes"):
        qualify_fixture_telemetry(replace(qualification, frames=tuple(frames)))


def test_non_ascii_gpu_uuid_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="ASCII"):
        qualify_fixture_telemetry(replace(_qualification(), gpu_uuid="GPU-é"))


def test_empty_frames_blocks() -> None:
    with pytest.raises(FixtureTelemetryBlockedError, match="at least one"):
        qualify_fixture_telemetry(replace(_qualification(), frames=()))
