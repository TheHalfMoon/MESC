"""Command-line entry point for the synthetic CW-001 Workspace shell."""

from __future__ import annotations

import json

from medscale_workspace.app import workspace_snapshot


def main() -> int:
    print(json.dumps(workspace_snapshot(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
