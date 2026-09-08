from __future__ import annotations

import sys
from pathlib import Path


def replace_exact(path: Path, old: str, new: str, *, count: int = 1) -> None:
    text = path.read_text(encoding="utf-8")
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} occurrence(s), found {actual}")
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def main(root: Path) -> None:
    source = root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"
    cli = root / "scripts/mesc_mrl_0801_hf_acquire.py"
    acquisition_tests = root / "tests/test_mesc_mrl_0801_hf_acquisition_v1.py"
    cli_tests = root / "tests/test_mesc_mrl_0801_hf_acquire_cli.py"
    spec = root / "specs/mesc-experiment-0/mrl-0801-hf-acquisition-provenance-v1.md"

    replace_exact(source, "import ctypes\n", "import contextlib\nimport ctypes\n")
    replace_exact(source, "import re\n", "import re\nimport secrets\n")
    replace_exact(
        source,
        "    required_dir_fd = (os.open, os.stat)\n",
        "    required_dir_fd = (os.mkdir, os.open, os.rmdir, os.stat, os.unlink)\n",
    )
    replace_exact(
        source,
        "        probe = _open_unnamed_temp_file(root_fd=descriptor)\n        os.close(probe)\n",
        "        _probe_atomic_descriptor_publication(root_fd=descriptor)\n",
    )
    source_helper = '''\n\ndef _probe_atomic_descriptor_publication(*, root_fd: int) -> None:\n    \"\"\"Prove unnamed-file atomic publication on this filesystem before network access.\"\"\"\n    probe_dir_name = f\".mrl-0801-publication-probe-{secrets.token_hex(16)}\"\n    probe_fd: int | None = None\n    source_fd: int | None = None\n    created_dir = False\n    published = False\n    try:\n        os.mkdir(probe_dir_name, 0o700, dir_fd=root_fd)\n        created_dir = True\n        probe_fd = os.open(\n            probe_dir_name,\n            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,\n            dir_fd=root_fd,\n        )\n        probe_directory = os.fstat(probe_fd)\n        if not stat.S_ISDIR(probe_directory.st_mode):\n            raise MRL0801HfAcquisitionError(\n                \"atomic publication capability probe did not bind a directory\"\n            )\n        source_fd = _open_unnamed_temp_file(root_fd=probe_fd)\n        source = os.fstat(source_fd)\n        if not stat.S_ISREG(source.st_mode):\n            raise MRL0801HfAcquisitionError(\n                \"atomic publication capability probe did not create a regular file\"\n            )\n        _publish_open_descriptor_no_replace(\n            source_fd=source_fd,\n            root_fd=probe_fd,\n            target_name=\"probe\",\n        )\n        published = True\n        linked = _descriptor_entry_stat(root_fd=probe_fd, name=\"probe\")\n        if (\n            linked is None\n            or not stat.S_ISREG(linked.st_mode)\n            or _stat_descriptor_identity(linked) != _stat_descriptor_identity(source)\n        ):\n            raise MRL0801HfAcquisitionError(\n                \"atomic publication capability probe produced an invalid identity\"\n            )\n        os.unlink(\"probe\", dir_fd=probe_fd)\n        published = False\n        os.close(source_fd)\n        source_fd = None\n        os.close(probe_fd)\n        probe_fd = None\n        os.rmdir(probe_dir_name, dir_fd=root_fd)\n        created_dir = False\n    except MRL0801HfAcquisitionError:\n        raise\n    except OSError:\n        raise MRL0801HfAcquisitionError(\n            \"atomic descriptor publication capability probe failed safely\"\n        ) from None\n    finally:\n        if source_fd is not None:\n            with contextlib.suppress(OSError):\n                os.close(source_fd)\n        if probe_fd is not None:\n            if published:\n                with contextlib.suppress(OSError):\n                    os.unlink(\"probe\", dir_fd=probe_fd)\n            with contextlib.suppress(OSError):\n                os.close(probe_fd)\n        if created_dir:\n            with contextlib.suppress(OSError):\n                os.rmdir(probe_dir_name, dir_fd=root_fd)\n'''
    replace_exact(source, "\n\ndef _acquire_one_file(\n", source_helper + "\n\ndef _acquire_one_file(\n")

    replace_exact(cli, "import os\n", "import os\nimport secrets\n")
    replace_exact(
        cli,
        "    required_dir_fd = (os.open, os.stat)\n",
        "    required_dir_fd = (os.mkdir, os.open, os.rmdir, os.stat, os.unlink)\n",
    )
    replace_exact(
        cli,
        '''        try:\n            probe = os.open(\n                \".\",\n                os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,\n                0o600,\n                dir_fd=output.descriptor,\n            )\n        except OSError:\n            raise AcquisitionEntrypointError(\n                \"unnamed receipt publication is unsupported on this filesystem\"\n            ) from None\n        os.close(probe)\n        return output\n''',
        '''        _probe_receipt_atomic_publication(output)\n        _require_bound_output_parent_identity(output)\n        return output\n''',
    )
    cli_helper = '''\n\ndef _probe_receipt_atomic_publication(output: _BoundReceiptOutput) -> None:\n    \"\"\"Prove receipt atomic publication on the bound filesystem before acquisition.\"\"\"\n    _require_bound_output_parent_identity(output)\n    probe_dir_name = f\".mrl-0801-receipt-probe-{secrets.token_hex(16)}\"\n    probe_fd: int | None = None\n    source_fd: int | None = None\n    created_dir = False\n    published = False\n    try:\n        os.mkdir(probe_dir_name, 0o700, dir_fd=output.descriptor)\n        created_dir = True\n        probe_fd = os.open(\n            probe_dir_name,\n            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,\n            dir_fd=output.descriptor,\n        )\n        probe_directory = os.fstat(probe_fd)\n        if not stat.S_ISDIR(probe_directory.st_mode):\n            raise AcquisitionEntrypointError(\n                \"atomic receipt publication probe did not bind a directory\"\n            )\n        try:\n            source_fd = os.open(\n                \".\",\n                os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,\n                0o600,\n                dir_fd=probe_fd,\n            )\n        except OSError:\n            raise AcquisitionEntrypointError(\n                \"unnamed receipt publication is unsupported on this filesystem\"\n            ) from None\n        source = os.fstat(source_fd)\n        if not stat.S_ISREG(source.st_mode):\n            raise AcquisitionEntrypointError(\n                \"atomic receipt publication probe did not create a regular file\"\n            )\n        probe_output = _BoundReceiptOutput(\n            path=output.parent_path / probe_dir_name / \"probe\",\n            parent_path=output.parent_path / probe_dir_name,\n            descriptor=probe_fd,\n            device=probe_directory.st_dev,\n            inode=probe_directory.st_ino,\n            name=\"probe\",\n        )\n        _publish_open_descriptor_no_replace(source_fd=source_fd, output=probe_output)\n        published = True\n        linked = _descriptor_output_stat(probe_output)\n        if (\n            linked is None\n            or not stat.S_ISREG(linked.st_mode)\n            or _stat_identity(linked) != _stat_identity(source)\n        ):\n            raise AcquisitionEntrypointError(\n                \"atomic receipt publication probe produced an invalid identity\"\n            )\n        os.unlink(\"probe\", dir_fd=probe_fd)\n        published = False\n        os.close(source_fd)\n        source_fd = None\n        os.close(probe_fd)\n        probe_fd = None\n        os.rmdir(probe_dir_name, dir_fd=output.descriptor)\n        created_dir = False\n        _require_bound_output_parent_identity(output)\n    except AcquisitionEntrypointError:\n        raise\n    except OSError:\n        raise AcquisitionEntrypointError(\n            \"atomic receipt publication capability probe failed safely\"\n        ) from None\n    finally:\n        if source_fd is not None:\n            with contextlib.suppress(OSError):\n                os.close(source_fd)\n        if probe_fd is not None:\n            if published:\n                with contextlib.suppress(OSError):\n                    os.unlink(\"probe\", dir_fd=probe_fd)\n            with contextlib.suppress(OSError):\n                os.close(probe_fd)\n        if created_dir:\n            with contextlib.suppress(OSError):\n                os.rmdir(probe_dir_name, dir_fd=output.descriptor)\n'''
    replace_exact(cli, "\n\ndef _write_exact_new(output: _BoundReceiptOutput, data: bytes) -> None:\n", cli_helper + "\n\ndef _write_exact_new(output: _BoundReceiptOutput, data: bytes) -> None:\n")

    replace_exact(
        acquisition_tests,
        '''    assert [item.name for item in destination.iterdir()] == [\"unexpected.txt\"]\n\n\ndef test_finalizer_extra_entry_is_rejected_and_snapshot_rollback_preserves_unbound_entry(\n''',
        '''    assert {item.name for item in destination.iterdir()} == {*FILES, \"unexpected.txt\"}\n\n\ndef test_finalizer_extra_entry_is_rejected_and_residue_is_retained(\n''',
    )
    replace_exact(
        acquisition_tests,
        '''    assert [item.name for item in destination.iterdir()] == [\"unexpected.txt\"]\n\n\ndef test_finalizer_asset_mutation_is_rejected_and_rolled_back(\n''',
        '''    assert {item.name for item in destination.iterdir()} == {*FILES, \"unexpected.txt\"}\n\n\ndef test_finalizer_asset_mutation_is_rejected_and_residue_is_retained(\n''',
    )
    replace_exact(
        acquisition_tests,
        '''    assert list(destination.iterdir()) == []\n\n\ndef test_provenance_validation_requires_exact_receipt_types(\n''',
        '''    assert {item.name for item in destination.iterdir()} == set(FILES)\n    assert (destination / FILES[1]).read_bytes() == b\"tamper-me\"\n\n\ndef test_late_failure_residue_blocks_retry_before_transport(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    patch_environment(monkeypatch)\n    destination = tmp_path / \"assets\"\n    destination.mkdir()\n    root = fake_repo(tmp_path)\n\n    def fail_finalize(\n        _: MRL0801AssetCustodyReceipt,\n        __: subject.MRL0801HfAcquisitionProvenanceReceipt,\n    ) -> None:\n        raise OSError(\"receipt publication failed\")\n\n    with pytest.raises(OSError, match=\"receipt publication failed\"):\n        subject.acquire_mrl_0801_hf_candidate(\n            authorization=authorization(),\n            transport=FakeTransport(),\n            repository_root=root,\n            destination=destination,\n            model_id=MODEL,\n            revision=REV,\n            finalizer=fail_finalize,\n        )\n    assert {item.name for item in destination.iterdir()} == set(FILES)\n\n    retry_transport = FakeTransport()\n    with pytest.raises(subject.MRL0801HfAcquisitionError, match=\"empty real directory\"):\n        subject.acquire_mrl_0801_hf_candidate(\n            authorization=authorization(),\n            transport=retry_transport,\n            repository_root=root,\n            destination=destination,\n            model_id=MODEL,\n            revision=REV,\n        )\n    assert retry_transport.calls == {}\n    assert retry_transport.downloads == []\n\n\ndef test_provenance_validation_requires_exact_receipt_types(\n''',
    )
    replace_exact(
        acquisition_tests,
        '''def test_destination_replacement_cannot_redirect_writes(\n''',
        '''def test_atomic_publication_capability_failure_precedes_transport(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    patch_environment(monkeypatch)\n    destination = tmp_path / \"assets\"\n    destination.mkdir()\n    transport = FakeTransport()\n\n    def unsupported_publication(**_: object) -> None:\n        raise subject.MRL0801HfAcquisitionError(\n            \"atomic descriptor publication is unsupported on this filesystem\"\n        )\n\n    monkeypatch.setattr(subject, \"_publish_open_descriptor_no_replace\", unsupported_publication)\n    with pytest.raises(subject.MRL0801HfAcquisitionError, match=\"atomic descriptor publication\"):\n        subject.acquire_mrl_0801_hf_candidate(\n            authorization=authorization(),\n            transport=transport,\n            repository_root=fake_repo(tmp_path),\n            destination=destination,\n            model_id=MODEL,\n            revision=REV,\n        )\n    assert transport.calls == {}\n    assert transport.downloads == []\n    assert list(destination.iterdir()) == []\n\n\ndef test_destination_replacement_cannot_redirect_writes(\n''',
    )

    replace_exact(
        cli_tests,
        '''def test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:\n''',
        '''def test_receipt_atomic_publication_capability_is_verified_before_binding(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    cli = load_cli()\n    root = repo(tmp_path)\n    snapshot = tmp_path / \"snapshot\"\n    snapshot.mkdir()\n    receipt = tmp_path / \"receipts/receipt.json\"\n    receipt.parent.mkdir()\n\n    def unsupported_publication(**_: object) -> None:\n        raise cli.AcquisitionEntrypointError(\n            \"atomic receipt publication is unsupported on this filesystem\"\n        )\n\n    monkeypatch.setattr(cli, \"_publish_open_descriptor_no_replace\", unsupported_publication)\n    with pytest.raises(cli.AcquisitionEntrypointError, match=\"atomic receipt publication\"):\n        cli._require_external_new_output(\n            path=receipt,\n            repository_root=root,\n            snapshot_root=snapshot,\n        )\n    assert list(receipt.parent.iterdir()) == []\n    assert not receipt.exists()\n\n\ndef test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:\n''',
    )

    replace_exact(
        spec,
        '''Before any model byte download:\n\n1. retrieve metadata for every and only authorized file;\n2. require every metadata record to resolve to the exact authorized revision;\n3. compute the exact allowlist byte count;\n4. execute the canonical storage-capacity preflight.\n''',
        '''Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the bound destination filesystem. The CLI performs the same proof for each bound receipt-parent filesystem before acquisition begins. A successful `O_TMPFILE` open or an exported `linkat` symbol alone is insufficient; the capability probe must successfully publish an unnamed file with `linkat(..., AT_EMPTY_PATH)`, verify the linked identity, and restore its isolated probe directory.\n\nAfter that capability proof and before any model byte download:\n\n1. retrieve metadata for every and only authorized file;\n2. require every metadata record to resolve to the exact authorized revision;\n3. compute the exact allowlist byte count;\n4. execute the canonical storage-capacity preflight.\n''',
    )
    replace_exact(
        spec,
        '''The executor never overwrites existing asset files. Every file is streamed into an unnamed same-filesystem `O_TMPFILE` opened through the bound destination descriptor, fully hashed and size-checked, then atomically published from that still-open file descriptor with `linkat(..., AT_EMPTY_PATH)`. If the primitive or filesystem support is unavailable, acquisition fails closed. If a racing target appears, the atomic link fails without modifying that target. Before publication, failure cleanup is descriptor close only because the temporary file has no directory entry.\n''',
        '''The executor never overwrites existing asset files. Before any remote metadata request, it performs an isolated same-filesystem capability probe through the bound destination descriptor that creates an unnamed `O_TMPFILE`, successfully publishes it with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, and removes only the private probe namespace before continuing. Every authorized file is then streamed into an unnamed same-filesystem `O_TMPFILE` opened through the bound destination descriptor, fully hashed and size-checked, then atomically published from that still-open file descriptor with `linkat(..., AT_EMPTY_PATH)`. If the primitive or filesystem support is unavailable, acquisition fails closed before network access. If a racing target appears, the atomic link fails without modifying that target. Before publication, failure cleanup is descriptor close only because the temporary file has no directory entry.\n''',
    )
    replace_exact(
        spec,
        '''Receipt publication by the CLI is supplied as the acquisition transaction finalizer and uses the same unnamed-file pattern in each pre-bound external receipt parent. Receipt bytes are written and fsynced before one atomic descriptor publication to the final name. The CLI performs no automatic receipt unlink cleanup.\n''',
        '''Receipt publication by the CLI is supplied as the acquisition transaction finalizer and uses the same unnamed-file pattern in each pre-bound external receipt parent. Before acquisition begins, every bound receipt parent must pass the same successful same-filesystem `O_TMPFILE` plus `linkat(..., AT_EMPTY_PATH)` capability proof. Receipt bytes are written and fsynced before one atomic descriptor publication to the final name. The CLI performs no automatic receipt unlink cleanup.\n''',
    )

    for path in (source, cli, acquisition_tests, cli_tests, spec):
        text = path.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            raise SystemExit(f"{path}: missing terminal newline")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: pr390_capability_patcher.py <repo-root>")
    main(Path(sys.argv[1]).resolve())
