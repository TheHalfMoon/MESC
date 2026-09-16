from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

import medscale.mesc._mrl_0808_sandbox_v1 as sandbox
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_ROOT = Path(__file__).resolve().parents[1]
_AUTH = _ROOT / "specs/mesc-experiment-0/mrl-0808-sandbox-authorization-v1.json"
_POLICIES = {
    "network": _ROOT / "specs/mesc-experiment-0/mrl-0808-network-policy-v1.json",
    "mutation": _ROOT / "specs/mesc-experiment-0/mrl-0808-mutation-paths-v1.json",
    "output": _ROOT / "specs/mesc-experiment-0/mrl-0808-output-destinations-v1.json",
    "stop": _ROOT / "specs/mesc-experiment-0/mrl-0808-stop-conditions-v1.json",
    "sandbox": _ROOT / "specs/mesc-experiment-0/mrl-0808-sandbox-policy-v1.json",
}
_PROBE = _ROOT / "scripts/mesc_mrl_0808_sandbox_probe.py"
_SUPERVISOR = _ROOT / "scripts/mesc_mrl_0808_sandbox_supervisor.py"
_LAUNCHER = _ROOT / "scripts/mesc_mrl_0808_colab_sandbox_launch.py"
_CHALLENGE = _ROOT / "scripts/mesc_mrl_0808_sandbox_challenge.py"
_ATTEST = _ROOT / "scripts/mesc_mrl_0808_sandbox_attest.py"
_QUALIFIER = _ROOT / "scripts/mesc_mrl_0808_sandbox_qualify.py"
_SLOT = _ROOT / "specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0808.json"
_TASKS = _ROOT / "specs/mesc-research-loop-v1/tasks.md"
_REPO_SHA = "1" * 40
_REPO_TREE = "2" * 40
_CHALLENGE_HEX = "3" * 64
_PROVIDER_ID = "colab-runtime-test-001"

_EXPECTED_SHA = {
    _AUTH: "838c7ed0b8aafd9f85a89d96846486660d0f54ba0e50c0ebec1a415a6b328575",
    _POLICIES["network"]: "4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f",
    _POLICIES["mutation"]: "044c61563880e630e079fad1e762aa5c9d3af505099a801070ef57d750633691",
    _POLICIES["output"]: "2b6c79b5662d3e91f107bf24d00155b8df0b4a1c96b0ad48284451afd0cbb8ea",
    _POLICIES["stop"]: "607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194",
    _POLICIES["sandbox"]: "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316",
}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(document: object) -> bytes:
    return canonical_json_bytes(document)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert type(value) is dict
    return cast(dict[str, Any], value)


def _synthetic_bundle(
    *,
    challenge: str = _CHALLENGE_HEX,
    repository_sha: str = _REPO_SHA,
    repository_tree: str = _REPO_TREE,
) -> dict[str, bytes]:
    context = {
        "bubblewrap_binary_sha256": "4" * 64,
        "bubblewrap_version": "bubblewrap 0.11.0",
        "colab_release_tag": "colab-test-release",
        "direct_host_root_bind": False,
        "gpu_observation": "Tesla T4, GPU-test, 15360",
        "kernel_release": "6.1.0-test",
        "model_weights_directory_empty": True,
        "nvidia_device_nodes": ["/dev/nvidia0", "/dev/nvidiactl"],
        "output_tmpfs_maximum_bytes": 67_108_864,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": _PROVIDER_ID,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "python_version": "3.11.15",
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_support_read_only_roots": ["/etc/ld.so.cache", "/sys", "/usr"],
        "runtime_support_symlinks": {
            "/bin": "usr/bin",
            "/lib": "usr/lib",
            "/sbin": "usr/sbin",
        },
        "schema_version": "MESC-MRL-0808-RUNTIME-CONTEXT-V1",
        "scratch_tmpfs_maximum_bytes": 268_435_456,
        "synthetic_input_sha256": _sha(b"MESC-MRL-0808-SYNTHETIC-READ-PROBE-V1\n"),
    }
    context_raw = _canonical(context)
    context_sha = _sha(context_raw)
    controls = {
        "cloud_metadata_access_denied": True,
        "control_sockets_absent": True,
        "credential_environment_empty": True,
        "dns_unavailable": True,
        "home_write_denied": True,
        "inputs_read_only_enforced": True,
        "model_weights_read_only_enforced": True,
        "network_egress_denied": True,
        "output_write_allowed": True,
        "repository_read_only_enforced": True,
        "root_write_denied": True,
        "scratch_write_allowed": True,
        "synthetic_input_read_allowed": True,
        "tmp_write_denied": True,
    }
    observation = {
        "challenge": challenge,
        "controls": controls,
        "monetary_cost_microunits": 0,
        "model_loaded": False,
        "mutation_paths_sha256": _EXPECTED_SHA[_POLICIES["mutation"]],
        "network_policy_sha256": _EXPECTED_SHA[_POLICIES["network"]],
        "output_destinations_sha256": _EXPECTED_SHA[_POLICIES["output"]],
        "predecessor_runtime_evidence_sha256": sandbox._EXPECTED_RUNTIME_EVIDENCE,
        "predecessor_runtime_identity_sha256": sandbox._EXPECTED_RUNTIME_IDENTITY,
        "runtime_context_sha256": context_sha,
        "sandbox_policy_sha256": _EXPECTED_SHA[_POLICIES["sandbox"]],
        "schema_version": "MESC-MRL-0808-RUNTIME-SANDBOX-OBSERVATION-V1",
        "sealed_tier3_item_content_accessed": False,
        "stop_conditions_sha256": _EXPECTED_SHA[_POLICIES["stop"]],
        "tokenizer_loaded": False,
        "training_performed": False,
        "weight_mutation_performed": False,
    }
    observation_raw = _canonical(observation)
    observation_sha = _sha(observation_raw)
    control = {
        "allowed_artifact_names": [
            "sandbox-observation.json",
            "sandbox-control-evidence.json",
        ],
        "challenge": challenge,
        "dev_directory_write_denied": True,
        "forbidden_host_data_roots_absent": True,
        "gpu_observation": context["gpu_observation"],
        "gpu_visible_inside_sandbox": True,
        "maximum_total_bytes": 67_108_864,
        "output_filesystem_type": "tmpfs",
        "output_mount_capacity_bytes": 67_108_864,
        "output_root": "/mesc-run/output",
        "output_root_capacity_enforced": True,
        "proc_write_denied": True,
        "runtime_context_sha256": context_sha,
        "runtime_support_roots_present": True,
        "schema_version": "MESC-MRL-0808-SANDBOX-CONTROL-EVIDENCE-V1",
        "undeclared_artifact_present": False,
    }
    control_raw = _canonical(control)
    control_sha = _sha(control_raw)
    cleanup = {
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
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_context_sha256": context_sha,
        "sandbox_control_evidence_sha256": control_sha,
        "sandbox_policy_sha256": _EXPECTED_SHA[_POLICIES["sandbox"]],
        "schema_version": "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1",
        "scratch_tmpfs_destroyed_after_namespace_exit": True,
        "state": "COMPLETED",
        "undeclared_output_challenge_blocked": True,
        "violation_probe_stopped": True,
    }
    cleanup_raw = _canonical(cleanup)
    cleanup_sha = _sha(cleanup_raw)
    challenge_receipt = {
        "challenge": challenge,
        "cleanup_receipt_sha256": cleanup_sha,
        "observation_sha256": observation_sha,
        "sandbox_control_evidence_sha256": control_sha,
        "predecessor_runtime_evidence_sha256": sandbox._EXPECTED_RUNTIME_EVIDENCE,
        "predecessor_runtime_identity_sha256": sandbox._EXPECTED_RUNTIME_IDENTITY,
        "provider_execution_id": _PROVIDER_ID,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_context_sha256": context_sha,
        "sandbox_policy_sha256": _EXPECTED_SHA[_POLICIES["sandbox"]],
        "schema_version": "MESC-MRL-0808-SANDBOX-CHALLENGE-RECEIPT-V1",
        "state": "CONSUMED",
        "task_id": "MRL-0808",
    }
    challenge_raw = _canonical(challenge_receipt)
    attestation = {
        "attestation_state": "COMPLETED",
        "challenge": challenge,
        "challenge_receipt_sha256": _sha(challenge_raw),
        "challenge_state": "CONSUMED",
        "cleanup_receipt_sha256": cleanup_sha,
        "sandbox_control_evidence_sha256": control_sha,
        "independent_verification_method": "control-plane-session-review",
        "independent_verification_reference": "synthetic-test-reference",
        "monetary_cost_microunits": 0,
        "observation_sha256": observation_sha,
        "policy_sha256": _EXPECTED_SHA[_POLICIES["sandbox"]],
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": _PROVIDER_ID,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_context_sha256": context_sha,
        "schema_version": "MESC-MRL-0808-RUNTIME-SANDBOX-ATTESTATION-V1",
    }
    return {
        "runtime_context": context_raw,
        "observation": observation_raw,
        "control": control_raw,
        "cleanup": cleanup_raw,
        "challenge": challenge_raw,
        "attestation": _canonical(attestation),
    }


def _qualify(
    bundle: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> sandbox.SandboxQualification:
    attestation_sha = _sha(bundle["attestation"])
    monkeypatch.setattr(
        sandbox,
        "TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256",
        frozenset({attestation_sha}),
    )
    return sandbox.qualify_mrl_0808_sandbox(
        authorization_bytes=_AUTH.read_bytes(),
        network_policy_bytes=_POLICIES["network"].read_bytes(),
        mutation_policy_bytes=_POLICIES["mutation"].read_bytes(),
        output_policy_bytes=_POLICIES["output"].read_bytes(),
        stop_policy_bytes=_POLICIES["stop"].read_bytes(),
        sandbox_policy_bytes=_POLICIES["sandbox"].read_bytes(),
        runtime_context_bytes=bundle["runtime_context"],
        observation_bytes=bundle["observation"],
        sandbox_control_evidence_bytes=bundle["control"],
        cleanup_receipt_bytes=bundle["cleanup"],
        challenge_receipt_bytes=bundle["challenge"],
        runtime_attestation_bytes=bundle["attestation"],
        repository_sha=_REPO_SHA,
        repository_tree=_REPO_TREE,
    )


def _mutate(raw: bytes, key: str, value: object) -> bytes:
    document = json.loads(raw.decode("utf-8"))
    document[key] = value
    return _canonical(document)


def _run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_ROOT / "src")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_script(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_authorization_and_policy_bytes_are_exact_owner_bounded_and_non_scientific() -> None:
    for path, expected in _EXPECTED_SHA.items():
        raw = path.read_bytes()
        assert raw.endswith(b"\n")
        assert _sha(raw) == expected
        assert canonical_json_bytes(json.loads(raw.decode("utf-8"))) == raw
    auth = _read_json(_AUTH)
    assert auth["authority_source"] == {
        "author_association": "OWNER",
        "author_login": "TheHalfMoon",
        "body_sha256": "fa45c02db6961714e2abc247102b39d5ba830c8b0de282a4bf709a010ac6e286",
        "created_at": "2026-09-15T17:45:34Z",
        "issue_node_id": "I_kwDOTT9yMs8AAAABRcQ2Ng",
        "issue_number": 424,
    }
    assert auth["authorized_base"]["main_sha"] == "520aec7630441f43c7b14f3603533f4533a71bbe"
    assert auth["authorized_base"]["main_tree"] == "2b0b64bbbe0a5c89dad61ca05b17a8488f95f8e1"
    assert auth["runtime_binding"]["provider"] == "GOOGLE_COLAB"
    assert auth["runtime_binding"]["runtime_instance_must_be_freshly_attested"] is True
    for field in (
        "model_loading_authorized",
        "paid_compute_spend_authorized",
        "scientific_evaluation_execution_authorized",
        "scientific_model_execution_authorized",
        "sealed_tier3_item_disclosure_authorized",
        "tokenizer_loading_authorized",
        "training_authorized",
        "training_ready",
        "weight_mutation_authorized",
    ):
        assert auth["policy"][field] is False


def test_producer_starts_with_empty_attestation_trust_and_does_not_admit_outer_evidence() -> None:
    assert frozenset() == sandbox.TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256
    assert _read_json(_SLOT) == {
        "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-SLOT-V1",
        "state": "ABSENT",
        "task_id": "MRL-0808",
    }
    tasks = _TASKS.read_text(encoding="utf-8")
    assert "- [ ] **MRL-0808 — Verify real execution sandbox**" in tasks
    assert "- [x] **MRL-0808 — Verify real execution sandbox**" not in tasks


def test_trusted_synthetic_bundle_is_deterministic_and_outer_parser_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    first = _qualify(bundle, monkeypatch)
    second = _qualify(bundle, monkeypatch)
    assert first == second
    assert first.runtime_context_sha256 == _sha(bundle["runtime_context"])
    assert first.cleanup_receipt_sha256 == _sha(bundle["cleanup"])
    assert first.sandbox_control_evidence_sha256 == _sha(bundle["control"])
    assert first.attestation_sha256 == _sha(bundle["attestation"])
    parsed = parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0808"
    assert parsed.kind == "mesc.mrl.real_preflight.sandbox.v1"
    assert parsed.evidence_sha256 == first.evidence_sha256
    document = cast(dict[str, Any], json.loads(first.evidence_bytes.decode("utf-8")))
    payload = cast(dict[str, Any], document["payload"])
    assert document["disposition"] == "PASS"
    assert payload["sandbox_qualified"] is True
    assert payload["network_policy_enforced"] is True


def test_untrusted_attestation_cannot_emit_sandbox_qualified_evidence() -> None:
    bundle = _synthetic_bundle()
    with pytest.raises(sandbox.MRL0808SandboxError, match="not admitted by canonical trust"):
        sandbox.qualify_mrl_0808_sandbox(
            authorization_bytes=_AUTH.read_bytes(),
            network_policy_bytes=_POLICIES["network"].read_bytes(),
            mutation_policy_bytes=_POLICIES["mutation"].read_bytes(),
            output_policy_bytes=_POLICIES["output"].read_bytes(),
            stop_policy_bytes=_POLICIES["stop"].read_bytes(),
            sandbox_policy_bytes=_POLICIES["sandbox"].read_bytes(),
            runtime_context_bytes=bundle["runtime_context"],
            observation_bytes=bundle["observation"],
            sandbox_control_evidence_bytes=bundle["control"],
            cleanup_receipt_bytes=bundle["cleanup"],
            challenge_receipt_bytes=bundle["challenge"],
            runtime_attestation_bytes=bundle["attestation"],
            repository_sha=_REPO_SHA,
            repository_tree=_REPO_TREE,
        )


@pytest.mark.parametrize("policy_name", ["network", "mutation", "output", "stop", "sandbox"])
def test_policy_byte_drift_fails_closed(policy_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _synthetic_bundle()
    attestation_sha = _sha(bundle["attestation"])
    monkeypatch.setattr(
        sandbox,
        "TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256",
        frozenset({attestation_sha}),
    )
    policy_bytes = {name: path.read_bytes() for name, path in _POLICIES.items()}
    policy_bytes[policy_name] += b" "
    with pytest.raises(sandbox.MRL0808SandboxError, match="digest drifted"):
        sandbox.qualify_mrl_0808_sandbox(
            authorization_bytes=_AUTH.read_bytes(),
            network_policy_bytes=policy_bytes["network"],
            mutation_policy_bytes=policy_bytes["mutation"],
            output_policy_bytes=policy_bytes["output"],
            stop_policy_bytes=policy_bytes["stop"],
            sandbox_policy_bytes=policy_bytes["sandbox"],
            runtime_context_bytes=bundle["runtime_context"],
            observation_bytes=bundle["observation"],
            sandbox_control_evidence_bytes=bundle["control"],
            cleanup_receipt_bytes=bundle["cleanup"],
            challenge_receipt_bytes=bundle["challenge"],
            runtime_attestation_bytes=bundle["attestation"],
            repository_sha=_REPO_SHA,
            repository_tree=_REPO_TREE,
        )


def test_false_control_or_authority_escalation_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _synthetic_bundle()
    observation = json.loads(bundle["observation"].decode("utf-8"))
    observation["controls"]["network_egress_denied"] = False
    bundle["observation"] = _canonical(observation)
    with pytest.raises(
        sandbox.MRL0808SandboxError, match=r"controls\.network_egress_denied must be true"
    ):
        _qualify(bundle, monkeypatch)


def test_runtime_context_provider_or_repository_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value, message in (
        ("provider", "LOCAL_DOCKER", "not the qualified Google Colab class"),
        ("repository_sha", "9" * 40, "repository SHA drifted"),
    ):
        bundle = _synthetic_bundle()
        bundle["runtime_context"] = _mutate(bundle["runtime_context"], key, value)
        with pytest.raises(sandbox.MRL0808SandboxError, match=message):
            _qualify(bundle, monkeypatch)


def test_sandbox_control_evidence_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _synthetic_bundle()
    bundle["control"] = _mutate(bundle["control"], "output_root_capacity_enforced", False)
    with pytest.raises(
        sandbox.MRL0808SandboxError, match="output_root_capacity_enforced must be true"
    ):
        _qualify(bundle, monkeypatch)

    bundle = _synthetic_bundle()
    bundle["control"] = _mutate(bundle["control"], "maximum_total_bytes", 67_108_865)
    with pytest.raises(sandbox.MRL0808SandboxError, match="output budget drifted"):
        _qualify(bundle, monkeypatch)


def test_cleanup_or_challenge_replay_semantics_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = _synthetic_bundle()
    bundle["cleanup"] = _mutate(bundle["cleanup"], "violation_probe_stopped", False)
    with pytest.raises(sandbox.MRL0808SandboxError, match="violation_probe_stopped must be true"):
        _qualify(bundle, monkeypatch)

    bundle = _synthetic_bundle()
    bundle["challenge"] = _mutate(bundle["challenge"], "state", "ISSUED")
    with pytest.raises(sandbox.MRL0808SandboxError, match="not one consumed MRL-0808 challenge"):
        _qualify(bundle, monkeypatch)


def test_attestation_cost_provider_or_cleanup_binding_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key, value, message in (
        ("monetary_cost_microunits", 1, "must be integer zero"),
        ("provider", "HUGGING_FACE_JOBS", "not the qualified Google Colab class"),
        ("cleanup_receipt_sha256", "9" * 64, "does not bind exact cleanup receipt"),
    ):
        bundle = _synthetic_bundle()
        bundle["attestation"] = _mutate(bundle["attestation"], key, value)
        with pytest.raises(sandbox.MRL0808SandboxError, match=message):
            _qualify(bundle, monkeypatch)


def test_launcher_rejects_symlink_directory_and_source_endpoints(tmp_path: Path) -> None:
    launcher = _load_script(_LAUNCHER, "mrl0808_launcher_symlink_test")
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)

    assert launcher.existing_dir(real, "real") == real.resolve()
    with pytest.raises(launcher.LauncherError, match="must be a real directory"):
        launcher.existing_dir(link, "linked")

    source_root = tmp_path / "source-root"
    source_root.mkdir()
    target = tmp_path / "launcher.py"
    target.write_text("# synthetic\n", encoding="utf-8")
    source = source_root / launcher.LAUNCHER
    source.parent.mkdir(parents=True)
    source.symlink_to(target)
    with pytest.raises(launcher.LauncherError, match="required source is unsafe"):
        launcher.require_exact_sources(source_root)

    with pytest.raises(launcher.LauncherError, match="must remain outside repository"):
        launcher.require_outside_repository(_ROOT / "specs", _ROOT, "custody")
    launcher.require_outside_repository(tmp_path, _ROOT, "custody")


def test_challenge_ledger_must_remain_outside_repository() -> None:
    challenge = _load_script(_CHALLENGE, "mrl0808_challenge_external_ledger_test")
    with pytest.raises(SystemExit, match="verifier ledger must remain outside repository"):
        challenge.verifier_ledger(str(_ROOT))


def test_challenge_cli_consumes_once_and_cancelled_challenge_cannot_be_consumed(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    issued_run = _run_script(
        _CHALLENGE,
        "issue",
        "--repository-sha",
        _REPO_SHA,
        "--repository-tree",
        _REPO_TREE,
        "--ledger-dir",
        str(ledger),
    )
    assert issued_run.returncode == 0, issued_run.stderr
    issuance = Path(issued_run.stdout.strip())
    issued = _read_json(issuance)
    bundle = _synthetic_bundle(challenge=issued["challenge"])
    files: dict[str, Path] = {}
    for name in ("runtime_context", "observation", "control", "cleanup"):
        path = tmp_path / f"{name}.json"
        path.write_bytes(bundle[name])
        files[name] = path
    consume_args = (
        "consume",
        "--issuance",
        str(issuance),
        "--observation",
        str(files["observation"]),
        "--runtime-context",
        str(files["runtime_context"]),
        "--sandbox-control-evidence",
        str(files["control"]),
        "--cleanup-receipt",
        str(files["cleanup"]),
        "--provider-execution-id",
        _PROVIDER_ID,
        "--ledger-dir",
        str(ledger),
    )
    first = _run_script(_CHALLENGE, *consume_args)
    assert first.returncode == 0, first.stderr
    second = _run_script(_CHALLENGE, *consume_args)
    assert second.returncode != 0
    assert "already consumed" in second.stderr

    ledger2 = tmp_path / "ledger2"
    ledger2.mkdir()
    issued2 = _run_script(
        _CHALLENGE,
        "issue",
        "--repository-sha",
        _REPO_SHA,
        "--repository-tree",
        _REPO_TREE,
        "--ledger-dir",
        str(ledger2),
    )
    issuance2 = Path(issued2.stdout.strip())
    cancelled = _run_script(
        _CHALLENGE,
        "cancel",
        "--issuance",
        str(issuance2),
        "--reason",
        "synthetic cancellation",
        "--ledger-dir",
        str(ledger2),
    )
    assert cancelled.returncode == 0, cancelled.stderr
    issue2 = _read_json(issuance2)
    bundle2 = _synthetic_bundle(challenge=issue2["challenge"])
    for name in ("runtime_context", "observation", "control", "cleanup"):
        (tmp_path / f"second-{name}.json").write_bytes(bundle2[name])
    denied = _run_script(
        _CHALLENGE,
        "consume",
        "--issuance",
        str(issuance2),
        "--observation",
        str(tmp_path / "second-observation.json"),
        "--runtime-context",
        str(tmp_path / "second-runtime_context.json"),
        "--sandbox-control-evidence",
        str(tmp_path / "second-control.json"),
        "--cleanup-receipt",
        str(tmp_path / "second-cleanup.json"),
        "--provider-execution-id",
        _PROVIDER_ID,
        "--ledger-dir",
        str(ledger2),
    )
    assert denied.returncode != 0
    assert "cancelled" in denied.stderr


def test_challenge_cli_rejects_forged_issuance_and_serializes_terminal_transition(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    issued_run = _run_script(
        _CHALLENGE,
        "issue",
        "--repository-sha",
        _REPO_SHA,
        "--repository-tree",
        _REPO_TREE,
        "--ledger-dir",
        str(ledger),
    )
    assert issued_run.returncode == 0, issued_run.stderr
    issuance = Path(issued_run.stdout.strip())
    issued = _read_json(issuance)
    challenge = issued["challenge"]

    forged = ledger / "forged-issued.json"
    forged.write_bytes(issuance.read_bytes())

    forged_run = _run_script(
        _CHALLENGE,
        "cancel",
        "--issuance",
        str(forged),
        "--reason",
        "must reject forged ledger entry",
        "--ledger-dir",
        str(ledger),
    )
    assert forged_run.returncode != 0
    assert "filename does not bind challenge" in forged_run.stderr

    issuance_link = ledger / "issuance-link.json"
    issuance_link.symlink_to(issuance)
    linked_run = _run_script(
        _CHALLENGE,
        "cancel",
        "--issuance",
        str(issuance_link),
        "--reason",
        "must reject symlink issuance",
        "--ledger-dir",
        str(ledger),
    )
    assert linked_run.returncode != 0
    assert "issuance must not be a symlink" in linked_run.stderr

    lock = ledger / f".{challenge}.terminal-transition.lock"
    lock.mkdir()
    blocked = _run_script(
        _CHALLENGE,
        "cancel",
        "--issuance",
        str(issuance),
        "--reason",
        "must serialize terminal transition",
        "--ledger-dir",
        str(ledger),
    )
    assert blocked.returncode != 0
    assert "terminal transition already in progress" in blocked.stderr
    assert not (ledger / f"{challenge}.cancelled.json").exists()
    assert not (ledger / f"{challenge}.consumed.json").exists()
    lock.rmdir()


def test_attestation_renderer_requires_consumed_challenge_and_exact_custody(tmp_path: Path) -> None:
    bundle = _synthetic_bundle()
    paths: dict[str, Path] = {}
    for name in ("runtime_context", "observation", "control", "cleanup", "challenge"):
        path = tmp_path / f"{name}.json"
        path.write_bytes(bundle[name])
        paths[name] = path
    output = tmp_path / "attestation.json"
    run = _run_script(
        _ATTEST,
        "--challenge-receipt",
        str(paths["challenge"]),
        "--observation",
        str(paths["observation"]),
        "--runtime-context",
        str(paths["runtime_context"]),
        "--sandbox-control-evidence",
        str(paths["control"]),
        "--cleanup-receipt",
        str(paths["cleanup"]),
        "--repository-sha",
        _REPO_SHA,
        "--repository-tree",
        _REPO_TREE,
        "--provider-execution-id",
        _PROVIDER_ID,
        "--verification-method",
        "synthetic-control-plane-review",
        "--verification-reference",
        "synthetic-reference",
        "--output",
        str(output),
    )
    assert run.returncode == 0, run.stderr
    rendered = _read_json(output)
    assert rendered["challenge_state"] == "CONSUMED"
    assert rendered["cleanup_receipt_sha256"] == _sha(bundle["cleanup"])
    assert rendered["sandbox_control_evidence_sha256"] == _sha(bundle["control"])
    assert rendered["runtime_context_sha256"] == _sha(bundle["runtime_context"])


def test_qualifier_rejects_symlink_repository_external_and_output_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualifier = _load_script(_QUALIFIER, "mrl0808_qualifier_symlink_test")

    real_repo = tmp_path / "real-repo"
    real_repo.mkdir()
    repo_link = tmp_path / "repo-link"
    repo_link.symlink_to(real_repo, target_is_directory=True)
    with pytest.raises(qualifier.EntrypointError, match="repository-root must not be a symlink"):
        qualifier.clean_root(repo_link)

    real_file = tmp_path / "real.json"
    real_file.write_text("{}\n", encoding="utf-8")
    file_link = tmp_path / "file-link.json"
    file_link.symlink_to(real_file)
    with pytest.raises(qualifier.EntrypointError, match="regular non-symlink file"):
        qualifier.external(file_link, real_repo, "runtime context")

    real_output = tmp_path / "real-output"
    real_output.mkdir()
    output_link = tmp_path / "output-link"
    output_link.symlink_to(real_output, target_is_directory=True)
    with pytest.raises(qualifier.EntrypointError, match="existing non-symlink directory"):
        qualifier.output_root(output_link, real_repo, False)

    fake_root = tmp_path / "fake-root"
    fake_root.mkdir()
    source_target = tmp_path / "source.py"
    source_target.write_text("# synthetic\n", encoding="utf-8")
    source_path = fake_root / qualifier.MODULE
    source_path.parent.mkdir(parents=True)
    source_path.symlink_to(source_target)

    def fake_git_text(_root: Path, *args: str) -> str:
        if args == ("rev-parse", "--show-toplevel"):
            return str(fake_root)
        if args == ("status", "--porcelain", "--untracked-files=all"):
            return ""
        if args == ("clean", "-ndx"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(qualifier, "git_text", fake_git_text)
    with pytest.raises(qualifier.EntrypointError, match="unsafe required source"):
        qualifier.clean_root(fake_root)


def test_attestation_renderer_requires_external_non_symlink_custody(tmp_path: Path) -> None:
    attest = _load_script(_ATTEST, "mrl0808_attest_external_test")
    with pytest.raises(SystemExit, match="must remain outside repository"):
        attest.external_file(str(_AUTH), "authorization")
    with pytest.raises(SystemExit, match="output must remain outside repository"):
        attest.external_output(str(_ROOT / "runtime-sandbox-attestation.json"))

    external = tmp_path / "external.json"
    external.write_text("{}\n", encoding="utf-8")
    link = tmp_path / "external-link.json"
    link.symlink_to(external)
    with pytest.raises(SystemExit, match="non-symlink external file"):
        attest.external_file(str(link), "runtime context")


def test_supervisor_undeclared_output_challenge_has_complete_declared_set_plus_extra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor = _load_script(_SUPERVISOR, "mrl0808_supervisor_extra_output_test")
    monkeypatch.setattr(supervisor, "OUTPUT_ROOT", tmp_path)
    assert supervisor.undeclared_output_challenge() == 43
    assert {path.name for path in tmp_path.iterdir()} == {
        supervisor.OBSERVATION_NAME,
        supervisor.CONTROL_NAME,
        "undeclared-output.bin",
    }


def test_probe_and_launcher_contain_no_model_loading_training_or_paid_compute_primitives() -> None:
    for path in (_PROBE, _SUPERVISOR, _LAUNCHER, _CHALLENGE, _ATTEST, _QUALIFIER):
        source = path.read_text(encoding="utf-8")
        for token in (
            "AutoModel",
            "AutoProcessor",
            "AutoTokenizer",
            "from_pretrained",
            "SFTTrainer",
            "optimizer.step",
            ".backward(",
            "bitsandbytes",
            "huggingface_hub.create_job",
        ):
            assert token not in source
    probe_imports = {
        alias.name.split(".")[0]
        for node in ast.walk(ast.parse(_PROBE.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert probe_imports.isdisjoint({"subprocess", "requests", "httpx", "urllib"})


def test_launcher_declares_minimal_root_bounded_output_and_stop_controls() -> None:
    source = _LAUNCHER.read_text(encoding="utf-8")
    supervisor = _SUPERVISOR.read_text(encoding="utf-8")
    for token in (
        '"--unshare-all"',
        '"--clearenv"',
        '"--die-with-parent"',
        '"--new-session"',
        '"--remount-ro"',
        '"--size"',
        '"--tmpfs"',
        '"/mesc-run/repository"',
        '"/mesc-run/model-weights"',
        '"/mesc-run/inputs"',
        '"/mesc-run/scratch"',
        '"/mesc-run/output"',
        ".mrl0808-forbidden-write",
        "MRL0808_UNDECLARED_OUTPUT_BLOCKED",
        "MRL0808_OUTPUT_BUDGET_BLOCKED",
        "mrl0808-synthetic-input.txt",
        "model-weights directory must remain empty",
    ):
        assert token in source or token in supervisor
    assert '"--share-net"' not in source
    assert '"--ro-bind",\n        "/",' not in source
    assert "sandbox-control-evidence.json" in source
    assert "MAXIMUM_TOTAL_BYTES" in supervisor
    launcher = _load_script(_LAUNCHER, "mrl0808_launcher_prefix_test")
    prefix, _ = launcher.sandbox_prefix(
        bwrap=Path("/usr/bin/bwrap"),
        repository=Path("/repo"),
        inputs=Path("/inputs"),
        weights=Path("/weights"),
        nvidia_nodes=(Path("/dev/nvidia0"),),
    )
    root_remount = [
        index
        for index in range(len(prefix) - 1)
        if prefix[index : index + 2] == ["--remount-ro", "/"]
    ]
    assert len(root_remount) == 1
    assert root_remount[0] > prefix.index("/mesc-run/output")


def test_qualifier_ast_normalization_allows_only_attestation_trust_registry_change() -> None:
    qualifier = _load_script(_QUALIFIER, "mrl0808_qualifier_test")
    original = (_ROOT / "src/medscale/mesc/_mrl_0808_sandbox_v1.py").read_bytes()
    trusted = original.replace(
        b"TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256: frozenset[str] = frozenset()",
        b'TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256: frozenset[str] = frozenset({"'
        + b"a" * 64
        + b'"})',
    )
    assert qualifier.normalize_trust_ast(original) == qualifier.normalize_trust_ast(trusted)
    drift = trusted.replace(b'"MRL-0808"', b'"MRL-9999"', 1)
    assert qualifier.normalize_trust_ast(original) != qualifier.normalize_trust_ast(drift)


def _git(repo: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _commit_all(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def test_qualifier_source_binding_accepts_trust_only_change_and_rejects_semantic_drift(
    tmp_path: Path,
) -> None:
    qualifier = _load_script(_QUALIFIER, "mrl0808_qualifier_lineage_test")
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "mrl0808@example.invalid")
    _git(repo, "config", "user.name", "MRL0808 Test")
    module = repo / "src/medscale/mesc/_mrl_0808_sandbox_v1.py"
    test = repo / "tests/test_mesc_mrl_0808_sandbox_v1.py"
    module.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    module.write_text(
        "from __future__ import annotations\n"
        "TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256: frozenset[str] = frozenset()\n"
        "VALUE = 1\n",
        encoding="utf-8",
    )
    test.write_text("VALUE = 1\n", encoding="utf-8")
    source = _commit_all(repo, "producer source")
    source_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    module.write_text(
        "from __future__ import annotations\n"
        'TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256: frozenset[str] = frozenset({"'
        + "a"
        * 64
        + '"})\n'
        "VALUE = 1\n",
        encoding="utf-8",
    )
    test.write_text("VALUE = 2\n", encoding="utf-8")
    trust_head = _commit_all(repo, "trust admission")
    qualifier.source_binding(repo, source, trust_head, source_tree)
    module.write_text(
        module.read_text(encoding="utf-8").replace("VALUE = 1", "VALUE = 99"), encoding="utf-8"
    )
    drift_head = _commit_all(repo, "semantic drift")
    with pytest.raises(qualifier.EntrypointError, match="semantics drifted"):
        qualifier.source_binding(repo, source, drift_head, source_tree)
