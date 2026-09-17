"""Optional real-XGrammar integration using only a synthetic local tokenizer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def test_xgrammar_027_compiles_frozen_patient_grammar_with_local_tokenizer() -> None:
    tokenizers: Any = pytest.importorskip("tokenizers")
    tokenizers_models: Any = pytest.importorskip("tokenizers.models")
    tokenizers_pre: Any = pytest.importorskip("tokenizers.pre_tokenizers")
    transformers: Any = pytest.importorskip("transformers")
    from medscale.backends.rq1_transformers import XGrammarProcessorFactory

    vocab = {
        "[UNK]": 0,
        "[EOS]": 1,
        "{": 2,
        "}": 3,
        "[": 4,
        "]": 5,
        ":": 6,
        ",": 7,
        '"': 8,
        "Patient": 9,
        "resourceType": 10,
        "id": 11,
        "male": 12,
        "female": 13,
        "true": 14,
        "false": 15,
        "x": 16,
        " ": 17,
    }
    backend = tokenizers.Tokenizer(tokenizers_models.WordLevel(vocab=vocab, unk_token="[UNK]"))
    backend.pre_tokenizer = tokenizers_pre.Whitespace()
    tokenizer = transformers.PreTrainedTokenizerFast(
        tokenizer_object=backend,
        unk_token="[UNK]",
        eos_token="[EOS]",
    )

    class SyntheticRuntime:
        model_vocab_size = len(vocab)

        def __init__(self) -> None:
            self.tokenizer = tokenizer

    grammar = (_ROOT / "specs/mesc-experiment-0/mrl-0809-rq1-patient-v1.gbnf").read_text(
        encoding="utf-8"
    )
    processor = XGrammarProcessorFactory().create(grammar, runtime=SyntheticRuntime())  # type: ignore[arg-type]
    assert type(processor).__name__ == "LogitsProcessor"
