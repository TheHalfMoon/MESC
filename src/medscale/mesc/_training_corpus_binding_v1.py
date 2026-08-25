"""Fail-closed binding between a qualified T5 record set and one canonical SFT corpus.

The binding is pure and in-memory. It proves that the corpus represents exactly the
T5-qualified training membership and freezes both semantic corpus identity and canonical
JSONL byte identity. It performs no filesystem, dataset, model, provider, or trainer I/O.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.mesc._training_dataset_qualification_v1 import TrainingDatasetQualificationReport
from medscale.mesc._training_example_contract_v1 import TrainingCorpusV1
from medscale.reproducibility import content_hash

TrainingCorpusBindingDisposition = Literal["BLOCKED", "PASS"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_BINDING_VERSION: Final = "MESC-TRAINING-CORPUS-BINDING-V1"
_TRAINING_RECORD_SET_KIND: Final = "mesc.training_dataset.record_ids.v1"


class TrainingCorpusBindingError(ValueError):
    """Fail-closed corpus-binding construction or invocation error."""


@dataclass(frozen=True, slots=True)
class TrainingCorpusBindingReport:
    """Content-addressed proof that one SFT corpus matches one qualified T5 train set."""

    disposition: TrainingCorpusBindingDisposition
    qualification_sha256: str
    training_dataset_sha256: str
    qualified_training_record_ids_sha256: str
    corpus_sha256: str
    corpus_training_record_ids_sha256: str
    canonical_jsonl_sha256: str
    canonical_jsonl_byte_count: int
    example_count: int
    blockers: tuple[str, ...]
    binding_version: str = _BINDING_VERSION

    def __post_init__(self) -> None:
        if self.binding_version != _BINDING_VERSION:
            raise TrainingCorpusBindingError(f"binding_version must be exactly {_BINDING_VERSION}")
        if self.disposition not in ("BLOCKED", "PASS"):
            raise TrainingCorpusBindingError("disposition must be exactly BLOCKED or PASS")
        for field, value in (
            ("qualification_sha256", self.qualification_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("qualified_training_record_ids_sha256", self.qualified_training_record_ids_sha256),
            ("corpus_sha256", self.corpus_sha256),
            ("corpus_training_record_ids_sha256", self.corpus_training_record_ids_sha256),
            ("canonical_jsonl_sha256", self.canonical_jsonl_sha256),
        ):
            _require_sha256(value, field=field)
        for count_field, count_value in (
            ("canonical_jsonl_byte_count", self.canonical_jsonl_byte_count),
            ("example_count", self.example_count),
        ):
            if type(count_value) is not int or count_value < 0:
                raise TrainingCorpusBindingError(f"{count_field} must be a non-negative int")
        if not isinstance(self.blockers, tuple):
            raise TrainingCorpusBindingError("blockers must be an immutable tuple")
        if any(not isinstance(blocker, str) or not blocker for blocker in self.blockers):
            raise TrainingCorpusBindingError("blockers must contain non-empty strings only")

        if self.disposition == "PASS":
            if self.blockers:
                raise TrainingCorpusBindingError("PASS binding cannot have blockers")
            if self.qualified_training_record_ids_sha256 != self.corpus_training_record_ids_sha256:
                raise TrainingCorpusBindingError(
                    "PASS binding requires exact T5/corpus training-record identity equality"
                )
            if self.canonical_jsonl_byte_count <= 0:
                raise TrainingCorpusBindingError(
                    "PASS binding requires positive canonical_jsonl_byte_count"
                )
            if self.example_count <= 0:
                raise TrainingCorpusBindingError("PASS binding requires positive example_count")

    @property
    def can_attest_local_artifact(self) -> bool:
        """Whether downstream local artifact attestation may consume this binding."""
        return self.disposition == "PASS" and not self.blockers

    @property
    def binding_sha256(self) -> str:
        """Deterministic identity of the complete corpus-binding report."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "binding_version": self.binding_version,
            "blockers": list(self.blockers),
            "canonical_jsonl_byte_count": self.canonical_jsonl_byte_count,
            "canonical_jsonl_sha256": self.canonical_jsonl_sha256,
            "corpus_sha256": self.corpus_sha256,
            "corpus_training_record_ids_sha256": self.corpus_training_record_ids_sha256,
            "disposition": self.disposition,
            "example_count": self.example_count,
            "qualification_sha256": self.qualification_sha256,
            "qualified_training_record_ids_sha256": self.qualified_training_record_ids_sha256,
            "training_dataset_sha256": self.training_dataset_sha256,
        }


def bind_training_corpus(
    *,
    qualification: TrainingDatasetQualificationReport,
    corpus: TrainingCorpusV1,
) -> TrainingCorpusBindingReport:
    """Bind one exact canonical corpus to one exact T5 qualification, fail closed."""
    if type(qualification) is not TrainingDatasetQualificationReport:
        raise TrainingCorpusBindingError(
            "qualification must be an exact TrainingDatasetQualificationReport"
        )
    if type(corpus) is not TrainingCorpusV1:
        raise TrainingCorpusBindingError("corpus must be an exact TrainingCorpusV1")

    corpus_record_ids_sha256 = _training_record_ids_sha256(corpus.training_record_ids)
    canonical_jsonl_bytes = corpus.canonical_jsonl().encode("utf-8")
    canonical_jsonl_sha256 = hashlib.sha256(canonical_jsonl_bytes).hexdigest()

    blockers: list[str] = []
    if not qualification.can_bind_to_readiness:
        blockers.append("training dataset qualification is not PASS")
    if corpus_record_ids_sha256 != qualification.training_record_ids_sha256:
        blockers.append("corpus training-record identity does not match T5 qualification")
    if not canonical_jsonl_bytes:
        blockers.append("canonical training corpus JSONL is empty")
    if not corpus.examples:
        blockers.append("canonical training corpus has no examples")

    disposition: TrainingCorpusBindingDisposition = "BLOCKED" if blockers else "PASS"
    return TrainingCorpusBindingReport(
        disposition=disposition,
        qualification_sha256=qualification.qualification_sha256,
        training_dataset_sha256=qualification.training_dataset_sha256,
        qualified_training_record_ids_sha256=qualification.training_record_ids_sha256,
        corpus_sha256=corpus.corpus_sha256,
        corpus_training_record_ids_sha256=corpus_record_ids_sha256,
        canonical_jsonl_sha256=canonical_jsonl_sha256,
        canonical_jsonl_byte_count=len(canonical_jsonl_bytes),
        example_count=len(corpus.examples),
        blockers=tuple(blockers),
    )


def _training_record_ids_sha256(record_ids: tuple[str, ...]) -> str:
    """Reproduce the T5 record-set identity algorithm exactly."""
    return content_hash(
        {
            "kind": _TRAINING_RECORD_SET_KIND,
            "record_ids": sorted(record_ids),
        }
    )


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingCorpusBindingError(f"{field} must be exactly 64 lowercase hex characters")
    return value
