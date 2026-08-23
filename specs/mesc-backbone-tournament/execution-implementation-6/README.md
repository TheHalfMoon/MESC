# MESC Backbone Tournament — Execution Implementation 6

Status: **DRAFT FIXTURE-ONLY PHI REMOTE-CODE MANIFEST VERIFIER — NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice adds only a pure, fixture-level verifier for the
`PHI_REMOTE_CODE_MANIFEST` contract required by
`FD-MESC-BT-EXEC-1` Section C.3.

Canonical base for this slice:

```text
BASE_MAIN_SHA = 35f98e112c3250f29fb5b252933fa40889c56fee
BASE_MAIN_TREE = b4c35a87beb7cac7a92363b08c4cb84a3cb8cb22
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
IMPLEMENTATION_5_CANONICAL_QUALIFICATION =
    REPAIRED_BY_POST_MERGE_ADOPTION_RECORD
ORIGINAL_PREMERGE_ORDERING =
    HISTORICAL_DEFECT_PRESERVED_AS_NOT_PROVEN
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-6/README.md
src/medscale/mesc/_bt_phi_remote_code_fixture_v1.py
tests/test_mesc_bt_phi_remote_code_fixture_v1.py
```

No dependency, workflow, credential, provider, model-weight, tokenizer,
processor, frozen corpus, frozen prompt, scoring contract, runtime acquisition,
sandbox, or execution-result path is changed.

## Implemented fixture contract

The pure verifier:

- requires duplicate-member-safe UTF-8 JSON with no BOM;
- requires a non-empty top-level JSON array;
- requires each entry to contain exactly `byte_length`, `git_blob_sha`, `path`,
  and `sha256`;
- requires `byte_length` to be an exact JSON integer `>= 0`;
- requires ASCII-only path/blob/digest values;
- enforces the canonical Section C.3 path grammar and rejects `.` / `..`
  components;
- requires lowercase 40-hex Git blob identities and lowercase 64-hex SHA-256
  values;
- rejects duplicate decoded paths;
- requires entries to be sorted by decoded path ASCII bytes;
- canonically reserializes with lexical object keys, compact separators, no
  insignificant whitespace, and no trailing newline;
- requires byte-for-byte equality with the supplied manifest before hashing;
- returns the exact manifest byte length and SHA-256;
- verifies injected pinned-revision object facts require a regular-file Git
  blob with mode exactly `100644` or `100755`;
- fail-closes malformed injected resolver metadata rather than leaking raw type
  errors;
- verifies the injected Git blob SHA, exact byte length, and SHA-256 equal the
  canonical manifest entry.

All Git/file facts are dependency-injected fixture values. The module itself
cannot fetch a repository, traverse a filesystem, open a file, import remote
code, execute a subprocess, access a network, or access a model.

## Deliberate non-claims

This slice does **not** establish `PHI_REMOTE_CODE_MANIFEST_SHA256` for a real
Phi repository checkout and does not inspect or acquire the real
`microsoft/Phi-4-multimodal-instruct` remote-code bytes.

It does not prove:

- completeness of the executable/imported remote-code file set;
- the complete import graph reachable from those files;
- `PHI_REMOTE_CODE_SECURITY_REVIEW = PASS`;
- `PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256`;
- descriptor-relative `openat2(2)` acquisition or runtime inode identity;
- equality between verified bytes and bytes actually imported by a model
  process;
- sandbox/network/credential controls;
- `PHI_SANDBOX_QUALIFICATION_SHA256`;
- live H100 telemetry qualification;
- gated-access authorization or access attestations;
- final activation receipt validity;
- production executor integration;
- any tournament execution property.

Those remain separately reviewed fail-closed prerequisites before activation.

The parser additionally rejects an empty manifest. Phi is authorized only under
`trust_remote_code=true`; treating an empty manifest as qualified would create
an avoidable completeness ambiguity. This stricter fail-closed rule does not
claim the manifest is complete: later complete-set and security-review
qualification must still independently establish the actual executable/import
graph.

## Hard boundary

```text
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

Keep any PR for this slice Draft until GitHub-native scope reconciliation,
fresh exact-head CI, fresh exact-head CodeQL, a fresh independent exact-head
technical/security review, and zero unresolved blocking review threads are all
proven. Any head mutation burns head-specific qualification evidence.
