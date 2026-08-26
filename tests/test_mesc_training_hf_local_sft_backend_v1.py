"""Tests for the local-only Hugging Face SFT training backend."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

import medscale.mesc._training_hf_local_sft_backend_v1 as backend_module
from medscale.mesc._training_executor_v1 import TrainingExecutionManifest
from medscale.mesc._training_hf_local_sft_backend_v1 import (
    HfLocalSftBackend,
    HfLocalSftBackendError,
    HfLocalSftExecutionProfile,
    HfSftRuntimeResult,
    build_hf_local_sft_runtime,
)
from medscale.mesc._training_hf_safetensors_identity_v1 import (
    identify_hf_safetensors_artifact,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe

_GIT_A = "1" * 40
_GIT_B = "2" * 40
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_DATASET_SHA = "c" * 64


class _FakeRuntime:
    def __init__(self, *, fail_seed: int | None = None) -> None:
        self.calls: list[int] = []
        self.fail_seed = fail_seed

    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult:
        assert model_root.is_dir()
        assert records
        assert recipe.recipe_id
        assert profile.max_length == 2048
        self.calls.append(seed)
        if seed == self.fail_seed:
            raise RuntimeError("fixture training failure")
        (output_dir / "adapter_model.safetensors").write_bytes(f"adapter-{seed}".encode())
        (output_dir / "adapter_config.json").write_text(
            '{"peft_type":"LORA"}\n',
            encoding="utf-8",
        )
        return HfSftRuntimeResult(
            metrics=(("train_loss", float(seed) / 100.0),),
            packages=(("trl", "fixture"),),
        )


class _InterruptRuntime(_FakeRuntime):
    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult:
        result = super().train_seed(
            model_root=model_root,
            records=records,
            recipe=recipe,
            seed=seed,
            output_dir=output_dir,
            profile=profile,
        )
        del result
        raise KeyboardInterrupt("fixture interrupt")


class _HardlinkRuntime(_FakeRuntime):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source

    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult:
        assert model_root.is_dir()
        assert records
        assert recipe.recipe_id
        assert profile.max_length == 2048
        self.calls.append(seed)
        (output_dir / "adapter_model.safetensors").hardlink_to(self.source)
        (output_dir / "adapter_config.json").write_text(
            '{"peft_type":"LORA"}\n',
            encoding="utf-8",
        )
        return HfSftRuntimeResult(
            metrics=(("train_loss", float(seed) / 100.0),),
            packages=(("trl", "fixture"),),
        )


def _recipe(*, model_id: str = "example/model") -> TrainingRecipe:
    return TrainingRecipe(
        base=ModelRef(
            model_id=model_id,
            revision=_GIT_A,
            quantization="nf4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef(
            name="mesc-evidence-sft-v1",
            version="1.0.0",
            content_sha256=_DATASET_SHA,
        ),
        seed=42,
        max_steps=2,
    )


def _corpus_raw() -> bytes:
    records = (
        {
            "completion": {"role": "assistant", "content": "Answer one."},
            "example_id": "ex-1",
            "prompt": [
                {"role": "system", "content": "Use evidence."},
                {"role": "user", "content": "Question one?"},
            ],
        },
        {
            "completion": {"role": "assistant", "content": "Answer two."},
            "example_id": "ex-2",
            "prompt": [{"role": "user", "content": "Question two?"}],
        },
    )
    return b"".join(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n"
        for record in records
    )


def _model(root: Path) -> str:
    root.mkdir()
    (root / "model.safetensors").write_bytes(b"fixture-model-weights")
    return identify_hf_safetensors_artifact(
        model_root=root,
        model_id="example/model",
        revision=_GIT_A,
    ).weights_sha256


def _manifest(
    *,
    weights_sha256: str,
    corpus_raw: bytes,
    recipe: TrainingRecipe,
) -> TrainingExecutionManifest:
    return TrainingExecutionManifest(
        role="compact",
        launch_plan_sha256=_SHA_A,
        run_plan_sha256=_SHA_B,
        readiness_manifest_sha256="d" * 64,
        corpus_binding_sha256="e" * 64,
        local_asset_attestation_sha256="f" * 64,
        environment_sha256="0" * 64,
        experiment_id="mesc-t6-compact-sft",
        model_id="example/model",
        revision=_GIT_A,
        weights_sha256=weights_sha256,
        training_dataset_sha256=_DATASET_SHA,
        recipe_id=recipe.recipe_id,
        seeds=(17, 42),
        runner_class="local",
        python_version="3.12",
        os_name="linux",
        gpu_model="fixture-gpu",
        repository_sha=_GIT_A,
        repository_tree=_GIT_B,
        dependency_lock_sha256="3" * 64,
        runtime_qualification_sha256="4" * 64,
        training_authorization_receipt_sha256="5" * 64,
        canonical_corpus_sha256=hashlib.sha256(corpus_raw).hexdigest(),
        canonical_corpus_byte_count=len(corpus_raw),
        model_verifier_receipt_sha256="6" * 64,
        result_namespaces=(
            "experiments/mesc-t6-compact-sft/outputs",
            "experiments/mesc-t6-compact-sft/results",
        ),
    )


def _backend(
    tmp_path: Path,
    runtime: _FakeRuntime,
) -> tuple[HfLocalSftBackend, TrainingExecutionManifest]:
    model_root = tmp_path / "model"
    weights = _model(model_root)
    corpus_raw = _corpus_raw()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(corpus_raw)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    recipe = _recipe()
    manifest = _manifest(weights_sha256=weights, corpus_raw=corpus_raw, recipe=recipe)
    backend = HfLocalSftBackend(
        recipe=recipe,
        model_root=model_root,
        corpus_path=corpus_path,
        repository_root=repository_root,
        runtime=runtime,
    )
    return backend, manifest


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


def test_success_runs_all_seeds_and_atomically_publishes_namespaces(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "SUCCEEDED"
    assert runtime.calls == [17, 42]
    assert result.failure_reason is None
    paths = tuple(item.path for item in result.artifacts)
    assert "experiments/mesc-t6-compact-sft/results/training-summary.json" in paths
    assert any(path.endswith("seed-17/adapter_model.safetensors") for path in paths)
    assert any(path.endswith("seed-42/adapter_model.safetensors") for path in paths)
    final_root = tmp_path / "repo" / "experiments" / "mesc-t6-compact-sft"
    assert (final_root / "outputs").is_dir()
    assert (final_root / "results").is_dir()
    summary = json.loads((final_root / "results" / "training-summary.json").read_text())
    assert summary["disposition"] == "SUCCEEDED"
    assert summary["started_at"] == result.started_at
    assert "finished_at" not in summary
    assert summary["publication_ready_at"] >= result.started_at
    assert result.finished_at >= summary["publication_ready_at"]
    assert summary["result_parent"] == "experiments/mesc-t6-compact-sft"
    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))


def test_publication_race_never_overwrites_existing_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    final_root = tmp_path / "repo" / "experiments" / "mesc-t6-compact-sft"
    original_publish = backend_module._rename_no_replace

    def raced_publish(
        *,
        source_name: str,
        destination_name: str,
        source_dir_fd: int,
        destination_dir_fd: int,
    ) -> None:
        final_root.mkdir(parents=True)
        original_publish(
            source_name=source_name,
            destination_name=destination_name,
            source_dir_fd=source_dir_fd,
            destination_dir_fd=destination_dir_fd,
        )

    monkeypatch.setattr(backend_module, "_rename_no_replace", raced_publish)
    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == [17, 42]
    assert result.artifacts == ()
    assert "appeared during publication" in (result.failure_reason or "")
    assert final_root.is_dir()
    assert not tuple(final_root.iterdir())
    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))


def test_runtime_failure_returns_failed_without_canonical_artifacts(tmp_path: Path) -> None:
    runtime = _FakeRuntime(fail_seed=42)
    backend, manifest = _backend(tmp_path, runtime)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == [17, 42]
    assert result.artifacts == ()
    assert result.failure_reason is not None
    assert not (tmp_path / "repo" / "experiments" / "mesc-t6-compact-sft").exists()


def test_interrupt_cleans_staging_and_reraises(tmp_path: Path) -> None:
    runtime = _InterruptRuntime()
    backend, manifest = _backend(tmp_path, runtime)

    with pytest.raises(KeyboardInterrupt, match="fixture interrupt"):
        backend.execute(manifest=manifest)

    repository_root = tmp_path / "repo"
    assert runtime.calls == [17]
    assert not (repository_root / "experiments" / "mesc-t6-compact-sft").exists()
    assert not tuple(repository_root.glob(".mesc-t6-compact-sft.mesc-sft-*"))


def test_symlinked_publication_ancestor_fails_before_runtime(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    repository_root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (repository_root / "experiments").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this platform")

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "symlink" in (result.failure_reason or "")
    assert not (outside / "mesc-t6-compact-sft").exists()


def test_hardlinked_runtime_output_fails_closed(tmp_path: Path) -> None:
    external = tmp_path / "external-adapter.safetensors"
    external.write_bytes(b"external-adapter")
    runtime = _HardlinkRuntime(external)
    backend, manifest = _backend(tmp_path, runtime)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == [17, 42]
    assert result.artifacts == ()
    assert "hard link" in (result.failure_reason or "")
    assert external.read_bytes() == b"external-adapter"
    repository_root = tmp_path / "repo"
    assert not (repository_root / "experiments" / "mesc-t6-compact-sft").exists()
    assert not tuple(repository_root.glob(".mesc-t6-compact-sft.mesc-sft-*"))


def test_model_weight_mismatch_fails_before_runtime(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    manifest = replace(manifest, weights_sha256="7" * 64)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "weights" in (result.failure_reason or "")


def test_corpus_digest_mismatch_fails_before_runtime(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    manifest = replace(manifest, canonical_corpus_sha256="8" * 64)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "corpus SHA-256" in (result.failure_reason or "")


def test_recipe_primary_seed_must_be_present_in_manifest(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    manifest = replace(manifest, seeds=(17,))

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "primary seed" in (result.failure_reason or "")


def test_existing_result_root_is_never_overwritten(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    final_root = tmp_path / "repo" / "experiments" / "mesc-t6-compact-sft"
    final_root.mkdir(parents=True)
    marker = final_root / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert marker.read_text(encoding="utf-8") == "keep"


def test_malformed_corpus_messages_fail_closed(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    model_root = tmp_path / "model"
    weights = _model(model_root)
    raw = b'{"prompt":[],"completion":{"role":"assistant","content":"x"}}\n'
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repo = tmp_path / "repo"
    repo.mkdir()
    recipe = _recipe()
    manifest = _manifest(weights_sha256=weights, corpus_raw=raw, recipe=recipe)
    backend = HfLocalSftBackend(
        recipe=recipe,
        model_root=model_root,
        corpus_path=corpus_path,
        repository_root=repo,
        runtime=runtime,
    )

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "prompt" in (result.failure_reason or "")


def test_qlora_requires_exact_nf4_identity(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    model_root = tmp_path / "model"
    weights = _model(model_root)
    raw = _corpus_raw()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repo = tmp_path / "repo"
    repo.mkdir()
    recipe = TrainingRecipe(
        base=ModelRef(
            model_id="example/model",
            revision=_GIT_A,
            quantization="int4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef("mesc-evidence-sft-v1", "1.0.0", _DATASET_SHA),
        seed=42,
        max_steps=2,
    )
    manifest = _manifest(weights_sha256=weights, corpus_raw=raw, recipe=recipe)
    backend = HfLocalSftBackend(
        recipe=recipe,
        model_root=model_root,
        corpus_path=corpus_path,
        repository_root=repo,
        runtime=runtime,
    )

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "nf4" in (result.failure_reason or "")


def test_result_namespaces_must_be_outputs_and_results_siblings(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    manifest = replace(
        manifest,
        result_namespaces=(
            "experiments/mesc-t6-compact-sft/outputs",
            "experiments/other/results",
        ),
    )

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "share one experiment parent" in (result.failure_reason or "")


def test_runtime_builder_imports_training_stack_only_when_called(
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


def test_runtime_builder_fails_closed_when_training_stack_is_missing() -> None:
    def loader(name: str) -> object:
        raise ModuleNotFoundError(name)

    with pytest.raises(
        HfLocalSftBackendError,
        match="runtime package is unavailable",
    ):
        build_hf_local_sft_runtime(module_loader=loader)


def test_real_runtime_uses_local_only_no_auth_hf_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("WORLD_SIZE", "LOCAL_RANK", "ACCELERATE_CONFIG_FILE"):
        monkeypatch.delenv(name, raising=False)
    calls: dict[str, object] = {}

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def is_bf16_supported() -> bool:
            return True

        @staticmethod
        def current_device() -> int:
            return 0

        @staticmethod
        def manual_seed_all(seed: int) -> None:
            calls["cuda_seed"] = seed

        @staticmethod
        def empty_cache() -> None:
            calls["empty_cache"] = True

    class _Torch:
        bfloat16 = "bf16"
        cuda = _Cuda()

        @staticmethod
        def manual_seed(seed: int) -> None:
            calls["torch_seed"] = seed

    class _Tokenizer:
        chat_template = "{{ messages }}"
        eos_token = "</s>"
        pad_token: str | None = None

        def save_pretrained(self, path: str) -> None:
            (Path(path) / "tokenizer.json").write_text("{}\n", encoding="utf-8")

    tokenizer = _Tokenizer()

    class _AutoTokenizer:
        @staticmethod
        def from_pretrained(path: str, **kwargs: object) -> _Tokenizer:
            calls["tokenizer_path"] = path
            calls["tokenizer_kwargs"] = kwargs
            return tokenizer

    class _Model:
        def save_pretrained(self, path: str, *, safe_serialization: bool) -> None:
            calls["safe_serialization"] = safe_serialization
            (Path(path) / "adapter_model.safetensors").write_bytes(b"adapter")

    model = _Model()

    class _AutoModel:
        @staticmethod
        def from_pretrained(path: str, **kwargs: object) -> _Model:
            calls["model_path"] = path
            calls["model_kwargs"] = kwargs
            return model

    class _BitsConfig:
        def __init__(self, **kwargs: object) -> None:
            calls["bits_kwargs"] = kwargs

    class _Transformers:
        AutoTokenizer = _AutoTokenizer
        AutoModelForCausalLM = _AutoModel
        BitsAndBytesConfig = _BitsConfig

    class _Peft:
        @staticmethod
        def prepare_model_for_kbit_training(
            value: _Model,
            *,
            use_gradient_checkpointing: bool,
        ) -> _Model:
            calls["prepare_gradient_checkpointing"] = use_gradient_checkpointing
            return value

        class LoraConfig:
            def __init__(self, **kwargs: object) -> None:
                calls["lora_kwargs"] = kwargs

    class _Dataset:
        @staticmethod
        def from_list(records: list[dict[str, object]]) -> list[dict[str, object]]:
            calls["dataset_records"] = records
            return records

    class _Datasets:
        Dataset = _Dataset

    class _SFTConfig:
        def __init__(self, **kwargs: object) -> None:
            calls["sft_config"] = kwargs

    class _TrainOutput:
        def __init__(self) -> None:
            self.metrics: dict[str, object] = {"train_loss": 0.25, "ignored": "text"}

    class _SFTTrainer:
        def __init__(
            self,
            *,
            model: _Model,
            args: _SFTConfig,
            train_dataset: object,
            processing_class: _Tokenizer,
            peft_config: object,
        ) -> None:
            del args, train_dataset, peft_config
            calls["processing_class"] = processing_class
            self.model = model

        def train(self) -> _TrainOutput:
            return _TrainOutput()

    class _Trl:
        SFTConfig = _SFTConfig
        SFTTrainer = _SFTTrainer

    modules = {
        "torch": _Torch(),
        "transformers": _Transformers(),
        "trl": _Trl(),
        "peft": _Peft(),
        "datasets": _Datasets(),
        "accelerate": object(),
    }

    runtime = build_hf_local_sft_runtime(
        module_loader=lambda name: modules[name],
        version_loader=lambda name: f"{name}-fixture",
    )
    model_root = tmp_path / "model"
    model_root.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    recipe = _recipe()
    records: tuple[dict[str, object], ...] = (
        {
            "prompt": [{"role": "user", "content": "Question?"}],
            "completion": [{"role": "assistant", "content": "Answer."}],
        },
    )

    result = runtime.train_seed(
        model_root=model_root,
        records=records,
        recipe=recipe,
        seed=42,
        output_dir=output_dir,
        profile=HfLocalSftExecutionProfile(),
    )

    tokenizer_kwargs = calls["tokenizer_kwargs"]
    model_kwargs = calls["model_kwargs"]
    sft_config = calls["sft_config"]
    assert isinstance(tokenizer_kwargs, dict)
    assert isinstance(model_kwargs, dict)
    assert isinstance(sft_config, dict)
    assert tokenizer_kwargs["local_files_only"] is True
    assert tokenizer_kwargs["trust_remote_code"] is False
    assert tokenizer_kwargs["token"] is False
    assert model_kwargs["local_files_only"] is True
    assert model_kwargs["trust_remote_code"] is False
    assert model_kwargs["token"] is False
    assert model_kwargs["use_safetensors"] is True
    assert model_kwargs["torch_dtype"] == "bf16"
    assert "dtype" not in model_kwargs
    assert sft_config["report_to"] == "none"
    assert sft_config["push_to_hub"] is False
    assert sft_config["completion_only_loss"] is True
    assert calls["processing_class"] is tokenizer
    assert tokenizer.pad_token == tokenizer.eos_token
    assert calls["safe_serialization"] is True
    assert result.metrics == (("train_loss", 0.25),)
    assert ("bitsandbytes", "bitsandbytes-fixture") in result.packages
