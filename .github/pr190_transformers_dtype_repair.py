from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected exactly once")
    return text.replace(old, new, 1)


source = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
text = source.read_text(encoding="utf-8")
text = replace_once(
    text,
    '                    "dtype": torch_module.bfloat16,\n',
    '                    "torch_dtype": torch_module.bfloat16,\n',
    label="Transformers dtype compatibility key",
)
source.write_text(text, encoding="utf-8", newline="\n")


tests = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
text = tests.read_text(encoding="utf-8")
text = replace_once(
    text,
    '    assert model_kwargs["use_safetensors"] is True\n',
    '    assert model_kwargs["use_safetensors"] is True\n'
    '    assert model_kwargs["torch_dtype"] == "bf16"\n'
    '    assert "dtype" not in model_kwargs\n',
    label="runtime dtype compatibility assertions",
)
tests.write_text(text, encoding="utf-8", newline="\n")


spec = Path("specs/mesc-hf-local-sft-backend-v1/README.md")
text = spec.read_text(encoding="utf-8")
text = replace_once(
    text,
    '- Transformers `dtype=` for the current model-loading API;\n',
    '- Transformers `torch_dtype=` for compatibility with the repository\'s current\n'
    '  `transformers>=4.44` surface; the later dependency-lock gate may narrow this to the\n'
    '  pinned current-major API;\n',
    label="spec dtype compatibility contract",
)
spec.write_text(text, encoding="utf-8", newline="\n")
