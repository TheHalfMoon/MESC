# MRL-0804 hosted runtime qualification producer

## Purpose

This package produces deterministic, **untrusted** MRL-0804 runtime/GPU qualification
evidence from an externally executed hosted-GPU smoke. It does not load a model or tokenizer,
run Experiment-0 scientific evaluation, perform inference, mutate weights, train, promote,
release, or deploy a model.

The committed authorization is:

```text
mrl-0804-runtime-authorization-v1.json
```

Its exact SHA-256 is bound in the producer implementation. The control-plane entry point also
requires a clean exact Git work tree descended from the authorized canonical MRL-0803 base.

## Authorized hosted runtime surfaces

The initial authorization contains two provider identities:

```text
GOOGLE_COLAB / DYNAMIC_ASSIGNED / runner=colab
HUGGING_FACE_JOBS / zero-a10g / runner=other
```

Google Colab remains the preferred Experiment-0 runtime surface. The Hugging Face Jobs entry
is a separately authorized hosted-GPU qualification surface and is restricted to the exact
`zero-a10g` flavor. The authorization does not permit a paid hardware fallback. If the exact
free/quota-backed surface is unavailable, MRL-0804 remains blocked rather than silently
switching to a billable GPU flavor.

The local control laptop is never a qualifying runtime surface.

## Network boundary

Repository/dependency/probe preparation may use separately authorized setup network access.
That setup phase is outside the smoke claim. The actual qualification observation and smoke
must record:

```text
network_accessed = false
remote_code_allowed = false
```

No model repository, tokenizer repository, inference endpoint, training dataset, or remote
code may be accessed by the smoke itself.

## Bounded GPU smoke

The standalone probe requires exactly one CUDA-visible hosted GPU, records its actual model
name and total memory, records Python/PyTorch/CUDA/runtime identity, and executes only a small
deterministic integer tensor expression on CUDA:

```text
x = [1..16]
y = x * 3 + 7
```

The exact result vector must match the deterministic CPU-computed expectation. The probe does
not import Transformers, Unsloth, PEFT, TRL, model code, tokenizer code, or training code.

## Exact source binding

The control-plane qualifier recomputes and binds:

- exact repository commit and tree;
- exact committed `uv.lock` SHA-256;
- exact committed GPU probe source SHA-256;
- exact committed authorization SHA-256;
- exact runtime observation SHA-256;
- exact smoke receipt SHA-256.

The hosted probe is expected to be acquired from an exact canonical commit and its downloaded
bytes must match the precomputed committed probe digest before execution.

## External custody outputs

The hosted probe emits externally:

```text
runtime-observation.json
runtime-smoke.json
```

The exact control-plane qualifier consumes those bytes and emits an external bundle:

```text
runtime-observation.json
runtime-smoke.json
runtime-identity.json
runtime-qualification-receipt.json
mrl-0804-real-preflight-evidence.json
```

A second verifier recomputes the entire deterministic bundle from the original observation and
smoke bytes and requires byte-identical derived artifacts.

## MRL-0804 evidence envelope

A qualifying candidate uses:

```text
kind = mesc.mrl.real_preflight.runtime.v1
platform_qualified = true
network_accessed = false
remote_code_allowed = false
subject_sha256 = runtime_identity_sha256
runtime_identity_sha256 = exact produced runtime identity
runtime_qualification_receipt_sha256 = exact produced qualification receipt
smoke_receipt_sha256 = exact bounded GPU smoke receipt
```

Schema validity is not trust admission.

## Trust boundary

The producer must not modify:

```text
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
real-preflight-evidence-index-v1.json
specs/mesc-research-loop-v1/tasks.md
```

After the producer is independently reviewed, merged, and post-merge qualified, genuine hosted
GPU evidence must be produced and independently revalidated. Only then may a separate
exact-digest trust-admission mutation be considered under Issue #410.

## Explicit non-authority

MRL-0804 runtime qualification does not grant model/tokenizer loading, inference, Experiment-0
scientific execution, training, fine-tuning, weight mutation, promotion, release, or clinical
deployment authority. Those gates remain fail-closed and separately governed.
