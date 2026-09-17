"""MRL-0809 repository-side prerequisite contracts; no scientific model loading."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

from medscale.backends.common import BackendUnsupportedGrammarError
from medscale.backends.llamacpp import backend as llamacpp_backend
from medscale.backends.rq1_transformers import (
    RQ1GenerationError,
    RQ1GrammarCompileError,
    RQ1TransformersConfig,
    RQ1TransformersError,
    RQ1TransformersTextGenerator,
)
from medscale.backends.transformers.backend import EncodedInput, TransformersTextGenerator
from medscale.backends.transformers.validation import TransformersGenerationConfig
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0809_fhir_gbnf_v1 import (
    RQ1_PATIENT_GBNF_SHA256,
    MRL0809FHIRGrammarError,
    compile_rq1_patient_gbnf,
)
from medscale.mesc._mrl_0809_runtime_feasibility_v1 import (
    MRL0809RuntimeFeasibilityError,
    validate_runtime_feasibility_receipt,
)
from medscale.modelkit.interfaces import GenerationRequest, ModelRef

_ROOT = Path(__file__).resolve().parents[1]
_GBNF = _ROOT / "specs/mesc-experiment-0/mrl-0809-rq1-patient-v1.gbnf"
_FHIR = _ROOT / "specs/mesc-experiment-0/fhir-r4"
_QWEN = "Qwen/Qwen3.8-27B"
_QWEN_SHA = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
_QWEN_VOCAB = 248320


class _B0Runtime:
    model_revision = "a" * 40
    tokenizer_revision = "a" * 40

    def __init__(self) -> None:
        self.touched = False

    def encode(self, text: str) -> EncodedInput:
        self.touched = True
        return EncodedInput((1,), (1,))

    def generate(self, encoded: EncodedInput, *, max_new_tokens: int) -> tuple[int, ...]:
        return (*encoded.input_ids, 2)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return "ok"


class _RQ1Runtime:
    model_revision = _QWEN_SHA
    tokenizer_revision = _QWEN_SHA
    model_vocab_size = _QWEN_VOCAB
    tokenizer: object = object()

    def __init__(self, *, prefix: bool = True) -> None:
        self.prefix = prefix
        self.calls: list[dict[str, object]] = []
        self.decoded: tuple[int, ...] | None = None

    def encode(self, text: str) -> EncodedInput:
        return EncodedInput((1, 2), (1, 1))

    def generate(
        self,
        encoded: EncodedInput,
        *,
        max_new_tokens: int,
        seed: int,
        logits_processors: tuple[Any, ...],
        do_sample: bool,
        num_beams: int,
    ) -> tuple[int, ...]:
        self.calls.append(
            {
                "max_new_tokens": max_new_tokens,
                "seed": seed,
                "logits_processors": logits_processors,
                "do_sample": do_sample,
                "num_beams": num_beams,
            }
        )
        tail = (7, 8)[:max_new_tokens]
        return encoded.input_ids + tail if self.prefix else tail

    def decode(self, token_ids: tuple[int, ...]) -> str:
        self.decoded = token_ids
        return "{}"


class _GrammarFactory:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0
        self.processor = object()

    def create(self, grammar: str, *, runtime: object) -> object:
        self.calls += 1
        if self.fail:
            raise RuntimeError("compile-failure")
        return self.processor


def _rq1_config() -> RQ1TransformersConfig:
    return RQ1TransformersConfig(
        model_id=_QWEN,
        model_revision=_QWEN_SHA,
        tokenizer_revision=_QWEN_SHA,
        model_vocab_size=_QWEN_VOCAB,
    )


def _b0_config() -> TransformersGenerationConfig:
    return TransformersGenerationConfig(
        model_id="meta-llama/Llama-3.2-3B-Instruct",
        model_revision="a" * 40,
        tokenizer_revision="a" * 40,
        max_new_tokens=8,
        seed=0,
    )


def _receipt() -> dict[str, object]:
    common = {
        "load_completed": True,
        "peak_cpu_memory_bytes": 1,
        "peak_gpu_memory_bytes": 1,
        "runtime_representation": "bitsandbytes-nf4-v1",
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": "d" * 64,
        "text_only_generation": True,
        "unloaded_after_probe": True,
    }
    return {
        "candidate_substitution_performed": False,
        "candidates": [
            {
                **common,
                "architecture": "Qwen3_5ForConditionalGeneration",
                "config_sha256": "191e0af232104ed8b65258cf3fb2b842e288008baca7633c11b82a1ac7203aab",
                "model_id": _QWEN,
                "processor_config_sha256": (
                    "27225450ac9c6529872ee1924fcb0962ff5634834f817040f444118116f4e516"
                ),
                "revision": _QWEN_SHA,
                "text_vocab_size": _QWEN_VOCAB,
                "tokenizer_config_sha256": (
                    "b11349aafa7cdc6a320767cf7ceb29ed82f7eda5d65e8e0819e76f0ce947bf27"
                ),
            },
            {
                **common,
                "architecture": "Gemma4ForConditionalGeneration",
                "config_sha256": "e967dd38bc5cfd38bd09a995a7bf4a754075df2b46aba68f7fbb5a791e6d8dd1",
                "model_id": "google/gemma-4-31B-it",
                "processor_config_sha256": (
                    "32bdf45d2ad4cc29a0822ddd157a182de76644f0419a6228d151495256e9813c"
                ),
                "revision": "842da3794eaa0b77d5f08bae87a17459d91ff475",
                "text_vocab_size": 262144,
                "tokenizer_config_sha256": (
                    "9f4fec4b1dc6ecddf8f4a92e9caea5971c0e67d81309f3f9066a2bee8c362633"
                ),
            },
        ],
        "capacity_fallback_performed": False,
        "cleanup_completed": True,
        "compute_dtype": "float16",
        "dependency_lock_sha256": "b" * 64,
        "disposition": "PASS",
        "gpu_model": "Tesla T4",
        "gpu_vram_bytes": 1,
        "local_files_only_during_isolated_execution": True,
        "monetary_cost_microunits": 0,
        "mrl_0804_evidence_sha256": (
            "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
        ),
        "mrl_0804_runtime_identity_sha256": (
            "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
        ),
        "mrl_0808_evidence_sha256": (
            "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"
        ),
        "network_access_during_isolated_generation": False,
        "network_access_during_isolated_load": False,
        "optimizer_present": False,
        "persistent_weight_writeback": False,
        "processor_policy": "AUTO_PROCESSOR_EXACT_REVISION",
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": "assignment:test",
        "provider_owner": "GOOGLE",
        "repository_sha": "1" * 40,
        "repository_tree": "2" * 40,
        "runtime_identity_sha256": "c" * 64,
        "sandbox_policy_sha256": "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316",
        "schema_version": "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V1",
        "static_prerequisite_manifest_sha256": "a" * 64,
        "training_performed": False,
        "trust_remote_code": False,
        "weight_mutation_performed": False,
    }


def test_bounded_fhir_compiler_reproduces_frozen_grammar_exactly() -> None:
    result = compile_rq1_patient_gbnf(
        patient_bytes=(_FHIR / "patient.profile.json").read_bytes(),
        address_bytes=(_FHIR / "address.profile.json").read_bytes(),
    )
    assert result == _GBNF.read_bytes()
    assert hashlib.sha256(result).hexdigest() == RQ1_PATIENT_GBNF_SHA256


def test_bounded_fhir_compiler_rejects_source_byte_drift() -> None:
    patient = (_FHIR / "patient.profile.json").read_bytes() + b" "
    with pytest.raises(MRL0809FHIRGrammarError, match="identity drifted"):
        compile_rq1_patient_gbnf(
            patient_bytes=patient,
            address_bytes=(_FHIR / "address.profile.json").read_bytes(),
        )


def test_generic_transformers_rejects_grammar_before_runtime_touch() -> None:
    runtime = _B0Runtime()
    generator = TransformersTextGenerator(_b0_config(), runtime=runtime)
    with pytest.raises(BackendUnsupportedGrammarError, match="cannot enforce"):
        generator.generate(GenerationRequest(prompt="p", seed=0, grammar='root ::= "x"'))
    assert runtime.touched is False


def test_llamacpp_placeholder_rejects_grammar(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llamacpp_backend, "validate_package_installed", lambda: None)
    generator = llamacpp_backend.LlamaCppTextGenerator(
        ModelRef(model_id="fixture", revision="a" * 40, backend="llama.cpp")
    )
    with pytest.raises(BackendUnsupportedGrammarError, match="cannot enforce"):
        generator.generate(GenerationRequest(prompt="p", seed=0, grammar='root ::= "x"'))


def test_rq1_adapter_passes_exact_frozen_processor_and_deterministic_flags() -> None:
    runtime = _RQ1Runtime()
    factory = _GrammarFactory()
    generator = RQ1TransformersTextGenerator(
        _rq1_config(), runtime=runtime, grammar_factory=factory
    )
    request = GenerationRequest(
        prompt="synthetic",
        seed=17,
        max_new_tokens=2,
        grammar=_GBNF.read_text(encoding="utf-8"),
    )
    result = generator.generate(request)
    assert result.text == "{}"
    assert runtime.decoded == (7, 8)
    assert factory.calls == 1
    assert runtime.calls == [
        {
            "max_new_tokens": 2,
            "seed": 17,
            "logits_processors": (factory.processor,),
            "do_sample": False,
            "num_beams": 1,
        }
    ]


def test_rq1_adapter_rejects_unfrozen_grammar_and_request_drift() -> None:
    generator = RQ1TransformersTextGenerator(_rq1_config(), runtime=_RQ1Runtime())
    with pytest.raises(BackendUnsupportedGrammarError, match="exact frozen"):
        generator.generate(GenerationRequest(prompt="p", seed=17, grammar='root ::= "x"'))
    with pytest.raises(RQ1TransformersError, match="seed"):
        generator.generate(GenerationRequest(prompt="p", seed=18))
    with pytest.raises(RQ1TransformersError, match="512-token"):
        generator.generate(GenerationRequest(prompt="p", seed=17, max_new_tokens=513))
    with pytest.raises(RQ1TransformersError, match="temperature"):
        generator.generate(GenerationRequest(prompt="p", seed=17, temperature=0.1))
    with pytest.raises(RQ1TransformersError, match="stop"):
        generator.generate(GenerationRequest(prompt="p", seed=17, stop=("x",)))


def test_rq1_adapter_maps_processor_failure_and_prefix_mismatch() -> None:
    generator = RQ1TransformersTextGenerator(
        _rq1_config(), runtime=_RQ1Runtime(), grammar_factory=_GrammarFactory(fail=True)
    )
    with pytest.raises(RQ1GrammarCompileError, match="processor construction"):
        generator.generate(
            GenerationRequest(prompt="p", seed=17, grammar=_GBNF.read_text(encoding="utf-8"))
        )
    generator = RQ1TransformersTextGenerator(_rq1_config(), runtime=_RQ1Runtime(prefix=False))
    with pytest.raises(RQ1GenerationError, match="exact prompt"):
        generator.generate(GenerationRequest(prompt="p", seed=17))


def test_runtime_feasibility_receipt_accepts_exact_dual_candidate_pass() -> None:
    raw = canonical_json_bytes(_receipt())
    receipt = validate_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256="a" * 64,
        expected_dependency_lock_sha256="b" * 64,
        expected_repository_sha="1" * 40,
        expected_repository_tree="2" * 40,
    )
    assert receipt.receipt_sha256 == hashlib.sha256(raw).hexdigest()
    assert receipt.runtime_representation == "bitsandbytes-nf4-v1"


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("training_performed", True),
        ("weight_mutation_performed", True),
        ("capacity_fallback_performed", True),
        ("network_access_during_isolated_load", True),
        ("monetary_cost_microunits", 1),
        ("cleanup_completed", False),
    ],
)
def test_runtime_feasibility_receipt_rejects_forbidden_evidence_drift(
    field: str, bad: object
) -> None:
    document = _receipt()
    document[field] = bad
    with pytest.raises(MRL0809RuntimeFeasibilityError):
        validate_runtime_feasibility_receipt(
            canonical_json_bytes(document),
            expected_static_prerequisite_manifest_sha256="a" * 64,
            expected_dependency_lock_sha256="b" * 64,
        )


def test_runtime_feasibility_receipt_rejects_candidate_substitution() -> None:
    document = _receipt()
    candidates = document["candidates"]
    assert isinstance(candidates, list)
    first = candidates[0]
    assert isinstance(first, dict)
    first["model_id"] = "other/model"
    with pytest.raises(MRL0809RuntimeFeasibilityError, match="frozen RQ1 roster"):
        validate_runtime_feasibility_receipt(
            canonical_json_bytes(document),
            expected_static_prerequisite_manifest_sha256="a" * 64,
            expected_dependency_lock_sha256="b" * 64,
        )
