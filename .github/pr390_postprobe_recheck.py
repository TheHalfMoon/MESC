from pathlib import Path
import sys


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one replacement site, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main(root: Path) -> None:
    source = root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"
    cli = root / "scripts/mesc_mrl_0801_hf_acquire.py"
    tests = root / "tests/test_mesc_mrl_0801_hf_acquisition_v1.py"
    cli_tests = root / "tests/test_mesc_mrl_0801_hf_acquire_cli.py"

    replace_exact(
        source,
        '''        _probe_atomic_descriptor_publication(root_fd=descriptor)\n        return _DestinationDirectory(\n''',
        '''        _probe_atomic_descriptor_publication(root_fd=descriptor)\n        if os.listdir(descriptor):  # noqa: PTH208 -- descriptor-relative listing is required\n            raise MRL0801HfAcquisitionError(\n                "acquisition destination changed during atomic publication preflight"\n            )\n        return _DestinationDirectory(\n''',
    )
    replace_exact(
        cli,
        '''        _probe_receipt_atomic_publication(output)\n        _require_bound_output_parent_identity(output)\n        return output\n''',
        '''        _probe_receipt_atomic_publication(output)\n        _require_bound_output_parent_identity(output)\n        if _descriptor_output_stat(output) is not None:\n            raise AcquisitionEntrypointError(\n                "receipt output appeared during atomic publication preflight"\n            )\n        return output\n''',
    )
    replace_exact(
        tests,
        '''def test_destination_replacement_cannot_redirect_writes(\n''',
        '''def test_destination_race_during_capability_probe_blocks_before_transport(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    patch_environment(monkeypatch)\n    destination = tmp_path / "assets"\n    destination.mkdir()\n    transport = FakeTransport()\n\n    def race(*, root_fd: int) -> None:\n        descriptor = os.open(\n            "foreign.txt",\n            os.O_WRONLY | os.O_CREAT | os.O_EXCL,\n            0o600,\n            dir_fd=root_fd,\n        )\n        os.close(descriptor)\n\n    monkeypatch.setattr(subject, "_probe_atomic_descriptor_publication", race)\n    with pytest.raises(subject.MRL0801HfAcquisitionError, match="changed during atomic"):\n        subject.acquire_mrl_0801_hf_candidate(\n            authorization=authorization(),\n            transport=transport,\n            repository_root=fake_repo(tmp_path),\n            destination=destination,\n            model_id=MODEL,\n            revision=REV,\n        )\n    assert transport.calls == {}\n    assert transport.downloads == []\n    assert (destination / "foreign.txt").exists()\n\n\ndef test_destination_replacement_cannot_redirect_writes(\n''',
    )
    replace_exact(
        tests,
        '''import json\n''',
        '''import json\nimport os\n''',
    )
    replace_exact(
        cli_tests,
        '''def test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:\n''',
        '''def test_receipt_target_race_during_capability_probe_is_rejected(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    cli = load_cli()\n    root = repo(tmp_path)\n    snapshot = tmp_path / "snapshot"\n    snapshot.mkdir()\n    receipt = tmp_path / "receipts/receipt.json"\n    receipt.parent.mkdir()\n\n    def race(output: object) -> None:\n        descriptor = getattr(output, "descriptor")\n        name = getattr(output, "name")\n        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=descriptor)\n        os.close(fd)\n\n    monkeypatch.setattr(cli, "_probe_receipt_atomic_publication", race)\n    with pytest.raises(cli.AcquisitionEntrypointError, match="appeared during atomic"):\n        cli._require_external_new_output(\n            path=receipt,\n            repository_root=root,\n            snapshot_root=snapshot,\n        )\n    assert receipt.exists()\n\n\ndef test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:\n''',
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: pr390_postprobe_recheck.py <repo-root>")
    main(Path(sys.argv[1]).resolve())
