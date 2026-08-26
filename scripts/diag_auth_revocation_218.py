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


if __name__ == "__main__":
    main()
