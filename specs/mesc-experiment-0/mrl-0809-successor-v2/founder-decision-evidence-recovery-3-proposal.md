# Founder decision proposal — MRL-0809 successor v2 Evidence-Recovery-3

Status: PROPOSED_ONLY / NOT_ACCEPTED / NO_IMPLEMENTATION_OR_RUNTIME_AUTHORITY.

Proposed decision ID: `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3`.

## Concrete reason

Recovery-2 consumed its sole allocation but stopped before setup because the temporary host
operator packet incorrectly required an active free session's nominal compute-unit rate to
equal zero. The server reported STANDARD/T4, zero balance, and a nominal rate of 1.07 units
per hour. That rate alone does not establish monetary charge. One bounded stop succeeded,
and independent provider observation confirmed no assignments remained. No model or runtime
execution occurred. The Recovery-2 failure record and public diagnostic copies must become canonical, bind
the seven byte-exact privately retained originals by hash, and remain immutable before any
successor implementation is eligible. The stopped provider endpoint remains redacted in
public copies; its original private bytes must be retained.

## Proposed bounded grant

If explicitly accepted, this decision would authorize versioned Evidence-Recovery-3
implementation and exactly one additional zero-paid-compute Google Colab Free STANDARD-T4
allocation for the original evidence-recovery objective. The implementation would replace
the unjustified nominal-rate-zero test with a documented paid-unit/free-tier preflight and
add regression coverage distinguishing nominal rate from monetary/paid-unit use. It must
retain positive rejection of paid units, wrong provider/GPU/shape, missing authority, dirty
or moved canonical identity, and failed retention.

The exact roster and runtime contract would remain:

```text
Qwen/Qwen3-8B @ b968826d9c46dd6066d109eabc6255188de91218
google/gemma-4-12B-it @ 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
MACHINE_SHAPE = STANDARD
MONETARY_COST = 0
INPUT = SYNTHETIC_ONLY
RUNTIME_REPRESENTATION = bitsandbytes-nf4-v1
CPU_OFFLOAD = FALSE
DISK_OFFLOAD = FALSE
AUTO_DEVICE_MAP = FALSE
```

Continuous host copy-out, local fsync and complete byte/hash verification, a bounded remote
exit hold, and a verified host ACK would remain mandatory. Standard output alone would not
establish evidence retention. Recovery-2 must not be relabeled, reopened, or bypassed.

## Effectiveness and consumption

Acceptance would authorize preparation only. A successor must bind the exact canonical
Recovery-2 outcome SHA/tree and failure-record SHA-256, receive genuine required review,
pass exact-head qualification, obtain explicit Founder approval of its final implementation
head for normal merge, pass all four fresh-main workflows on that canonical merge, and pass
a clean live-main authority gate before allocation.

The first successor allocation would consume the single grant even on allocation, provider,
preflight, or retention failure. No automatic retry, replacement allocation, or relaunch.

## Non-grants

No model/revision/GPU/quantization substitution, paid compute, CPU/disk offload, RQ1 execution,
training, weight mutation, promotion, trust admission, MRL-0809/MRL-0899 closeout, release,
deployment, PHI, or clinical production authority would be granted. Any further allocation
would require another explicit Founder decision.

## Acceptance record

No Founder acceptance exists. Do not treat this proposal, repository inclusion, or a general
instruction to continue as approval. No Recovery-3 implementation or allocation may begin
until the Founder explicitly accepts this exact bounded decision.
