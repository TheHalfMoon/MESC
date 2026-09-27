# CW-013 Canonical Closeout Evidence

- **Task:** CW-013 -- Bounded FHIR R4 import/export
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main; see section 8)
- **Parent issue:** [#504](https://github.com/TheHalfMoon/MESC/issues/504) -- CW-013 activation
- **Implementation PR:** [#505](https://github.com/TheHalfMoon/MESC/pull/505) -- `codex/feat/cw-013-fhir-r4`
- **Qualified head:** `8c837f6e83f6a53ab47028b6c6cf0997e7f528e5`
- **Head tree:** `d179aa6ac3336893ffcc22e5cde6e98429e5e47e`
- **Base:** `ad16af4feaa5692a90482393e662b09b33950d70` (CW-012 closeout merge)
- **Canonical merge SHA:** `235df781f9372d6479cd00bfc7ab60ce7449743b`
- **Canonical merge tree:** `d179aa6ac3336893ffcc22e5cde6e98429e5e47e`
- **Merge parents:** `ad16af4feaa5692a90482393e662b09b33950d70` (previous canonical `main`), `8c837f6e83f6a53ab47028b6c6cf0997e7f528e5` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, or autonomous-action authority.

## 1. Governance state entering implementation

```text
CW-001 through CW-012 CLOSED_CANONICAL
CW-012 closeout merge                ad16af4feaa5692a90482393e662b09b33950d70
CW-013                               activated under Issue 504 as the single active unit under R4
gating contracts                     no new ADR required; synthetic-only deterministic path under Issue 504 activation contract
model contract                       NONE -- no real generation model selected, admitted, or ratified
authorization                        synthetic fixtures only; no network connectors, no remote retrieval, no model download, no paid compute, no PHI
new dependencies                     none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `8c837f6e83f6a53ab47028b6c6cf0997e7f528e5` on base `ad16af4feaa5692a90482393e662b09b33950d70`:

- CI run `36309007710` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, docs link hygiene, diff check, strict mypy
- CodeQL run `36309007732` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- mergeable MERGEABLE with clean merge state at merge time (protected merge completed 2026-09-27T10:21:52Z)
- unresolved review threads immediately before merge: 0
- approving reviews on the PR: none recorded; the merge was executed directly by the Founder (see section 2.5)

### 2.1 Review lanes for PR 505, recorded honestly

```text
Jev bounded review         CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider) on the FINAL effective
diff (head 8c837f6), after the forward-only size-bound fix. Nine yes/no probes over synthetic-only
design facts; no PHI, real patient data, secrets, credentials, API keys, production data, or
sealed MRL material sent. Results, all no: stale-state acceptance 0.03, provenance bypass 0.04,
cross-workspace leakage 0.02, unsupported-state promotion 0.02, malicious-content authority 0.02,
export-containment escape 0.03, hidden network/model 0.02, security-label loss 0.03,
identity collision 0.03. Jev screening only; not claimed as a merge gate.
Alibaba Open Code Review   Tool installation verified on this host: open-code-review v1.12.9
(windows/amd64, build 2026-09-22) at C:/Users/Shehr/.opencodereview/bin/ocr.exe, matching the
official release manifest. Full LLM review lane blocked at the provider-authority boundary: the
only configured provider (anthropic) has no API key, no zero-cost provider credential exists,
and paid compute is not authorized, so no review content was sent anywhere. The official no-LLM
lanes were executed instead (review preview over the exact base/head diff: 3 source files
reviewable, 2 test files excluded as default_path; delegate rule lane plus per-file rules check
for the Python rule group), and those rules were applied to the final diff by host-agent review.
One valid finding resulted (unenforced MAXIMUM_RESOURCE_BYTES, fixed forward-only in 8c837f6
with an adversarial regression test; lanes re-executed on the new head). No OCR source,
workflow, dependency, or configuration was added to MESC. No OCR review claimed beyond this
record.
host-agent review          Performed on the complete final diff, covering authority boundaries,
deterministic uuid5 identities, separated validation stages, workspace/patient bindings,
reference integrity, provenance and audit correctness, deletion refusal with dependents,
stale-read fail-closed behavior, export path algebra, security-label retention, inert content,
workspace isolation, the absence of donor-schema vendoring, and the absence of network, remote
retrieval, model, PHI, production, and EHR/external-write scope. The mypy-untyped-def density
under a newer local mypy matches origin/main siblings and apps/workspace is outside the
canonical strict-mypy file set (CI py3.11/py3.12 authoritative and green). No defects carried
to commit.
reviewing GitHub bots      qodo billing-blocked (no review); CodeRabbit pass (review skipped for this repository).
```

### 2.2 Repairs inside PR 505

PR 505 holds two commits, forward-only with one repair commit and no history rewrite:

```text
00f1d2a  feat: implement CW-013 bounded FHIR R4 import/export
8c837f6  fix: enforce CW-013 FHIR payload size bound at parse stage
```

Host review found `MAXIMUM_RESOURCE_BYTES` declared but unenforced, unlike sibling bounds
(asr/encounter audio, binding revision). `validate_payload` now refuses oversized payloads at
the parse stage with later stages unevaluated; `admit_resource` inherits the refusal via
validation. An adversarial regression test (`test_oversized_payload_refused_at_parse_stage`)
was added. Ruff check, ruff format, `git diff --check`, and the CW-013 suites (17/17) were
verified locally before commit. No rebase, no force-push (fast-forward `00f1d2a..8c837f6`),
no history rewrite, no protection bypass, no frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
FHIR_NAMESPACE = f0131a40-0004-4000-8000-000000013 (uuid5 namespace)
FHIR_REVISION = fhir-resource-00000001
PRODUCER_VERSION = cw013-v1
DERIVATION_METHOD = cw013-deterministic-fhir
DERIVATION_METHOD_VERSION = 1
SCHEMA_VERSION = cw013-fhir-r4/1
FHIR_SCHEMA_VERSION = 1
FHIR_VERSION = 4.0.1
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
```

Resource admission is mechanical validation of caller-supplied synthetic JSON against the
bounded subset (8 resource types, per-type required/allowlist keys, reference and patient
bindings against already-admitted store objects); fixture and operator identities are
deterministic test values only and are not a real-model decision. No real model is used to
infer, classify, score, or generate workspace content.

### 2.4 Negative and superseded evidence

```text
superseded GitHub head    00f1d2ab5504fc8c988aeae17058d3b36eec0423 with its own exact-head
evidence: CI 36305610246 SUCCESS, CodeQL 36305610239 SUCCESS; superseded by the forward-only
fix 8c837f6, never claimed as the merged head, never deleted
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; the Workspace package is outside the strict mypy file set while Issue 464 item 1 is open (CI py3.11/py3.12 authoritative); symlink/filemode MRL tests fail locally on Windows for privilege reasons and pass on Linux CI
MRL binding note          no MRL-0809-frozen source was touched by this increment, so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

### 2.5 Authority-history annotation (forward-only, no rewrite)

An authority-history discrepancy was flagged for honest recording: a prior approval record is
said to reference the superseded head `00f1d2a`, while the merged head is `8c837f6`. This
record resolves it without rewriting anything:

```text
claimed pre-merge approval of 8c837f6   NONE -- no exact-head approval naming 8c837f6 is claimed
MERGE_READY packet                      issued for the FINAL head 8c837f6 with exact-head CI/CodeQL,
Jev final-diff TRUE, OCR final-diff TRUE, host review PASS
merge act                               executed directly by the Founder (TheHalfMoon, human,
non-bot) on 2026-09-27T10:21:52Z as an ordinary merge commit with the two expected parents
merge-approval rule                     approval is exact-head specific; the superseded-head record
does not transfer, and no transfer is claimed here
canonical basis                         under R1-R7 and roles_and_authority the Founder is the final
decision-maker; no canonical rule requires post-hoc ratification of a Founder-executed merge
of a fully qualified head, so the remediation is this explicit annotation, not a new authority act
```

The superseded head, its runs, the fix commit, the re-qualification runs, and the merge commit
are all preserved above. No timestamp altered, no evidence deleted, no approval fabricated,
no CLOSED_CANONICAL claimed before this closeout completes its own merge + fresh-main path
(see section 8).

## 3. Protected merge

PR 505 merged through the protected path on 2026-09-27 (mergedAt 2026-09-27T10:21:52Z,
ordinary merge commit with expected parents, merged by the Founder). No squash, no rebase,
no force-push, no history rewrite, no gate weakening, no protection bypass.

```text
BASE  = ad16af4feaa5692a90482393e662b09b33950d70
HEAD  = 8c837f6e83f6a53ab47028b6c6cf0997e7f528e5
MERGE = 235df781f9372d6479cd00bfc7ab60ce7449743b
TREE  = d179aa6ac3336893ffcc22e5cde6e98429e5e47e
PARENTS = ad16af4feaa5692a90482393e662b09b33950d70, 8c837f6e83f6a53ab47028b6c6cf0997e7f528e5
```

The merge tree equals the qualified head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification

Workflows triggered by merge commit `235df781f9372d6479cd00bfc7ab60ce7449743b`:

- CI run `36312295431` (CI): SUCCESS
- CodeQL run `36312295458` (CodeQL): SUCCESS
- Optional Extras / Backends run `36312295460`: SUCCESS
- Hugging Face Publication Qualification run `36312295447`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

## 5. What CW-013 delivered

```text
bounded subset               exactly 8 FHIR R4 types (Patient, Encounter, Observation, Condition,
AllergyIntolerance, MedicationRequest, Procedure, DiagnosticReport) with per-type required-key
and allowlist-key tables; unknown types/members refused, never truncated
separated states             parse, structure, profile, reference, and provenance validated in order;
each refusal names the stage that failed; reference/provenance unevaluated without a store
deterministic identity       uuid5 over (workspace_id, resource type, fhir id, version); version
change yields a new identity; re-admission collides loudly instead of overwriting
workspace/patient binding    every entry point checks workspace identity; every non-Patient resource
binds an admitted Patient in the same workspace; bindings re-checked on every read
security labels              meta.security entries retained as validated tuples and surfaced on every
read; count bounded at 8
provenance mapping           every admit writes a provenance record (producer, source refs including
FHIR_RESOURCE plus EVIDENCE_SOURCE where applicable, digest); every read re-verifies the digest;
audit trail records writes, deletions, exports
currency checks              missing reference/source at admit raises FhirRevisionError; at read raises
FhirStaleError; source revision/digest drift makes dependents stale; deletion refused while
dependents exist
export quarantine            computed Domain X manifest only; target proven strictly below the
quarantine root and outside every Research Core root by string algebra; '..' refused; no file
written; module holds no filesystem or network capability
inert content                payload text stored as frozen tuples, never evaluated or executed;
malicious instruction strings remain data and grant no capability
size bounds                  payloads over 32768 bytes refused at parse; per-string/per-list/depth
bounds enforced; control characters refused
no donor schema              MedScale-owned minimal allowlists; no vendored FHIR schema; no
conformance claim beyond mechanical validation of synthetic fixtures
tests                      CW-013 suites in tests/test_clinical_workspace_fhir_v1.py (8 acceptance tests) and tests/test_clinical_workspace_fhir_adversarial_v1.py (9 adversarial tests) plus implementation in apps/workspace/src/medscale_workspace/fhir_r4.py with identity and error extensions
```

## 6. Recorded limitations

```text
bounds               payloads at most 32768 bytes, strings at most 1024 chars, lists at most 128
members, depth at most 8, identifiers at most 128 chars, codings at most 128 chars, security
labels at most 8, references at most 16, paths at most 512 chars; larger or unadmitted inputs
refused, not truncated
lexical paths        export containment is pure string algebra (no symlink/junction resolution:
the module holds no filesystem capability by design); link-based escape remains owned by the
first later unit with a filesystem capability and by CW-019
frozen derived state a resource revision is immutable; a new version yields a new identity;
currency is established by re-reading and stale reads fail closed
no inference         no terminology validation, no semantic support judgment, no clinical
correctness claim; a structurally valid resource is not automatically clinically correct
no connectors        EHR network access, SMART-on-FHIR, and production endpoints are absent by
design; FHIR compatibility is not production/EHR authority
no quality claim     no support-quality, clinical quality, or production readiness claim granted
by this unit
no real model        fixture and operator identities are deterministic test values, not a
real-model decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata
visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append
cost, ASR link-based export escape, draft link-based export escape, review link-based export
escape, lexical-overlap ranking, snapshot bounds, graph view bounds, and path depth bounds
remain as previously declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_013 = CLOSED_CANONICAL (on closeout merge + fresh-main; see section 8)
CW-001 through CW-013 = CLOSED_CANONICAL
CW-014, CW-015, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 504 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-013 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_013 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW_013_MODEL_AUTHORITY = NONE
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED
REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED
NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED
EHR_WRITE_AUTHORIZATION = NOT_GRANTED
EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED
TRAINING_AUTHORIZATION = NOT_GRANTED
PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED
CLINICAL_QUALITY = NOT_CLAIMED
SUPPORT_QUALITY = NOT_CLAIMED
PRODUCTION_READINESS = NOT_GRANTED
```

No real model has been selected or admitted. No support or clinical quality is claimed. No production readiness is granted. Deterministic FHIR mechanics are a correctness property, not a quality claim.
