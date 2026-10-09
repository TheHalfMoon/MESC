# Recovery-3 implementation and activation boundary

This document supplements the immutable, hash-bound historical implementation
entry. It does not change that entry, the accepted implementation authorization,
the consumed Recovery-2 failure record, or any earlier scientific source.

## Implemented engineering controls

The versioned host and driver bind the frozen Qwen/Gemma revisions, NF4
representation and synthetic-only evidence workflow. The admission verifier
requires a clean checkout at live canonical main, exact executing source bytes,
the approved implementation's unchanged static manifest, a normal two-parent
merge of PR #543, and the latest applicable successful workflow attempts.

CI, CodeQL and Optional Extras must qualify the exact PR implementation head
before its final-SHA approval. Approval must precede the normal merge. After
merge, CI, CodeQL, Optional Extras and Hugging Face Publication Qualification
must succeed on exact live main. Main and approval are observed again before
admission returns. Missing, edited, revoked, mismatched or unavailable approval
and qualification evidence rejects admission; implementation acceptance alone
does not arm the allocation.

The host retains an exclusive, durable decision-scoped allocation receipt in
the operating system's account state directory. The location is independent of
HOME, USERPROFILE, checkout, evidence directory and implementation revision.
It is never removed or replaced by the controller. A separate execution-start
receipt prevents another driver invocation through a different custody path.
The remote POSIX driver writes its own fixed account/session execution receipt
before the BMM sequence. Failed attempts remain consumed; neither layer retries
allocation or model execution.

Allocation, copying, execution and stop commands are bounded. Owned-session
cleanup covers early setup errors, runtime failure and success. A successful
stop command is diagnostic only: a separate bounded provider observation must
verify zero assignments before termination is recorded as VERIFIED_UNASSIGNED.
Failed observation remains UNPROVEN. Private provider endpoints are excluded
from the read-only observer's public output.

## Separate final-SHA approval record

The Founder must first approve the exact fully qualified implementation SHA.
An agent must never infer that decision from broad engineering authorization
or write an approval without the direct human decision. The following public
record is created only after that decision and before merge, in Issue #450,
under the trusted Founder account (`TheHalfMoon`, GitHub numeric ID 285091250).
The admission verifier reads the record through GitHub's fixed HTTPS API.
The initial header is exact, followed by one JSON object:

```text
MESC_RECOVERY_3_FINAL_SHA_APPROVAL_V1
{"decision_id":"FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3","state":"APPROVED","implementation_sha":"<EXACT_FINAL_40_HEX_SHA>","static_manifest_sha256":"<EXACT_FINAL_MANIFEST_64_HEX_SHA256>","pull_request":543,"allocations_authorized":1,"provider_class":"GOOGLE_COLAB_FREE","gpu_class":"STANDARD_T4","paid_compute_authorized":false,"automatic_retry_authorized":false}
```

Placeholders are documentation, never an approval. An edited comment is
rejected. A newer structured decision supersedes earlier records, including a
REVOKED decision. Reapproval, a new implementation SHA or a new evidence
directory cannot replenish the fixed Recovery-3 consumption state.

## Remaining operational requirements

No real provider/model allocation is part of engineering tests. Before the
single authorized allocation, verify the actual authenticated Colab Free
contract and account, STANDARD/T4 capability, zero paid-unit balance and absence
of assignments. Positive nominal hourly rate is telemetry, not proof of a
monetary charge; neither zero balance nor a caller's provider-class label is an
authenticated billing receipt. No paid service or purchased units are allowed.

Prepare the host evidence disk, provider observer, exclusive consumption store,
remote clean canonical checkout, frozen local synthetic inputs, continuous
copy-out and host ACK. All complete artifacts must be retained and hash checked
before success. Failed retention, incomplete telemetry and partial ACK never
establish scientific success, trust admission or research closeout.

The final-SHA grant, normal merge and fresh-main qualification remain separate
gates. This document grants no allocation, RQ1 execution, training, offload,
model substitution, PHI use, clinical activation, trust admission, publication
or release authority.
