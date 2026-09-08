from pathlib import Path

SCRIPT = Path("scripts/mesc_mrl_0801_hf_acquire.py")
TEST = Path("tests/test_mesc_mrl_0801_hf_acquire_cli.py")

script = SCRIPT.read_text(encoding="utf-8")
old = '''    if root == snapshot or _is_descendant(root, snapshot):\n        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")\n    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC\n'''
new = '''    if root == snapshot or _is_descendant(root, snapshot):\n        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")\n    for ancestor in (root, *root.parents):\n        if (ancestor / ".git").exists():\n            raise AcquisitionEntrypointError("receipt witness root is inside a Git work tree")\n    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC\n'''
if script.count(old) != 1:
    raise SystemExit(f"script marker count: {script.count(old)}")
script = script.replace(old, new, 1)

marker = '''def test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:\n'''
addition = '''def test_receipt_witness_root_inside_foreign_git_work_tree_is_rejected(tmp_path: Path) -> None:\n    cli = load_cli()\n    root = repo(tmp_path)\n    snapshot = tmp_path / "snapshot"\n    snapshot.mkdir()\n    foreign = tmp_path / "foreign-repo"\n    foreign.mkdir()\n    (foreign / ".git").mkdir()\n    witness = foreign / "witnesses"\n    witness.mkdir()\n\n    with pytest.raises(cli.AcquisitionEntrypointError, match="Git work tree"):\n        cli._require_external_witness_root(\n            path=witness,\n            repository_root=root,\n            snapshot_root=snapshot,\n        )\n\n\n'''
if TEST.read_text(encoding="utf-8").count(marker) != 1:
    raise SystemExit("test marker mismatch")
test = TEST.read_text(encoding="utf-8").replace(marker, addition + marker, 1)

SCRIPT.write_text(script, encoding="utf-8")
TEST.write_text(test, encoding="utf-8")
