from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected exactly once")
    return text.replace(old, new, 1)


source = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
source_text = source.read_text(encoding="utf-8")
source_text = replace_once(
    source_text,
    "            if type(value) is not Path:\n",
    "            if not isinstance(value, Path):\n",
    label="constructor path runtime type guard",
)
source_text = replace_once(
    source_text,
    "    if type(path) is not Path:\n",
    "    if not isinstance(path, Path):\n",
    label="corpus path runtime type guard",
)
source_text = replace_once(
    source_text,
    "    if type(repository_root) is not Path:\n",
    "    if not isinstance(repository_root, Path):\n",
    label="repository root runtime type guard",
)
source.write_text(source_text, encoding="utf-8", newline="\n")

tests = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
test_text = tests.read_text(encoding="utf-8")
test_text = replace_once(
    test_text,
    "from pathlib import Path\n",
    "from pathlib import Path\nfrom typing import cast\n",
    label="cast import",
)
marker = (
    "\n\ndef test_success_runs_all_seeds_and_atomically_publishes_namespaces("
    "tmp_path: Path) -> None:\n"
)
regression = '''


def test_constructor_accepts_platform_path_and_rejects_non_path(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, _ = _backend(tmp_path, runtime)
    assert isinstance(backend, HfLocalSftBackend)

    recipe = _recipe()
    with pytest.raises(
        HfLocalSftBackendError,
        match=r"model_root must be an exact pathlib[.]Path",
    ):
        HfLocalSftBackend(
            recipe=recipe,
            model_root=cast(Path, "not-a-path"),
            corpus_path=tmp_path / "corpus.jsonl",
            repository_root=tmp_path / "repo",
            runtime=runtime,
        )
'''
test_text = replace_once(
    test_text,
    marker,
    regression + marker,
    label="path runtime regression test",
)
tests.write_text(test_text, encoding="utf-8", newline="\n")
