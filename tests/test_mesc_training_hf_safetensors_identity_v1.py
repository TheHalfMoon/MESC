"""Tests for canonical local Hugging Face SafeTensors weight identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from medscale.mesc._training_hf_safetensors_identity_v1 import (
    HfSafeTensorsLocalModelVerifier,
    TrainingModelArtifactIdentityError,
    identify_hf_safetensors_artifact,
)
from medscale.mesc._training_launch_plan_v1 import (
    TrainingRole,
    TrainingRunPlan,
)
from medscale.modelkit.manifests import RunnerClass

_GIT_A = "1" * 40
_GIT_B = "2" * 40
_SHA_A = "a" * 64
_SHA_B = "b" * 64


def _run(
    *,
    weights_sha256: str,
    role: TrainingRole = "compact",
) -> TrainingRunPlan:
    return TrainingRunPlan(
        role=role,
        experiment_id=f"train-{role}",
        rq_refs=("RQ1",),
        recipe_id=_SHA_A,
        model_id="example/model",
        revision=_GIT_A,
        weights_sha256=weights_sha256,
        training_dataset_sha256=_SHA_B,
        seeds=(7,),
        runner_class=RunnerClass.LOCAL,
        python_version="3.11",
        os_name="linux",
        gpu_model="test-gpu",
        dependency_lock_sha256=_SHA_A,
        repository_sha=_GIT_A,
        repository_tree=_GIT_B,
        result_paths=(f"artifacts/{role}/result",),
        reproduction_command=f"medscale mesc train {role}",
    )


def _identify(root: Path):
    return identify_hf_safetensors_artifact(
        model_root=root,
        model_id="example/model",
        revision=_GIT_A,
    )


def _single(root: Path, raw: bytes = b"fixture-safetensors") -> None:
    root.mkdir()
    (root / "model.safetensors").write_bytes(raw)


def _sharded(
    root: Path,
    *,
    index_raw: bytes | None = None,
) -> None:
    root.mkdir()
    (root / "model-00001-of-00002.safetensors").write_bytes(b"shard-one")
    (root / "model-00002-of-00002.safetensors").write_bytes(b"shard-two")
    if index_raw is None:
        index_raw = json.dumps(
            {
                "metadata": {"total_size": 18},
                "weight_map": {
                    "layer.0": "model-00001-of-00002.safetensors",
                    "layer.1": "model-00002-of-00002.safetensors",
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    (root / "model.safetensors.index.json").write_bytes(index_raw)


def test_single_identity_is_path_independent_and_content_addressed(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _single(first_root)
    _single(second_root)

    first = _identify(first_root)
    second = _identify(second_root)

    assert first.layout == "single"
    assert first.files[0].path == "model.safetensors"
    assert first.files[0].kind == "weight"
    assert first.files[0].sha256 == hashlib.sha256(b"fixture-safetensors").hexdigest()
    assert first.files[0].byte_count == len(b"fixture-safetensors")
    assert first.weights_sha256 == second.weights_sha256
    assert first.verifier_receipt_sha256 == second.verifier_receipt_sha256

    (second_root / "model.safetensors").write_bytes(b"mutated-safetensors")
    mutated = _identify(second_root)
    assert mutated.weights_sha256 != first.weights_sha256


def test_sharded_identity_binds_index_and_complete_shards(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _sharded(root)

    identity = _identify(root)

    assert identity.layout == "sharded"
    assert tuple(item.path for item in identity.files) == (
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
    )
    assert tuple(item.kind for item in identity.files) == (
        "index",
        "weight",
        "weight",
    )
    assert len(identity.weights_sha256) == 64
    assert len(identity.verifier_receipt_sha256) == 64


def test_raw_index_bytes_participate_in_weight_identity(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"

    compact = (
        b'{"metadata":{},"weight_map":{"a":"model-00001-of-00002.safetensors",'
        b'"b":"model-00002-of-00002.safetensors"}}'
    )
    spaced = (
        b'{ "metadata": {}, "weight_map": {'
        b'"a": "model-00001-of-00002.safetensors", '
        b'"b": "model-00002-of-00002.safetensors"} }'
    )
    _sharded(first_root, index_raw=compact)
    _sharded(second_root, index_raw=spaced)

    first = _identify(first_root)
    second = _identify(second_root)

    assert first.files[1:] == second.files[1:]
    assert first.files[0].sha256 != second.files[0].sha256
    assert first.weights_sha256 != second.weights_sha256


def test_missing_weight_layout_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="does not contain a canonical SafeTensors",
    ):
        _identify(root)


def test_ambiguous_single_and_sharded_layout_fails_closed(
    tmp_path: Path,
) -> None:
    root = tmp_path / "model"
    _single(root)
    (root / "model.safetensors.index.json").write_text(
        '{"weight_map":{}}',
        encoding="utf-8",
    )

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="ambiguous",
    ):
        _identify(root)


def test_single_layout_rejects_additional_safetensors(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _single(root)
    (root / "adapter.safetensors").write_bytes(b"adapter")

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="unexpected additional weight files",
    ):
        _identify(root)


@pytest.mark.parametrize("suffix", [".bin", ".pt", ".pth"])
def test_pickle_compatible_weights_are_forbidden(
    tmp_path: Path,
    suffix: str,
) -> None:
    root = tmp_path / "model"
    _single(root)
    (root / f"pytorch_model{suffix}").write_bytes(b"unsafe")

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="pickle-compatible weight files are forbidden",
    ):
        _identify(root)


def test_sharded_layout_rejects_missing_referenced_shard(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _sharded(root)
    (root / "model-00002-of-00002.safetensors").unlink()

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="could not be statted",
    ):
        _identify(root)


def test_sharded_layout_rejects_unreferenced_weight_file(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _sharded(root)
    (root / "orphan.safetensors").write_bytes(b"orphan")

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="unreferenced weight files",
    ):
        _identify(root)


def test_sharded_layout_rejects_noncontiguous_sequence(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model-00001-of-00003.safetensors").write_bytes(b"one")
    (root / "model-00003-of-00003.safetensors").write_bytes(b"three")
    index = {
        "weight_map": {
            "a": "model-00001-of-00003.safetensors",
            "b": "model-00003-of-00003.safetensors",
        }
    }
    (root / "model.safetensors.index.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="complete contiguous sequence",
    ):
        _identify(root)


def test_sharded_layout_rejects_mixed_declared_totals(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model-00001-of-00002.safetensors").write_bytes(b"one")
    (root / "model-00002-of-00003.safetensors").write_bytes(b"two")
    index = {
        "weight_map": {
            "a": "model-00001-of-00002.safetensors",
            "b": "model-00002-of-00003.safetensors",
        }
    }
    (root / "model.safetensors.index.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="same shard count",
    ):
        _identify(root)


def test_malformed_index_json_fails_closed(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model.safetensors.index.json").write_bytes(b"{not-json")

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="valid UTF-8 JSON",
    ):
        _identify(root)


def test_index_rejects_traversal_shard_name(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    index = {
        "weight_map": {
            "a": "../model-00001-of-00001.safetensors",
        }
    }
    (root / "model.safetensors.index.json").write_text(
        json.dumps(index),
        encoding="utf-8",
    )

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="canonical POSIX basename",
    ):
        _identify(root)


def test_index_rejects_unknown_top_level_fields(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {"a": "model-00001-of-00001.safetensors"},
                "unexpected": True,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="only metadata and weight_map",
    ):
        _identify(root)


def test_symlink_weight_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "target.safetensors"
    target.write_bytes(b"target")
    root = tmp_path / "model"
    root.mkdir()
    link = root / "model.safetensors"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("symlink creation is unavailable on this runner")

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match=r"non-symlink regular file|opened safely",
    ):
        _identify(root)


def test_directory_named_as_weight_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "model"
    root.mkdir()
    (root / "model.safetensors").mkdir()

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="non-symlink regular file",
    ):
        _identify(root)


def test_local_verifier_emits_exact_local_only_observation(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _single(root)
    identity = _identify(root)
    run = _run(weights_sha256=identity.weights_sha256)
    verifier = HfSafeTensorsLocalModelVerifier()

    observed = verifier.verify(
        role="compact",
        model_root=root,
        run_plan=run,
    )

    assert observed.role == "compact"
    assert observed.model_id == run.model_id
    assert observed.revision == run.revision
    assert observed.weights_sha256 == run.weights_sha256
    assert observed.verifier_id == "mesc-hf-safetensors-local-verifier"
    assert observed.verifier_version == "v1"
    assert observed.verifier_receipt_sha256 == identity.verifier_receipt_sha256
    assert observed.network_accessed is False
    assert observed.remote_code_allowed is False
    assert observed.gated_terms_accepted is False


def test_local_verifier_rejects_role_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "model"
    _single(root)
    identity = _identify(root)
    run = _run(weights_sha256=identity.weights_sha256, role="compact")
    verifier = HfSafeTensorsLocalModelVerifier()

    with pytest.raises(
        TrainingModelArtifactIdentityError,
        match="role must match",
    ):
        verifier.verify(
            role="reasoner",
            model_root=root,
            run_plan=run,
        )
