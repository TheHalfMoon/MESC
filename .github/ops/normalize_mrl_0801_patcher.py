from __future__ import annotations

import sys
from pathlib import Path


if len(sys.argv) != 2:
    raise SystemExit("usage: normalize_mrl_0801_patcher.py PATCHER")

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''replace_once(
    mount_test,
    "acquired=(_acquired_file(asset.name),),",
    "acquired=(_acquired_file(asset),),",
)'''
new = '''mount_path = Path(mount_test)
mount_text = mount_path.read_text(encoding="utf-8")
old_mount_call = "acquired=(_acquired_file(asset.name),),"
if mount_text.count(old_mount_call) != 2:
    raise SystemExit(
        f"{mount_test}: expected two mount-helper replacements, "
        f"found {mount_text.count(old_mount_call)}"
    )
mount_path.write_text(
    mount_text.replace(old_mount_call, "acquired=(_acquired_file(asset),),"),
    encoding="utf-8",
)'''
if text.count(old) != 1:
    raise SystemExit(f"patcher normalization target count is {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
