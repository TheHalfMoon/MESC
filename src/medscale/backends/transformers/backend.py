"""Deterministic, dependency-injected Transformers generation boundary.

No model, tokenizer, ``torch``, or pipeline is imported or constructed at module
import time. Runtime construction is separated from generation and injected, so
tests exercise the whole boundary — including the real PyTorch adapter — with
fake ``torch``/tokenizer/model objects, and never touch a real model, the
network, or the filesystem. Production generation never echoes the prompt: only
the newly generated tokens are decoded and returned.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Protocol

from medscale.backends.common import BackendError, BackendUnsupportedGrammarError
from medscale.backends.transformers.validation import (
    TransformersGenerationConfig,
    validate_generation_config,
    validate_package_installed,
)
from medscale.modelkit.interfaces import (
    FinishReason,
    GenerationRequest,
    GenerationResult,
    ModelRef,
    Span,
)

__all__ = [
    "EncodedInput",
    "TransformersBackend",
    "TransformersDecodeError",
    "TransformersGenerateError",
    "TransformersLoadError",
    "TransformersRuntime",
    "TransformersSpanExtractor",
    "TransformersTextGenerator",
    "TransformersTokenizeError",
    "build_transformers_runtime",
]


class TransformersLoadError(BackendError):
    """Runtime/model construction failed."""


class TransformersTokenizeError(BackendError):
    """Tokenization of the prompt failed."""


class TransformersGenerateError(BackendError):
    """Token generation failed or produced an inconsistent result."""


class TransformersDecodeError(BackendError):
    """Decoding of generated tokens failed."""


@dataclass(frozen=True, slots=True)
class EncodedInput:
    """A typed encoded-input boundary; no hidden or global runtime state.

    ``input_ids`` and ``attention_mask`` are plain integer tuples used for
    deterministic prompt-prefix verification. ``backend_input`` carries the
    optional backend tensors for the real runtime and is ``None`` for fakes.
    """

    input_ids: tuple[int, ...]
    attention_mask: tuple[int, ...]
    backend_input: Any = None


class TransformersRuntime(Protocol):
    """The injectable runtime boundary: encode, generate, decode, revisions.

    ``generate`` returns the full token sequence (the exact prompt tokens
    followed by newly generated tokens), so the generator can strip the prompt
    prefix and never echo it.
    """

    @property
    def model_revision(self) -> str: ...

    @property
    def tokenizer_revision(self) -> str: ...

    def encode(self, text: str) -> EncodedInput: ...

    def generate(self, encoded: EncodedInput, *, max_new_tokens: int) -> tuple[int, ...]: ...

    def decode(self, token_ids: tuple[int, ...]) -> str: ...


class TransformersBackend:
    name = "transformers"
    version = "0.1.0"


class TransformersTextGenerator:
    """Deterministic generator over an injected :class:`TransformersRuntime`.

    Configuration is validated before anything else; a runtime whose resolved
    model/tokenizer revisions do not match the validated config is rejected. The
    returned completion contains only the generated tokens, never the prompt.
    """

    def __init__(
        self, config: TransformersGenerationConfig, *, runtime: TransformersRuntime
    ) -> None:
        validate_generation_config(config)
        if runtime.model_revision != config.model_revision:
            raise TransformersLoadError(
                f"runtime model_revision {runtime.model_revision!r} does not match "
                f"config {config.model_revision!r}"
            )
        if runtime.tokenizer_revision != config.tokenizer_revision:
            raise TransformersLoadError(
                f"runtime tokenizer_revision {runtime.tokenizer_revision!r} does not match "
                f"config {config.tokenizer_revision!r}"
            )
        self._config = config
        self._runtime = runtime
        self._ref = ModelRef(
            model_id=config.model_id, revision=config.model_revision, backend="transformers"
        )

    @property
    def model(self) -> ModelRef:
        return self._ref

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.grammar is not None:
            raise BackendUnsupportedGrammarError(
                "B0 Transformers backend cannot enforce grammar-constrained generation; "
                "use a dedicated grammar-capable backend"
            )
        encoded = self._encode(request.prompt)
        output_ids = self._generate(encoded)
        if output_ids[: len(encoded.input_ids)] != encoded.input_ids:
            raise TransformersGenerateError(
                "generation output does not begin with the exact prompt tokens"
            )
        new_ids = output_ids[len(encoded.input_ids) :]
        text = self._decode(new_ids)
        finish = (
            FinishReason.LENGTH
            if len(new_ids) >= self._config.max_new_tokens
            else FinishReason.STOP
        )
        return GenerationResult(text=text, model=self._ref, finish_reason=finish)

    def _encode(self, prompt: str) -> EncodedInput:
        try:
            return self._runtime.encode(prompt)
        except TransformersTokenizeError:
            raise
        except Exception as exc:  # normalize any tokenizer failure
            raise TransformersTokenizeError(f"tokenization failed: {exc}") from exc

    def _generate(self, encoded: EncodedInput) -> tuple[int, ...]:
        try:
            return tuple(
                int(token)
                for token in self._runtime.generate(
                    encoded, max_new_tokens=self._config.max_new_tokens
                )
            )
        except TransformersGenerateError:
            raise
        except Exception as exc:  # normalize any generation failure
            raise TransformersGenerateError(f"generation failed: {exc}") from exc

    def _decode(self, token_ids: tuple[int, ...]) -> str:
        try:
            return self._runtime.decode(token_ids)
        except TransformersDecodeError:
            raise
        except Exception as exc:  # normalize any decode failure
            raise TransformersDecodeError(f"decoding failed: {exc}") from exc


class TransformersSpanExtractor:
    def __init__(self, ref: ModelRef) -> None:
        validate_package_installed()
        self.model = ref

    def extract(self, text: str) -> tuple[Span, ...]:
        return (
            Span(
                start=0,
                end=min(4, len(text)),
                label="TRANSFORMER",
                text=text[:4],
            ),
        )


def _valid_token_id(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _resolve_dtype(torch_module: Any, name: str) -> Any:
    if name not in ("float32", "float16", "bfloat16"):
        raise TransformersLoadError(f"unsupported dtype {name!r}")
    dtype = getattr(torch_module, name, None)
    if dtype is None:
        raise TransformersLoadError(f"torch exposes no dtype {name!r}")
    return dtype


def _resolve_device(torch_module: Any, device: str) -> str:
    if device not in ("cpu", "cuda"):
        raise TransformersLoadError(f"unsupported device {device!r}")
    if device == "cuda" and not bool(torch_module.cuda.is_available()):
        raise TransformersLoadError("CUDA device requested but CUDA is not available")
    return device


def _resolve_pad_eos(tokenizer: Any) -> tuple[int, int]:
    eos = getattr(tokenizer, "eos_token_id", None)
    if not _valid_token_id(eos):
        raise TransformersLoadError(f"tokenizer eos_token_id is missing or malformed: {eos!r}")
    assert isinstance(eos, int)
    pad = getattr(tokenizer, "pad_token_id", None)
    if not _valid_token_id(pad):
        pad = eos
    assert isinstance(pad, int)
    return pad, eos


class _RealTransformersRuntime:
    """Production runtime adapter over injected ``torch``/tokenizer/model objects.

    Correctness (attention mask, device placement, dtype, ``eval``,
    ``inference_mode``, pad/eos) is exercised in tests with fakes; the real
    objects are supplied only by :func:`build_transformers_runtime`.
    """

    def __init__(
        self,
        *,
        torch_module: Any,
        tokenizer: Any,
        model: Any,
        model_revision: str,
        tokenizer_revision: str,
        device: str,
        dtype: str,
    ) -> None:
        self._torch = torch_module
        self._tok = tokenizer
        self._model = model
        self._model_revision = model_revision
        self._tokenizer_revision = tokenizer_revision
        self._device = _resolve_device(torch_module, device)
        self._dtype = _resolve_dtype(torch_module, dtype)
        self._pad_id, self._eos_id = _resolve_pad_eos(tokenizer)
        self._model.to(self._device)

    @property
    def model_revision(self) -> str:
        return self._model_revision

    @property
    def tokenizer_revision(self) -> str:
        return self._tokenizer_revision

    def encode(self, text: str) -> EncodedInput:
        enc: Any = self._tok(text, return_tensors="pt")
        input_ids_tensor: Any = enc["input_ids"]
        attention_mask_tensor: Any = enc["attention_mask"]
        input_ids = tuple(int(token) for token in input_ids_tensor[0])
        attention_mask = tuple(int(mask) for mask in attention_mask_tensor[0])
        return EncodedInput(
            input_ids=input_ids,
            attention_mask=attention_mask,
            backend_input=(input_ids_tensor, attention_mask_tensor),
        )

    def generate(self, encoded: EncodedInput, *, max_new_tokens: int) -> tuple[int, ...]:
        input_ids_tensor, attention_mask_tensor = encoded.backend_input
        input_ids_dev = input_ids_tensor.to(self._device)
        attention_mask_dev = attention_mask_tensor.to(self._device)
        self._model.eval()
        with self._torch.inference_mode():
            output: Any = self._model.generate(
                input_ids=input_ids_dev,
                attention_mask=attention_mask_dev,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                num_beams=1,
                pad_token_id=self._pad_id,
                eos_token_id=self._eos_id,
            )
        return tuple(int(token) for token in output[0])

    def decode(self, token_ids: tuple[int, ...]) -> str:
        return str(self._tok.decode(list(token_ids), skip_special_tokens=True))


def build_transformers_runtime(config: TransformersGenerationConfig) -> TransformersRuntime:
    """Construct the real runtime after validating config and dependency presence.

    Loads the tokenizer and model at their explicit immutable revisions,
    local-files-only, with remote code disabled. ``torch`` and ``transformers``
    are imported lazily, never at module import time. Not invoked by the
    deterministic test suite.
    """
    validate_generation_config(config)
    validate_package_installed()
    try:
        transformers: Any = importlib.import_module("transformers")
        torch_module: Any = importlib.import_module("torch")
        dtype = _resolve_dtype(torch_module, config.dtype)
        _resolve_device(torch_module, config.device)
        tokenizer: Any = transformers.AutoTokenizer.from_pretrained(
            config.model_id,
            revision=config.tokenizer_revision,
            trust_remote_code=config.trust_remote_code,
            local_files_only=config.local_files_only,
        )
        model: Any = transformers.AutoModelForCausalLM.from_pretrained(
            config.model_id,
            revision=config.model_revision,
            trust_remote_code=config.trust_remote_code,
            local_files_only=config.local_files_only,
            torch_dtype=dtype,
        )
    except TransformersLoadError:
        raise
    except Exception as exc:
        raise TransformersLoadError(
            f"failed to load {config.model_id} at model={config.model_revision} "
            f"tokenizer={config.tokenizer_revision} locally: {exc}"
        ) from exc
    return _RealTransformersRuntime(
        torch_module=torch_module,
        tokenizer=tokenizer,
        model=model,
        model_revision=config.model_revision,
        tokenizer_revision=config.tokenizer_revision,
        device=config.device,
        dtype=config.dtype,
    )
