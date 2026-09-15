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
    _AUTH: "967820d67e2791d84f73eee4f1016929b154ede783dd744fbc0fe0880cb447ec",
    _POLICIES["network"]: "4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f",
    _POLICIES["mutation"]: "238ef158fe54e47cc6115502bec60763c7149f74130ea35e57a84e70da2f02c8",
    _POLICIES["output"]: "7d890a8608485c58391bc1c422590b0aa1d17a35b63f3ed1f0decba5f18b726e",
    _POLICIES["stop"]: "607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194",
    _POLICIES["sandbox"]: "b156b8c6813880f7062b9f7ce6dcf053f1fb761d6ad0ba562aa753403b13d0bd",
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
        "gpu_observation": "Tesla T4, GPU-test, 15360",
        "kernel_release": "6.1.0-test",
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": _PROVIDER_ID,
        "provider_flavor": "DYNAMIC_ASSIGNED",
        "provider_owner": "GOOGLE",
        "python_version": "3.11.15",
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "schema_version": "MESC-MRL-0808-RUNTIME-CONTEXT-V1",
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
    cleanup = {
        "challenge": challenge,
        "forbidden_repository_write_absent": True,
        "normal_probe_exit_code": 0,
        "observation_sha256": observation_sha,
        "output_empty_after_cleanup": True,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_context_sha256": context_sha,
        "sandbox_policy_sha256": _EXPECTED_SHA[_POLICIES["sandbox"]],
        "schema_version": "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1",
        "scratch_empty_after_cleanup": True,
        "state": "COMPLETED",
        "violation_probe_stopped": True,
    }
    cleanup_raw = _canonical(cleanup)
    cleanup_sha = _sha(cleanup_raw)
    challenge_receipt = {
        "challenge": challenge,
        "cleanup_receipt_sha256": cleanup_sha,
        "observation_sha256": observation_sha,
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
    for name in ("runtime_context", "observation", "cleanup"):
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
    for name in ("runtime_context", "observation", "cleanup"):
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
        "--cleanup-receipt",
        str(tmp_path / "second-cleanup.json"),
        "--provider-execution-id",
        _PROVIDER_ID,
        "--ledger-dir",
        str(ledger2),
    )
    assert denied.returncode != 0
    assert "cancelled" in denied.stderr


def test_attestation_renderer_requires_consumed_challenge_and_exact_custody(tmp_path: Path) -> None:
    bundle = _synthetic_bundle()
    paths: dict[str, Path] = {}
    for name in ("runtime_context", "observation", "cleanup", "challenge"):
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
    assert rendered["runtime_context_sha256"] == _sha(bundle["runtime_context"])


def test_probe_and_launcher_contain_no_model_loading_training_or_paid_compute_primitives() -> None:
    for path in (_PROBE, _LAUNCHER, _CHALLENGE, _ATTEST, _QUALIFIER):
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


def test_launcher_declares_real_namespace_mount_environment_and_stop_controls() -> None:
    source = _LAUNCHER.read_text(encoding="utf-8")
    for token in (
        '"--unshare-all"',
        '"--clearenv"',
        '"--die-with-parent"',
        '"--new-session"',
        '"--ro-bind"',
        '"/mesc-run/repository"',
        '"/mesc-run/model-weights"',
        '"/mesc-run/inputs"',
        '"/mesc-run/scratch"',
        '"/mesc-run/output"',
        ".mrl0808-forbidden-write",
        "sandbox left unexpected scratch/output residue",
    ):
        assert token in source
    assert '"--share-net"' not in source
    assert '"--bind",\n            str(root)' not in source


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
