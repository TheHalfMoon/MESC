"""CLI for the deterministic fixture-only MESC golden-path smoke."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from medscale.mesc._mrl_fixture_smoke_v1 import build_fixture_smoke_payload
from medscale.reproducibility import canonical_json

DESCRIPTION = (
    "Run the deterministic offline fixture-only MESC plumbing smoke. "
    "This command uses no model, network, GPU, credentials, real data, or training and "
    "produces non-evidence only."
)


def _parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        prog="medscale mesc-fixture-smoke",
        description=DESCRIPTION,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Emit one canonical fixture-only golden-path summary to stdout."""

    _parser().parse_args(argv)
    sys.stdout.write(canonical_json(build_fixture_smoke_payload()))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
