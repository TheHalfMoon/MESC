#!/usr/bin/env python3
"""Reproduce bounded MRL-0802 synthetic FHIR corpus evidence artifacts."""

from __future__ import annotations

import argparse
from pathlib import Path

from medscale.mesc._mrl_0802_synthetic_fhir_corpus_v1 import (
    build_mrl_0802_fixture_corpus,
    parse_mrl_0802_authorization,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data/mesc-mrl-0802-fhir-v1/source-fixtures.jsonl"
DEFAULT_AUTH = ROOT / "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-authorization-v1.json"
DEFAULT_OUTPUT = ROOT / "data/mesc-mrl-0802-fhir-v1/evidence"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--authorization", type=Path, default=DEFAULT_AUTH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    authorization = parse_mrl_0802_authorization(args.authorization.read_bytes())
    result = build_mrl_0802_fixture_corpus(
        source_bytes=args.source.read_bytes(),
        authorization=authorization,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "corpus.jsonl": result.corpus_bytes,
        "rights.json": result.rights_bytes,
        "provenance.json": result.provenance_bytes,
        "mrl-0802-real-preflight-evidence.json": result.evidence_bytes,
    }
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
