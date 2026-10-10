#!/usr/bin/env python3
"""Read-only Colab Free control-plane observation for Recovery-3.

This program never allocates, purchases units, launches, retries or stops a
session. It never writes the provider endpoint or auth tokens to disk/stdout.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
from typing import Literal, cast

from medscale.mesc._mrl_0809_evidence_recovery_3_control_plane_v1 import (
    validate_recovery_3_control_plane,
)


def observe(phase: str, session_name: str) -> dict[str, object]:
    # Import in the function so static qualification never needs colab-cli.
    colab_client = importlib.import_module("colab_cli.client")
    state = importlib.import_module("colab_cli.common").state

    info = state.client.get_consumption_user_info()
    assignments = state.client.list_assignments()
    session: dict[str, object] | None = None
    if phase == "AFTER_ALLOCATION":
        entry = state.get_session(session_name)
        if entry is not None:
            # Endpoint comparison is in-memory only. The endpoint is private.
            if (
                len(assignments) != 1
                or assignments[0].endpoint != entry.endpoint
                or assignments[0].accelerator != colab_client.Accelerator.T4
                or assignments[0].variant != colab_client.AssignmentVariant.GPU
                or assignments[0].machine_shape != colab_client.Shape.STANDARD
            ):
                raise ValueError("provider assignment does not match frozen T4 identity")
            session = {
                "name": entry.name,
                "accelerator": entry.accelerator,
                "variant": entry.variant,
                "machine_shape": entry.machine_shape,
            }

    document: dict[str, object] = {
        "schema_version": "MESC-MRL-0809-EVIDENCE-RECOVERY-3-CONTROL-PLANE-V1",
        "phase": phase,
        "provider_class": "GOOGLE_COLAB_FREE",
        "paid_compute_units_balance": info.paid_compute_units_balance,
        "nominal_rate_hourly": info.consumption_rate_hourly,
        "account_assignments": info.assignments_count,
        "server_assignments": len(assignments),
        "session": session,
    }
    validate_recovery_3_control_plane(
        document,
        phase=cast(Literal["BEFORE_ALLOCATION", "AFTER_ALLOCATION"], phase),
        session_name=session_name,
    )
    return document


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("BEFORE_ALLOCATION", "AFTER_ALLOCATION"), required=True)
    parser.add_argument("--session", default="mesc-evidence-recovery-3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = observe(args.phase, args.session)
    raw = (
        json.dumps(
            document, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    print(json.dumps({"phase": args.phase, "verified": True, "nominal_rate_is_charge": False}))


if __name__ == "__main__":
    main()
