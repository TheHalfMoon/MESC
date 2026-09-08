# ADR-0037 — Adopt fail-closed retained-residue semantics for MRL-0801 acquisition

- **Status:** Accepted
- **Date:** 2026-09-08
- **Deciders:** Founder
- **Approval record:** Issue #389 comment `5589118654`
- **Supersedes:** none
- **Superseded by:** none
- **Related:** Issue #389, PR #390, ADR-0035, ADR-0036, Rules R4–R6, `specs/mesc-experiment-0/mrl-0801-hf-acquisition-provenance-v1.md`

## Context

Issue #389 originally requires an operational public Hugging Face acquisition executor and requires the executor to transactionally remove files created by the current run if a later step fails.

Security review of PR #390 demonstrated that a public namespace entry cannot safely be deleted merely because an earlier descriptor-relative `stat` observed a transaction-owned `(device, inode)`. Another writer can replace the name between the identity observation and `unlink`/`rmdir`, causing cleanup to delete a foreign entry. Retaining a directory descriptor constrains parent resolution but does not make the earlier inode observation and later name deletion one atomic kernel operation.

The hardened implementation uses `O_TMPFILE` plus `linkat(..., AT_EMPTY_PATH)` for atomic no-replace publication and performs no automatic identity-check-then-unlink cleanup. The earlier safe V1 substrate published and retained a witness inside the transaction directory and returned `BLOCKED` before remote metadata access. That substrate established the security problem but was not operational and did not by itself satisfy Issue #389.

Linux provides atomic no-replace publication from an open unnamed file through `linkat(..., AT_EMPTY_PATH)`. Ordinary `unlinkat()` removes the directory entry named at call time and provides no flag that conditions removal on a previously observed inode. `renameat2(..., RENAME_EXCHANGE)` atomically exchanges two names, but likewise does not condition the exchange on the destination still referencing a previously observed inode. A destructive rollback guarantee against an attacker-mutable namespace therefore cannot be implemented by combining a prior identity check with a later pathname deletion or exchange.

This is an expensive security and evidence-contract decision under Rule R6. The Founder/operator explicitly approved this ADR after the proposal was presented; the canonical approval record is Issue #389 comment `5589118654`.

## Decision

**Accepted — authorized for implementation under Issue #389.**

1. **Replace destructive public-entry rollback with fail-closed retained residue.**
   Once a transaction-created file receives a public namespace name, the executor never automatically deletes, replaces, exchanges, repairs, or reuses that name after a later failure. A failed transaction remains `BLOCKED`; its public residue is quarantined evidence for operator inspection.

2. **Separate capability witnesses from the model destination and receipt outputs.**
   Operational acquisition requires an explicit, pre-existing external capability-witness root on the same filesystem device as the transaction directory being qualified. The executor binds that witness root once through a no-follow directory descriptor, verifies exact device/inode identity, publishes a random hidden zero-byte witness from `O_TMPFILE` with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode, and retains it permanently. The model destination and receipt-output parent therefore remain unchanged by the capability proof.

3. **Continue only after successful retained-witness proof.**
   After the witness is published and verified in the dedicated witness root, the executor may proceed to the already-authorized public, unauthenticated, exact-revision metadata and model-byte acquisition path. Capability proof does not grant model loading, tokenizer loading, inference, GPU, training, weight mutation, trust admission, or MRL-0801 population authority.

4. **Preserve atomic no-replace asset publication.**
   Each authorized model file is streamed into an unnamed same-filesystem `O_TMPFILE`, byte-counted and content-verified, and only then atomically linked to its final authorized basename with no overwrite. A racing target causes the transaction to fail without modifying that foreign target. Any model files already published by the failed transaction remain retained residue.

5. **Make residue explicit evidence, never success.**
   No custody or provenance success receipt may be returned after a failed transaction. Any late metadata, byte, custody, destination-identity, receipt-publication, or finalizer failure leaves the transaction `BLOCKED`. A subsequent acquisition attempt must use a separately inspected empty model destination and unused receipt-output names. Existing residue is never resumed or silently repaired.

6. **Receipt publication follows the same rule.**
   Receipt capability proof uses the dedicated same-filesystem witness root. Receipt files themselves use unnamed-file atomic no-replace publication. If one receipt is published and a later receipt/finalization step fails, published receipt residue is retained and the transaction remains `BLOCKED`; automatic receipt deletion is prohibited.

7. **Amend Issue #389 acceptance after ADR acceptance.**
   Issue #389 must replace the phrase requiring destructive transactional removal of current-run public files with the retained-residue transaction contract above. The operational executor still must satisfy every other authorization, transport, storage, byte-integrity, SafeTensors custody, provenance, CI, independent-review, and post-merge qualification requirement already recorded in #389.

8. **Keep the trust boundary narrow and explicit.**
   This ADR does not claim that ordinary pathname deletion is inode-bound and does not weaken the concurrent-mutation threat model. It removes destructive cleanup from that threat surface instead.

## Consequences

**Positive**

- The executor cannot delete a foreign replacement merely because it previously observed a transaction-owned inode.
- Capability proof can become operational without polluting the model destination or receipt-output directory.
- The existing `O_TMPFILE` plus `linkat(..., AT_EMPTY_PATH)` no-replace publication path can be retained.
- Failure remains visible and auditable rather than being converted into an unsafe best-effort cleanup claim.
- Genuine MRL-0801 acquisition can proceed after canonical implementation and qualification without broadening model-loading, inference, GPU, or training authority.

**Negative / costs**

- Failed attempts may consume storage until an operator inspects and separately removes quarantined residue.
- The transaction contract becomes logical fail-closed atomicity rather than physical deletion rollback.
- Operators must provide and retain an external capability-witness root on each relevant filesystem.
- A fresh destination and unused receipt names are required after any failed attempt.

## Alternatives considered

- **Keep the always-blocked witness V1** — Rejected as the operational design because it cannot satisfy Issue #389 or produce genuine MRL-0801 acquisition evidence.
- **`stat`/`fstatat` followed by `unlinkat`/`rmdir`** — Rejected. The namespace entry can be replaced between the identity observation and deletion.
- **`renameat2(..., RENAME_EXCHANGE)` rollback** — Rejected as a general ownership guarantee. The exchange is atomic, but it does not require the destination name to still reference the previously observed inode and can move a foreign replacement.
- **Rely on random names alone** — Rejected. Unpredictability reduces accidental collision probability but does not establish ownership against a concurrent writer.
- **Rely on advisory locks, process-local locks, or ordinary owner-only mode bits** — Rejected as the generic contract. They do not prove exclusion of every same-credential concurrent writer.
- **Privileged detached-mount or mount-namespace transaction** — Not selected for V1 because Linux detached mount creation/attachment requires `CAP_SYS_ADMIN`, which would unnecessarily narrow portability and enlarge runtime authority. It remains a future platform-specific option if separately governed.
- **Atomic whole-directory exchange** — Not selected as the generic rollback primitive because `RENAME_EXCHANGE` is not conditioned on the target directory retaining the previously verified inode. It may be reconsidered only with a separately proven publication namespace contract.

## Compliance

Rule R6 approval is satisfied for this decision. Implementation must add deterministic network-free coverage proving at least:

1. capability witnesses are published only in the bound external witness root and never deleted automatically;
2. witness root and transaction directory are on the same filesystem device before proof is accepted;
3. model destination remains empty after capability proof and before metadata access;
4. an exact successful capability proof permits the authorized metadata phase to begin;
5. a foreign replacement of any witness, model target, or receipt target is never deleted or overwritten;
6. late acquisition/finalizer failure retains transaction residue and returns no success receipt;
7. a subsequent attempt against a non-empty failed destination is rejected before network access;
8. success still requires exact allowlist, revision, remote identity, storage, SafeTensors custody, provenance, Git identity, and path/credential-free receipt checks;
9. CI performs no live model-weight acquisition; and
10. exact-head CI, CodeQL, substantive independent review, ruleset verification, guarded merge, and fresh post-merge qualification all succeed before genuine external acquisition.

Acceptance of this ADR authorizes only the transaction semantics above. It does not authorize model/tokenizer loading, inference, GPU execution, training, weight mutation, credentials, terms acceptance, MRL-0801 trust admission, or production trust-registry mutation.