# Versioning

- **Status:** Binding policy (ADR-0011, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03

One rule everywhere: **a version identifies immutable content.** Anything changed is a
new version. Content hashes (`medscale.reproducibility.content_hash`) back identity
checks wherever the artifact is data.

The current package baseline at governance reconciliation is `0.2.0`. This policy does
not itself authorize a version bump or new tag.

## Per-class schemes

| Class | Scheme | MAJOR means | MINOR means | PATCH means |
|---|---|---|---|---|
| Python package | SemVer `X.Y.Z` | Breaking API | Additive API | Fixes only |
| Models | `vX.Y` | Base model, objective, or task-definition change (scores not comparable) | Retrain/content change with same task + base | — (no silent weight patches; any weight change is at least MINOR) |
| Datasets | `vX.Y` | Schema or generation change breaking comparability | Additive rows/fields, same schema | — |
| Benchmarks | `vX.Y` | Task or metric definition change → **new leaderboard** | Additive tasks/slices; existing scores stay valid | — |
| Evidence/knowledge/FHIR schemas | Integer `1, 2, …` (append-only, ADR-0009) | Any governed non-compatible change | — | — |
| Documentation | Repository git history + release tags snapshot the docs | — | — | — |
| ADRs | Immutable once Accepted; policy changes require a new ADR with `Supersedes:` | — | — | — |

**Why models/datasets/benchmarks drop PATCH:** a "patch" to data or weights silently
changes results; forcing MINOR makes every content change visible in citations.

## Package pre-1.0 policy

`0.Y.Z`: MINOR may break API when explicitly recorded; PATCH does not intentionally
break the public API. **1.0.0 criterion** remains evidence-dependent rather than
calendar-driven: the core MESC/benchmark/litdb promise must be demonstrated by its
applicable canonical evidence before 1.0.0 is justified.

## Version sources (single-sourced, no drift)

| Class | Source of the number |
|---|---|
| Package | `src/medscale/__about__.py` (wired to package metadata) |
| Git tags | Package: `vX.Y.Z`; other artifacts: `<artifact>-vX.Y` |
| Datasets/models | The governed tag + release manifest/card metadata |
| Schemas | The `schema_version` field in the governed objects |

**Why per-artifact tags in one repo:** MedScale is a single-repo program (ADR-0004);
prefixed tags give each artifact class an independent release cadence without
splitting the repository.

## Cross-version compatibility statements

Every model release names the benchmark version it was evaluated on; every benchmark
MAJOR bump states explicitly that prior scores are incomparable; every dataset release
names its schema integer. A release missing required compatibility/provenance metadata
fails its applicable gate rather than receiving an inferred version claim.
