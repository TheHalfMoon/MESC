from __future__ import annotations

from types import SimpleNamespace

import pytest

from medscale.mesc._mrl_0809_device_placement_audit_v1 import (
    PLACEMENT_AUDIT_SCHEMA,
    PlacementAuditError,
    audit_model_cuda0_placement,
)


class _Tensor:
    def __init__(self, device_type: str, index: int | None = None) -> None:
        self.device = SimpleNamespace(type=device_type, index=index)


class _Model:
    def __init__(
        self,
        *,
        parameters: list[tuple[str, object]] | None = None,
        buffers: list[tuple[str, object]] | None = None,
        device_map: object = ...,
    ) -> None:
        self._parameters: list[tuple[str, object]] = (
            parameters if parameters is not None else [("weight", _Tensor("cuda", 0))]
        )
        self._buffers: list[tuple[str, object]] = (
            buffers if buffers is not None else [("cache", _Tensor("cuda", 0))]
        )
        if device_map is not ...:
            self.hf_device_map = device_map

    def named_parameters(self, recurse: bool = True) -> list[tuple[str, object]]:
        assert recurse is True
        return self._parameters

    def named_buffers(self, recurse: bool = True) -> list[tuple[str, object]]:
        assert recurse is True
        return self._buffers


def test_missing_device_map_may_pass_when_actual_tensors_are_cuda0() -> None:
    result = audit_model_cuda0_placement(_Model())
    assert result == {
        "all_materialized_tensors_on_cuda_device_0": True,
        "buffer_count": 1,
        "hf_device_map_entry_count": 0,
        "hf_device_map_present": False,
        "parameter_count": 1,
        "schema_version": PLACEMENT_AUDIT_SCHEMA,
        "tensor_count": 2,
    }


def test_present_device_map_and_actual_tensors_must_both_be_cuda0() -> None:
    result = audit_model_cuda0_placement(_Model(device_map={"": 0, "model": "cuda:0"}))
    assert result["hf_device_map_present"] is True
    assert result["hf_device_map_entry_count"] == 2


def test_non_string_device_map_key_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="non-canonical module key"):
        audit_model_cuda0_placement(_Model(device_map={0: "cuda:0"}))


@pytest.mark.parametrize("target", ["cpu", "disk", "meta", "cuda", "cuda:1", 1])
def test_metadata_offload_ambiguous_or_other_cuda_device_fails_closed(target: object) -> None:
    with pytest.raises(PlacementAuditError):
        audit_model_cuda0_placement(_Model(device_map={"model": target}))


def test_ambiguous_metadata_cuda_device_without_index_fails_closed() -> None:
    target = SimpleNamespace(type="cuda", index=None)
    with pytest.raises(PlacementAuditError, match="ambiguous CUDA target"):
        audit_model_cuda0_placement(_Model(device_map={"model": target}))


def test_metadata_cannot_override_real_cpu_parameter() -> None:
    model = _Model(
        parameters=[("weight", _Tensor("cpu"))],
        device_map={"": 0},
    )
    with pytest.raises(PlacementAuditError, match=r"parameter 'weight'.*cpu"):
        audit_model_cuda0_placement(model)


def test_cuda1_parameter_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="CUDA device 0"):
        audit_model_cuda0_placement(_Model(parameters=[("weight", _Tensor("cuda", 1))]))


def test_meta_parameter_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="meta"):
        audit_model_cuda0_placement(_Model(parameters=[("weight", _Tensor("meta"))]))


def test_cpu_buffer_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match=r"buffer 'cache'.*cpu"):
        audit_model_cuda0_placement(_Model(buffers=[("cache", _Tensor("cpu"))]))


def test_mixed_parameter_placement_fails_closed() -> None:
    model = _Model(
        parameters=[("a", _Tensor("cuda", 0)), ("b", _Tensor("cpu"))],
        buffers=[],
    )
    with pytest.raises(PlacementAuditError, match=r"parameter 'b'.*cpu"):
        audit_model_cuda0_placement(model)


def test_empty_materialized_tensor_set_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="no materialized parameters or buffers"):
        audit_model_cuda0_placement(_Model(parameters=[], buffers=[]))


def test_empty_present_device_map_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="empty or not a mapping"):
        audit_model_cuda0_placement(_Model(device_map={}))


def test_unrecognized_metadata_target_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="not deterministically auditable"):
        audit_model_cuda0_placement(_Model(device_map={"model": object()}))


def test_ambiguous_actual_cuda_device_without_index_fails_closed() -> None:
    with pytest.raises(PlacementAuditError, match="cuda:None"):
        audit_model_cuda0_placement(_Model(parameters=[("weight", _Tensor("cuda", None))]))


def test_malformed_named_tensor_entry_fails_closed() -> None:
    model = _Model()
    model._parameters = [
        ("weight", _Tensor("cuda", 0)),
        ("bad",),  # type: ignore[list-item]
    ]
    with pytest.raises(PlacementAuditError, match="malformed parameter entry"):
        audit_model_cuda0_placement(model)
