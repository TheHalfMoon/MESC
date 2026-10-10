# ADR-0042 — Kaggle reservation and billing telemetry

Status: accepted for authorized engineering scope (2026-10-10).
Hosted execution remains NOT AUTHORIZED.

## Context

The official installed Kaggle 2.2.4 SDK exposes consumed, reserved and total
weekly quota. Reserved time belongs to currently running sessions. Subtracting
only consumed time overstates the observed unreserved budget. Its generated
`ApiAcceleratorQuota` also defaults `is_pay_to_scale_enabled` to false, and
`FieldMetadata.set_from_dict` discards omitted/default values. The decoded
object cannot prove that the server explicitly reported false.

## Decision

Version private read-only telemetry as V2. Report remaining whole seconds only
when consumed and reserved durations are known, normalized, nonnegative and
their sum does not exceed the observed total. Preserve exact integer
microseconds; missing reservation leaves remaining budget unknown.

Report a true pay-to-scale flag as SDK_REPORTED_TRUE, false as
SDK_DEFAULT_OR_REPORTED_FALSE, and missing/non-boolean values as UNKNOWN.
None of these telemetry states certifies zero paid compute. Capacity, billing,
authority and hosted session admission remain independently governed.

## Consequences

- Running sessions' reservations cannot silently become a new session budget.
- Existing private V1 observations remain historical with their original meaning;
  consumers must recognize V2 semantics rather than relabel old evidence.
- This observer still performs only authentication and supported read-only calls.
  It creates no session, approval, model work or scientific readiness.
- ADR-0041's provider separation and offline-candidate boundary remain unchanged.
