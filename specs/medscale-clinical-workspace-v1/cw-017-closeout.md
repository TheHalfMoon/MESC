# CW-017 Canonical Closeout Evidence

- **Task:** CW-017 -- Dataset Workspace and export quarantine
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main; see discrepancy record below)
- **Parent issue:** [#516](https://github.com/TheHalfMoon/MESC/issues/516) -- CW-017 activation
- **Original implementation PR:** [#517](https://github.com/TheHalfMoon/MESC/pull/517) -- `codex/feat/cw-017-dataset-export`
- **Original qualified head:** `ecf25dd8a0d0cb13404884ba0f67bcd25afe9313`
- **Original implementation merge:** `a58d537de606dadcadbb165f1dc5981bd244f9a1` (tree `f4566f14dbc060a556793cccdc706dcc4110ff3d`)
- **Repair PR:** [#518](https://github.com/TheHalfMoon/MESC/pull/518) -- `codex/fix/cw-017-read-currency`
- **Repair qualified head:** `13d9dc0434e56f563de1027b346780fdf9496b5f` (tree `c75ea090d9d4dc21cf9b8be122dc0e0cacc7a1e8`)
- **Repair merge:** `6a18b317a384749431146a8f3f7c1747e6e0f3bb` (tree `c75ea090d9d4dc21cf9b8be122dc0e0cacc7a1e8`)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, telemetry, or autonomous-action authority. Dataset collections are read-only pinned workspace records over dataset-manifest research views; export manifests are reference-only Domain X staging records. Neither is a research dataset, benchmark input, MRL evidence, training data, or an external transmission, and nothing here admits Workspace-derived data into Research Core.

CW-017 closes through two canonical merges: PR #517 introduced the implementation, and PR #518 is the forward-only repair of defects found by post-merge review of #517 before canonical closure. The #517 implementation was **not** defect-free; the defect history is recorded in section 3 without sanitization.

## 1. Governance state entering implementation

```text
CW-001 through CW-016 CLOSED_CANONICAL
CW-016 closeout merge                73fdf5a92cce411223bfdff538edbee0a31fe9e5
CW-017                               activated under Issue 516 on 2026-09-28 as the single active unit under R4
gating contracts                     no new ADR required; synthetic-only deterministic path under Issue 516 activation contract
model contract                       NONE -- no real generation model selected, admitted, or ratified
authorization                        synthetic fixtures only; local store reads only; no network, no remote retrieval, no model download, no paid compute, no PHI, no production use
research admission                   Workspace-derived data NOT AUTHORIZED
new dependencies                     none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                separately governed and untouched
```

## 2. Original implementation: PR 517

### 2.1 Exact-head evidence

Qualified head `ecf25dd8a0d0cb13404884ba0f67bcd25afe9313` on base `73fdf5a92cce411223bfdff538edbee0a31fe9e5`:

- CI run `36445013485` (CI, pull_request event): SUCCESS
- CodeQL run `36445013776` (CodeQL, pull_request event): SUCCESS
- GitHub PR reviews recorded: none (no APPROVED review exists via the API); review threads: none
- reviewing bot signals: none claimed as review evidence; none substitutes for Alibaba Open Code Review

PR 517 holds one commit (`ecf25dd  feat: implement CW-017 dataset workspace and export quarantine`); no head was superseded and no other runs exist on the branch.

Changed files (6 files, 2010 insertions, no deletions):

```text
apps/workspace/src/medscale_workspace/dataset.py                          +1215 new dataset collection and export staging module
apps/workspace/src/medscale_workspace/errors.py                           +36 DatasetCollection* and ExportStaging* error classes
apps/workspace/src/medscale_workspace/identity.py                         +8 WORKSPACE_DATASET_COLLECTION, WORKSPACE_EXPORT_MANIFEST
apps/workspace/src/medscale_workspace/provenance.py                       +4 EXPORT_SOURCE source kind
tests/test_clinical_workspace_dataset_adversarial_v1.py                   +446 13 adversarial tests
tests/test_clinical_workspace_dataset_v1.py                               +301 7 acceptance tests
```

### 2.2 Review lanes claimed for PR 517 (as recorded in the PR body only)

The PR 517 body states: acceptance (7) plus adversarial (13) suites 20/20 locally; boundary guard, ruff check and format, mypy on new tests passing; a Jev 10-probe screen with host review (10 NO, no valid defects); Alibaba OCR official no-LLM lanes executed with the full LLM lane blocked by the provider credential boundary.

The raw Jev and OCR outputs behind those statements are **not available** on the host that produced this closeout. They are recorded here as PR-body claims only and are not re-asserted as independently verified evidence. The post-merge review in section 3 is the independently re-executed record.

### 2.3 Merge

```text
BASE    = 73fdf5a92cce411223bfdff538edbee0a31fe9e5
HEAD    = ecf25dd8a0d0cb13404884ba0f67bcd25afe9313
MERGE   = a58d537de606dadcadbb165f1dc5981bd244f9a1
TREE    = f4566f14dbc060a556793cccdc706dcc4110ff3d
PARENTS = 73fdf5a92cce411223bfdff538edbee0a31fe9e5, ecf25dd8a0d0cb13404884ba0f67bcd25afe9313
MERGED  = 2026-09-28T16:22:25Z by TheHalfMoon (ordinary merge commit; GitHub signature verified)
```

Fresh-main on `a58d537de606dadcadbb165f1dc5981bd244f9a1`: CI `36450548777` SUCCESS, CodeQL `36450548850` SUCCESS, Optional Extras / Backends `36450548947` SUCCESS, Hugging Face Publication Qualification `36450549043` SUCCESS.

### 2.4 Governance discrepancy (forward-only record, not concealed)

No explicit exact-head merge approval for `ecf25dd8a0d0cb13404884ba0f67bcd25afe9313` is provable from the available record before PR #517 merged. The merge was executed under the Founder/operator credential (`TheHalfMoon`, mergedAt 2026-09-28T16:22:25Z) as an ordinary merge commit with the expected parents. No approval is fabricated here and none is claimed retroactively. No history was rewritten and no evidence was altered. Approving the closeout PR with knowledge of this section constitutes post-merge ratification of the #517 merge; a separate standalone ratification remains available if the Founder requires it.

Canonical basis: under R1-R7 and `docs/governance/roles_and_authority.md` the Founder is the final decision-maker; this is the same treatment used in [cw-013-closeout.md](cw-013-closeout.md) section 2.5, [cw-015-closeout.md](cw-015-closeout.md) section 2.0 and [cw-016-closeout.md](cw-016-closeout.md) section 2.0.

## 3. Post-merge defect discovery and forward-only repair: PR 518

### 3.1 Defects found in the merged #517 implementation

Post-merge host review, Jev, and the Alibaba OCR delegate rule lane over the exact #517 diff (`73fdf5a9..ecf25dd8`) found four defects:

```text
1 stale export acceptance        read_export_manifest returned a staged manifest after one of its
                                 staged sources was deleted or its payload drifted (VALID)
2 stale collection acceptance    read_dataset_collection returned a collection after a pinned
                                 member view was deleted; list_collection_views surfaced a raw
                                 ResearchViewInputError instead of a dataset-collection error (VALID)
3 wrong exception class          DatasetCollectionRecord.from_document raised ExportStagingInputError
                                 (not a DatasetCollectionError) for a non-string stored member (VALID)
4 unused parameter               _refuse_item(raw) never read raw (VALID, minor; OCR dead-code rule)
```

Reproduction before the fix (local, synthetic fixtures, merged module `ecf25dd8`):

```text
FINDING-1 CONFIRMED: manifest with deleted source read OK
FINDING-2 CONFIRMED: collection with deleted member read OK
list_collection_views raises medscale_workspace.errors ResearchViewInputError
FINDING-3 from_document non-string name raises: ExportStagingInputError is DatasetCollectionError: False
```

### 3.2 Repair

PR 518 holds one commit (`13d9dc0  fix: re-verify CW-017 collection and export currency on read`), 2 files, +154/-25:

- public reads re-verify currency: collections re-read every pinned view (still a dataset-manifest view); export manifests re-read every staged source and recompute its digest; a deleted or drifted reference fails closed with the existing `DatasetCollectionStaleError` / `ExportStagingStaleError`; `WorkspaceIsolationError` still propagates unmasked;
- deletion uses an integrity-only read, so stale records remain deletable;
- `_string_member` takes the error class explicitly; `_refuse_item` lost its unused parameter;
- no new dependency, error class, object type, network, model, Research Core, or write path.

Regression coverage: new adversarial tests `test_stale_export_source_reads_fail_closed` and `test_stale_collection_member_reads_fail_closed`, plus a non-string-member assertion in `test_forged_collection_documents_fail_closed`. Against the unrepaired module these fail (`3 failed, 12 passed`); against the repair they pass.

Local verification on the repair head (Windows host, py3.12 frozen uv environment; CI py3.11/py3.12 authoritative): CW-017 suites 22/22 (7 acceptance, 15 adversarial); all 35 Clinical Workspace test files 596 passed (baseline 594 + 2 new); ruff check PASS; ruff format --check PASS; mypy PASS (529 source files); boundary guard PASS; docs link hygiene PASS; `git diff --check` clean.

### 3.3 Jev record (preserved exactly, not rewritten)

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)

scope: merged #517 module (dataset.py at ecf25dd8)
probes: 22 -- 21 NO, 1 YES
YES: stale_state_acceptance 0.88
NO: provenance_bypass 0.04, audit_bypass 0.18, source_revision_mismatch 0.12,
deterministic_identity_failure 0.04, nondeterministic_serialization 0.06,
cross_workspace_access 0.13, research_core_mutation 0.08, hidden_research_admission 0.02,
deidentification_as_admission 0.02, export_manifest_content_leakage 0.03,
quarantine_root_escape 0.03, automatic_export 0.02, consent_rights_bypass 0.03,
hidden_network 0.02, telemetry_creep 0.04, model_creep 0.01, malicious_content_authority 0.06,
deletion_inconsistency 0.24, wrong_exception_class 0.43, residual_identifier_failure 0.06,
capability_escalation_untrusted 0.04
host adjudication: stale_state_acceptance VALID DEFECT (findings 1 and 2), fixed in PR 518.
wrong_exception_class answered NO at 0.43 but finding 3 is host-confirmed by reproduction;
a Jev NO does not override host evidence.

scope: repaired module (dataset.py at 13d9dc04)
probes: 23 -- 23 NO (stale_state_acceptance 0.05, wrong_exception_class 0.07,
stale_record_undeletable 0.08, deletion_inconsistency 0.25, all others <= 0.16)

scope: repair diff (a58d537d..13d9dc04)
probes: 4 -- 3 NO, 1 YES
YES: behavior_beyond_scope 0.51
NO: tests_weakened 0.09, new_capability_added 0.08, stale_error_swallowed 0.04
host adjudication: behavior_beyond_scope NOT A DEFECT -- exact diff review shows only read-time
currency checks and exception-class selection; the list_collection_views exception change is
the direct consequence of the currency check and is test-covered.

JEV_FINAL_DIFF_REVIEWED = TRUE (binds 13d9dc0434e56f563de1027b346780fdf9496b5f)
```

Raw Jev JSON outputs for all three scopes were retained on the qualifying host (not committed) and the figures above were re-tallied from them for this closeout. Jev screening only; YES signals are preserved as YES with exact probabilities. No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent.

### 3.4 Alibaba Open Code Review record

```text
OCR_VERSION = open-code-review v1.12.9 (bccbc15f) windows/amd64, built 2026-09-22T11:06:41Z
OCR_BINARY = C:/Users/Shehr/.opencodereview/bin/ocr.exe
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
OCR_MODE = ocr delegate preview + ocr delegate rule; resolved Python rule group applied by host review

#517 range 73fdf5a9..ecf25dd8: 4 reviewable / 6 total
  reviewed: dataset.py, errors.py, identity.py, provenance.py
  excluded: tests/test_clinical_workspace_dataset_adversarial_v1.py (default_path),
            tests/test_clinical_workspace_dataset_v1.py (default_path)
  findings: finding 3 (error handling) and finding 4 (dead code), both fixed in PR 518

#518 range a58d537d..13d9dc04: 1 reviewable / 2 total
  reviewed: dataset.py
  excluded: tests/test_clinical_workspace_dataset_adversarial_v1.py (default_path), host-reviewed
            separately (additions only; no existing assertion removed or loosened)
  findings: none
OCR_FINAL_DIFF_REVIEWED = TRUE
```

The only configured provider has no API key and paid compute is not authorized, so no review content was sent anywhere and no LLM review is claimed. No OCR source, workflow, dependency, or configuration was added to MESC.

### 3.5 Host review

Performed on the complete #517 diff and the final #518 diff: activation scope, deterministic uuid5 identities over sorted canonical inputs, canonical JSON serialization, closed consent/rights/de-identification vocabularies, reference-only manifests (no content bytes), quarantine containment through `admit_export_path`, explicit boolean export request, provenance and audit on every create and delete, workspace isolation, read-time currency after the repair, narrow exception handling with preserved causes, inert content, and the absence of network, remote retrieval, model, PHI, production, Research Core admission, MRL mutation, and EHR/external-write scope. PASS; no known defect carried to merge.

### 3.6 Exact-head qualification and approved merge

Repair head `13d9dc0434e56f563de1027b346780fdf9496b5f` on base `a58d537de606dadcadbb165f1dc5981bd244f9a1`:

- CI run `36582897450` (pull_request): SUCCESS
- CodeQL run `36582897623` (pull_request): SUCCESS
- mergeable MERGEABLE, merge state CLEAN, reviews none, unresolved threads 0

Explicit Founder exact-head merge approval for `13d9dc0434e56f563de1027b346780fdf9496b5f` (tree `c75ea090d9d4dc21cf9b8be122dc0e0cacc7a1e8`, base `a58d537de606dadcadbb165f1dc5981bd244f9a1`) was given by the Founder at 2026-09-29T15:19:45Z, before the merge, conditioned on the head, tree, CI `36582897450` SUCCESS and CodeQL `36582897623` SUCCESS remaining unchanged and restricted to an ordinary merge commit. All conditions held at merge time. Merge executed at 2026-09-29T15:20:01Z as an ordinary merge commit with expected-head protection (`gh pr merge 518 --merge --match-head-commit 13d9dc0434e56f563de1027b346780fdf9496b5f`):

```text
BASE    = a58d537de606dadcadbb165f1dc5981bd244f9a1
HEAD    = 13d9dc0434e56f563de1027b346780fdf9496b5f
MERGE   = 6a18b317a384749431146a8f3f7c1747e6e0f3bb
TREE    = c75ea090d9d4dc21cf9b8be122dc0e0cacc7a1e8
PARENTS = a58d537de606dadcadbb165f1dc5981bd244f9a1, 13d9dc0434e56f563de1027b346780fdf9496b5f
MERGED  = 2026-09-29T15:20:03Z
```

The merge tree equals the approved head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification (both generations)

```text
a58d537de606dadcadbb165f1dc5981bd244f9a1 (PR 517 merge)
  CI 36450548777 SUCCESS, CodeQL 36450548850 SUCCESS,
  Optional Extras / Backends 36450548947 SUCCESS, HF Publication 36450549043 SUCCESS
6a18b317a384749431146a8f3f7c1747e6e0f3bb (PR 518 repair merge)
  CI 36589391230 SUCCESS, CodeQL 36589391059 SUCCESS,
  Optional Extras / Backends 36589391061 SUCCESS, HF Publication 36589391267 SUCCESS
```

## 5. What CW-017 delivered

```text
research dataset mode      immutable dataset collections pinning 1-64 dataset-manifest research
views (CW-016) through the existing versioned read interface; every member re-verified at store
time and at read time; collections carry identities only
Domain X export staging    reference-only export manifests pinning source identity, kind, revision,
and recomputed payload digest for 1-64 already-stored Workspace objects; EXPORT_QUARANTINE data
class; quarantine target proven below the declared Domain X root and outside every declared
Research Core root; no file written; explicit boolean export request required
de-identification          recorded as an export transformation (method reference-only, version 1,
input/output digests), never as research admission
residual identifiers       content bytes have no parameter and never enter the manifest; planted
identifier strings in sources are proven absent from manifests
source/consent/rights      closed vocabularies (synthetic-only consent, synthetic-fixture rights)
no Research Core identity  no entry point mints a Research Core dataset identity or marks anything
research admitted; the no-backflow guard refuses Workspace-to-Research flows
currency (after PR 518)    deleted or drifted pinned views and staged sources fail closed as stale
on read; stale records stay deletable
lifecycle                  deletion removes record plus provenance in audited operations; the audit
trail survives; replays collide instead of overwriting
tests                      tests/test_clinical_workspace_dataset_v1.py (7 acceptance) and
tests/test_clinical_workspace_dataset_adversarial_v1.py (15 adversarial)
```

## 6. Recorded limitations

```text
bounds               collections 1-64 members, exports 1-64 items, names 64 chars, revisions 128
chars, paths 512 chars, records 32768 canonical bytes; larger inputs refused, not truncated
vocabularies         only synthetic-only consent, synthetic-fixture rights, and reference-only
de-identification are admitted; real consent/rights models need separate authority
no export write      staging records a manifest only; writing or transmitting an export is a
separate explicit authority
lexical containment  quarantine containment is path algebra (as CW-004); no filesystem resolution
no real model        no model-backed de-identification or classification
prior limitations    as declared in earlier closeouts unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_017 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW-001 through CW-017 = CLOSED_CANONICAL
CW-018 = ELIGIBLE_NOT_ACTIVATED (depends on CW-002, CW-003, CW-011, CW-017, all CLOSED_CANONICAL)
CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 516 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
```

## 8. Explicit non-grants preserved

```text
CW_017_MODEL_AUTHORITY = NONE
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED
REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED
NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED
EHR_WRITE_AUTHORIZATION = NOT_GRANTED
EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED
TRAINING_AUTHORIZATION = NOT_GRANTED
PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED
RESEARCH_ADMISSION_OF_WORKSPACE_DATA = NOT_GRANTED
CLINICAL_QUALITY = NOT_CLAIMED
PRODUCTION_READINESS = NOT_GRANTED
```

## 9. Closeout-diff qualification (docs-only increment)

This section qualifies the closeout increment itself (this file plus the `tasks.md` and `README.md` reconciliation). No implementation code or test is altered by this increment.

```text
JEV_VERSION = jev CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider)
JEV_SCOPE = final closeout diff (cw-017-closeout.md plus tasks.md and README.md reconciliation),
screened against a ground-truth block re-verified live from the GitHub API and git
JEV_PROBES = 16 (fabricated approval, fabricated merge evidence, wrong head, false workflow claims,
rewritten Jev history, rewritten OCR history, defect concealment, premature CLOSED_CANONICAL,
wrong dependency promotion, hidden authority grant, CW-021 authorization, governed-issue touch,
history rewrite, code change, Research Core backflow, unverified raw-evidence claim)
JEV_RESULTS = 16 NO, 0 YES -- fabricated-approval 0.49 NO, fabricated-merge-evidence 0.15 NO,
wrong-head 0.08 NO, false-workflow-claims 0.23 NO, rewritten-Jev-history 0.31 NO,
rewritten-OCR-history 0.05 NO, defect-concealment 0.04 NO, premature-CLOSED_CANONICAL 0.11 NO,
wrong-dependency-promotion 0.24 NO, hidden-authority-grant 0.02 NO, CW-021-authorization 0.02 NO,
governed-issue-touch 0.03 NO, history-rewrite 0.03 NO, code-change 0.04 NO,
Research-Core-backflow 0.02 NO, unverified-raw-evidence-claim 0.03 NO
JEV_ELEVATED_SIGNAL = fabricated-approval 0.49 (first screen 0.48). Diagnostic single-probe
reruns on altered inputs -- with the #517 post-merge-ratification sentence removed, and with the
#518 approval timestamp clause removed -- scored 0.52 YES and 0.51 YES, so neither passage drives
the signal; the compound probe sits near its threshold. Host adjudication: NOT A DEFECT. The #518
approval (2026-09-29T15:19:45Z) precedes the --match-head-commit merge (15:20:01Z) in the session
transcript; the #517 approval is recorded as not provable and no retroactive approval is claimed.
JEV_FINAL_RESCREEN = 16 NO, 0 YES on the diff including the lines above -- fabricated-approval
0.40, wrong-dependency-promotion 0.27, rewritten-Jev-history 0.29, false-workflow-claims 0.21,
fabricated-merge-evidence 0.17, all others <= 0.12
JEV_FINDINGS = no valid findings
JEV_FINAL_DIFF_REVIEWED = TRUE
```

Jev screening only; not claimed as a merge gate. No PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material was sent. The closeout diff was re-screened after this section was added; the record above reflects the final diff apart from these result lines themselves.

```text
OCR_VERSION = open-code-review v1.12.9 (bccbc15f) windows/amd64, built 2026-09-22T11:06:41Z
ALIBABA_OPEN_CODE_REVIEW = LOCAL_OFFICIAL_LANES_EXECUTED; FULL_LLM_LANE_BLOCKED_BY_PROVIDER_CREDENTIAL_BOUNDARY
OCR_MODE = official local/no-LLM lanes (delegate preview) over the closeout diff
MARKDOWN = UNSUPPORTED_EXT
OCR_FINAL_DIFF_REVIEWED = TRUE
```

All three closeout files are Markdown and are excluded by the official tool as `unsupported_ext` (0 reviewable / 3 total); no OCR review of Markdown is claimed. Every closeout claim was instead independently host-reviewed against live GitHub truth: Issue #516 activation, PR #517 and PR #518 heads, merge SHAs, parents, trees and timestamps, exact-head CI/CodeQL for both PRs, fresh-main CI/CodeQL/Optional Extras/HF Publication for both merges, the three Jev records re-tallied from raw outputs with both YES signals preserved, the OCR records, the four-defect history, the #517 approval discrepancy, tasks.md dependency math, README frontier, and non-authority. Host review: PASS with no defects carried to commit.

Closeout increment checks: relative links in the three changed files 91 checked, 0 missing (the repository link checker covers root and `docs/` Markdown only: PASS, 128 files); boundary guard PASS; `git diff --check` clean; CW-017 suites 22/22 re-verified locally on `6a18b317` with explicit writable basetemp (CI py3.11/py3.12 authoritative).
