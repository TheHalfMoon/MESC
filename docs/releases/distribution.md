# Distribution Strategy

- **Status:** Strategy (ADR-0010, Accepted)
- **Original strategy date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23
- **Related:** [distribution_hf.md](../architecture/distribution_hf.md) (identity record),
  [ADR-0003](../adr/0003-repository-topology.md)

## Direction of truth

```
GitHub  ──►  CI  ──►  GitHub Releases  ──►  Hugging Face  ──►  Users
```

This diagram is the accepted distribution direction, not a claim that every downstream
publisher is currently implemented.

**Never the reverse.** Concretely:

- No artifact may originate on HF; any future HF repo must mirror a governed GitHub
  release.
- No manual editing on HF: card fixes must originate in GitHub and be redistributed
  through an authorized CI path.
- Any future HF mirror must record the source tag and manifest/content identity needed
  to detect drift.
- If a downstream mirror disappeared, GitHub remains the canonical source of record.

Canonical `main` currently implements package build, exact-artifact qualification,
version/tag binding, and a tag-driven GitHub Release path in
`.github/workflows/release.yml`. It does **not** currently implement or authorize
TestPyPI/PyPI or Hugging Face publication.

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

TestPyPI and PyPI trusted-publishing paths are **not implemented** in canonical `main`.
They remain separately gated successor work. A future implementation must use CI-only
trusted publishing/OIDC, least privilege, an explicitly governed environment/approval
boundary, and the exact artifact that already passed build, byte-identity,
clean-install, and version-binding qualification. Local `twine` uploads and long-lived
publishing tokens are not an approved substitute.

The current package version/tag baseline `0.2.0` is not evidence of PyPI publication and
does not itself authorize one.
