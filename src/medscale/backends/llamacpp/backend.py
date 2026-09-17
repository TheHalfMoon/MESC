from __future__ import annotations

from medscale.backends.common import BackendUnsupportedGrammarError
from medscale.backends.llamacpp.validation import validate_package_installed
from medscale.modelkit.interfaces import (
    FinishReason,
    GenerationRequest,
    GenerationResult,
    ModelRef,
    Span,
)

__all__ = [
    "LlamaCppBackend",
    "LlamaCppSpanExtractor",
    "LlamaCppTextGenerator",
]


class LlamaCppBackend:
    name = "llama.cpp"
    version = "0.1.0"


class LlamaCppTextGenerator:
    def __init__(self, ref: ModelRef) -> None:
        validate_package_installed()
        self.model = ref

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.grammar is not None:
            raise BackendUnsupportedGrammarError(
                "the llama.cpp placeholder backend cannot enforce GenerationRequest.grammar"
            )
        return GenerationResult(
            text=f"[llama.cpp:{self.model.model_id}] {request.prompt}",
            model=self.model,
            finish_reason=FinishReason.STOP,
        )


class LlamaCppSpanExtractor:
    def __init__(self, ref: ModelRef) -> None:
        validate_package_installed()
        self.model = ref

    def extract(self, text: str) -> tuple[Span, ...]:
        return (
            Span(
                start=0,
                end=min(4, len(text)),
                label="LLAMA",
                text=text[:4],
            ),
        )
