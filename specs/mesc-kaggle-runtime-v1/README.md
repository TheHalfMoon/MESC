# MESC / MedScale Kaggle runtime adapter V1

Engineering scope: [Issue #545](https://github.com/TheHalfMoon/MESC/issues/545).
Provider boundary: [ADR-0041](../../docs/adr/0041-separate-kaggle-runtime-candidate-boundary.md).

## Authority and delivered surface

This optional adapter implements private read-only account/quota observation,
environment-candidate validation, and local/offline custody simulation. It has no
hosted execution transport. `require_scientific_execution` always rejects; no
caller label, test, quota result, model metadata or JSON approval arms execution.
The supplied source revision/tree/manifest are checked for exact identity, but
are caller inputs, not independently authenticated canonical main. Contract
validation is explicitly not runtime feasibility or trusted evidence admission.

The official CLI/SDK is an operator-installed inspection tool, not a new package
dependency. `scripts/mesc_kaggle_readonly.py` uses only authentication, a bounded
personal notebook listing and the supported `quota_view` method when available.
It reports UNKNOWN on absence/rejection/invalid quota and never echoes tokens,
notebook names, account names, endpoints or exception text. Its output is private
account status and must stay off public GitHub. An SDK quota observation does not
establish free billing, currently available GPUs, session isolation or fit.

The private observer now emits `MESC-KAGGLE-PRIVATE-READONLY-OBSERVATION-V2`.
Observed remaining whole seconds subtract both consumed and currently reserved
quota using exact integer microseconds. Missing reservations leave remaining
budget unknown; negative, malformed or overcommitted durations reject quota.
V1 observations remain historical and must not be relabeled with V2 semantics.
The official SDK defaults an omitted pay-to-scale field to false, so its false
value is `SDK_DEFAULT_OR_REPORTED_FALSE`, true is `SDK_REPORTED_TRUE`, and a
missing/non-boolean value is UNKNOWN. `zero_paid_compute_proven` remains false
in every case. These private telemetry labels establish no billing guarantee,
GPU capacity or execution authority. See [ADR-0042](../../docs/adr/0042-kaggle-reservation-and-billing-telemetry.md).

## Frozen environment candidate

The strict field envelope rejects extra fields, boolean-as-integer budgets,
unsupported providers, source mismatches, ambiguous identities and protocol drift.
The candidate binds the original uv.lock SHA-256
`6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4` and the
eight package versions in the existing MRL-0809 v2 frozen harness. Python is
3.11.x on Linux x86_64, matching the frozen comparable runtime. Numeric CUDA/driver
identities are required, but ABI and
CUDA/BMM compatibility require an actual future probe; matching labels do not
prove binary compatibility.

Frozen candidates remain:

- `Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`.
- `google/gemma-4-12B-it@707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`.
- `bitsandbytes-nf4-v1`; the single synthetic blue-triangle prompt only.

One or two Tesla T4 devices with compute capability 7.5 are inventoried separately;
each declared memory size must independently cover the frozen 12-GiB peak ceiling.
This is a minimum inventory screen, not proof of actual free memory/model fit.
All candidates run sequentially on cuda:0 in any future comparable probe. Extra
devices provide no pooled memory. Do not alter existing Colab preflight's exact
one-visible-device constraint to accommodate Kaggle. A separately authorized
Kaggle probe must demonstrate isolation and use the existing materialized tensor
placement audit, exact weight/staging manifest verification and BMM smoke.

CPU/disk offload, automatic device-map fallback, changed candidates/revisions,
quantization, input, training, weight mutation and paid compute reject validation.
No model weights, scientific datasets or patient content are read by this adapter.

## Offline custody contract

`OfflineCustodySession` accepts only canonical OFFLINE_SIMULATION candidates.
Its explicit test-state directory is a mock store, not a real grant location.
State/custody must be operator-owned directories without concurrent hostile
writers. Symlinks and Windows reparse directories are rejected; this offline
pathname-based helper does not provide a descriptor-relative hardened host
boundary. A future real controller requires that stronger filesystem boundary.
The exclusive fsynced run-ID consumption receipt precedes custody creation.
Changing custody does not refill that mock grant. Existing files are never
overwritten or deleted. Simulations may use new mock run IDs under tests; this
has no relationship to authorized provider allocation counts.

Every emitted environment/result artifact is immediately written exclusively,
fsynced and hashed locally. Only fixed result filenames are accepted. The
deterministic manifest sorts artifact names; a host ACK binds its exact byte hash.
Missing results, altered hashes, nonregular/linked files, exceeded budgets,
duplicate writes, interruption and timeout reject completion and preserve a
failure receipt where the disk permits. Null/negative mock results are preserved.
Failure receipts and manifests always identify OFFLINE_SIMULATION and confer no
scientific PASS. No stop command or real unassignment is simulated as a fact.

The mock elapsed clock is supplied by tests and must be an integer, nondecreasing,
and within the candidate bound (at most 14,400 seconds). The retained payload
budget is at most 1 MiB; small control receipts are additional bounded metadata.
These are offline engineering ceilings, not a ratified Kaggle campaign budget.
The future hosted controller must use its own trusted monotonic clock, watchdog,
fixed-account store and independent remote termination observation.

## Runtime gates still blocked

The following require a separately authorized hosted probe; none is proven by
offline tests or an authenticated notebook list:

1. Exact live final implementation/tree/manifest qualification and immutable human
   provider-specific authority; no Colab grant reuse.
2. Authenticated no-paid contract, current quota sufficient for the bounded run,
   available GPU identity, isolation, actual CUDA/BMM/package compatibility.
3. Both exact frozen model/staging/weights manifests and actual CUDA0 tensor
   placement, single-device memory fit and frozen no-network sandbox behavior.
4. A provider-supported preservation strategy that survives interruption and
   yields complete artifact bytes/hash checks plus independent host custody ACK.
   Official log streaming is a capability, not proof of full-artifact retention.
5. Fixed OS-account/provider consumption before the first launch, a hard runtime
   budget, and independent termination/unassignment. No retry on partial failure.

No kernel push/update/run is permitted by this specification. No training,
promotion, scientific RQ1 execution, clinical activation, PHI, production,
publication, release or MRL-0809/0899 closeout authority is granted.

## Acceptance commands

Run with the repository environment and `PYTHONPATH=src;scripts;tests` on Windows
(use colon separators on POSIX):

```text
python -m pytest tests/test_kaggle_runtime_adapter_v1.py tests/test_mesc_kaggle_readonly.py -q
ruff check src/medscale/mesc/_kaggle_runtime_adapter_v1.py scripts/mesc_kaggle_readonly.py tests/test_kaggle_runtime_adapter_v1.py tests/test_mesc_kaggle_readonly.py
ruff format --check src/medscale/mesc/_kaggle_runtime_adapter_v1.py scripts/mesc_kaggle_readonly.py tests/test_kaggle_runtime_adapter_v1.py tests/test_mesc_kaggle_readonly.py
mypy src/medscale/mesc/_kaggle_runtime_adapter_v1.py scripts/mesc_kaggle_readonly.py tests/test_kaggle_runtime_adapter_v1.py tests/test_mesc_kaggle_readonly.py
```

Independent correctness/security/scientific-boundary review, genuine native OCR
coverage/status, Graft structural evidence, Jev availability, exact-head CI and
CodeQL, normal merge and fresh-main qualification must be recorded truthfully.
