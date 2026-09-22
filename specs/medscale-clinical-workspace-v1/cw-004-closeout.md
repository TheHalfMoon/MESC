# CW-004 Canonical Closeout Evidence

- **Task:** CW-004 — No-backflow and data-classification guard
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#474](https://github.com/TheHalfMoon/MESC/issues/474) — CW-004 activation
- **Implementation PR:** [#475](https://github.com/TheHalfMoon/MESC/pull/475) — `feat/cw-004-no-backflow-guard`
- **Qualified PR head:** `bae0734c7460b58478cec9641ae728cdb31b9f5c`
- **Qualified head tree:** `462f270a400883fce0e186dfe6ac84febc2f50cd`
- **Base:** `2ae276f2f6e80eacd2a9cc705f6a9972aabd3f88` (tree `d42ba26cd7629279329a2ec02ec43ee1aa475340`)
- **Canonical merge SHA:** `7029691e67b121c3b0903db5a6402a7c4719b78a`
- **Canonical merge tree:** `462f270a400883fce0e186dfe6ac84febc2f50cd`
- **Merge parents:** `2ae276f2f6e80eacd2a9cc705f6a9972aabd3f88` (previous canonical `main`), `bae0734c7460b58478cec9641ae728cdb31b9f5c` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md) sections 3.4 (research evidence and clinical state are different asset classes), 4 (data domains) and 9 (data domains R/W/X), [data security and threat model](data_security.md) sections 2 through 4 (trust domains, data-flow rules, data classification), [migration/recovery contract](migration_recovery.md)

This record documents closure evidence that already exists on canonical `main`; it creates no
clinical, PHI, training, publication, research-admission or runtime authority.

## 1. Governance state entering implementation

```text
CW-001, CW-002, CW-003          CLOSED_CANONICAL
CW-003 closeout merge           2ae276f2f6e80eacd2a9cc705f6a9972aabd3f88
CW-004                          activated under Issue #474 on 2026-09-22
gating contracts                already Founder-ratified through the canonically effective
                                CW-000 planning package (ADR-0038, as accepted under R6);
                                no new ADR was required by the ledger, and none was invented
new dependencies                none: no new runtime dependency was introduced
Issue #464 item 3               load-bearing data-class constant; resolved inside this unit
                                by the canonical typed vocabulary (items 1 and 2 stay separate)
```

## 2. Pre-merge exact-head evidence

Exact head `bae0734c7460b58478cec9641ae728cdb31b9f5c` on base `2ae276f2f6e80eacd2a9cc705f6a9972aabd3f88`:

- CI run `35702277708` (CI #2195): SUCCESS — `static (py3.11)`, `static (py3.12)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`;
- CodeQL run `35702277660` (CodeQL #2205): SUCCESS (`analyze (python)`);
- the required checks were present and passing on that exact head (`statusCheckRollup` all SUCCESS; `cubic` NEUTRAL/skipping only);
- unresolved review threads immediately before merge: 0 (protected merge succeeded under the thread-resolution rule; no open review threads reported).

### 2.1 Review lane, recorded honestly

```text
Alibaba Open Code Review   v1.12.8 (5c7b383), windows/amd64, verified installed before use
                           (https://github.com/alibaba/open-code-review). Its review path
                           sends diffs to a configurable LLM service, which would be remote
                           model egress of repository content; that is NOT_AUTHORIZED in this
                           program, so only its local no-LLM paths were used
                           (`delegate preview`, `delegate rule`, `rules check`).
                           No OCR LLM review is claimed.
OCR default exclusions     recorded, and explicitly covered by the host review instead:
                           ROADMAP.md, apps/workspace/README.md,
                           specs/medscale-clinical-workspace-v1/README.md and tasks.md
                           (unsupported_ext), and both new test modules (default_path).
Jev screening              NOT PERFORMED. The `jev` executable is not installed in this
                           environment, and remote-model egress of repository content is not
                           authorized by this program's standing non-grants, so no repository
                           content was sent to any Jev/TypeSafe provider. No Jev version,
                           finding, or confidence value is claimed.
host-agent review          PERFORMED on the complete diff, attributed to the host agent,
                           applying the OCR rule set (dead code, mutable shared state,
                           boundary/edge cases, error handling, identity comparisons,
                           resources, concurrency, security-sensitive code) plus a manual
                           semantic and security pass over every file class OCR excludes.
reviewing GitHub bots      cubic (NEUTRAL/skipping), CodeRabbit (pass / review skipped:
                           manual review required) — no finding produced.
```

### 2.2 Review-driven repairs inside PR #475

PR #475 arrived as a single commit (`bae0734`); the three host-review findings below were
found and repaired before that head and are covered by adversarial regression tests in the
same head:

| Finding | Repair in `bae0734` |
|---|---|
| fail-open: a raw classification string resolved to a domain through `StrEnum` equality, so an unvalidated string could reach the canonical table | `class_admission_of` now requires an admitted member; raw strings fail closed |
| fail-open: export containment compared path components but not the volume root, so a target on another drive could read as inside the quarantine root | containment now compares the drive letter / UNC server-share as well |
| fail-open: a hand-built `FlowEvaluation` (`admitted=False`, no refusal class) would have passed `require()`, and a hand-built `FlowDecision` could claim an admitted Domain R destination | both now fail closed at construction |

### 2.3 Negative and superseded evidence

```text
superseded GitHub heads   none claimed: no GitHub-visible superseded head with in-flight
                          CI exists for PR #475; the repairs above predate the pushed head
cancelled / stale runs    none claimed as success
local Windows limit       tests/test_mesc_mrl_0808_sandbox_v1.py imports the Unix-only
                          `fcntl` module at import time, so that unrelated file cannot run
                          locally on Windows; it was not weakened, skipped, or modified
```

No MRL-0809-frozen source (`pyproject.toml`, `uv.lock`, workflows, MRL modules, MRL evidence)
was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR #475 merged through the repository's protected merge path on 2026-09-22 (`mergedAt`
2026-09-22T08:41:30Z, by TheHalfMoon, `merge` method). No bypass, no force-push, no rebase,
no history rewrite, no gate weakening.

```text
BASE  = 2ae276f2f6e80eacd2a9cc705f6a9972aabd3f88
HEAD  = bae0734c7460b58478cec9641ae728cdb31b9f5c
MERGE = 7029691e67b121c3b0903db5a6402a7c4719b78a
TREE  = 462f270a400883fce0e186dfe6ac84febc2f50cd
```

## 4. Fresh-main qualification

Workflows triggered by merge commit `7029691e67b121c3b0903db5a6402a7c4719b78a`:

- CI run `35706184021` (CI #2196): SUCCESS;
- CodeQL run `35706183919` (CodeQL #2206): SUCCESS;
- Optional Extras / Backends run `35706183998` (#501): SUCCESS;
- Hugging Face Publication Qualification run `35706183993` (#56): SUCCESS.

Local supporting evidence on the merged tree, never a substitute for the GitHub gates above:

```text
Clinical Workspace suites (CW-001 .. CW-004)   304 passed (133 CW-004: 66 focused + 67 adversarial)
CW-004 re-verified on this checkout            133 passed
strict mypy                                    no issues in 501 source files
ruff check . / ruff format --check .           clean
docs link hygiene                              PASS (127 Markdown files)
boundary guard                                 PASS (CW-002/003/004 rules)
```

## 5. What CW-004 delivered

```text
classification   one canonical typed vocabulary in data_class.py: the five trust domains
                 of the planning package, the admitted data classes, and one table binding
                 every class to exactly one domain; the domain is always derived, never
                 asserted; unknown/malformed class, unsupported version, or a recorded
                 domain contradicting the table fails closed; the repeated SYNTHETIC
                 literal of Issue #464 item 3 is replaced by the one canonical value
no-backflow      nobackflow.py holds the single declared trust-domain flow table and the
                 only guard entry points; Domain R is refused as a destination for every
                 source (no write/copy/import/admission from the Workspace package);
                 quarantined export refused automatic Research admission and refused
                 re-admission as Workspace state; telemetry/analytics/logs refused as
                 Research Core data; secret-class material refused every flow including
                 inside Domain W; undeclared and declared-but-unauthorised edges refused;
                 refusals carry provenance metadata (rule, domains, object identity),
                 never payload content
export           admit_export_path and stage_export prove a strict below-root quarantine
containment      target outside every Research Core root over caller-supplied absolute
                 paths (components plus volume root); de-identification is a transformation
                 of an export, never an admission
guard            scripts/check_clinical_workspace_boundary.py gains the CW-004 structural
                 rules: the typed vocabulary defined once in data_class.py, the flow table
                 and guard entry points defined once in nobackflow.py, no classification
                 literal or TrustDomain/DataClass member named elsewhere, both declared
                 tables validated at import time
tests            133 CW-004 tests (66 focused, 67 adversarial): file shapes (traversal,
                 separators, drive-relative, UNC, extended-length, ADS colon, trailing
                 dot/space, device names, NUL/controls, other volume), API shapes (raw
                 strings, duck types, str subclass, int destinations, non-bool flags,
                 lookalikes, forged rule), object shapes (relabelling, forged/contradicted
                 domains, extra/missing members, shared-mutation, hand-built objects)
```

## 6. Recorded limitations

```text
filesystem links          the Workspace package holds no filesystem capability (no os,
                          no pathlib, no open; the boundary guard forbids them), so the
                          file-level rule is a lexical containment proof and does not
                          resolve symlinks, junctions or reparse points; link-based escape
                          is owned by the first later unit that obtains a filesystem
                          capability, and by CW-019
guard performs no I/O     the guard decides and records; it never stages or reads an export
M1-M3 migrations          CW-004 adds no schema change, so CW-018 still owns the M1-M3
                          machinery
Issue #464 items 1-2      Workspace strict mypy coverage and version single-sourcing remain
                          separate and are not bundled here
prior limitations         platform secret-storage provider, whole-store rollback, plaintext
                          metadata visibility, secure_delete scope, audit write-once scope,
                          tail-truncation head digest, and append cost remain as previously
                          declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_004 = CLOSED_CANONICAL
CW_005, CW_009, CW_011, CW_013, CW_016, CW_017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own activation)
CW_006, CW_007, CW_008, CW_010, CW_012, CW_014, CW_015, CW_018, CW_019, CW_020 = BLOCKED_DEPENDENCY
CW_021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder/governance
  clinical-pilot authorization
Issue #474 = close with this closeout (activation fulfilled)
Issue #464 = open, separate CW-001 follow-up work unit (items 1-2; item 3 resolved here)
MRL-0809 (#429/#450) and MRL-0899 = separately governed and untouched
```

CW-004 grants no PHI ingestion, real patient import, clinical production use, real EHR write,
autonomous clinical action, remote application-model egress, Workspace-data training or
research evaluation/admission, model promotion, external publication, paid compute, MRL
contract mutation or new MRL Stage-4 attempt.
