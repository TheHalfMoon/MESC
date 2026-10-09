#!/usr/bin/env python3
"""Private, bounded read-only Kaggle account/quota observation; no kernel push.

Run with an externally installed official Kaggle SDK. This does not install a
dependency, access model assets, allocate GPUs, or establish runtime authority.
Keep the account observation private. Never publish this command's raw result.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.metadata
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def _microseconds(duration: Any) -> int:
    fields = (duration.days, duration.seconds, duration.microseconds)
    if any(type(value) is not int for value in fields):
        raise ValueError("quota duration has non-integral components")
    days, seconds, micros = fields
    if days < 0 or not 0 <= seconds < 86400 or not 0 <= micros < 1000000:
        raise ValueError("quota duration is not nonnegative and normalized")
    return int((days * 86400 + seconds) * 1000000 + micros)


def observe(api: Any) -> dict[str, object]:
    """Use only official authenticate, personal listing and optional quota view."""
    api.authenticate()
    notebooks = api.kernels_list(mine=True, page_size=5, page=1)
    if type(notebooks) is not list:
        raise ValueError("personal notebook observation unavailable")
    result: dict[str, object] = {
        "schema_version": "MESC-KAGGLE-PRIVATE-READONLY-OBSERVATION-V1",
        "authenticated_personal_listing_succeeded": True,
        "sample_notebook_count": len(notebooks),
        "quota_state": "UNKNOWN",
        "gpu_capacity_state": "UNKNOWN",
        "allocation_performed": False,
        "scientific_execution_authorized": False,
        "paid_compute_requested": False,
    }
    quota_view = getattr(api, "quota_view", None)
    if not callable(quota_view):
        result["quota_limitation"] = "SUPPORTED_QUOTA_METHOD_ABSENT"
        return result
    try:
        response = quota_view()
        gpu = response.gpu_quota
        if gpu is None:
            result["quota_limitation"] = "PROVIDER_RETURNED_NO_GPU_QUOTA"
            return result
        total, used = _microseconds(gpu.total_time_allowed), _microseconds(gpu.time_used)
        if used > total:
            raise ValueError("quota used exceeds observed total")
        result.update(
            quota_state="OBSERVED_NOT_CAPACITY_GUARANTEE",
            gpu_total_microseconds=total,
            gpu_used_microseconds=used,
            gpu_remaining_seconds=(total - used) // 1000000,
        )
    except Exception as exc:
        # Exception text can contain credential/account identifiers. Retain only type.
        result["quota_limitation"] = type(exc).__name__
    return result


def _worker() -> int:
    # Third-party import/auth diagnostics are never copied to stdout or evidence.
    with (
        Path(os.devnull).open("w", encoding="utf-8") as discarded,
        contextlib.redirect_stdout(discarded),
        contextlib.redirect_stderr(discarded),
    ):
        try:
            module = importlib.import_module("kaggle.api.kaggle_api_extended")
            result = observe(module.KaggleApi())
            result["official_sdk_version"] = importlib.metadata.version("kaggle")
        except Exception as exc:
            result = {
                "read_only_observation": "UNAVAILABLE",
                "error_type": type(exc).__name__,
                "allocation_performed": False,
                "scientific_execution_authorized": False,
            }
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 1 if result.get("read_only_observation") == "UNAVAILABLE" else 0


def main() -> None:
    if sys.argv[1:] == ["--worker"]:
        raise SystemExit(_worker())
    if sys.argv[1:]:
        raise SystemExit("This read-only observer accepts no account or credential arguments")
    try:
        with tempfile.TemporaryFile(mode="w+b") as captured:
            result = subprocess.run(
                (sys.executable, str(Path(__file__).resolve()), "--worker"),
                check=False,
                stdout=captured,
                stderr=subprocess.DEVNULL,
                timeout=45,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            captured.seek(0)
            raw = captured.read(8193)
    except subprocess.TimeoutExpired:
        print(
            json.dumps(
                {
                    "read_only_observation": "UNAVAILABLE",
                    "error_type": "TimeoutExpired",
                    "allocation_performed": False,
                    "scientific_execution_authorized": False,
                }
            )
        )
        raise SystemExit(1) from None
    # The worker suppresses third-party text. Validate its output before forwarding.
    try:
        if len(raw) > 8192:
            raise ValueError("oversized worker observation")
        observation = json.loads(raw)
        if type(observation) is not dict or observation.get("allocation_performed") is not False:
            raise ValueError("invalid worker observation")
    except ValueError:
        print(
            json.dumps(
                {
                    "read_only_observation": "UNAVAILABLE",
                    "error_type": "InvalidWorkerOutput",
                    "allocation_performed": False,
                    "scientific_execution_authorized": False,
                }
            )
        )
        raise SystemExit(1) from None
    print(json.dumps(observation, sort_keys=True, allow_nan=False))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
