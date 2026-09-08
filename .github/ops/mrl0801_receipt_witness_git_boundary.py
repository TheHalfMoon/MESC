from pathlib import Path

cli_path = Path("scripts/mesc_mrl_0801_hf_acquire.py")
test_path = Path("tests/test_mesc_mrl_0801_hf_acquire_cli.py")

cli = cli_path.read_text(encoding="utf-8")
old = '''    if root == snapshot or _is_descendant(root, snapshot):
        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
'''
new = '''    if root == snapshot or _is_descendant(root, snapshot):
        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise AcquisitionEntrypointError("receipt witness root is inside a Git work tree")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
'''
if cli.count(old) != 1:
    raise SystemExit(f"expected one CLI witness boundary match, got {cli.count(old)}")
cli_path.write_text(cli.replace(old, new, 1), encoding="utf-8")

test = test_path.read_text(encoding="utf-8")
anchor = '''def test_receipt_atomic_publication_capability_is_verified_before_use(
'''
addition = '''def test_receipt_witness_root_inside_other_git_work_tree_is_rejected(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    other_repo = tmp_path / "other-repo"
    other_repo.mkdir()
    (other_repo / ".git").mkdir()
    witness_dir = other_repo / "receipt-witnesses"
    witness_dir.mkdir()

    with pytest.raises(cli.AcquisitionEntrypointError, match="Git work tree"):
        cli._require_external_witness_root(
            path=witness_dir,
            repository_root=root,
            snapshot_root=snapshot,
        )


'''
if test.count(anchor) != 1:
    raise SystemExit(f"expected one test insertion anchor, got {test.count(anchor)}")
test_path.write_text(test.replace(anchor, addition + anchor, 1), encoding="utf-8")
