"""ADR-0018 regressions for ADR-0020 public constructor compatibility."""

from medscale.evidence import EvidenceObject, ExtractionMethod, StudyType, VerificationState
from medscale.provenance import Provenance, SourceAPI


def test_legacy_positional_schema_version_keeps_its_argument_slot() -> None:
    provenance = Provenance(
        SourceAPI.PUBMED,
        "10.1000/legacy-positional",
        "2026-07-10T00:00:00+00:00",
        "b" * 64,
    )
    obj = EvidenceObject(
        "Legacy positional claim.",
        StudyType.COHORT,
        provenance,
        "2026-07-10T00:00:00+00:00",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "medscale-study-design-v1",
        "3",
        ExtractionMethod.HUMAN,
        VerificationState.UNVERIFIED,
        "legacy-schema-version",
    )

    assert obj.schema_version == "legacy-schema-version"
    assert obj.identity_version == 1
