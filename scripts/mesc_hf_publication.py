#!/usr/bin/env python3
"""Qualify a canonical Hugging Face publication plan without publishing."""

from __future__ import annotations

import argparse
from pathlib import Path

from medscale.mesc._hf_publication_v1 import (
    build_dry_run_receipt,
    parse_publication_plan,
    qualify_publication_plan,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-tree", required=True)
    parser.add_argument("--expected-tag", required=True)
    parser.add_argument("--receipt-out", type=Path, required=True)
    args = parser.parse_args()

    plan = parse_publication_plan(args.plan.read_bytes())
    qualification = qualify_publication_plan(
        plan,
        expected_repository=args.expected_repository,
        expected_sha=args.expected_sha,
        expected_tree=args.expected_tree,
        expected_tag=args.expected_tag,
    )
    if qualification.disposition != "DRY_RUN_READY":
        for blocker in qualification.blockers:
            print(f"BLOCKED: {blocker}")
        raise SystemExit(2)
    receipt = build_dry_run_receipt(
        plan,
        qualification,
        expected_repository=args.expected_repository,
        expected_sha=args.expected_sha,
        expected_tree=args.expected_tree,
        expected_tag=args.expected_tag,
    )
    args.receipt_out.parent.mkdir(parents=True, exist_ok=True)
    args.receipt_out.write_bytes(receipt)
    print(f"DRY_RUN_READY plan_sha256={qualification.plan_sha256}")
    print(f"artifact_manifest_sha256={qualification.artifact_manifest_sha256}")


if __name__ == "__main__":
    main()
