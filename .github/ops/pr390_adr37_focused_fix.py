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
acq = acq.replace(old, new, 1)
old_residue = '    assert list(original.iterdir()) == []\n    assert (destination / "sentinel.txt").read_text(encoding="utf-8") == "replacement"\n'
new_residue = '    assert {item.name for item in original.iterdir()} == set(FILES)\n    assert (destination / "sentinel.txt").read_text(encoding="utf-8") == "replacement"\n'
if acq.count(old_residue) != 1:
    raise SystemExit(f"destination retained-residue marker count: {acq.count(old_residue)}")
ACQ.write_text(acq.replace(old_residue, new_residue, 1), encoding="utf-8")

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
witness = witness.replace(old_noqa, new_noqa, 1)
old_device = '''    real_fstat = os.fstat

    def mismatched(fd: int) -> os.stat_result:
        observed = real_fstat(fd)
        if fd == destination_root.descriptor:
            return observed
        values = list(observed)
        values[2] = observed.st_dev + 1
        return os.stat_result(values)

    monkeypatch.setattr(subject.os, "fstat", mismatched)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="transaction filesystem"):
            subject._require_external_witness_root(
                witness_root=witness_dir,
                repository_root=repository,
                transaction_root=destination_root,
            )
    finally:
        os.close(destination_root.descriptor)
'''
new_device = '''    witness_root = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    real_fstat = os.fstat

    def mismatched(fd: int) -> os.stat_result:
        observed = real_fstat(fd)
        if not stat.S_ISREG(observed.st_mode):
            return observed
        values = list(observed)
        values[2] = observed.st_dev + 1
        return os.stat_result(values)

    monkeypatch.setattr(subject.os, "fstat", mismatched)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="transaction filesystem"):
            subject._probe_atomic_descriptor_publication(
                source_root_fd=destination_root.descriptor,
                witness_root=witness_root,
            )
    finally:
        os.close(witness_root.descriptor)
        os.close(destination_root.descriptor)
'''
if witness.count(old_device) != 1:
    raise SystemExit(f"device mismatch marker count: {witness.count(old_device)}")
witness = witness.replace(old_device, new_device, 1)
if 'import stat\n' not in witness:
    witness = witness.replace('import os\n', 'import os\nimport stat\n', 1)
WITNESS.write_text(witness, encoding="utf-8")
