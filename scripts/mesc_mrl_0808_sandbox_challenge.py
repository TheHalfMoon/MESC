#!/usr/bin/env python3
"""Issue, consume, or cancel one external MRL-0808 sandbox verifier challenge."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

SHA64 = re.compile(r"^[0-9a-f]{64}$")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
ISSUE_SCHEMA = "MESC-MRL-0808-SANDBOX-CHALLENGE-ISSUANCE-V1"
RECEIPT_SCHEMA = "MESC-MRL-0808-SANDBOX-CHALLENGE-RECEIPT-V1"
CANCEL_SCHEMA = "MESC-MRL-0808-SANDBOX-CHALLENGE-CANCELLATION-V1"
CONTEXT_SCHEMA = "MESC-MRL-0808-RUNTIME-CONTEXT-V1"
CLEANUP_SCHEMA = "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1"
TASK = "MRL-0808"
POLICY = "b156b8c6813880f7062b9f7ce6dcf053f1fb761d6ad0ba562aa753403b13d0bd"
RUNTIME_EVID = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
RUNTIME_ID = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"


def load(path: Path) -> tuple[dict[str, object], bytes]:
    raw = path.read_bytes()
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"invalid JSON: {path}") from exc
    if type(obj) is not dict or canonical_json_bytes(obj) != raw:
        raise SystemExit(f"non-canonical JSON: {path}")
    return cast(dict[str, object], obj), raw


def xwrite(path: Path, obj: object) -> None:
    raw = canonical_json_bytes(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SystemExit(f"refusing overwrite: {path}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def valid_sha(value: str, length: int) -> str:
    pattern = SHA64 if length == 64 else SHA40
    if pattern.fullmatch(value) is None:
        raise SystemExit(f"invalid {length}-hex identity: {value!r}")
    return value


def issue(args: argparse.Namespace) -> None:
    repository_sha = valid_sha(args.repository_sha, 40)
    repository_tree = valid_sha(args.repository_tree, 40)
    challenge = secrets.token_hex(32)
    obj = {
        "challenge": challenge,
        "predecessor_runtime_evidence_sha256": RUNTIME_EVID,
        "predecessor_runtime_identity_sha256": RUNTIME_ID,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "sandbox_policy_sha256": POLICY,
        "schema_version": ISSUE_SCHEMA,
        "state": "ISSUED",
        "task_id": TASK,
    }
    path = Path(args.ledger_dir) / f"{challenge}.issued.json"
    xwrite(path, obj)
    print(path)


def consume(args: argparse.Namespace) -> None:
    issued, _ = load(Path(args.issuance))
    challenge = str(issued.get("challenge", ""))
    if (
        issued.get("schema_version") != ISSUE_SCHEMA
        or issued.get("state") != "ISSUED"
        or issued.get("task_id") != TASK
    ):
        raise SystemExit("issuance state/schema invalid")
    valid_sha(challenge, 64)
    ledger = Path(args.ledger_dir).resolve()
    issuance_path = Path(args.issuance).resolve()
    if issuance_path.parent != ledger:
        raise SystemExit("issuance is outside verifier ledger")
    cancelled = ledger / f"{challenge}.cancelled.json"
    consumed = ledger / f"{challenge}.consumed.json"
    if cancelled.exists():
        raise SystemExit("challenge is cancelled")
    if consumed.exists():
        raise SystemExit("challenge is already consumed")

    observation, observation_raw = load(Path(args.observation))
    context, context_raw = load(Path(args.runtime_context))
    cleanup, cleanup_raw = load(Path(args.cleanup_receipt))
    observation_sha = hashlib.sha256(observation_raw).hexdigest()
    context_sha = hashlib.sha256(context_raw).hexdigest()
    cleanup_sha = hashlib.sha256(cleanup_raw).hexdigest()
    provider = args.provider_execution_id.strip()
    if not provider or "\x00" in provider:
        raise SystemExit("invalid provider execution id")

    if observation.get("challenge") != challenge:
        raise SystemExit("observation challenge mismatch")
    for key, expected in (
        ("sandbox_policy_sha256", POLICY),
        ("predecessor_runtime_evidence_sha256", RUNTIME_EVID),
        ("predecessor_runtime_identity_sha256", RUNTIME_ID),
    ):
        if observation.get(key) != expected:
            raise SystemExit(f"observation {key} drifted")
    if observation.get("runtime_context_sha256") != context_sha:
        raise SystemExit("observation runtime-context binding mismatch")

    if (
        context.get("schema_version") != CONTEXT_SCHEMA
        or context.get("provider") != "GOOGLE_COLAB"
        or context.get("provider_flavor") != "DYNAMIC_ASSIGNED"
        or context.get("provider_owner") != "GOOGLE"
        or context.get("provider_execution_id") != provider
        or context.get("repository_sha") != issued.get("repository_sha")
        or context.get("repository_tree") != issued.get("repository_tree")
    ):
        raise SystemExit("runtime context does not match issued challenge/provider")

    expected_cleanup = {
        "schema_version": CLEANUP_SCHEMA,
        "state": "COMPLETED",
        "challenge": challenge,
        "observation_sha256": observation_sha,
        "runtime_context_sha256": context_sha,
        "repository_sha": issued.get("repository_sha"),
        "repository_tree": issued.get("repository_tree"),
        "sandbox_policy_sha256": POLICY,
        "normal_probe_exit_code": 0,
        "violation_probe_stopped": True,
        "forbidden_repository_write_absent": True,
        "scratch_empty_after_cleanup": True,
        "output_empty_after_cleanup": True,
    }
    if cleanup != expected_cleanup:
        raise SystemExit("cleanup receipt does not prove exact sandbox stop/cleanup state")

    receipt = {
        "challenge": challenge,
        "cleanup_receipt_sha256": cleanup_sha,
        "observation_sha256": observation_sha,
        "predecessor_runtime_evidence_sha256": RUNTIME_EVID,
        "predecessor_runtime_identity_sha256": RUNTIME_ID,
        "provider_execution_id": provider,
        "repository_sha": issued["repository_sha"],
        "repository_tree": issued["repository_tree"],
        "runtime_context_sha256": context_sha,
        "sandbox_policy_sha256": POLICY,
        "schema_version": RECEIPT_SCHEMA,
        "state": "CONSUMED",
        "task_id": TASK,
    }
    xwrite(consumed, receipt)
    print(consumed)


def cancel(args: argparse.Namespace) -> None:
    issued, _ = load(Path(args.issuance))
    challenge = str(issued.get("challenge", ""))
    valid_sha(challenge, 64)
    ledger = Path(args.ledger_dir).resolve()
    issuance_path = Path(args.issuance).resolve()
    if issuance_path.parent != ledger:
        raise SystemExit("issuance is outside verifier ledger")
    if (ledger / f"{challenge}.consumed.json").exists():
        raise SystemExit("cannot cancel a consumed challenge")
    reason = args.reason.strip()
    if not reason or "\x00" in reason:
        raise SystemExit("invalid cancellation reason")
    obj = {
        "challenge": challenge,
        "reason": reason,
        "schema_version": CANCEL_SCHEMA,
        "state": "CANCELLED",
        "task_id": TASK,
    }
    path = ledger / f"{challenge}.cancelled.json"
    xwrite(path, obj)
    print(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    command = subparsers.add_parser("issue")
    command.add_argument("--repository-sha", required=True)
    command.add_argument("--repository-tree", required=True)
    command.add_argument("--ledger-dir", required=True)
    command.set_defaults(fn=issue)
    command = subparsers.add_parser("consume")
    command.add_argument("--issuance", required=True)
    command.add_argument("--observation", required=True)
    command.add_argument("--runtime-context", required=True)
    command.add_argument("--cleanup-receipt", required=True)
    command.add_argument("--provider-execution-id", required=True)
    command.add_argument("--ledger-dir", required=True)
    command.set_defaults(fn=consume)
    command = subparsers.add_parser("cancel")
    command.add_argument("--issuance", required=True)
    command.add_argument("--reason", required=True)
    command.add_argument("--ledger-dir", required=True)
    command.set_defaults(fn=cancel)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
