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
| ALIGN-10 | Prepare final evidence-backed GO/NO-GO recommendation for publishing | owner | ALIGN-24 | done | issue #355; PR #356; `final-publication-go-no-go.md` |
| ALIGN-11 | Record hygiene NO-GO / zero eligible Group A files | owner | ALIGN-08 | done | historical disposition |
| ALIGN-12 | Audit minimum dependency-complete Phase 2 evidence/dataset foundation | owner | ALIGN-11 | done | phase2 boundary audit |
| ALIGN-13 | Capability foundation: public exports, benchmark run artifact, CLI entry, smoke tests | owner | ALIGN-12 | done | PR #10 / historical merge evidence |
| ALIGN-14 | Deterministic split-assignment freeze + governance closeout | owner | ALIGN-13 | done | PRs #12/#13 / historical merge evidence |
| ALIGN-15 | Evaluation boundary audit/reconciliation | owner | ALIGN-14 | done | `specs/align-15/` |
| ALIGN-16 | Model runtime/governance boundary audit | owner | ALIGN-15 | done | PR #15 / ADR-0033 history |
| ALIGN-17 | ModelKit public surface/runtime governance decision | owner | ALIGN-16 | done | PR #16 / ADR-0033 / `specs/align-17/` |
| ALIGN-18 | Reconcile live repository identity, ownership, and ADR index | owner | ALIGN-17 and current-main audit | done | issue #340; PR #341; merge `1f27f4128229f1c3c973355c5a14bcac2cec0dfe` |
| ALIGN-19 | Reconcile current public status, release truth, execution docs, and alignment control docs | owner | ALIGN-18 | done | issue #342; PR #343; merge `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1` |
| ALIGN-20 | Add deterministic offline fixture-only executable golden path | owner | ALIGN-19 | done | issue #344; PR #345; merge `3a632457d92bfd98075b6dc082324a9f92a89d97` |
| ALIGN-21 | Enforce clean installed-wheel release qualification | owner | ALIGN-20 | done | issue #346; PR #347; merge `5e8ee576ff51301ac94eb4876e11d777120b193d` |
| ALIGN-22 | Enforce documentation source/link hygiene readiness | owner | ALIGN-21 | done | issue #348; PR #349; merge `02b4ad0956aef613a792a1de853d31b4e1c41fda` |
| ALIGN-23 | Reconcile and ratify release/version governance | owner | ALIGN-22 | done | issue #351; PR #352; merge `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c` |
| ALIGN-24 | Qualify fail-closed TestPyPI Trusted Publishing repository path | owner | ALIGN-23 | done | issue #353; PR #354; merge `b6f26b3dedce20e559b3936e9f85f962153e826e` |

## Final closeout

- ALIGN-24 is canonically complete through issue #353 / PR #354 / merge
  `b6f26b3dedce20e559b3936e9f85f962153e826e`.
- ALIGN-10 is the final alignment task. Its evidence-backed result is recorded in
  `specs/public-repository-alignment/final-publication-go-no-go.md` under issue #355 / PR #356
  and becomes canonical only through PR #356's exact-head CI/CodeQL, substantive independent
  semantic review, review-thread reconciliation, final main/base/head/ruleset verification,
  and guarded expected-head merge.
- The Public Repository Alignment sequence has no automatic successor. Completion of this
  ledger creates no external publication, release, model/GPU execution, training, promotion,
  scientific publication, hosted-documentation deployment, product deployment, or clinical
  authority.
- Repository/source alignment is a GO outcome, while unresolved independent axes remain
  explicit NO-GO or UNVERIFIED outcomes in the final report.
- TestPyPI external activation remains separately evidence-dependent: the protected
  `testpypi` GitHub Environment, matching TestPyPI Trusted Publisher, and explicit enable
  decision must not be inferred from repository YAML.
- Production PyPI and Hugging Face publication remain separately unimplemented/unauthorized.
- Hosted documentation deployment remains not currently justified absent a concrete
  consumer/provider.
- Canonical MRL real-evidence gates remain authoritative and are not changed by this closeout.

No task in this ledger grants external-data, model/GPU execution, training, promotion,
publication, release, hosted-documentation deployment, product deployment, or clinical-use
authority unless its own separately governed scope explicitly does so.
