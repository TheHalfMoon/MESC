from pathlib import Path

path = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
text = path.read_text(encoding="utf-8")
old = '            \'{"peft_type":"LORA"}\n\',\n'
new = '            \'{"peft_type":"LORA"}\\n\',\n'
if text.count(old) != 1:
    raise SystemExit(f"generated newline repair matched {text.count(old)} times, expected once")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
