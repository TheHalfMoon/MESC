"""MRL-0809 producer regressions for fail-closed unsupported grammar requests."""

from __future__ import annotations

import pytest

from medscale.backends import BackendUnsupportedGrammarError
from medscale.backends.llamacpp import backend as llamacpp_backend
from medscale.backends.transformers.backend import EncodedInput, TransformersTextGenerator
from medscale.backends.transformers.validation import TransformersGenerationConfig
from medscale.modelkit.interfaces import GenerationRequest, ModelRef

_SHA = "a" * 40
_MODEL = "meta-llama/Llama-3.2-3B-Instruct"
_GRAMMAR = 'root ::= "Patient"'


class _UntouchedRuntime:
    def __init__(self) -> None:
        self.touched = False

    @property
    def model_revision(self) -> str:
        return _SHA

    @property
    def tokenizer_revision(self) -> str:
        return _SHA

    def encode(self, text: str) -> EncodedInput:
        self.touched = True
        return EncodedInput(input_ids=(1,), attention_mask=(1,))

    def generate(self, encoded: EncodedInput, *, max_new_tokens: int) -> tuple[int, ...]:
        self.touched = True
        return (*encoded.input_ids, 2)

    def decode(self, token_ids: tuple[int, ...]) -> str:
        self.touched = True
        return "decoded"


def _transformers_config() -> TransformersGenerationConfig:
    return TransformersGenerationConfig(
        model_id=_MODEL,
        model_revision=_SHA,
        tokenizer_revision=_SHA,
        max_new_tokens=8,
        seed=0,
    )


def test_b0_transformers_rejects_grammar_before_runtime_touch() -> None:
    runtime = _UntouchedRuntime()
    generator = TransformersTextGenerator(_transformers_config(), runtime=runtime)

    with pytest.raises(BackendUnsupportedGrammarError, match="cannot enforce grammar"):
        generator.generate(GenerationRequest(prompt="p", seed=0, grammar=_GRAMMAR))

    assert runtime.touched is False


def test_llamacpp_placeholder_rejects_grammar_before_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llamacpp_backend, "validate_package_installed", lambda: None)
    generator = llamacpp_backend.LlamaCppTextGenerator(
        ModelRef(model_id="fixture/model", revision=_SHA, backend="llama.cpp")
    )

    with pytest.raises(BackendUnsupportedGrammarError, match="cannot enforce grammar"):
        generator.generate(GenerationRequest(prompt="p", seed=0, grammar=_GRAMMAR))
