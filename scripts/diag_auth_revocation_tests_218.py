from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if marker in text:
        raise RuntimeError(f"{path}: revocation regression already present")
    file_path.write_text(text.rstrip() + "\n\n\n" + addition.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    append_once(
        "specs/mesc-training-authorization-receipt-v1/README.md",
        "## Use-time trust and revocation",
        '''## Use-time trust and revocation\n\nTrust admission is not a one-time construction check. Every `AUTHORIZED` receipt must still match the exact current repository-controlled trust-registry identity, and its authorization-artifact digest must remain admitted, whenever the receipt is bound into readiness or used to recompute launch authority.\n\nAny trust-registry mutation therefore invalidates previously admitted receipts fail-closed, including explicit digest removal. A caller must obtain a newly admitted receipt under the new canonical registry snapshot before training can become `READY_TO_LAUNCH` again. Executor and orchestrator paths recompute readiness before backend invocation, so revoked authority cannot be grandfathered into a live training run. This rule does not provision any real authorization digest or grant current training authority.''',
    )

    install_only = '''from _training_authorization_test_support import (\n    install_training_authorization_test_trust,\n)\n'''
    install_and_restore = '''from _training_authorization_test_support import (\n    install_training_authorization_test_trust,\n    restore_training_authorization_test_trust,\n)\n'''
    for path in (
        "tests/test_mesc_training_readiness_receipt_binding_v1.py",
        "tests/test_mesc_training_readiness_v1.py",
        "tests/test_mesc_training_executor_v1.py",
    ):
        replace_once(path, install_only, install_and_restore)

    append_once(
        "tests/test_mesc_training_authorization_receipt_v1.py",
        "test_authorized_receipt_rejects_current_trust_after_registry_revocation",
        '''def test_authorized_receipt_rejects_current_trust_after_registry_revocation() -> None:\n    receipt = _build(authorize=True)\n\n    with pytest.raises(\n        TrainingAuthorizationReceiptError,\n        match=r"trust registry changed|no longer trusted",\n    ):\n        receipt.validate_current_trust()''',
    )

    append_once(
        "tests/test_mesc_training_readiness_receipt_binding_v1.py",
        "test_binding_rejects_authorization_after_registry_revocation",
        '''def test_binding_rejects_authorization_after_registry_revocation() -> None:\n    scientific = _scientific_manifest()\n    runtime = _runtime(smoke=True)\n    with_runtime = bind_runtime_qualification_to_readiness(scientific, runtime)\n    auth = build_training_authorization_receipt(\n        authorizer_id="founder",\n        authorization_subject_sha256=with_runtime.authorization_subject_sha256,\n        runtime_qualification_sha256=runtime.receipt_sha256,\n        corpus_binding_sha256=_CORPUS,\n        authorization_statement="Authorize TRAINING_EXECUTION for the bound subject.",\n        authorize=True,\n    )\n    restore_training_authorization_test_trust()\n\n    with pytest.raises(\n        TrainingReadinessReceiptBindingError,\n        match="current canonical registry",\n    ):\n        bind_training_authorization_to_readiness(\n            with_runtime,\n            auth,\n            runtime_qualification=runtime,\n        )''',
    )

    append_once(
        "tests/test_mesc_training_readiness_v1.py",
        "test_revoked_authorization_blocks_ready_to_launch",
        '''def test_revoked_authorization_blocks_ready_to_launch() -> None:\n    manifest = _authorized_manifest()\n    assert assess_training_readiness(manifest).disposition == "READY_TO_LAUNCH"\n\n    restore_training_authorization_test_trust()\n    report = assess_training_readiness(manifest)\n\n    assert report.disposition == "BLOCKED"\n    assert report.can_launch_training is False\n    assert (\n        "training authorization receipt is not trusted by the current canonical registry"\n        in report.blockers\n    )''',
    )

    append_once(
        "tests/test_mesc_training_executor_v1.py",
        "test_revoked_authorization_fails_before_backend_invocation",
        '''def test_revoked_authorization_fails_before_backend_invocation() -> None:\n    manifest, readiness, launch, binding, assets, environment = _bundle()\n    backend = _SuccessBackend()\n    restore_training_authorization_test_trust()\n\n    with pytest.raises(TrainingExecutionError, match="recomputed readiness"):\n        execute_training(\n            manifest=manifest,\n            readiness=readiness,\n            launch_plan=launch,\n            corpus_binding=binding,\n            local_assets=assets,\n            environment=environment,\n            role="compact",\n            backend=backend,\n        )\n\n    assert backend.calls == 0''',
    )


if __name__ == "__main__":
    main()
