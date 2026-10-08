#!/usr/bin/env python3
"""Pre-probe CUDA BMM portability smoke for the MRL-0809 successor repair."""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import sys
from typing import Any, Final

SCHEMA: Final = "MESC-MRL-0809-BMM-PORTABILITY-PREFLIGHT-V1"
EXPECTED_TORCH: Final = "2.13.0"


class BMMPortabilityError(RuntimeError):
    """The isolated runtime cannot satisfy the bounded BMM compatibility policy."""


def _disable_native_bmm_override() -> None:
    try:
        registry: Any = importlib.import_module("torch._native.registry")
        deregister = registry.deregister_op_overrides
        if not callable(deregister):
            raise TypeError("deregister_op_overrides is not callable")
        deregister(disable_op_symbols="bmm")
    except Exception as exc:
        raise BMMPortabilityError(
            "failed to disable the experimental torch native bmm override"
        ) from exc


def main() -> None:
    if importlib.metadata.version("torch") != EXPECTED_TORCH:
        raise BMMPortabilityError("torch package identity drifted")
    torch: Any = importlib.import_module("torch")
    _disable_native_bmm_override()
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise BMMPortabilityError("preflight requires exactly one CUDA GPU")

    left = torch.ones((1, 2, 1), device=torch.device("cuda:0"), dtype=torch.float32)
    right = torch.ones((1, 1, 3), device=torch.device("cuda:0"), dtype=torch.float32)
    result = torch.bmm(left, right)
    expected = torch.ones((1, 2, 3), device=torch.device("cuda:0"), dtype=torch.float32)
    torch.cuda.synchronize()
    if not bool(torch.equal(result, expected)):
        raise BMMPortabilityError("CUDA bmm result drifted")

    document = {
        "bmm_result_verified": True,
        "cuda_device_count": 1,
        "disabled_op_symbols": ["bmm"],
        "schema_version": SCHEMA,
        "torch_version": EXPECTED_TORCH,
    }
    sys.stdout.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
