# MRL-0809 Evidence-Recovery-2 failure disposition

Status: CONSUMED / FAIL_HOST_PREFLIGHT_BEFORE_RUNTIME.

Recovery-2's only allocation was invoked on 2026-10-08 after the Founder approved PR #539
head `bbe2353f4688028bc6624e260fd2171c04863232` and its normal canonical merge
`56aaa5df4a4088cf0c3ba1ad19c2674e33adb0ef` passed fresh-main CI, CodeQL, Optional Extras /
Backends, and Hugging Face Publication Qualification. The clean live-main authority gate and
host fsync/journal checks also passed.

The canonical host allocator fsync'd its consumption receipt before the sole allocation.
Allocation returned zero and reported Session READY. The subsequent control-plane check in
the temporary host packet asserted that an active session's nominal usage rate must equal
zero as well as its compute-unit balance. That added rate condition was stricter than the
canonical runbook and caused the preflight failure. The subsequent retained observation
reported balance `0.0`, nominal rate `1.07` units/hour, one T4/GPU assignment, and STANDARD
machine shape. A nominal compute-unit rate is not a monetary billing receipt; this record
does not establish a cash charge or paid-unit consumption. No purchase command was invoked.

Google's [Colab FAQ](https://research.google.com/colaboratory/faq.html) states that exhausted
compute-unit balances revert to free-tier policies. This policy context does not turn the
rate observation into a billing measurement. Future operational preflight design must
distinguish nominal resource rate from paid-unit use without weakening the zero-paid-compute
contract.

No remote setup/config upload, dependency installation, model staging, BMM portability
preflight, candidate probe, or Recovery-2 driver invocation occurred. GPU UUID, VRAM, Colab
release identity, model observations, runtime feasibility receipt, recovery bundle, and host
ACK were never obtained. No runtime PASS, recovery success, trust admission, or closeout is
claimed.

One bounded canonical stop command returned zero and reported Session terminated. A separate
post-stop observation found balance `0.0`, usage rate `0.0`, account assignments `0`, and
server assignments `0`. Provider unassignment was observed; command return code alone was
not used as that proof.

The [failure record](../../specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-2-failure-record.json)
binds the exact implementation identity, authority, and qualification run IDs. Seven original
diagnostic/provenance files remain byte-exact in a private local archive. Six public copies
preserve their original bytes; the active-observation copy is a redacted derivative that
omits the stopped provider endpoint. Its manifest row separately binds the original private
bytes and the public derivative by byte count and SHA-256. The private archive hash is also
recorded. No raw endpoint is publicly disclosed. The captured temporary preflight source is
stored as text data with its original bytes intact. These files are failure diagnostics,
not scientific evidence or an active runtime entrypoint.

The first hosted allocation consumed the grant regardless of this operational error.
Recovery-2 cannot be reopened or automatically retried. Recovery-1 and all predecessor
records remain immutable. Any later allocation requires a new explicit bounded Founder
decision; the [Recovery-3 proposal](../../specs/mesc-experiment-0/mrl-0809-successor-v2/founder-decision-evidence-recovery-3-proposal.md)
is a proposal only and grants no implementation or runtime authority.

MRL-0809 and MRL-0899 remain open. RQ1 execution, training, weight mutation, model promotion,
release, deployment, trust admission, CPU/disk offload, paid compute, and clinical data are
not authorized by this failure disposition.
