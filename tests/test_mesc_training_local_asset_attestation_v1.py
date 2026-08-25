"""Tests for fail-closed local MESC training-asset attestation."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from medscale.mesc._training_corpus_binding_v1 import (
    TrainingCorpusBindingDisposition,
    TrainingCorpusBindingReport,
)
from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlan,
    TrainingRole,
    TrainingRunPlan,
)
from medscale.mesc._training_local_asset_attestation_v1 import (
    LocalModelAssetObservation,
    TrainingLocalAssetAttestationError,
    TrainingLocalAssetAttestationReport,
    attest_local_training_assets,
)
from medscale.modelkit.manifests import RunnerClass

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_GIT_A = "1" * 40
_GIT_B = "2" * 40


def _run(role: TrainingRole) -> TrainingRunPlan:
    suffix = role
    return TrainingRunPlan(
        role=role,
        experiment_id=f"train-{suffix}",
        rq_refs=("RQ1",),
        recipe_id=_SHA_A,
        model_id=f"example/{suffix}",
        revision=_GIT_A if role == "compact" else _GIT_B,
        weights_sha256=_SHA_B if role == "compact" else _SHA_C,
        training_dataset_sha256=_SHA_D,
        seeds=(7,),
        runner_class=RunnerClass.LOCAL,
        python_version="3.11",
        os_name="linux",
        gpu_model="test-gpu",
        dependency_lock_sha256=_SHA_A,
        repository_sha=_GIT_A,
        repository_tree=_GIT_B,
        result_paths=(f"artifacts/{suffix}/metrics.json",),
        reproduction_command=f"medscale mesc train {suffix}",
    )


def _launch() -> TrainingLaunchPlan:
    return TrainingLaunchPlan(
        readiness_manifest_sha256=_SHA_A,
        runtime_qualification_sha256=_SHA_B,
        training_authorization_receipt_sha256=_SHA_C,
        compact=_run("compact"),
        reasoner=_run("reasoner"),
    )


def _binding(
    raw: bytes,
    *,
    disposition: TrainingCorpusBindingDisposition = "PASS",
) -> TrainingCorpusBindingReport:
    blockers = () if disposition == "PASS" else ("blocked",)
    return TrainingCorpusBindingReport(
        disposition=disposition,
        qualification_sha256=_SHA_A,
        training_dataset_sha256=_SHA_D,
        qualified_training_record_ids_sha256=_SHA_B,
        corpus_sha256=_SHA_C,
        corpus_training_record_ids_sha256=_SHA_B,
        canonical_jsonl_sha256=hashlib.sha256(raw).hexdigest(),
        canonical_jsonl_byte_count=len(raw),
        example_count=1,
        blockers=blockers,
    )


class _Verifier:
    def __init__(
        self,
        *,
        network_accessed: bool = False,
        remote_code_allowed: bool = False,
        gated_terms_accepted: bool = False,
        wrong_weights: bool = False,
    ) -> None:
        self.network_accessed = network_accessed
        self.remote_code_allowed = remote_code_allowed
        self.gated_terms_accepted = gated_terms_accepted
        self.wrong_weights = wrong_weights
        self.calls = 0

    def verify(
        self,
        *,
        role: TrainingRole,
        model_root: Path,
        run_plan: TrainingRunPlan,
    ) -> LocalModelAssetObservation:
        self.calls += 1
        assert model_root.is_dir()
        return LocalModelAssetObservation(
            role=role,
            model_id=run_plan.model_id,
            revision=run_plan.revision,
            weights_sha256=_SHA_A if self.wrong_weights else run_plan.weights_sha256,
            verifier_id="fixture-local-verifier",
            verifier_version="v1",
            verifier_receipt_sha256=_SHA_D,
            network_accessed=self.network_accessed,
            remote_code_allowed=self.remote_code_allowed,
            gated_terms_accepted=self.gated_terms_accepted,
        )


def _paths(tmp_path: Path, raw: bytes) -> tuple[Path, Path]:
    model_root = tmp_path / "model"
    model_root.mkdir()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    return model_root, corpus_path


def _attest(
    tmp_path: Path,
    raw: bytes,
    verifier: _Verifier | None = None,
) -> TrainingLocalAssetAttestationReport:
    model_root, corpus_path = _paths(tmp_path, raw)
    return attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(raw),
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=_Verifier() if verifier is None else verifier,
    )


def test_exact_local_assets_pass_and_paths_do_not_change_identity(tmp_path: Path) -> None:
    raw = b'{"example":"one"}\n'
    verifier = _Verifier()
    report = _attest(tmp_path, raw, verifier)

    assert report.disposition == "PASS"
    assert report.can_execute_training is True
    assert report.observed_weights_sha256 == _SHA_B
    assert report.observed_corpus_sha256 == hashlib.sha256(raw).hexdigest()
    assert report.observed_corpus_byte_count == len(raw)
    assert verifier.calls == 1

    other = tmp_path / "other"
    other.mkdir()
    other_report = _attest(other, raw)
    assert other_report.attestation_sha256 == report.attestation_sha256


def test_corpus_content_and_size_mismatch_block(tmp_path: Path) -> None:
    expected = b'{"example":"one"}\n'
    actual = b'{"example":"tampered"}\n'
    model_root, corpus_path = _paths(tmp_path, actual)
    report = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(expected),
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=_Verifier(),
    )
    assert report.disposition == "BLOCKED"
    assert any("corpus SHA" in item for item in report.blockers)
    assert any("corpus byte count" in item for item in report.blockers)


def test_missing_paths_fail_closed_without_model_verification(tmp_path: Path) -> None:
    raw = b'{"example":"one"}\n'
    verifier = _Verifier()
    report = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(raw),
        role="compact",
        model_root=tmp_path / "missing-model",
        corpus_path=tmp_path / "missing-corpus",
        verifier=verifier,
    )
    assert report.disposition == "BLOCKED"
    assert verifier.calls == 0
    assert report.observed_weights_sha256 is None
    assert report.observed_corpus_sha256 is None


def test_blocked_binding_and_dataset_mismatch_cannot_pass(tmp_path: Path) -> None:
    raw = b'{"example":"one"}\n'
    model_root, corpus_path = _paths(tmp_path, raw)
    blocked = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(raw, disposition="BLOCKED"),
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=_Verifier(),
    )
    assert blocked.disposition == "BLOCKED"
    assert "corpus binding is not PASS" in blocked.blockers

    mismatch_binding = replace(_binding(raw), training_dataset_sha256=_SHA_A)
    mismatch = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=mismatch_binding,
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=_Verifier(),
    )
    assert mismatch.disposition == "BLOCKED"
    assert any("training dataset" in item for item in mismatch.blockers)


def test_model_identity_mismatch_blocks(tmp_path: Path) -> None:
    report = _attest(
        tmp_path,
        b'{"example":"one"}\n',
        _Verifier(wrong_weights=True),
    )
    assert report.disposition == "BLOCKED"
    assert any("weights_sha256" in item for item in report.blockers)


@pytest.mark.parametrize(
    ("network_accessed", "remote_code_allowed", "gated_terms_accepted", "fragment"),
    [
        (True, False, False, "network"),
        (False, True, False, "remote code"),
        (False, False, True, "gated terms"),
    ],
)
def test_security_observations_block(
    tmp_path: Path,
    network_accessed: bool,
    remote_code_allowed: bool,
    gated_terms_accepted: bool,
    fragment: str,
) -> None:
    verifier = _Verifier(
        network_accessed=network_accessed,
        remote_code_allowed=remote_code_allowed,
        gated_terms_accepted=gated_terms_accepted,
    )
    report = _attest(tmp_path, b'{"example":"one"}\n', verifier)
    assert report.disposition == "BLOCKED"
    assert any(fragment in item for item in report.blockers)


def test_verifier_exception_and_subclass_observation_fail_closed(tmp_path: Path) -> None:
    raw = b'{"example":"one"}\n'
    model_root, corpus_path = _paths(tmp_path, raw)

    class BrokenVerifier:
        def verify(
            self,
            *,
            role: TrainingRole,
            model_root: Path,
            run_plan: TrainingRunPlan,
        ) -> LocalModelAssetObservation:
            raise RuntimeError("boom")

    broken = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(raw),
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=BrokenVerifier(),
    )
    assert broken.disposition == "BLOCKED"
    assert "local model verifier failed" in broken.blockers

    class FakeObservation(LocalModelAssetObservation):
        pass

    class ForgingVerifier:
        def verify(
            self,
            *,
            role: TrainingRole,
            model_root: Path,
            run_plan: TrainingRunPlan,
        ) -> LocalModelAssetObservation:
            return FakeObservation(
                role=role,
                model_id=run_plan.model_id,
                revision=run_plan.revision,
                weights_sha256=run_plan.weights_sha256,
                verifier_id="fake",
                verifier_version="v1",
                verifier_receipt_sha256=_SHA_D,
                network_accessed=False,
                remote_code_allowed=False,
                gated_terms_accepted=False,
            )

    forged = attest_local_training_assets(
        launch_plan=_launch(),
        corpus_binding=_binding(raw),
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=ForgingVerifier(),
    )
    assert forged.disposition == "BLOCKED"
    assert any("non-canonical" in item for item in forged.blockers)


def test_non_string_revisions_fail_with_contract_errors(tmp_path: Path) -> None:
    bad_revision: Any = 123
    with pytest.raises(TrainingLocalAssetAttestationError, match="revision"):
        LocalModelAssetObservation(
            role="compact",
            model_id="example/compact",
            revision=bad_revision,
            weights_sha256=_SHA_B,
            verifier_id="fixture-local-verifier",
            verifier_version="v1",
            verifier_receipt_sha256=_SHA_D,
            network_accessed=False,
            remote_code_allowed=False,
            gated_terms_accepted=False,
        )

    report = _attest(tmp_path, b'{"example":"one"}\n')
    with pytest.raises(TrainingLocalAssetAttestationError, match="revision"):
        replace(report, revision=bad_revision)


def test_direct_pass_report_rejects_forged_content(tmp_path: Path) -> None:
    report = _attest(tmp_path, b'{"example":"one"}\n')
    with pytest.raises(TrainingLocalAssetAttestationError, match="weight identity"):
        replace(report, observed_weights_sha256=_SHA_A)
    with pytest.raises(TrainingLocalAssetAttestationError, match="corpus SHA"):
        replace(report, observed_corpus_sha256=_SHA_A)
    with pytest.raises(TrainingLocalAssetAttestationError, match="corpus byte"):
        replace(report, observed_corpus_byte_count=report.expected_corpus_byte_count + 1)
    with pytest.raises(TrainingLocalAssetAttestationError, match="positive corpus byte count"):
        replace(report, expected_corpus_byte_count=0, observed_corpus_byte_count=0)
    with pytest.raises(TrainingLocalAssetAttestationError, match="model_verifier_id"):
        replace(report, model_verifier_id="")
    with pytest.raises(TrainingLocalAssetAttestationError, match="model_verifier_version"):
        replace(report, model_verifier_version="")
    with pytest.raises(TrainingLocalAssetAttestationError, match="cannot have blockers"):
        replace(report, blockers=("forged",))
    with pytest.raises(TrainingLocalAssetAttestationError, match="forbids network"):
        replace(report, model_network_accessed=True)


def test_rejects_subclassed_canonical_plan_and_binding(tmp_path: Path) -> None:
    raw = b'{"example":"one"}\n'
    model_root, corpus_path = _paths(tmp_path, raw)

    class FakeLaunch(TrainingLaunchPlan):
        pass

    class FakeBinding(TrainingCorpusBindingReport):
        pass

    launch = _launch()
    fake_launch: Any = FakeLaunch(
        readiness_manifest_sha256=launch.readiness_manifest_sha256,
        runtime_qualification_sha256=launch.runtime_qualification_sha256,
        training_authorization_receipt_sha256=launch.training_authorization_receipt_sha256,
        compact=launch.compact,
        reasoner=launch.reasoner,
    )
    binding = _binding(raw)
    fake_binding: Any = FakeBinding(
        disposition=binding.disposition,
        qualification_sha256=binding.qualification_sha256,
        training_dataset_sha256=binding.training_dataset_sha256,
        qualified_training_record_ids_sha256=binding.qualified_training_record_ids_sha256,
        corpus_sha256=binding.corpus_sha256,
        corpus_training_record_ids_sha256=binding.corpus_training_record_ids_sha256,
        canonical_jsonl_sha256=binding.canonical_jsonl_sha256,
        canonical_jsonl_byte_count=binding.canonical_jsonl_byte_count,
        example_count=binding.example_count,
        blockers=binding.blockers,
    )

    with pytest.raises(TrainingLocalAssetAttestationError, match="exact TrainingLaunchPlan"):
        attest_local_training_assets(
            launch_plan=fake_launch,
            corpus_binding=binding,
            role="compact",
            model_root=model_root,
            corpus_path=corpus_path,
            verifier=_Verifier(),
        )
    with pytest.raises(
        TrainingLocalAssetAttestationError,
        match="exact TrainingCorpusBindingReport",
    ):
        attest_local_training_assets(
            launch_plan=launch,
            corpus_binding=fake_binding,
            role="compact",
            model_root=model_root,
            corpus_path=corpus_path,
            verifier=_Verifier(),
        )
