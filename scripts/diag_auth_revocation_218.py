from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one replacement, found {count}")
    file_path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    receipt = "src/medscale/mesc/_training_authorization_receipt_v1.py"
    replace_once(
        receipt,
        '''    @property\n    def authorization_artifact_sha256(self) -> str | None:\n''',
        '''    def validate_current_trust(self) -> None:\n        """Require this AUTHORIZED receipt to remain trusted by the current registry."""\n        if self.disposition != "AUTHORIZED" or not self.real_training_authorized:\n            raise TrainingAuthorizationReceiptError(\n                "current-trust validation requires an AUTHORIZED receipt"\n            )\n        artifact = self.authorization_artifact\n        if artifact is None:\n            raise TrainingAuthorizationReceiptError(\n                "AUTHORIZED receipt lacks validated authorization artifact bytes"\n            )\n        current_registry_sha256 = (\n            authorization_trust.training_authorization_trust_registry_sha256()\n        )\n        if self.authorization_trust_registry_sha256 != current_registry_sha256:\n            raise TrainingAuthorizationReceiptError(\n                "authorization trust registry changed after receipt admission"\n            )\n        if not authorization_trust.is_trusted_training_authorization_artifact_sha256(\n            artifact.artifact_sha256\n        ):\n            raise TrainingAuthorizationReceiptError(\n                "authorization artifact is no longer trusted by the canonical registry"\n            )\n\n    @property\n    def authorization_artifact_sha256(self) -> str | None:\n''',
    )

    readiness = "src/medscale/mesc/_training_readiness_v1.py"
    replace_once(
        readiness,
        '''from medscale.mesc._training_authorization_receipt_v1 import TrainingAuthorizationReceipt\n''',
        '''from medscale.mesc._training_authorization_receipt_v1 import (\n    TrainingAuthorizationReceipt,\n    TrainingAuthorizationReceiptError,\n)\n''',
    )
    replace_once(
        readiness,
        '''    if receipt.blockers:\n        blockers.append("training authorization receipt retains blockers")\n    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:\n''',
        '''    if receipt.blockers:\n        blockers.append("training authorization receipt retains blockers")\n    try:\n        receipt.validate_current_trust()\n    except TrainingAuthorizationReceiptError:\n        blockers.append(\n            "training authorization receipt is not trusted by the current canonical registry"\n        )\n    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:\n''',
    )

    binding = "src/medscale/mesc/_training_readiness_receipt_binding_v1.py"
    replace_once(
        binding,
        '''from medscale.mesc._training_authorization_receipt_v1 import TrainingAuthorizationReceipt\n''',
        '''from medscale.mesc._training_authorization_receipt_v1 import (\n    TrainingAuthorizationReceipt,\n    TrainingAuthorizationReceiptError,\n)\n''',
    )
    replace_once(
        binding,
        '''    if receipt.disposition != "AUTHORIZED" or not receipt.real_training_authorized:\n        raise TrainingReadinessReceiptBindingError(\n            "authorization receipt must be AUTHORIZED with real_training_authorized=true"\n        )\n    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:\n''',
        '''    if receipt.disposition != "AUTHORIZED" or not receipt.real_training_authorized:\n        raise TrainingReadinessReceiptBindingError(\n            "authorization receipt must be AUTHORIZED with real_training_authorized=true"\n        )\n    try:\n        receipt.validate_current_trust()\n    except TrainingAuthorizationReceiptError as exc:\n        raise TrainingReadinessReceiptBindingError(\n            "authorization receipt is not trusted by the current canonical registry"\n        ) from exc\n    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:\n''',
    )

    support = Path("tests/_training_authorization_test_support.py")
    support.write_text(
        '''"""Test-only lifetime support for synthetic training-authorization trust."""\n\nfrom __future__ import annotations\n\nimport hashlib\nfrom collections.abc import Callable\nfrom unittest.mock import patch\n\nfrom medscale.mesc import _training_authorization_trust_v1 as authorization_trust\n\n_TRUST_CLEANUPS: list[Callable[[], object]] = []\n\n\ndef install_training_authorization_test_trust(artifact: bytes) -> None:\n    """Trust one synthetic artifact until the current pytest test finishes."""\n    digest = hashlib.sha256(artifact).hexdigest()\n    trusted = authorization_trust.TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256 | frozenset(\n        {digest}\n    )\n    patcher = patch.object(\n        authorization_trust,\n        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",\n        trusted,\n    )\n    patcher.start()\n    _TRUST_CLEANUPS.append(patcher.stop)\n\n\ndef restore_training_authorization_test_trust() -> None:\n    """Restore all temporary registry patches in reverse installation order."""\n    while _TRUST_CLEANUPS:\n        _TRUST_CLEANUPS.pop()()\n''',
        encoding="utf-8",
    )
    Path("tests/conftest.py").write_text(
        '''"""Shared pytest lifecycle guards for MESC tests."""\n\nfrom __future__ import annotations\n\nfrom collections.abc import Iterator\n\nimport pytest\n\nfrom _training_authorization_test_support import (\n    restore_training_authorization_test_trust,\n)\n\n\n@pytest.fixture(autouse=True)\ndef _restore_training_authorization_trust_after_test() -> Iterator[None]:\n    """Never leak synthetic authorization trust across test boundaries."""\n    try:\n        yield\n    finally:\n        restore_training_authorization_test_trust()\n''',
        encoding="utf-8",
    )

    test_files = (
        "tests/test_mesc_training_readiness_receipt_binding_v1.py",
        "tests/test_mesc_training_readiness_v1.py",
        "tests/test_mesc_training_launch_plan_v1.py",
        "tests/test_mesc_training_executor_v1.py",
        "tests/test_mesc_training_orchestrator_v1.py",
    )
    old_trust = '''    trusted = frozenset({hashlib.sha256(artifact).hexdigest()})\n    with patch.object(\n        authorization_trust,\n        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",\n        trusted,\n    ):\n        return _build_training_authorization_receipt(\n'''
    new_trust = '''    install_training_authorization_test_trust(artifact)\n    return _build_training_authorization_receipt(\n'''
    for test_file in test_files:
        replace_once(
            test_file,
            "import pytest\n\n",
            "import pytest\n\nfrom _training_authorization_test_support import (\n    install_training_authorization_test_trust,\n)\n\n",
        )
        replace_once(test_file, old_trust, new_trust)


if __name__ == "__main__":
    main()
