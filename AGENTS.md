# AGENTS.md

Guide for coding agents (and humans) working on mm-arena. Read `docs/methodology.md` before
changing scoring, statistics or the trace format.

## What this is

A benchmark that puts an LLM (or any agent) in the market maker's seat in trading-interview
games. Hidden state is finite and enumerated, so the simulator knows the exact public
posterior at every step and scores each quote exactly against a myopic Bayes-optimal quoter.
Committed results: `results/core-v1/` (traces, `summary.json`, `REPORT.md`).

## Conventions

- uv + hatchling, `src/` layout, Python >= 3.11, typed code with
  `from __future__ import annotations`, `ruff check` + `ruff format` (line length 100),
  pytest. The only runtime dependency is numpy; SDKs and matplotlib are optional extras.
- Files are LF; use `pathlib` and forward slashes so everything runs on Windows.
- Scoring (`market.py`, `engine.py`, `metrics.py`) changes every published number: open an
  issue first and record it in the changelog. Common random numbers must hold: hidden outcome
  and counterparty draws depend only on (game id, seed), never on the agent.
- Suites are versioned. A change that alters any game or the prompt ships as a new suite
  version; never edit a released suite TOML.
- Replicate runs are named `agent#rN` (N >= 2) via `--name` and need `--no-cache`. Reports
  keep primary runs in the main tables and pool replicates in Run-to-run variability.
- Tests: offline, no API keys (fake providers), `tmp_path` for files, `@pytest.mark.slow`
  for anything over a few seconds.
- API keys come from environment variables only; never log, print or commit them.
- Every README number must trace to `results/core-v1/REPORT.md`, `summary.json` or the
  traces. Rescore with `mm-arena report`, never edit generated files by hand.
- Scratch files go in `tmp/` (gitignored); `runs/` is gitignored. No `.bak` copies.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The repository
  is public: change it through pull requests with CI, not direct pushes to main. No personal
  names, local user paths or machine details in committed files or logs.

## Layout

| Path | Role |
| --- | --- |
| `src/mmarena/games/` | game families and the `Game` / `Market` types |
| `src/mmarena/market.py` | exact posterior, quote value, Bayes and zero-profit quotes |
| `src/mmarena/engine.py`, `runner.py` | episodes and resumable JSONL suite runs |
| `src/mmarena/agents/`, `providers/` | baselines, LLM agent and prompt, API / CLI providers |
| `src/mmarena/metrics.py`, `stats.py`, `decompose.py` | per-episode metrics, bootstrap and tests, centring vs width |
| `src/mmarena/report.py`, `plots.py` | `summary.json`, `leaderboard.csv`, `REPORT.md`, plots |
| `scripts/figures.py` | README figures from a run directory |
| `scripts/tune_k.py`, `scripts/headroom.py` | `bayes-mean` tuning, lookahead headroom |

## How to test

```sh
uv sync --all-extras --dev
uv run pytest -m "not slow"        # what CI runs
uv run pytest --runslow            # plus slow tests
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mm-arena run --agent bayes --suite smoke --out runs/ci && uv run mm-arena report runs/ci
```

## How to run and report

```sh
uv run mm-arena run --agent claude-cli:claude-opus-5-5@high --suite core-v1 --out runs/core-v1
uv run mm-arena run --agent claude-cli:claude-opus-5-5@high \
  --name 'claude-cli:claude-opus-5-5@high#r2' --no-cache --suite core-v1 --out runs/core-v1
uv run mm-arena report runs/core-v1
uv run python scripts/figures.py runs/core-v1 docs/figures
```

LLM runs are long (a `core-v1` run is 860 quotes): run them in a resume-on-failure loop.
Traces append per episode and reruns skip finished episodes.

## Status and next steps

Updated: 2026-10-30 (v0.2.1 prepared on branch `polish-2026-10-30`, not tagged).

Done:
- v0.2.0 (2026-10-10): 16 agents on `core-v1`, centring vs width, clustered inference,
  replicates of Opus 5.5 @high and Haiku 5.5 @high, effort curve, cost chart.
- v0.2.1: trace version 2 (provenance, prompt hashes), top-two-LLM variance row, run-to-run SD
  per setup, effort-figure subtitle built from the report.
- Same-day replicates on Claude Code 2.1.308 (2026-10-30) of the four high-effort setups
  (Fable `#r2`, Haiku `#r3`, Opus `#r3`, Sonnet `#r2`) committed in `results/core-v1/`, report
  and README updated. Haiku `#r4` (same version and day as `#r3`) added: the first
  within-version pair, +1.4 [-4.5, 6.8] points. Every high-effort setup has two to four runs.

Open:
1. Drift within one Claude Code version rests on one pair (Haiku @high r3/r4). More
   same-version pairs, for other setups too, would make it an estimate (README Open question 1).
2. Tag v0.2.1 after the branch is merged.
3. Dependabot branches (checkout, setup-uv, anthropic, openai, ruff) are unmerged: diff each
   before merging. `origin/upgrades-2026-10-23` and `origin/claude/audit-fixes-2026-10-10`
   look squash-merged; delete them if so.
4. CI pins actions by tag; pin them to commit SHAs.
5. Research questions are listed under "Open questions" in the README (within-version drift,
   Haiku cards swings, competitive-market prompt, recall vs computation, deeper headroom).
