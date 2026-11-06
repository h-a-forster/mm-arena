# Backlog

## In progress

## Waiting on me

- Branch `polish-2026-10-30` is merged through a pull request (merge commit or fast-forward, CI on the pull request).
- v0.2.1 is tagged after the merge, with the release date in `CHANGELOG.md`, `CITATION.cff` and `docs/release-notes-0.2.1.md` matching the tag.
- The version is decided: 0.2.1 as prepared, or 0.3.0 for strict semver because of trace version 2.
- The 13 unpushed pre-audit commits on the branch carry a Claude `Co-Authored-By` trailer: kept, or stripped before the merge (history already on `main` stays as it is).
- Dependabot pull requests #11 to #15 are diffed and merged or closed; #11 needs a rebase on the SHA pins.
- The GitHub repository description carries the README's new first line (a public change).
- Stale remote branches are deleted: `upgrades-2026-10-23`, `claude/audit-fixes-2026-10-10` (no unique code; holds the removed `AUDIT-TASKS.md`) and the superseded Dependabot branches.

## Decided

## Proposed

- Drift within one Claude Code version is an estimate, not one pair: same-version replicates for Fable, Opus and Sonnet (README Open question 1).
- A second 2.1.296 run shows whether that version suited Haiku or its run 2 was a high draw.
- Run-level inference is in the report: a test with runs as the unit in `REPORT.md` and `summary.json`, so the Welch result no longer lives only in the README.
- A trace records the harness version that produced a cached reply, not the version installed at replay.
- A v2 suite with undisclosed or drifting α and s tests estimating the trader model from flow (fable review M1).
- `mm-arena --help` and the package docstring carry the README's first line; they still say "benchmark for LLM agents" (`src/`, left out of the docs-only pass).
- Each corrected p-value in the README names its Holm family size (fable review M3).
- Cost claims name their price column (fable review M4; low value, the frontier is the same in both columns).
- The README says the original eight runs can never be attributed to a Claude Code version, not only that it is unrecorded (fable review M5).
- The research questions in the README's Open questions have runs behind them (Haiku cards swings, competitive-market prompt, recall vs computation, deeper headroom).
