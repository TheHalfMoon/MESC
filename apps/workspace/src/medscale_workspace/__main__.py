"""Command-line entry point for the synthetic CW-001 Workspace shell."""

from __future__ import annotations

import json

from medscale_workspace.data_class import synthetic_data_class_value


def main() -> int:
    """Emit only non-object startup metadata.

    Patient and encounter data must never be written to stdout/stderr by the
    Workspace entry point, even while fixtures are synthetic.
    """

    status = {
        "application": "medscale-workspace",
        "data_class": synthetic_data_class_value(),
        "mode": "offline-shell",
        "ready": True,
    }
    print(json.dumps(status, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
