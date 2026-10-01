"""Fail-closed CUDA device-placement audit for MRL-0809 successor repair.

This module is repository-only repair infrastructure authorized by
FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1. It does not authorize a hosted
runtime attempt. The audit treats materialized tensor placement as the primary
source of truth and uses ``hf_device_map`` only as additional evidence when it
is present.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

PLACEMENT_AUDIT_SCHEMA: Final = "MESC-MRL-0809-PLACEMENT-AUDIT-V1"
CUDA0: Final = "cuda:0"


class PlacementAuditError(RuntimeError):
    """Raised when device placement cannot be proven to be CUDA device 0 only."""


def _metadata_target(target: object) -> str:
    if type(target) is int:
        if target == 0:
            return CUDA0
        raise PlacementAuditError(f"device map targets forbidden CUDA device {target}")

    if type(target) is str:
        normalized = target.strip().lower()
        if normalized in {"cuda", CUDA0}:
            return CUDA0
        if normalized in {"cpu", "disk", "meta"}:
            raise PlacementAuditError(f"device map contains prohibited target {normalized}")
        raise PlacementAuditError(
            f"device map target is not deterministically auditable: {target!r}"
        )

    device_type = getattr(target, "type", None)
    device_index = getattr(target, "index", None)
    if device_type == "cuda" and device_index in (None, 0):
        return CUDA0
    if device_type in {"cpu", "meta"}:
        raise PlacementAuditError(f"device map contains prohibited target {device_type}")
    if device_type == "cuda" and type(device_index) is int:
        raise PlacementAuditError(f"device map targets forbidden CUDA device {device_index}")
    raise PlacementAuditError(
        f"device map target is not deterministically auditable: {type(target).__name__}"
    )


def _tensor_device(tensor: object, *, kind: str, name: str) -> str:
    device = getattr(tensor, "device", None)
    if device is None:
        raise PlacementAuditError(f"{kind} {name!r} has no auditable device")

    if type(device) is str:
        normalized = device.strip().lower()
        if normalized == CUDA0:
            return CUDA0
        if normalized in {"cpu", "meta", "cuda"}:
            raise PlacementAuditError(
                f"{kind} {name!r} is on prohibited/ambiguous device {normalized}"
            )
        if normalized.startswith("cuda:"):
            raise PlacementAuditError(
                f"{kind} {name!r} is not on CUDA device 0: {normalized}"
            )
        raise PlacementAuditError(f"{kind} {name!r} has unrecognized device {device!r}")

    device_type = getattr(device, "type", None)
    device_index = getattr(device, "index", None)
    if device_type == "cuda" and device_index == 0:
        return CUDA0
    if device_type == "cuda":
        raise PlacementAuditError(
            f"{kind} {name!r} is not on CUDA device 0: cuda:{device_index}"
        )
    if device_type in {"cpu", "meta"}:
        raise PlacementAuditError(f"{kind} {name!r} is on prohibited device {device_type}")
    raise PlacementAuditError(
        f"{kind} {name!r} has unrecognized device type {device_type!r}"
    )


def _named_tensors(model: object, method_name: str, *, kind: str) -> list[tuple[str, object]]:
    method = getattr(model, method_name, None)
    if not callable(method):
        raise PlacementAuditError(f"model does not expose callable {method_name}()")
    try:
        rows = list(method(recurse=True))
    except TypeError:
        rows = list(method())
    except Exception as exc:  # pragma: no cover - defensive fail-closed boundary
        raise PlacementAuditError(f"{method_name}() failed during placement audit") from exc

    result: list[tuple[str, object]] = []
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 2 or type(row[0]) is not str:
            raise PlacementAuditError(f"{method_name}() returned a malformed {kind} entry")
        name, tensor = row
        if tensor is None:
            raise PlacementAuditError(f"{kind} {name!r} is not materialized")
        result.append((name, tensor))
    return result


def audit_model_cuda0_placement(model: object) -> dict[str, Any]:
    """Prove that every materialized parameter and buffer is on CUDA device 0.

    Actual tensor placement is authoritative. A present ``hf_device_map`` is
    validated independently and may only add evidence; it can never override a
    contradictory parameter/buffer placement.
    """

    dynamic_model: Any = model
    device_map = dynamic_model.hf_device_map if hasattr(dynamic_model, "hf_device_map") else None
    map_present = device_map is not None
    map_entries = 0
    if map_present:
        if not isinstance(device_map, Mapping) or not device_map:
            raise PlacementAuditError("present hf_device_map is empty or not a mapping")
        for key, target in device_map.items():
            if type(key) is not str or not key:
                raise PlacementAuditError("hf_device_map contains a non-canonical module key")
            _metadata_target(target)
            map_entries += 1

    parameters = _named_tensors(model, "named_parameters", kind="parameter")
    buffers = _named_tensors(model, "named_buffers", kind="buffer")
    if not parameters and not buffers:
        raise PlacementAuditError("no materialized parameters or buffers were available to audit")

    for name, tensor in parameters:
        _tensor_device(tensor, kind="parameter", name=name)
    for name, tensor in buffers:
        _tensor_device(tensor, kind="buffer", name=name)

    return {
        "all_materialized_tensors_on_cuda_device_0": True,
        "buffer_count": len(buffers),
        "hf_device_map_entry_count": map_entries,
        "hf_device_map_present": map_present,
        "parameter_count": len(parameters),
        "schema_version": PLACEMENT_AUDIT_SCHEMA,
        "tensor_count": len(parameters) + len(buffers),
    }
