# Benchmark Publication

- **Status:** Binding strategy (ADR-0010, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03
- **Related:** [Blueprint §8](../vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md),
  [reproducibility policy](../research/reproducibility_policy.md)

MedScale-Bench publication rules are intentionally strict. A benchmark release is
**one versioned unit**: specification + data + scorers + baseline results. This policy
does not claim that a benchmark version or external mirror has already been released.

## The unit of release

| Component | Requirement |
|---|---|
| Specification | Task definitions, metric formulae, split policy, failure taxonomy — a document, versioned with the release |
| Data | Passes the [dataset checklist](release_process.md); split content hashes published when the release is authorized |
| Scorers | Deterministic, unit-tested, byte-identical re-runs demonstrated in CI; **no LLM-as-judge in any primary metric** |
| Baselines | The applicable frozen benchmark specification defines the required baselines; baseline results must be evidence-backed before publication |

## Scoring reproducibility

Published scores carry the benchmark version, model/version, required seeds and
uncertainty summary, scorer version, and applicable environment/evidence manifest. A
score whose required evidence is absent is not promoted to a published result (R7).

## Immutable versions

- Task or metric definition changes ⇒ **MAJOR** bump ⇒ a new leaderboard; old scores
  are never silently mixed with new ones.
- Additive tasks ⇒ MINOR when existing task-score comparability is preserved.
- Scorer bug fixes that change governed scores require a comparability decision and a
  visible version/erratum treatment; a score-moving fix is never silent.

## Leaderboard policy

- Repository-hosted result tables require committed manifests and reproducible outputs.
- Any future held-out test administration requires separately implemented
  infrastructure and governance; absence of that infrastructure must not be disguised
  as a live leaderboard.
- Integrity firewall (Vision §7): MedScale/Afia results follow the same published
  evaluation rules as external results; unfavorable results are not selectively hidden.

## Acceptance criteria for hosting external results

Applicable manifest complete · outputs reproducible from the governed released model +
benchmark version · licence of the evaluated model recorded · no prohibited test-split
tuning · deterministic primary metrics according to the benchmark specification.

## Publication workflow

1. Benchmark spec frozen under its applicable governance →
2. Data + scorers qualify through their checklists →
3. Required baselines run and evidence is committed →
4. GitHub Release `medscale-bench-vX.Y` under separate release authority →
5. Any Hugging Face dataset mirror or viewer is created only through a separately
   implemented, qualified, operator-approved distribution/deployment path →
6. Papers cite only the actually released benchmark version.
