# Distribution Strategy

- **Status:** Strategy (ADR-0010, Accepted)
- **Original strategy date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23; TestPyPI repository path added under ALIGN-24
- **Related:** [distribution_hf.md](../architecture/distribution_hf.md) (identity record),
  [ADR-0003](../adr/0003-repository-topology.md)

## Direction of truth

```text
GitHub  ──►  CI  ──►  GitHub Releases  ──►  Separately authorized distribution  ──►  Users
```

This diagram is the accepted distribution direction, not a claim that every downstream
publisher is currently activated.

**Never the reverse.** Concretely:

- No artifact may originate on HF or a package index; external distribution follows a
  governed GitHub release and its exact qualified artifacts.
- No manual editing/upload on downstream surfaces: fixes must originate in GitHub and
  be redistributed through an authorized CI path.
- Any future mirror must record the source tag and manifest/content identity needed to
  detect drift.
- If a downstream surface disappeared, GitHub remains the canonical source of record.

Canonical `main` implements package build, exact-artifact qualification, version/tag
binding, and a tag-driven GitHub Release path in `.github/workflows/release.yml`.
ALIGN-24 adds a fail-closed TestPyPI repository path after GitHub Release creation. The
path is not externally activated by repository code and does not authorize production
PyPI or Hugging Face publication.

## GitHub Releases

| Element | Policy |
|---|---|
| Tags | `vX.Y.Z` (package), `<artifact>-vX.Y` (models/datasets/benchmarks) |
| Release notes | CHANGELOG excerpt + applicable manifest/evidence links |
| Assets | Qualified artifacts appropriate to the release class |
| Immutability | Tags are never moved; published release artifacts are never replaced in place |

The repository already has the historical package tag `v0.2.0`. Later release-workflow
hardening must not be projected backward as evidence that this historical tag passed
checks added after it was created.

## Hugging Face distribution target

The MedScaleAI Hugging Face organization is a planned downstream distribution surface,
not a second source of truth. Model, dataset, Space, and collection publication remains
artifact-specific future work and requires separately applicable governance, evidence,
rights review, release qualification, and publication authority.

### Naming conventions

- Repos use `lowercase-kebab`; models carry family + task (`mesc-fhir`); datasets carry
  the `medscale-` prefix.
- Versions are identified by the governed source release/tag and mirrored metadata;
  downstream repository names do not replace canonical GitHub version identity.

### Required metadata when a mirror is authorized

| Field | Requirement |
|---|---|
| `license` | Evidence-backed licence identifier matching [licensing.md](licensing.md) |
| `tags` | Artifact-appropriate metadata, including safety classification where applicable |
| `base_model` (models) | Exact base id + revision when applicable |
| Source pointer | Canonical GitHub repository + release/tag + applicable manifest/content identity |
| Cards | Per [model_cards.md](model_cards.md) / [dataset_cards.md](dataset_cards.md) |

### Space policy

Any future Space may demonstrate **released and authorized** artifacts only, must pin
exact versions, must not collect PHI, and must remain a downstream view rather than a
canonical source.

## TestPyPI / PyPI

ALIGN-24 implements a **repository-side TestPyPI Trusted Publishing path**. It runs only
on the governed `v*` tag workflow after successful GitHub Release creation, downloads
the exact same-run qualified distribution artifact, performs no rebuild, scopes
`id-token: write` to the publishing job, references `environment: testpypi`, and uses
the SHA-pinned official PyPA publishing action against TestPyPI.

The path remains **disabled by default** behind
`vars.TESTPYPI_PUBLISH_ENABLED == 'true'`. Repository code neither sets that variable
nor proves that the `testpypi` GitHub Environment is protected or that TestPyPI has the
matching Trusted Publisher. Those external controls require independent evidence and
operator approval before the enable guard may be set true. A workflow environment name
alone is not evidence of protection.

Production PyPI remains unimplemented and separately gated. Local `twine` uploads,
long-lived publishing tokens, and manual web uploads are not approved substitutes.

The current package version/tag baseline `0.2.0` is not evidence of TestPyPI/PyPI
publication and does not itself authorize one.
