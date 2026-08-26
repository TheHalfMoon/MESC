from __future__ import annotations

from pathlib import Path

SUPPORT = '''"""Synthetic MESC training-authorization evidence for repository tests only."""

from __future__ import annotations

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_authorization_receipt_v1 import (
    AuthorizationScope,
    TrainingAuthorizationReceipt,
    build_training_authorization_receipt as _build_training_authorization_receipt,
)


def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    authorization_subject_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    authorization_statement: str,
    authorization_scope: AuthorizationScope = "TRAINING_EXECUTION",
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Exercise positive paths with explicit canonical synthetic artifact bytes."""
    artifact = None
    if authorize:
        artifact = canonical_json_bytes(
            {
                "authorization_scope": authorization_scope,
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
        authorization_scope=authorization_scope,
        authorize=authorize,
        authorization_artifact=artifact,
    )
'''

SIMPLE_FILES = (
    "tests/test_mesc_training_readiness_v1.py",
    "tests/test_mesc_training_launch_plan_v1.py",
    "tests/test_mesc_training_executor_v1.py",
    "tests/test_mesc_training_orchestrator_v1.py",
)
SIMPLE_OLD = """from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt,
)
"""
SIMPLE_NEW = """from test_support.mesc_training_authorization import (
    build_training_authorization_receipt,
)
"""
BINDING_FILE = "tests/test_mesc_training_readiness_receipt_binding_v1.py"
BINDING_OLD = """from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    build_training_authorization_receipt,
)
"""
BINDING_NEW = """from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
)
from test_support.mesc_training_authorization import (
    build_training_authorization_receipt,
)
"""


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one import block in {path}; found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    support = Path("test_support")
    support.mkdir(exist_ok=True)
    (support / "__init__.py").write_text("", encoding="utf-8")
    (support / "mesc_training_authorization.py").write_text(SUPPORT, encoding="utf-8")
    for filename in SIMPLE_FILES:
        replace_once(Path(filename), SIMPLE_OLD, SIMPLE_NEW)
    replace_once(Path(BINDING_FILE), BINDING_OLD, BINDING_NEW)


if __name__ == "__main__":
    main()
