from __future__ import annotations

from pathlib import Path

mount_path = Path("tests/test_mesc_mrl_0801_hf_mount_rollback_v1.py")
mount = mount_path.read_text(encoding="utf-8")
old = '''    root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
    try:
        with pytest.raises(OSError):
            subject._rollback_created_files(
                root_fd=root_fd,
                acquired=(_acquired_file(asset),),
                pre_finalizer_entries=frozenset({asset.name}),
            )
    finally:
        os.close(root_fd)
'''
new = '''    root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
    try:
        subject._rollback_created_files(
            root_fd=root_fd,
            acquired=(_acquired_file(asset),),
            pre_finalizer_entries=frozenset({asset.name}),
        )
    finally:
        os.close(root_fd)
'''
if mount.count(old) != 1:
    raise SystemExit(f"mount nonempty rollback target count: {mount.count(old)}")
mount = mount.replace(old, new, 1)
old = '''        root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
        try:
            with pytest.raises(OSError):
                subject._rollback_created_files(
                    root_fd=root_fd,
                    acquired=(_acquired_file(asset),),
                    pre_finalizer_entries=frozenset({asset.name}),
                )
        finally:
            os.close(root_fd)
'''
new = '''        root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
        try:
            subject._rollback_created_files(
                root_fd=root_fd,
                acquired=(_acquired_file(asset),),
                pre_finalizer_entries=frozenset({asset.name}),
            )
        finally:
            os.close(root_fd)
'''
if mount.count(old) != 1:
    raise SystemExit(f"mount bind rollback target count: {mount.count(old)}")
mount_path.write_text(mount.replace(old, new, 1), encoding="utf-8")

publish_path = Path("tests/test_mesc_mrl_0801_hf_publish_v1.py")
publish = publish_path.read_text(encoding="utf-8")
old = '''    assert partial.read_bytes() == b"stale"
    assert not (tmp_path / ASSET).exists()



def test_rollback_preserves_replaced_published_target'''
new = '''    assert partial.read_bytes() == b"stale"
    assert not (tmp_path / ASSET).exists()


def test_rollback_preserves_replaced_published_target'''
if publish.count(old) != 1:
    raise SystemExit(f"publish spacing target count: {publish.count(old)}")
publish_path.write_text(publish.replace(old, new, 1), encoding="utf-8")
