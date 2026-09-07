"""Determinism qualification for MRL-0801 acquisition provenance receipts."""

from __future__ import annotations

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0801_acquisition_custody_v1 import required_mrl_0801_free_bytes


def receipt_document() -> dict[str, object]:
    total_bytes = 123
    required_bytes = required_mrl_0801_free_bytes(total_bytes)
    file_sha256 = "a" * 64
    return {
        "access_authorization_sha256": "b" * 64,
        "artifact_identity_sha256": "c" * 64,
        "asset_custody_sha256": "d" * 64,
        "candidate_roster_sha256": "e" * 64,
        "credentials_used": False,
        "executor_code_commit": "1" * 40,
        "executor_code_tree": "2" * 40,
        "executor_source_sha256": "f" * 64,
        "files": [
            {
                "byte_count": total_bytes,
                "local_sha256": file_sha256,
                "path": "model.safetensors",
                "remote_etag": file_sha256,
                "remote_etag_algorithm": "sha256",
            }
        ],
        "gpu_execution_performed": False,
        "inference_performed": False,
        "model_id": "example/model",
        "model_loading_performed": False,
        "mrl_0801_population_performed": False,
        "network_accessed": True,
        "public_unauthenticated": True,
        "remote_code_allowed": False,
        "revision": "3" * 40,
        "schema_version": "MESC-MRL-0801-HF-ACQUISITION-PROVENANCE-RECEIPT-V1",
        "source": "huggingface.co",
        "storage_available_bytes_at_preflight": required_bytes,
        "storage_required_bytes": required_bytes,
        "terms_accepted": False,
        "tokenizer_loading_performed": False,
        "total_byte_count": total_bytes,
        "training_performed": False,
        "trust_registry_mutation_performed": False,
        "weight_mutation_performed": False,
        "weights_sha256": "0" * 64,
    }


def test_receipt_bytes_are_deterministic_and_exclude_execution_locations() -> None:
    document = receipt_document()
    reversed_document = dict(reversed(tuple(document.items())))

    first = subject.MRL0801HfAcquisitionProvenanceReceipt(canonical_json_bytes(document))
    second = subject.MRL0801HfAcquisitionProvenanceReceipt(
        canonical_json_bytes(reversed_document)
    )

    assert first.canonical_bytes == second.canonical_bytes
    assert first.receipt_sha256 == second.receipt_sha256
    assert b"/tmp/" not in first.canonical_bytes
    assert b"https://" not in first.canonical_bytes
    assert b"?" not in first.canonical_bytes
