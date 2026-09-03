# Model Card Requirements

- **Status:** Strategy (ADR-0010, Accepted)
- **Original strategy date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23

A MedScale model card is a *verification document*, not marketing. A card that asserts
capability without committed, applicable evidence violates R7 and fails the governed
release boundary. These are binding requirements for any future model release; they do
not imply that a model has been trained, qualified, released, or mirrored to Hugging
Face.

## 1. Identity

- Name + version, release date, canonical GitHub source tag, and applicable
  manifest/content identity.
- One-sentence honest description of the artifact and its task boundary.

## 2. Mandatory safety statements

Any released model card must carry the repository's then-current mandatory safety
statements exactly as required by the applicable accepted governance. Card text must
not imply clinical authority, PHI use, real-patient validation, or a stronger evidence
state than the canonical model/training/evaluation records support.

## 3. Model details

Base model (exact id + revision + licence tier), adapter/training method if applicable,
constraint/configuration identity, parameters touched, and compute actually used. None
of these fields may be populated from a plan or intended configuration as though an
execution occurred.

## 4. Training data

Dataset name + exact version/content identity; generator/version/seed/config where
applicable; licence/provenance evidence for every source; contamination/split evidence
when required by the applicable training/evaluation specification.

## 5. Evaluation

Benchmark name + exact version; only metrics supported by committed result artifacts;
required seeds/intervals and failure analysis when the governing evaluation contract
requires them; negative/null results reported without suppression. A card must not
convert fixture-only plumbing, planned runs, or incomplete evidence into a model-result
claim.

## 6. Limitations & out-of-scope use

State the actual evaluated domain and known gaps, including any synthetic-only or
non-clinical boundary that applies. Unmeasured transfer must be described as
unmeasured, not implied by neighboring infrastructure.

## 7. Reproduction

Pointer to the governed replication/reproduction materials that actually exist for the
release: canonical source tag, applicable manifests, exact commands, and expected
outputs. If those materials are not qualified, the model is not eligible for release.

## 8. Citation & licence

Citation block plus evidence-backed artifact/base-model licensing and attribution.
Licensing statements must follow [licensing.md](licensing.md) and the actual upstream
terms applicable to the released bytes; policy acceptance does not manufacture rights.

## Hugging Face metadata when publication is separately authorized

Any future HF mirror must carry artifact-appropriate `license`, `base_model`, source
identity, safety tags, datasets/evaluation references, and other metadata required by
the applicable publication contract. No HF model publication path is implemented or
authorized merely by this document or ADR-0010 acceptance.
