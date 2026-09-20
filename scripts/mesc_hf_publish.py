#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11,<3.12"
# dependencies = [
#   "huggingface-hub==1.23.0",
# ]
# [tool.uv]
# exclude-newer = "2026-09-20T00:00:00Z"
# ///
"""Governed Hugging Face Trusted Publisher transport CLI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from medscale.mesc._hf_publication_v2 import (
    HfPublicationTransportError,
    PublicationAuthority,
    parse_authority,
    publish_with_trusted_publisher,
    transport_manifest_sha256,
    verify_live_github_boundaries,
    verify_source_tag,
    verify_transport_manifest,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUTHORITY = REPOSITORY_ROOT / "specs" / "mesc-hf-publication-v2" / "authority.json"


def _load_authority(path: Path) -> PublicationAuthority:
    return parse_authority(path.read_bytes())


def _github_token() -> str:
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise HfPublicationTransportError("GH_TOKEN is required for live GitHub verification")
    return token


def _add_live_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-workflow-ref", required=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-authority")
    validate.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)

    subparsers.add_parser("transport-manifest")

    preflight = subparsers.add_parser("preflight")
    _add_live_args(preflight)

    publish = subparsers.add_parser("publish")
    _add_live_args(publish)
    publish.add_argument("--receipt-out", type=Path, required=True)
    publish.add_argument("--github-run-id", required=True)
    publish.add_argument("--github-run-attempt", required=True)
    publish.add_argument("--github-actor", required=True)

    args = parser.parse_args()
    if args.command == "validate-authority":
        authority = _load_authority(args.authority)
        print(f"AUTHORITY_RECORD_VALID state={authority.state}")
        return
    if args.command == "transport-manifest":
        print(f"TRANSPORT_MANIFEST_SHA256={transport_manifest_sha256(REPOSITORY_ROOT)}")
        return

    authority = _load_authority(args.authority)
    if authority.transport_manifest_sha256 is None:
        raise HfPublicationTransportError("active authority has no transport manifest digest")
    verify_transport_manifest(REPOSITORY_ROOT, authority.transport_manifest_sha256)
    verify_source_tag(REPOSITORY_ROOT, authority)
    if args.command == "preflight":
        verify_live_github_boundaries(
            authority,
            github_token=_github_token(),
            expected_repository=args.expected_repository,
            expected_workflow_sha=args.expected_sha,
            expected_workflow_ref=args.expected_workflow_ref,
        )
        print("PREFLIGHT_OK")
        return
    if args.command != "publish":
        raise HfPublicationTransportError("unsupported command")
    destination_commit = publish_with_trusted_publisher(
        REPOSITORY_ROOT,
        authority,
        github_token=_github_token(),
        expected_repository=args.expected_repository,
        expected_workflow_sha=args.expected_sha,
        expected_workflow_ref=args.expected_workflow_ref,
        receipt_out=args.receipt_out,
        github_run_id=args.github_run_id,
        github_run_attempt=args.github_run_attempt,
        github_actor=args.github_actor,
    )
    print(f"PUBLICATION_OK destination_commit={destination_commit}")


if __name__ == "__main__":
    main()
