"""Fail-closed MRL binding to the existing canonical runtime ExperimentManifest.

MRL-0104 does not create a second runtime manifest. It validates that one immutable
ResearchExperimentPlan's expected manifest envelope matches an existing
``medscale.modelkit.manifests.ExperimentManifest`` and then content-addresses only the
plan/runtime-manifest identity pair. The binding is declarative and grants no filesystem,
network, model, data, GPU, inference, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    ExpectedDatasetBinding,
    ExpectedExperimentManifestBinding,
    ExpectedModelBinding,
    ResearchExperimentPlan,
    ResearchExperimentPlanError,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import DatasetSnapshot, ExperimentManifest, RunnerClass, RunnerEnv

__all__ = [
    "ExperimentManifestBinding",
    "ExperimentManifestBindingError",
    "bind_experiment_manifest",
]


class ExperimentManifestBindingError(ValueError):
    """Fail-closed validation error for a plan/runtime-manifest binding."""


@dataclass(frozen=True, slots=True)
class ExperimentManifestBinding:
    """Content-addressed linkage to the existing canonical runtime manifest.

    The semantic payload contains identities only. The referenced plan and runtime
    manifest are retained privately so every public semantic/hash view can rebuild and
    revalidate both sides before emitting a trust-bearing identity pair.
    """

    plan: ResearchExperimentPlan = field(repr=False)
    manifest: ExperimentManifest = field(repr=False)

    def __post_init__(self) -> None:
        plan = _snapshot_plan(self.plan)
        manifest = _snapshot_manifest(self.manifest)
        _require_expected_manifest_match(plan.expected_manifest, manifest)
        object.__setattr__(self, "plan", plan)
        object.__setattr__(self, "manifest", manifest)

    def _validated_snapshot(self) -> ExperimentManifestBinding:
        return ExperimentManifestBinding(
            plan=_snapshot_plan(self.plan),
            manifest=_snapshot_manifest(self.manifest),
        )

    def _semantic_dict_validated(self) -> dict[str, str]:
        return {
            "format": "MRL-EXPERIMENT-MANIFEST-BINDING-V1",
            "experiment_plan_sha256": self.plan.content_sha256,
            "experiment_manifest_sha256": self.manifest.manifest_id,
        }

    def semantic_dict(self) -> dict[str, str]:
        """Return the exact validated plan/runtime-manifest identity pair."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical semantic bytes without self-referential identity."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive binding identity outside its own canonical semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, str]:
        """Return the identity pair plus the derived binding content identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def bind_experiment_manifest(
    plan: ResearchExperimentPlan,
    manifest: ExperimentManifest,
) -> ExperimentManifestBinding:
    """Validate and bind an existing runtime manifest to one frozen research plan."""
    return ExperimentManifestBinding(plan=plan, manifest=manifest)


def _snapshot_plan(value: ResearchExperimentPlan) -> ResearchExperimentPlan:
    _require_exact_instance(value, ResearchExperimentPlan, "plan")
    try:
        return value._validated_snapshot()
    except ResearchExperimentPlanError as exc:
        raise ExperimentManifestBindingError("plan failed canonical revalidation") from exc


def _snapshot_manifest(value: ExperimentManifest) -> ExperimentManifest:
    _require_exact_instance(value, ExperimentManifest, "manifest")
    _require_exact_str(value.experiment_id, "manifest.experiment_id")
    _require_tuple_of_exact(value.rq_refs, str, "manifest.rq_refs")
    _require_exact_str(value.configuration, "manifest.configuration")
    _require_exact_tuple(value.datasets, "manifest.datasets")
    for dataset in value.datasets:
        _require_exact_instance(dataset, DatasetSnapshot, "manifest.datasets item")
        _require_exact_str(dataset.name, "manifest dataset name")
        _require_exact_str(dataset.version, "manifest dataset version")
        _require_exact_str(dataset.content_sha256, "manifest dataset content_sha256")

    _require_exact_instance(value.model, ModelRef, "manifest.model")
    _require_exact_str(value.model.model_id, "manifest.model.model_id")
    if value.model.revision is not None:
        _require_exact_str(value.model.revision, "manifest.model.revision")
    _require_exact_str(value.model.quantization, "manifest.model.quantization")
    _require_exact_str(value.model.backend, "manifest.model.backend")

    _require_exact_int(value.model_tier, "manifest.model_tier")
    _require_exact_str(value.code_sha, "manifest.code_sha")
    _require_exact_tuple(value.seeds, "manifest.seeds")
    for seed in value.seeds:
        _require_exact_int(seed, "manifest seed")

    _require_exact_instance(value.runner, RunnerEnv, "manifest.runner")
    _require_exact_instance(value.runner.runner, RunnerClass, "manifest.runner.runner")
    _require_exact_str(value.runner.python, "manifest.runner.python")
    _require_exact_str(value.runner.os_name, "manifest.runner.os_name")
    if value.runner.gpu is not None:
        _require_exact_str(value.runner.gpu, "manifest.runner.gpu")
    if value.runner.peak_vram_gb is not None:
        if isinstance(value.runner.peak_vram_gb, bool) or not isinstance(
            value.runner.peak_vram_gb,
            (int, float),
        ):
            raise ExperimentManifestBindingError(
                "manifest.runner.peak_vram_gb must be numeric or None"
            )

    _require_exact_str(value.started_at, "manifest.started_at")
    _require_tuple_of_exact(value.results_paths, str, "manifest.results_paths")
    _require_exact_str(value.reproduction, "manifest.reproduction")

    try:
        return ExperimentManifest(
            experiment_id=value.experiment_id,
            rq_refs=tuple(value.rq_refs),
            configuration=value.configuration,
            datasets=tuple(
                DatasetSnapshot(
                    name=dataset.name,
                    version=dataset.version,
                    content_sha256=dataset.content_sha256,
                )
                for dataset in value.datasets
            ),
            model=ModelRef(
                model_id=value.model.model_id,
                revision=value.model.revision,
                quantization=value.model.quantization,
                backend=value.model.backend,
            ),
            model_tier=value.model_tier,
            code_sha=value.code_sha,
            seeds=tuple(value.seeds),
            runner=RunnerEnv(
                runner=value.runner.runner,
                python=value.runner.python,
                os_name=value.runner.os_name,
                gpu=value.runner.gpu,
                peak_vram_gb=value.runner.peak_vram_gb,
            ),
            started_at=value.started_at,
            results_paths=tuple(value.results_paths),
            reproduction=value.reproduction,
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ExperimentManifestBindingError(
            "manifest failed canonical runtime revalidation"
        ) from exc


def _require_expected_manifest_match(
    expected: ExpectedExperimentManifestBinding,
    manifest: ExperimentManifest,
) -> None:
    _require_exact_instance(
        expected,
        ExpectedExperimentManifestBinding,
        "plan.expected_manifest",
    )

    _require_equal("experiment_id", expected.experiment_id, manifest.experiment_id)
    _require_equal("rq_refs", expected.rq_refs, manifest.rq_refs)
    _require_equal(
        "configuration_sha256",
        expected.configuration_sha256,
        manifest.configuration_sha256,
    )

    expected_datasets = tuple(_expected_dataset_tuple(dataset) for dataset in expected.datasets)
    manifest_datasets = tuple(_runtime_dataset_tuple(dataset) for dataset in manifest.datasets)
    _require_equal("datasets", expected_datasets, manifest_datasets)

    _require_exact_instance(expected.model, ExpectedModelBinding, "plan.expected_manifest.model")
    expected_model = (
        expected.model.model_id,
        expected.model.revision,
        expected.model.quantization,
        expected.model.backend,
    )
    manifest_model = (
        manifest.model.model_id,
        manifest.model.revision,
        manifest.model.quantization,
        manifest.model.backend,
    )
    _require_equal("model", expected_model, manifest_model)

    _require_equal("model_tier", expected.model_tier, manifest.model_tier)
    _require_equal("code_sha", expected.code_sha, manifest.code_sha)
    _require_equal("seeds", expected.seeds, manifest.seeds)
    _require_equal("results_paths", expected.results_paths, manifest.results_paths)


def _expected_dataset_tuple(value: ExpectedDatasetBinding) -> tuple[str, str, str]:
    _require_exact_instance(value, ExpectedDatasetBinding, "plan.expected_manifest.datasets item")
    return (value.name, value.version, value.content_sha256)


def _runtime_dataset_tuple(value: DatasetSnapshot) -> tuple[str, str, str]:
    _require_exact_instance(value, DatasetSnapshot, "manifest.datasets item")
    return (value.name, value.version, value.content_sha256)


def _require_equal(name: str, expected: object, actual: object) -> None:
    if actual != expected:
        raise ExperimentManifestBindingError(f"manifest {name} does not match the frozen plan")


def _require_exact_instance(value: object, expected_type: type[object], name: str) -> None:
    if type(value) is not expected_type:
        raise ExperimentManifestBindingError(
            f"{name} must be exact {expected_type.__name__}; subclasses/type substitution are rejected"
        )


def _require_exact_tuple(value: object, name: str) -> None:
    if type(value) is not tuple:
        raise ExperimentManifestBindingError(f"{name} must be an immutable tuple")


def _require_tuple_of_exact(value: object, item_type: type[object], name: str) -> None:
    _require_exact_tuple(value, name)
    assert isinstance(value, tuple)
    if any(type(item) is not item_type for item in value):
        raise ExperimentManifestBindingError(f"{name} contains invalid item types")


def _require_exact_str(value: object, name: str) -> None:
    if type(value) is not str:
        raise ExperimentManifestBindingError(f"{name} must be an exact string")


def _require_exact_int(value: object, name: str) -> None:
    if type(value) is not int:
        raise ExperimentManifestBindingError(f"{name} must be an exact integer")
