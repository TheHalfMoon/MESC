# Contributing to MedScale

Thank you for your interest. MedScale is an open research platform for **verifiable
clinical AI**. Its value comes from discipline, not volume — so contributions are held
to explicit scientific and engineering standards.

Please read this document, the [Code of Conduct](CODE_OF_CONDUCT.md), and the
[program rules R1–R7](docs/governance/rules.md) before opening a pull request.

## Ground rules (non-negotiable)

MedScale preserves these invariants at all times:

- **FHIR-native, validator-first, grammar-constrained, deterministic.**
- **Synthetic-only, PHI-free.** No real patient data enters training, evaluation, or
  benchmarks — ever (Rule R2).
- **No LLM-as-judge in any primary metric** (Rule R5). Headline metrics are executable.
- **One-way dependency.** MedScale must never depend on Afia.
- **Permissive licensing.** Anything shipped must permit derivative models and
  commercial use (Rule R3).
- **Reproducibility.** No result without a script and a committed artifact (Rule R7).

A change that violates any invariant will not be merged, regardless of quality.

## Development setup

MedScale uses [uv](https://docs.astral.sh/uv/) and Python 3.11.

```bash
git clone https://github.com/TheHalfMoon/MESC MedScale
cd MedScale
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

## The quality gate

Every change must pass, locally and in CI, before merge:

```bash
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy                  # strict typing
uv run pytest                # tests
```

The pre-commit hooks run the same checks. Do not bypass them.

## Workflow

1. **Trace your work.** Every change maps to an issue and, for research work, a research
   question (RQ1–RQ7) and a horizon. Work that maps to nothing is out of scope until the
   [Research Vision](docs/vision/MEDSCALE_RESEARCH_VISION.md) is amended.
2. **One ticket at a time** (Rule R4). Finish, verify, commit — do not open the next.
3. **Branch** from `main`; keep the change small and focused.
4. **Test deterministically.** New behavior needs a deterministic test with a fixed seed.
5. **Commit** using [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `docs:`, `build:`, `ci:`, `refactor:`, `test:`, `chore:`).
6. **Open a PR** using the template. Fill the checklist honestly.

## Decisions and ADRs

Any decision that would cost more than a day to reverse requires an
[ADR](docs/adr/) (Rule R6): propose, wait for approval, then implement. Use
[`docs/adr/0000-template.md`](docs/adr/0000-template.md).

## Citations

No citation is written from memory (Rule R1). Every reference resolves to a live API
response with an identifier, `verified_at`, and `source_api`. See the
[reproducibility policy](docs/research/reproducibility_policy.md).

## Reporting issues

Use the issue templates. For security or PHI concerns, follow [SECURITY](SECURITY.md).
