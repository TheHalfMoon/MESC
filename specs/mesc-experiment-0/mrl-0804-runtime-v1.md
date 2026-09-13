# MRL-0804 hosted runtime qualification producer

## Purpose

This package produces deterministic, **untrusted** MRL-0804 runtime/GPU qualification evidence from a bounded hosted-GPU smoke plus independently reviewed provider/control-plane evidence. It does not load a model or tokenizer, run Experiment-0 scientific evaluation, perform inference, mutate weights, train, promote, release, or deploy a model.

The committed authorization is `mrl-0804-runtime-authorization-v1.json`. Its exact SHA-256 is bound in the producer implementation. The control-plane entry point also requires a clean exact Git work tree descended from the authorized canonical MRL-0803 base.

## Authorized hosted runtime surfaces

The authorization contains these provider identities:

```text
GOOGLE_COLAB / DYNAMIC_ASSIGNED / owner=GOOGLE / runner=colab
HUGGING_FACE_JOBS / zero-a10g / owner=MedScale / runner=other
```

Google Colab remains the preferred surface. Hugging Face Jobs is authorized only for the exact `zero-a10g` runtime when it is demonstrably free or quota-backed. Paid hardware fallback is forbidden. If zero cost cannot be proven, MRL-0804 remains blocked.

The local control laptop is never a qualifying runtime surface.

## Provider identity is not self-authenticating

The hosted probe records provider labels and an execution identity, but those observation fields are **not authority**. A local host can reproduce environment strings, so runtime claims alone can never set canonical trust.

For Hugging Face Jobs, the probe observes provider-injected `JOB_ID` and `ACCELERATOR`. For Colab, setup must obtain the runtime identity from Colab control-plane/session evidence and expose it as `MESC_COLAB_RUNTIME_ID` before the isolated smoke. `COLAB_RELEASE_TAG` is used only to identify the runtime family. Neither path is sufficient by itself for trust admission.

A separate canonical `MESC-MRL-0804-PROVIDER-ATTESTATION-V1` document must independently bind:

- provider, flavor, owner, and execution identity;
- exact runtime observation SHA-256;
- exact smoke receipt SHA-256;
- exact repository commit and tree;
- exact dependency-lock SHA-256;
- exact probe-source SHA-256;
- provider status `COMPLETED`;
- `monetary_cost_microunits = 0`;
- an independent verification method and reference.

Any non-zero or unproven monetary cost fails closed.

## Network and process boundary

Repository preparation, provider scheduling, dependency setup, and PyTorch import may occur before the isolated smoke boundary. They must not be misrepresented as part of the no-network claim.

Immediately before the bounded CUDA smoke, the probe installs a Python audit hook that rejects socket activity, child-process launch, and `os.system`. The smoke records:

```text
network_accessed = false
remote_code_allowed = false
```

The probe source is additionally regression-tested to prohibit direct imports of socket, subprocess, urllib, requests, or httpx and to prohibit model/training primitives.

## Bounded GPU smoke

The probe requires exactly one CUDA-visible hosted GPU, records its actual model and memory, records Python/PyTorch/CUDA/runtime identity, and executes only:

```text
x = [1..16]
y = x * 3 + 7
```

The exact result vector must match the deterministic CPU-computed expectation. No model, tokenizer, dataset, evaluation, inference, or training code is authorized.

## Exact source binding

The control-plane qualifier recomputes and binds:

- exact repository commit and tree;
- exact committed `uv.lock` SHA-256;
- exact committed GPU probe source SHA-256;
- exact committed authorization SHA-256;
- exact runtime observation SHA-256;
- exact smoke receipt SHA-256;
- exact provider-attestation SHA-256.

The hosted probe must be acquired from an exact canonical commit, and its bytes must match the expected committed probe digest before execution.

## External custody outputs

The hosted probe emits:

```text
runtime-observation.json
runtime-smoke.json
```

Independent control-plane review supplies:

```text
provider-attestation.json
```

The exact control-plane qualifier emits the six-artifact bundle:

```text
runtime-observation.json
runtime-smoke.json
provider-attestation.json
runtime-identity.json
runtime-qualification-receipt.json
mrl-0804-real-preflight-evidence.json
```

Verify-existing mode recomputes the full deterministic bundle and requires byte-identical derived artifacts.

## MRL-0804 evidence envelope

A candidate envelope uses:

```text
kind = mesc.mrl.real_preflight.runtime.v1
platform_qualified = true
network_accessed = false
remote_code_allowed = false
provider_attestation_sha256 = exact provider attestation
runtime_identity_sha256 = exact runtime identity
runtime_qualification_receipt_sha256 = exact qualification receipt
smoke_receipt_sha256 = exact bounded GPU smoke receipt
```

Schema validity is not trust admission.

## Dual trust boundary

MRL-0804 admission requires two separately controlled exact digests:

```text
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
TRUSTED_MRL0804_PROVIDER_ATTESTATION_SHA256
```

The producer PR intentionally adds **no MRL-0804 digest** to either registry. A later trust-admission PR may add the exact evidence digest and exact provider-attestation digest only after genuine hosted execution and independent verification.

The producer must not mutate the real-preflight evidence index, the MRL-0804 checklist state, or any project-completion state.

## Explicit non-authority

MRL-0804 runtime qualification does not grant model/tokenizer loading, inference, Experiment-0 scientific execution, training, fine-tuning, weight mutation, promotion, release, or clinical deployment authority. Those gates remain fail-closed and separately governed.
