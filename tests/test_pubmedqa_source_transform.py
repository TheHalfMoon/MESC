"""Deterministic PubMedQA Layer-1 source transformation tests.

Uses ONLY synthetic strings. No network access. No public contract mutation.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from medscale.dataset._pubmedqa_source import (
    NativeAnnotationTrace,
    NativeContextSegment,
    PilotPubMedQASourceRecord,
    _record_to_envelope,
    _row_to_source_record,
)

# ============================================================================
# Synthetic helpers
# ============================================================================


def _make_row(
    *,
    pubid: int = 1,
    question: str = "  QUESTION  ",
    long_answer: str = "  LONG_ANSWER  ",
    final_decision: str = "  yes  ",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    default_context = {
        "contexts": ["alpha text", "beta text", "alpha text"],
        "labels": ["BACKGROUND", "METHODS", "BACKGROUND"],
        "meshes": ["mesh1", "mesh2"],
        "reasoning_required_pred": ["a", "b"],
        "reasoning_free_pred": ["c", "d"],
    }
    return {
        "pubid": pubid,
        "question": question,
        "long_answer": long_answer,
        "final_decision": final_decision,
        "context": context if context is not None else default_context,
    }


def _write_synthetic_parquet(path: Path) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table(
        {
            "pubid": pa.array([1], type=pa.int64()),
            "question": pa.array(["q"], type=pa.string()),
            "context": pa.array(
                [_make_row()["context"]],
                type=pa.struct(
                    [
                        pa.field("contexts", pa.list_(pa.field("item", pa.string()))),
                        pa.field("labels", pa.list_(pa.field("item", pa.string()))),
                        pa.field("meshes", pa.list_(pa.field("item", pa.string()))),
                        pa.field(
                            "reasoning_required_pred",
                            pa.list_(pa.field("item", pa.string())),
                        ),
                        pa.field(
                            "reasoning_free_pred",
                            pa.list_(pa.field("item", pa.string())),
                        ),
                    ]
                ),
            ),
            "long_answer": pa.array(["a"], type=pa.string()),
            "final_decision": pa.array(["yes"], type=pa.string()),
        }
    )
    pq.write_table(table, str(path))
    return path


# ============================================================================
# P01-03D dataclass contract
# ============================================================================


class TestP0103DContract:
    def test_pilot_record_fields(self) -> None:
        expected = {
            "schema_version",
            "dataset_id",
            "dataset_revision",
            "configuration",
            "original_example_id",
            "source_document_id",
            "pubid",
            "question",
            "context_segments",
            "mesh_terms",
            "long_answer",
            "final_decision",
            "native_annotation_trace",
            "license_id",
        }
        assert expected == set(PilotPubMedQASourceRecord.__dataclass_fields__.keys())

    def test_pilot_record_absent_fields_removed(self) -> None:
        removed = {
            "transformation_version",
            "source_record_hash",
            "question_text",
            "annotation_traces",
        }
        assert removed.isdisjoint(PilotPubMedQASourceRecord.__dataclass_fields__.keys())

    def test_pilot_record_pubid_type(self) -> None:
        assert PilotPubMedQASourceRecord.__dataclass_fields__["pubid"].type == "str"

    def test_pilot_record_question_type(self) -> None:
        assert PilotPubMedQASourceRecord.__dataclass_fields__["question"].type == "str"


# ============================================================================
# Frozen / slots without custom emulation
# ============================================================================


class TestFrozenSlotted:
    def test_native_frozen_slots(self) -> None:
        segment = NativeContextSegment(ordinal=0, text="t", section_label="s")
        with pytest.raises(AttributeError):
            segment.ordinal = 1  # type: ignore[misc]
        assert set(NativeContextSegment.__slots__) == {"ordinal", "text", "section_label"}

    def test_native_annotation_trace_slots(self) -> None:
        trace = NativeAnnotationTrace(reasoning_required_pred=("r",), reasoning_free_pred=("f",))
        with pytest.raises(AttributeError):
            trace.reasoning_required_pred = ("x",)  # type: ignore[misc]
        assert set(NativeAnnotationTrace.__slots__) == {
            "reasoning_required_pred",
            "reasoning_free_pred",
        }

    def test_pilot_record_slots(self) -> None:
        anchors = {
            "schema_version",
            "dataset_id",
            "dataset_revision",
            "configuration",
            "original_example_id",
            "source_document_id",
            "pubid",
            "question",
            "context_segments",
            "mesh_terms",
            "long_answer",
            "final_decision",
            "native_annotation_trace",
            "license_id",
        }
        assert anchors.issubset(set(PilotPubMedQASourceRecord.__slots__))


# ============================================================================
# PyArrow import isolation
# ============================================================================


class TestPyArrowIsolation:
    def test_private_module_import_does_not_require_pyarrow(self) -> None:
        code = """
import sys
import medscale.dataset._pubmedqa_source
polluted = [name for name in sys.modules if name == "pyarrow" or name.startswith("pyarrow.")]
raise SystemExit(1 if polluted else 0)
"""
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr


# ============================================================================
# Native mapping correctness
# ============================================================================


class TestNativeMapping:
    def test_zero_based_ordinals(self) -> None:
        context = {
            "contexts": ["a", "b", "c"],
            "labels": ["x", "y", "z"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        assert [segment.ordinal for segment in row.context_segments] == [0, 1, 2]

    def test_exact_duplicate_context_preserved(self) -> None:
        context = {
            "contexts": ["dup", "dup", "unique"],
            "labels": ["same", "same", "diff"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        assert len(row.context_segments) == 3
        assert row.context_segments[0] == NativeContextSegment(
            ordinal=0, text="dup", section_label="same"
        )
        assert row.context_segments[1] == NativeContextSegment(
            ordinal=1, text="dup", section_label="same"
        )

    def test_pubid_canonical_string(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        row = _row_to_source_record(12345, "q", context, "a", "yes", 0)
        assert row.pubid == "12345"
        assert row.source_document_id == "pmid:12345"

    def test_mesh_terms_preserved(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": ["mesh1", "mesh2", "mesh1"],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        assert row.mesh_terms == ("mesh1", "mesh2", "mesh1")

    def test_single_annotation_trace(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": ["mesh1"],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        assert isinstance(row.native_annotation_trace, NativeAnnotationTrace)
        assert row.native_annotation_trace.reasoning_required_pred == ("r1",)
        assert row.native_annotation_trace.reasoning_free_pred == ("f1",)

    def test_text_is_not_stripped(self) -> None:
        context = {
            "contexts": ["  segmented text  "],
            "labels": ["BACKGROUND"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        row = _row_to_source_record(1, "  question  ", context, "  answer  ", "yes", 0)
        assert row.question == "  question  "
        assert row.long_answer == "  answer  "
        assert row.context_segments[0].text == "  segmented text  "

    def test_empty_after_strip_raises(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        with pytest.raises(ValueError):
            _row_to_source_record(1, "   ", context, "a", "yes", 0)


# ============================================================================
# Hash behavior
# ============================================================================


class TestHashBehavior:
    def test_hash_outside_record(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        envelope = _record_to_envelope(row)
        assert "record" in envelope
        assert "source_record_hash" in envelope
        assert "source_record_hash" not in envelope["record"]

    def test_hash_covers_all_scientific_fields(self) -> None:
        scientific_fields = {
            "schema_version",
            "dataset_id",
            "dataset_revision",
            "configuration",
            "original_example_id",
            "source_document_id",
            "pubid",
            "question",
            "context_segments",
            "mesh_terms",
            "long_answer",
            "final_decision",
            "reasoning_required_pred",
            "reasoning_free_pred",
            "license_id",
        }
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": ["m1"],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        row = _row_to_source_record(1, "q", context, "a", "yes", 0)
        envelope = _record_to_envelope(row)
        assert set(envelope["record"].keys()) == scientific_fields

    def test_hash_deterministic(self) -> None:
        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        first = _row_to_source_record(1, "q", context, "a", "yes", 0)
        second = _row_to_source_record(1, "q", context, "a", "yes", 0)
        assert (
            _record_to_envelope(first)["source_record_hash"]
            == _record_to_envelope(second)["source_record_hash"]
        )

    def test_hash_changes_with_scientific_field(self) -> None:
        context_a = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        context_b = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": ["r1"],
            "reasoning_free_pred": ["f1"],
        }
        row_a = _row_to_source_record(1, "q", context_a, "a", "yes", 0)
        row_b = _row_to_source_record(2, "q", context_b, "a", "yes", 0)
        assert (
            _record_to_envelope(row_a)["source_record_hash"]
            != _record_to_envelope(row_b)["source_record_hash"]
        )


# ============================================================================
# Public namespace integrity
# ============================================================================


class TestPublicNamespace:
    def test_internal_not_in_public_all(self) -> None:
        public_all = getattr(__import__("medscale.dataset", fromlist=[""]), "__all__", [])
        assert "_pubmedqa_source" not in public_all

    def test_no_pilot_record_in_public(self) -> None:
        assert "PilotPubMedQASourceRecord" not in dir(
            __import__("medscale.dataset", fromlist=["PilotPubMedQASourceRecord"])
        )

    def test_no_public_example_id_function(self) -> None:
        mod = __import__("medscale.dataset", fromlist=["pubmedqa_example_id"])
        assert not hasattr(mod, "pubmedqa_example_id")


# ============================================================================
# Operator harness
# ============================================================================


EXPECTED_OUTPUT_FILES = {
    "source-records.jsonl",
    "source-record-registry.jsonl",
    "transformation-manifest.json",
    "transformation-run.local.json",
}


def _run_operator(args: list[str]) -> tuple[int, dict[str, Any] | None]:
    script = Path(__file__).resolve().parents[1] / "scripts" / "mesc_pilot_01_transform_pubmedqa.py"
    completed = subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        sys.stderr.write(completed.stderr)
        return completed.returncode, None
    try:
        return completed.returncode, json.loads(completed.stdout)
    except json.JSONDecodeError:
        return completed.returncode, None


def _fresh_output_path(base: Path, name: str) -> Path:
    candidate = base / name
    assert not candidate.exists(), f"test intended an absent output directory: {candidate}"
    return candidate


# ============================================================================
# Deterministic output contract
# ============================================================================


class TestDeterministicContract:
    def test_exact_four_final_files(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        actual_dir = final
        files = {p.name for p in actual_dir.iterdir() if p.is_file()}
        assert EXPECTED_OUTPUT_FILES.issubset(files)
        assert all((actual_dir / name).exists() for name in EXPECTED_OUTPUT_FILES)

    def test_manifest_filename(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        assert (final / "transformation-manifest.json").exists()
        assert not (final / "source-record-manifest.json").exists()

    def test_no_repository_report_in_external_output(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        assert not (final / "transformation-report.json").exists()


# ============================================================================
# Promotion safety
# ============================================================================


class TestPromotionSafety:
    def test_existing_destination_fails(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        pre_existing = _fresh_output_path(tmp_path, "pre-existing")
        pre_existing.mkdir()
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(pre_existing),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 1
        assert not (pre_existing / "source-records.jsonl").exists()

    def test_temporary_directories_do_not_overwrite_each_other(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        rc1, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(_fresh_output_path(tmp_path, "run1")),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        rc2, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(_fresh_output_path(tmp_path, "run2")),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc1 == 0
        assert rc2 == 0


# ============================================================================
# Deterministic manifest metadata
# ============================================================================


class TestDeterministicManifestMetadata:
    def test_manifest_no_run_identities(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        manifest = json.loads((final / "transformation-manifest.json").read_text(encoding="utf-8"))
        assert "run_id" not in manifest
        assert "timestamp" not in manifest
        assert "output_directory" not in manifest
        assert "pyarrow_version" not in manifest


# ============================================================================
# Operator contract
# ============================================================================


class TestOperatorContract:
    def test_stdout_only_concise_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _payload = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        assert _payload is not None
        assert _payload.get("schema_version") == "mesc-pubmedqa-operator-result/1"
        assert set(_payload.get("output_files", [])) == EXPECTED_OUTPUT_FILES


# ============================================================================
# Cross-run equality
# ============================================================================


class TestCrossRunEquality:
    def test_independent_runs_produce_equal_three_file_bundle(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        first_dir = _fresh_output_path(tmp_path, "run1")
        second_dir = _fresh_output_path(tmp_path, "run2")
        rc1, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(first_dir),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        rc2, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(second_dir),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc1 == 0
        assert rc2 == 0
        first_files = {
            name: (first_dir / name).read_bytes() for name in sorted(EXPECTED_OUTPUT_FILES)
        }
        second_files = {
            name: (second_dir / name).read_bytes() for name in sorted(EXPECTED_OUTPUT_FILES)
        }
        assert first_files == second_files

    def test_three_file_byte_sizes_match_across_runs(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        first_dir = _fresh_output_path(tmp_path, "run1")
        second_dir = _fresh_output_path(tmp_path, "run2")
        rc1, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(first_dir),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        rc2, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(second_dir),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc1 == 0
        assert rc2 == 0
        for name in EXPECTED_OUTPUT_FILES:
            assert (first_dir / name).stat().st_size == (second_dir / name).stat().st_size


# ============================================================================
# Synthetic parquet integration
# ============================================================================


class TestSyntheticParquetIntegration:
    def test_exact_nested_struct_shape(self, tmp_path: Path) -> None:
        parquet = tmp_path / "fake.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "out")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        content = (final / "source-records.jsonl").read_text(encoding="utf-8")
        lines = [line for line in content.splitlines() if line.strip()]
        assert len(lines) == 1
        record = json.loads(lines[0])["record"]
        assert record["pubid"] == "1"
        assert record["context_segments"][0]["ordinal"] == 0


# ============================================================================
# Operator output-path safety
# ============================================================================
_OPERATOR_SPEC = importlib.util.spec_from_file_location(
    "mesc_pilot_01_transform_pubmedqa_under_test",
    Path(__file__).resolve().parents[1] / "scripts" / "mesc_pilot_01_transform_pubmedqa.py",
)
if _OPERATOR_SPEC is None or _OPERATOR_SPEC.loader is None:
    raise RuntimeError("failed to load the PubMedQA transformation operator")
_OPERATOR_MODULE = importlib.util.module_from_spec(_OPERATOR_SPEC)
sys.modules[_OPERATOR_SPEC.name] = _OPERATOR_MODULE
_OPERATOR_SPEC.loader.exec_module(_OPERATOR_MODULE)
_is_safe_output_parent = _OPERATOR_MODULE._is_safe_output_parent


class TestOperatorOutputPathSafety:
    def test_repository_root_level(self) -> None:
        operator_script = (
            Path(__file__).resolve().parents[1] / "scripts" / "mesc_pilot_01_transform_pubmedqa.py"
        )
        repo_root = operator_script.parents[1]
        computed = Path(operator_script).resolve().parents[1]
        assert computed == repo_root
        repo_output = repo_root / "output"
        with pytest.raises(ValueError, match="must not be inside the MedScale repository"):
            _is_safe_output_parent(repo_output)

    def test_output_directly_inside_repository_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        repo_output = repo_root / "output"
        with pytest.raises(ValueError, match="must not be inside the MedScale repository"):
            _is_safe_output_parent(repo_output)

    def test_output_nested_inside_repository_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        nested_output = repo_root / "sub" / "output"
        with pytest.raises(ValueError, match="must not be inside the MedScale repository"):
            _is_safe_output_parent(nested_output)

    def test_output_inside_raw_directory_rejected(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        raw_output = repo_root / "data" / "raw" / "output"
        with pytest.raises(ValueError, match="must not be inside the raw-data directory"):
            _is_safe_output_parent(raw_output)

    def test_external_sibling_accepted(self, tmp_path: Path) -> None:
        sibling = tmp_path / "repo-output"
        try:
            _is_safe_output_parent(sibling)
        except ValueError:
            pytest.fail("external sibling path was incorrectly rejected")

    def test_external_sibling_textual_prefix_accepted(self, tmp_path: Path) -> None:
        textual_sibling = tmp_path / "repo-extra"
        try:
            _is_safe_output_parent(textual_sibling)
        except ValueError:
            pytest.fail("sibling path sharing a textual prefix was incorrectly rejected")

    def test_onedrive_marker_rejected(self, tmp_path: Path) -> None:
        onedrive_output = tmp_path / "OneDrive" / "output"
        onedrive_output.mkdir(parents=True)
        with pytest.raises(ValueError, match="must not be inside OneDrive"):
            _is_safe_output_parent(onedrive_output)

    def test_existing_destination_fails(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        pre_existing = _fresh_output_path(tmp_path, "pre-existing")
        pre_existing.mkdir()
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(pre_existing),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 1
        assert not (pre_existing / "source-records.jsonl").exists()

    def test_deterministic_synthetic_transformation_unchanged(self, tmp_path: Path) -> None:
        parquet = tmp_path / "source.parquet"
        _write_synthetic_parquet(parquet)
        sha = hashlib.sha256(parquet.read_bytes()).hexdigest()
        final = _fresh_output_path(tmp_path, "final")
        rc, _ = _run_operator(
            [
                "--input",
                str(parquet),
                "--output-dir",
                str(final),
                "--expected-sha256",
                sha,
                "--expected-size",
                str(parquet.stat().st_size),
            ]
        )
        assert rc == 0
        actual_dir = final
        files = {p.name for p in actual_dir.iterdir() if p.is_file()}
        assert EXPECTED_OUTPUT_FILES.issubset(files)
        assert all((actual_dir / name).exists() for name in EXPECTED_OUTPUT_FILES)


# ============================================================================
# Comparison helper
# ============================================================================


class TestComparisonHelper:
    def test_compare_fails_on_mismatch(self) -> None:
        from medscale.dataset._pubmedqa_source import _record_to_envelope

        context = {
            "contexts": ["a"],
            "labels": ["x"],
            "meshes": [],
            "reasoning_required_pred": [],
            "reasoning_free_pred": [],
        }
        first = _row_to_source_record(1, "q", context, "a", "yes", 0)
        second = _row_to_source_record(2, "q", context, "a", "yes", 0)
        assert (
            _record_to_envelope(first)["source_record_hash"]
            != _record_to_envelope(second)["source_record_hash"]
        )


# ---------------------------------------------------------------------------
# Input-unchanged attestation (regression: the run report used to copy the
# pre-hash into sha256_post without recomputing, and nothing compared the
# recomputed post-hash to the pre-hash).
# ---------------------------------------------------------------------------


class TestInputAttestation:
    def test_post_hash_is_recomputed_and_attested(self, tmp_path: Path) -> None:
        from medscale.dataset._pubmedqa_source import transform_pubmedqa_parquet

        parquet = _write_synthetic_parquet(tmp_path / "input.parquet")
        expected = hashlib.sha256(parquet.read_bytes()).hexdigest()
        report = transform_pubmedqa_parquet(parquet, tmp_path / "out")
        assert report["input"]["sha256_pre"] == expected
        assert report["input"]["sha256_post"] == expected
        local = json.loads(
            (tmp_path / "out" / "transformation-run.local.json").read_text(encoding="utf-8")
        )
        assert local["input_sha256_pre"] == expected
        assert local["input_sha256_post"] == expected

    def test_input_mutation_during_transform_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import medscale.dataset._pubmedqa_source as source_module

        parquet = _write_synthetic_parquet(tmp_path / "input.parquet")
        real_sha256_file = source_module._sha256_file
        calls = {"count": 0}

        def unstable_sha256_file(path: Path) -> str:
            calls["count"] += 1
            if calls["count"] >= 2:  # post-transform recomputation
                return "0" * 64
            return real_sha256_file(path)

        monkeypatch.setattr(source_module, "_sha256_file", unstable_sha256_file)
        with pytest.raises(RuntimeError, match="changed during transformation"):
            source_module.transform_pubmedqa_parquet(parquet, tmp_path / "out")
        assert calls["count"] >= 2
