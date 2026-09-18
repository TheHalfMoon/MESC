"""MRL-0809 machine-state prerequisite-gate adversarial coverage."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    generate_machine_state,
)

_ROOT = Path(__file__).resolve().parents[1]
_TASKS = Path("specs/mesc-research-loop-v1/tasks.md")
_MANIFEST = Path("specs/mesc-experiment-0/mrl-0809-static-prerequisites-v1.json")
_TRUST = Path("specs/mesc-experiment-0/mrl-0809-runtime-feasibility-trust-v1.json")
_SLOT = Path("specs/mesc-experiment-0/mrl-0809-runtime-feasibility-slot-v1.json")
_QWEN_SHA = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
_GEMMA_SHA = "842da3794eaa0b77d5f08bae87a17459d91ff475"
_QWEN_CONFIG_SHA = "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab"
_QWEN_PROCESSOR_SHA = "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
_QWEN_TOKENIZER_SHA = "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27"
_GEMMA_CONFIG_SHA = "e967dd38bc5cfd38bd09a995a7bf4a754075df2b46aba68f7fbb5a791e6d8dd1"
_GEMMA_PROCESSOR_SHA = "32bdf45d2ad4cc29a0822ddd157a182de76644f0419a6228d151495256e9813c"
_GEMMA_TOKENIZER_SHA = "9f4fec4b1dc6ecddf8f4a92e9caea5971c0e67d81309f3f9066a2bee8c362633"
_MRL0804_EVIDENCE = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
_MRL0804_RUNTIME = "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
_MRL0808_EVIDENCE = "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ("git", *args),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _clone(tmp_path: Path) -> Path:
    destination = tmp_path / "repo"
    subprocess.run(
        ("git", "clone", "--quiet", "--no-hardlinks", str(_ROOT), str(destination)),
        check=True,
        capture_output=True,
        text=True,
    )
    source_head = _git(_ROOT, "rev-parse", "HEAD")
    _git(destination, "checkout", "--detach", source_head)
    _git(destination, "config", "user.name", "MRL-0809 test")
    _git(destination, "config", "user.email", "mrl0809-test@example.invalid")
    _git(destination, "update-ref", "refs/remotes/origin/main", source_head)
    return destination


def _commit(root: Path, message: str, *paths: Path) -> str:
    _git(root, "add", *(str(path) for path in paths))
    _git(root, "commit", "-m", message)
    head = _git(root, "rev-parse", "HEAD")
    _git(root, "update-ref", "refs/remotes/origin/main", head)
    return head


def _task_state(root: Path, tmp_path: Path) -> str:
    output = tmp_path / "machine-state"
    generate_machine_state(root, output)
    payload = json.loads((output / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    tasks = payload["tasks"]
    assert isinstance(tasks, list)
    indexed = {row["task_id"]: row for row in tasks}
    state = indexed["MRL-0809"]["state"]
    assert isinstance(state, str)
    return state


def _receipt(
    *, producer_sha: str, producer_tree: str, manifest_sha: str, lock_sha: str
) -> dict[str, object]:
    generation_evidence = {
        "decoded_text_sha256": "d" * 64,
        "generated_token_ids": [11, 12],
        "synthetic_prompt_sha256": (
            "19db6d407fdb52d48b9894900e3f0afe9e81b4a12e96669ef8a863419ba4d60d"
        ),
    }
    common = {
        "generation_evidence": generation_evidence,
        "load_completed": True,
        "peak_cpu_memory_bytes": 1,
        "peak_gpu_memory_bytes": 1,
        "runtime_representation": "bitsandbytes-nf4-v1",
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": hashlib.sha256(
            canonical_json_bytes(generation_evidence)
        ).hexdigest(),
        "text_only_generation": True,
        "unloaded_after_probe": True,
    }
    runtime_identity = {
        "bubblewrap_sha256": "e" * 64,
        "bubblewrap_version": "bubblewrap 0.11.0",
        "colab_release_tag": "release-fixture",
        "compute_dtype": "float16",
        "gpu_model": "Tesla T4",
        "gpu_uuid": "GPU-fixture",
        "gpu_vram_bytes": 1,
        "harness_sha256": "f" * 64,
        "kernel_release": "kernel-fixture",
        "package_versions": {
            "accelerate": "1.14.0",
            "bitsandbytes": "0.50.2",
            "huggingface-hub": "1.23.0",
            "torch": "2.13.0",
            "transformers": "5.16.1",
            "xgrammar": "0.2.7",
        },
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": "assignment:test-only",
        "provider_owner": "GOOGLE",
        "python_version": "3.11.15",
        "runtime_representation": "bitsandbytes-nf4-v1",
    }
    return {
        "candidate_substitution_performed": False,
        "candidates": [
            {
                **common,
                "architecture": "Qwen3_5ForConditionalGeneration",
                "artifact_identity_sha256": (
                    "47fa40e84d8f5d5b3be87e40e2abe45ed8c6141f03c4c29b51dd2fbeffd4d227"
                ),
                "config_sha256": _QWEN_CONFIG_SHA,
                "model_id": "Qwen/Qwen3.8-27B",
                "processor_config_sha256": _QWEN_PROCESSOR_SHA,
                "stage_receipt_sha256": "1" * 64,
                "revision": _QWEN_SHA,
                "text_vocab_size": 248320,
                "tokenizer_config_sha256": _QWEN_TOKENIZER_SHA,
                "weights_sha256": (
                    "27c470ae6cfe721b205e468b9449fe86cfbf8fd7777772b7011f419887e345c3"
                ),
            },
            {
                **common,
                "architecture": "Gemma4ForConditionalGeneration",
                "artifact_identity_sha256": (
                    "85b8e3fedd5423bdf1c01c9d451c8702ace1e42c447f1608e94c855e17d052f9"
                ),
                "config_sha256": _GEMMA_CONFIG_SHA,
                "model_id": "google/gemma-4-31B-it",
                "processor_config_sha256": _GEMMA_PROCESSOR_SHA,
                "stage_receipt_sha256": "2" * 64,
                "revision": _GEMMA_SHA,
                "text_vocab_size": 262144,
                "tokenizer_config_sha256": _GEMMA_TOKENIZER_SHA,
                "weights_sha256": (
                    "bca2cd08fe0ba249c668a6ce576612c26c49f38b15b63c1774138dd6fc31d537"
                ),
            },
        ],
        "capacity_fallback_performed": False,
        "cleanup_completed": True,
        "compute_dtype": "float16",
        "dependency_lock_sha256": lock_sha,
        "disposition": "PASS",
        "gpu_model": "Tesla T4",
        "gpu_vram_bytes": 1,
        "local_files_only_during_isolated_execution": True,
        "monetary_cost_microunits": 0,
        "mrl_0804_evidence_sha256": _MRL0804_EVIDENCE,
        "mrl_0804_runtime_identity_sha256": _MRL0804_RUNTIME,
        "mrl_0808_evidence_sha256": _MRL0808_EVIDENCE,
        "mrl_0801_authorization_sha256": (
            "af69087c6968c3bddb28556002a2a89fcf18932506a55d1eb7d6ff318e21b9d7"
        ),
        "network_access_during_isolated_generation": False,
        "network_access_during_isolated_load": False,
        "optimizer_present": False,
        "persistent_weight_writeback": False,
        "processor_policy": "AUTO_PROCESSOR_EXACT_REVISION",
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": "assignment:test-only",
        "provider_owner": "GOOGLE",
        "repository_sha": producer_sha,
        "repository_tree": producer_tree,
        "runtime_identity": runtime_identity,
        "runtime_identity_sha256": hashlib.sha256(
            canonical_json_bytes(runtime_identity)
        ).hexdigest(),
        "sandbox_policy_sha256": "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316",
        "schema_version": "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V1",
        "static_prerequisite_manifest_sha256": manifest_sha,
        "training_performed": False,
        "trust_remote_code": False,
        "weight_mutation_performed": False,
    }


def test_producer_absent_slot_holds_mrl0809_planned(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    assert _task_state(repo, tmp_path) == "PLANNED"


def test_manual_checkbox_cannot_bypass_absent_prerequisite_gate(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    path = repo / _TASKS
    text = path.read_text(encoding="utf-8")
    old = "- [ ] **MRL-0809 — Exact-head preflight qualification**"
    assert old in text
    path.write_text(text.replace(old, old.replace("[ ]", "[x]"), 1), encoding="utf-8")
    _commit(repo, "test: forge MRL-0809 checkbox", _TASKS)
    assert _task_state(repo, tmp_path) == "PLANNED"


def test_manifest_bound_source_drift_fails_closed(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    path = repo / "src/medscale/backends/common.py"
    path.write_bytes(path.read_bytes() + b"\n")
    _commit(repo, "test: drift manifest-bound source", Path("src/medscale/backends/common.py"))
    with pytest.raises(
        MachineStateGenerationError, match="MRL-0809 prerequisite gate failed closed"
    ):
        _task_state(repo, tmp_path)


def test_forged_present_slot_and_trust_fail_closed(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    receipt = {"forged": True}
    receipt_bytes = canonical_json_bytes(receipt)
    trust = {
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1",
        "trusted_receipt_sha256": [hashlib.sha256(receipt_bytes).hexdigest()],
    }
    slot = {
        "receipt": receipt,
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V1",
        "state": "PRESENT",
        "task_id": "MRL-0809",
    }
    (repo / _TRUST).write_bytes(canonical_json_bytes(trust))
    (repo / _SLOT).write_bytes(canonical_json_bytes(slot))
    _commit(repo, "test: forge MRL-0809 runtime evidence", _TRUST, _SLOT)
    with pytest.raises(
        MachineStateGenerationError, match="MRL-0809 prerequisite gate failed closed"
    ):
        _task_state(repo, tmp_path)


def test_separate_valid_trusted_pass_makes_unchecked_mrl0809_eligible(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    producer_sha = _git(repo, "rev-parse", "HEAD")
    producer_tree = _git(repo, "rev-parse", "HEAD^{tree}")
    manifest_bytes = (repo / _MANIFEST).read_bytes()
    manifest = json.loads(manifest_bytes)
    lock_sha = manifest["dependency_lock_sha256"]
    assert isinstance(lock_sha, str)
    receipt = _receipt(
        producer_sha=producer_sha,
        producer_tree=producer_tree,
        manifest_sha=hashlib.sha256(manifest_bytes).hexdigest(),
        lock_sha=lock_sha,
    )
    receipt_bytes = canonical_json_bytes(receipt)
    trust = {
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1",
        "trusted_receipt_sha256": [hashlib.sha256(receipt_bytes).hexdigest()],
    }
    slot = {
        "receipt": receipt,
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V1",
        "state": "PRESENT",
        "task_id": "MRL-0809",
    }
    (repo / _TRUST).write_bytes(canonical_json_bytes(trust))
    (repo / _SLOT).write_bytes(canonical_json_bytes(slot))
    _commit(repo, "test: admit MRL-0809 runtime feasibility", _TRUST, _SLOT)
    assert _task_state(repo, tmp_path) == "ELIGIBLE"
