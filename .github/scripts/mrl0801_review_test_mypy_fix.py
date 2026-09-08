from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1])
path = root / "tests/test_mesc_mrl_0801_hf_witness_v1.py"
text = path.read_text(encoding="utf-8")
old = '    monkeypatch.setattr(subject.os, "fstat", mismatched)\n'
new = '    monkeypatch.setattr(os, "fstat", mismatched)\n'
if text.count(old) != 1:
    raise SystemExit("expected exactly one subject.os fstat monkeypatch")
path.write_text(text.replace(old, new), encoding="utf-8")
