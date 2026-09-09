from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

import medscale.mesc._mrl_0802_synthea_fhir_v1 as synthea
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


def _load_synthea_cli() -> ModuleType:
    """Load the qualification CLI under an isolated module identity for regression tests."""
    script = ROOT / "scripts/mesc_mrl_0802_synthea_qualify.py"
    spec = importlib.util.spec_from_file_location("mesc_mrl_0802_synthea_cli_test", script)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load Synthea qualification CLI")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _fake_synthea_checkout(tmp_path: Path) -> tuple[Path, str, str, dict[str, str]]:
    source = tmp_path / "synthea"
    source.mkdir()
    files = {
        "LICENSE": b"license\n",
        "NOTICE": b"notice\n",
        "README.md": b"readme\n",
        "run_synthea": b"#!/bin/sh\nexit 0\n",
        "src/main/resources/synthea.properties": b"property=value\n",
    }
    (source / ".gitignore").write_text("build/\n.gradle/\n", encoding="utf-8")
    for relative, payload in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD^{tree}"], text=True
    ).strip()
    hashes = {relative: hashlib.sha256(payload).hexdigest() for relative, payload in files.items()}
    return source, revision, tree, hashes


def _install_fake_synthea_identity(
    monkeypatch: pytest.MonkeyPatch, revision: str, tree: str, hashes: dict[str, str]
) -> None:
    monkeypatch.setattr(synthea, "_SYNTHEA_REVISION", revision)
    monkeypatch.setattr(synthea, "_SYNTHEA_TREE", tree)
    monkeypatch.setattr(synthea, "_SOURCE_FILE_SHA256", hashes)


def _write_fake_synthea_output(output: Path) -> None:
    fhir = output / "fhir"
    fhir.mkdir()
    for index, payload in enumerate(_run()):
        (fhir / f"patient-{index:04d}.json").write_bytes(payload)


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


def test_authorized_execution_uses_distinct_pristine_disposable_source_clones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorization = _authorization()
    rights = _rights()
    source, revision, tree, hashes = _fake_synthea_checkout(tmp_path)
    _install_fake_synthea_identity(monkeypatch, revision, tree, hashes)
    output = tmp_path / "output"
    output.mkdir()
    observed_sources: list[Path] = []

    def runner(run_source: Path, run_output: Path) -> None:
        observed_sources.append(run_source)
        assert run_source != source
        assert not (run_source / "build" / "run-a-residue").exists()
        build = run_source / "build"
        build.mkdir()
        marker = "run-a-residue" if len(observed_sources) == 1 else "run-b-residue"
        (build / marker).write_text("generated\n", encoding="utf-8")
        _write_fake_synthea_output(run_output)

    result = synthea.run_authorized_synthea_corpus(
        source_root=source,
        output_root=output,
        authorization=authorization,
        rights_review=rights,
        runner=runner,
    )

    assert len(observed_sources) == 2
    assert observed_sources[0] != observed_sources[1]
    assert all(not path.exists() for path in observed_sources)
    assert result.record_ids == tuple(f"synthea-{index:04d}" for index in range(16))


def test_authorized_execution_cleans_disposable_clone_after_runner_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorization = _authorization()
    rights = _rights()
    source, revision, tree, hashes = _fake_synthea_checkout(tmp_path)
    _install_fake_synthea_identity(monkeypatch, revision, tree, hashes)
    output = tmp_path / "output"
    output.mkdir()
    observed_sources: list[Path] = []

    def runner(run_source: Path, run_output: Path) -> None:
        del run_output
        observed_sources.append(run_source)
        raise MRL0802SyntheaCorpusError("synthetic runner failure")

    with pytest.raises(MRL0802SyntheaCorpusError, match="synthetic runner failure"):
        synthea.run_authorized_synthea_corpus(
            source_root=source,
            output_root=output,
            authorization=authorization,
            rights_review=rights,
            runner=runner,
        )
    assert len(observed_sources) == 1
    assert not observed_sources[0].exists()


def test_authorized_execution_rejects_post_run_tracked_source_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    authorization = _authorization()
    rights = _rights()
    source, revision, tree, hashes = _fake_synthea_checkout(tmp_path)
    _install_fake_synthea_identity(monkeypatch, revision, tree, hashes)
    output = tmp_path / "output"
    output.mkdir()
    observed_sources: list[Path] = []

    def runner(run_source: Path, run_output: Path) -> None:
        observed_sources.append(run_source)
        (run_source / "README.md").write_text("mutated\n", encoding="utf-8")
        _write_fake_synthea_output(run_output)

    with pytest.raises(MRL0802SyntheaCorpusError, match="tracked worktree bytes"):
        synthea.run_authorized_synthea_corpus(
            source_root=source,
            output_root=output,
            authorization=authorization,
            rights_review=rights,
            runner=runner,
        )
    assert len(observed_sources) == 1
    assert not observed_sources[0].exists()


def test_ignored_build_state_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "synthea"
    source.mkdir()

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


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_unsafe_tracked_index_flags_fail_closed(tmp_path: Path, flag: str) -> None:
    source = tmp_path / "synthea"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True
    )
    subprocess.run(["git", "-C", str(source), "config", "user.name", "test"], check=True)
    tracked = source / "tracked.txt"
    tracked.write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "base"], check=True)
    subprocess.run(["git", "-C", str(source), "update-index", flag, "tracked.txt"], check=True)
    tracked.write_text("foreign\n", encoding="utf-8")
    with pytest.raises(MRL0802SyntheaCorpusError, match="unsafe Git index flag"):
        _require_pristine_git_tree(source)


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_repository_preimport_rejects_hidden_medscale_mutation(tmp_path: Path, flag: str) -> None:
    cli = _load_synthea_cli()
    repository = tmp_path / "mesc"
    package_file = repository / "src/medscale/__init__.py"
    module_file = repository / "src/medscale/mesc/_mrl_0802_synthea_fhir_v1.py"
    auth_relative = Path(
        "specs/mesc-experiment-0/mrl-0802-synthetic-fhir-corpus-authorization-v1.json"
    )
    rights_relative = Path("specs/mesc-experiment-0/mrl-0802-synthetic-fhir-rights-review-v1.json")
    auth_file = repository / auth_relative
    rights_file = repository / rights_relative
    for path in (package_file, module_file, auth_file, rights_file):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("committed\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "add", "-f", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=test",
            "-c",
            "user.email=test@example.com",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "base",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repository), "update-index", flag, "src/medscale/__init__.py"],
        check=True,
    )
    package_file.write_text("foreign code\n", encoding="utf-8")

    with pytest.raises(cli.EntrypointError, match="unsafe Git index flag"):
        cli._require_clean_repository(repository)


def test_operational_evidence_binds_exact_mesc_git_identity() -> None:
    cli = _load_synthea_cli()
    repository_commit, repository_tree = cli._require_authorized_repository_identity(
        ROOT, AUTH.read_bytes()
    )
    result = qualify_mrl_0802_synthea_runs(
        _run(), _run(), authorization=_authorization(), rights_review=_rights()
    )
    provenance_bytes, evidence_bytes, provenance_sha256, evidence_sha256 = (
        cli._bind_repository_identity(
            result.provenance_bytes,
            result.evidence_bytes,
            repository_commit=repository_commit,
            repository_tree=repository_tree,
        )
    )
    provenance = json.loads(provenance_bytes)
    evidence = json.loads(evidence_bytes)
    assert provenance["mesc_executor"] == {
        "repository": "TheHalfMoon/MESC",
        "commit": repository_commit,
        "tree": repository_tree,
    }
    assert evidence["payload"]["provenance_sha256"] == provenance_sha256
    assert hashlib.sha256(evidence_bytes).hexdigest() == evidence_sha256


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
