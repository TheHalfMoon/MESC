"""Fail-closed, content-addressed MRL V1 research-input admission contract.

The contract classifies candidate inputs before they may enter MRL learning surfaces.
It keeps external evaluation evidence read-only, rejects clinical/product/PHI and other
protected runtime inputs, and prevents declared transformed lineage from laundering a
restricted parent into a more permissive research-learning class.

This module is declarative only. It grants no filesystem, network, model, data, GPU,
inference, training, promotion, deployment, release, or clinical authority.

Integrity checks cover caller-controlled values, post-construction mutation of canonical artifact
data, and accidental or hostile rebinding of ordinary module-level trust names. Arbitrary Python
code execution that rewrites executable interpreter state such as function code, closure cells,
class methods, or ``sys.modules`` is outside this contract-level boundary: such a caller can replace
the enforcement code itself. Untrusted research execution must therefore run outside the
trust-bearing interpreter/process under the separately governed execution boundary.

Lineage validation is iterative, graph-bounded, and non-amplifying: pathological
depth or breadth fails closed instead of triggering repeated recursive snapshots.
"""

from __future__ import annotations

import enum
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_input_permission_trust_v1 import (
    ResearchInputPermissionTrustError,
)
from medscale.mesc._mrl_research_input_permission_trust_v1 import (
    validate_research_input_source_permission_trust as _canonical_validate_permission_trust,
)

__all__ = [
    "ResearchInputAdmissionContract",
    "ResearchInputAdmissionError",
    "ResearchInputClassification",
    "ResearchInputDisposition",
    "ResearchInputParentRef",
    "ResearchInputSourcePermission",
    "ResearchLearningSurface",
]

_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_MAX_LINEAGE_DEPTH: Final = 128
_MAX_LINEAGE_NODES: Final = 4096
_MAX_LINEAGE_EDGES: Final = 16384


class ResearchInputAdmissionError(ValueError):
    """Fail-closed validation error for MRL research-input admission semantics."""


class ResearchInputClassification(enum.Enum):
    """Canonical MRL V1 candidate-input classifications."""

    RESEARCH_ARTIFACT = "RESEARCH_ARTIFACT"
    DETERMINISTIC_FIXTURE_OUTPUT = "DETERMINISTIC_FIXTURE_OUTPUT"
    NEGATIVE_OR_INVALID_RESEARCH_RESULT = "NEGATIVE_OR_INVALID_RESEARCH_RESULT"
    EXTERNAL_EVALUATION_EVIDENCE = "EXTERNAL_EVALUATION_EVIDENCE"
    CLINICAL_RUNTIME_STATE = "CLINICAL_RUNTIME_STATE"
    PRODUCT_TELEMETRY = "PRODUCT_TELEMETRY"
    PHI_OR_PATIENT_DATA = "PHI_OR_PATIENT_DATA"
    CREDENTIAL_OR_PROVIDER_CONTROL_STATE = "CREDENTIAL_OR_PROVIDER_CONTROL_STATE"
    SEALED_TIER3_ITEM_CONTENT = "SEALED_TIER3_ITEM_CONTENT"
    UNKNOWN = "UNKNOWN"


class ResearchInputDisposition(enum.Enum):
    """The only admission dispositions derived from input classification."""

    LEARNING_ADMITTED = "LEARNING_ADMITTED"
    EXTERNAL_EVALUATION_ONLY = "EXTERNAL_EVALUATION_ONLY"
    REJECTED = "REJECTED"


class ResearchLearningSurface(enum.Enum):
    """MRL learning surfaces protected by the admission boundary."""

    CAMPAIGN_HISTORY = "CAMPAIGN_HISTORY"
    OBSERVATION = "OBSERVATION"
    PROCEDURE_EXTRACTION = "PROCEDURE_EXTRACTION"
    RESEARCH_SEARCH_INDEX = "RESEARCH_SEARCH_INDEX"


_LEARNING_CLASSIFICATIONS: Final[frozenset[ResearchInputClassification]] = frozenset(
    {
        ResearchInputClassification.RESEARCH_ARTIFACT,
        ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
    }
)
_REJECTED_CLASSIFICATIONS: Final[frozenset[ResearchInputClassification]] = frozenset(
    {
        ResearchInputClassification.CLINICAL_RUNTIME_STATE,
        ResearchInputClassification.PRODUCT_TELEMETRY,
        ResearchInputClassification.PHI_OR_PATIENT_DATA,
        ResearchInputClassification.CREDENTIAL_OR_PROVIDER_CONTROL_STATE,
        ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
        ResearchInputClassification.UNKNOWN,
    }
)


@dataclass(frozen=True, slots=True)
class ResearchInputSourcePermission:
    """Content-addressed permission for one exact governed research-input source."""

    permission_id: str
    source_artifact_sha256: str
    source_contract_sha256: str
    classification: ResearchInputClassification
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]

    def __post_init__(self) -> None:
        _require_token(self.permission_id, "permission_id")
        _require_sha256(self.source_artifact_sha256, "source_artifact_sha256")
        _require_sha256(self.source_contract_sha256, "source_contract_sha256")
        _require_exact_enum(self.classification, ResearchInputClassification, "classification")
        _require_learning_surfaces(self.allowed_learning_surfaces)
        disposition = _disposition_for_classification(self.classification)
        if disposition is ResearchInputDisposition.REJECTED:
            raise ResearchInputAdmissionError(
                "source permissions cannot authorize a rejected classification"
            )
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if not self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning source permission requires at least one learning surface"
                )
        elif self.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                "external-evaluation source permission cannot grant learning surfaces"
            )

    def _validated_snapshot(self) -> ResearchInputSourcePermission:
        _require_exact_source_permission(self)
        return ResearchInputSourcePermission(
            permission_id=self.permission_id,
            source_artifact_sha256=self.source_artifact_sha256,
            source_contract_sha256=self.source_contract_sha256,
            classification=self.classification,
            allowed_learning_surfaces=self.allowed_learning_surfaces,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-V1",
            "permission_id": self.permission_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_contract_sha256": self.source_contract_sha256,
            "classification": self.classification.value,
            "allowed_learning_surfaces": [
                surface.value for surface in self.allowed_learning_surfaces
            ],
        }

    @property
    def content_sha256(self) -> str:
        _require_exact_source_permission(self)
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        _require_exact_source_permission(self)
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class ResearchInputParentRef:
    """Reference derived from one actual validated parent admission.

    The semantic reference exposes only the parent's content identity, classification,
    and canonical disposition, but those values are never accepted independently from
    a caller. They are derived from the exact validated parent admission and rebound on
    every public view so a detached or relabelled digest cannot launder lineage.
    """

    parent_admission: ResearchInputAdmissionContract
    _bound_admission_sha256: str = field(init=False, repr=False)
    _bound_classification: ResearchInputClassification = field(init=False, repr=False)
    _bound_disposition: ResearchInputDisposition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _require_exact_admission(self.parent_admission)
        _, current_sha256, current_classification, current_disposition = _local_admission_state(
            self.parent_admission
        )
        object.__setattr__(self, "_bound_admission_sha256", current_sha256)
        object.__setattr__(self, "_bound_classification", current_classification)
        object.__setattr__(self, "_bound_disposition", current_disposition)

    def _validated_binding(
        self,
    ) -> tuple[str, ResearchInputClassification, ResearchInputDisposition]:
        _require_exact_parent_ref(self)
        _require_exact_admission(self.parent_admission)
        _, current_sha256, current_classification, current_disposition = _validated_admission_state(
            self.parent_admission
        )
        _require_sha256(self._bound_admission_sha256, "bound parent admission sha256")
        _require_exact_enum(
            self._bound_classification,
            ResearchInputClassification,
            "bound parent classification",
        )
        _require_exact_enum(
            self._bound_disposition,
            ResearchInputDisposition,
            "bound parent disposition",
        )
        if (
            current_sha256 != self._bound_admission_sha256
            or current_classification is not self._bound_classification
            or current_disposition is not self._bound_disposition
        ):
            raise ResearchInputAdmissionError(
                "parent admission binding changed after reference creation"
            )
        return current_sha256, current_classification, current_disposition

    @property
    def admission_sha256(self) -> str:
        return self._validated_binding()[0]

    @property
    def classification(self) -> ResearchInputClassification:
        return self._validated_binding()[1]

    @property
    def disposition(self) -> ResearchInputDisposition:
        return self._validated_binding()[2]

    def _validated_snapshot(self) -> ResearchInputParentRef:
        """Validate the live binding without recursively rebuilding its ancestry."""
        self._validated_binding()
        return self

    def to_dict(self) -> dict[str, str]:
        """Return one freshly validated parent-reference semantic mapping."""
        admission_sha256, classification, disposition = self._validated_binding()
        return {
            "admission_sha256": admission_sha256,
            "classification": classification.value,
            "disposition": disposition.value,
        }


def _build_admission_graph_trust_gate(
    validate_permission_trust: Callable[[str], object],
) -> Callable[[ResearchInputAdmissionContract], None]:
    """Bind admission authority to one import-time canonical validator closure."""

    def require_admission_graph_trust(root: ResearchInputAdmissionContract) -> None:
        _validated_admission_state(root)
        stack = [root]
        visited: set[int] = set()
        while stack:
            node = stack.pop()
            node_id = id(node)
            if node_id in visited:
                continue
            visited.add(node_id)
            _require_exact_admission(node)
            disposition = _disposition_for_classification(node.classification)
            if disposition is not ResearchInputDisposition.REJECTED:
                _require_source_permission_binding(node)
                permission = node.source_permission
                if type(permission) is not ResearchInputSourcePermission:
                    raise ResearchInputAdmissionError(
                        "admissible input requires an exact ResearchInputSourcePermission"
                    )
                permission_snapshot = permission._validated_snapshot()
                permission_sha256 = derive_content_sha256(
                    permission_snapshot._semantic_dict_validated()
                )
                try:
                    validate_permission_trust(permission_sha256)
                except ResearchInputPermissionTrustError as exc:
                    raise ResearchInputAdmissionError(
                        "source permission is not trusted by canonical research-input governance"
                    ) from exc
            for parent_ref in node.parent_inputs:
                _require_exact_parent_ref(parent_ref)
                stack.append(parent_ref.parent_admission)

    return require_admission_graph_trust


_require_admission_graph_trust = _build_admission_graph_trust_gate(
    _canonical_validate_permission_trust
)
del _build_admission_graph_trust_gate
del _canonical_validate_permission_trust


def _bind_learning_admission_trust(
    trust_gate: Callable[[ResearchInputAdmissionContract], None],
) -> Callable[
    [Callable[[ResearchInputAdmissionContract, ResearchLearningSurface], None]],
    Callable[[ResearchInputAdmissionContract, ResearchLearningSurface], None],
]:
    """Bind the canonical trust gate lexically into the public learning method."""

    def decorate(
        method: Callable[[ResearchInputAdmissionContract, ResearchLearningSurface], None],
    ) -> Callable[[ResearchInputAdmissionContract, ResearchLearningSurface], None]:
        def guarded(
            self: ResearchInputAdmissionContract,
            surface: ResearchLearningSurface,
        ) -> None:
            method(self, surface)
            trust_gate(self)

        return guarded

    return decorate


def _bind_external_evaluation_trust(
    trust_gate: Callable[[ResearchInputAdmissionContract], None],
) -> Callable[
    [Callable[[ResearchInputAdmissionContract], None]],
    Callable[[ResearchInputAdmissionContract], None],
]:
    """Bind the canonical trust gate lexically into the public evaluation method."""

    def decorate(
        method: Callable[[ResearchInputAdmissionContract], None],
    ) -> Callable[[ResearchInputAdmissionContract], None]:
        def guarded(self: ResearchInputAdmissionContract) -> None:
            method(self)
            trust_gate(self)

        return guarded

    return decorate


@dataclass(frozen=True, slots=True)
class ResearchInputAdmissionContract:
    """Immutable classification and admission envelope for one candidate MRL input."""

    input_id: str
    classification_policy_sha256: str
    classification: ResearchInputClassification
    source_artifact_sha256: str | None
    source_contract_sha256: str | None
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]
    source_permission: ResearchInputSourcePermission | None = field(default=None, repr=False)
    transformation_kind: str | None = None
    parent_inputs: tuple[ResearchInputParentRef, ...] = ()

    def __post_init__(self) -> None:
        # Exact-type enforcement belongs to authoritative/public validation. A subclass may
        # exist as an untrusted object, but every public view and admission gate rejects it.
        if type(self) is not ResearchInputAdmissionContract:
            return
        _local_admission_state(self)

    @property
    def disposition(self) -> ResearchInputDisposition:
        """Return validated policy disposition; authority still requires a public gate."""
        _require_exact_admission(self)
        return _validated_admission_state(self)[3]

    @_bind_learning_admission_trust(_require_admission_graph_trust)
    def require_learning_admission(self, surface: ResearchLearningSurface) -> None:
        """Fail closed unless this exact input may enter the requested MRL learning surface."""
        _require_exact_admission(self)
        _require_exact_enum(surface, ResearchLearningSurface, "surface")
        _, _, _, disposition = _validated_admission_state(self)
        if disposition is not ResearchInputDisposition.LEARNING_ADMITTED:
            raise ResearchInputAdmissionError("input is not admitted as an MRL learning signal")
        if surface not in self.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                f"input is not admitted to learning surface {surface.value!r}"
            )

    @_bind_external_evaluation_trust(_require_admission_graph_trust)
    def require_external_evaluation_use(self) -> None:
        """Fail closed unless this input is separately classified as external evidence only."""
        _require_exact_admission(self)
        _, _, _, disposition = _validated_admission_state(self)
        if disposition is not ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            raise ResearchInputAdmissionError(
                "input is not admitted as separately governed external evaluation evidence"
            )

    def _validated_snapshot(self) -> ResearchInputAdmissionContract:
        """Validate the live graph without recursively rebuilding equivalent objects."""
        _require_exact_admission(self)
        _validated_admission_state(self)
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        """Return semantics from one bounded, fully validated graph pass."""
        return _validated_admission_state(self)[0]

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one bounded validated graph pass."""
        _require_exact_admission(self)
        return _validated_admission_state(self)[0]

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes from one bounded validated graph pass."""
        _require_exact_admission(self)
        semantic, _, _, _ = _validated_admission_state(self)
        return canonical_semantic_bytes(semantic)

    @property
    def content_sha256(self) -> str:
        """Derive content identity outside the semantic preimage."""
        _require_exact_admission(self)
        return _validated_admission_state(self)[1]

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived content identity."""
        _require_exact_admission(self)
        data, content_sha256, _, _ = _validated_admission_state(self)
        data["content_sha256"] = content_sha256
        return data


del _bind_learning_admission_trust
del _bind_external_evaluation_trust
del _require_admission_graph_trust


def _disposition_for_classification(
    classification: ResearchInputClassification,
) -> ResearchInputDisposition:
    _require_exact_enum(classification, ResearchInputClassification, "classification")
    if classification in _LEARNING_CLASSIFICATIONS:
        return ResearchInputDisposition.LEARNING_ADMITTED
    if classification is ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE:
        return ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
    if classification in _REJECTED_CLASSIFICATIONS:
        return ResearchInputDisposition.REJECTED
    raise ResearchInputAdmissionError("unsupported research-input classification")


def _local_admission_state(
    node: ResearchInputAdmissionContract,
) -> tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition]:
    """Validate one envelope using bound parent metadata without traversing ancestry."""
    _require_exact_admission(node)
    _require_token(node.input_id, "input_id")
    _require_sha256(node.classification_policy_sha256, "classification_policy_sha256")
    _require_exact_enum(node.classification, ResearchInputClassification, "classification")
    _require_optional_sha256(node.source_artifact_sha256, "source_artifact_sha256")
    _require_optional_sha256(node.source_contract_sha256, "source_contract_sha256")
    _require_learning_surfaces(node.allowed_learning_surfaces)
    parents = node.parent_inputs
    if type(parents) is not tuple:
        raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")
    if len(parents) > _MAX_LINEAGE_NODES:
        raise ResearchInputAdmissionError(
            "research-input parent lineage exceeds the fail-closed direct-parent limit"
        )
    _require_transformation_lineage(node.transformation_kind, parents)

    disposition = _disposition_for_classification(node.classification)
    if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
        if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
            raise ResearchInputAdmissionError(
                "learning-admitted input requires exact source artifact and contract identities"
            )
        if not node.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                "learning-admitted input requires at least one explicit learning surface"
            )
        _require_source_permission_binding(node)
    elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
        if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
            raise ResearchInputAdmissionError(
                "external evaluation evidence requires exact artifact and "
                "governing contract identities"
            )
        if node.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                "external evaluation evidence cannot enter an MRL learning surface"
            )
        _require_source_permission_binding(node)
    else:
        if node.source_permission is not None:
            raise ResearchInputAdmissionError(
                "rejected input cannot carry a source permission into MRL"
            )
        if node.source_artifact_sha256 is not None or node.source_contract_sha256 is not None:
            raise ResearchInputAdmissionError(
                "rejected input cannot carry source artifact or contract identities into MRL"
            )
        if node.allowed_learning_surfaces:
            raise ResearchInputAdmissionError("rejected input cannot enter an MRL learning surface")

    parent_payloads: list[dict[str, str]] = []
    parent_digests: list[str] = []
    for parent_ref in parents:
        _require_exact_parent_ref(parent_ref)
        _require_exact_admission(parent_ref.parent_admission)
        _require_sha256(parent_ref._bound_admission_sha256, "bound parent admission sha256")
        _require_exact_enum(
            parent_ref._bound_classification,
            ResearchInputClassification,
            "bound parent classification",
        )
        _require_exact_enum(
            parent_ref._bound_disposition,
            ResearchInputDisposition,
            "bound parent disposition",
        )
        if (
            parent_ref._bound_disposition is ResearchInputDisposition.REJECTED
            and disposition is not ResearchInputDisposition.REJECTED
        ):
            raise ResearchInputAdmissionError(
                "a rejected parent cannot be transformed into an admissible MRL input"
            )
        if (
            parent_ref._bound_disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
            and disposition is ResearchInputDisposition.LEARNING_ADMITTED
        ):
            raise ResearchInputAdmissionError(
                "external evaluation evidence cannot be transformed into an MRL learning signal"
            )
        parent_payloads.append(
            {
                "admission_sha256": parent_ref._bound_admission_sha256,
                "classification": parent_ref._bound_classification.value,
                "disposition": parent_ref._bound_disposition.value,
            }
        )
        parent_digests.append(parent_ref._bound_admission_sha256)

    if tuple(parent_digests) != tuple(sorted(set(parent_digests))):
        raise ResearchInputAdmissionError(
            "parent_inputs must be unique and strictly sorted by admission_sha256"
        )

    source_permission_sha256: str | None = None
    if node.source_permission is not None:
        _require_exact_source_permission(node.source_permission)
        permission = node.source_permission._validated_snapshot()
        source_permission_sha256 = derive_content_sha256(permission._semantic_dict_validated())

    semantic: dict[str, object] = {
        "format": "MRL-RESEARCH-INPUT-ADMISSION-V1",
        "input_id": node.input_id,
        "classification_policy_sha256": node.classification_policy_sha256,
        "classification": node.classification.value,
        "disposition": disposition.value,
        "source_artifact_sha256": node.source_artifact_sha256,
        "source_contract_sha256": node.source_contract_sha256,
        "allowed_learning_surfaces": [surface.value for surface in node.allowed_learning_surfaces],
        "source_permission_sha256": source_permission_sha256,
        "transformation_kind": node.transformation_kind,
        "parent_inputs": parent_payloads,
    }
    content_sha256 = derive_content_sha256(semantic)
    return semantic, content_sha256, node.classification, disposition


def _parent_graph_postorder(
    root: ResearchInputAdmissionContract,
) -> list[ResearchInputAdmissionContract]:
    """Return parent-first order while bounding cycles, depth, and graph cardinality."""
    active: set[int] = set()
    visited: set[int] = set()
    discovered: set[int] = set()
    edge_count = 0
    order: list[ResearchInputAdmissionContract] = []
    stack: list[tuple[ResearchInputAdmissionContract, int, bool]] = [(root, 0, False)]

    while stack:
        node, depth, exiting = stack.pop()
        node_id = id(node)
        if exiting:
            active.remove(node_id)
            visited.add(node_id)
            order.append(node)
            continue
        _require_exact_admission(node)
        if node_id in active:
            raise ResearchInputAdmissionError("cyclic research-input parent lineage is forbidden")
        if depth > _MAX_LINEAGE_DEPTH:
            raise ResearchInputAdmissionError(
                "research-input parent lineage exceeds the fail-closed depth limit"
            )
        if node_id in visited:
            continue
        if node_id not in discovered:
            discovered.add(node_id)
            if len(discovered) > _MAX_LINEAGE_NODES:
                raise ResearchInputAdmissionError(
                    "research-input parent lineage exceeds the fail-closed node limit"
                )
        parents = node.parent_inputs
        if type(parents) is not tuple:
            raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")
        edge_count += len(parents)
        if edge_count > _MAX_LINEAGE_EDGES:
            raise ResearchInputAdmissionError(
                "research-input parent lineage exceeds the fail-closed edge limit"
            )
        active.add(node_id)
        stack.append((node, depth, True))
        for parent_ref in reversed(parents):
            _require_exact_parent_ref(parent_ref)
            parent = parent_ref.parent_admission
            _require_exact_admission(parent)
            stack.append((parent, depth + 1, False))

    return order


def _validated_admission_state(
    root: ResearchInputAdmissionContract,
) -> tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition]:
    """Validate and serialize an admission DAG once, memoizing every ancestor by identity."""
    states: dict[
        int,
        tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition],
    ] = {}

    for node in _parent_graph_postorder(root):
        _require_token(node.input_id, "input_id")
        _require_sha256(node.classification_policy_sha256, "classification_policy_sha256")
        _require_exact_enum(node.classification, ResearchInputClassification, "classification")
        _require_optional_sha256(node.source_artifact_sha256, "source_artifact_sha256")
        _require_optional_sha256(node.source_contract_sha256, "source_contract_sha256")
        _require_learning_surfaces(node.allowed_learning_surfaces)
        parents = node.parent_inputs
        _require_transformation_lineage(node.transformation_kind, parents)

        disposition = _disposition_for_classification(node.classification)
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires exact source artifact and contract identities"
                )
            if not node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires at least one explicit learning surface"
                )
            _require_source_permission_binding(node)
        elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence requires exact artifact and "
                    "governing contract identities"
                )
            if node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot enter an MRL learning surface"
                )
            _require_source_permission_binding(node)
        else:
            if node.source_permission is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry a source permission into MRL"
                )
            if node.source_artifact_sha256 is not None or node.source_contract_sha256 is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry source artifact or contract identities into MRL"
                )
            if node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "rejected input cannot enter an MRL learning surface"
                )

        parent_payloads: list[dict[str, str]] = []
        parent_digests: list[str] = []
        parent_dispositions: list[ResearchInputDisposition] = []
        for parent_ref in parents:
            _require_exact_parent_ref(parent_ref)
            parent = parent_ref.parent_admission
            _require_exact_admission(parent)
            parent_state = states.get(id(parent))
            if parent_state is None:
                raise ResearchInputAdmissionError("parent admission validation order is incomplete")
            _, parent_sha256, parent_classification, parent_disposition = parent_state
            _require_sha256(parent_ref._bound_admission_sha256, "bound parent admission sha256")
            _require_exact_enum(
                parent_ref._bound_classification,
                ResearchInputClassification,
                "bound parent classification",
            )
            _require_exact_enum(
                parent_ref._bound_disposition,
                ResearchInputDisposition,
                "bound parent disposition",
            )
            if (
                parent_sha256 != parent_ref._bound_admission_sha256
                or parent_classification is not parent_ref._bound_classification
                or parent_disposition is not parent_ref._bound_disposition
            ):
                raise ResearchInputAdmissionError(
                    "parent admission binding changed after reference creation"
                )
            parent_payloads.append(
                {
                    "admission_sha256": parent_sha256,
                    "classification": parent_classification.value,
                    "disposition": parent_disposition.value,
                }
            )
            parent_digests.append(parent_sha256)
            parent_dispositions.append(parent_disposition)

        if tuple(parent_digests) != tuple(sorted(set(parent_digests))):
            raise ResearchInputAdmissionError(
                "parent_inputs must be unique and strictly sorted by admission_sha256"
            )
        for parent_disposition in parent_dispositions:
            if (
                parent_disposition is ResearchInputDisposition.REJECTED
                and disposition is not ResearchInputDisposition.REJECTED
            ):
                raise ResearchInputAdmissionError(
                    "a rejected parent cannot be transformed into an admissible MRL input"
                )
            if (
                parent_disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
                and disposition is ResearchInputDisposition.LEARNING_ADMITTED
            ):
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot be transformed into an MRL learning signal"
                )

        source_permission_sha256: str | None = None
        if node.source_permission is not None:
            _require_exact_source_permission(node.source_permission)
            permission = node.source_permission._validated_snapshot()
            source_permission_sha256 = derive_content_sha256(permission._semantic_dict_validated())

        semantic: dict[str, object] = {
            "format": "MRL-RESEARCH-INPUT-ADMISSION-V1",
            "input_id": node.input_id,
            "classification_policy_sha256": node.classification_policy_sha256,
            "classification": node.classification.value,
            "disposition": disposition.value,
            "source_artifact_sha256": node.source_artifact_sha256,
            "source_contract_sha256": node.source_contract_sha256,
            "allowed_learning_surfaces": [
                surface.value for surface in node.allowed_learning_surfaces
            ],
            "source_permission_sha256": source_permission_sha256,
            "transformation_kind": node.transformation_kind,
            "parent_inputs": parent_payloads,
        }
        content_sha256 = derive_content_sha256(semantic)
        states[id(node)] = (semantic, content_sha256, node.classification, disposition)

    state = states.get(id(root))
    if state is None:
        raise ResearchInputAdmissionError("research-input graph validation produced no root state")
    return state


def _require_source_permission_binding(contract: ResearchInputAdmissionContract) -> None:
    permission = contract.source_permission
    if type(permission) is not ResearchInputSourcePermission:
        raise ResearchInputAdmissionError(
            "admissible input requires an exact ResearchInputSourcePermission"
        )
    snapshot = permission._validated_snapshot()
    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:
        raise ResearchInputAdmissionError(
            "source permission does not bind the admitted source artifact"
        )
    if contract.source_contract_sha256 != snapshot.source_contract_sha256:
        raise ResearchInputAdmissionError(
            "source permission does not bind the governing source contract"
        )
    if contract.classification is not snapshot.classification:
        raise ResearchInputAdmissionError(
            "source permission does not authorize the admitted classification"
        )
    requested = frozenset(contract.allowed_learning_surfaces)
    permitted = frozenset(snapshot.allowed_learning_surfaces)
    if not requested.issubset(permitted):
        raise ResearchInputAdmissionError(
            "source permission does not authorize the requested learning surfaces"
        )


def _require_transformation_lineage(
    transformation_kind: str | None,
    parents: tuple[ResearchInputParentRef, ...],
) -> None:
    if transformation_kind is None:
        if parents:
            raise ResearchInputAdmissionError(
                "parent inputs require an explicit transformation_kind"
            )
        return
    _require_token(transformation_kind, "transformation_kind")
    if not parents:
        raise ResearchInputAdmissionError(
            "transformed input requires at least one parent admission identity"
        )


def _require_learning_surfaces(
    surfaces: tuple[ResearchLearningSurface, ...],
) -> None:
    if type(surfaces) is not tuple:
        raise ResearchInputAdmissionError("allowed_learning_surfaces must be an exact tuple")
    values: list[str] = []
    for surface in surfaces:
        _require_exact_enum(surface, ResearchLearningSurface, "learning surface")
        values.append(surface.value)
    if tuple(values) != tuple(sorted(set(values))):
        raise ResearchInputAdmissionError(
            "allowed_learning_surfaces must be unique and strictly sorted"
        )


def _require_exact_admission(value: ResearchInputAdmissionContract) -> None:
    if type(value) is not ResearchInputAdmissionContract:
        raise ResearchInputAdmissionError(
            "research input admission requires an exact ResearchInputAdmissionContract instance"
        )


def _require_exact_parent_ref(value: ResearchInputParentRef) -> None:
    if type(value) is not ResearchInputParentRef:
        raise ResearchInputAdmissionError(
            "parent input reference must be an exact ResearchInputParentRef instance"
        )


def _require_exact_source_permission(value: ResearchInputSourcePermission) -> None:
    if type(value) is not ResearchInputSourcePermission:
        raise ResearchInputAdmissionError(
            "source permission must be an exact ResearchInputSourcePermission instance"
        )


def _require_exact_enum(value: object, expected: type[enum.Enum], label: str) -> None:
    if type(value) is not expected:
        raise ResearchInputAdmissionError(f"{label} must be an exact {expected.__name__}")


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or not _TOKEN_ID.fullmatch(value):
        raise ResearchInputAdmissionError(f"{label} must be a canonical token identifier")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise ResearchInputAdmissionError(f"{label} must be exactly 64 lowercase hex characters")


def _require_optional_sha256(value: object, label: str) -> None:
    if value is None:
        return
    _require_sha256(value, label)
