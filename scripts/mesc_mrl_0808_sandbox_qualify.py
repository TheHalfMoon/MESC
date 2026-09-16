#!/usr/bin/env python3
"""Produce or independently verify exact MRL-0808 sandbox qualification evidence."""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

MODULE = Path("src/medscale/mesc/_mrl_0808_sandbox_v1.py")
TEST = Path("tests/test_mesc_mrl_0808_sandbox_v1.py")
AUTH = Path("specs/mesc-experiment-0/mrl-0808-sandbox-authorization-v1.json")
POLICIES = {
    "network": Path("specs/mesc-experiment-0/mrl-0808-network-policy-v1.json"),
    "mutation": Path("specs/mesc-experiment-0/mrl-0808-mutation-paths-v1.json"),
    "output": Path("specs/mesc-experiment-0/mrl-0808-output-destinations-v1.json"),
    "stop": Path("specs/mesc-experiment-0/mrl-0808-stop-conditions-v1.json"),
    "sandbox": Path("specs/mesc-experiment-0/mrl-0808-sandbox-policy-v1.json"),
}
PROBE = Path("scripts/mesc_mrl_0808_sandbox_probe.py")
SUPERVISOR = Path("scripts/mesc_mrl_0808_sandbox_supervisor.py")
CHALLENGE = Path("scripts/mesc_mrl_0808_sandbox_challenge.py")
ATTEST = Path("scripts/mesc_mrl_0808_sandbox_attest.py")
SCRIPT = Path("scripts/mesc_mrl_0808_sandbox_qualify.py")
ARTIFACTS = {
    "runtime_context": "runtime-context.json",
    "observation": "sandbox-observation.json",
    "control": "sandbox-control-evidence.json",
    "cleanup": "sandbox-cleanup-receipt.json",
    "challenge": "challenge-receipt.json",
    "attestation": "runtime-sandbox-attestation.json",
    "runtime": "runtime-sandbox-evidence.json",
    "receipt": "sandbox-qualification-receipt.json",
    "evidence": "mrl-0808-real-preflight-evidence.json",
}
TRUST_NAME = "TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256"


class EntrypointError(RuntimeError):
    pass


def git_text(root: Path, *args: str) -> str:
    cp = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if cp.returncode:
        raise EntrypointError("Git identity cannot be resolved")
    return cp.stdout


def git_bytes(root: Path, *args: str) -> bytes:
    cp = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if cp.returncode:
        raise EntrypointError("Git bytes cannot be resolved")
    return cp.stdout


def clean_root(root: Path) -> Path:
    candidate = root.expanduser()
    if candidate.is_symlink():
        raise EntrypointError("repository-root must not be a symlink")
    r = candidate.resolve(strict=True)
    top = Path(git_text(r, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if top != r:
        raise EntrypointError("repository-root is not exact work-tree root")
    if (
        git_text(r, "status", "--porcelain", "--untracked-files=all").strip()
        or git_text(r, "clean", "-ndx").strip()
    ):
        raise EntrypointError("repository must be clean with no ignored/untracked state")
    for rel in (MODULE, AUTH, *POLICIES.values(), PROBE, SUPERVISOR, CHALLENGE, ATTEST, SCRIPT):
        source = r / rel
        if source.is_symlink():
            raise EntrypointError(f"unsafe required source: {rel}")
        p = source.resolve(strict=True)
        if not p.is_file():
            raise EntrypointError(f"unsafe required source: {rel}")
        if p.read_bytes() != git_bytes(r, "show", f"HEAD:{rel.as_posix()}"):
            raise EntrypointError(f"working bytes differ from HEAD: {rel}")
    return r


def external(path: Path, root: Path, label: str) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise EntrypointError(f"{label} must be regular non-symlink file")
    p = candidate.resolve(strict=True)
    if not p.is_file():
        raise EntrypointError(f"{label} must be regular non-symlink file")
    try:
        p.relative_to(root)
    except ValueError:
        return p
    raise EntrypointError(f"{label} must remain outside repository")


def stable_read(p: Path, label: str) -> bytes:
    a = p.stat(follow_symlinks=False)
    raw = p.read_bytes()
    b = p.stat(follow_symlinks=False)
    if (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns) != (
        b.st_dev,
        b.st_ino,
        b.st_size,
        b.st_mtime_ns,
    ) or len(raw) != b.st_size:
        raise EntrypointError(f"{label} changed while read")
    return raw


def output_root(path: Path, root: Path, verify: bool) -> Path:
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise EntrypointError("output-root must be existing non-symlink directory")
    p = candidate.resolve(strict=True)
    if not p.is_dir():
        raise EntrypointError("output-root must be existing non-symlink directory")
    try:
        p.relative_to(root)
        raise EntrypointError("output-root must be outside repository")
    except ValueError:
        pass
    names = {x.name for x in p.iterdir()}
    if verify and names != set(ARTIFACTS.values()):
        raise EntrypointError("verify-existing output set mismatch")
    if not verify and names:
        raise EntrypointError("production output-root must be empty")
    return p


def first_parent_contains(root: Path, source: str, head: str) -> bool:
    return source in git_text(root, "rev-list", "--first-parent", head).splitlines()


def normalize_trust_ast(raw: bytes) -> str:
    try:
        tree = ast.parse(raw.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as exc:
        raise EntrypointError("sandbox module is invalid Python") from exc
    found = 0
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == TRUST_NAME:
                node.value = ast.Call(
                    func=ast.Name(id="frozenset", ctx=ast.Load()), args=[], keywords=[]
                )
                found += 1
        elif isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if names == [TRUST_NAME]:
                node.value = ast.Call(
                    func=ast.Name(id="frozenset", ctx=ast.Load()), args=[], keywords=[]
                )
                found += 1
    if found != 1:
        raise EntrypointError("sandbox module must define exactly one attestation trust registry")
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def source_binding(root: Path, source: str, head: str, tree_expected: str) -> None:
    if git_text(root, "rev-parse", f"{source}^{{commit}}").strip() != source:
        raise EntrypointError("source commit unresolved")
    if git_text(root, "rev-parse", f"{source}^{{tree}}").strip() != tree_expected:
        raise EntrypointError("source tree mismatch")
    if not first_parent_contains(root, source, head):
        raise EntrypointError("source is not on canonical first-parent lineage")
    changed = set(git_text(root, "diff", "--name-only", f"{source}..{head}").splitlines())
    allowed = {MODULE.as_posix(), TEST.as_posix()}
    if not changed <= allowed:
        raise EntrypointError(
            f"qualification semantics drifted outside trust-only scope: {sorted(changed - allowed)}"
        )
    src = git_bytes(root, "show", f"{source}:{MODULE.as_posix()}")
    cur = (root / MODULE).read_bytes()
    assert isinstance(src, bytes)
    if normalize_trust_ast(src) != normalize_trust_ast(cur):
        raise EntrypointError("sandbox module semantics drifted beyond attestation trust registry")


def load_module(root: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            del sys.modules[name]
    sys.path.insert(0, str((root / "src").resolve(strict=True)))
    m = importlib.import_module("medscale.mesc._mrl_0808_sandbox_v1")
    if Path(str(m.__file__)).resolve(strict=True) != (root / MODULE).resolve(strict=True):
        raise EntrypointError("sandbox module imported from non-canonical source")
    return m


def write_new(p: Path, raw: bytes) -> None:
    with p.open("xb") as f:
        f.write(raw)


def produce(
    root: Path,
    out: Path,
    runtime_context: bytes,
    observation: bytes,
    control: bytes,
    cleanup: bytes,
    challenge: bytes,
    attestation: bytes,
) -> Any:
    m = load_module(root)
    att_doc = json.loads(attestation.decode("utf-8"))
    source = str(att_doc.get("repository_sha", ""))
    source_tree = str(att_doc.get("repository_tree", ""))
    head = git_text(root, "rev-parse", "HEAD").strip()
    source_binding(root, source, head, source_tree)
    result = m.qualify_mrl_0808_sandbox(
        authorization_bytes=(root / AUTH).read_bytes(),
        network_policy_bytes=(root / POLICIES["network"]).read_bytes(),
        mutation_policy_bytes=(root / POLICIES["mutation"]).read_bytes(),
        output_policy_bytes=(root / POLICIES["output"]).read_bytes(),
        stop_policy_bytes=(root / POLICIES["stop"]).read_bytes(),
        sandbox_policy_bytes=(root / POLICIES["sandbox"]).read_bytes(),
        observation_bytes=observation,
        runtime_context_bytes=runtime_context,
        sandbox_control_evidence_bytes=control,
        cleanup_receipt_bytes=cleanup,
        challenge_receipt_bytes=challenge,
        runtime_attestation_bytes=attestation,
        repository_sha=source,
        repository_tree=source_tree,
    )
    from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

    parsed = parse_mrl_real_preflight_evidence(result.evidence_bytes)
    if parsed.task_id != "MRL-0808" or parsed.evidence_sha256 != result.evidence_sha256:
        raise EntrypointError("outer MRL-0808 evidence parser identity mismatch")
    payloads = {
        "runtime_context": runtime_context,
        "observation": observation,
        "control": control,
        "cleanup": cleanup,
        "challenge": challenge,
        "attestation": attestation,
        "runtime": result.runtime_sandbox_evidence_bytes,
        "receipt": result.receipt_bytes,
        "evidence": result.evidence_bytes,
    }
    for k, v in payloads.items():
        write_new(out / ARTIFACTS[k], v)
    return result


def verify(root: Path, out: Path) -> Any:
    payload = {k: stable_read(out / name, name) for k, name in ARTIFACTS.items()}
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        result = produce(
            root,
            t,
            payload["runtime_context"],
            payload["observation"],
            payload["control"],
            payload["cleanup"],
            payload["challenge"],
            payload["attestation"],
        )
        for k, name in ARTIFACTS.items():
            if (t / name).read_bytes() != payload[k]:
                raise EntrypointError(f"byte mismatch in {name}")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--repository-root", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--runtime-context", type=Path)
    p.add_argument("--observation", type=Path)
    p.add_argument("--sandbox-control-evidence", type=Path)
    p.add_argument("--cleanup-receipt", type=Path)
    p.add_argument("--challenge-receipt", type=Path)
    p.add_argument("--runtime-attestation", type=Path)
    p.add_argument("--verify-existing", action="store_true")
    a = p.parse_args()
    root = clean_root(a.repository_root)
    head = git_text(root, "rev-parse", "HEAD").strip()
    origin = git_text(root, "rev-parse", "origin/main").strip()
    live = git_text(root, "ls-remote", "origin", "refs/heads/main").split("\t")[0]
    if head != origin or head != live:
        raise EntrypointError("qualification requires exact canonical main")
    out = output_root(a.output_root, root, a.verify_existing)
    if a.verify_existing:
        result = verify(root, out)
    else:
        if not (
            a.runtime_context
            and a.observation
            and a.sandbox_control_evidence
            and a.cleanup_receipt
            and a.challenge_receipt
            and a.runtime_attestation
        ):
            raise EntrypointError(
                "production requires runtime context, observation, sandbox-control evidence, "
                "cleanup receipt, challenge receipt, and runtime attestation"
            )
        runtime_context = stable_read(
            external(a.runtime_context, root, "runtime context"), "runtime context"
        )
        observation = stable_read(external(a.observation, root, "observation"), "observation")
        control = stable_read(
            external(a.sandbox_control_evidence, root, "sandbox-control evidence"),
            "sandbox-control evidence",
        )
        cleanup = stable_read(
            external(a.cleanup_receipt, root, "cleanup receipt"), "cleanup receipt"
        )
        challenge = stable_read(
            external(a.challenge_receipt, root, "challenge receipt"), "challenge receipt"
        )
        attestation = stable_read(
            external(a.runtime_attestation, root, "attestation"), "attestation"
        )
        result = produce(
            root, out, runtime_context, observation, control, cleanup, challenge, attestation
        )
    print("MRL0808_SANDBOX_QUALIFICATION=PASS")
    print("RUNTIME_SANDBOX_EVIDENCE_SHA256=" + result.runtime_sandbox_evidence_sha256)
    print("RECEIPT_SHA256=" + result.receipt_sha256)
    print("EVIDENCE_SHA256=" + result.evidence_sha256)


if __name__ == "__main__":
    main()
