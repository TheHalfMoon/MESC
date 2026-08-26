from __future__ import annotations

from pathlib import Path

TARGET_FILES = (
    "tests/test_mesc_training_readiness_v1.py",
    "tests/test_mesc_training_launch_plan_v1.py",
    "tests/test_mesc_training_executor_v1.py",
    "tests/test_mesc_training_orchestrator_v1.py",
    "tests/test_mesc_training_readiness_receipt_binding_v1.py",
)

SIMPLE_IMPORT = """from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt,
)
"""
SIMPLE_REPLACEMENT = """from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    build_training_authorization_receipt as _build_training_authorization_receipt,
)
"""
BINDING_IMPORT = """from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    build_training_authorization_receipt,
)
"""
BINDING_REPLACEMENT = """from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    build_training_authorization_receipt as _build_training_authorization_receipt,
)
"""

HELPER = '''

def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    authorization_subject_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    authorization_statement: str,
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Build explicit canonical synthetic authorization evidence for this test module."""
    artifact = None
    if authorize:
        artifact = canonical_json_bytes(
            {
                "authorization_scope": "TRAINING_EXECUTION",
                "authorization_statement": authorization_statement,
                "authorization_subject_sha256": authorization_subject_sha256,
                "authorize": True,
                "authorizer_id": authorizer_id,
                "corpus_binding_sha256": corpus_binding_sha256,
                "kind": "mesc.training_authorization.v1",
                "runtime_qualification_sha256": runtime_qualification_sha256,
            }
        )
    return _build_training_authorization_receipt(
        authorizer_id=authorizer_id,
        authorization_subject_sha256=authorization_subject_sha256,
        runtime_qualification_sha256=runtime_qualification_sha256,
        corpus_binding_sha256=corpus_binding_sha256,
        authorization_statement=authorization_statement,
        authorize=authorize,
        authorization_artifact=artifact,
    )
'''


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one {label}; found {count}")
    return text.replace(old, new, 1)


def update_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if path.name == "test_mesc_training_readiness_receipt_binding_v1.py":
        text = replace_once(text, BINDING_IMPORT, BINDING_REPLACEMENT, label="binding import")
    else:
        text = replace_once(text, SIMPLE_IMPORT, SIMPLE_REPLACEMENT, label="simple import")
    marker = "\n\ndef _candidate("
    text = replace_once(text, marker, HELPER + marker, label="candidate insertion marker")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    for filename in TARGET_FILES:
        update_file(Path(filename))


if __name__ == "__main__":
    main()
