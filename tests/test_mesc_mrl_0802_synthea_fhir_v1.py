from __future__ import annotations

import json
from pathlib import Path

import pytest

from medscale.mesc._mrl_0802_synthea_fhir_v1 import (
    MRL0802SyntheaAuthorization,
    MRL0802SyntheaCorpusError,
    MRL0802SyntheaRightsReview,
    _require_external_empty_output,
    _require_pristine_git_tree,
    parse_mrl_0802_synthea_authorization,
    parse_mrl_0802_synthea_rights_review,
    qualify_mrl_0802_synthea_runs,
    synthea_generation_arguments,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import parse_mrl_real_preflight_evidence

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-corpus-authorization-v1.json"
RIGHTS = ROOT / "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-rights-review-v1.json"
AUTH_SHA256 = "d1aec2915d02da100cf7c941c3ecc89fb584bfb4cc8c3968ecff96bab382c291"
RIGHTS_SHA256 = "d9cd5e4ae17eb392060811890309b4ad69cd707ac953d6156a2ad18b9233b33f"


def _authorization() -> MRL0802SyntheaAuthorization:
    return parse_mrl_0802_synthea_authorization(AUTH.read_bytes())


def _rights() -> MRL0802SyntheaRightsReview:
    return parse_mrl_0802_synthea_rights_review(RIGHTS.read_bytes())


def _raw_patient(index: int, *, gender: str | None = None) -> bytes:
    patient = {
        "resourceType": "Patient",
        "id": f"synthea-{index:04d}",
        "gender": gender or ("male" if index % 2 else "female"),
        "birthDate": f"1980-01-{(index % 28) + 1:02d}",
        "address": [
            {
                "line": [f"{index} Synthetic Street"],
                "city": "Synthetic City",
                "state": "Massachusetts",
                "postalCode": f"02{index:03d}",
                "country": "US",
            }
        ],
        "name": [{"family": "Synthetic", "given": [f"Patient{index}"]}],
        "telecom": [{"system": "phone", "value": "555-0000"}],
        "identifier": [
            {
                "system": "http://hospital.example/identifier",
                "value": f"external-{index}",
            }
        ],
        "maritalStatus": {"coding": [{"system": "http://snomed.info/sct", "code": "123"}]},
        "extension": [
            {
                "url": "http://example.invalid/loinc",
                "valueCoding": {"system": "http://loinc.org", "code": "x"},
            }
        ],
    }
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [{"resource": patient}],
    }
    return json.dumps(bundle, separators=(",", ":")).encode("utf-8")


def _run() -> tuple[bytes, ...]:
    return tuple(_raw_patient(index) for index in range(16))


def test_exact_authorization_and_rights_artifacts_are_admitted() -> None:
    authorization = _authorization()
    rights = _rights()
    assert authorization.authorization_sha256 == AUTH_SHA256
    assert rights.rights_review_sha256 == RIGHTS_SHA256


def test_authorization_and_rights_mutation_fail_closed() -> None:
    with pytest.raises(MRL0802SyntheaCorpusError, match="canonical JSON"):
        parse_mrl_0802_synthea_authorization(AUTH.read_bytes() + b"\n")
    with pytest.raises(MRL0802SyntheaCorpusError, match="canonical JSON"):
        parse_mrl_0802_synthea_rights_review(RIGHTS.read_bytes() + b"\n")


def test_generation_arguments_are_exact_and_bounded(tmp_path: Path) -> None:
    arguments = synthea_generation_arguments(tmp_path)
    assert arguments[:10] == (
        "-s",
        "3910802",
        "-cs",
        "3910803",
        "-p",
        "16",
        "-r",
        "20260101",
        "-o",
        "false",
    )
    assert "--exporter.fhir.included_resources=Patient" in arguments
    assert "--exporter.fhir.use_us_core_ig=false" in arguments
    assert "--exporter.hospital.fhir.export=false" in arguments
    assert "--exporter.practitioner.fhir.export=false" in arguments
    assert arguments[-1] == "Massachusetts"


def test_two_identical_runs_produce_valid_mrl_0802_evidence() -> None:
    result = qualify_mrl_0802_synthea_runs(
        _run(),
        _run(),
        authorization=_authorization(),
        rights_review=_rights(),
    )
    parsed = parse_mrl_real_preflight_evidence(result.evidence_bytes)
    assert parsed.task_id == "MRL-0802"
    assert parsed.kind == "mesc.mrl.real_preflight.corpus_rights.v1"
    assert parsed.subject_sha256 == result.corpus_sha256
    assert len(result.record_ids) == 16
    assert result.record_ids[0] == "synthea-0000"
    assert result.record_ids[-1] == "synthea-0015"


def test_projection_strips_identity_and_external_terminology_content() -> None:
    result = qualify_mrl_0802_synthea_runs(
        _run(),
        _run(),
        authorization=_authorization(),
        rights_review=_rights(),
    )
    lowered = result.corpus_bytes.lower()
    for marker in (
        b"snomed",
        b"loinc",
        b"rxnorm",
        b'"coding"',
        b'"identifier"',
        b'"extension"',
        b'"telecom"',
        b'"name"',
        b"synthetic street",
    ):
        assert marker not in lowered
    records = [json.loads(line) for line in result.corpus_bytes.splitlines()]
    assert all(
        set(record) <= {"address", "birthDate", "gender", "id", "resourceType"}
        for record in records
    )
    assert all(
        set(record["address"][0]) <= {"city", "country", "postalCode", "state"}
        for record in records
    )


def test_rights_and_provenance_bind_exact_projected_corpus() -> None:
    result = qualify_mrl_0802_synthea_runs(
        _run(),
        _run(),
        authorization=_authorization(),
        rights_review=_rights(),
    )
    rights = json.loads(result.rights_bytes)
    provenance = json.loads(result.provenance_bytes)
    assert rights["rights_disposition"] == "PASS"
    assert rights["external_terminology_codings_in_admitted_projection"] is False
    assert rights["snomed_ct_vendored"] is False
    assert provenance["corpus_sha256"] == result.corpus_sha256
    assert provenance["byte_count"] == len(result.corpus_bytes)
    assert provenance["repeated_projection_byte_identity"] is True
    assert provenance["generation"]["population_size"] == 16


def test_repeated_generation_drift_fails_closed() -> None:
    second = list(_run())
    second[5] = _raw_patient(5, gender="unknown")
    with pytest.raises(MRL0802SyntheaCorpusError, match="not byte-identical"):
        qualify_mrl_0802_synthea_runs(
            _run(),
            second,
            authorization=_authorization(),
            rights_review=_rights(),
        )


def test_population_count_mismatch_fails_closed() -> None:
    short = _run()[:-1]
    with pytest.raises(MRL0802SyntheaCorpusError, match="population size"):
        qualify_mrl_0802_synthea_runs(
            short,
            short,
            authorization=_authorization(),
            rights_review=_rights(),
        )


def test_duplicate_patient_identity_fails_closed() -> None:
    duplicate = list(_run())
    duplicate[-1] = _raw_patient(0)
    with pytest.raises(MRL0802SyntheaCorpusError, match="unique"):
        qualify_mrl_0802_synthea_runs(
            duplicate,
            duplicate,
            authorization=_authorization(),
            rights_review=_rights(),
        )


def test_ignored_build_state_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "synthea"
    source.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(source), "config", "user.name", "test"], check=True)
    (source / ".gitignore").write_text("build/\n", encoding="utf-8")
    (source / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "base"], check=True)
    _require_pristine_git_tree(source)

    (source / "build").mkdir()
    (source / "build/cache.bin").write_bytes(b"stale")
    with pytest.raises(MRL0802SyntheaCorpusError, match="ignored or untracked build state"):
        _require_pristine_git_tree(source)


def test_external_output_rejects_symlink_traversal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    repository = tmp_path / "repo"
    target = tmp_path / "target"
    source.mkdir()
    repository.mkdir()
    target.mkdir()
    link = tmp_path / "linked-output"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(MRL0802SyntheaCorpusError, match="symbolic link"):
        _require_external_empty_output(
            link,
            source_root=source,
            repository_root=repository,
        )
