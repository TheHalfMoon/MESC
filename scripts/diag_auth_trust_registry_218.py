from __future__ import annotations

from pathlib import Path

SOURCE = Path("src/medscale/mesc/_training_authorization_receipt_v1.py")
CORE_TEST = Path("tests/test_mesc_training_authorization_receipt_v1.py")
README = Path("specs/mesc-training-authorization-receipt-v1/README.md")
DOWNSTREAM = (
    Path("tests/test_mesc_training_readiness_v1.py"),
    Path("tests/test_mesc_training_launch_plan_v1.py"),
    Path("tests/test_mesc_training_executor_v1.py"),
    Path("tests/test_mesc_training_orchestrator_v1.py"),
    Path("tests/test_mesc_training_readiness_receipt_binding_v1.py"),
)


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {label}; found {count}")
    return text.replace(old, new, 1)


def patch_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes\n",
        "from medscale.mesc import _training_authorization_trust_v1 as authorization_trust\n"
        "from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes\n",
        label="trust import",
    )
    text = replace_once(
        text,
        "    blockers: tuple[str, ...]\n    authorization_artifact: TrainingAuthorizationArtifact | None = None\n",
        "    blockers: tuple[str, ...]\n"
        "    authorization_trust_registry_sha256: str | None = None\n"
        "    authorization_artifact: TrainingAuthorizationArtifact | None = None\n",
        label="receipt trust field",
    )
    text = replace_once(
        text,
        "        if self.authorization_artifact is not None and (\n"
        "            type(self.authorization_artifact) is not TrainingAuthorizationArtifact\n"
        "        ):\n"
        "            raise TrainingAuthorizationReceiptError(\n"
        "                \"authorization_artifact must be an exact TrainingAuthorizationArtifact\"\n"
        "            )\n\n"
        "        if self.disposition == \"AUTHORIZED\":\n",
        "        if self.authorization_trust_registry_sha256 is not None:\n"
        "            _require_sha256(\n"
        "                self.authorization_trust_registry_sha256,\n"
        "                field=\"authorization_trust_registry_sha256\",\n"
        "            )\n"
        "        if self.authorization_artifact is not None and (\n"
        "            type(self.authorization_artifact) is not TrainingAuthorizationArtifact\n"
        "        ):\n"
        "            raise TrainingAuthorizationReceiptError(\n"
        "                \"authorization_artifact must be an exact TrainingAuthorizationArtifact\"\n"
        "            )\n\n"
        "        if self.disposition == \"AUTHORIZED\":\n",
        label="receipt trust validation",
    )
    text = replace_once(
        text,
        "            if not self.authorization_artifact.authorize:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"AUTHORIZED receipt artifact must carry authorize=true\"\n"
        "                )\n"
        "        else:\n",
        "            if not self.authorization_artifact.authorize:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"AUTHORIZED receipt artifact must carry authorize=true\"\n"
        "                )\n"
        "            expected_registry_sha256 = (\n"
        "                authorization_trust.training_authorization_trust_registry_sha256()\n"
        "            )\n"
        "            if self.authorization_trust_registry_sha256 != expected_registry_sha256:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"AUTHORIZED receipt does not bind the canonical authorization trust registry\"\n"
        "                )\n"
        "            if not authorization_trust.is_trusted_training_authorization_artifact_sha256(\n"
        "                self.authorization_artifact.artifact_sha256\n"
        "            ):\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"AUTHORIZED receipt artifact is not present in the canonical trust registry\"\n"
        "                )\n"
        "        else:\n",
        label="authorized registry enforcement",
    )
    text = replace_once(
        text,
        "            if self.real_training_authorized:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"BLOCKED receipts forbid real_training_authorized=true\"\n"
        "                )\n"
        "            if self.authorization_artifact is not None:\n",
        "            if self.real_training_authorized:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"BLOCKED receipts forbid real_training_authorized=true\"\n"
        "                )\n"
        "            if self.authorization_trust_registry_sha256 is not None:\n"
        "                raise TrainingAuthorizationReceiptError(\n"
        "                    \"BLOCKED receipts cannot claim an authorization trust registry\"\n"
        "                )\n"
        "            if self.authorization_artifact is not None:\n",
        label="blocked trust invariant",
    )
    text = replace_once(
        text,
        "            \"authorization_statement\": self.authorization_statement,\n"
        "            \"authorization_subject_sha256\": self.authorization_subject_sha256,\n",
        "            \"authorization_statement\": self.authorization_statement,\n"
        "            \"authorization_subject_sha256\": self.authorization_subject_sha256,\n"
        "            \"authorization_trust_registry_sha256\": (\n"
        "                self.authorization_trust_registry_sha256\n"
        "            ),\n",
        label="receipt payload trust identity",
    )
    text = replace_once(
        text,
        "    ``authorize=True`` never creates authority by itself. An AUTHORIZED receipt requires\n"
        "    separately supplied canonical ``authorization_artifact`` bytes whose exact semantic\n"
        "    fields match every scalar binding supplied here. ``authorize=False`` remains a\n"
        "    fail-closed fixture/negative path and may omit the artifact entirely.\n",
        "    ``authorize=True`` never creates authority by itself. An AUTHORIZED receipt requires\n"
        "    separately supplied canonical ``authorization_artifact`` bytes whose exact semantic\n"
        "    fields match every scalar binding and whose SHA-256 was independently provisioned in\n"
        "    the repository-controlled trust registry. ``authorize=False`` remains fail-closed.\n",
        label="builder docstring",
    )
    text = replace_once(
        text,
        "    if authorize and artifact is None:\n"
        "        raise TrainingAuthorizationReceiptError(\n"
        "            \"authorize=true requires validated authorization_artifact bytes\"\n"
        "        )\n\n"
        "    blockers: list[str] = []\n",
        "    if authorize and artifact is None:\n"
        "        raise TrainingAuthorizationReceiptError(\n"
        "            \"authorize=true requires validated authorization_artifact bytes\"\n"
        "        )\n"
        "    if (\n"
        "        authorize\n"
        "        and artifact is not None\n"
        "        and not authorization_trust.is_trusted_training_authorization_artifact_sha256(\n"
        "            artifact.artifact_sha256\n"
        "        )\n"
        "    ):\n"
        "        raise TrainingAuthorizationReceiptError(\n"
        "            \"authorization artifact is not present in the canonical trusted authorization registry\"\n"
        "        )\n\n"
        "    blockers: list[str] = []\n",
        label="builder registry gate",
    )
    text = replace_once(
        text,
        "        real_training_authorized=disposition == \"AUTHORIZED\",\n"
        "        blockers=tuple(blockers),\n"
        "        authorization_artifact=artifact,\n",
        "        real_training_authorized=disposition == \"AUTHORIZED\",\n"
        "        blockers=tuple(blockers),\n"
        "        authorization_trust_registry_sha256=(\n"
        "            authorization_trust.training_authorization_trust_registry_sha256()\n"
        "            if disposition == \"AUTHORIZED\"\n"
        "            else None\n"
        "        ),\n"
        "        authorization_artifact=artifact,\n",
        label="builder registry identity",
    )
    SOURCE.write_text(text, encoding="utf-8")


LOCAL_HELPER_START = "def build_training_authorization_receipt(\n"
LOCAL_HELPER_END = "\n\ndef _candidate("
LOCAL_HELPER = '''def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    authorization_subject_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    authorization_statement: str,
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Build explicit synthetic evidence under a test-only temporary trust registry."""
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
    if artifact is None:
        return _build_training_authorization_receipt(
            authorizer_id=authorizer_id,
            authorization_subject_sha256=authorization_subject_sha256,
            runtime_qualification_sha256=runtime_qualification_sha256,
            corpus_binding_sha256=corpus_binding_sha256,
            authorization_statement=authorization_statement,
            authorize=authorize,
            authorization_artifact=None,
        )
    trusted = frozenset({hashlib.sha256(artifact).hexdigest()})
    with patch.object(
        authorization_trust,
        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",
        trusted,
    ):
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


def patch_downstream(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "import hashlib\n" not in text:
        text = replace_once(
            text,
            "from __future__ import annotations\n\n",
            "from __future__ import annotations\n\nimport hashlib\n",
            label=f"{path} hashlib import",
        )
    if "from unittest.mock import patch\n" not in text:
        anchor = "import hashlib\n"
        text = replace_once(
            text,
            anchor,
            anchor + "from unittest.mock import patch\n",
            label=f"{path} patch import",
        )
    if "as authorization_trust" not in text:
        text = replace_once(
            text,
            "import pytest\n\n",
            "import pytest\n\nfrom medscale.mesc import _training_authorization_trust_v1 as authorization_trust\n",
            label=f"{path} trust module import",
        )
    start = text.index(LOCAL_HELPER_START)
    end = text.index(LOCAL_HELPER_END, start)
    text = text[:start] + LOCAL_HELPER + text[end:]
    path.write_text(text, encoding="utf-8")


def patch_readiness_end_to_end() -> None:
    path = Path("tests/test_mesc_training_readiness_v1.py")
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from medscale.mesc._training_authorization_receipt_v1 import (\n"
        "    TrainingAuthorizationReceipt,\n"
        ")\n",
        "from medscale.mesc._training_authorization_receipt_v1 import (\n"
        "    TrainingAuthorizationReceipt,\n"
        "    TrainingAuthorizationReceiptError,\n"
        ")\n",
        label="readiness error import",
    )
    marker = "\n\ndef test_authorization_for_different_subject_blocks() -> None:\n"
    test = '''

def test_caller_created_canonical_authorization_cannot_unlock_readiness() -> None:
    pre = _manifest_without_authorization()
    artifact = canonical_json_bytes(
        {
            "authorization_scope": "TRAINING_EXECUTION",
            "authorization_statement": "Forged caller authorization.",
            "authorization_subject_sha256": pre.authorization_subject_sha256,
            "authorize": True,
            "authorizer_id": "caller",
            "corpus_binding_sha256": pre.corpus_binding_sha256,
            "kind": "mesc.training_authorization.v1",
            "runtime_qualification_sha256": pre.runtime_qualification_sha256,
        }
    )
    with pytest.raises(TrainingAuthorizationReceiptError, match="trusted authorization registry"):
        _build_training_authorization_receipt(
            authorizer_id="caller",
            authorization_subject_sha256=pre.authorization_subject_sha256,
            runtime_qualification_sha256=pre.runtime_qualification_sha256 or "",
            corpus_binding_sha256=pre.corpus_binding_sha256 or "",
            authorization_statement="Forged caller authorization.",
            authorize=True,
            authorization_artifact=artifact,
        )

    report = assess_training_readiness(pre)
    assert report.disposition == "READY_FOR_AUTHORIZATION"
    assert report.can_launch_training is False
'''
    text = replace_once(text, marker, test + marker, label="end-to-end forged authority test")
    path.write_text(text, encoding="utf-8")


def patch_core_test() -> None:
    text = CORE_TEST.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from __future__ import annotations\n\nfrom typing import cast\n",
        "from __future__ import annotations\n\nimport hashlib\nfrom typing import cast\nfrom unittest.mock import patch\n",
        label="core imports",
    )
    text = replace_once(
        text,
        "import pytest\n\n",
        "import pytest\n\nfrom medscale.mesc import _training_authorization_trust_v1 as authorization_trust\n",
        label="core trust import",
    )
    old = '''def _build(*, authorize: bool, with_artifact: bool | None = None) -> TrainingAuthorizationReceipt:
    include_artifact = authorize if with_artifact is None else with_artifact
    return build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=_SUBJECT,
        runtime_qualification_sha256=_RUNTIME,
        corpus_binding_sha256=_CORPUS,
        authorization_statement=_STATEMENT,
        authorize=authorize,
        authorization_artifact=_artifact(authorize=authorize) if include_artifact else None,
    )
'''
    new = '''def _build(
    *,
    authorize: bool,
    with_artifact: bool | None = None,
    trust_artifact: bool = True,
) -> TrainingAuthorizationReceipt:
    include_artifact = authorize if with_artifact is None else with_artifact
    artifact = _artifact(authorize=authorize) if include_artifact else None
    if authorize and artifact is not None and trust_artifact:
        trusted = frozenset({hashlib.sha256(artifact).hexdigest()})
        with patch.object(
            authorization_trust,
            "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",
            trusted,
        ):
            return build_training_authorization_receipt(
                authorizer_id="fixture-founder",
                authorization_subject_sha256=_SUBJECT,
                runtime_qualification_sha256=_RUNTIME,
                corpus_binding_sha256=_CORPUS,
                authorization_statement=_STATEMENT,
                authorize=authorize,
                authorization_artifact=artifact,
            )
    return build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=_SUBJECT,
        runtime_qualification_sha256=_RUNTIME,
        corpus_binding_sha256=_CORPUS,
        authorization_statement=_STATEMENT,
        authorize=authorize,
        authorization_artifact=artifact,
    )
'''
    text = replace_once(text, old, new, label="core build helper")
    marker = "\n\ndef test_explicit_artifact_authorization_binds_pre_authorization_subject() -> None:\n"
    test = '''

def test_caller_created_canonical_artifact_is_rejected_without_trust_registry() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="trusted authorization registry"):
        _build(authorize=True, trust_artifact=False)
'''
    text = replace_once(text, marker, test + marker, label="untrusted artifact regression")
    text = replace_once(
        text,
        "    assert receipt.authorization_artifact_sha256 is not None\n"
        "    assert len(receipt.authorization_artifact_sha256) == 64\n",
        "    assert receipt.authorization_artifact_sha256 is not None\n"
        "    assert len(receipt.authorization_artifact_sha256) == 64\n"
        "    assert receipt.authorization_trust_registry_sha256 is not None\n"
        "    assert len(receipt.authorization_trust_registry_sha256) == 64\n",
        label="registry identity assertion",
    )
    CORE_TEST.write_text(text, encoding="utf-8")


def patch_readme() -> None:
    text = README.read_text(encoding="utf-8")
    if "## Canonical trust registry" in text:
        raise RuntimeError("trust registry section already exists")
    section = '''

## Canonical trust registry

Canonical JSON and SHA-256 prove artifact identity, not who authorized it. Therefore an
`authorize=true` artifact is necessary but not sufficient for `AUTHORIZED`.

The validator additionally requires the artifact SHA-256 to be present in the
repository-controlled registry implemented by:

```text
src/medscale/mesc/_training_authorization_trust_v1.py
```

The production registry is intentionally empty in this implementation. No repository
caller can mint real training authority from scalars or self-authored canonical bytes.
Provisioning a real artifact digest is a separate governance mutation: it must bind the
exact artifact, be independently reviewed, and be authenticated by the repository's
Founder-attestation process before canonical adoption. Test code may temporarily replace
the private in-process registry only to exercise positive paths; no synthetic digest is
shipped as a production trust root.

An `AUTHORIZED` receipt content-addresses the exact trust-registry identity used when the
artifact was admitted. Missing, malformed, or unregistered authority evidence fails
closed. This package does not provision a Founder key, fabricate a Founder attestation,
or grant current real-world training authority.
'''
    README.write_text(text.rstrip() + section + "\n", encoding="utf-8")


def main() -> None:
    patch_source()
    for path in DOWNSTREAM:
        patch_downstream(path)
    patch_readiness_end_to_end()
    patch_core_test()
    patch_readme()


if __name__ == "__main__":
    main()
