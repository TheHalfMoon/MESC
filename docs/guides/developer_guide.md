# Developer Guide

- **Status:** Guide
- **Date:** 2026-07-10
- **Related:** [CONTRIBUTING](../../CONTRIBUTING.md), [Program Rules](../governance/rules.md)

How to work in the MedScale repository.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (package/environment manager)
- Python 3.11 (uv can install it: `uv python install 3.11`)
- Git

> A JRE + the pinned HL7 FHIR validator will be required from **T2** onward (the FHIR
> toolkit). It is **not** needed for the current foundation.

## Setup

```bash
git clone https://github.com/TheHalfMoon/MESC MedScale
cd MedScale
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

## The quality gate

Run before every commit (pre-commit runs these automatically):

```bash
uv run ruff check .            # lint
uv run ruff format .           # format (use --check in CI)
uv run mypy                    # strict typing
uv run pytest                  # tests (add --cov for coverage)
```

All four must pass. Never commit with the gate red.

## Project layout

```
src/medscale/        the package (public API in __init__.py)
tests/               the test suite (deterministic)
docs/                all documentation
.github/workflows/   CI (ruff, mypy, pytest) + CodeQL
```

## Conventions

- **src-layout**, full type hints, `py.typed` shipped (downstream gets types).
- **Public API** is whatever `medscale/__init__.py` exports; keep it small and stable.
- **Determinism first:** new behavior gets a deterministic test with a fixed seed.
- **Conventional Commits** for messages (`feat:`, `fix:`, `docs:`, `build:`, `ci:`,
  `refactor:`, `test:`, `chore:`).
- **One ticket per session** (R4); trace each change to an issue / RQ / horizon.

## Adding a subpackage (when there is research to hold)

MedScale is intentionally one package. When a phase needs new code (e.g. `fhirkit` at
T2), add it as a subpackage under `src/medscale/` with its own tests and a clear public
surface — do **not** create empty top-level packages ahead of need
(see [ADR-0004](../adr/0004-t0-foundation-scope.md)).

## Releasing

Versioning is single-sourced in `src/medscale/__about__.py`. See the CHANGELOG and (when
introduced) the release workflow. Semantic Versioning; `0.x` while pre-research.
