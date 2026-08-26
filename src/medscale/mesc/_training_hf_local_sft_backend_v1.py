"""Local-only Hugging Face SFT backend for the canonical MESC training executor.

The module is dependency-injected and imports no Hugging Face or Torch package at
module import time. The real runtime is constructed lazily and is constrained to
already-local SafeTensors model roots and an already-attested canonical JSONL corpus.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final, Protocol

from medscale.mesc._training_executor_v1 import (
    TrainingBackendResult,
    TrainingExecutionManifest,
    TrainingResultArtifact,
)
from medscale.mesc._training_hf_safetensors_identity_v1 import (
    HfSafeTensorsArtifactIdentity,
    TrainingModelArtifactIdentityError,
    identify_hf_safetensors_artifact,
)
from medscale.modelkit.recipes import AdapterMethod, TrainingRecipe
from medscale.reproducibility import canonical_json

_BACKEND_ID: Final = "mesc-hf-local-sft"
_BACKEND_VERSION: Final = "v1"
_PROFILE_VERSION: Final = "MESC-HF-LOCAL-SFT-PROFILE-V1"
_SHA256_CHUNK: Final = 1024 * 1024
_O_BINARY: Final = getattr(os, "O_BINARY", 0)
_O_DIRECTORY: Final = getattr(os, "O_DIRECTORY", 0)
_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_REQUIRED_RUNTIME_MODULES: Final = (
    "torch",
    "transformers",
    "trl",
    "peft",
    "datasets",
    "accelerate",
)
_OFFLINE_ENV: Final = {
    "HF_HUB_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "WANDB_DISABLED": "true",
}


class HfLocalSftBackendError(ValueError):
    """Raised when the local SFT backend cannot preserve its fail-closed contract."""


@dataclass(frozen=True, slots=True)
class HfLocalSftExecutionProfile:
    """Repository-bound trainer knobs that callers cannot override in V1."""

    per_device_train_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    max_length: int = 2048
    bf16: bool = True
    fp16: bool = False
    tf32: bool = False
    gradient_checkpointing: bool = True
    packing: bool = False
    completion_only_loss: bool = True
    profile_version: str = _PROFILE_VERSION

    def __post_init__(self) -> None:
        if self.profile_version != _PROFILE_VERSION:
            raise HfLocalSftBackendError(f"profile_version must be exactly {_PROFILE_VERSION}")

    def to_dict(self) -> dict[str, object]:
        return {
            "bf16": self.bf16,
            "completion_only_loss": self.completion_only_loss,
            "fp16": self.fp16,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "gradient_checkpointing": self.gradient_checkpointing,
            "max_length": self.max_length,
            "packing": self.packing,
            "per_device_train_batch_size": self.per_device_train_batch_size,
            "profile_version": self.profile_version,
            "tf32": self.tf32,
        }


@dataclass(frozen=True, slots=True)
class HfSftRuntimeResult:
    """Normalized observation returned by one concrete seed execution."""

    metrics: tuple[tuple[str, float], ...]
    packages: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if tuple(key for key, _ in self.metrics) != tuple(sorted(key for key, _ in self.metrics)):
            raise HfLocalSftBackendError("runtime metrics must use canonical key ordering")
        if tuple(key for key, _ in self.packages) != tuple(sorted(key for key, _ in self.packages)):
            raise HfLocalSftBackendError("runtime packages must use canonical key ordering")
        if len({key for key, _ in self.metrics}) != len(self.metrics):
            raise HfLocalSftBackendError("runtime metric keys must be unique")
        if len({key for key, _ in self.packages}) != len(self.packages):
            raise HfLocalSftBackendError("runtime package keys must be unique")
        for key, metric_value in self.metrics:
            _require_text(key, field="runtime metric name")
            if type(metric_value) is not float:
                raise HfLocalSftBackendError("runtime metric values must be floats")
        for key, package_value in self.packages:
            _require_text(key, field="runtime package name")
            _require_text(package_value, field="runtime package version")


class HfLocalSftRuntime(Protocol):
    """Injected runtime boundary; default CI supplies fake implementations only."""

    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult: ...


ModuleLoader = Callable[[str], Any]
VersionLoader = Callable[[str], str]


class HfLocalSftBackend:
    """TrainingBackend implementation for already-local HF LoRA/QLoRA SFT."""

    def __init__(
        self,
        *,
        recipe: TrainingRecipe,
        model_root: Path,
        corpus_path: Path,
        repository_root: Path,
        runtime: HfLocalSftRuntime,
    ) -> None:
        if type(recipe) is not TrainingRecipe:
            raise HfLocalSftBackendError("recipe must use the exact canonical TrainingRecipe type")
        for field, value in (
            ("model_root", model_root),
            ("corpus_path", corpus_path),
            ("repository_root", repository_root),
        ):
            if not isinstance(value, Path):
                raise HfLocalSftBackendError(f"{field} must be an exact pathlib.Path")
        self._recipe = recipe
        self._model_root = model_root
        self._corpus_path = corpus_path
        self._repository_root = repository_root
        self._runtime = runtime
        self._profile = HfLocalSftExecutionProfile()

    def execute(self, *, manifest: TrainingExecutionManifest) -> TrainingBackendResult:
        if type(manifest) is not TrainingExecutionManifest:
            raise HfLocalSftBackendError(
                "manifest must use the exact canonical TrainingExecutionManifest type"
            )
        started_at = _utc_now()
        staging: Path | None = None
        repository_fd: int | None = None
        publication_fd: int | None = None
        try:
            self._require_manifest_binding(manifest)
            model_identity = self._identify_model(manifest)
            raw_corpus = _read_attested_file(self._corpus_path)
            _require_corpus_identity(raw_corpus, manifest=manifest)
            records = _project_trl_records(raw_corpus)
            final_parent, final_parent_relative = _resolve_result_parent(
                manifest.result_namespaces,
                repository_root=self._repository_root,
            )
            if _path_exists_no_follow(final_parent):
                raise HfLocalSftBackendError("planned experiment result root already exists")
            publication_parent = _prepare_publication_parent(
                final_parent.parent,
                repository_root=self._repository_root,
            )
            repository_fd = _open_directory_fd(
                self._repository_root,
                field="repository_root",
            )
            publication_fd = _open_directory_fd(
                publication_parent,
                field="publication_parent",
            )
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{manifest.experiment_id}.mesc-sft-",
                    dir=self._repository_root,
                )
            )
            outputs_dir = staging / "outputs"
            results_dir = staging / "results"
            outputs_dir.mkdir()
            results_dir.mkdir()

            seed_observations: list[dict[str, object]] = []
            for seed in manifest.seeds:
                current = self._identify_model(manifest)
                if current.weights_sha256 != model_identity.weights_sha256:
                    raise HfLocalSftBackendError("model weight identity changed before training")
                seed_dir = outputs_dir / f"seed-{seed}"
                seed_dir.mkdir()
                runtime_result = self._runtime.train_seed(
                    model_root=self._model_root,
                    records=records,
                    recipe=self._recipe,
                    seed=seed,
                    output_dir=seed_dir,
                    profile=self._profile,
                )
                if type(runtime_result) is not HfSftRuntimeResult:
                    raise HfLocalSftBackendError(
                        "runtime returned a non-canonical HfSftRuntimeResult"
                    )
                after = self._identify_model(manifest)
                if after.weights_sha256 != model_identity.weights_sha256:
                    raise HfLocalSftBackendError("model weight identity changed during training")
                seed_observations.append(
                    {
                        "metrics": dict(runtime_result.metrics),
                        "packages": dict(runtime_result.packages),
                        "seed": seed,
                    }
                )

            summary = {
                "backend_id": _BACKEND_ID,
                "backend_version": _BACKEND_VERSION,
                "execution_manifest_sha256": manifest.execution_manifest_sha256,
                "experiment_id": manifest.experiment_id,
                "model_id": manifest.model_id,
                "profile": self._profile.to_dict(),
                "recipe_id": manifest.recipe_id,
                "revision": manifest.revision,
                "role": manifest.role,
                "seed_runs": seed_observations,
                "training_dataset_sha256": manifest.training_dataset_sha256,
                "weights_sha256": manifest.weights_sha256,
            }
            (results_dir / "training-summary.json").write_text(
                canonical_json(summary) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            staged_artifacts = _collect_result_artifacts(
                staging,
                final_parent_relative=final_parent_relative,
            )
            if publication_fd is None or repository_fd is None:
                raise HfLocalSftBackendError("publication descriptors are unavailable")
            _require_publication_parent_safe(
                publication_parent,
                repository_root=self._repository_root,
            )
            _require_directory_fd_matches_path(
                repository_fd,
                self._repository_root,
                field="repository_root",
            )
            _require_directory_fd_matches_path(
                publication_fd,
                publication_parent,
                field="publication_parent",
            )
            if _path_exists_no_follow(final_parent):
                raise HfLocalSftBackendError(
                    "planned experiment result root appeared during training"
                )
            try:
                os.replace(
                    staging.name,
                    final_parent.name,
                    src_dir_fd=repository_fd,
                    dst_dir_fd=publication_fd,
                )
            except OSError as exc:
                raise HfLocalSftBackendError(
                    "staged experiment root could not be published atomically"
                ) from exc
            staging = None
            return TrainingBackendResult(
                disposition="SUCCEEDED",
                backend_id=_BACKEND_ID,
                backend_version=_BACKEND_VERSION,
                started_at=started_at,
                finished_at=_utc_now(),
                artifacts=staged_artifacts,
            )
        except Exception as exc:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            return TrainingBackendResult(
                disposition="FAILED",
                backend_id=_BACKEND_ID,
                backend_version=_BACKEND_VERSION,
                started_at=started_at,
                finished_at=_utc_now(),
                artifacts=(),
                failure_reason=_failure_reason(exc),
            )
        except BaseException:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            if publication_fd is not None:
                os.close(publication_fd)
            if repository_fd is not None:
                os.close(repository_fd)

    def _identify_model(
        self,
        manifest: TrainingExecutionManifest,
    ) -> HfSafeTensorsArtifactIdentity:
        try:
            identity = identify_hf_safetensors_artifact(
                model_root=self._model_root,
                model_id=manifest.model_id,
                revision=manifest.revision,
            )
        except TrainingModelArtifactIdentityError as exc:
            raise HfLocalSftBackendError("local SafeTensors identity verification failed") from exc
        if identity.weights_sha256 != manifest.weights_sha256:
            raise HfLocalSftBackendError("local model weights do not match execution manifest")
        return identity

    def _require_manifest_binding(self, manifest: TrainingExecutionManifest) -> None:
        recipe = self._recipe
        if recipe.recipe_id != manifest.recipe_id:
            raise HfLocalSftBackendError("recipe_id does not match execution manifest")
        if recipe.base.model_id != manifest.model_id:
            raise HfLocalSftBackendError("recipe base model_id does not match execution manifest")
        if recipe.base.revision != manifest.revision:
            raise HfLocalSftBackendError("recipe base revision does not match execution manifest")
        if recipe.dataset.content_sha256 != manifest.training_dataset_sha256:
            raise HfLocalSftBackendError("recipe dataset does not match execution manifest")
        if recipe.base.backend != "transformers":
            raise HfLocalSftBackendError("V1 requires recipe base backend 'transformers'")
        if manifest.runner_class != "local":
            raise HfLocalSftBackendError("V1 supports only the local training runner")
        if recipe.seed not in manifest.seeds:
            raise HfLocalSftBackendError("recipe primary seed must be present in manifest seeds")
        if recipe.method is AdapterMethod.LORA:
            if recipe.base.quantization != "none":
                raise HfLocalSftBackendError("LoRA V1 requires unquantized base identity")
        elif recipe.method is AdapterMethod.QLORA:
            if recipe.base.quantization != "nf4":
                raise HfLocalSftBackendError(
                    "QLoRA V1 requires exact nf4 base quantization identity"
                )
        else:
            raise HfLocalSftBackendError("unsupported adapter method")


class _RealHfLocalSftRuntime:
    def __init__(
        self,
        modules: Mapping[str, Any],
        *,
        version_loader: VersionLoader,
    ) -> None:
        self._torch = modules["torch"]
        self._transformers = modules["transformers"]
        self._trl = modules["trl"]
        self._peft = modules["peft"]
        self._datasets = modules["datasets"]
        self._version_loader = version_loader

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
        _require_single_process_environment()
        torch_module = self._torch
        if not bool(torch_module.cuda.is_available()):
            raise HfLocalSftBackendError("CUDA is required by the V1 HF SFT runtime")
        bf16_supported = getattr(torch_module.cuda, "is_bf16_supported", None)
        if not callable(bf16_supported) or not bool(bf16_supported()):
            raise HfLocalSftBackendError("BF16-capable CUDA is required by the V1 HF SFT runtime")

        torch_module.manual_seed(seed)
        torch_module.cuda.manual_seed_all(seed)
        model: Any = None
        trainer: Any = None
        tokenizer: Any = None
        dataset: Any = None
        with _offline_hf_environment():
            try:
                tokenizer = self._transformers.AutoTokenizer.from_pretrained(
                    str(model_root),
                    local_files_only=True,
                    trust_remote_code=False,
                    token=False,
                )
                _require_tokenizer_contract(tokenizer)
                quantization_config: Any = None
                if recipe.method is AdapterMethod.QLORA:
                    quantization_config = self._transformers.BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_quant_type="nf4",
                        bnb_4bit_use_double_quant=True,
                        bnb_4bit_compute_dtype=torch_module.bfloat16,
                    )
                model_kwargs: dict[str, Any] = {
                    "dtype": torch_module.bfloat16,
                    "local_files_only": True,
                    "token": False,
                    "trust_remote_code": False,
                    "use_safetensors": True,
                    "device_map": {"": int(torch_module.cuda.current_device())},
                }
                if quantization_config is not None:
                    model_kwargs["quantization_config"] = quantization_config
                model = self._transformers.AutoModelForCausalLM.from_pretrained(
                    str(model_root),
                    **model_kwargs,
                )
                if recipe.method is AdapterMethod.QLORA:
                    model = self._peft.prepare_model_for_kbit_training(
                        model,
                        use_gradient_checkpointing=profile.gradient_checkpointing,
                    )
                peft_config = self._peft.LoraConfig(
                    r=recipe.lora_r,
                    lora_alpha=recipe.lora_alpha,
                    lora_dropout=recipe.lora_dropout,
                    target_modules=list(recipe.target_modules),
                    bias="none",
                    task_type="CAUSAL_LM",
                )
                dataset = self._datasets.Dataset.from_list(list(records))
                optim = (
                    "paged_adamw_8bit"
                    if recipe.method is AdapterMethod.QLORA
                    else "adamw_torch_fused"
                )
                args = self._trl.SFTConfig(
                    output_dir=str(output_dir),
                    per_device_train_batch_size=profile.per_device_train_batch_size,
                    gradient_accumulation_steps=profile.gradient_accumulation_steps,
                    learning_rate=recipe.learning_rate,
                    max_steps=recipe.max_steps,
                    optim=optim,
                    bf16=profile.bf16,
                    fp16=profile.fp16,
                    tf32=profile.tf32,
                    gradient_checkpointing=profile.gradient_checkpointing,
                    report_to="none",
                    eval_strategy="no",
                    save_strategy="no",
                    logging_strategy="no",
                    push_to_hub=False,
                    full_determinism=True,
                    seed=seed,
                    data_seed=seed,
                    dataloader_num_workers=0,
                    max_length=profile.max_length,
                    packing=profile.packing,
                    completion_only_loss=profile.completion_only_loss,
                    assistant_only_loss=False,
                    trust_remote_code=False,
                )
                trainer = self._trl.SFTTrainer(
                    model=model,
                    args=args,
                    train_dataset=dataset,
                    processing_class=tokenizer,
                    peft_config=peft_config,
                )
                train_output = trainer.train()
                trainer.model.save_pretrained(
                    str(output_dir),
                    safe_serialization=True,
                )
                tokenizer.save_pretrained(str(output_dir))
                metrics = _normalize_metrics(getattr(train_output, "metrics", {}))
                packages = _runtime_package_versions(
                    recipe.method,
                    version_loader=self._version_loader,
                )
                return HfSftRuntimeResult(metrics=metrics, packages=packages)
            finally:
                trainer = None
                model = None
                tokenizer = None
                dataset = None
                empty_cache = getattr(torch_module.cuda, "empty_cache", None)
                if callable(empty_cache):
                    empty_cache()


def build_hf_local_sft_runtime(
    *,
    module_loader: ModuleLoader = importlib.import_module,
    version_loader: VersionLoader = importlib.metadata.version,
) -> HfLocalSftRuntime:
    """Import the production training stack lazily and return the real local runtime."""
    modules: dict[str, Any] = {}
    with _offline_hf_environment():
        try:
            for name in _REQUIRED_RUNTIME_MODULES:
                modules[name] = module_loader(name)
        except Exception as exc:
            raise HfLocalSftBackendError(
                "required Hugging Face SFT runtime package is unavailable"
            ) from exc
    return _RealHfLocalSftRuntime(modules, version_loader=version_loader)


def _resolve_result_parent(
    namespaces: tuple[str, ...],
    *,
    repository_root: Path,
) -> tuple[Path, str]:
    if not isinstance(repository_root, Path):
        raise HfLocalSftBackendError("repository_root must be an exact pathlib.Path")
    if repository_root.is_symlink() or not repository_root.is_dir():
        raise HfLocalSftBackendError("repository_root must be an existing non-symlink directory")
    if not isinstance(namespaces, tuple) or len(namespaces) != 2:
        raise HfLocalSftBackendError("V1 requires exactly outputs and results namespaces")
    parsed = tuple(PurePosixPath(value) for value in namespaces)
    if {path.name for path in parsed} != {"outputs", "results"}:
        raise HfLocalSftBackendError("V1 namespaces must end in outputs and results")
    parents = {path.parent for path in parsed}
    if len(parents) != 1:
        raise HfLocalSftBackendError("V1 output namespaces must share one experiment parent")
    parent = next(iter(parents))
    if parent == PurePosixPath(".") or parent.is_absolute() or ".." in parent.parts:
        raise HfLocalSftBackendError("experiment result parent must be repository-relative")
    parent_text = parent.as_posix()
    final_parent = repository_root.joinpath(*parent.parts)
    return final_parent, parent_text


def _path_exists_no_follow(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise HfLocalSftBackendError("publication path could not be inspected safely") from exc
    return True


def _open_directory_fd(path: Path, *, field: str) -> int:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0:
        raise HfLocalSftBackendError(
            "platform cannot enforce descriptor-pinned publication directories"
        )
    flags = os.O_RDONLY | _O_BINARY | _O_DIRECTORY | _O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HfLocalSftBackendError(f"{field} could not be opened safely") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise HfLocalSftBackendError(f"{field} descriptor must reference a directory")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _require_directory_fd_matches_path(fd: int, path: Path, *, field: str) -> None:
    try:
        descriptor_info = os.fstat(fd)
        path_info = os.lstat(path)
    except OSError as exc:
        raise HfLocalSftBackendError(f"{field} changed during execution") from exc
    if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISDIR(path_info.st_mode):
        raise HfLocalSftBackendError(f"{field} must remain a non-symlink directory")
    if (descriptor_info.st_dev, descriptor_info.st_ino) != (path_info.st_dev, path_info.st_ino):
        raise HfLocalSftBackendError(f"{field} changed during execution")


def _prepare_publication_parent(
    publication_parent: Path,
    *,
    repository_root: Path,
) -> Path:
    return _walk_publication_parent(
        publication_parent,
        repository_root=repository_root,
        create_missing=True,
    )


def _require_publication_parent_safe(
    publication_parent: Path,
    *,
    repository_root: Path,
) -> None:
    _walk_publication_parent(
        publication_parent,
        repository_root=repository_root,
        create_missing=False,
    )


def _walk_publication_parent(
    publication_parent: Path,
    *,
    repository_root: Path,
    create_missing: bool,
) -> Path:
    try:
        root_info = os.lstat(repository_root)
    except OSError as exc:
        raise HfLocalSftBackendError("repository_root could not be inspected safely") from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise HfLocalSftBackendError("repository_root must be an existing non-symlink directory")
    try:
        relative = publication_parent.relative_to(repository_root)
    except ValueError as exc:
        raise HfLocalSftBackendError(
            "publication parent must remain inside repository_root"
        ) from exc

    current = repository_root
    for part in relative.parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if not create_missing:
                raise HfLocalSftBackendError(
                    "publication parent disappeared during execution"
                ) from None
            try:
                current.mkdir()
                info = os.lstat(current)
            except OSError as exc:
                raise HfLocalSftBackendError(
                    "publication parent could not be created safely"
                ) from exc
        except OSError as exc:
            raise HfLocalSftBackendError(
                "publication parent could not be inspected safely"
            ) from exc
        if stat.S_ISLNK(info.st_mode):
            raise HfLocalSftBackendError("publication parent ancestors must not be symlinks")
        if not stat.S_ISDIR(info.st_mode):
            raise HfLocalSftBackendError("publication parent ancestors must be directories")
        if info.st_dev != root_info.st_dev:
            raise HfLocalSftBackendError(
                "publication parent must remain on the repository filesystem"
            )

    try:
        root_resolved = repository_root.resolve(strict=True)
        current_resolved = current.resolve(strict=True)
    except OSError as exc:
        raise HfLocalSftBackendError("publication parent could not be resolved safely") from exc
    if current_resolved != root_resolved and root_resolved not in current_resolved.parents:
        raise HfLocalSftBackendError("publication parent resolved outside repository_root")
    return current


def _read_attested_file(path: Path) -> bytes:
    if not isinstance(path, Path):
        raise HfLocalSftBackendError("corpus_path must be an exact pathlib.Path")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HfLocalSftBackendError("canonical corpus could not be opened safely") from exc
    chunks: list[bytes] = []
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise HfLocalSftBackendError("canonical corpus must be a non-empty regular file")
        while True:
            chunk = os.read(fd, _SHA256_CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if _stat_identity(before) != _stat_identity(after):
        raise HfLocalSftBackendError("canonical corpus changed while being read")
    raw = b"".join(chunks)
    if len(raw) != before.st_size:
        raise HfLocalSftBackendError("canonical corpus byte count changed while being read")
    return raw


def _require_corpus_identity(raw: bytes, *, manifest: TrainingExecutionManifest) -> None:
    if len(raw) != manifest.canonical_corpus_byte_count:
        raise HfLocalSftBackendError("canonical corpus byte count does not match manifest")
    if hashlib.sha256(raw).hexdigest() != manifest.canonical_corpus_sha256:
        raise HfLocalSftBackendError("canonical corpus SHA-256 does not match manifest")


def _project_trl_records(raw: bytes) -> tuple[dict[str, object], ...]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HfLocalSftBackendError("canonical corpus must be UTF-8 JSONL") from exc
    lines = text.splitlines()
    if not lines:
        raise HfLocalSftBackendError("canonical corpus must contain at least one example")
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(lines, start=1):
        if not line:
            raise HfLocalSftBackendError("canonical corpus cannot contain empty JSONL records")
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HfLocalSftBackendError(
                f"canonical corpus record {line_number} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise HfLocalSftBackendError("canonical corpus records must be JSON objects")
        prompt = payload.get("prompt")
        completion = payload.get("completion")
        if not isinstance(prompt, list) or not prompt:
            raise HfLocalSftBackendError("canonical corpus prompt must be a non-empty message list")
        projected_prompt = [_require_message(item, completion=False) for item in prompt]
        projected_completion = _require_message(completion, completion=True)
        records.append(
            {
                "completion": [projected_completion],
                "prompt": projected_prompt,
            }
        )
    return tuple(records)


def _require_message(value: object, *, completion: bool) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"content", "role"}:
        raise HfLocalSftBackendError("training messages must contain exactly role and content")
    role = value.get("role")
    content = value.get("content")
    if role not in ("system", "user", "assistant") or not isinstance(content, str) or not content:
        raise HfLocalSftBackendError("training message role/content is invalid")
    if completion and role != "assistant":
        raise HfLocalSftBackendError("training completion must use assistant role")
    return {"content": content, "role": role}


def _collect_result_artifacts(
    staging: Path,
    *,
    final_parent_relative: str,
) -> tuple[TrainingResultArtifact, ...]:
    artifacts: list[TrainingResultArtifact] = []
    represented: set[str] = set()
    for child in sorted(staging.rglob("*")):
        if child.is_symlink():
            raise HfLocalSftBackendError("runtime output must not contain symlinks")
        if child.is_dir():
            continue
        info = child.stat(follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            raise HfLocalSftBackendError("runtime output must contain non-empty regular files only")
        if info.st_nlink != 1:
            raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
        relative = child.relative_to(staging)
        if relative.parts[0] not in ("outputs", "results"):
            raise HfLocalSftBackendError("runtime output escaped planned namespaces")
        represented.add(relative.parts[0])
        raw_sha, byte_count = _hash_regular_file(child)
        path = PurePosixPath(final_parent_relative, *relative.parts).as_posix()
        artifacts.append(
            TrainingResultArtifact(
                path=path,
                sha256=raw_sha,
                byte_count=byte_count,
            )
        )
    if represented != {"outputs", "results"}:
        raise HfLocalSftBackendError("successful runtime must represent both result namespaces")
    return tuple(sorted(artifacts, key=lambda item: item.path))


def _hash_regular_file(path: Path) -> tuple[str, int]:
    if _O_NOFOLLOW == 0:
        raise HfLocalSftBackendError("platform cannot enforce no-follow runtime output hashing")
    flags = os.O_RDONLY | _O_BINARY | _O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HfLocalSftBackendError("runtime output could not be opened safely") from exc

    digest = hashlib.sha256()
    byte_count = 0
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise HfLocalSftBackendError("runtime output must contain non-empty regular files only")
        if before.st_nlink != 1:
            raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
        while True:
            chunk = os.read(fd, _SHA256_CHUNK)
            if not chunk:
                break
            byte_count += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)

    if _stat_identity(before) != _stat_identity(after):
        raise HfLocalSftBackendError("runtime output changed while being hashed")
    if byte_count != before.st_size:
        raise HfLocalSftBackendError("runtime output byte count changed while being hashed")
    try:
        current = os.lstat(path)
    except OSError as exc:
        raise HfLocalSftBackendError("runtime output changed after hashing") from exc
    if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
        raise HfLocalSftBackendError("runtime output path changed after hashing")
    if current.st_nlink != 1:
        raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
    if _stat_identity(after) != _stat_identity(current):
        raise HfLocalSftBackendError("runtime output changed after hashing")
    return digest.hexdigest(), byte_count


def _normalize_metrics(value: object) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Mapping):
        return ()
    normalized: list[tuple[str, float]] = []
    for key, item in value.items():
        if not isinstance(key, str) or isinstance(item, bool) or not isinstance(item, (int, float)):
            continue
        normalized.append((key, float(item)))
    return tuple(sorted(normalized))


def _runtime_package_versions(
    method: AdapterMethod,
    *,
    version_loader: VersionLoader,
) -> tuple[tuple[str, str], ...]:
    names = list(_REQUIRED_RUNTIME_MODULES)
    if method is AdapterMethod.QLORA:
        names.append("bitsandbytes")
    versions: list[tuple[str, str]] = []
    for name in names:
        try:
            version = version_loader(name)
        except importlib.metadata.PackageNotFoundError as exc:
            raise HfLocalSftBackendError(f"runtime package metadata missing for {name}") from exc
        versions.append((name, version))
    return tuple(sorted(versions))


def _require_tokenizer_contract(tokenizer: Any) -> None:
    chat_template = getattr(tokenizer, "chat_template", None)
    if not isinstance(chat_template, str) or not chat_template.strip():
        raise HfLocalSftBackendError("local tokenizer must provide a non-empty chat template")
    eos_token = getattr(tokenizer, "eos_token", None)
    if not isinstance(eos_token, str) or not eos_token:
        raise HfLocalSftBackendError("local tokenizer must provide eos_token")
    if getattr(tokenizer, "pad_token", None) is None:
        tokenizer.pad_token = eos_token


def _require_single_process_environment() -> None:
    world_size = os.environ.get("WORLD_SIZE")
    if world_size not in (None, "", "1"):
        raise HfLocalSftBackendError("V1 refuses implicit distributed training")
    local_rank = os.environ.get("LOCAL_RANK")
    if local_rank not in (None, "", "-1", "0"):
        raise HfLocalSftBackendError("V1 refuses externally selected local ranks")
    if os.environ.get("ACCELERATE_CONFIG_FILE"):
        raise HfLocalSftBackendError("V1 refuses implicit Accelerate config files")


@contextmanager
def _offline_hf_environment() -> Iterator[None]:
    previous = {name: os.environ.get(name) for name in _OFFLINE_ENV}
    try:
        os.environ.update(_OFFLINE_ENV)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _failure_reason(exc: Exception) -> str:
    name = type(exc).__name__
    text = str(exc).strip()
    if not text:
        text = "backend execution failed"
    return f"{name}: {text}"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise HfLocalSftBackendError(f"{field} must be non-empty NUL-free text")
    return value
