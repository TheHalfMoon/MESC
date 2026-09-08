from pathlib import Path

SCRIPT = Path("scripts/mesc_mrl_0801_hf_acquire.py")
ACQ = Path("tests/test_mesc_mrl_0801_hf_acquisition_v1.py")
CLI = Path("tests/test_mesc_mrl_0801_hf_acquire_cli.py")
WITNESS = Path("tests/test_mesc_mrl_0801_hf_witness_v1.py")

script = SCRIPT.read_text(encoding="utf-8")
replacements = {
    '        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")\n':
        '        raise AcquisitionEntrypointError(\n            "receipt witness root must be outside the raw snapshot root"\n        )\n',
    '        raise AcquisitionEntrypointError("receipt witness root could not be opened safely") from None\n':
        '        raise AcquisitionEntrypointError(\n            "receipt witness root could not be opened safely"\n        ) from None\n',
    '        raise AcquisitionEntrypointError("receipt witness root changed during acquisition") from None\n':
        '        raise AcquisitionEntrypointError(\n            "receipt witness root changed during acquisition"\n        ) from None\n',
}
for old, new in replacements.items():
    count = script.count(old)
    if count == 0:
        raise SystemExit(f"missing script marker: {old!r}")
    script = script.replace(old, new)
SCRIPT.write_text(script, encoding="utf-8")

acq = ACQ.read_text(encoding="utf-8")
old = '                witness_root=witness_root_for(tmp_path / hashlib.sha256(revision.encode()).hexdigest()),\n'
new = '                witness_root=witness_root_for(\n                    tmp_path / hashlib.sha256(revision.encode()).hexdigest()\n                ),\n'
if acq.count(old) != 1:
    raise SystemExit(f"acquisition marker count: {acq.count(old)}")
ACQ.write_text(acq.replace(old, new, 1), encoding="utf-8")

cli = CLI.read_text(encoding="utf-8")
if 'from typing import Any\n' not in cli:
    raise SystemExit("CLI Any import marker missing")
CLI.write_text(cli.replace('from typing import Any\n', '', 1), encoding="utf-8")

witness = WITNESS.read_text(encoding="utf-8")
if 'from typing import Any\n' not in witness:
    raise SystemExit("witness Any import marker missing")
witness = witness.replace('from typing import Any\n', '', 1)
old_noqa = '            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)  # noqa: PTH104\n'
new_noqa = '            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)\n'
if witness.count(old_noqa) != 1:
    raise SystemExit(f"witness noqa marker count: {witness.count(old_noqa)}")
WITNESS.write_text(witness.replace(old_noqa, new_noqa, 1), encoding="utf-8")
