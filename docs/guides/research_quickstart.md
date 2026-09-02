# Research Quick Start

*Fifteen minutes from a fresh clone to your first screening decisions - no source
code reading required.*

## 1. Install (once)

```bash
git clone https://github.com/TheHalfMoon/MESC MedScale
cd MedScale
uv sync          # Python 3.11+, no runtime dependencies
```

Every command below is run from the repository root. The corpus lives in
`data/litdb` (the default `--root`), and it ships with the repository - you already
have 1,346 deduplicated records to work with.

## 2. Orient yourself

```bash
uv run medscale --version          # cite this in your methods section
uv run medscale check              # integrity: must say CLEAN before you start
uv run medscale screen status      # where the review stands
```

`check` exits 0 only when the corpus, screening log, and evidence store are
referentially intact. Run it **before and after every session** - it is the same
gate CI runs.

## 3. Resolve uncertain duplicates first

If `screen status` shows unresolved uncertain-duplicate groups, resolve them before
screening - otherwise you may screen the same paper twice under different records:

```bash
uv run medscale screen duplicates --reviewer <your-id>
```

For each group: pick the member to keep (`1`..`n`), declare them `d`istinct, or
`s`kip. Progress saves after every group; quit anytime with `q`.

## 4. Screen

```bash
uv run medscale screen next --reviewer <your-id> --query Q2 --limit 25
```

- **Always pass `--reviewer`** - every decision is permanently attributed to it in
  the audit trail. Do not screen as the default `operator`.
- `--query Q2` restricts to one research question's records; omit it to screen
  everything. `--limit` caps the session.
- Keys: `1` include, `2` exclude (you'll pick a reason from the taxonomy),
  `3` maybe (comes back later), `4` duplicate, `5` skip, `q` quit.
- Quit or Ctrl+C anytime: **every recorded decision is already saved.**

Made a mistake? Correct it - history is never rewritten, corrections are new
audit-trail events:

```bash
uv run medscale screen amend --record <record-id-prefix> --reviewer <your-id>
```

## 5. See what you did, then freeze it

```bash
uv run medscale stats > my-stats.json      # PRISMA counts, machine-readable
uv run medscale snapshot                   # citable knowledge-state identity
```

The snapshot id is a content hash of the entire knowledge state (corpus + decisions
+ evidence). Cite it in anything you write; anyone can later run
`medscale snapshot --verify <file>` to prove the state you cited is byte-for-byte
the state they have.

## 6. Commit your session

The data files are part of the repository on purpose - the git history is the
research record:

```bash
git add data/litdb && git commit -m "screening session: Q2, 25 records (<your-id>)"
```

## Where to go next

- The full workflow, stage by stage: [First Systematic Review](first_systematic_review.md)
- When something looks wrong: [Troubleshooting](troubleshooting.md)
- The rules the tooling enforces and why: `docs/governance/rules.md`, ADR-0017

## The three rules that keep your review reproducible

1. **Never edit anything under `data/litdb` by hand.** Every file there is either
   append-only or content-addressed; the CLIs are the only writers.
2. **One writer at a time.** The logs assume a single concurrent reviewer.
3. **Commit after every session.** Uncommitted work has no provenance.
