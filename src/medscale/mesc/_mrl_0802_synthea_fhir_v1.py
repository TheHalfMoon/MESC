"""Bounded Synthea FHIR corpus execution and qualification for MRL-0802.

The module binds one exact Synthea v4.0.0 checkout and one exact generation
configuration. It projects generated Patient resources onto a terminology-free
FHIR R4 structural surface, requires byte-identical projected output across two
runs, and emits path-free rights/provenance/evidence artifacts. It performs no
model loading, inference, GPU execution, training, or trust-registry mutation.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import (
    CanonicalContractError,
    canonical_json_bytes,
    canonical_jsonl_bytes,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

_AUTHORIZATION_SHA256: Final = "d1aec2915d02da100cf7c941c3ecc89fb584bfb4cc8c3968ecff96bab382c291"
_RIGHTS_REVIEW_SHA256: Final = "d9cd5e4ae17eb392060811890309b4ad69cd707ac953d6156a2ad18b9233b33f"
_SYNTHEA_REVISION: Final = "0185c09ea9d10a822c6f5f3ef9bdcbcbe960c813"
_SYNTHEA_TREE: Final = "3560f3c00eb6ae2a7e391f1d3b18241f4ce0b61f"
_FHIR_VERSION: Final = "4.0.1"
_PROJECTION_VERSION: Final = "MESC-MRL-0802-SYNTHEA-PATIENT-PROJECTION-V1"
_CORPUS_ID: Final = "mesc-synthea-v4.0.0-fhir-r4-patient-structural-v1"
_SEED: Final = 3910802
_CLINICIAN_SEED: Final = 3910803
_POPULATION_SIZE: Final = 16
_REFERENCE_DATE: Final = "20260101"
_STATE: Final = "Massachusetts"
_SOURCE_FILE_SHA256: Final[dict[str, str]] = {
    "LICENSE": "b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1",
    "NOTICE": "aefac5c5d632a0cf595688712eff8a45da0bdadc92c07718aef9876f2f346b97",
    "README.md": "674a227885066e2787dce85a04b4f39fd411f7e1f616e7c26fed10735929c8f1",
    "run_synthea": "7719d3fe0942f1fb219554af06179e70a98cbe9d748fb098f66574496bacbf24",
    "src/main/resources/synthea.properties": (
        "be7d6ba5a217423b94c7d28a307361e05ed3728f1544841282656565b8896920"
    ),
}


class MRL0802SyntheaCorpusError(ValueError):
    """Raised when Synthea corpus execution or qualification fails closed."""


@dataclass(frozen=True, slots=True)
class MRL0802SyntheaAuthorization:
    """Validated exact Synthea source/generation authorization."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="authorization")
        digest = hashlib.sha256(self.canonical_bytes).hexdigest()
        if digest != _AUTHORIZATION_SHA256:
            raise MRL0802SyntheaCorpusError(
                "authorization does not match the exact authorized scope"
            )
        _validate_authorization_document(document)
        object.__setattr__(self, "authorization_sha256", digest)


@dataclass(frozen=True, slots=True)
class MRL0802SyntheaRightsReview:
    """Validated exact source/standard rights review."""

    canonical_bytes: bytes = field(repr=False)
    rights_review_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes, label="rights review")
        digest = hashlib.sha256(self.canonical_bytes).hexdigest()
        if digest != _RIGHTS_REVIEW_SHA256:
            raise MRL0802SyntheaCorpusError("rights review does not match the exact reviewed scope")
        _validate_rights_document(document)
        object.__setattr__(self, "rights_review_sha256", digest)


@dataclass(frozen=True, slots=True)
class MRL0802SyntheaCorpusQualification:
    """Deterministic evidence candidate for one exact generated corpus."""

    corpus_bytes: bytes = field(repr=False)
    rights_bytes: bytes = field(repr=False)
    provenance_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    corpus_sha256: str
    rights_evidence_sha256: str
    provenance_sha256: str
    evidence_sha256: str
    record_ids: tuple[str, ...]
    raw_run_a_sha256: str
    raw_run_b_sha256: str


SyntheaRunner = Callable[[Path, Path], None]


def parse_mrl_0802_synthea_authorization(raw: bytes) -> MRL0802SyntheaAuthorization:
    """Parse the exact committed Synthea authorization bytes."""
    return MRL0802SyntheaAuthorization(raw)


def parse_mrl_0802_synthea_rights_review(raw: bytes) -> MRL0802SyntheaRightsReview:
    """Parse the exact committed rights-review bytes."""
    return MRL0802SyntheaRightsReview(raw)


def synthea_generation_arguments(output_root: Path) -> tuple[str, ...]:
    """Return the exact bounded Synthea CLI arguments, excluding the executable."""
    return (
        "-s",
        str(_SEED),
        "-cs",
        str(_CLINICIAN_SEED),
        "-p",
        str(_POPULATION_SIZE),
        "-r",
        _REFERENCE_DATE,
        "-o",
        "false",
        f"--exporter.baseDirectory={output_root}",
        "--exporter.ccda.export=false",
        "--exporter.cpcds.export=false",
        "--exporter.csv.export=false",
        "--exporter.fhir.bulk_data=false",
        "--exporter.fhir.export=true",
        "--exporter.fhir.included_resources=Patient",
        "--exporter.fhir.transaction_bundle=true",
        "--exporter.fhir.use_us_core_ig=false",
        "--exporter.hospital.fhir.export=false",
        "--exporter.practitioner.fhir.export=false",
        _STATE,
    )


def require_exact_synthea_checkout(source_root: Path) -> Path:
    """Require the exact clean authorized Synthea source checkout."""
    root = source_root.resolve(strict=True)
    if not (root / ".git").exists():
        raise MRL0802SyntheaCorpusError("Synthea source root is not a Git work tree")
    top = Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top != root:
        raise MRL0802SyntheaCorpusError("Synthea source root is not the exact Git work-tree root")
    _require_pristine_git_tree(root)
    if _git(root, "rev-parse", "HEAD") != _SYNTHEA_REVISION:
        raise MRL0802SyntheaCorpusError("Synthea source revision is not authorized")
    if _git(root, "rev-parse", "HEAD^{tree}") != _SYNTHEA_TREE:
        raise MRL0802SyntheaCorpusError("Synthea source tree is not authorized")
    for relative, expected in _SOURCE_FILE_SHA256.items():
        path = (root / relative).resolve(strict=True)
        if not path.is_file() or not _is_descendant(path, root):
            raise MRL0802SyntheaCorpusError("Synthea source file escaped the authorized root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise MRL0802SyntheaCorpusError(f"Synthea source file identity mismatch: {relative}")
    return root


def _require_pristine_git_tree(root: Path) -> None:
    tagged = _git(root, "ls-files", "-v", "-z")
    for record in tagged.split("\0"):
        if not record:
            continue
        tag = record[0]
        if tag == "S" or tag.islower():
            raise MRL0802SyntheaCorpusError(
                "Synthea source work tree contains an unsafe Git index flag"
            )
    for arguments in (
        ("diff-files", "--quiet", "--"),
        ("diff-index", "--cached", "--quiet", "HEAD", "--"),
    ):
        completed = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise MRL0802SyntheaCorpusError(
                "Synthea tracked worktree bytes must match the exact HEAD tree"
            )
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise MRL0802SyntheaCorpusError("Synthea source work tree must be clean")
    if _git(root, "clean", "-ndx"):
        raise MRL0802SyntheaCorpusError(
            "Synthea source work tree must contain no ignored or untracked build state"
        )


def _clone_exact_synthea_source(source: Path, destination: Path) -> Path:
    """Create one disposable pristine clone for a single generation run."""
    if destination.exists() or destination.is_symlink():
        raise MRL0802SyntheaCorpusError("disposable Synthea source destination already exists")
    try:
        completed = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                str(source),
                str(destination),
            ],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise MRL0802SyntheaCorpusError("disposable Synthea source clone failed")
        checkout = subprocess.run(
            [
                "git",
                "-C",
                str(destination),
                "checkout",
                "--quiet",
                "--detach",
                _SYNTHEA_REVISION,
            ],
            check=False,
            capture_output=True,
        )
        if checkout.returncode != 0:
            raise MRL0802SyntheaCorpusError("disposable Synthea source checkout failed")
        return require_exact_synthea_checkout(destination)
    except BaseException:
        if destination.is_symlink():
            destination.unlink()
        elif destination.exists():
            shutil.rmtree(destination, ignore_errors=False)
        raise


def _require_tracked_source_unchanged(root: Path) -> None:
    """Require execution to leave tracked worktree and index state at the authorized revision."""
    tagged = _git(root, "ls-files", "-v", "-z")
    for record in tagged.split("\0"):
        if not record:
            continue
        tag = record[0]
        if tag == "S" or tag.islower():
            raise MRL0802SyntheaCorpusError("Synthea execution introduced an unsafe Git index flag")
    for arguments in (
        ("diff-files", "--quiet", "--ignore-submodules", "--"),
        ("diff-index", "--cached", "--quiet", "HEAD", "--"),
    ):
        completed = subprocess.run(
            ["git", "-C", str(root), "-c", "core.filemode=true", *arguments],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            raise MRL0802SyntheaCorpusError("Synthea execution mutated tracked source bytes")
    if _git(root, "rev-parse", "HEAD") != _SYNTHEA_REVISION:
        raise MRL0802SyntheaCorpusError("Synthea execution changed source revision")
    if _git(root, "rev-parse", "HEAD^{tree}") != _SYNTHEA_TREE:
        raise MRL0802SyntheaCorpusError("Synthea execution changed source tree identity")


def _remove_disposable_synthea_sources(sources: Sequence[Path | None]) -> None:
    """Attempt cleanup of every transaction-owned source clone and fail closed afterward."""
    cleanup_errors: list[OSError] = []
    for source in sources:
        if source is None:
            continue
        try:
            if source.is_symlink():
                source.unlink()
            elif source.exists():
                shutil.rmtree(source, ignore_errors=False)
        except OSError as exc:
            cleanup_errors.append(exc)
    if cleanup_errors:
        raise MRL0802SyntheaCorpusError(
            "disposable Synthea source cleanup failed"
        ) from cleanup_errors[0]


def run_authorized_synthea_corpus(
    *,
    source_root: Path,
    output_root: Path,
    authorization: MRL0802SyntheaAuthorization,
    rights_review: MRL0802SyntheaRightsReview,
    repository_root: Path | None = None,
    runner: SyntheaRunner | None = None,
) -> MRL0802SyntheaCorpusQualification:
    """Run two isolated pristine Synthea generations and qualify projected identity."""
    if type(authorization) is not MRL0802SyntheaAuthorization:
        raise MRL0802SyntheaCorpusError("authorization type is invalid")
    if type(rights_review) is not MRL0802SyntheaRightsReview:
        raise MRL0802SyntheaCorpusError("rights review type is invalid")
    source = require_exact_synthea_checkout(source_root)
    output = _require_external_empty_output(
        output_root, source_root=source, repository_root=repository_root
    )
    run_a = output / "run-a"
    run_b = output / "run-b"
    run_a.mkdir()
    run_b.mkdir()
    source_a: Path | None = None
    source_b: Path | None = None
    execute = runner or _subprocess_synthea_runner
    try:
        source_a = _clone_exact_synthea_source(source, output / ".source-run-a")
        source_b = _clone_exact_synthea_source(source, output / ".source-run-b")
        execute(source_a, run_a)
        _require_tracked_source_unchanged(source_a)
        execute(source_b, run_b)
        _require_tracked_source_unchanged(source_b)
        first_files = _read_fhir_outputs(run_a)
        second_files = _read_fhir_outputs(run_b)
    finally:
        _remove_disposable_synthea_sources((source_a, source_b))
    return qualify_mrl_0802_synthea_runs(
        first_files,
        second_files,
        authorization=authorization,
        rights_review=rights_review,
    )


def qualify_mrl_0802_synthea_runs(
    run_a_files: Sequence[bytes],
    run_b_files: Sequence[bytes],
    *,
    authorization: MRL0802SyntheaAuthorization,
    rights_review: MRL0802SyntheaRightsReview,
) -> MRL0802SyntheaCorpusQualification:
    """Qualify two generated runs without performing network or process execution."""
    if type(authorization) is not MRL0802SyntheaAuthorization:
        raise MRL0802SyntheaCorpusError("authorization type is invalid")
    if type(rights_review) is not MRL0802SyntheaRightsReview:
        raise MRL0802SyntheaCorpusError("rights review type is invalid")
    corpus_a, ids_a = _project_run(run_a_files)
    corpus_b, ids_b = _project_run(run_b_files)
    if corpus_a != corpus_b or ids_a != ids_b:
        raise MRL0802SyntheaCorpusError(
            "repeated Synthea generation is not byte-identical after projection"
        )
    if len(ids_a) != _POPULATION_SIZE:
        raise MRL0802SyntheaCorpusError(
            "projected corpus does not contain the authorized population size"
        )

    corpus_sha256 = hashlib.sha256(corpus_a).hexdigest()
    raw_a_sha256 = _raw_run_identity(run_a_files)
    raw_b_sha256 = _raw_run_identity(run_b_files)
    rights_bytes = canonical_json_bytes(
        {
            "schema_version": "MESC-MRL-0802-SYNTHEA-CORPUS-RIGHTS-EVIDENCE-V1",
            "corpus_sha256": corpus_sha256,
            "rights_review_sha256": rights_review.rights_review_sha256,
            "source_software_license_spdx": "Apache-2.0",
            "fhir_core_license_spdx": "CC0-1.0",
            "synthetic_only": True,
            "phi_present": False,
            "real_patient_data_present": False,
            "credentialed_source_used": False,
            "external_terminology_codings_in_admitted_projection": False,
            "snomed_ct_vendored": False,
            "loinc_content_vendored": False,
            "rxnorm_content_vendored": False,
            "derivative_model_use": True,
            "commercial_use": True,
            "rights_disposition": "PASS",
        }
    )
    rights_sha256 = hashlib.sha256(rights_bytes).hexdigest()
    provenance_bytes = canonical_json_bytes(
        {
            "schema_version": "MESC-MRL-0802-SYNTHEA-PROVENANCE-V1",
            "access_authorization_sha256": authorization.authorization_sha256,
            "rights_review_sha256": rights_review.rights_review_sha256,
            "source": {
                "repository": "https://github.com/synthetichealth/synthea.git",
                "revision": _SYNTHEA_REVISION,
                "tree": _SYNTHEA_TREE,
                "file_sha256": dict(sorted(_SOURCE_FILE_SHA256.items())),
            },
            "generation": {
                "seed": _SEED,
                "clinician_seed": _CLINICIAN_SEED,
                "population_size": _POPULATION_SIZE,
                "reference_date": _REFERENCE_DATE,
                "state": _STATE,
                "fhir_version": _FHIR_VERSION,
            },
            "projection_schema_version": _PROJECTION_VERSION,
            "record_ids": list(ids_a),
            "record_count": len(ids_a),
            "byte_count": len(corpus_a),
            "corpus_sha256": corpus_sha256,
            "raw_run_a_sha256": raw_a_sha256,
            "raw_run_b_sha256": raw_b_sha256,
            "repeated_projection_byte_identity": True,
        }
    )
    provenance_sha256 = hashlib.sha256(provenance_bytes).hexdigest()
    evidence_bytes = canonical_json_bytes(
        {
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "task_id": "MRL-0802",
            "kind": "mesc.mrl.real_preflight.corpus_rights.v1",
            "disposition": "PASS",
            "subject_sha256": corpus_sha256,
            "payload": {
                "access_authorization_sha256": authorization.authorization_sha256,
                "byte_count": len(corpus_a),
                "corpus_id": _CORPUS_ID,
                "corpus_present": True,
                "corpus_sha256": corpus_sha256,
                "provenance_sha256": provenance_sha256,
                "rights_disposition": "PASS",
                "rights_evidence_sha256": rights_sha256,
            },
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != "MRL-0802" or parsed.subject_sha256 != corpus_sha256:
        raise MRL0802SyntheaCorpusError("generated MRL-0802 evidence failed semantic binding")
    return MRL0802SyntheaCorpusQualification(
        corpus_bytes=corpus_a,
        rights_bytes=rights_bytes,
        provenance_bytes=provenance_bytes,
        evidence_bytes=evidence_bytes,
        corpus_sha256=corpus_sha256,
        rights_evidence_sha256=rights_sha256,
        provenance_sha256=provenance_sha256,
        evidence_sha256=parsed.evidence_sha256,
        record_ids=ids_a,
        raw_run_a_sha256=raw_a_sha256,
        raw_run_b_sha256=raw_b_sha256,
    )


def _project_run(raw_files: Sequence[bytes]) -> tuple[bytes, tuple[str, ...]]:
    if not raw_files:
        raise MRL0802SyntheaCorpusError("Synthea run produced no FHIR bytes")
    patients: list[dict[str, object]] = []
    for raw in raw_files:
        patients.extend(_extract_patients(raw))
    projected = [_project_patient(patient) for patient in patients]
    ids = [cast(str, item["id"]) for item in projected]
    if len(ids) != len(set(ids)):
        raise MRL0802SyntheaCorpusError("projected Patient ids must be unique")
    ordered = sorted(projected, key=lambda item: cast(str, item["id"]))
    ordered_ids = tuple(cast(str, item["id"]) for item in ordered)
    corpus = canonical_jsonl_bytes(ordered)
    _assert_projection_has_no_external_terminology(corpus)
    return corpus, ordered_ids


def _extract_patients(raw: bytes) -> list[dict[str, object]]:
    document = _parse_json_object(raw, label="Synthea FHIR output")
    if document.get("resourceType") == "Patient":
        return [document]
    if document.get("resourceType") != "Bundle":
        return []
    entries = document.get("entry")
    if type(entries) is not list:
        raise MRL0802SyntheaCorpusError("FHIR Bundle entry must be an array")
    patients: list[dict[str, object]] = []
    for entry in entries:
        if type(entry) is not dict:
            raise MRL0802SyntheaCorpusError("FHIR Bundle entry must be an object")
        resource = entry.get("resource")
        if type(resource) is dict and resource.get("resourceType") == "Patient":
            patients.append(cast(dict[str, object], resource))
    return patients


def _project_patient(patient: dict[str, object]) -> dict[str, object]:
    patient_id = patient.get("id")
    if type(patient_id) is not str or not patient_id.strip():
        raise MRL0802SyntheaCorpusError("Patient id must be a non-blank string")
    projected: dict[str, object] = {"resourceType": "Patient", "id": patient_id}
    for primitive in ("gender", "birthDate", "deceasedBoolean"):
        value = patient.get(primitive)
        if type(value) in (str, bool):
            projected[primitive] = value
    addresses = patient.get("address")
    if type(addresses) is list:
        clean_addresses: list[dict[str, str]] = []
        for address in addresses:
            if type(address) is not dict:
                continue
            clean = {
                key: cast(str, address[key])
                for key in ("city", "country", "postalCode", "state")
                if type(address.get(key)) is str and cast(str, address[key]).strip()
            }
            if clean:
                clean_addresses.append(clean)
        if clean_addresses:
            projected["address"] = clean_addresses
    return projected


def _assert_projection_has_no_external_terminology(corpus: bytes) -> None:
    lowered = corpus.lower()
    prohibited = (
        b"snomed",
        b"loinc",
        b"rxnorm",
        b"http://snomed.info/sct",
        b"http://loinc.org",
        b"http://www.nlm.nih.gov/research/umls/rxnorm",
        b'"coding"',
        b'"identifier"',
        b'"extension"',
        b'"telecom"',
        b'"name"',
    )
    if any(marker in lowered for marker in prohibited):
        raise MRL0802SyntheaCorpusError(
            "admitted projection contains prohibited identity or terminology content"
        )


def _raw_run_identity(raw_files: Sequence[bytes]) -> str:
    manifest = sorted(
        ({"byte_count": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for raw in raw_files),
        key=lambda item: (cast(str, item["sha256"]), cast(int, item["byte_count"])),
    )
    return hashlib.sha256(canonical_json_bytes(manifest)).hexdigest()


def _subprocess_synthea_runner(source_root: Path, output_root: Path) -> None:
    command = [str(source_root / "run_synthea"), *synthea_generation_arguments(output_root)]
    environment = os.environ.copy()
    environment["GRADLE_USER_HOME"] = str(source_root / ".gradle-user-home")
    completed = subprocess.run(
        command,
        cwd=source_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        env=environment,
    )
    if completed.returncode != 0:
        raise MRL0802SyntheaCorpusError("Synthea generation failed")


def _read_fhir_outputs(run_root: Path) -> tuple[bytes, ...]:
    fhir_root = run_root / "fhir"
    if not fhir_root.is_dir():
        raise MRL0802SyntheaCorpusError("Synthea run produced no FHIR output directory")
    files = tuple(sorted(path for path in fhir_root.glob("*.json") if path.is_file()))
    if not files:
        raise MRL0802SyntheaCorpusError("Synthea run produced no FHIR JSON files")
    return tuple(path.read_bytes() for path in files)


def _require_external_empty_output(
    output_root: Path,
    *,
    source_root: Path,
    repository_root: Path | None,
) -> Path:
    raw_output = output_root.expanduser().absolute()
    if raw_output.is_symlink() or any(parent.is_symlink() for parent in raw_output.parents):
        raise MRL0802SyntheaCorpusError("output root must not traverse a symbolic link")
    output = raw_output.resolve(strict=True)
    if not output.is_dir():
        raise MRL0802SyntheaCorpusError("output root must be a real directory")
    protected = [source_root.resolve(strict=True)]
    if repository_root is not None:
        protected.append(repository_root.resolve(strict=True))
    if any(output == root or _is_descendant(output, root) for root in protected):
        raise MRL0802SyntheaCorpusError("output root must be outside Git source repositories")
    if any(output.iterdir()):
        raise MRL0802SyntheaCorpusError("output root must be empty before execution")
    return output


def _validate_authorization_document(document: dict[str, object]) -> None:
    if document.get("schema_version") != "MESC-MRL-0802-SYNTHETIC-FHIR-CORPUS-AUTHORIZATION-V1":
        raise MRL0802SyntheaCorpusError("authorization schema_version is invalid")
    if document.get("scope") != "MRL-0802_SYNTHETIC_FHIR_CORPUS_ONLY":
        raise MRL0802SyntheaCorpusError("authorization scope is invalid")
    source = _require_object(document.get("source"), label="source")
    generation = _require_object(document.get("generation"), label="generation")
    policy = _require_object(document.get("policy"), label="policy")
    projection = _require_object(document.get("projection"), label="projection")
    if source.get("revision") != _SYNTHEA_REVISION or source.get("tree") != _SYNTHEA_TREE:
        raise MRL0802SyntheaCorpusError("authorization Synthea identity is invalid")
    expected_generation = {
        "seed": _SEED,
        "clinician_seed": _CLINICIAN_SEED,
        "population_size": _POPULATION_SIZE,
        "reference_date": _REFERENCE_DATE,
        "state": _STATE,
        "fhir_version": _FHIR_VERSION,
    }
    for key, expected in expected_generation.items():
        if generation.get(key) != expected:
            raise MRL0802SyntheaCorpusError(f"authorization generation field is invalid: {key}")
    if projection.get("projection_schema_version") != _PROJECTION_VERSION:
        raise MRL0802SyntheaCorpusError("authorization projection identity is invalid")
    if projection.get("corpus_id") != _CORPUS_ID:
        raise MRL0802SyntheaCorpusError("authorization corpus identity is invalid")
    required_false = (
        "credentialed_sources_authorized",
        "gpu_execution_authorized",
        "inference_authorized",
        "model_loading_authorized",
        "mrl_0802_population_authorized",
        "phi_authorized",
        "production_trust_registry_mutation_authorized",
        "real_patient_sources_authorized",
        "snomed_ct_vendoring_authorized",
        "training_authorized",
        "weight_mutation_authorized",
    )
    if policy.get("synthetic_only") is not True or any(
        policy.get(key) is not False for key in required_false
    ):
        raise MRL0802SyntheaCorpusError("authorization policy expands prohibited authority")


def _validate_rights_document(document: dict[str, object]) -> None:
    if document.get("schema_version") != "MESC-MRL-0802-SYNTHETIC-FHIR-RIGHTS-REVIEW-V1":
        raise MRL0802SyntheaCorpusError("rights review schema_version is invalid")
    if document.get("disposition") != "PASS_FOR_PROJECTED_PATIENT_STRUCTURAL_CORPUS_ONLY":
        raise MRL0802SyntheaCorpusError("rights review disposition is invalid")
    policy = _require_object(document.get("policy"), label="rights policy")
    required_true = ("synthetic_only", "derivative_model_use_required")
    required_false = (
        "external_terminology_codings_in_admitted_projection",
        "loinc_content_vendored",
        "phi_present",
        "real_patient_data_present",
        "rxnorm_content_vendored",
        "snomed_ct_vendored",
    )
    if any(policy.get(key) is not True for key in required_true):
        raise MRL0802SyntheaCorpusError("rights review lacks required positive disposition")
    if any(policy.get(key) is not False for key in required_false):
        raise MRL0802SyntheaCorpusError("rights review admits prohibited content")
    fhir_core = _require_object(document.get("fhir_core"), label="FHIR core")
    if fhir_core.get("version") != _FHIR_VERSION or fhir_core.get("license_spdx") != "CC0-1.0":
        raise MRL0802SyntheaCorpusError("FHIR core rights identity is invalid")


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0802SyntheaCorpusError(f"{label} must be non-empty exact bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(parsed) is not dict:
            raise MRL0802SyntheaCorpusError(f"{label} must be a JSON object")
        document = cast(dict[str, object], parsed)
        canonical = canonical_json_bytes(document)
    except MRL0802SyntheaCorpusError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError, CanonicalContractError) as exc:
        raise MRL0802SyntheaCorpusError(f"{label} must be valid canonical UTF-8 JSON") from exc
    if canonical != raw:
        raise MRL0802SyntheaCorpusError(f"{label} bytes are not canonical JSON")
    return document


def _parse_json_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0802SyntheaCorpusError(f"{label} must be non-empty bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise MRL0802SyntheaCorpusError(f"{label} must be valid UTF-8 JSON") from exc
    if type(parsed) is not dict:
        raise MRL0802SyntheaCorpusError(f"{label} must be a JSON object")
    return cast(dict[str, object], parsed)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0802SyntheaCorpusError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise MRL0802SyntheaCorpusError(f"non-standard JSON constant is prohibited: {value}")


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0802SyntheaCorpusError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _git(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise MRL0802SyntheaCorpusError("Git source identity cannot be resolved")
    return completed.stdout.strip()


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True
