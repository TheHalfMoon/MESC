# MRL-0809 Evidence-Recovery-3 — authorized engineering entry

Status: IMPLEMENTATION_IN_PROGRESS / NO_HOSTED_ALLOCATION_AUTHORITY.

## Authority and canonical predecessor

The Founder accepted `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3`
in [Issue #450 acceptance comment](https://github.com/TheHalfMoon/MESC/issues/450#issuecomment-6064511682).
The original [proposal](../../specs/mesc-experiment-0/mrl-0809-successor-v2/founder-decision-evidence-recovery-3-proposal.md)
remains historical **PROPOSED_ONLY** evidence; the later Founder acceptance is the
separate controlling decision. Never rewrite the historical proposal.

Recovery-2 failure record was normally merged as [PR #542](https://github.com/TheHalfMoon/MESC/pull/542):

- Canonical outcome merge SHA: `60ec9973694a8b64cc2ae58cd5e5a2e410d91b91`
- Canonical outcome tree: `0add794a81ba68aaa61fd2f23da7280baefbf9e7`
- Exact Recovery-2 failure-record SHA-256:
  `af1c2ddb2c5b7b046ce441a6cbe717071fd3962114f280c4deea01fdb62aafba`
- Disposition: `FAIL_HOST_PREFLIGHT_BEFORE_RUNTIME`; the only Recovery-2
  allocation was consumed and stopped, with provider unassignment observed.
- Zero model staging, zero BMM preflight, zero model probe or runtime PASS.

## Current engineering grain

This grain implements a separately versioned **read-only** Colab Free control-plane
validator and CLI observer. It requires the frozen session identity, T4 GPU,
STANDARD machine shape, a zero paid-compute-unit balance and the expected
number of assignments. It does **not** require a nominal rate of zero.
The nominal hourly usage rate is provider telemetry, **not** a monetary charge
receipt, and a positive rate does not by itself authorize or disqualify
free-tier compute. Unmeasured monetary charges must never be called zero.

The observer may read the active provider endpoint **in memory only** to compare
assignment identity. It deliberately excludes the endpoint from output files
and standard output. The CLI performs no allocation, purchases, training,
model calls, retries, relaunches, or automatic stops.

The validated source is:

- `src/medscale/mesc/_mrl_0809_evidence_recovery_3_control_plane_v1.py`
- `scripts/mesc_mrl_0809_evidence_recovery_3_control_plane.py`

This is an **engineering-only, unarmed** prerequisite. It neither implements
the complete Recovery-3 host/driver/authority chain nor licenses Colab
allocation, RQ1 scientific execution, trust admission, or closeout.

## Remaining implementation and effectiveness gates

1. Version and freeze the Recovery-3 authorization, static manifest, and
   fail-closed canonical authority gate against the exact predecessor merge
   and failure-record SHA-256.
2. Implement versioned Recovery-3 one-shot allocator, remote driver, host
   retention, all required custody artifacts, byte/hash verification, and
   ACK hold. Preserve source contracts and the exact frozen Qwen/Gemma
   revisions, NF4 runtime representation, no offload and synthetic-only scope.
3. Integrate the before/after provider observation with host operator
   controls and fail closed on paid-unit use, wrong hardware, missing
   authority, dirty or moved canonical main, and failed retention.
4. Complete positive, negative, adversarial and regression testing, real
   Jev and Alibaba OpenCodeReview accounting, independent engineering and
   security reviews, exact-head CI and documentation checks.
5. Obtain **new Founder approval of the final Recovery-3 implementation
   SHA** before a normal merge; then pass all four fresh-main workflows and
   a clean live canonical authority gate.
6. Only then evaluate the sole free STANDARD-T4 allocation. Persist the
   host consumption receipt *before* attempting allocation; its first
   invocation consumes the grant even if it fails. Never retry/relaunch.
   No purchased units, CPU/disk offload, candidate substitution, scientific
   RQ1, training, PHI, trust admission, promotion, release or closeout.

Recovery-1 and Recovery-2 failure records and their originals remain
immutable and must never be overwritten or relabeled.
