#!/usr/bin/env python3
"""Reproduce bounded MRL-0802 synthetic FHIR corpus evidence artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from medscale.mesc._mrl_0802_synthetic_fhir_corpus_v1 import (
    MRL0802CorpusQualification,
    build_mrl_0802_fixture_corpus,
    parse_mrl_0802_authorization,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/mesc-mrl-0802-fhir-v1/source-fixtures.jsonl"
DEFAULT_AUTH = ROOT / "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-authorization-v1.json"
DEFAULT_OUTPUT = ROOT / "data/mesc-mrl-0802-fhir-v1/evidence"


def evidence_artifacts(result: MRL0802CorpusQualification) -> dict[str, bytes]:
    """Return the exact committed artifact mapping for one qualification result."""
    return {
        "corpus.jsonl": result.corpus_bytes,
        "rights.json": result.rights_bytes,
        "provenance.json": result.provenance_bytes,
        "mrl-0802-real-preflight-evidence.json": result.evidence_bytes,
    }


def evidence_drift(output: Path, artifacts: dict[str, bytes]) -> tuple[str, ...]:
    """Return artifact names whose committed bytes are absent or stale."""
    return tuple(
        name
        for name, payload in artifacts.items()
        if not (output / name).is_file() or (output / name).read_bytes() != payload
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    authorization = parse_mrl_0802_authorization(args.authorization.read_bytes())
    result = build_mrl_0802_fixture_corpus(
        source_bytes=args.source.read_bytes(),
        authorization=authorization,
    )
    artifacts = evidence_artifacts(result)
    if args.check:
        stale = evidence_drift(args.output, artifacts)
        if stale:
            print("BLOCKED: committed MRL-0802 evidence drift: " + ", ".join(stale))
            return 1
    else:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, payload in artifacts.items():
            (args.output / name).write_bytes(payload)

    print(f"corpus_sha256={result.corpus_sha256}")
    print(f"rights_evidence_sha256={result.rights_evidence_sha256}")
    print(f"provenance_sha256={result.provenance_sha256}")
    print(f"evidence_sha256={result.evidence_sha256}")
    print(f"dataset_fingerprint={result.dataset_fingerprint}")
    print(f"split_freeze_fingerprint={result.split_freeze_fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
