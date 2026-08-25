from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected once")
    return text.replace(old, new, 1)


test_path = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
test_text = test_path.read_text(encoding="utf-8")
test_text = replace_once(
    test_text,
    '            \'{"peft_type":"LORA"}\n\',\n',
    '            \'{"peft_type":"LORA"}\\n\',\n',
    label="generated newline repair",
)
test_path.write_text(test_text, encoding="utf-8", newline="\n")

source_path = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
source_text = source_path.read_text(encoding="utf-8")
source_text = replace_once(
    source_text,
    '                raise HfLocalSftBackendError("publication parent disappeared during execution")\n',
    '                raise HfLocalSftBackendError(\n'
    '                    "publication parent disappeared during execution"\n'
    '                ) from None\n',
    label="B904 publication parent repair",
)
source_path.write_text(source_text, encoding="utf-8", newline="\n")
