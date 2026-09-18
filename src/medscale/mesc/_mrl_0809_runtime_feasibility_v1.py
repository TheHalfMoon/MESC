"""Canonical MRL-0809 runtime model-load feasibility receipt validation.

The validator consumes already-supplied canonical evidence bytes. It performs no
network access, provider scheduling, model/tokenizer loading, inference,
training, quantization, or weight mutation.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes

_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_EXPECTED_0804_EVIDENCE: Final = "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
_EXPECTED_0804_RUNTIME_IDENTITY: Final = (
    "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
)
_EXPECTED_0808_EVIDENCE: Final = "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"
_EXPECTED_MRL0801_AUTH: Final = "af69087c6968c3bddb28556002a2a89fcf18932506a55d1eb7d6ff318e21b9d7"
_EXPECTED_GPU_MODEL: Final = "Tesla T4"
_EXPECTED_RUNTIME_REPRESENTATION: Final = "bitsandbytes-nf4-v1"
_EXPECTED_SYNTHETIC_PROMPT_SHA256: Final = (
    "19db6d407fdb52d48b9894900e3f0afe9e81b4a12e96669ef8a863419ba4d60d"
)
_MAX_NEW_TOKENS: Final = 12
_EXPECTED_PACKAGES: Final[dict[str, str]] = {
    "accelerate": "1.14.0",
    "bitsandbytes": "0.50.2",
    "huggingface-hub": "1.23.0",
    "torch": "2.13.0",
    "transformers": "5.16.1",
    "xgrammar": "0.2.7",
}
_EXPECTED_0808_SANDBOX_POLICY: Final = (
    "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"
)
_EXPECTED_CANDIDATES: Final[dict[str, dict[str, object]]] = {
    "Qwen/Qwen3.8-27B": {
        "architecture": "Qwen3_5ForConditionalGeneration",
        "artifact_identity_sha256": (
            "47fa40e84d8f5d5b3be87e40e2abe45ed8c6141f03c4c29b51dd2fbeffd4d227"
        ),
        "config_sha256": "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab",
        "processor_config_sha256": (
            "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
        ),
        "revision": "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
        "text_vocab_size": 248320,
        "tokenizer_config_sha256": (
            "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27"
        ),
        "weights_sha256": "27c470ae6cfe721b205e468b9449fe86cfbf8fd7777772b7011f419887e345c3",
    },
    "google/gemma-4-31B-it": {
        "architecture": "Gemma4ForConditionalGeneration",
        "artifact_identity_sha256": (
            "85b8e3fedd5423bdf1c01c9d451c8702ace1e42c447f1608e94c855e17d052f9"
        ),
        "config_sha256": "e967dd38bc5cfd38bd09a995a7bf4a754075df2b46aba68f7fbb5a791e6d8dd1",
        "processor_config_sha256": (
            "32bdf45d2ad4cc29a0822ddd157a182de76644f0419a6228d151495256e9813c"
        ),
        "revision": "842da3794eaa0b77d5f08bae87a17459d91ff475",
        "text_vocab_size": 262144,
        "tokenizer_config_sha256": (
            "9f4fec4b1dc6ecddf8f4a92e9caea5971c0e67d81309f3f9066a2bee8c362633"
        ),
        "weights_sha256": "bca2cd08fe0ba249c668a6ce576612c26c49f38b15b63c1774138dd6fc31d537",
    },
}
_TOP_LEVEL_KEYS: Final = frozenset(
    {
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
        "mrl_0801_authorization_sha256",
        "network_access_during_isolated_generation",
        "network_access_during_isolated_load",
        "optimizer_present",
        "persistent_weight_writeback",
        "processor_policy",
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
        "training_performed",
        "trust_remote_code",
        "weight_mutation_performed",
    }
)
_CANDIDATE_KEYS: Final = frozenset(
    {
        "architecture",
        "artifact_identity_sha256",
        "config_sha256",
        "generation_evidence",
        "load_completed",
        "model_id",
        "peak_cpu_memory_bytes",
        "peak_gpu_memory_bytes",
        "processor_config_sha256",
        "stage_receipt_sha256",
        "revision",
        "runtime_representation",
        "synthetic_generation_completed",
        "synthetic_generation_sha256",
        "text_only_generation",
        "text_vocab_size",
        "tokenizer_config_sha256",
        "unloaded_after_probe",
        "weights_sha256",
    }
)
_GENERATION_EVIDENCE_KEYS: Final = frozenset(
    {"decoded_text_sha256", "generated_token_ids", "synthetic_prompt_sha256"}
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


class MRL0809RuntimeFeasibilityError(ValueError):
    """Fail-closed error for runtime-feasibility evidence validation."""


@dataclass(frozen=True, slots=True)
class RuntimeFeasibilityReceipt:
    """Validated canonical PASS receipt for both frozen RQ1 candidates."""

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


def _reject_constant(value: str) -> Never:
    raise MRL0809RuntimeFeasibilityError(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0809RuntimeFeasibilityError(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _canonical_document(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0809RuntimeFeasibilityError("runtime-feasibility receipt must be non-empty bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(parsed) is not dict:
            raise MRL0809RuntimeFeasibilityError("runtime-feasibility receipt must be an object")
        document = cast(dict[str, object], parsed)
        canonical = canonical_json_bytes(document)
    except MRL0809RuntimeFeasibilityError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809RuntimeFeasibilityError("runtime-feasibility receipt is invalid JSON") from exc
    if canonical != raw:
        raise MRL0809RuntimeFeasibilityError("runtime-feasibility receipt is not canonical JSON")
    return document


def _text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value or value != value.strip() or "\x00" in value:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be canonical non-empty text")
    return value


def _sha256(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name)
    if _SHA256.fullmatch(text) is None:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be 64 lowercase hex")
    return text


def _git_sha(value: object, *, field_name: str) -> str:
    text = _text(value, field_name=field_name)
    if _GIT_SHA.fullmatch(text) is None:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be 40 lowercase hex")
    return text


def _require_true(value: object, *, field_name: str) -> None:
    if value is not True:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be exact JSON true")


def _require_false(value: object, *, field_name: str) -> None:
    if value is not False:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be exact JSON false")


def _positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0809RuntimeFeasibilityError(f"{field_name} must be a positive integer")
    return value


def _validate_generation_evidence(
    value: object,
    *,
    index: int,
    expected_sha256: str,
) -> None:
    if type(value) is not dict:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}].generation_evidence must be an object"
        )
    evidence = cast(dict[str, object], value)
    if set(evidence) != _GENERATION_EVIDENCE_KEYS:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}].generation_evidence key set is invalid"
        )
    _sha256(
        evidence["decoded_text_sha256"],
        field_name=f"candidates[{index}].generation_evidence.decoded_text_sha256",
    )
    prompt_sha = _sha256(
        evidence["synthetic_prompt_sha256"],
        field_name=f"candidates[{index}].generation_evidence.synthetic_prompt_sha256",
    )
    if prompt_sha != _EXPECTED_SYNTHETIC_PROMPT_SHA256:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}] synthetic prompt identity drifted"
        )
    token_ids = evidence["generated_token_ids"]
    if type(token_ids) is not list or not token_ids or len(token_ids) > _MAX_NEW_TOKENS:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}] generated token evidence is invalid"
        )
    if any(type(token) is not int or token < 0 for token in cast(list[object], token_ids)):
        raise MRL0809RuntimeFeasibilityError(f"candidates[{index}] generated token ids are invalid")
    actual_sha = hashlib.sha256(canonical_json_bytes(evidence)).hexdigest()
    if actual_sha != expected_sha256:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}] synthetic generation evidence digest drifted"
        )


def _validate_candidate(value: object, *, index: int) -> tuple[str, str]:
    if type(value) is not dict:
        raise MRL0809RuntimeFeasibilityError(f"candidates[{index}] must be an object")
    candidate = cast(dict[str, object], value)
    if set(candidate) != _CANDIDATE_KEYS:
        raise MRL0809RuntimeFeasibilityError(f"candidates[{index}] key set is invalid")
    model_id = _text(candidate["model_id"], field_name=f"candidates[{index}].model_id")
    expected = _EXPECTED_CANDIDATES.get(model_id)
    if expected is None:
        raise MRL0809RuntimeFeasibilityError("candidate is outside the frozen RQ1 roster")
    for field_name in (
        "architecture",
        "artifact_identity_sha256",
        "config_sha256",
        "processor_config_sha256",
        "revision",
        "text_vocab_size",
        "tokenizer_config_sha256",
        "weights_sha256",
    ):
        if candidate[field_name] != expected[field_name]:
            raise MRL0809RuntimeFeasibilityError(
                f"candidates[{index}].{field_name} drifted from frozen identity"
            )
    _git_sha(candidate["revision"], field_name=f"candidates[{index}].revision")
    for field_name in (
        "artifact_identity_sha256",
        "config_sha256",
        "processor_config_sha256",
        "stage_receipt_sha256",
        "tokenizer_config_sha256",
        "weights_sha256",
    ):
        _sha256(candidate[field_name], field_name=f"candidates[{index}].{field_name}")
    _positive_int(
        candidate["peak_cpu_memory_bytes"], field_name=f"candidates[{index}].peak_cpu_memory_bytes"
    )
    _positive_int(
        candidate["peak_gpu_memory_bytes"], field_name=f"candidates[{index}].peak_gpu_memory_bytes"
    )
    representation = _text(
        candidate["runtime_representation"],
        field_name=f"candidates[{index}].runtime_representation",
    )
    if representation != _EXPECTED_RUNTIME_REPRESENTATION:
        raise MRL0809RuntimeFeasibilityError(
            f"candidates[{index}].runtime_representation drifted from frozen policy"
        )
    generation_sha = _sha256(
        candidate["synthetic_generation_sha256"],
        field_name=f"candidates[{index}].synthetic_generation_sha256",
    )
    _validate_generation_evidence(
        candidate["generation_evidence"],
        index=index,
        expected_sha256=generation_sha,
    )
    for field_name in (
        "load_completed",
        "synthetic_generation_completed",
        "text_only_generation",
        "unloaded_after_probe",
    ):
        _require_true(candidate[field_name], field_name=f"candidates[{index}].{field_name}")
    return model_id, representation


def _validate_runtime_identity(
    value: object,
    *,
    expected_sha256: str,
    provider_execution_id: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0809RuntimeFeasibilityError("runtime_identity must be an object")
    identity = cast(dict[str, object], value)
    if set(identity) != _RUNTIME_IDENTITY_KEYS:
        raise MRL0809RuntimeFeasibilityError("runtime_identity key set is invalid")
    if hashlib.sha256(canonical_json_bytes(identity)).hexdigest() != expected_sha256:
        raise MRL0809RuntimeFeasibilityError("runtime_identity digest mismatch")
    if identity["provider"] != "GOOGLE_COLAB" or identity["provider_owner"] != "GOOGLE":
        raise MRL0809RuntimeFeasibilityError("runtime_identity provider drifted")
    if identity["provider_execution_id"] != provider_execution_id:
        raise MRL0809RuntimeFeasibilityError("runtime_identity provider execution id drifted")
    if identity["gpu_model"] != _EXPECTED_GPU_MODEL:
        raise MRL0809RuntimeFeasibilityError("runtime_identity GPU model drifted")
    _text(identity["gpu_uuid"], field_name="runtime_identity.gpu_uuid")
    _positive_int(identity["gpu_vram_bytes"], field_name="runtime_identity.gpu_vram_bytes")
    for field_name in (
        "bubblewrap_version",
        "colab_release_tag",
        "kernel_release",
    ):
        _text(identity[field_name], field_name=f"runtime_identity.{field_name}")
    for field_name in ("bubblewrap_sha256", "harness_sha256"):
        _sha256(identity[field_name], field_name=f"runtime_identity.{field_name}")
    if identity["compute_dtype"] != "float16":
        raise MRL0809RuntimeFeasibilityError("runtime_identity compute dtype drifted")
    if identity["runtime_representation"] != _EXPECTED_RUNTIME_REPRESENTATION:
        raise MRL0809RuntimeFeasibilityError("runtime_identity representation drifted")
    python_version = _text(identity["python_version"], field_name="runtime_identity.python_version")
    if not python_version.startswith("3.11."):
        raise MRL0809RuntimeFeasibilityError("runtime_identity Python must be CPython 3.11.x")
    packages = identity["package_versions"]
    if type(packages) is not dict or packages != _EXPECTED_PACKAGES:
        raise MRL0809RuntimeFeasibilityError("runtime_identity package versions drifted")
    return identity


def validate_runtime_feasibility_receipt(
    raw: bytes,
    *,
    expected_static_prerequisite_manifest_sha256: str,
    expected_dependency_lock_sha256: str,
    expected_repository_sha: str | None = None,
    expected_repository_tree: str | None = None,
) -> RuntimeFeasibilityReceipt:
    """Validate one exact PASS receipt without executing either scientific model."""
    expected_manifest = _sha256(
        expected_static_prerequisite_manifest_sha256,
        field_name="expected_static_prerequisite_manifest_sha256",
    )
    expected_lock = _sha256(
        expected_dependency_lock_sha256, field_name="expected_dependency_lock_sha256"
    )
    document = _canonical_document(raw)
    if set(document) != _TOP_LEVEL_KEYS:
        raise MRL0809RuntimeFeasibilityError("runtime-feasibility top-level key set is invalid")
    if document["schema_version"] != _SCHEMA or document["disposition"] != "PASS":
        raise MRL0809RuntimeFeasibilityError("runtime-feasibility schema/disposition is invalid")
    manifest_sha = _sha256(
        document["static_prerequisite_manifest_sha256"],
        field_name="static_prerequisite_manifest_sha256",
    )
    dependency_lock_sha = _sha256(
        document["dependency_lock_sha256"], field_name="dependency_lock_sha256"
    )
    if manifest_sha != expected_manifest or dependency_lock_sha != expected_lock:
        raise MRL0809RuntimeFeasibilityError("static manifest or dependency lock identity drifted")
    repository_sha = _git_sha(document["repository_sha"], field_name="repository_sha")
    repository_tree = _git_sha(document["repository_tree"], field_name="repository_tree")
    if expected_repository_sha is not None and repository_sha != _git_sha(
        expected_repository_sha, field_name="expected_repository_sha"
    ):
        raise MRL0809RuntimeFeasibilityError(
            "repository SHA does not match expected producer lineage"
        )
    if expected_repository_tree is not None and repository_tree != _git_sha(
        expected_repository_tree, field_name="expected_repository_tree"
    ):
        raise MRL0809RuntimeFeasibilityError(
            "repository tree does not match expected producer lineage"
        )
    expected_fixed = {
        "mrl_0804_evidence_sha256": _EXPECTED_0804_EVIDENCE,
        "mrl_0804_runtime_identity_sha256": _EXPECTED_0804_RUNTIME_IDENTITY,
        "mrl_0808_evidence_sha256": _EXPECTED_0808_EVIDENCE,
        "sandbox_policy_sha256": _EXPECTED_0808_SANDBOX_POLICY,
    }
    for field_name, expected in expected_fixed.items():
        if _sha256(document[field_name], field_name=field_name) != expected:
            raise MRL0809RuntimeFeasibilityError(f"{field_name} identity drifted")
    if (
        _sha256(
            document["mrl_0801_authorization_sha256"], field_name="mrl_0801_authorization_sha256"
        )
        != _EXPECTED_MRL0801_AUTH
    ):
        raise MRL0809RuntimeFeasibilityError("MRL-0801 authorization identity drifted")
    if document["provider"] != "GOOGLE_COLAB" or document["provider_owner"] != "GOOGLE":
        raise MRL0809RuntimeFeasibilityError(
            "runtime provider is outside the qualified hosted class"
        )
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
    if document["gpu_model"] != _EXPECTED_GPU_MODEL:
        raise MRL0809RuntimeFeasibilityError("T4 feasibility GPU must be exactly Tesla T4")
    gpu_vram_bytes = _positive_int(document["gpu_vram_bytes"], field_name="gpu_vram_bytes")
    if (
        runtime_identity["gpu_model"] != document["gpu_model"]
        or runtime_identity["gpu_vram_bytes"] != gpu_vram_bytes
    ):
        raise MRL0809RuntimeFeasibilityError(
            "top-level GPU identity disagrees with runtime identity"
        )
    if document["compute_dtype"] != "float16":
        raise MRL0809RuntimeFeasibilityError("T4 feasibility compute_dtype must be exactly float16")
    if document["processor_policy"] != "AUTO_PROCESSOR_EXACT_REVISION":
        raise MRL0809RuntimeFeasibilityError("processor policy drifted")
    if (
        type(document["monetary_cost_microunits"]) is not int
        or document["monetary_cost_microunits"] != 0
    ):
        raise MRL0809RuntimeFeasibilityError("runtime feasibility must prove zero monetary cost")
    for field_name in (
        "candidate_substitution_performed",
        "capacity_fallback_performed",
        "network_access_during_isolated_generation",
        "network_access_during_isolated_load",
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
    if type(raw_candidates) is not list or len(raw_candidates) != len(_EXPECTED_CANDIDATES):
        raise MRL0809RuntimeFeasibilityError("receipt must contain exactly both frozen candidates")
    candidate_rows = [
        _validate_candidate(item, index=index)
        for index, item in enumerate(cast(list[object], raw_candidates))
    ]
    model_ids = tuple(model_id for model_id, _representation in candidate_rows)
    if model_ids != tuple(sorted(_EXPECTED_CANDIDATES)):
        raise MRL0809RuntimeFeasibilityError(
            "candidates must be exact, unique, and sorted by model_id"
        )
    representations = {representation for _model_id, representation in candidate_rows}
    if len(representations) != 1:
        raise MRL0809RuntimeFeasibilityError(
            "both candidates must use one frozen representation policy"
        )
    (representation,) = tuple(representations)
    if runtime_identity["runtime_representation"] != representation:
        raise MRL0809RuntimeFeasibilityError(
            "candidate representation disagrees with runtime identity"
        )
    return RuntimeFeasibilityReceipt(
        canonical_bytes=raw,
        receipt_sha256=hashlib.sha256(raw).hexdigest(),
        static_prerequisite_manifest_sha256=manifest_sha,
        dependency_lock_sha256=dependency_lock_sha,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        runtime_identity_sha256=runtime_identity_sha,
        runtime_identity=runtime_identity,
        provider_execution_id=provider_execution_id,
        runtime_representation=representation,
    )


__all__ = [
    "MRL0809RuntimeFeasibilityError",
    "RuntimeFeasibilityReceipt",
    "validate_runtime_feasibility_receipt",
]
