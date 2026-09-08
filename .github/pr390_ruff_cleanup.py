from __future__ import annotations

import sys
from pathlib import Path


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    observed = text.count(old)
    if observed != count:
        raise SystemExit(f"expected {count} replacements in {path}, found {observed}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main(root: Path) -> None:
    replace_exact(
        root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py",
        "import contextlib\nimport ctypes\n",
        "import ctypes\n",
    )
    cli_test = root / "tests/test_mesc_mrl_0801_hf_acquire_cli.py"
    replace_exact(
        cli_test,
        "from types import ModuleType\n\nimport pytest\n",
        "from types import ModuleType\nfrom typing import Any\n\nimport pytest\n",
    )
    replace_exact(
        cli_test,
        '''    def race(output: object) -> None:\n        descriptor = getattr(output, "descriptor")\n        name = getattr(output, "name")\n''',
        '''    def race(output: Any) -> None:\n        descriptor = output.descriptor\n        name = output.name\n''',
    )
    replace_exact(
        root / "tests/test_mesc_mrl_0801_hf_witness_v1.py",
        "            os.rename(  # noqa: PTH104 -- descriptor-relative race injection is required\n",
        "            os.rename(\n",
        count=2,
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: pr390_ruff_cleanup.py <repo-root>")
    main(Path(sys.argv[1]))
