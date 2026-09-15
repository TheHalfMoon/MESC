#!/usr/bin/env python3
"""Launch the synthetic MRL-0808 probe in a real bubblewrap isolation boundary on Colab."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
POLICY = "b156b8c6813880f7062b9f7ce6dcf053f1fb761d6ad0ba562aa753403b13d0bd"
NETWORK = "4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f"
MUTATION = "238ef158fe54e47cc6115502bec60763c7149f74130ea35e57a84e70da2f02c8"
OUTPUT = "7d890a8608485c58391bc1c422590b0aa1d17a35b63f3ed1f0decba5f18b726e"
STOP = "607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194"
RUNTIME_EVID = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
RUNTIME_ID = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
PROBE = Path("scripts/mesc_mrl_0808_sandbox_probe.py")


def git(root: Path, *args: str) -> str:
    cp = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if cp.returncode:
        raise SystemExit("cannot resolve repository identity")
    return cp.stdout.strip()


def existing_dir(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_dir():
        raise SystemExit(f"{label} must be real directory")
    return resolved


def require_empty(path: Path, label: str) -> None:
    if any(path.iterdir()):
        raise SystemExit(f"{label} must be empty before sandbox qualification")


def write_new(path: Path, raw: bytes) -> None:
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise SystemExit(f"refusing overwrite: {path}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def sandbox_prefix(
    *,
    bwrap: Path,
    empty: Path,
    mesc: Path,
    repository: Path,
    inputs: Path,
    weights: Path,
    scratch: Path,
    output: Path,
) -> list[str]:
    return [
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        "/",
        "/",
        "--ro-bind",
        str(empty),
        "/home",
        "--ro-bind",
        str(empty),
        "/root",
        "--ro-bind",
        str(empty),
        "/run",
        "--ro-bind",
        str(empty),
        "/tmp",
        "--ro-bind",
        str(mesc),
        "/mesc-run",
        "--ro-bind",
        str(repository),
        "/mesc-run/repository",
        "--ro-bind",
        str(inputs),
        "/mesc-run/inputs",
        "--ro-bind",
        str(weights),
        "/mesc-run/model-weights",
        "--bind",
        str(scratch),
        "/mesc-run/scratch",
        "--bind",
        str(output),
        "/mesc-run/output",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--model-weights", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--custody-dir", type=Path, required=True)
    parser.add_argument("--challenge", required=True)
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise SystemExit("MRL-0808 hosted launcher requires Linux")
    if SHA64.fullmatch(args.challenge) is None:
        raise SystemExit("challenge must be 64 lowercase hex")
    runtime_id = os.environ.get("MESC_COLAB_RUNTIME_ID", "").strip()
    release = os.environ.get("COLAB_RELEASE_TAG", "").strip()
    if not runtime_id or "\x00" in runtime_id or not release or "\x00" in release:
        raise SystemExit("missing/invalid independently obtained Colab runtime identity/family")

    root = existing_dir(args.repository_root, "repository")
    inputs = existing_dir(args.inputs, "inputs")
    weights = existing_dir(args.model_weights, "model weights")
    scratch = existing_dir(args.scratch, "scratch")
    output = existing_dir(args.output, "output")
    custody = existing_dir(args.custody_dir, "custody")
    require_empty(scratch, "scratch")
    require_empty(output, "output")
    require_empty(custody, "custody")

    head = git(root, "rev-parse", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    origin = git(root, "rev-parse", "origin/main")
    live = git(root, "ls-remote", "origin", "refs/heads/main").split("\t")[0]
    if (
        head != origin
        or head != live
        or SHA40.fullmatch(head) is None
        or SHA40.fullmatch(tree) is None
    ):
        raise SystemExit("launcher requires exact canonical main")
    if git(root, "status", "--porcelain", "--untracked-files=all") or git(root, "clean", "-ndx"):
        raise SystemExit("repository must be clean")
    probe = (root / PROBE).resolve(strict=True)
    if probe.read_bytes() != subprocess.check_output(
        ["git", "-C", str(root), "show", f"HEAD:{PROBE.as_posix()}"]
    ):
        raise SystemExit("probe bytes differ from HEAD")

    bwrap_raw = shutil.which("bwrap")
    if not bwrap_raw:
        raise SystemExit("bubblewrap is required; install during setup outside isolated window")
    bwrap = Path(bwrap_raw).resolve(strict=True)
    bwrap_sha = hashlib.sha256(bwrap.read_bytes()).hexdigest()
    bwrap_version = subprocess.check_output([str(bwrap), "--version"], text=True).strip()
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,uuid,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True,
        text=True,
    )
    if gpu.returncode:
        raise SystemExit("qualified hosted runtime must expose nvidia-smi")
    gpu_lines = [line.strip() for line in gpu.stdout.splitlines() if line.strip()]
    if len(gpu_lines) != 1:
        raise SystemExit("exactly one hosted GPU is required")

    context = {
        "bubblewrap_binary_sha256": bwrap_sha,
        "bubblewrap_version": bwrap_version,
        "colab_release_tag": release,
        "gpu_observation": gpu_lines[0],
        "kernel_release": platform.release(),
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": runtime_id,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "python_version": platform.python_version(),
        "repository_sha": head,
        "repository_tree": tree,
        "schema_version": "MESC-MRL-0808-RUNTIME-CONTEXT-V1",
    }
    context_raw = canonical_json_bytes(context)
    context_sha = hashlib.sha256(context_raw).hexdigest()

    with tempfile.TemporaryDirectory(prefix="mrl0808-layout-") as temporary:
        layout = Path(temporary)
        mesc = layout / "mesc-run"
        mesc.mkdir()
        for name in ("repository", "inputs", "model-weights", "scratch", "output"):
            (mesc / name).mkdir()
        empty = layout / "empty"
        empty.mkdir()
        prefix = sandbox_prefix(
            bwrap=bwrap,
            empty=empty,
            mesc=mesc,
            repository=root,
            inputs=inputs,
            weights=weights,
            scratch=scratch,
            output=output,
        )
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONDONTWRITEBYTECODE": "1",
            "MESC_MRL0808_CHALLENGE": args.challenge,
            "MESC_MRL0808_SANDBOX_POLICY_SHA256": POLICY,
            "MESC_MRL0808_NETWORK_POLICY_SHA256": NETWORK,
            "MESC_MRL0808_MUTATION_PATHS_SHA256": MUTATION,
            "MESC_MRL0808_OUTPUT_DESTINATIONS_SHA256": OUTPUT,
            "MESC_MRL0808_STOP_CONDITIONS_SHA256": STOP,
            "MESC_MRL0808_PREDECESSOR_RUNTIME_EVIDENCE_SHA256": RUNTIME_EVID,
            "MESC_MRL0808_PREDECESSOR_RUNTIME_IDENTITY_SHA256": RUNTIME_ID,
            "MESC_MRL0808_RUNTIME_CONTEXT_SHA256": context_sha,
        }
        probe_command = prefix.copy()
        for key, value in env.items():
            probe_command += ["--setenv", key, value]
        probe_command += ["/usr/bin/env", "python3", "/mesc-run/repository/" + PROBE.as_posix()]
        probe_run = subprocess.run(probe_command, capture_output=True)
        if probe_run.returncode:
            raise SystemExit(
                "sandbox probe failed: " + probe_run.stderr.decode("utf-8", "replace")[-4000:]
            )
        try:
            observation = json.loads(probe_run.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SystemExit("probe output is not JSON") from exc
        observation_raw = canonical_json_bytes(observation)
        if observation_raw != probe_run.stdout:
            raise SystemExit("probe output is not exact canonical MESC JSON")
        observation_sha = hashlib.sha256(observation_raw).hexdigest()

        forbidden_relative = Path(".mrl0808-forbidden-write")
        forbidden_host = root / forbidden_relative
        if forbidden_host.exists():
            raise SystemExit("forbidden-write sentinel already exists")
        violation_code = (
            "from pathlib import Path; "
            "Path('/mesc-run/repository/.mrl0808-forbidden-write').write_bytes(b'forbidden')"
        )
        violation_command = [
            *prefix,
            "--setenv",
            "PATH",
            "/usr/local/bin:/usr/bin:/bin",
            "/usr/bin/env",
            "python3",
            "-c",
            violation_code,
        ]
        violation_run = subprocess.run(violation_command, capture_output=True)
        if violation_run.returncode == 0 or forbidden_host.exists():
            raise SystemExit("forbidden write was not stopped by sandbox policy")
        if any(scratch.iterdir()) or any(output.iterdir()):
            raise SystemExit("sandbox left unexpected scratch/output residue")

    cleanup = {
        "challenge": args.challenge,
        "forbidden_repository_write_absent": True,
        "normal_probe_exit_code": 0,
        "observation_sha256": observation_sha,
        "output_empty_after_cleanup": True,
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_context_sha256": context_sha,
        "sandbox_policy_sha256": POLICY,
        "schema_version": "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1",
        "scratch_empty_after_cleanup": True,
        "state": "COMPLETED",
        "violation_probe_stopped": True,
    }
    cleanup_raw = canonical_json_bytes(cleanup)
    write_new(custody / "runtime-context.json", context_raw)
    write_new(custody / "sandbox-observation.json", observation_raw)
    write_new(custody / "sandbox-cleanup-receipt.json", cleanup_raw)
    print("RUNTIME_CONTEXT_SHA256=" + context_sha)
    print("OBSERVATION_SHA256=" + observation_sha)
    print("CLEANUP_RECEIPT_SHA256=" + hashlib.sha256(cleanup_raw).hexdigest())
    print("PROVIDER_EXECUTION_ID=" + runtime_id)
    print("MONETARY_COST_MICROUNITS=UNATTESTED_REQUIRES_INDEPENDENT_CONTROL_PLANE_REVIEW")


if __name__ == "__main__":
    main()
