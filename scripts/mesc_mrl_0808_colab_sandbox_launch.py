#!/usr/bin/env python3
"""Launch the synthetic MRL-0808 control probe in a bounded Colab bubblewrap sandbox."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
SHA64: Final = re.compile(r"^[0-9a-f]{64}$")
POLICY: Final = "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"
NETWORK: Final = "4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f"
MUTATION: Final = "044c61563880e630e079fad1e762aa5c9d3af505099a801070ef57d750633691"
OUTPUT: Final = "2b6c79b5662d3e91f107bf24d00155b8df0b4a1c96b0ad48284451afd0cbb8ea"
STOP: Final = "607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194"
RUNTIME_EVID: Final = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
RUNTIME_ID: Final = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
MAX_OUTPUT_BYTES: Final = 67_108_864
MAX_SCRATCH_BYTES: Final = 268_435_456
SYNTHETIC_INPUT_NAME: Final = "mrl0808-synthetic-input.txt"
SYNTHETIC_INPUT_BYTES: Final = b"MESC-MRL-0808-SYNTHETIC-READ-PROBE-V1\n"
PROBE: Final = Path("scripts/mesc_mrl_0808_sandbox_probe.py")
SUPERVISOR: Final = Path("scripts/mesc_mrl_0808_sandbox_supervisor.py")
LAUNCHER: Final = Path("scripts/mesc_mrl_0808_colab_sandbox_launch.py")
MUTATION_POLICY: Final = Path("specs/mesc-experiment-0/mrl-0808-mutation-paths-v1.json")
OUTPUT_POLICY: Final = Path("specs/mesc-experiment-0/mrl-0808-output-destinations-v1.json")
SANDBOX_POLICY: Final = Path("specs/mesc-experiment-0/mrl-0808-sandbox-policy-v1.json")
_COLLECTION_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-COLLECTION-V1"


class LauncherError(RuntimeError):
    """Fail-closed launcher error."""


def _reject_constant(token: str) -> Never:
    raise LauncherError(f"non-standard JSON constant prohibited: {token}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise LauncherError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    """Parse and reserialize one exact canonical MESC JSON object."""
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except LauncherError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise LauncherError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict:
        raise LauncherError(f"{label} must be one object")
    document = cast(dict[str, object], value)
    if canonical_json_bytes(document) != raw:
        raise LauncherError(f"{label} is not exact canonical MESC JSON")
    return document


def git(root: Path, *args: str) -> str:
    """Return one textual Git result or fail closed."""
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise LauncherError("cannot resolve repository identity")
    return completed.stdout.strip()


def git_bytes(root: Path, *args: str) -> bytes:
    """Return one binary Git result or fail closed."""
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise LauncherError("cannot resolve repository bytes")
    return completed.stdout


def existing_dir(path: Path, label: str) -> Path:
    """Resolve one real directory without accepting symlink endpoints."""
    candidate = path.expanduser()
    if candidate.is_symlink():
        raise LauncherError(f"{label} must be a real directory")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_dir():
        raise LauncherError(f"{label} must be a real directory")
    return resolved


def require_empty(path: Path, label: str) -> None:
    """Require an externally controlled custody directory to begin empty."""
    if any(path.iterdir()):
        raise LauncherError(f"{label} must be empty before sandbox qualification")


def require_outside_repository(path: Path, repository: Path, label: str) -> None:
    """Require staging/custody paths to remain outside the producer repository."""
    try:
        path.relative_to(repository)
    except ValueError:
        return
    raise LauncherError(f"{label} must remain outside repository")


def require_synthetic_qualification_inputs(inputs: Path, weights: Path) -> None:
    """Expose one declared synthetic input and no model weights during qualification."""
    entries = list(inputs.iterdir())
    if len(entries) != 1:
        raise LauncherError(
            "sandbox qualification inputs must contain exactly one synthetic marker"
        )
    marker = entries[0]
    if (
        marker.name != SYNTHETIC_INPUT_NAME
        or marker.is_symlink()
        or not marker.is_file()
        or marker.read_bytes() != SYNTHETIC_INPUT_BYTES
    ):
        raise LauncherError("sandbox qualification synthetic input bytes drifted")
    if any(weights.iterdir()):
        raise LauncherError("sandbox qualification model-weights directory must remain empty")


def write_new(path: Path, raw: bytes) -> None:
    """Create one custody artifact without overwrite."""
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise LauncherError(f"refusing overwrite: {path}") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def sha256_file(path: Path) -> str:
    """Return SHA-256 for one stable local file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_exact_sources(root: Path) -> None:
    """Bind launcher, probe, supervisor, and frozen policies to exact HEAD bytes."""
    expected_hashes = {
        MUTATION_POLICY: MUTATION,
        OUTPUT_POLICY: OUTPUT,
        SANDBOX_POLICY: POLICY,
    }
    for relative in (LAUNCHER, PROBE, SUPERVISOR, *expected_hashes):
        candidate = root / relative
        if candidate.is_symlink():
            raise LauncherError(f"required source is unsafe: {relative.as_posix()}")
        path = candidate.resolve(strict=True)
        if not path.is_file():
            raise LauncherError(f"required source is unsafe: {relative.as_posix()}")
        if path.read_bytes() != git_bytes(root, "show", f"HEAD:{relative.as_posix()}"):
            raise LauncherError(f"required source differs from exact HEAD: {relative.as_posix()}")
    for relative, expected in expected_hashes.items():
        if sha256_file(root / relative) != expected:
            raise LauncherError(f"frozen policy digest drifted: {relative.as_posix()}")


def nvidia_device_nodes() -> tuple[Path, ...]:
    """Discover only NVIDIA character devices required by the qualified GPU runtime."""
    nodes: list[Path] = []
    for candidate in sorted(Path("/dev").glob("nvidia*")):
        candidates = candidate.rglob("*") if candidate.is_dir() else (candidate,)
        for path in candidates:
            try:
                mode = path.stat().st_mode
            except OSError:
                continue
            if stat.S_ISCHR(mode):
                nodes.append(path)
    unique = tuple(sorted(set(nodes), key=lambda value: str(value)))
    if not unique:
        raise LauncherError("qualified hosted runtime exposes no NVIDIA character devices")
    return unique


def runtime_symlink_args() -> tuple[list[str], dict[str, str]]:
    """Recreate only standard runtime symlinks needed beneath the empty sandbox root."""
    args: list[str] = []
    identities: dict[str, str] = {}
    for destination in (Path("/bin"), Path("/sbin"), Path("/lib"), Path("/lib64")):
        if destination.is_symlink():
            target = str(destination.readlink())
            args.extend(["--symlink", target, str(destination)])
            identities[str(destination)] = target
        elif destination.exists() and destination.is_dir():
            args.extend(["--ro-bind", str(destination), str(destination)])
            identities[str(destination)] = "DIRECT_READ_ONLY_BIND"
    return args, identities


def sandbox_prefix(
    *,
    bwrap: Path,
    repository: Path,
    inputs: Path,
    weights: Path,
    nvidia_nodes: tuple[Path, ...],
) -> tuple[list[str], dict[str, str]]:
    """Build a minimal-root, no-network, bounded-output bubblewrap command prefix."""
    symlink_args, symlink_identities = runtime_symlink_args()
    args = [
        str(bwrap),
        "--unshare-all",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        "/usr",
        "/usr",
        *symlink_args,
        "--ro-bind",
        "/sys",
        "/sys",
        "--dir",
        "/etc",
        "--ro-bind",
        "/etc/ld.so.cache",
        "/etc/ld.so.cache",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
    ]
    parent_dirs = sorted({node.parent for node in nvidia_nodes if node.parent != Path("/dev")})
    for parent in parent_dirs:
        args.extend(["--dir", str(parent)])
    for node in nvidia_nodes:
        args.extend(["--dev-bind", str(node), str(node)])
    args.extend(
        [
            "--remount-ro",
            "/dev",
            "--remount-ro",
            "/proc",
            "--dir",
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
            "--size",
            str(MAX_SCRATCH_BYTES),
            "--tmpfs",
            "/mesc-run/scratch",
            "--size",
            str(MAX_OUTPUT_BYTES),
            "--tmpfs",
            "/mesc-run/output",
            "--remount-ro",
            "/",
            "--chdir",
            "/mesc-run/repository",
        ]
    )
    return args, symlink_identities


def sandbox_env(challenge: str, runtime_context_sha256: str) -> dict[str, str]:
    """Return the complete model-visible environment for the control probe."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
        "MESC_MRL0808_CHALLENGE": challenge,
        "MESC_MRL0808_SANDBOX_POLICY_SHA256": POLICY,
        "MESC_MRL0808_NETWORK_POLICY_SHA256": NETWORK,
        "MESC_MRL0808_MUTATION_PATHS_SHA256": MUTATION,
        "MESC_MRL0808_OUTPUT_DESTINATIONS_SHA256": OUTPUT,
        "MESC_MRL0808_STOP_CONDITIONS_SHA256": STOP,
        "MESC_MRL0808_PREDECESSOR_RUNTIME_EVIDENCE_SHA256": RUNTIME_EVID,
        "MESC_MRL0808_PREDECESSOR_RUNTIME_IDENTITY_SHA256": RUNTIME_ID,
        "MESC_MRL0808_RUNTIME_CONTEXT_SHA256": runtime_context_sha256,
    }


def run_sandbox(
    prefix: list[str], env: dict[str, str], command: list[str]
) -> subprocess.CompletedProcess[bytes]:
    """Run one fresh disposable sandbox invocation."""
    full = prefix.copy()
    for key, value in env.items():
        full.extend(["--setenv", key, value])
    full.extend(command)
    return subprocess.run(full, check=False, capture_output=True)


def collection_artifacts(
    raw: bytes, *, expected_gpu: str, context_sha: str, challenge: str
) -> tuple[bytes, bytes, int]:
    """Validate the in-sandbox output-class and byte-budget collection envelope."""
    envelope = parse_canonical_object(raw, label="sandbox collection envelope")
    if set(envelope) != {"artifacts", "maximum_total_bytes", "schema_version", "total_bytes"}:
        raise LauncherError("sandbox collection envelope key set drifted")
    if (
        envelope["schema_version"] != _COLLECTION_SCHEMA
        or envelope["maximum_total_bytes"] != MAX_OUTPUT_BYTES
    ):
        raise LauncherError("sandbox collection envelope identity drifted")
    artifacts = envelope["artifacts"]
    if type(artifacts) is not list or len(artifacts) != 2:
        raise LauncherError("sandbox collection must contain exactly two declared artifacts")
    expected = {
        "sandbox-observation.json": "qualification-observation",
        "sandbox-control-evidence.json": "sandbox-control-evidence",
    }
    payloads: dict[str, bytes] = {}
    for value in artifacts:
        if type(value) is not dict:
            raise LauncherError("sandbox collection artifact must be one object")
        artifact = cast(dict[str, object], value)
        if set(artifact) != {"class", "document", "name", "sha256"}:
            raise LauncherError("sandbox collection artifact key set drifted")
        name = artifact["name"]
        if type(name) is not str or name not in expected or artifact["class"] != expected[name]:
            raise LauncherError("sandbox collection contains undeclared artifact class/name")
        document = artifact["document"]
        if type(document) is not dict:
            raise LauncherError("sandbox collection artifact document must be one object")
        payload = canonical_json_bytes(document)
        if hashlib.sha256(payload).hexdigest() != artifact["sha256"]:
            raise LauncherError("sandbox collection artifact digest mismatch")
        if name in payloads:
            raise LauncherError("sandbox collection artifact name is duplicated")
        payloads[name] = payload
    if set(payloads) != set(expected):
        raise LauncherError("sandbox collection artifact set is incomplete")
    total = sum(len(value) for value in payloads.values())
    if (
        type(envelope["total_bytes"]) is not int
        or envelope["total_bytes"] != total
        or total > MAX_OUTPUT_BYTES
    ):
        raise LauncherError("sandbox collection byte budget mismatch")
    observation_raw = payloads["sandbox-observation.json"]
    control_raw = payloads["sandbox-control-evidence.json"]
    observation = parse_canonical_object(observation_raw, label="sandbox observation")
    control = parse_canonical_object(control_raw, label="sandbox control evidence")
    if (
        observation.get("challenge") != challenge
        or observation.get("runtime_context_sha256") != context_sha
    ):
        raise LauncherError("sandbox observation challenge/runtime-context binding drifted")
    required_true = (
        "dev_directory_write_denied",
        "forbidden_host_data_roots_absent",
        "gpu_visible_inside_sandbox",
        "output_root_capacity_enforced",
        "proc_write_denied",
        "runtime_support_roots_present",
    )
    if (
        control.get("challenge") != challenge
        or control.get("runtime_context_sha256") != context_sha
    ):
        raise LauncherError("sandbox control evidence challenge/runtime-context binding drifted")
    if control.get("gpu_observation") != expected_gpu:
        raise LauncherError("GPU identity changed across the sandbox boundary")
    if any(control.get(field) is not True for field in required_true):
        raise LauncherError("sandbox control evidence did not prove every required control")
    if (
        control.get("output_filesystem_type") != "tmpfs"
        or control.get("maximum_total_bytes") != MAX_OUTPUT_BYTES
    ):
        raise LauncherError("sandbox output tmpfs identity drifted")
    capacity = control.get("output_mount_capacity_bytes")
    if type(capacity) is not int or capacity > MAX_OUTPUT_BYTES:
        raise LauncherError("sandbox output mount exceeds frozen byte budget")
    if control.get("allowed_artifact_names") != [
        "sandbox-observation.json",
        "sandbox-control-evidence.json",
    ]:
        raise LauncherError("sandbox control evidence allowed-artifact set drifted")
    if control.get("undeclared_artifact_present") is not False:
        raise LauncherError("sandbox control evidence reports an undeclared artifact")
    return observation_raw, control_raw, total


def main() -> None:
    """Execute one bounded, non-scientific, real hosted sandbox qualification probe."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--model-weights", type=Path, required=True)
    parser.add_argument("--custody-dir", type=Path, required=True)
    parser.add_argument("--challenge", required=True)
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise LauncherError("MRL-0808 hosted launcher requires Linux")
    if SHA64.fullmatch(args.challenge) is None:
        raise LauncherError("challenge must be 64 lowercase hex")
    runtime_id = os.environ.get("MESC_COLAB_RUNTIME_ID", "").strip()
    release = os.environ.get("COLAB_RELEASE_TAG", "").strip()
    if not runtime_id or "\x00" in runtime_id or not release or "\x00" in release:
        raise LauncherError("missing/invalid independently obtained Colab runtime identity/family")

    root = existing_dir(args.repository_root, "repository")
    inputs = existing_dir(args.inputs, "inputs")
    weights = existing_dir(args.model_weights, "model weights")
    custody = existing_dir(args.custody_dir, "custody")
    require_outside_repository(inputs, root, "inputs")
    require_outside_repository(weights, root, "model weights")
    require_outside_repository(custody, root, "custody")
    require_empty(custody, "custody")
    require_synthetic_qualification_inputs(inputs, weights)
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
        raise LauncherError("launcher requires exact canonical main")
    if git(root, "status", "--porcelain", "--untracked-files=all") or git(root, "clean", "-ndx"):
        raise LauncherError("repository must be clean")
    require_exact_sources(root)

    bwrap_raw = shutil.which("bwrap")
    if not bwrap_raw:
        raise LauncherError("bubblewrap is required; install during setup outside isolated window")
    bwrap = Path(bwrap_raw).resolve(strict=True)
    bwrap_sha = sha256_file(bwrap)
    bwrap_version = subprocess.check_output([str(bwrap), "--version"], text=True).strip()
    gpu = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,uuid,memory.total", "--format=csv,noheader,nounits"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if gpu.returncode != 0:
        raise LauncherError("qualified hosted runtime must expose nvidia-smi")
    gpu_lines = [line.strip() for line in gpu.stdout.splitlines() if line.strip()]
    if len(gpu_lines) != 1:
        raise LauncherError("exactly one hosted GPU is required")
    devices = nvidia_device_nodes()
    prefix, runtime_symlinks = sandbox_prefix(
        bwrap=bwrap,
        repository=root,
        inputs=inputs,
        weights=weights,
        nvidia_nodes=devices,
    )
    context = {
        "bubblewrap_binary_sha256": bwrap_sha,
        "bubblewrap_version": bwrap_version,
        "colab_release_tag": release,
        "direct_host_root_bind": False,
        "gpu_observation": gpu_lines[0],
        "kernel_release": platform.release(),
        "model_weights_directory_empty": True,
        "nvidia_device_nodes": [str(path) for path in devices],
        "output_tmpfs_maximum_bytes": MAX_OUTPUT_BYTES,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": runtime_id,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "python_version": platform.python_version(),
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_support_read_only_roots": ["/etc/ld.so.cache", "/sys", "/usr"],
        "runtime_support_symlinks": runtime_symlinks,
        "schema_version": "MESC-MRL-0808-RUNTIME-CONTEXT-V1",
        "scratch_tmpfs_maximum_bytes": MAX_SCRATCH_BYTES,
        "synthetic_input_sha256": hashlib.sha256(SYNTHETIC_INPUT_BYTES).hexdigest(),
    }
    context_raw = canonical_json_bytes(context)
    context_sha = hashlib.sha256(context_raw).hexdigest()
    env = sandbox_env(args.challenge, context_sha)
    supervisor_path = "/mesc-run/repository/" + SUPERVISOR.as_posix()

    normal = run_sandbox(
        prefix, env, ["/usr/bin/env", "python3", supervisor_path, "--mode", "normal"]
    )
    if normal.returncode != 0:
        raise LauncherError(
            "sandbox supervisor failed: " + normal.stderr.decode("utf-8", "replace")[-4000:]
        )
    observation_raw, control_raw, collected_bytes = collection_artifacts(
        normal.stdout,
        expected_gpu=gpu_lines[0],
        context_sha=context_sha,
        challenge=args.challenge,
    )
    observation_sha = hashlib.sha256(observation_raw).hexdigest()
    control_sha = hashlib.sha256(control_raw).hexdigest()

    undeclared = run_sandbox(
        prefix,
        env,
        ["/usr/bin/env", "python3", supervisor_path, "--mode", "undeclared-output"],
    )
    if undeclared.returncode != 43 or b"MRL0808_UNDECLARED_OUTPUT_BLOCKED" not in undeclared.stderr:
        raise LauncherError("undeclared output-class challenge was not blocked")
    budget = run_sandbox(
        prefix,
        env,
        ["/usr/bin/env", "python3", supervisor_path, "--mode", "output-budget"],
    )
    if budget.returncode != 42 or b"MRL0808_OUTPUT_BUDGET_BLOCKED" not in budget.stderr:
        raise LauncherError("output byte-budget challenge was not blocked")

    forbidden_relative = Path(".mrl0808-forbidden-write")
    forbidden_host = root / forbidden_relative
    if forbidden_host.exists():
        raise LauncherError("forbidden-write sentinel already exists")
    violation_code = (
        "from pathlib import Path; "
        "Path('/mesc-run/repository/.mrl0808-forbidden-write').write_bytes(b'forbidden')"
    )
    violation = run_sandbox(
        prefix,
        {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
        ["/usr/bin/env", "python3", "-c", violation_code],
    )
    if violation.returncode == 0 or forbidden_host.exists():
        raise LauncherError("forbidden repository write was not stopped")

    cleanup = {
        "challenge": args.challenge,
        "collected_bytes_before_cleanup": collected_bytes + len(context_raw),
        "forbidden_repository_write_absent": True,
        "minimal_runtime_root_enforced": True,
        "normal_probe_exit_code": 0,
        "observation_sha256": observation_sha,
        "output_budget_challenge_blocked": True,
        "output_tmpfs_destroyed_after_namespace_exit": True,
        "repository_sha": head,
        "repository_tree": tree,
        "runtime_context_sha256": context_sha,
        "sandbox_control_evidence_sha256": control_sha,
        "sandbox_policy_sha256": POLICY,
        "schema_version": "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1",
        "scratch_tmpfs_destroyed_after_namespace_exit": True,
        "state": "COMPLETED",
        "undeclared_output_challenge_blocked": True,
        "violation_probe_stopped": True,
    }
    cleanup_raw = canonical_json_bytes(cleanup)
    if (
        len(context_raw) + len(observation_raw) + len(control_raw) + len(cleanup_raw)
        > MAX_OUTPUT_BYTES
    ):
        raise LauncherError("collected control-plane custody exceeds frozen output budget")
    write_new(custody / "runtime-context.json", context_raw)
    write_new(custody / "sandbox-observation.json", observation_raw)
    write_new(custody / "sandbox-control-evidence.json", control_raw)
    write_new(custody / "sandbox-cleanup-receipt.json", cleanup_raw)
    print("RUNTIME_CONTEXT_SHA256=" + context_sha)
    print("OBSERVATION_SHA256=" + observation_sha)
    print("SANDBOX_CONTROL_EVIDENCE_SHA256=" + control_sha)
    print("CLEANUP_RECEIPT_SHA256=" + hashlib.sha256(cleanup_raw).hexdigest())
    print("PROVIDER_EXECUTION_ID=" + runtime_id)
    print("MONETARY_COST_MICROUNITS=UNATTESTED_REQUIRES_INDEPENDENT_CONTROL_PLANE_REVIEW")


if __name__ == "__main__":
    main()
