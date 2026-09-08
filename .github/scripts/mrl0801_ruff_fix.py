from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def replace_exact(path: str, old: str, new: str, *, expected: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} exact match(es), found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "scripts/mesc_mrl_0801_hf_acquire.py",
    '        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")',
    '        raise AcquisitionEntrypointError(\n            "receipt witness root must be outside the raw snapshot root"\n        )',
    expected=2,
)
replace_exact(
    "scripts/mesc_mrl_0801_hf_acquire.py",
    '        raise AcquisitionEntrypointError("receipt witness root could not be opened safely") from None',
    '        raise AcquisitionEntrypointError(\n            "receipt witness root could not be opened safely"\n        ) from None',
)
replace_exact(
    "scripts/mesc_mrl_0801_hf_acquire.py",
    '        raise AcquisitionEntrypointError("receipt witness root changed during acquisition") from None',
    '        raise AcquisitionEntrypointError(\n            "receipt witness root changed during acquisition"\n        ) from None',
)
replace_exact(
    "tests/test_mesc_mrl_0801_hf_acquire_cli.py",
    "from typing import Any\n",
    "",
)
replace_exact(
    "tests/test_mesc_mrl_0801_hf_witness_v1.py",
    "from typing import Any\n",
    "",
)
replace_exact(
    "tests/test_mesc_mrl_0801_hf_witness_v1.py",
    "            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)  # noqa: PTH104",
    "            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)",
)
replace_exact(
    "tests/test_mesc_mrl_0801_hf_acquisition_v1.py",
    "                witness_root=witness_root_for(tmp_path / hashlib.sha256(revision.encode()).hexdigest()),",
    "                witness_root=witness_root_for(\n                    tmp_path / hashlib.sha256(revision.encode()).hexdigest()\n                ),",
)
