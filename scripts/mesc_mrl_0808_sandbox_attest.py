#!/usr/bin/env python3
"""Render one untrusted MRL-0808 runtime-sandbox attestation after independent review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
POLICY = "b156b8c6813880f7062b9f7ce6dcf053f1fb761d6ad0ba562aa753403b13d0bd"


def load(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    if type(obj) is not dict or canonical_json_bytes(obj) != raw:
        raise SystemExit(f"non-canonical input: {path}")
    return cast(dict[str, object], obj), raw


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--challenge-receipt", required=True)
    parser.add_argument("--observation", required=True)
    parser.add_argument("--runtime-context", required=True)
    parser.add_argument("--cleanup-receipt", required=True)
    parser.add_argument("--repository-sha", required=True)
    parser.add_argument("--repository-tree", required=True)
    parser.add_argument("--provider-execution-id", required=True)
    parser.add_argument("--verification-method", required=True)
    parser.add_argument("--verification-reference", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if (
        SHA40.fullmatch(args.repository_sha) is None
        or SHA40.fullmatch(args.repository_tree) is None
    ):
        raise SystemExit("invalid repository identity")

    receipt, receipt_raw = load(Path(args.challenge_receipt))
    observation, observation_raw = load(Path(args.observation))
    context, context_raw = load(Path(args.runtime_context))
    cleanup, cleanup_raw = load(Path(args.cleanup_receipt))
    observation_sha = hashlib.sha256(observation_raw).hexdigest()
    context_sha = hashlib.sha256(context_raw).hexdigest()
    cleanup_sha = hashlib.sha256(cleanup_raw).hexdigest()
    receipt_sha = hashlib.sha256(receipt_raw).hexdigest()
    provider = args.provider_execution_id.strip()

    if receipt.get("state") != "CONSUMED" or receipt.get("task_id") != "MRL-0808":
        raise SystemExit("challenge is not consumed")
    if receipt.get("observation_sha256") != observation_sha or receipt.get(
        "challenge"
    ) != observation.get("challenge"):
        raise SystemExit("challenge/observation mismatch")
    if receipt.get("runtime_context_sha256") != context_sha:
        raise SystemExit("challenge/runtime-context mismatch")
    if receipt.get("cleanup_receipt_sha256") != cleanup_sha:
        raise SystemExit("challenge/cleanup-receipt mismatch")
    if (
        receipt.get("repository_sha") != args.repository_sha
        or receipt.get("repository_tree") != args.repository_tree
        or context.get("repository_sha") != args.repository_sha
        or context.get("repository_tree") != args.repository_tree
        or cleanup.get("repository_sha") != args.repository_sha
        or cleanup.get("repository_tree") != args.repository_tree
    ):
        raise SystemExit("repository binding mismatch")
    if (
        receipt.get("sandbox_policy_sha256") != POLICY
        or observation.get("sandbox_policy_sha256") != POLICY
        or cleanup.get("sandbox_policy_sha256") != POLICY
    ):
        raise SystemExit("policy binding mismatch")
    if (
        receipt.get("provider_execution_id") != provider
        or context.get("provider_execution_id") != provider
        or context.get("provider") != "GOOGLE_COLAB"
        or context.get("provider_flavor") != "DYNAMIC_ASSIGNED"
        or context.get("provider_owner") != "GOOGLE"
    ):
        raise SystemExit("provider execution identity mismatch")
    if observation.get("runtime_context_sha256") != context_sha:
        raise SystemExit("observation runtime-context mismatch")
    if (
        cleanup.get("runtime_context_sha256") != context_sha
        or cleanup.get("observation_sha256") != observation_sha
    ):
        raise SystemExit("cleanup binding mismatch")
    method = args.verification_method.strip()
    reference = args.verification_reference.strip()
    if (
        not provider
        or "\x00" in provider
        or not method
        or not reference
        or "\x00" in method
        or "\x00" in reference
    ):
        raise SystemExit("invalid independent verification evidence")

    doc = {
        "attestation_state": "COMPLETED",
        "challenge": receipt["challenge"],
        "challenge_receipt_sha256": receipt_sha,
        "challenge_state": "CONSUMED",
        "cleanup_receipt_sha256": cleanup_sha,
        "independent_verification_method": method,
        "independent_verification_reference": reference,
        "monetary_cost_microunits": 0,
        "observation_sha256": observation_sha,
        "policy_sha256": POLICY,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": provider,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "repository_sha": args.repository_sha,
        "repository_tree": args.repository_tree,
        "runtime_context_sha256": context_sha,
        "schema_version": "MESC-MRL-0808-RUNTIME-SANDBOX-ATTESTATION-V1",
    }
    raw = canonical_json_bytes(doc)
    out = Path(args.output)
    try:
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SystemExit(f"refusing overwrite: {out}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    print("ATTESTATION_SHA256=" + hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
