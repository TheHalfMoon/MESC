from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path("scripts/diag_auth_trust_registry_218.py")


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("diag_auth_trust_registry_218", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load diagnostic module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = _load()
    original = module.replace_once

    def replace_once(text: str, old: str, new: str, *, label: str) -> str:
        count = text.count(old)
        if label == "receipt payload trust identity" and count == 2:
            index = text.rfind(old)
            if index < 0:
                raise RuntimeError("receipt payload trust identity not found")
            return text[:index] + new + text[index + len(old) :]
        return original(text, old, new, label=label)

    module.replace_once = replace_once
    module.main()


if __name__ == "__main__":
    main()
