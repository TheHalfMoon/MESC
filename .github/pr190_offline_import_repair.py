from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected exactly once")
    return text.replace(old, new, 1)


source = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
source_text = source.read_text(encoding="utf-8")
old_builder = '''    modules: dict[str, Any] = {}
    try:
        for name in _REQUIRED_RUNTIME_MODULES:
            modules[name] = module_loader(name)
    except Exception as exc:
        raise HfLocalSftBackendError(
            "required Hugging Face SFT runtime package is unavailable"
        ) from exc
    return _RealHfLocalSftRuntime(modules, version_loader=version_loader)
'''
new_builder = '''    modules: dict[str, Any] = {}
    with _offline_hf_environment():
        try:
            for name in _REQUIRED_RUNTIME_MODULES:
                modules[name] = module_loader(name)
        except Exception as exc:
            raise HfLocalSftBackendError(
                "required Hugging Face SFT runtime package is unavailable"
            ) from exc
    return _RealHfLocalSftRuntime(modules, version_loader=version_loader)
'''
source_text = replace_once(
    source_text,
    old_builder,
    new_builder,
    label="runtime import offline context",
)
source.write_text(source_text, encoding="utf-8", newline="\n")

tests = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
test_text = tests.read_text(encoding="utf-8")
test_text = replace_once(
    test_text,
    "import json\n",
    "import json\nimport os\n",
    label="os import",
)
old_test = '''def test_runtime_builder_imports_training_stack_only_when_called() -> None:
    imported: list[str] = []

    class _Cuda:
        pass

    class _Torch:
        cuda = _Cuda()

    modules = {
        "torch": _Torch(),
        "transformers": object(),
        "trl": object(),
        "peft": object(),
        "datasets": object(),
        "accelerate": object(),
    }

    def loader(name: str) -> object:
        imported.append(name)
        return modules[name]

    runtime = build_hf_local_sft_runtime(
        module_loader=loader,
        version_loader=lambda name: f"{name}-fixture",
    )

    assert runtime is not None
    assert imported == ["torch", "transformers", "trl", "peft", "datasets", "accelerate"]
'''
new_test = '''def test_runtime_builder_imports_training_stack_only_when_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported: list[str] = []
    offline_env = {
        "HF_DATASETS_OFFLINE": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "WANDB_DISABLED": "true",
    }
    for name in offline_env:
        monkeypatch.delenv(name, raising=False)

    class _Cuda:
        pass

    class _Torch:
        cuda = _Cuda()

    modules = {
        "torch": _Torch(),
        "transformers": object(),
        "trl": object(),
        "peft": object(),
        "datasets": object(),
        "accelerate": object(),
    }

    def loader(name: str) -> object:
        assert {key: os.environ.get(key) for key in offline_env} == offline_env
        imported.append(name)
        return modules[name]

    runtime = build_hf_local_sft_runtime(
        module_loader=loader,
        version_loader=lambda name: f"{name}-fixture",
    )

    assert runtime is not None
    assert imported == ["torch", "transformers", "trl", "peft", "datasets", "accelerate"]
    assert all(os.environ.get(name) is None for name in offline_env)
'''
test_text = replace_once(
    test_text,
    old_test,
    new_test,
    label="runtime import offline regression",
)
tests.write_text(test_text, encoding="utf-8", newline="\n")
