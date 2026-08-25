"""Canonical supervised-training example contract for MESC post-training.

The contract turns the frontier-program data requirements into deterministic,
content-addressed records and a trainer-neutral corpus. It performs no dataset,
model, provider, tokenizer, trainer, or GPU access.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from typing import Final, Literal

from medscale.provenance import validate_timestamp
from medscale.reproducibility import canonical_json, content_hash

MessageRole = Literal["system", "user", "assistant"]
TrainingOrigin = Literal["synthetic", "hand_authored_fixture"]
TrainingStage = Literal[
    "evidence_sft",
    "clinical_reasoning_sft",
    "uncertainty_sft",
    "safety_sft",
]
UncertaintyClass = Literal[
    "SUPPORTED",
    "PARTIAL",
    "INSUFFICIENT",
    "CONFLICTED",
    "STALE",
    "SAFETY_CRITICAL",
]
AbstentionTarget = Literal[
    "ANSWER_SUPPORTED",
    "ANSWER_WITH_UNCERTAINTY",
    "REQUEST_MORE_INFORMATION",
    "VERIFY_EVIDENCE",
    "ABSTAIN_INSUFFICIENT_EVIDENCE",
    "ABSTAIN_CONFLICTED_EVIDENCE",
    "ESCALATE_SAFETY",
]
ContradictionState = Literal["NONE", "PRESENT", "UNKNOWN"]
VerificationState = Literal["VERIFIED", "REJECTED", "PENDING"]
ClinicianReviewState = Literal["REVIEWED_PASS", "REVIEWED_FAIL", "PENDING"]
ContaminationState = Literal["CLEAR", "BLOCKED", "PENDING"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_STABLE_ID: Final = re.compile(r"^[a-z0-9]+(?:[._:-][a-z0-9]+)*$", flags=re.ASCII)
_LANGUAGE: Final = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$", flags=re.ASCII)
_CONTRACT_VERSION: Final = "MESC-TRAINING-EXAMPLE-V1"
_CORPUS_VERSION: Final = "MESC-SFT-CORPUS-V1"

_ALLOWED_ROLES: Final = frozenset({"system", "user", "assistant"})
_ALLOWED_ORIGINS: Final = frozenset({"synthetic", "hand_authored_fixture"})
_ALLOWED_STAGES: Final = frozenset(
    {"evidence_sft", "clinical_reasoning_sft", "uncertainty_sft", "safety_sft"}
)
_ALLOWED_UNCERTAINTY: Final = frozenset(
    {"SUPPORTED", "PARTIAL", "INSUFFICIENT", "CONFLICTED", "STALE", "SAFETY_CRITICAL"}
)
_ALLOWED_ABSTENTION: Final = frozenset(
    {
        "ANSWER_SUPPORTED",
        "ANSWER_WITH_UNCERTAINTY",
        "REQUEST_MORE_INFORMATION",
        "VERIFY_EVIDENCE",
        "ABSTAIN_INSUFFICIENT_EVIDENCE",
        "ABSTAIN_CONFLICTED_EVIDENCE",
        "ESCALATE_SAFETY",
    }
)
_ALLOWED_CONTRADICTION: Final = frozenset({"NONE", "PRESENT", "UNKNOWN"})
_ALLOWED_VERIFICATION: Final = frozenset({"VERIFIED", "REJECTED", "PENDING"})
_ALLOWED_CLINICIAN_REVIEW: Final = frozenset({"REVIEWED_PASS", "REVIEWED_FAIL", "PENDING"})
_ALLOWED_CONTAMINATION: Final = frozenset({"CLEAR", "BLOCKED", "PENDING"})


class TrainingExampleContractError(ValueError):
    """Fail-closed training-example or corpus validation error."""


@dataclass(frozen=True, slots=True)
class TrainingMessage:
    """One normalized conversational message."""

    role: MessageRole
    content: str

    def __post_init__(self) -> None:
        _require_choice(self.role, allowed=_ALLOWED_ROLES, field="message role")
        _require_text(self.content, field="message content")

    def to_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(frozen=True, slots=True)
class TrainingExampleV1:
    """One provenance-complete supervised MESC training example."""

    example_id: str
    training_record_id: str
    source_id: str
    source_revision: str
    source_license: str
    source_sha256: str
    source_timestamp: str
    origin: TrainingOrigin
    synthetic_provenance_sha256: str | None
    evidence_refs: tuple[str, ...]
    task_type: str
    specialty: str
    patient_population: str
    language: str
    training_stage: TrainingStage
    prompt: tuple[TrainingMessage, ...]
    completion: TrainingMessage
    uncertainty_class: UncertaintyClass
    abstention_target: AbstentionTarget
    contradiction_state: ContradictionState
    verification_state: VerificationState
    clinician_review_state: ClinicianReviewState
    contamination_state: ContaminationState
    contract_version: str = _CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != _CONTRACT_VERSION:
            raise TrainingExampleContractError(
                f"contract_version must be exactly {_CONTRACT_VERSION}"
            )
        _require_stable_id(self.example_id, field="example_id")
        _require_stable_id(self.training_record_id, field="training_record_id")
        _require_stable_id(self.source_id, field="source_id")
        _require_text(self.source_revision, field="source_revision")
        _require_text(self.source_license, field="source_license")
        _require_sha256(self.source_sha256, field="source_sha256")
        _require_text(self.source_timestamp, field="source_timestamp")
        try:
            validate_timestamp(self.source_timestamp, "source_timestamp")
        except ValueError as exc:
            raise TrainingExampleContractError(str(exc)) from exc

        _require_choice(self.origin, allowed=_ALLOWED_ORIGINS, field="origin")
        if self.origin == "synthetic":
            if self.synthetic_provenance_sha256 is None:
                raise TrainingExampleContractError(
                    "synthetic examples require synthetic_provenance_sha256"
                )
            _require_sha256(
                self.synthetic_provenance_sha256,
                field="synthetic_provenance_sha256",
            )
        elif self.synthetic_provenance_sha256 is not None:
            raise TrainingExampleContractError(
                "hand-authored fixtures must not claim synthetic provenance"
            )

        if not self.evidence_refs:
            raise TrainingExampleContractError("evidence_refs must be non-empty")
        for ref in self.evidence_refs:
            _require_stable_id(ref, field="evidence_refs member")
        if len(set(self.evidence_refs)) != len(self.evidence_refs):
            raise TrainingExampleContractError("evidence_refs must not contain duplicates")

        for field, value in (
            ("task_type", self.task_type),
            ("specialty", self.specialty),
            ("patient_population", self.patient_population),
        ):
            _require_text(value, field=field)
        if not isinstance(self.language, str) or _LANGUAGE.fullmatch(self.language) is None:
            raise TrainingExampleContractError("language must be a BCP-47-like language tag")
        _require_choice(self.training_stage, allowed=_ALLOWED_STAGES, field="training_stage")

        _validate_prompt(self.prompt)
        if not isinstance(self.completion, TrainingMessage):
            raise TrainingExampleContractError("completion must be a TrainingMessage")
        if self.completion.role != "assistant":
            raise TrainingExampleContractError("completion role must be exactly assistant")
        _require_choice(
            self.uncertainty_class,
            allowed=_ALLOWED_UNCERTAINTY,
            field="uncertainty_class",
        )
        _require_choice(
            self.abstention_target,
            allowed=_ALLOWED_ABSTENTION,
            field="abstention_target",
        )
        _require_choice(
            self.contradiction_state,
            allowed=_ALLOWED_CONTRADICTION,
            field="contradiction_state",
        )
        _require_choice(
            self.verification_state,
            allowed=_ALLOWED_VERIFICATION,
            field="verification_state",
        )
        _require_choice(
            self.clinician_review_state,
            allowed=_ALLOWED_CLINICIAN_REVIEW,
            field="clinician_review_state",
        )
        _require_choice(
            self.contamination_state,
            allowed=_ALLOWED_CONTAMINATION,
            field="contamination_state",
        )
        _validate_target_consistency(self)

    @property
    def eligible_for_sft(self) -> bool:
        """Whether this record may enter a canonical MESC SFT corpus."""
        return (
            self.verification_state == "VERIFIED"
            and self.clinician_review_state == "REVIEWED_PASS"
            and self.contamination_state == "CLEAR"
        )

    @property
    def example_sha256(self) -> str:
        """Deterministic identity of the complete auditable example."""
        return content_hash(self.to_dict())

    def to_trl_prompt_completion(self) -> dict[str, object]:
        """Project to TRL's conversational prompt-completion representation."""
        return {
            "prompt": [message.to_dict() for message in self.prompt],
            "completion": [self.completion.to_dict()],
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "abstention_target": self.abstention_target,
            "clinician_review_state": self.clinician_review_state,
            "completion": self.completion.to_dict(),
            "contamination_state": self.contamination_state,
            "contract_version": self.contract_version,
            "contradiction_state": self.contradiction_state,
            "evidence_refs": list(self.evidence_refs),
            "example_id": self.example_id,
            "language": self.language,
            "origin": self.origin,
            "patient_population": self.patient_population,
            "prompt": [message.to_dict() for message in self.prompt],
            "source_id": self.source_id,
            "source_license": self.source_license,
            "source_revision": self.source_revision,
            "source_sha256": self.source_sha256,
            "source_timestamp": self.source_timestamp,
            "specialty": self.specialty,
            "synthetic_provenance_sha256": self.synthetic_provenance_sha256,
            "task_type": self.task_type,
            "training_record_id": self.training_record_id,
            "training_stage": self.training_stage,
            "uncertainty_class": self.uncertainty_class,
            "verification_state": self.verification_state,
        }


@dataclass(frozen=True, slots=True)
class TrainingCorpusV1:
    """A deterministic, trainer-neutral corpus of eligible examples."""

    examples: tuple[TrainingExampleV1, ...]
    corpus_version: str = _CORPUS_VERSION

    def __post_init__(self) -> None:
        if self.corpus_version != _CORPUS_VERSION:
            raise TrainingExampleContractError(f"corpus_version must be exactly {_CORPUS_VERSION}")
        if not isinstance(self.examples, tuple):
            raise TrainingExampleContractError("training corpus examples must be a tuple")
        if not self.examples:
            raise TrainingExampleContractError("training corpus must be non-empty")
        if any(not isinstance(example, TrainingExampleV1) for example in self.examples):
            raise TrainingExampleContractError(
                "training corpus members must be TrainingExampleV1 values"
            )
        ids = [example.example_id for example in self.examples]
        if len(ids) != len(set(ids)):
            raise TrainingExampleContractError("training corpus contains duplicate example_id")
        if tuple(ids) != tuple(sorted(ids)):
            raise TrainingExampleContractError("corpus examples must be sorted by example_id")
        if any(not example.eligible_for_sft for example in self.examples):
            raise TrainingExampleContractError(
                "every corpus example must be verified, clinician-reviewed, and contamination-clear"
            )

    @property
    def corpus_sha256(self) -> str:
        return content_hash(
            {
                "corpus_version": self.corpus_version,
                "examples": [example.to_dict() for example in self.examples],
            }
        )

    @property
    def training_record_ids(self) -> tuple[str, ...]:
        """Unique sorted T5 record identifiers represented by this corpus."""
        return tuple(sorted({example.training_record_id for example in self.examples}))

    def canonical_jsonl(self) -> str:
        """Return byte-stable full-fidelity JSONL for storage and audit."""
        return "".join(canonical_json(example.to_dict()) + "\n" for example in self.examples)

    def to_trl_records(self) -> tuple[dict[str, object], ...]:
        """Return trainer projection without discarding the canonical source records."""
        return tuple(example.to_trl_prompt_completion() for example in self.examples)


def build_training_corpus(examples: Sequence[TrainingExampleV1]) -> TrainingCorpusV1:
    """Sort and freeze eligible examples into one deterministic corpus."""
    ordered = tuple(sorted(examples, key=lambda example: example.example_id))
    return TrainingCorpusV1(examples=ordered)


def _validate_prompt(prompt: object) -> None:
    if not isinstance(prompt, tuple) or not prompt:
        raise TrainingExampleContractError("prompt must be a non-empty tuple")
    messages: list[TrainingMessage] = []
    for message in prompt:
        if not isinstance(message, TrainingMessage):
            raise TrainingExampleContractError("prompt members must be TrainingMessage values")
        messages.append(message)

    system_positions: list[int] = []
    for index, message in enumerate(messages):
        if message.role == "system":
            system_positions.append(index)
    if len(system_positions) > 1 or (system_positions and system_positions[0] != 0):
        raise TrainingExampleContractError("prompt may contain at most one leading system message")
    if messages[-1].role != "user":
        raise TrainingExampleContractError("prompt must end with a user message")


def _validate_target_consistency(example: TrainingExampleV1) -> None:
    if example.abstention_target == "ANSWER_SUPPORTED":
        if example.uncertainty_class != "SUPPORTED" or example.contradiction_state != "NONE":
            raise TrainingExampleContractError(
                "ANSWER_SUPPORTED requires SUPPORTED uncertainty and no contradiction"
            )
    elif example.abstention_target == "ABSTAIN_INSUFFICIENT_EVIDENCE":
        if example.uncertainty_class != "INSUFFICIENT":
            raise TrainingExampleContractError(
                "ABSTAIN_INSUFFICIENT_EVIDENCE requires INSUFFICIENT uncertainty"
            )
    elif example.abstention_target == "ABSTAIN_CONFLICTED_EVIDENCE":
        if example.uncertainty_class != "CONFLICTED" or example.contradiction_state != "PRESENT":
            raise TrainingExampleContractError(
                "ABSTAIN_CONFLICTED_EVIDENCE requires conflicted uncertainty and contradiction"
            )
    elif example.abstention_target == "ESCALATE_SAFETY":
        if example.uncertainty_class != "SAFETY_CRITICAL":
            raise TrainingExampleContractError(
                "ESCALATE_SAFETY requires SAFETY_CRITICAL uncertainty"
            )
    elif example.abstention_target == "REQUEST_MORE_INFORMATION":
        if example.uncertainty_class not in {"PARTIAL", "INSUFFICIENT"}:
            raise TrainingExampleContractError(
                "REQUEST_MORE_INFORMATION requires PARTIAL or INSUFFICIENT uncertainty"
            )
    elif (
        example.abstention_target == "ANSWER_WITH_UNCERTAINTY"
        and example.uncertainty_class not in {"PARTIAL", "STALE"}
    ):
        raise TrainingExampleContractError(
            "ANSWER_WITH_UNCERTAINTY requires PARTIAL or STALE uncertainty"
        )


def _require_choice(value: object, *, allowed: Collection[str], field: str) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise TrainingExampleContractError(f"unsupported {field}")
    return value


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TrainingExampleContractError(f"{field} must be non-empty text without NUL")
    return value


def _require_stable_id(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _STABLE_ID.fullmatch(value) is None:
        raise TrainingExampleContractError(f"{field} must be a stable lowercase identifier")
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingExampleContractError(f"{field} must be exactly 64 lowercase hex characters")
    return value
