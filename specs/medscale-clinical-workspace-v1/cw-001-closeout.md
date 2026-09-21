# CW-001 Canonical Closeout Evidence

- **Task:** CW-001 — Workspace boundary skeleton
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** #462
- **Implementation PR:** #463
- **Qualified PR head:** `bb2e47d3a5a03e6fb09b211c7eeeaddf1416472b`
- **Canonical merge SHA:** `1ec0c3dd2e379649fd0b6a710b9dbde0f60490f3`
- **Canonical merge tree:** `6a77c34111105826a5bfe1df88a78f8bc95c5aee`

This record documents closure evidence that already exists on canonical `main`; it does not create clinical, PHI, training, publication or runtime authority.

## Pre-merge exact-head evidence

Exact head `bb2e47d3a5a03e6fb09b211c7eeeaddf1416472b` on base `00df6f1f97c3ac2f50b085b73881f178b3dfa6ea`:

- CI run `35602052984`: SUCCESS — `static (py3.11)`, `static (py3.12)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`;
- CodeQL run `35602053013`: SUCCESS (`analyze (python)` job `106340237786`);
- the three required status checks were present on that exact head: `quality (py3.11)`, `quality (py3.12)`, `analyze (python)`;
- unresolved review threads immediately before merge: 0 of 7;
- independent review: Alibaba Open Code Review v1.12.7 (`85cecfe`, windows/amd64) in delegation mode, which is LLM-free on the tool side, over the complete diff with full coverage accounting; no open critical or high finding on the qualified head.

### Review-driven repairs inside PR #463

| Found on head | Finding | Repair commit |
|---|---|---|
| `9c67a82774d1603d2e4fa36fb735087e9d448893` | indirect capability acquisition (`getattr(__builtins__, "__import__")(...)`, aliases, dictionary indirection) passed the fail-closed boundary guard | `9aad0b9c735d9df087596fe57d0e45745bd58b7f` |
| `9c67a82774d1603d2e4fa36fb735087e9d448893` | patient object type was not validated, and every encounter reused the constant `encounter-001` source key | `9aad0b9c735d9df087596fe57d0e45745bd58b7f` |
| `9aad0b9c735d9df087596fe57d0e45745bd58b7f` | object-graph capability reconstruction (`().__class__.__base__.__subclasses__()`, `object.__dict__["__subclasses__"]`) was not detected | `227b6e0837cb46f2e2c5df302adcc022034ad6d4` |
| `227b6e0837cb46f2e2c5df302adcc022034ad6d4` | frame-introspection escape (`exc.__traceback__.tb_frame.f_globals`), concatenated capability keys (`table["__imp" + "ort__"]`), and the runtime code-importing builtins `breakpoint()`/`help()` were not detected | `bb2e47d3a5a03e6fb09b211c7eeeaddf1416472b` |

Local negative-path evidence, recorded as supporting evidence only and never as a substitute for the GitHub gates above:

- an independent 26-case adversarial battery (21 hostile, 5 benign) driving `scripts/check_clinical_workspace_boundary.py` reported zero mismatches on the qualified head;
- the focused acceptance module passed 27 tests locally, strict mypy passed over 495 files, and Ruff lint/format passed repository-wide.

The in-flight CI runs for the superseded heads `9aad0b9c735d9df087596fe57d0e45745bd58b7f` and `227b6e0837cb46f2e2c5df302adcc022034ad6d4` were cancelled when the successor head was pushed. Those runs are recorded here as superseded, not as successes.

## Protected merge

PR #463 merged through the repository's protected merge path — ruleset `MedScale canonical main protection v1`: pull request required, review-thread resolution required, required status checks `quality (py3.11)` and `quality (py3.12)` and `analyze (python)` under a strict up-to-date policy, and `merge` as the only allowed merge method. No bypass, no force-push, no rebase, no history rewrite, no gate weakening.

```text
BASE = 00df6f1f97c3ac2f50b085b73881f178b3dfa6ea
HEAD = bb2e47d3a5a03e6fb09b211c7eeeaddf1416472b
MERGE = 1ec0c3dd2e379649fd0b6a710b9dbde0f60490f3
TREE = 6a77c34111105826a5bfe1df88a78f8bc95c5aee
```

## Fresh-main qualification

Workflows triggered by the merge commit `1ec0c3dd2e379649fd0b6a710b9dbde0f60490f3`:

- CodeQL run `35606839338`: SUCCESS;
- Optional Extras / Backends run `35606839442`: SUCCESS (`backends-transformers`, `backends-llamacpp`, `core-without-backends`, `rq1-grammar`, `rq1-runtime-feasibility`);
- Hugging Face Publication Qualification run `35606839473`: SUCCESS;
- CI run `35606839367`: SUCCESS on the merge commit — `static (py3.11)`, `static (py3.12)`, `analyze (python)`, all eight `pytest shard N (py3.11|py3.12)` jobs, `quality (py3.11)`, `quality (py3.12)`.

Every check run on the merge commit is terminal successful: `static (py3.11)`, `static (py3.12)`, `analyze (python)`, the eight pytest shards, `quality (py3.11)`, `quality (py3.12)`, `backends-transformers`, `backends-llamacpp`, `core-without-backends`, `rq1-grammar`, `rq1-runtime-feasibility`, and `publication contracts`.

## Result

```text
CW_001 = CLOSED_CANONICAL
CW_002 = ELIGIBLE_NOT_ACTIVATED
CW_003_THROUGH_CW_021 = BLOCKED_DEPENDENCY
```

CW-002 additionally requires its own implementation ADR (storage engine, key and cryptography strategy, migration approach) ratified under R6, plus separate activation, before any implementation begins.

This closeout grants no PHI ingestion, clinical production use, real EHR write, autonomous clinical action, Workspace-data training or research evaluation, model promotion, external publication, paid compute, MRL contract mutation, or new MRL Stage-4 attempt.
