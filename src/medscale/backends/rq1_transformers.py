"""RQ1-only Transformers constrained-decoding adapter."""

from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Final, Literal, Protocol

from medscale.backends.common import BackendError, BackendUnsupportedGrammarError
from medscale.backends.transformers.backend import EncodedInput
from medscale.modelkit.interfaces import FinishReason, GenerationRequest, GenerationResult, ModelRef

_XGRAMMAR_VERSION: Final = "0.2.7"
_RQ1_PATIENT_GBNF_SHA256: Final = "b63ff5003471f3af8c3624e508f08a418f7e9f7f6ed18ecf743d7f6ad8b7f16c"
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_RQ1_SEEDS: Final = frozenset({17, 29, 43})
_RQ1_MAX_NEW_TOKENS: Final = 512
_FROZEN_CANDIDATES: Final[dict[str, tuple[str, int]]] = {
    "Qwen/Qwen3.8-27B": (
        "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0",
        248320,
    ),
    "google/gemma-4-31B-it": (
        "842da3794eaa0b77d5f08bae87a17459d91ff475",
        262144,
    ),
}


class RQ1TransformersError(BackendError):
    """Base fail-closed error for the RQ1 Transformers lane."""


class RQ1GrammarCompileError(RQ1TransformersError):
    """The exact frozen grammar could not be compiled or enforced."""


class RQ1GenerationError(RQ1TransformersError):
    """The injected RQ1 runtime failed or returned inconsistent tokens."""


@dataclass(frozen=True, slots=True)
class RQ1TransformersConfig:
    """Exact candidate/runtime identity needed by the repository-side adapter."""

    model_id: str
    model_revision: str
    tokenizer_revision: str
    model_vocab_size: int
    quantization: str = "none"

    def __post_init__(self) -> None:
        expected = _FROZEN_CANDIDATES.get(self.model_id)
        if expected is None:
            raise RQ1TransformersError("model_id is outside the frozen RQ1 candidate roster")
        expected_revision, expected_vocab = expected
        if (
            _SHA40.fullmatch(self.model_revision) is None
            or self.model_revision != expected_revision
            or self.tokenizer_revision != expected_revision
        ):
            raise RQ1TransformersError(
                "model/tokenizer revision does not match frozen RQ1 identity"
            )
        if self.model_vocab_size != expected_vocab:
            raise RQ1TransformersError("model vocabulary size does not match frozen RQ1 identity")
        if not self.quantization.strip():
            raise RQ1TransformersError("quantization identity must be non-empty")


class RQ1TransformersRuntime(Protocol):
    """Injected text-only generation seam over a separately qualified model load."""

    @property
    def model_revision(self) -> str: ...

    @property
    def tokenizer_revision(self) -> str: ...

    @property
    def model_vocab_size(self) -> int: ...

    @property
    def tokenizer(self) -> Any: ...

    def encode(self, text: str) -> EncodedInput: ...

    def generate(
        self,
        encoded: EncodedInput,
        *,
        max_new_tokens: int,
        seed: int,
        logits_processors: tuple[Any, ...],
        do_sample: Literal[False],
        num_beams: Literal[1],
    ) -> tuple[int, ...]: ...

    def decode(self, token_ids: tuple[int, ...]) -> str: ...


class GrammarProcessorFactory(Protocol):
    """Construct one fresh grammar processor for one generation request."""

    def create(self, grammar: str, *, runtime: RQ1TransformersRuntime) -> Any: ...


class XGrammarProcessorFactory:
    """Lazy exact-version XGrammar bridge."""

    def create(self, grammar: str, *, runtime: RQ1TransformersRuntime) -> Any:
        try:
            xgr: Any = importlib.import_module("xgrammar")
            hf: Any = importlib.import_module("xgrammar.contrib.hf")
        except Exception as exc:
            raise RQ1GrammarCompileError("xgrammar 0.2.7 is unavailable") from exc
        try:
            installed_version = metadata.version("xgrammar")
        except metadata.PackageNotFoundError as exc:
            raise RQ1GrammarCompileError("xgrammar distribution metadata is unavailable") from exc
        if installed_version != _XGRAMMAR_VERSION:
            raise RQ1GrammarCompileError("xgrammar runtime version does not match frozen 0.2.7")
        try:
            tokenizer_info = xgr.TokenizerInfo.from_huggingface(
                runtime.tokenizer,
                vocab_size=runtime.model_vocab_size,
            )
            compiler = xgr.GrammarCompiler(tokenizer_info, max_threads=1, cache_enabled=False)
            compiled = compiler.compile_grammar(grammar, root_rule_name="root")
            return hf.LogitsProcessor(compiled)
        except Exception as exc:
            raise RQ1GrammarCompileError("frozen RQ1 grammar compilation failed") from exc


class RQ1TransformersTextGenerator:
    """Deterministic RQ1 generator with explicit constrained decoding."""

    def __init__(
        self,
        config: RQ1TransformersConfig,
        *,
        runtime: RQ1TransformersRuntime,
        grammar_factory: GrammarProcessorFactory | None = None,
    ) -> None:
        if runtime.model_revision != config.model_revision:
            raise RQ1TransformersError("runtime model revision does not match RQ1 config")
        if runtime.tokenizer_revision != config.tokenizer_revision:
            raise RQ1TransformersError("runtime tokenizer revision does not match RQ1 config")
        if runtime.model_vocab_size != config.model_vocab_size:
            raise RQ1TransformersError("runtime model vocabulary does not match RQ1 config")
        self._config = config
        self._runtime = runtime
        self._grammar_factory = grammar_factory or XGrammarProcessorFactory()
        self._ref = ModelRef(
            model_id=config.model_id,
            revision=config.model_revision,
            quantization=config.quantization,
            backend="transformers-rq1-xgrammar",
        )

    @property
    def model(self) -> ModelRef:
        return self._ref

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self._validate_request(request)
        if request.grammar is None:
            raise BackendUnsupportedGrammarError(
                "RQ1 constrained lane requires the exact frozen Patient grammar; "
                "unconstrained generation is not admitted"
            )
        grammar_bytes = request.grammar.encode("utf-8")
        if hashlib.sha256(grammar_bytes).hexdigest() != _RQ1_PATIENT_GBNF_SHA256:
            raise BackendUnsupportedGrammarError(
                "RQ1 constrained lane accepts only the exact frozen Patient grammar"
            )
        processors: tuple[Any, ...]
        try:
            processors = (self._grammar_factory.create(request.grammar, runtime=self._runtime),)
        except (BackendUnsupportedGrammarError, RQ1GrammarCompileError):
            raise
        except Exception as exc:
            raise RQ1GrammarCompileError("grammar processor construction failed") from exc
        try:
            encoded = self._runtime.encode(request.prompt)
            output = tuple(
                int(token)
                for token in self._runtime.generate(
                    encoded,
                    max_new_tokens=request.max_new_tokens,
                    seed=request.seed,
                    logits_processors=processors,
                    do_sample=False,
                    num_beams=1,
                )
            )
        except (RQ1GrammarCompileError, BackendUnsupportedGrammarError):
            raise
        except Exception as exc:
            raise RQ1GenerationError(f"RQ1 generation failed: {exc}") from exc
        if output[: len(encoded.input_ids)] != encoded.input_ids:
            raise RQ1GenerationError("RQ1 output does not begin with exact prompt tokens")
        new_ids = output[len(encoded.input_ids) :]
        try:
            text = self._runtime.decode(new_ids)
        except Exception as exc:
            raise RQ1GenerationError(f"RQ1 decoding failed: {exc}") from exc
        finish_reason = (
            FinishReason.LENGTH if len(new_ids) >= request.max_new_tokens else FinishReason.STOP
        )
        return GenerationResult(text=text, model=self._ref, finish_reason=finish_reason)

    @staticmethod
    def _validate_request(request: GenerationRequest) -> None:
        if request.temperature != 0.0:
            raise RQ1TransformersError("RQ1 generation requires temperature=0")
        if request.stop:
            raise RQ1TransformersError(
                "RQ1 generation does not admit request-specific stop strings"
            )
        if request.seed not in _RQ1_SEEDS:
            raise RQ1TransformersError("RQ1 generation seed is outside the frozen seed set")
        if request.max_new_tokens > _RQ1_MAX_NEW_TOKENS:
            raise RQ1TransformersError("RQ1 max_new_tokens exceeds the frozen 512-token ceiling")


__all__ = [
    "GrammarProcessorFactory",
    "RQ1GenerationError",
    "RQ1GrammarCompileError",
    "RQ1TransformersConfig",
    "RQ1TransformersError",
    "RQ1TransformersRuntime",
    "RQ1TransformersTextGenerator",
    "XGrammarProcessorFactory",
]
