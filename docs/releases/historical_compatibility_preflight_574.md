# MedOrigin — Historical v0.2.0 Compatibility Preflight

- **Status:** Source-structural audit complete; behavioral/data compatibility audit **OPEN**
- **Audit date:** 2026-10-17
- **Historical baseline:** annotated `v0.2.0`, dereferenced commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`
- **Compared protected main:** `261bee561176d2288878b94ff46ceaf8beb34a2a` (PR #582 documentation merged)
- **Purpose:** Inform [issue #574](https://github.com/TheHalfMoon/MedOrigin/issues/574) and the [unapproved successor-version dossier](successor_version_decision_574.md), **not** assert complete compatibility or approve `0.3.0`

## Scope and reproducibility

The historical annotated tag `v0.2.0` resolves to source commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`. The comparison uses immutable git commit objects, not a mutable package index or artifacts rebuilt from another SHA. The commands below require a local clone containing both commits, with `HEAD` and research files left untouched.

```bash
git diff --name-status d2e651a55c92f2218aca49acaa5b7bd18a75f096 261bee561176d2288878b94ff46ceaf8beb34a2a -- src/medscale
git diff --numstat d2e651a55c92f2218aca49acaa5b7bd18a75f096 261bee561176d2288878b94ff46ceaf8beb34a2a -- src/medscale/__init__.py src/medscale/workspace.py src/medscale/reproducibility.py src/medscale/_layout.py src/medscale/cli/__init__.py src/medscale/cli/dataset.py
git diff -U4 d2e651a55c92f2218aca49acaa5b7bd18a75f096 261bee561176d2288878b94ff46ceaf8beb34a2a -- src/medscale/cli/dataset.py
```

The `src/medscale` source comparison includes **187 changed paths: 160 added, 26 modified, 1 deleted**. A large number of new modules is not automatically a breaking API change, but this volume precludes any claim that a few unchanged facades prove binary, runtime, persistence or scientific-result compatibility.

## Verified static invariants

| Surface | Historical-to-current evidence | What the evidence does **not** prove |
| --- | --- | --- |
| `src/medscale/__init__.py` | **Byte-identical file** (49 lines); the same 12 symbols in `__all__`: `Benchmark`, `Corpus`, `Evidence`, `EvidenceQueryResult`, `RecordQueryResult`, `Snapshot`, `VerificationEngine`, `Workspace`, `__version__`, `canonical_json`, `content_hash`, `set_global_seed` | Identical runtime behavior of transitively imported modules |
| `src/medscale/workspace.py` | **Byte-identical file** (279 lines), containing the same seven named facade classes | Semantics of underlying stores, scorers, corpus data or IO |
| `src/medscale/reproducibility.py` | No source-file diff at these commits | Every downstream identity or result byte remains identical |
| `src/medscale/_layout.py` | No source-file diff at these commits | Every added writer uses the historic layout/format rules |
| `src/medscale/cli/__init__.py` | Seven legacy dispatcher commands retained; six additive commands introduced | Flags, outputs, error codes, files or stdout compatibility in every command |

**Legacy CLI commands preserved by name:** `screen`, `extract`, `check`, `stats`, `snapshot`, `bench`, `dataset`.

**New additive dispatcher names:** `fhir`, `mesc-eval`, `mesc-b1-eval`, `mesc-b1-evidence`, `mesc-machine-state`, `mesc-fixture-smoke`.

The root version is still `medscale 0.2.0`, independently derived by Hatch from `src/medscale/__about__.py`. Preserving the import and console command **names** does not change the rule that any successor release must use a separately approved, new immutable tag.

## Concrete behavioral/data-contract change requiring review

`src/medscale/cli/dataset.py` changed from the historical tag (11 added and 11 deleted lines). In `dataset freeze`, the old sequence wrote the base manifest, computed checksums, then rewrote `manifest.json` to add `dataset_fingerprint`; that could leave `checksums/manifest.json.sha256` stale relative to the bytes finally shipped.

Current code instead computes the fingerprint against the base manifest, writes the fingerprint-bearing final manifest, and **then** computes checksum files, using explicit LF newline handling. The committed code comments identify the former ordering as a self-invalidating freeze bug.

This is desirable integrity hardening, **but it can alter persisted manifest/checksum bytes** between historical `v0.2.0` and the current developer source. Under [ADR-0017](../adr/0017-identifier-stability-contract.md), [ADR-0020](../adr/0020-public-api-stability.md), and [versioning policy](versioning.md), treating it as an invisible patch would be unsafe. The exact old-record read/validate/migrate contract and source-to-output regression evidence must be assessed before approving `0.3.0`. Do not rewrite prior dataset receipts or attest that the old outputs were byte-identical.

The `dataset init` schema writer also now uses explicit LF newline handling; on affected hosts this may alter newly generated `schema.json` bytes. There is no assertion here of observed Windows-vs-Linux output differences; it is a source-derived risk to check.

## Required dynamic and policy checks before successor version adoption

- [ ] Differentially exercise the seven historical CLI commands against matching, non-sensitive pinned synthetic fixture inputs, capturing exit status, stdout/stderr and all output artifact hashes on both historical `v0.2.0` and candidate source in isolated Python 3.11/3.12 environments. Distinguish approved additive behavior from changes requiring a changelog or migration.
- [ ] Run `dataset init → manifest → freeze → validate` under historical and successor sources with equal synthetic fixtures and pinned timezone/seed; inspect `manifest.json`, `dataset_fingerprint`, checksums and hash identities. Test old-on-new reads and whether checksums produced by the historical faulty ordering fail integrity; **do not repair historical research artifacts in place**.
- [ ] Review public-frozen root-export constructor/method signatures and documented semantics transitively; unchanged facade files alone are insufficient if imported internals changed.
- [ ] Inventory **all governed persisted formats and identifiers** reachable from the public API under ADR-0017 and ADR-0020; supply append-only migration tools/ADRs for actual breaking changes, rather than cosmetic version bumps.
- [ ] Inspect the 187 changed `src/medscale` paths for optional backend side effects, new implicit dependencies, stability-class regressions and third-party rights if anything vendored is proposed for redistribution.
- [ ] On an *authorized future* new-version candidate, test both independent distribution wheels and sdists in isolated hosted Python 3.11/3.12 clean installs, with provenance and license bytes, exact matching installed metadata/CLI/tag, no-PHI/no-backflow regressions, and exact-head CI/CodeQL.

## Release boundary

The root `pyproject.toml` and `uv.lock` are held to frozen MRL-0809 byte identities: SHA-256 `c36c33208236dafb136a147dfff0060d592e23daab4b4240521d4747d23ea510` and `6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4`. A successor MedOrigin-branded metadata change requires an independently authorized research-input reconciliation, as described in the version-decision dossier. The historical `v0.2.0` tag remains immutable. No current source-preflight receipt authorizes version bumps, external publisher activation, GitHub tag/Release creation, patient/PHI data, EHR operations, GPU experiments or scientific/clinical readiness claims.

**Disposition:** preliminary public-source stability **PASS in the specifically enumerated unchanged surfaces**; full behavioral/persisted-format compatibility **PENDING**; new version, publication and clinical/scientific readiness **NOT AUTHORIZED**.
