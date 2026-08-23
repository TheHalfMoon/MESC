# MESC Backbone Tournament — Execution Implementation 12

Status: **DRAFT / FIXTURE-ONLY EXECUTOR RUNTIME-IDENTITY VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the Section D runtime-object
identity and immutable-handoff predicates for the executor/harness allowlist.

Canonical base:

```text
BASE_MAIN_SHA = bf1201bff17b9171e986033b52c3a370e7fe1a11
BASE_MAIN_TREE = c1e84670f5e99dffe53b9205be7d627a16c36b0e
PR_154 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-12/README.md
src/medscale/mesc/_bt_executor_runtime_identity_fixture_v1.py
tests/test_mesc_bt_executor_runtime_identity_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus/prompt,
scoring-key, real executor checkout, filesystem-verifier implementation,
execution-result, or activation-artifact path is changed.

## Canonical requirement

Section D already has a canonical allowlist primitive through Execution
Implementation 1. That primitive validates exact canonical
`EXECUTOR_PATHS_AND_BLOB_SHAS` bytes and injected exact-commit Git object
metadata, but it explicitly performs no checkout, file opening, import, or
execution.

Section D separately requires the future activation verifier to acquire each
allowlisted runtime path descriptor-relatively from the exact read-only checkout
root bound by `repository_checkout_sha` and `repository_checkout_tree` using:

```text
openat2
RESOLVE_BENEATH
RESOLVE_NO_SYMLINKS
RESOLVE_NO_MAGICLINKS
RESOLVE_NO_XDEV
O_RDONLY
O_CLOEXEC
O_NOFOLLOW
```

The exact opened descriptor must be a regular file. Its Git blob object ID must
be recomputed from the exact opened bytes using Git's canonical
`blob <byte_length>\0<bytes>` framing and must equal the allowlist entry's
`git_blob_sha`. Execution/import must then use that same immutable opened object,
or an object whose inode/bytes identity is mechanically proven equivalent on an
immutable read-only mount immediately before execution/import.

Implementation 1 does not implement these runtime-object predicates, and no
other canonical Backbone Tournament implementation currently provides this
executor-specific primitive.

## Deliberately fixture-only

Implementation 12 does **not** call `openat2(2)`, open a checkout, read files,
compute a real Git blob object ID, inspect inodes, create mounts, import harness
code, or execute any process. Instead it validates caller-supplied fixture
evidence from a future separately reviewed producer.

The production verifier introduced by this slice accepts:

- a parser-validated canonical `ExecutorAllowlist`;
- an injected expected `execution_code_sha`;
- an injected expected `execution_code_tree`;
- one injected `RuntimeExecutorObjectObservation` per allowlisted path.

`execution_code_sha` and `execution_code_tree` must be exact built-in strings
matching lowercase 40-hex Git identities. They are expected identities only;
this slice does not resolve the commit to its tree.

## Allowlist revalidation

Before runtime evidence is accepted, the supplied allowlist is revalidated:

- exact `ExecutorAllowlist` outer type;
- exact tuple container;
- exact `ExecutorAllowlistEntry` entry types;
- exact built-in string scalar types;
- exact built-in integer byte length;
- canonical reserialization and parse round-trip;
- full object equality with the reparsed canonical allowlist, including digest
  and byte length.

This prevents forged dataclass/subclass or equality-compatible representations
from being accepted merely because they serialize like canonical values.

## Runtime observation contract

For every allowlisted path, exact `RuntimeExecutorObjectObservation` is required.
It records only injected fixture facts:

```text
path
open_api
descriptor_relative
resolve_flags
open_flags
repository_checkout_sha
repository_checkout_tree
checkout_root_read_only
fstat_regular_file
git_blob_recomputed_from_exact_opened_bytes
verification_device
verification_inode
verification_byte_length
verification_git_blob_sha
handoff_device
handoff_inode
handoff_byte_length
handoff_git_blob_sha
handoff_mount_read_only
handoff_mount_immutable
identity_checked_immediately_before_execution_or_import
execution_or_import_uses_same_opened_object_or_proven_equivalent
```

The verifier requires:

1. exact path equality with the current allowlist entry;
2. exact built-in string `open_api = openat2`;
3. exact `frozenset` resolve/open flag containers, exact-string members, and
   exact required flag sets;
4. exact checkout SHA/tree equality with the expected execution-code identities;
5. exact-true descriptor-relative, read-only-root, regular-file, recomputed-blob,
   immutable-handoff, immediate-identity-check, and same-object/equivalent-object
   predicates;
6. exact built-in integer device/inode/byte-length identities with nonnegative
   device/length and positive inode values;
7. unchanged device, inode, and byte length between verification and handoff;
8. exact lowercase 40-hex verification/handoff Git blob identities;
9. verification Git blob equality with the allowlist entry;
10. unchanged Git blob identity at handoff.

Unknown, malformed, substituted, subclass-spoofed, mismatched, or unproven
values fail closed.

## Deliberate non-claims

This slice does **not**:

- establish the future `EXECUTION_CODE_SHA` or `EXECUTION_CODE_TREE` values;
- mechanically verify that `EXECUTION_CODE_SHA` resolves to
  `EXECUTION_CODE_TREE`; that Section D Git commit/tree-resolution predicate
  remains independent;
- treat activation-identity binding of those values as proof of the Git
  commit/tree-resolution predicate;
- create or hash a new artifact format;
- prove a real repository checkout, mount, inode, or file identity;
- prove a real Git blob recomputation occurred;
- implement `openat2(2)` or any filesystem operation;
- establish the complete executed/imported executor-and-harness path-set equality
  predicate; that remains an independent Section D prerequisite;
- implement the Backbone Tournament model executor;
- access model weights or gated model resources;
- serialize prompts, run inference/generation, score, rank, select a winner,
  execute the tournament, or train;
- allocate a provider instance or GPU;
- grant execution authority.

## Relationship to adjacent slices

Execution Implementation 1 remains the canonical parser/Git-tree allowlist
primitive. Implementation 12 consumes its validated allowlist object but does
not replace or weaken it.

The existing activation-identity fixture binds independently supplied
`execution_code_sha`, `execution_code_tree`, `repository_checkout_sha`, and
`repository_checkout_tree` values into activation identity. That binding does
not itself prove the Section D requirement that the execution commit resolve to
the exact execution tree, and Implementation 12 does not add such a claim.

The Section D requirement that the independently reviewed executable/imported
executor-and-harness path set equal the allowlist exactly is deliberately not
collapsed into this runtime-object identity slice. A later separately reviewed
fixture primitive may address that predicate without executing harness code.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security review PASS;
5. fresh independent external exact-head review with no blocker;
6. zero unresolved blocking review threads.

Any head mutation burns prior head-specific evidence. Do not mark Ready or merge
until all exact-head gates are proven.

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
