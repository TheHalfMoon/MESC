# MESC Backbone Tournament — Execution Implementation 17

Status: **DRAFT / FIXTURE-ONLY ARTIFACT-MANIFEST COVERAGE VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded slice addresses only one remaining fixture-level prerequisite from the
frozen reproducibility contract: a fail-closed declaration that a future execution
artifact manifest covers every required identity and hash-binding category.

Canonical base:

```text
BASE_MAIN_SHA = 2a85420abcfdb884169c3b4b0299f6f5a464fb5f
BASE_MAIN_TREE = 49a9f49f5a55014b5d99e15c52b327473696a422
PR_159 = CLOSED_CANONICAL
IMPLEMENTATION_16_FIXTURE_OUTPUT_CONTRACT_PIPELINE_VERIFIER = CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-17/README.md
src/medscale/mesc/_bt_artifact_manifest_coverage_fixture_v1.py
tests/test_mesc_bt_artifact_manifest_coverage_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus, prompt,
scoring-key, runtime, remote-code, execution-result, report, ranking, activation,
or training path is changed.

## Frozen source requirement

`readiness-repair-2-result/reproducibility-schema.md` requires a future separately
authorized run to bind:

- exact MESC commit and tree;
- exact candidate/model/processor/runtime revisions;
- hardware and provider identity;
- the frozen corpus/prompt/schema/parser/scoring/report/protocol digest identities;
- access evidence;
- start and end timestamps;
- every raw and normalized per-item artifact hash;
- no floating executable identity.

The same frozen contract binds the canonical four candidate keys and the canonical
240-item corpus identity. Implementation 17 validates only an injected fixture
declaration of those coverage requirements.

## Implemented fixture contract

`ArtifactManifestCoverageEvidence` contains caller-supplied fixture declarations for:

```text
binding_fields
static_digest_bindings
candidate_keys
item_ids
manifest_complete
no_floating_executable_identity
candidate_revisions_bound
model_processor_runtime_revisions_bound
hardware_provider_identity_bound
access_evidence_bound
timestamps_bound
raw_per_item_hashes_bound
normalized_per_item_hashes_bound
unbound_required_fields
unattributed_artifact_hashes
```

The verifier requires exact equality to:

1. the canonical future-run binding categories;
2. all 14 frozen SHA-256 name/value bindings from the reproducibility contract;
3. the exact Section C candidate order:

```text
gpt_oss_20b
apertus_1_5_8b
phi_4_multimodal_instruct
medgemma_1_5_4b_it
```

4. the exact canonical 240 item IDs in A001..F040 order;
5. exact built-in boolean `True` for every positive coverage predicate;
6. exact built-in integer zero for unbound required fields and unattributed artifact hashes.

Tuple substitution, string subclasses, missing/extra/reordered coverage fields,
changed digest identities, candidate drift, item-ID drift, false controls, bool/int
substitution, and nonzero/negative counters fail closed.

## Snapshot / mutation boundary

The verifier constructs a local evidence snapshot before validation. Regression
tests mutate caller-owned state after the snapshot is constructed and prove that
post-snapshot mutation cannot change the validation result.

This is only an in-process fixture-verifier property. It does not establish an
atomic production manifest capture protocol and does not qualify any future
manifest producer.

## Deliberate non-claims

This slice does **not**:

- create a production execution artifact manifest;
- read, enumerate, hash, or persist real execution artifacts;
- prove that any raw or normalized per-item artifact exists;
- read the real frozen corpus, scoring keys, task prompt bundle, or system prompt;
- read or hash real runtime/model/processor files;
- establish actual candidate/model/processor/runtime revisions for a live run;
- establish provider, hardware, access, or timestamp evidence for a live run;
- qualify a future artifact-manifest producer;
- implement production parsing, schema validation, scoring, or report validation;
- serialize a prompt to any model;
- access model weights, gated resources, Phi remote code, providers, or GPUs;
- run inference or generation;
- rank candidates or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

Execution Implementation 3's fixture artifact manifest remains a bounded fixture
bundle, not the complete future tournament manifest. Implementation 17 does not
upgrade it into production evidence; it adds an independent coverage requirement
primitive for a future separately authorized producer.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent external exact-head review with no blocker;
6. zero unresolved blocking review threads.

Any head mutation burns prior head-specific evidence. Do not mark Ready or merge
until every exact-head gate is re-proven.

## Hard boundary

```text
REAL_EXECUTION_ARTIFACT_MANIFEST = NOT_PRODUCED
REAL_EXECUTION_ARTIFACT_ENUMERATION = NOT_PERFORMED
REAL_EXECUTION_ARTIFACT_HASHING = NOT_PERFORMED
ARTIFACT_MANIFEST_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
REAL_OUTPUT_PARSING = NOT_PERFORMED
REAL_SCHEMA_VALIDATION = NOT_PERFORMED
REAL_SCORING = NOT_PERFORMED
REAL_REPORT_VALIDATION = NOT_PERFORMED
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PHI_REMOTE_CODE_IMPORT_OR_EXECUTION = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```
