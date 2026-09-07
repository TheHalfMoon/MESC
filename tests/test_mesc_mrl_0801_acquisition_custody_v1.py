"""Tests for bounded MRL-0801 acquisition authorization and custody receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0801_acquisition_custody_v1 import (
    MRL0801AcquisitionCustodyError,
    MRL0801AssetCustodyReceipt,
    canonical_mrl_0801_acquisition_authorization_bytes,
    generate_mrl_0801_asset_custody_receipt,
    parse_mrl_0801_acquisition_authorization,
    require_mrl_0801_storage_capacity,
    required_mrl_0801_free_bytes,
    validate_mrl_0801_custody_receipt_authorization,
)

_AUTHORIZATION_SHA256 = "af69087c6968c3bddb28556002a2a89fcf18932506a55d1eb7d6ff318e21b9d7"
_QWEN_MODEL_ID = "Qwen/Qwen3.8-27B"
_QWEN_REVISION = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
_GEMMA_MODEL_ID = "google/gemma-4-31B-it"
_GEMMA_REVISION = "842da3794eaa0b77d5f08bae87a17459d91ff475"
_ROSTER_SHA256 = "2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489"
_AUTHORIZATION_PATH = (
    Path(__file__).parents[1]
    / "specs"
    / "mesc-experiment-0"
    / "mrl-0801-acquisition-custody-authorization-v1.json"
)


def _authorization_bytes() -> bytes:
    return _AUTHORIZATION_PATH.read_bytes()


def _write_gemma_layout(root: Path) -> None:
    root.mkdir()
    first = "model-00001-of-00002.safetensors"
    second = "model-00002-of-00002.safetensors"
    (root / first).write_bytes(b"gemma-shard-one")
    (root / second).write_bytes(b"gemma-shard-two")
    index = {
        "metadata": {"total_size": len(b"gemma-shard-one") + len(b"gemma-shard-two")},
        "weight_map": {"layer.0": first, "layer.1": second},
    }
    (root / "model.safetensors.index.json").write_text(
        json.dumps(index, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _authorization_document() -> dict[str, object]:
    value = json.loads(_authorization_bytes().decode("utf-8"))
    assert type(value) is dict
    return cast(dict[str, object], value)


def test_committed_authorization_matches_exact_canonical_contract() -> None:
    raw = _authorization_bytes()

    assert raw == canonical_mrl_0801_acquisition_authorization_bytes()
    assert hashlib.sha256(raw).hexdigest() == _AUTHORIZATION_SHA256

    authorization = parse_mrl_0801_acquisition_authorization(raw)
    assert authorization.authorization_sha256 == _AUTHORIZATION_SHA256
    candidate_identities = tuple(
        (item.model_id, item.revision, item.role) for item in authorization.candidates
    )
    assert candidate_identities == (
        (_QWEN_MODEL_ID, _QWEN_REVISION, "PREFERRED_FOUNDATION_CANDIDATE"),
        (_GEMMA_MODEL_ID, _GEMMA_REVISION, "PRIMARY_CHALLENGER"),
    )
    assert all("Phi" not in item.model_id for item in authorization.candidates)


def test_authorization_binds_exact_base_roster_and_weight_only_allowlists() -> None:
    document = _authorization_document()
    base = cast(dict[str, object], document["authorized_base"])
    roster = cast(dict[str, object], document["candidate_roster"])
    candidates = cast(list[dict[str, object]], document["candidates"])

    assert base == {
        "main_sha": "07b98baded530b7914dc0d1d89534cfcf6ee568a",
        "main_tree": "339125e96fa38c2cdab4b2f93c0a634f333f2587",
        "post_merge_ci_run": 34139543250,
        "post_merge_ci_success": True,
    }
    assert roster == {
        "path": "specs/mesc-experiment-0/candidate-roster-v1.json",
        "sha256": _ROSTER_SHA256,
    }
    assert len(cast(list[str], candidates[0]["allowed_files"])) == 19
    assert len(cast(list[str], candidates[1]["allowed_files"])) == 3
    for candidate in candidates:
        allowed_files = cast(list[str], candidate["allowed_files"])
        assert allowed_files[0] == "model.safetensors.index.json"
        assert all(
            path == "model.safetensors.index.json" or path.endswith(".safetensors")
            for path in allowed_files
        )


def test_authorization_scope_expansion_fails_closed() -> None:
    document = _authorization_document()
    policy = cast(dict[str, object], document["acquisition_policy"])
    policy["training_authorized"] = True
    raw = canonical_json_bytes(document)

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="exact authorized scope",
    ):
        parse_mrl_0801_acquisition_authorization(raw)


def test_authorization_stale_revision_fails_closed() -> None:
    document = _authorization_document()
    candidates = cast(list[dict[str, object]], document["candidates"])
    candidates[0]["revision"] = "0" * 40

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="exact authorized scope",
    ):
        parse_mrl_0801_acquisition_authorization(canonical_json_bytes(document))


def test_noncanonical_authorization_bytes_fail_closed() -> None:
    document = _authorization_document()
    noncanonical = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="not canonical JSON",
    ):
        parse_mrl_0801_acquisition_authorization(noncanonical)


def test_storage_capacity_preflight_uses_exact_bytes_plus_maximum_margin() -> None:
    one_gib = 1024 * 1024 * 1024
    ten_gib = 10 * one_gib
    hundred_gib = 100 * one_gib
    two_hundred_gib = 200 * one_gib

    assert required_mrl_0801_free_bytes(hundred_gib) == hundred_gib + ten_gib
    assert required_mrl_0801_free_bytes(two_hundred_gib) == two_hundred_gib + 20 * one_gib
    assert (
        require_mrl_0801_storage_capacity(
            exact_allowlist_bytes=hundred_gib,
            available_bytes=hundred_gib + ten_gib,
        )
        == hundred_gib + ten_gib
    )

    with pytest.raises(MRL0801AcquisitionCustodyError, match="below"):
        require_mrl_0801_storage_capacity(
            exact_allowlist_bytes=hundred_gib,
            available_bytes=hundred_gib + ten_gib - 1,
        )


def test_genuine_local_custody_receipt_is_path_free_and_deterministic(tmp_path: Path) -> None:
    authorization = parse_mrl_0801_acquisition_authorization(_authorization_bytes())
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    _write_gemma_layout(first_root)
    _write_gemma_layout(second_root)

    first = generate_mrl_0801_asset_custody_receipt(
        model_root=first_root,
        authorization=authorization,
        model_id=_GEMMA_MODEL_ID,
        revision=_GEMMA_REVISION,
    )
    second = generate_mrl_0801_asset_custody_receipt(
        model_root=second_root,
        authorization=authorization,
        model_id=_GEMMA_MODEL_ID,
        revision=_GEMMA_REVISION,
    )

    assert first.asset_custody_sha256 == second.asset_custody_sha256
    assert first.canonical_bytes == second.canonical_bytes
    assert first.access_authorization_sha256 == _AUTHORIZATION_SHA256
    assert len(first.artifact_identity_sha256) == 64
    assert len(first.weights_sha256) == 64
    assert str(tmp_path).encode("utf-8") not in first.canonical_bytes
    validate_mrl_0801_custody_receipt_authorization(
        receipt=first,
        authorization=authorization,
        model_root=first_root,
    )


def test_custody_generation_requires_exact_authorized_manifest(tmp_path: Path) -> None:
    authorization = parse_mrl_0801_acquisition_authorization(_authorization_bytes())
    root = tmp_path / "model"
    _write_gemma_layout(root)
    (root / "model-00002-of-00002.safetensors").unlink()

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="verification failed",
    ):
        generate_mrl_0801_asset_custody_receipt(
            model_root=root,
            authorization=authorization,
            model_id=_GEMMA_MODEL_ID,
            revision=_GEMMA_REVISION,
        )


def test_custody_receipt_requires_current_exact_authorization_binding(tmp_path: Path) -> None:
    authorization = parse_mrl_0801_acquisition_authorization(_authorization_bytes())
    root = tmp_path / "model"
    _write_gemma_layout(root)
    receipt = generate_mrl_0801_asset_custody_receipt(
        model_root=root,
        authorization=authorization,
        model_id=_GEMMA_MODEL_ID,
        revision=_GEMMA_REVISION,
    )
    document = json.loads(receipt.canonical_bytes.decode("utf-8"))
    assert type(document) is dict
    document["access_authorization_sha256"] = "0" * 64
    altered = MRL0801AssetCustodyReceipt(canonical_json_bytes(document))

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="different acquisition authorization",
    ):
        validate_mrl_0801_custody_receipt_authorization(
            receipt=altered,
            authorization=authorization,
            model_root=root,
        )


def test_parsed_custody_receipt_requires_live_local_byte_reverification(tmp_path: Path) -> None:
    authorization = parse_mrl_0801_acquisition_authorization(_authorization_bytes())
    root = tmp_path / "model"
    _write_gemma_layout(root)
    generated = generate_mrl_0801_asset_custody_receipt(
        model_root=root,
        authorization=authorization,
        model_id=_GEMMA_MODEL_ID,
        revision=_GEMMA_REVISION,
    )
    parsed = MRL0801AssetCustodyReceipt(generated.canonical_bytes)
    (root / "model-00002-of-00002.safetensors").write_bytes(b"tampered-local-shard")

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="current local bytes",
    ):
        validate_mrl_0801_custody_receipt_authorization(
            receipt=parsed,
            authorization=authorization,
            model_root=root,
        )


def test_unlisted_model_revision_is_not_authorized(tmp_path: Path) -> None:
    authorization = parse_mrl_0801_acquisition_authorization(_authorization_bytes())
    root = tmp_path / "model"
    _write_gemma_layout(root)

    with pytest.raises(
        MRL0801AcquisitionCustodyError,
        match="outside the MRL-0801 acquisition authorization",
    ):
        generate_mrl_0801_asset_custody_receipt(
            model_root=root,
            authorization=authorization,
            model_id="microsoft/Phi-4-multimodal-instruct",
            revision="450bd6eb5ed6a74e38a03ada0320c4fa07865c81",
        )
