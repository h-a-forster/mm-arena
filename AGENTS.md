# AGENTS.md

Guide for coding agents (and humans) working on mm-arena. Read `docs/methodology.md` before
changing scoring, statistics or the trace format, and `docs/methodology-v2.md` before touching
the session suites.

## What this is

A benchmark that puts an LLM (or any agent) in the market maker's seat in trading-interview
games with the trader model fully disclosed. Hidden state is finite and enumerated, so the
simulator knows the exact public posterior at every step and scores each quote exactly against
a myopic Bayes-optimal quoter.
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
  version; never edit a released suite TOML. `core-v2`, `tight-v2` and `pilot-v2` are written by
  `scripts/make_suites_v2.py`; `tests/test_v1_frozen.py` and `tests/test_sessions.py` pin the
  released files. `docs/prereg-core-v2.md` changes only by dated amendment.
- Replicate runs are named `agent#rN` (N >= 2) via `--name` and need `--no-cache`, which
  `mm-arena run` enforces for LLM agents. Reports keep primary runs in the main tables and pool
  replicates in Run-to-run variability.
- Tests: offline, no API keys (fake providers), `tmp_path` for files, `@pytest.mark.slow`
  for anything over a few seconds.
- API keys come from environment variables only; never log, print or commit them.
- Every README number must trace to `results/core-v1/REPORT.md`, `summary.json` or, through
  `scripts/readme_numbers.py`, the traces. Rescore with `mm-arena report`, never edit generated
  files by hand.
- Scratch files go in `tmp/` (gitignored); `runs/` is gitignored. No `.bak` copies.
- The repository is public: change it through pull requests with CI, not direct pushes to
  main. No personal names, local user paths or machine details in committed files or logs.

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
| `scripts/readme_numbers.py` | rebuilds every `results/*/` report and checks it; README numbers that `REPORT.md` does not print |
| `scripts/open_weight.py` | open-weight arm: pinned GGUF on llama.cpp's server, run, report |
| `scripts/tune_k.py`, `scripts/headroom.py` | `bayes-mean` tuning, lookahead headroom |
| `src/mmarena/joint.py`, `sessions.py` | session suites: joint posterior over (regime, outcome), session specs, suite format 2 |
| `src/mmarena/session_engine.py`, `session_metrics.py`, `session_report.py` | sessions (trace version 3), per-session metrics, the session report |
| `src/mmarena/agents/session_baselines.py`, `agents/prompt_v2.py` | session baselines (oracle, learner, lookahead, ...), prompt v2.0 |
| `scripts/*_v2.py` | session suites: suite files and held-out suite, ladder, tuning, noise projection, learning-response calibration, ceiling |

## How to test

```sh
uv sync --all-extras --dev
uv run pytest -m "not slow"        # what CI runs
uv run pytest --runslow            # plus slow tests
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mm-arena run --agent bayes --suite smoke --out runs/ci && uv run mm-arena report runs/ci
uv run mm-arena run --agent bayes --suite smoke-v2 --out runs/ci2 && uv run mm-arena report runs/ci2
uv run python scripts/make_suites_v2.py            # suite files match their generation rules
uv run python scripts/readme_numbers.py
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

A session-suite run directory gets the reference quoters first, then the LLM runs: the report
reads a model's skill axes against their rows and names any that are absent.

```sh
uv run mm-arena run --agent baselines --suite pilot-v2 --out runs/pilot-v2
uv run mm-arena run --agent claude-cli:claude-opus-5-5@high --suite pilot-v2 --out runs/pilot-v2
uv run mm-arena report runs/pilot-v2
```

## Status

Updated: 2026-11-21. v0.2.1 is tagged (2026-11-08).

Done:
- v0.2.0 (2026-10-10): 16 agents on `core-v1`, centring vs width, clustered inference,
  replicates of Opus 5.5 @high and Haiku 5.5 @high, effort curve, cost chart.
- v0.2.1: trace version 2 (provenance, prompt hashes), top-two-LLM variance row, run-to-run SD
  per setup, effort-figure subtitle built from the report.
- Same-day replicates on Claude Code 2.1.308 (2026-10-30) of the four high-effort setups
  (Fable `#r2`, Haiku `#r3`, Opus `#r3`, Sonnet `#r2`) committed in `results/core-v1/`, report
  and README updated. Haiku `#r4` (same version and day as `#r3`) added: the first
  within-version pair, +1.4 [-4.5, 6.8] points. Every high-effort setup has two to four runs.
- Fable 5.2 @low and Opus 5.5 @high `#r4` on Claude Code 2.1.330 committed in
  `results/core-v1/` (17 agents). Fable 5.2 @low scores 97.4, 2.6 below `bayes`: `core-v1` has
  little room left to separate strong models, so no higher-effort Fable 5.2 runs were made on it.
- Open-weight arm prepared (`scripts/open_weight.py`, Qwen3-14B Q4_K_M), not yet run; it
  writes to `results/core-v1-open-weight/` so the `core-v1` Holm families stay unchanged.
- Session suites built beside core-v1 (no LLM run yet): `core-v2` (15 open + 30 mixed
  sessions, hidden informed share), the extension `tight-v2`, `pilot-v2` and `smoke-v2`;
  baseline results in `results/core-v2/` and `results/tight-v2/`; pre-registration in
  `docs/prereg-core-v2.md`. Next: the two-stage LLM pilot on `pilot-v2`.
