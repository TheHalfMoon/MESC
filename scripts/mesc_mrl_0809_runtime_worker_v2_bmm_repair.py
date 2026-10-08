#!/usr/bin/env python3
"""Isolated MRL-0809 successor worker with placement and BMM portability repair."""

from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final, Never, cast

try:
    from placement_audit import (  # type: ignore[import-not-found]
        PlacementAuditError,
        audit_model_cuda0_placement,
    )
except ModuleNotFoundError:  # repository-side tests/imports, never the sandbox path
    from medscale.mesc._mrl_0809_device_placement_audit_v1 import (
        PlacementAuditError,
        audit_model_cuda0_placement,
    )

SCHEMA_WORKER: Final = "MESC-MRL-0809-CANDIDATE-WORKER-V2"
RUNTIME_REPRESENTATION: Final = "bitsandbytes-nf4-v1"
AUTO_PROCESSOR: Final = "AUTO_PROCESSOR_EXACT_REVISION"
TOKENIZER_ONLY: Final = "TOKENIZER_ONLY_TEXT_MODEL"
PROMPT_CONSTRUCTION: Final = "CHAT_TEMPLATE_ADD_GENERATION_PROMPT"
MAX_PEAK_GPU_MEMORY_BYTES: Final = 12 * 1024**3
SYNTHETIC_PROMPT: Final = "Write one short sentence about a blue triangle."
MAX_NEW_TOKENS: Final = 12

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
    },
    "google/gemma-4-12B-it": {
        "architecture": "Gemma4UnifiedForConditionalGeneration",
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
    },
}


class RuntimeWorkerError(RuntimeError):
    """Fail-closed isolated successor worker error."""


def _reject_constant(value: str) -> Never:
    raise RuntimeWorkerError(f"non-standard JSON constant prohibited: {value}")


def _normalize_canonical(value: object) -> object:
    if value is None or type(value) is bool:
        return value
    if type(value) is int:
        return value
    if type(value) is str:
        value.encode("utf-8")
        return value
    if isinstance(value, float):
        raise RuntimeWorkerError("floating-point values are prohibited in canonical JSON")
    if isinstance(value, Mapping):
        snapshot = list(value.items())
        if any(type(key) is not str for key, _ in snapshot):
            raise RuntimeWorkerError("canonical JSON object keys must be exact strings")
        return {
            cast(str, key): _normalize_canonical(item)
            for key, item in sorted(snapshot, key=lambda pair: cast(str, pair[0]))
        }
    if isinstance(value, list | tuple):
        return [_normalize_canonical(item) for item in value]
    raise RuntimeWorkerError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    normalized = _normalize_canonical(value)
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8") + b"\n"


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_digests(candidate: str, snapshot: Path) -> dict[str, str | None]:
    expected = EXPECTED_CANDIDATES[candidate]
    config = snapshot / "config.json"
    tokenizer = snapshot / "tokenizer_config.json"
    if not config.is_file() or not tokenizer.is_file():
        raise RuntimeWorkerError("required candidate metadata is missing")
    result: dict[str, str | None] = {
        "config_sha256": _sha256_file(config),
        "processor_config_sha256": None,
        "tokenizer_config_sha256": _sha256_file(tokenizer),
    }
    expected_processor = expected["processor_config_sha256"]
    if expected_processor is not None:
        processor = snapshot / "processor_config.json"
        if not processor.is_file():
            raise RuntimeWorkerError("required processor metadata is missing")
        result["processor_config_sha256"] = _sha256_file(processor)
    for field, observed in result.items():
        if observed != expected[field]:
            raise RuntimeWorkerError(f"candidate metadata drifted: {field}")
    return result


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package, expected in EXPECTED_PACKAGES.items():
        try:
            observed = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeWorkerError(f"required runtime package is missing: {package}") from exc
        if observed != expected:
            raise RuntimeWorkerError(
                f"runtime package drifted: {package} observed={observed} expected={expected}"
            )
        versions[package] = observed
    return versions


def _disable_experimental_native_bmm_override() -> None:
    """Force PyTorch 2.13 BMM back to the stable ATen implementation."""

    try:
        registry: Any = importlib.import_module("torch._native.registry")
        deregister = registry.deregister_op_overrides
        if not callable(deregister):
            raise TypeError("deregister_op_overrides is not callable")
        deregister(disable_op_symbols="bmm")
    except Exception as exc:
        raise RuntimeWorkerError(
            "failed to disable the experimental torch native bmm override"
        ) from exc


def run_worker(candidate: str, snapshot: Path) -> None:
    if candidate not in EXPECTED_CANDIDATES:
        raise RuntimeWorkerError("worker candidate is outside the frozen roster")
    if os.environ.get("HF_HUB_OFFLINE") != "1" or os.environ.get("TRANSFORMERS_OFFLINE") != "1":
        raise RuntimeWorkerError("worker offline policy is missing")
    snapshot = snapshot.resolve(strict=True)
    expected = EXPECTED_CANDIDATES[candidate]
    digests = _metadata_digests(candidate, snapshot)
    versions = _package_versions()

    try:
        resource_module: Any = importlib.import_module("resource")
        torch: Any = importlib.import_module("torch")
        transformers: Any = importlib.import_module("transformers")
        auto_processor: Any = transformers.AutoProcessor
        auto_tokenizer: Any = transformers.AutoTokenizer
        bitsandbytes_config: Any = transformers.BitsAndBytesConfig
    except Exception as exc:
        raise RuntimeWorkerError("frozen runtime packages failed to import") from exc

    _disable_experimental_native_bmm_override()

    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeWorkerError("worker requires exactly one CUDA GPU")

    architecture = cast(str, expected["architecture"])
    model_class = getattr(transformers, architecture, None)
    if model_class is None:
        raise RuntimeWorkerError(f"transformers does not expose {architecture}")

    uses_processor = expected["processor_policy"] == AUTO_PROCESSOR
    baseline_gpu = int(torch.cuda.memory_allocated())
    torch.cuda.reset_peak_memory_stats()

    tokenizer: Any = None
    processor: Any = None
    model: Any = None
    input_ids: Any = None
    output: Any = None
    generated_ids: list[int] = []
    prompt_token_ids: list[int] = []
    decoded_hash = ""
    logits_finite = False
    peak_gpu = 0
    peak_cpu = 0
    placement_audit: dict[str, Any] | None = None

    try:
        tokenizer = auto_tokenizer.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
        )
        if uses_processor:
            processor = auto_processor.from_pretrained(
                str(snapshot),
                local_files_only=True,
                trust_remote_code=False,
            )
        prompt_token_ids = [
            int(token)
            for token in tokenizer.apply_chat_template(
                [{"role": "user", "content": SYNTHETIC_PROMPT}],
                add_generation_prompt=True,
                tokenize=True,
                return_dict=False,
            )
        ]
        if _sha256(canonical_json_bytes(prompt_token_ids)) != expected["prompt_token_ids_sha256"]:
            raise RuntimeWorkerError("chat-template prompt tokens drifted from the frozen identity")

        quantization = bitsandbytes_config(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        model = model_class.from_pretrained(
            str(snapshot),
            local_files_only=True,
            trust_remote_code=False,
            quantization_config=quantization,
            device_map={"": 0},
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
        torch.cuda.synchronize()
        try:
            placement_audit = audit_model_cuda0_placement(model)
        except PlacementAuditError as exc:
            raise RuntimeWorkerError(f"placement audit failed: {exc}") from exc

        if model.__class__.__name__ != architecture:
            raise RuntimeWorkerError("loaded model architecture drifted from frozen identity")
        if model.training:
            raise RuntimeWorkerError("runtime-feasibility model must remain in eval mode")

        input_ids = torch.tensor([prompt_token_ids], device=torch.device("cuda:0"))
        with torch.inference_mode():
            output = model.generate(
                input_ids=input_ids,
                attention_mask=torch.ones_like(input_ids),
                do_sample=False,
                num_beams=1,
                max_new_tokens=MAX_NEW_TOKENS,
                output_logits=True,
                return_dict_in_generate=True,
            )
        sequence = output.sequences[0]
        generated_ids = [int(token) for token in sequence[len(prompt_token_ids) :].tolist()]
        if not generated_ids:
            raise RuntimeWorkerError("synthetic generation produced no new tokens")
        step_logits = tuple(output.logits)
        if len(step_logits) != len(generated_ids):
            raise RuntimeWorkerError("generation logits do not cover every generated token")
        logits_finite = all(bool(torch.isfinite(step).all()) for step in step_logits)
        if not logits_finite:
            raise RuntimeWorkerError("synthetic generation produced non-finite logits")
        decoded = tokenizer.decode(generated_ids, skip_special_tokens=True)
        if not decoded.strip():
            raise RuntimeWorkerError("synthetic generation decoded to empty text")
        torch.cuda.synchronize()
        decoded_hash = _sha256(decoded.encode("utf-8"))
        peak_gpu = int(torch.cuda.max_memory_allocated())
        peak_cpu = int(resource_module.getrusage(resource_module.RUSAGE_SELF).ru_maxrss) * 1024
        if peak_gpu <= 0 or peak_cpu <= 0:
            raise RuntimeWorkerError("candidate memory observations must be positive")
        if peak_gpu > MAX_PEAK_GPU_MEMORY_BYTES:
            raise RuntimeWorkerError("peak GPU memory exceeded the successor headroom ceiling")
    finally:
        del output, input_ids, model, processor, tokenizer
        gc.collect()
        torch.cuda.empty_cache()

    residual_gpu = int(torch.cuda.memory_allocated())
    unloaded = residual_gpu <= baseline_gpu + (64 * 1024 * 1024)
    if not unloaded:
        raise RuntimeWorkerError("GPU allocations did not return to the bounded cleanup envelope")
    if placement_audit is None:
        raise RuntimeWorkerError("placement audit evidence is missing")

    generation_evidence = {
        "all_generated_logits_finite": logits_finite,
        "decoded_text_sha256": decoded_hash,
        "generated_token_ids": generated_ids,
        "prompt_construction": PROMPT_CONSTRUCTION,
        "prompt_token_ids_sha256": _sha256(canonical_json_bytes(prompt_token_ids)),
        "synthetic_prompt_sha256": _sha256(SYNTHETIC_PROMPT.encode("utf-8")),
    }
    generation_sha256 = _sha256(canonical_json_bytes(generation_evidence))
    candidate_receipt = {
        "all_modules_on_cuda_device_0": placement_audit[
            "all_materialized_tensors_on_cuda_device_0"
        ],
        "architecture": architecture,
        "config_sha256": digests["config_sha256"],
        "load_completed": True,
        "model_id": candidate,
        "peak_cpu_memory_bytes": peak_cpu,
        "peak_gpu_memory_bytes": peak_gpu,
        "processor_config_sha256": digests["processor_config_sha256"],
        "processor_loaded": uses_processor,
        "processor_policy": expected["processor_policy"],
        "revision": expected["revision"],
        "runtime_representation": RUNTIME_REPRESENTATION,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": generation_sha256,
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": digests["tokenizer_config_sha256"],
        "tokenizer_loaded": True,
        "unloaded_after_probe": True,
    }
    worker = {
        "candidate": candidate_receipt,
        "generation_evidence": generation_evidence,
        "model_id": candidate,
        "package_versions": versions,
        "schema_version": SCHEMA_WORKER,
    }
    sys.stdout.buffer.write(canonical_json_bytes(worker))
    sys.stdout.buffer.flush()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", choices=sorted(EXPECTED_CANDIDATES), required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()
    run_worker(args.candidate, args.snapshot)


if __name__ == "__main__":
    main()
