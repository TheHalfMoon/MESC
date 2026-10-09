# Recovery-3 official Colab CLI compatibility repair

## Observed pre-allocation failure

At canonical main `7242c8977813ec119fdf9f7da6188db24ef19a41`, the
Recovery-3 effectiveness gate and all four fresh-main workflows passed.
The operational pre-allocation observation then failed with
`ModuleNotFoundError: No module named 'colab_cli.common.state';
'colab_cli.common' is not a package` under official `google-colab-cli 0.7.4`.
No allocation controller invocation or model work followed this exception.
Both host consumption stores and the planned attempt custody directory
were independently observed absent immediately afterward. This is a
preflight engineering failure, not a consumed hosted scientific attempt.
Private account observations and provider endpoints remain off GitHub.

The official distribution exposes its singleton as `colab_cli.common.state`
through the `common.py` module's `state` attribute. It does not expose an
importable `colab_cli.common.state` submodule. The observer now imports the
module and reads that attribute. The official `Client.list_assignments()`
returns `ListedAssignment` objects with independent endpoint, accelerator,
variant and machine-shape fields; the generic `Assignment` type is not the
read-only listing schema. Server identity checks remain unchanged.

SDK-shaped regression tests cover the idle observation, allocated STANDARD-T4
identity, nominal-rate telemetry, private endpoint omission and server/local
identity disagreement. Tests use synthetic objects and perform no API calls,
allocation, stop, token change or model work.

## Activation remains separately gated

This repair changes frozen observer bytes and therefore the static source
manifest. The previous final-SHA approval of PR #543 cannot authorize the
changed implementation. A new immutable Founder decision must bind the
qualified final repair head, its exact manifest digest and the repair PR,
before its normal merge. The effectiveness verifier must target that repair
PR and retain all approval-timing, normal-merge, source-identity and workflow
requirements. Its source digest is also included in the updated manifest.

This is an amendment of the same still-unconsumed Recovery-3 grant, not a
second allocation grant. The authorization document, decision digest,
predecessor lineage, fixed account consumption stores, host execution store,
driver, retention/ACK process and one-shot/no-retry limits are unchanged.
Existing receipts, if any appear, always block allocation; this repair never
removes or replaces them. The original PR #543 and its approval history are
preserved.

The Founder separately permitted the single allocation to act as the
capacity test because CLI 0.7.4 has no supported read-only capacity query.
That clarification does not approve new source bytes. After final-SHA
approval, normal merge and four fresh-main successes, recheck the complete
canonical gate, clean executing source, paid-unit state, assignment state,
Free-only confirmation and durable storage before invoking the canonical
controller once. The first allocation call consumes the grant even if it
fails. Verify actual STANDARD-T4 identity before model work; preserve any
failure and terminate the owned assignment with independent unassignment
verification. No replacement allocation, retry or provider substitution is
permitted.

MRL-0809 and MRL-0899 remain open. This engineering repair proves no runtime
feasibility, trust admission, training, release or clinical readiness.
