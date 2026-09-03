"""The `medscale` command-line entry point.

A thin dispatcher over subcommands. Kept deliberately minimal — no framework, just argv
dispatch.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Sequence

from medscale.__about__ import __version__
from medscale.cli import bench as bench_cli
from medscale.cli import check as check_cli
from medscale.cli import dataset as dataset_cli
from medscale.cli import extract as extract_cli
from medscale.cli import fhir as fhir_cli
from medscale.cli import mesc_b1_eval as mesc_b1_eval_cli
from medscale.cli import mesc_b1_evidence as mesc_b1_evidence_cli
from medscale.cli import mesc_eval as mesc_eval_cli
from medscale.cli import mesc_fixture_smoke as mesc_fixture_smoke_cli
from medscale.cli import mesc_machine_state as mesc_machine_state_cli
from medscale.cli import research as research_cli
from medscale.cli import screen as screen_cli

_SUBCOMMANDS = {
    "screen": screen_cli.main,
    "extract": extract_cli.main,
    "check": check_cli.main,
    "stats": research_cli.stats_main,
    "snapshot": research_cli.snapshot_main,
    "bench": bench_cli.main,
    "dataset": dataset_cli.main,
    "fhir": fhir_cli.main,
    "mesc-eval": mesc_eval_cli.main,
    "mesc-b1-eval": mesc_b1_eval_cli.main,
    "mesc-b1-evidence": mesc_b1_evidence_cli.main,
    "mesc-machine-state": mesc_machine_state_cli.main,
    "mesc-fixture-smoke": mesc_fixture_smoke_cli.main,
}


def _never_crash_on_console_encoding() -> None:
    """Record titles/abstracts are arbitrary Unicode; Windows consoles are often cp1252.

    Unencodable characters degrade to ``?`` instead of killing a screening session.
    """
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main(argv: Sequence[str] | None = None) -> int:
    _never_crash_on_console_encoding()
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in ("--version", "-V"):
        print(f"medscale {__version__}")
        return 0
    if not args or args[0] in ("-h", "--help"):
        print("usage: medscale <command> [options]")
        print("\ncommands:\n  screen   human literature screening (status/duplicates/next/amend)")
        print("  extract  turn INCLUDED records into verified Evidence Objects")
        print("  check    verify corpus/log/evidence referential integrity")
        print("  stats    machine-readable corpus/screening/evidence statistics")
        print("  snapshot capture or --verify a citable knowledge-state identity")
        print("  bench    list/validate/run snapshot-bound evidence benchmarks")
        print("  dataset  init/preview/validate/freeze deterministic dataset artifacts")
        print("  fhir     validate FHIR payloads and store deterministic reports")
        print("  mesc-eval deterministic B0 zero-shot evaluation (research baseline)")
        print("  mesc-b1-eval deterministic B1 evidence-cued baseline (research)")
        print("  mesc-b1-evidence deterministic B1 evidence tooling: subset/annotate/cues")
        print("  mesc-machine-state generate/check deterministic MRL state projections")
        print("  mesc-fixture-smoke deterministic offline fixture-only plumbing smoke")
        print("\nrun `medscale <command> --help` for options and examples;")
        print("new here? start with docs/guides/research_quickstart.md")
        return 0 if args else 1
    command, rest = args[0], args[1:]
    handler = _SUBCOMMANDS.get(command)
    if handler is None:
        print(
            f"unknown command {command!r}; known: {', '.join(sorted(_SUBCOMMANDS))}",
            file=sys.stderr,
        )
        return 2
    return handler(rest)


if __name__ == "__main__":
    raise SystemExit(main())
