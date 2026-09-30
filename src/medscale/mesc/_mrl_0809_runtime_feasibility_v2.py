"""Canonical MRL-0809 successor (v2) runtime model-load feasibility receipt validation.

The v2 contract is the Founder-authorized smaller-roster successor of the v1 contract in
``_mrl_0809_runtime_feasibility_v1``, which stays byte-identical and historically
INFEASIBLE_ON_FROZEN_STANDARD_T4_CONTRACT. v2 keeps the v1 runtime class, sandbox,
dependency lock and ``bitsandbytes-nf4-v1`` representation. It changes only what the new
roster forces:
- the frozen candidates;
- a per-candidate processor policy;
- chat-template prompt construction with a frozen prompt-token digest per candidate;
- explicit finite-logit evidence;
- a peak-GPU headroom ceiling;
- bindings to the v2 roster, the successor authorization and the v1 infeasibility record.

The validator consumes already-supplied canonical evidence bytes. It performs no network
access, provider scheduling, model/tokenizer loading, inference, training, quantization, or
weight mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes

SCHEMA: Final = "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V2"
CANDIDATE_ROSTER_SHA256: Final = "61351863e82aa9108c6325304e26b7ea4cb92f84a9fbbb5ef761c13f0a882de2"
SUCCESSOR_AUTHORIZATION_SHA256: Final = (
    "114aebbefa64499c8855e28eca650e09c68f926cb7da9beacfa47d364091ade6"
)
V1_INFEASIBILITY_RECORD_SHA256: Final = (
    "933de39a27a37a9b62d68db3d3a388805572c720f3db136a829d22354bd13ebe"
)
RUNTIME_REPRESENTATION: Final = "bitsandbytes-nf4-v1"
PROMPT_CONSTRUCTION: Final = "CHAT_TEMPLATE_ADD_GENERATION_PROMPT"
SYNTHETIC_PROMPT_SHA256: Final = "19db6d407fdb52d48b9894900e3f0afe9e81b4a12e96669ef8a863419ba4d60d"
MAX_NEW_TOKENS: Final = 12
# Material headroom below the ~14.56 GiB usable T4: a PASS must peak at or below 12 GiB.
MAX_PEAK_GPU_MEMORY_BYTES: Final = 12 * 1024**3
GPU_MODEL: Final = "Tesla T4"
AUTO_PROCESSOR: Final = "AUTO_PROCESSOR_EXACT_REVISION"
TOKENIZER_ONLY: Final = "TOKENIZER_ONLY_TEXT_MODEL"

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_EXPECTED_0804_EVIDENCE: Final = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
_EXPECTED_0804_RUNTIME_IDENTITY: Final = (
    "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
)
_EXPECTED_0808_EVIDENCE: Final = "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"
_EXPECTED_0808_SANDBOX_POLICY: Final = (
    "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"
)
EXPECTED_PACKAGES: Final[dict[str, str]] = {
    "accelerate": "1.14.0",
    "bitsandbytes": "0.50.2",
    "huggingface-hub": "1.23.0",
    "pillow": "12.3.0",
    "torch": "2.13.0",
    "torchvision": "0.28.0",
    "transformers": "5.16.1",
    "xgrammar": "0.2.7",
}
EXPECTED_CANDIDATES: Final[dict[str, dict[str, object]]] = {
    "Qwen/Qwen3-8B": {
        "architecture": "Qwen3ForCausalLM",
        "artifact_identity_sha256": (
            "d427ce5eeab11a278a80dcbfce0bbf523baf0cf41e3ba6d6da64492feffc719d"
        ),
        "config_sha256": "f7c4eadfbbf522470667b797a3c89be2524832d2d599797248dc304fff447c30",
        "processor_config_sha256": None,
        "processor_policy": TOKENIZER_ONLY,
        "prompt_token_ids_sha256": (
            "dff106287fb0d1c188e5d1c10b9a58a824c00179af4d040150163d82f71c9f44"
        ),
        "revision": "b968826d9c46dd6066d109eabc6255188de91218",
        "text_vocab_size": 151936,
        "tokenizer_config_sha256": (
            "d5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101"
        ),
        "weights_sha256": "74ddc11aa1c5f0a1aec4758eff603adce262a8fa2d847f032092e518ddcbe14b",
    },
    "google/gemma-4-12B-it": {
        "architecture": "Gemma4UnifiedForConditionalGeneration",
        "artifact_identity_sha256": (
            "2100e96da837dcd2ad98fbfad310cbf87e964065d8dbc9b8538466bd0dab1b22"
        ),
        "config_sha256": "478c46e8d2c52d5c2d85bf67e3b3e8c90e7c9d91086cee27e3c267907e936bd9",
        "processor_config_sha256": (
            "6b938e76555b3e9946890770e1abcd442a4718f34041a58e8139dc8ad34545c9"
        ),
        "processor_policy": AUTO_PROCESSOR,
        "prompt_token_ids_sha256": (
            "0969c3e2c1147307a557c910a95cea00005eafa76587e3225d43308d2126682d"
        ),
        "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        "text_vocab_size": 262144,
        "tokenizer_config_sha256": (
            "a62f4e85a47c0c136edaaa3a4f591fd6783717299a9def47e5ad03a49f6a5eb9"
        ),
        "weights_sha256": "b2baeebd544de7d2f27b442111de54e953589395991ea20f3aeb0fdc7194ddf5",
    },
}
_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "candidate_roster_sha256",
        "candidate_substitution_performed",
        "candidates",
        "capacity_fallback_performed",
        "cleanup_completed",
        "compute_dtype",
        "dependency_lock_sha256",
        "disposition",
        "gpu_model",
        "gpu_vram_bytes",
        "local_files_only_during_isolated_execution",
        "monetary_cost_microunits",
        "mrl_0804_evidence_sha256",
        "mrl_0804_runtime_identity_sha256",
        "mrl_0808_evidence_sha256",
        "network_access_during_isolated_generation",
        "network_access_during_isolated_load",
        "offload_performed",
        "optimizer_present",
        "persistent_weight_writeback",
        "provider",
        "provider_execution_id",
        "provider_owner",
        "repository_sha",
        "repository_tree",
        "runtime_identity",
        "runtime_identity_sha256",
        "sandbox_policy_sha256",
        "schema_version",
        "static_prerequisite_manifest_sha256",
        "successor_authorization_sha256",
        "training_performed",
        "trust_remote_code",
        "v1_infeasibility_record_sha256",
        "weight_mutation_performed",
    }
)
_CANDIDATE_KEYS: Final = frozenset(
    {
        "all_modules_on_cuda_device_0",
        "architecture",
        "artifact_identity_sha256",
        "config_sha256",
        "generation_evidence",
        "load_completed",
        "model_id",
        "peak_cpu_memory_bytes",
        "peak_gpu_memory_bytes",
        "processor_config_sha256",
        "processor_loaded",
        "processor_policy",
        "revision",
        "runtime_representation",
        "stage_receipt_sha256",
        "synthetic_generation_completed",
        "synthetic_generation_sha256",
        "text_only_generation",
        "text_vocab_size",
        "tokenizer_config_sha256",
        "tokenizer_loaded",
        "unloaded_after_probe",
        "weights_sha256",
    }
)
_GENERATION_EVIDENCE_KEYS: Final = frozenset(
    {
        "all_generated_logits_finite",
        "decoded_text_sha256",
        "generated_token_ids",
        "prompt_construction",
        "prompt_token_ids_sha256",
        "synthetic_prompt_sha256",
    }
)
_RUNTIME_IDENTITY_KEYS: Final = frozenset(
    {
        "bubblewrap_sha256",
        "bubblewrap_version",
        "colab_release_tag",
        "compute_dtype",
        "gpu_model",
        "gpu_uuid",
        "gpu_vram_bytes",
        "harness_sha256",
        "kernel_release",
        "package_versions",
        "provider",
        "provider_execution_id",
        "provider_owner",
        "python_version",
        "runtime_representation",
    }
)


class MRL0809SuccessorRuntimeFeasibilityError(ValueError):
    """Fail-closed error for successor runtime-feasibility evidence validation."""


@dataclass(frozen=True, slots=True)
class SuccessorRuntimeFeasibilityReceipt:
    """Validated canonical PASS receipt for both frozen successor candidates."""

    canonical_bytes: bytes = field(repr=False)
    receipt_sha256: str
    static_prerequisite_manifest_sha256: str
    dependency_lock_sha256: str
    repository_sha: str
    repository_tree: str
    runtime_identity_sha256: str
    runtime_identity: dict[str, object] = field(repr=False)
    provider_execution_id: str
    runtime_representation: str


def _fail(message: str) -> Never:
    raise MRL0809SuccessorRuntimeFeasibilityError(message)


def _reject_constant(value: str) -> Never:
    _fail(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _canonical_document(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail("runtime-feasibility receipt must be non-empty bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(parsed) is not dict:
            _fail("runtime-feasibility receipt must be an object")
        document = cast(dict[str, object], parsed)
        canonical = canonical_json_bytes(document)
    except MRL0809SuccessorRuntimeFeasibilityError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809SuccessorRuntimeFeasibilityError(
            "runtime-feasibility receipt is invalid JSON"
        ) from exc
    if canonical != raw:
        _fail("runtime-feasibility receipt is not canonical JSON")
    return document


def _text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value != value.strip() or "\x00" in value:
        _fail(f"{field_name} must be canonical non-empty text")
    return value


def _sha256(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{field_name} must be 64 lowercase hex")
    return text


def _git_sha(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name)
    if _GIT_SHA.fullmatch(text) is None:
        _fail(f"{field_name} must be 40 lowercase hex")
    return text


def _require_true(value: object, *, field_name: str) -> None:
    if value is not True:
        _fail(f"{field_name} must be exact JSON true")


def _require_false(value: object, *, field_name: str) -> None:
    if value is not False:
        _fail(f"{field_name} must be exact JSON false")


def _positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        _fail(f"{field_name} must be a positive integer")
    return value


def _validate_generation_evidence(
    value: object,
    *,
    index: int,
    expected_sha256: str,
    expected_prompt_tokens_sha256: str,
) -> None:
    if type(value) is not dict:
        _fail(f"candidates[{index}].generation_evidence must be an object")
    evidence = cast(dict[str, object], value)
    if set(evidence) != _GENERATION_EVIDENCE_KEYS:
        _fail(f"candidates[{index}].generation_evidence key set is invalid")
    _sha256(
        evidence["decoded_text_sha256"],
        field_name=f"candidates[{index}].generation_evidence.decoded_text_sha256",
    )
    if evidence["synthetic_prompt_sha256"] != SYNTHETIC_PROMPT_SHA256:
        _fail(f"candidates[{index}] synthetic prompt identity drifted")
    if evidence["prompt_construction"] != PROMPT_CONSTRUCTION:
        _fail(f"candidates[{index}] prompt construction policy drifted")
    if evidence["prompt_token_ids_sha256"] != expected_prompt_tokens_sha256:
        _fail(f"candidates[{index}] prompt token identity drifted from the frozen template")
    _require_true(
        evidence["all_generated_logits_finite"],
        field_name=f"candidates[{index}].generation_evidence.all_generated_logits_finite",
    )
    token_ids = evidence["generated_token_ids"]
    if type(token_ids) is not list or not token_ids or len(token_ids) > MAX_NEW_TOKENS:
        _fail(f"candidates[{index}] generated token evidence is invalid")
    if any(type(token) is not int or token < 0 for token in cast(list[object], token_ids)):
        _fail(f"candidates[{index}] generated token ids are invalid")
    actual_sha = hashlib.sha256(canonical_json_bytes(evidence)).hexdigest()
    if actual_sha != expected_sha256:
        _fail(f"candidates[{index}] synthetic generation evidence digest drifted")


def _validate_candidate(value: object, *, index: int, gpu_vram_bytes: int) -> str:
    if type(value) is not dict:
        _fail(f"candidates[{index}] must be an object")
    candidate = cast(dict[str, object], value)
    if set(candidate) != _CANDIDATE_KEYS:
        _fail(f"candidates[{index}] key set is invalid")
    model_id = _text(candidate["model_id"], field_name=f"candidates[{index}].model_id")
    expected = EXPECTED_CANDIDATES.get(model_id)
    if expected is None:
        _fail("candidate is outside the frozen successor roster")
    for field_name in (
        "architecture",
        "artifact_identity_sha256",
        "config_sha256",
        "processor_config_sha256",
        "processor_policy",
        "revision",
        "text_vocab_size",
        "tokenizer_config_sha256",
        "weights_sha256",
    ):
        if candidate[field_name] != expected[field_name]:
            _fail(f"candidates[{index}].{field_name} drifted from frozen identity")
    _git_sha(candidate["revision"], field_name=f"candidates[{index}].revision")
    for field_name in (
        "artifact_identity_sha256",
        "config_sha256",
        "stage_receipt_sha256",
        "tokenizer_config_sha256",
        "weights_sha256",
    ):
        _sha256(candidate[field_name], field_name=f"candidates[{index}].{field_name}")
    if expected["processor_policy"] == AUTO_PROCESSOR:
        _sha256(
            candidate["processor_config_sha256"],
            field_name=f"candidates[{index}].processor_config_sha256",
        )
        _require_true(
            candidate["processor_loaded"], field_name=f"candidates[{index}].processor_loaded"
        )
    elif candidate["processor_loaded"] is not False:
        _fail(f"candidates[{index}] tokenizer-only candidate must not claim a processor load")
    _positive_int(
        candidate["peak_cpu_memory_bytes"], field_name=f"candidates[{index}].peak_cpu_memory_bytes"
    )
    peak_gpu = _positive_int(
        candidate["peak_gpu_memory_bytes"], field_name=f"candidates[{index}].peak_gpu_memory_bytes"
    )
    if peak_gpu > MAX_PEAK_GPU_MEMORY_BYTES or peak_gpu > gpu_vram_bytes:
        _fail(f"candidates[{index}] peak GPU memory exceeds the successor headroom ceiling")
    if candidate["runtime_representation"] != RUNTIME_REPRESENTATION:
        _fail(f"candidates[{index}].runtime_representation drifted from frozen policy")
    generation_sha = _sha256(
        candidate["synthetic_generation_sha256"],
        field_name=f"candidates[{index}].synthetic_generation_sha256",
    )
    _validate_generation_evidence(
        candidate["generation_evidence"],
        index=index,
        expected_sha256=generation_sha,
        expected_prompt_tokens_sha256=cast(str, expected["prompt_token_ids_sha256"]),
    )
    for field_name in (
        "all_modules_on_cuda_device_0",
        "load_completed",
        "synthetic_generation_completed",
        "text_only_generation",
        "tokenizer_loaded",
        "unloaded_after_probe",
    ):
        _require_true(candidate[field_name], field_name=f"candidates[{index}].{field_name}")
    return model_id


def _validate_runtime_identity(
    value: object,
    *,
    expected_sha256: str,
    provider_execution_id: str,
) -> dict[str, object]:
    if type(value) is not dict:
        _fail("runtime_identity must be an object")
    identity = cast(dict[str, object], value)
    if set(identity) != _RUNTIME_IDENTITY_KEYS:
        _fail("runtime_identity key set is invalid")
    if hashlib.sha256(canonical_json_bytes(identity)).hexdigest() != expected_sha256:
        _fail("runtime_identity digest mismatch")
    if identity["provider"] != "GOOGLE_COLAB" or identity["provider_owner"] != "GOOGLE":
        _fail("runtime_identity provider drifted")
    if identity["provider_execution_id"] != provider_execution_id:
        _fail("runtime_identity provider execution id drifted")
    if identity["gpu_model"] != GPU_MODEL:
        _fail("runtime_identity GPU model drifted")
    _text(identity["gpu_uuid"], field_name="runtime_identity.gpu_uuid")
    _positive_int(identity["gpu_vram_bytes"], field_name="runtime_identity.gpu_vram_bytes")
    for field_name in ("bubblewrap_version", "colab_release_tag", "kernel_release"):
        _text(identity[field_name], field_name=f"runtime_identity.{field_name}")
    for field_name in ("bubblewrap_sha256", "harness_sha256"):
        _sha256(identity[field_name], field_name=f"runtime_identity.{field_name}")
    if identity["compute_dtype"] != "float16":
        _fail("runtime_identity compute dtype drifted")
    if identity["runtime_representation"] != RUNTIME_REPRESENTATION:
        _fail("runtime_identity representation drifted")
    python_version = _text(identity["python_version"], field_name="runtime_identity.python_version")
    if not python_version.startswith("3.11."):
        _fail("runtime_identity Python must be CPython 3.11.x")
    if type(identity["package_versions"]) is not dict or identity["package_versions"] != (
        EXPECTED_PACKAGES
    ):
        _fail("runtime_identity package versions drifted")
    return identity


def validate_successor_runtime_feasibility_receipt(
    raw: bytes,
    *,
    expected_static_prerequisite_manifest_sha256: str,
    expected_dependency_lock_sha256: str,
    expected_repository_sha: str | None = None,
    expected_repository_tree: str | None = None,
) -> SuccessorRuntimeFeasibilityReceipt:
    """Validate one exact successor PASS receipt without executing either model."""
    expected_manifest = _sha256(
        expected_static_prerequisite_manifest_sha256,
        field_name="expected_static_prerequisite_manifest_sha256",
    )
    expected_lock = _sha256(
        expected_dependency_lock_sha256, field_name="expected_dependency_lock_sha256"
    )
    document = _canonical_document(raw)
    if set(document) != _TOP_LEVEL_KEYS:
        _fail("runtime-feasibility top-level key set is invalid")
    if document["schema_version"] != SCHEMA or document["disposition"] != "PASS":
        _fail("runtime-feasibility schema/disposition is invalid")
    manifest_sha = _sha256(
        document["static_prerequisite_manifest_sha256"],
        field_name="static_prerequisite_manifest_sha256",
    )
    lock_sha = _sha256(document["dependency_lock_sha256"], field_name="dependency_lock_sha256")
    if manifest_sha != expected_manifest or lock_sha != expected_lock:
        _fail("static manifest or dependency lock identity drifted")
    repository_sha = _git_sha(document["repository_sha"], field_name="repository_sha")
    repository_tree = _git_sha(document["repository_tree"], field_name="repository_tree")
    if expected_repository_sha is not None and repository_sha != _git_sha(
        expected_repository_sha, field_name="expected_repository_sha"
    ):
        _fail("repository SHA does not match expected producer lineage")
    if expected_repository_tree is not None and repository_tree != _git_sha(
        expected_repository_tree, field_name="expected_repository_tree"
    ):
        _fail("repository tree does not match expected producer lineage")
    fixed = {
        "candidate_roster_sha256": CANDIDATE_ROSTER_SHA256,
        "mrl_0804_evidence_sha256": _EXPECTED_0804_EVIDENCE,
        "mrl_0804_runtime_identity_sha256": _EXPECTED_0804_RUNTIME_IDENTITY,
        "mrl_0808_evidence_sha256": _EXPECTED_0808_EVIDENCE,
        "sandbox_policy_sha256": _EXPECTED_0808_SANDBOX_POLICY,
        "successor_authorization_sha256": SUCCESSOR_AUTHORIZATION_SHA256,
        "v1_infeasibility_record_sha256": V1_INFEASIBILITY_RECORD_SHA256,
    }
    for field_name, expected in fixed.items():
        if _sha256(document[field_name], field_name=field_name) != expected:
            _fail(f"{field_name} identity drifted")
    if document["provider"] != "GOOGLE_COLAB" or document["provider_owner"] != "GOOGLE":
        _fail("runtime provider is outside the qualified hosted class")
    provider_execution_id = _text(
        document["provider_execution_id"], field_name="provider_execution_id"
    )
    runtime_identity_sha = _sha256(
        document["runtime_identity_sha256"], field_name="runtime_identity_sha256"
    )
    runtime_identity = _validate_runtime_identity(
        document["runtime_identity"],
        expected_sha256=runtime_identity_sha,
        provider_execution_id=provider_execution_id,
    )
    if document["gpu_model"] != GPU_MODEL:
        _fail("T4 feasibility GPU must be exactly Tesla T4")
    gpu_vram_bytes = _positive_int(document["gpu_vram_bytes"], field_name="gpu_vram_bytes")
    if (
        runtime_identity["gpu_model"] != document["gpu_model"]
        or runtime_identity["gpu_vram_bytes"] != gpu_vram_bytes
    ):
        _fail("top-level GPU identity disagrees with runtime identity")
    if document["compute_dtype"] != "float16":
        _fail("T4 feasibility compute_dtype must be exactly float16")
    if (
        type(document["monetary_cost_microunits"]) is not int
        or document["monetary_cost_microunits"] != 0
    ):
        _fail("runtime feasibility must prove zero monetary cost")
    for field_name in (
        "candidate_substitution_performed",
        "capacity_fallback_performed",
        "network_access_during_isolated_generation",
        "network_access_during_isolated_load",
        "offload_performed",
        "optimizer_present",
        "persistent_weight_writeback",
        "training_performed",
        "trust_remote_code",
        "weight_mutation_performed",
    ):
        _require_false(document[field_name], field_name=field_name)
    for field_name in ("cleanup_completed", "local_files_only_during_isolated_execution"):
        _require_true(document[field_name], field_name=field_name)
    raw_candidates = document["candidates"]
    if type(raw_candidates) is not list or len(raw_candidates) != len(EXPECTED_CANDIDATES):
        _fail("receipt must contain exactly both frozen successor candidates")
    model_ids = tuple(
        _validate_candidate(item, index=index, gpu_vram_bytes=gpu_vram_bytes)
        for index, item in enumerate(cast(list[object], raw_candidates))
    )
    if model_ids != tuple(sorted(EXPECTED_CANDIDATES)):
        _fail("candidates must be exact, unique, and sorted by model_id")
    return SuccessorRuntimeFeasibilityReceipt(
        canonical_bytes=raw,
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        static_prerequisite_manifest_sha256=manifest_sha,
        dependency_lock_sha256=lock_sha,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        runtime_identity_sha256=runtime_identity_sha,
        runtime_identity=runtime_identity,
        provider_execution_id=provider_execution_id,
        runtime_representation=RUNTIME_REPRESENTATION,
    )


__all__ = [
    "AUTO_PROCESSOR",
    "CANDIDATE_ROSTER_SHA256",
    "EXPECTED_CANDIDATES",
    "EXPECTED_PACKAGES",
    "MAX_NEW_TOKENS",
    "MAX_PEAK_GPU_MEMORY_BYTES",
    "PROMPT_CONSTRUCTION",
    "RUNTIME_REPRESENTATION",
    "SCHEMA",
    "SUCCESSOR_AUTHORIZATION_SHA256",
    "SYNTHETIC_PROMPT_SHA256",
    "TOKENIZER_ONLY",
    "V1_INFEASIBILITY_RECORD_SHA256",
    "MRL0809SuccessorRuntimeFeasibilityError",
    "SuccessorRuntimeFeasibilityReceipt",
    "validate_successor_runtime_feasibility_receipt",
]
