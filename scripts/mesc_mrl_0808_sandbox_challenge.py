#!/usr/bin/env python3
"""Issue, consume, or cancel one external MRL-0808 sandbox verifier challenge."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import secrets
from collections.abc import Iterator
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
CONTROL_SCHEMA = "MESC-MRL-0808-SANDBOX-CONTROL-EVIDENCE-V1"
TASK = "MRL-0808"
POLICY = "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"
RUNTIME_EVID = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
RUNTIME_ID = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


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


def verifier_ledger(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if candidate.is_symlink():
        raise SystemExit("verifier ledger must not be a symlink")
    try:
        ledger = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise SystemExit("verifier ledger must already exist") from exc
    if not ledger.is_dir():
        raise SystemExit("verifier ledger must be a directory")
    try:
        ledger.relative_to(REPOSITORY_ROOT)
    except ValueError:
        pass
    else:
        raise SystemExit("verifier ledger must remain outside repository")
    return ledger


def validated_issuance(path: str, ledger: Path) -> tuple[dict[str, object], str]:
    candidate = Path(path).expanduser()
    if candidate.is_symlink():
        raise SystemExit("issuance must not be a symlink")
    issuance_path = candidate.resolve(strict=True)
    if issuance_path.parent != ledger:
        raise SystemExit("issuance is outside verifier ledger")
    issued, _ = load(issuance_path)
    expected_keys = {
        "challenge",
        "predecessor_runtime_evidence_sha256",
        "predecessor_runtime_identity_sha256",
        "repository_sha",
        "repository_tree",
        "sandbox_policy_sha256",
        "schema_version",
        "state",
        "task_id",
    }
    if set(issued) != expected_keys:
        raise SystemExit("issuance key set drifted")
    challenge = str(issued.get("challenge", ""))
    valid_sha(challenge, 64)
    if issuance_path.name != f"{challenge}.issued.json":
        raise SystemExit("issuance filename does not bind challenge")
    if (
        issued.get("schema_version") != ISSUE_SCHEMA
        or issued.get("state") != "ISSUED"
        or issued.get("task_id") != TASK
        or issued.get("sandbox_policy_sha256") != POLICY
        or issued.get("predecessor_runtime_evidence_sha256") != RUNTIME_EVID
        or issued.get("predecessor_runtime_identity_sha256") != RUNTIME_ID
    ):
        raise SystemExit("issuance state/schema/authority invalid")
    valid_sha(str(issued.get("repository_sha", "")), 40)
    valid_sha(str(issued.get("repository_tree", "")), 40)
    return issued, challenge


@contextlib.contextmanager
def terminal_transition(ledger: Path, challenge: str) -> Iterator[None]:
    lock = ledger / f".{challenge}.terminal-transition.lock"
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise SystemExit("challenge terminal transition already in progress") from exc
    try:
        yield
    finally:
        with contextlib.suppress(FileNotFoundError):
            lock.rmdir()


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
    ledger = verifier_ledger(args.ledger_dir)
    path = ledger / f"{challenge}.issued.json"
    xwrite(path, obj)
    print(path)


def consume(args: argparse.Namespace) -> None:
    ledger = verifier_ledger(args.ledger_dir)
    issued, challenge = validated_issuance(args.issuance, ledger)
    cancelled = ledger / f"{challenge}.cancelled.json"
    consumed = ledger / f"{challenge}.consumed.json"
    with terminal_transition(ledger, challenge):
        if cancelled.exists():
            raise SystemExit("challenge is cancelled")
        if consumed.exists():
            raise SystemExit("challenge is already consumed")
        observation, observation_raw = load(Path(args.observation))
        context, context_raw = load(Path(args.runtime_context))
        control, control_raw = load(Path(args.sandbox_control_evidence))
        cleanup, cleanup_raw = load(Path(args.cleanup_receipt))
        observation_sha = hashlib.sha256(observation_raw).hexdigest()
        context_sha = hashlib.sha256(context_raw).hexdigest()
        control_sha = hashlib.sha256(control_raw).hexdigest()
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
            control.get("schema_version") != CONTROL_SCHEMA
            or control.get("challenge") != challenge
            or control.get("runtime_context_sha256") != context_sha
            or control.get("gpu_observation") != context.get("gpu_observation")
            or control.get("output_root_capacity_enforced") is not True
            or control.get("gpu_visible_inside_sandbox") is not True
            or control.get("undeclared_artifact_present") is not False
        ):
            raise SystemExit(
                "sandbox-control evidence does not bind issued challenge/runtime controls"
            )

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
            "challenge": challenge,
            "collected_bytes_before_cleanup": len(context_raw)
            + len(observation_raw)
            + len(control_raw),
            "forbidden_repository_write_absent": True,
            "minimal_runtime_root_enforced": True,
            "normal_probe_exit_code": 0,
            "observation_sha256": observation_sha,
            "output_budget_challenge_blocked": True,
            "output_tmpfs_destroyed_after_namespace_exit": True,
            "repository_sha": issued.get("repository_sha"),
            "repository_tree": issued.get("repository_tree"),
            "runtime_context_sha256": context_sha,
            "sandbox_control_evidence_sha256": control_sha,
            "sandbox_policy_sha256": POLICY,
            "schema_version": CLEANUP_SCHEMA,
            "scratch_tmpfs_destroyed_after_namespace_exit": True,
            "state": "COMPLETED",
            "undeclared_output_challenge_blocked": True,
            "violation_probe_stopped": True,
        }
        if cleanup != expected_cleanup:
            raise SystemExit("cleanup receipt does not prove exact sandbox stop/cleanup state")

        receipt = {
            "challenge": challenge,
            "cleanup_receipt_sha256": cleanup_sha,
            "observation_sha256": observation_sha,
            "sandbox_control_evidence_sha256": control_sha,
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
    ledger = verifier_ledger(args.ledger_dir)
    _, challenge = validated_issuance(args.issuance, ledger)
    consumed = ledger / f"{challenge}.consumed.json"
    cancelled = ledger / f"{challenge}.cancelled.json"
    reason = args.reason.strip()
    if not reason or "\x00" in reason:
        raise SystemExit("invalid cancellation reason")
    with terminal_transition(ledger, challenge):
        if consumed.exists():
            raise SystemExit("cannot cancel a consumed challenge")
        if cancelled.exists():
            raise SystemExit("challenge is already cancelled")
        obj = {
            "challenge": challenge,
            "reason": reason,
            "schema_version": CANCEL_SCHEMA,
            "state": "CANCELLED",
            "task_id": TASK,
        }
        xwrite(cancelled, obj)
    print(cancelled)


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
    command.add_argument("--sandbox-control-evidence", required=True)
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
