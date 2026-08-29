"""Generate or verify deterministic MRL machine-state projections."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    generate_machine_state,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="medscale mesc-machine-state",
        description=(
            "Generate or check non-authoritative MRL machine-state projections for the "
            "exact local Git HEAD."
        ),
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=Path.cwd(),
        help="Git repository root to represent (default: current directory)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory containing CAPABILITY_MATRIX.json, PROJECT_STATE.json, and "
        "RESEARCH_PROGRAM_INDEX.json",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify existing projection bytes instead of writing outputs",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run deterministic machine-state generation/checking."""
    args = _parser().parse_args(argv)
    try:
        render_set = generate_machine_state(
            args.repository_root,
            args.output_dir,
            check=args.check,
        )
    except MachineStateGenerationError as exc:
        print(f"mesc-machine-state: {exc}", file=sys.stderr)
        return 1

    action = "verified" if args.check else "generated"
    print(
        f"{action} MRL machine state for commit {render_set.commit_sha} tree {render_set.tree_sha}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
