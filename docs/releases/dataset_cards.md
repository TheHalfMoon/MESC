# Dataset Card Requirements

- **Status:** Binding strategy (ADR-0010, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03

A dataset card answers three questions with evidence: *where did every field come
from, what may you do with it, and how do you rebuild it byte-for-byte.* These are
release requirements, not evidence that a dataset or external mirror already exists.

## Required sections

### 1. Identity

Name + version, release date, GitHub tag, content hash of the canonical export, size
(records/bytes), schema version.

### 2. Provenance

- **Literature-derived** (litdb): source APIs, query-set commit SHA
  (search_strategy), run manifests, PRISMA counts per stage (identified → included),
  screening log reference. Every released record carries the applicable resolvable
  identifier and verification provenance (R1).
- **Synthetic** (bench/FHIR data): generator + version + seed + config hash; corruption
  taxonomy and sampling parameters; validator identity used for labels where applicable.
- **PHI statement:** the release card must state the actual governed data boundary; no
  release may imply real-patient data authority where none exists (R2).

### 3. Schema & metadata model

Field table: name, type, source, licence class per field. For litdb: the applicable
litdb schema and evidence/verification fields. For bench data: task format, split
definitions, and split content identities required by contamination controls.

### 4. Licensing (field-level where composite)

Per [licensing.md](licensing.md): use the applicable dataset licence only when
provenance/upstream terms support it; composite sources require a field-level table,
required attribution, and explicit exclusions. The card must say what consumers may do
without inventing rights not established by release evidence.

### 5. Validation

Record the validation required by the applicable release gate and its actual output.
Do not claim schema, licence, contamination, or count validation unless that check was
implemented and executed for the released artifact.

### 6. Versioning & immutability

This version's diff vs prior (added/removed/changed and why); statement that the
snapshot is immutable; DOI only if/when a separately governed archival/publication path
has actually created one.

### 7. Known limitations

State the limitations supported by the released artifact's evidence, including relevant
coverage, operator, and synthetic/external-validity constraints.

### 8. Reproduction & citation

Rebuild instructions backed by the released tooling/evidence; exact source/tag pointer;
CFF/BibTeX or other citation metadata as applicable.

## External distribution metadata

Any Hugging Face or other external metadata block is populated only when that
distribution path is separately implemented, qualified, and authorized. It must bind
back to the GitHub source/release identity and preserve the applicable licence,
provenance, safety, and version metadata.
