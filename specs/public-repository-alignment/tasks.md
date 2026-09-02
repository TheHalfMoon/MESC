# Public Repository Alignment — Tasks

| ID | Task | Owner | Deps | Status | Evidence |
|---|---|---|---|---|---|
| ALIGN-01 | Capture divergence audit output and classify uncommitted files by risk/phase | owner | — | done | historical audit |
| ALIGN-02 | Enumerate public/experimental/internal exports for M17–M18 surfaces | owner | ALIGN-01 | done | historical export scan |
| ALIGN-03 | Document README/roadmap drift relative to code | owner | ALIGN-01 | done | historical audit |
| ALIGN-04 | Document version metadata mismatches | owner | ALIGN-01 | done | historical version scan |
| ALIGN-05 | Document docs/ADR index gaps | owner | ALIGN-03 | done | historical docs audit |
| ALIGN-06 | Propose public API stability classification | owner | ALIGN-02 | done | historical classification |
| ALIGN-07 | Draft dependency-ordered public repository alignment sequence | owner | ALIGN-04, ALIGN-06 | done | plan/report history |
| ALIGN-08 | Run quality/build verification and capture evidence | owner | — | done | historical verification |
| ALIGN-09 | Install built wheel in a clean environment and run core smoke commands | owner | ALIGN-08 | done | historical clean-wheel smoke |
| ALIGN-10 | Prepare final evidence-backed GO/NO-GO recommendation for publishing | owner | later alignment predecessors | pending | final report not yet authorized/completed |
| ALIGN-11 | Record hygiene NO-GO / zero eligible Group A files | owner | ALIGN-08 | done | historical disposition |
| ALIGN-12 | Audit minimum dependency-complete Phase 2 evidence/dataset foundation | owner | ALIGN-11 | done | phase2 boundary audit |
| ALIGN-13 | Capability foundation: public exports, benchmark run artifact, CLI entry, smoke tests | owner | ALIGN-12 | done | PR #10 / historical merge evidence |
| ALIGN-14 | Deterministic split-assignment freeze + governance closeout | owner | ALIGN-13 | done | PRs #12/#13 / historical merge evidence |
| ALIGN-15 | Evaluation boundary audit/reconciliation | owner | ALIGN-14 | done | `specs/align-15/` |
| ALIGN-16 | Model runtime/governance boundary audit | owner | ALIGN-15 | done | PR #15 / ADR-0033 history |
| ALIGN-17 | ModelKit public surface/runtime governance decision | owner | ALIGN-16 | done | PR #16 / ADR-0033 / `specs/align-17/` |
| ALIGN-18 | Reconcile live repository identity, ownership, and ADR index | owner | ALIGN-17 and current-main audit | done | issue #340; PR #341; merge `1f27f4128229f1c3c973355c5a14bcac2cec0dfe` |
| ALIGN-19 | Reconcile current public status, release truth, execution docs, and alignment control docs | owner | ALIGN-18 | in progress | issue #342; exact base `1f27f4128229f1c3c973355c5a14bcac2cec0dfe` |

## Successor ordering

- Do not open ALIGN-20 until ALIGN-19 is finished, exact-head qualified, merged, and post-merge verified.
- Intended next subject after ALIGN-19, if the canonical post-merge audit still supports it: Phase 6 deterministic offline fixture-only golden path.
- Phase 7 hardening follows only through separately scoped tickets for **remaining** gaps. Current audit already finds action SHA pinning, coverage enforcement, package build/roundtrip qualification, CODEOWNERS, and issue/PR templates implemented.
- ALIGN-10 remains the final evidence synthesis and does not itself publish anything.

No task in this ledger grants external-data, model/GPU execution, training, promotion, publication, release, or deployment authority unless its own canonical scope explicitly does so.
