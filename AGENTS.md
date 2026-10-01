# Repository Agent Tooling

This file establishes cross-repository agent tooling. Existing project-specific governance, specifications, ADRs, and canonical evidence remain authoritative.

<!-- graft:start -->
## Graft — repository context layer

Graft is required as the default codebase context and navigation layer for coding agents in this repository.

If Graft is unavailable, or the local `graft/` graph is absent or stale, initialize it from the upstream project at https://github.com/trailhq/Graft (`@nanonets/graft`). Run `graft init`, select the active agents (Codex and/or Claude as applicable), then run `graft build`.

Before broad source exploration, prefer the Graft graph:

- `graft check` — verify graph freshness.
- `graft map` — orient to the repository before exploring source.
- `graft ask "<question>" --source` — retrieve ranked context with source spans.
- `graft skeleton <file>` — inspect an API surface without reading the whole file.
- `graft callers <symbol>` — trace callers/dependencies and blast radius.
- `graft grep "<literal>"` — perform exhaustive indexed literal search.

After material code changes, run `graft build` to refresh the graph.

Treat `graft/` as a local, regenerable cache and do not commit it. Keep Graft usage zero-cost: deterministic structural graph operations are allowed; do not introduce paid model/API usage. Any model-backed enrichment must use an already-authorized local or free provider.

Graft provides repository context and navigation, not correctness or qualification evidence. Continue to run all repository-required tests, Jev qualification/review where applicable, Alibaba Open Code Review, CI, and security checks. Never fabricate Graft output, tool execution, CI, review, or evidence.
<!-- graft:end -->
