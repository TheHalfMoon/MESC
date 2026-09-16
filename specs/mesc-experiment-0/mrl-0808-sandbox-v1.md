# MRL-0808 real execution sandbox qualification producer

## Purpose

This package implements the deterministic repository-owned portion of MRL-0808 under Issue
#424. It freezes the exact sandbox policy, challenge lifecycle, hosted control probe,
provider/runtime custody contract, independent attestation boundary, and deterministic
qualification logic required before `mesc.mrl.real_preflight.sandbox.v1` may be admitted.

The producer does **not** qualify a sandbox by itself. The committed runtime-attestation
trust root is intentionally empty. A real hosted observation must be produced from a clean
canonical main checkout, independently attested, admitted through a separate minimal trust
mutation, and only then requalified into an untrusted MRL-0808 real-preflight evidence
candidate.

No model/tokenizer loading, scientific inference, dataset evaluation, training, weight
mutation, promotion, release, deployment, or clinical authority is granted here.

## Canonical predecessor

The producer authorization is bound to:

```text
PREDECESSOR_MAIN_SHA = 520aec7630441f43c7b14f3603533f4533a71bbe
PREDECESSOR_MAIN_TREE = 2b0b64bbbe0a5c89dad61ca05b17a8488f95f8e1
MRL_0804_EVIDENCE_SHA256 = f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0
MRL_0804_RUNTIME_IDENTITY_SHA256 = 05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45
MRL_0806_EVIDENCE_SHA256 = 27ed7a990b6408b8972980d576da3692801dfdb3f7bd444beda1b0135f7d7de2
AUTHORITY_ISSUE = #424
```

The canonical MRL-0804 evidence came from the qualified Google Colab hosted-runtime class.
Hugging Face Jobs `zero-a10g` was previously rejected before job creation because free or
quota-backed entitlement could not be proven; paid fallback remains prohibited. The local
control laptop is not a qualifying MRL-0808 execution surface.

## Frozen policy identities

All authoritative JSON below uses the repository canonical JSON byte contract, including the
terminal LF inside the SHA-256 identity.

```text
MRL0808_AUTHORIZATION_SHA256 = 838c7ed0b8aafd9f85a89d96846486660d0f54ba0e50c0ebec1a415a6b328575
NETWORK_POLICY_SHA256 = 4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f
MUTATION_PATHS_SHA256 = 044c61563880e630e079fad1e762aa5c9d3af505099a801070ef57d750633691
OUTPUT_DESTINATIONS_SHA256 = 2b6c79b5662d3e91f107bf24d00155b8df0b4a1c96b0ad48284451afd0cbb8ea
STOP_CONDITIONS_SHA256 = 607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194
SANDBOX_POLICY_SHA256 = 169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316
```

Any byte drift fails closed.

## Isolation boundary

The hosted launcher requires Linux and the exact clean canonical `main` checkout. Synthetic
input staging, empty model-weight staging, and evidence custody must resolve outside the
producer repository. It requires
an independently obtained Colab runtime/session identity and records the actual GPU
observation, kernel, Python, Colab release family, bubblewrap version, and exact bubblewrap
binary SHA-256 into `runtime-context.json`.

Dependency setup and provider scheduling occur outside the isolated execution window. The
scientific/control probe boundary uses bubblewrap with:

```text
--unshare-all
--die-with-parent
--new-session
--clearenv
direct host-root bind = forbidden
/usr, /sys, /etc/ld.so.cache = explicit read-only runtime support
/dev = fresh device filesystem + explicit NVIDIA character devices, then remounted read-only
/proc = fresh procfs, then remounted read-only
/mesc-run/repository = read-only
/mesc-run/inputs = read-only, exactly one declared synthetic marker
/mesc-run/model-weights = read-only and empty for qualification
/mesc-run/scratch = bounded 256 MiB tmpfs
/mesc-run/output = bounded 64 MiB tmpfs
/ = remounted read-only after scratch/output submount creation; only declared tmpfs submounts remain writable
/content, /home, /mnt, /root, /run, /var = not mounted
```

The launcher does not use `--share-net`; the isolated process receives a separate network
namespace. The model-visible environment contains only the bounded PATH/Python control
variables and exact frozen MRL policy identities. Reusable credentials are not forwarded.

If bubblewrap is unavailable or the hosted kernel/provider does not permit the required
namespace/mount controls, qualification is `BLOCKED`; the producer must not downgrade to a
weaker container/config-only claim.

## Synthetic control probe

`scripts/mesc_mrl_0808_sandbox_probe.py` is control-only. It loads no model, tokenizer,
corpus, evaluator, or sealed Tier-3 content. From inside the sandbox it proves:

- the exact declared synthetic input is readable;
- repository, input, and empty model-weight roots reject writes;
- scratch and output roots accept bounded temporary writes;
- root, home, and `/tmp` reject writes;
- DNS is unavailable;
- direct network egress is denied;
- cloud metadata access is denied;
- known container/control sockets are absent;
- reusable credential environment variables are absent.

The observation records zero monetary cost as a probe claim only; independent provider
attestation remains required before that claim can become trusted evidence.

## Stop and cleanup proof

A successful normal probe is not sufficient. The launcher starts a second disposable
sandbox process that deliberately attempts a forbidden repository write. Qualification
requires that process to terminate non-zero and that the forbidden file never appear in the
host repository.

The in-sandbox supervisor also validates the output tmpfs capacity and exact artifact-class
set, emits `sandbox-control-evidence.json`, and runs separate disposable challenges proving
that an extra undeclared output class is blocked even when the complete declared artifact set
is present, and that writing beyond the frozen 64 MiB output
budget terminates with ENOSPC. The run-scoped tmpfs mounts are destroyed when each namespace
exits. The launcher then emits `sandbox-cleanup-receipt.json`, binding:

- the exact challenge;
- exact runtime-context, observation, and sandbox-control-evidence digests;
- exact repository SHA/tree;
- exact sandbox policy identity;
- normal probe exit code zero;
- stopped forbidden-write violation probe;
- blocked undeclared-output challenge;
- blocked output-budget challenge;
- absent forbidden repository write;
- destruction of the run-scoped scratch/output tmpfs namespaces;
- minimal runtime-root enforcement.

A cleanup or stop-control mismatch fails closed before challenge consumption or attestation.

## One-time verifier challenge

`scripts/mesc_mrl_0808_sandbox_challenge.py` maintains an external verifier ledger. The ledger
path is mechanically rejected if it resolves inside the producer repository. A fresh challenge
begins as `ISSUED` and is bound to the exact producer-source repository SHA/tree,
MRL-0804 runtime evidence/identity, and sandbox policy identity.

Consumption requires exact canonical bytes for:

```text
runtime-context.json
sandbox-observation.json
sandbox-control-evidence.json
sandbox-cleanup-receipt.json
```

and the independently known provider execution identity. Issuance paths must be direct
non-symlink files whose filename binds the exact challenge. `consume` and `cancel` serialize
through one non-blocking advisory per-challenge terminal-transition lock before testing or
writing terminal state. The operating system releases the lock on process exit, so a stale
lock-file inode cannot permanently strand an issued challenge. A successful consumption writes
one `CONSUMED` receipt binding all four digests. The
same challenge cannot be consumed twice. A cancelled challenge cannot be consumed, and a
consumed challenge cannot subsequently be cancelled.

Challenge ledger files remain external custody and are never production trust by themselves.

## Independent runtime-sandbox attestation

`scripts/mesc_mrl_0808_sandbox_attest.py` renders an **untrusted** canonical attestation only
after an independent control-plane review has verified the hosted execution/session. Every
input and the attestation output are mechanically required to remain outside the producer
repository and symlink endpoints are rejected. It
binds:

- Google Colab / dynamic-assigned / owner Google;
- exact provider execution identity;
- exact consumed challenge receipt;
- exact runtime context, observation, sandbox-control-evidence, and cleanup receipt digests;
- exact producer repository SHA/tree;
- zero monetary cost;
- independent verification method and reference.

Rendering structurally valid bytes does not grant trust. The exact attestation SHA-256 must
later be admitted through the separately controlled
`TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256` registry.

## Staged trust boundary

The producer commits:

```text
TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256 = frozenset()
```

Therefore the producer cannot emit `sandbox_qualified=true`, even with locally fabricated
observation and attestation bytes.

After genuine hosted execution and independent verification, the dependency order is:

1. review the exact hosted custody and attestation;
2. admit only the exact runtime-sandbox attestation digest through a minimal trust PR;
3. merge that PR under ordinary guarded governance;
4. run the qualifier from fresh exact canonical main against the immutable producer-source
   custody;
5. independently `--verify-existing` the deterministic nine-artifact qualification bundle;
6. admit only the exact MRL-0808 real-preflight evidence digest through a separate minimal
   evidence/index/checklist PR;
7. require fresh post-admission canonical-main qualification before closing #424.

The attestation-trust PR and real-preflight-evidence admission PR are intentionally distinct.

## Immutable producer-source semantics

A genuine hosted sandbox execution is bound to the producer-source commit and tree. Later
attestation-trust admission necessarily changes the trust registry, so
`scripts/mesc_mrl_0808_sandbox_qualify.py` permits a later verifier commit only when:

- the producer source is on the verifier's canonical first-parent lineage;
- the source tree matches the attested tree;
- all changes from source to verifier are confined to the sandbox module and its focused
  trust-regression test;
- after AST normalization of the one attestation-trust assignment, the sandbox module is
  semantically identical.

Any other policy, parser, probe, qualifier, authorization, or sandbox-semantic drift requires
new hosted evidence rather than rebinding historical execution.

## Deterministic qualification bundle

After attestation trust admission, the qualifier emits exactly:

```text
runtime-context.json
sandbox-observation.json
sandbox-control-evidence.json
sandbox-cleanup-receipt.json
challenge-receipt.json
runtime-sandbox-attestation.json
runtime-sandbox-evidence.json
sandbox-qualification-receipt.json
mrl-0808-real-preflight-evidence.json
```

`--verify-existing` recomputes all derived artifacts and requires byte identity. The final
real-preflight envelope remains untrusted until the separate outer evidence admission PR.

## Outer MRL-0808 evidence

The deterministic envelope uses the already canonical evidence role:

```text
task_id = MRL-0808
kind = mesc.mrl.real_preflight.sandbox.v1
sandbox_qualified = true
network_policy_enforced = true
mutation_paths_frozen = true
output_destinations_frozen = true
stop_conditions_frozen = true
```

Its `runtime_sandbox_evidence_sha256` binds the trusted attestation, one-time consumed
challenge, runtime context, observation, sandbox-control evidence, and cleanup proof. Its
subject is the deterministic sandbox-qualification receipt.

## Producer non-admission

This producer PR must not mutate:

- `TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256`;
- the real-preflight evidence index;
- `specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0808.json`;
- the MRL-0808 task checkbox;
- MRL-0809/MRL-0899 readiness state;
- training, promotion, release, deployment, or clinical authority.

MRL-0808 remains `PLANNED` until the genuine evidence-admission path is complete on canonical
main.

## Explicit non-grants

```text
MODEL_LOADING = FALSE
TOKENIZER_LOADING = FALSE
SCIENTIFIC_MODEL_EXECUTION = FALSE
SCIENTIFIC_EVALUATION_EXECUTION = FALSE
SEALED_TIER3_ITEM_DISCLOSURE_TO_MODEL = FALSE
TRAINING_AUTHORIZED = FALSE
TRAINING_READY = FALSE
WEIGHT_MUTATION_AUTHORIZED = FALSE
PAID_COMPUTE_SPEND = NOT_AUTHORIZED
PROMOTION_AUTHORITY_PRESENT = FALSE
RELEASE_AUTHORITY_PRESENT = FALSE
CLINICAL_AUTHORITY_PRESENT = FALSE
MRL_REAL_EXPERIMENT_READY = FALSE
PROJECT_COMPLETION = NOT_CLAIMED
```

## Closure rule

MRL-0808 may close only after separate genuine attestation and evidence admission, guarded
merges, successful exact-main CI/CodeQL/Optional Extras, and fresh canonical machine-state
proof of:

```text
MRL-0806 = CLOSED_CANONICAL
MRL-0807 = CLOSED_CANONICAL
MRL-0808 = CLOSED_CANONICAL
MRL-0809 = PLANNED
MRL-0899 = PLANNED
MRL_REAL_EXPERIMENT_READY = FALSE
TRAINING_AUTHORIZED = FALSE
TRAINING_READY = FALSE
PROJECT_COMPLETION = NOT_CLAIMED
```
