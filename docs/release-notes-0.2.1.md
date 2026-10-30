# mm-arena 0.2.1

Released 2026-10-30. Reporting and provenance changes, and same-day replicates of the four
high-effort setups, including a second same-version run of Haiku @high. Scoring (`market.py`, `metrics.py`, `stats.py`, `decompose.py`) is unchanged
from 0.2.0.

## Added

- Trace version 2. Each trace carries a `provenance` object: the package version and, for LLM
  agents, provider, model, options, the harness version (`claude --version` for `claude-cli`,
  the SDK version for `anthropic` and `openai`) and a SHA-256 of the step-0 prompt. Each LLM
  step's `info` records `prompt_sha256`. Version 1 traces still load and score unchanged.
- Variance table: paired realized vs expected P&L for the two highest-ranked LLM setups
  (`variance.top_llm_pair` in `summary.json`).
- Run-to-run section: the sample SD of each setup's run edges, for any number of replicate
  runs (`replicates.setups[].pooled.run_sd`).
- Run-to-run section: setups with three or more runs also compare their later runs with each
  other (`replicates.setups[].later_pairs`).
- Five `core-v1` replicates run on one day with one Claude Code version (2.1.308): Fable 5.1
  @high r2 (its first replicate), Opus 5.5 @high r3, Haiku 5.5 @high r3 and r4, and Sonnet 5.5
  @high r2.

## Results

- Run-to-run SD of edge captured: Fable 5.1 @high 1.5 points (2 runs), Opus 5.5 @high 2.0 (3),
  Sonnet 5.5 @high 1.9 (2), Haiku 5.5 @high 4.4 (4).
- Drift within one Claude Code version, first look: Haiku @high runs 3 and 4 (2.1.308, same
  day, same prompts) differ by +1.4 [-4.5, 6.8] points (p 0.66), against gaps of 5.8 to 10.5
  points between its 2.1.296 run and the other three. One pair is one draw: the interval does
  not rule out several points of drift within a version.
- Fable leads Opus at high effort in all six pairings of their runs (0.9 to 6.9 points): pooled
  over games +4.0 [2.0, 6.3], same day and version +3.3 [0.6, 6.0]. With runs as the unit (two
  against three) the lead is not yet settled (Welch p 0.085).
- Haiku's 10.5-point jump in its second run did not repeat: runs 3 and 4 scored +3.3
  [-1.4, 8.9] and +4.7 [-1.9, 11.1] over run 1. Whether Claude Code 2.1.296 suited Haiku or run
  2 was a high draw is still open.
- Pooled, Opus and Haiku at high effort are indistinguishable (+1.1 [-2.7, 5.4]); Haiku @high
  beats Sonnet @high (+14.0 [9.3, 18.3]).

## Changed

- Effort figure: lines that skip an effort level without a run are dashed, and the subtitle
  lists the replicate runs found in the report on its own line.

## Upgrading

No action needed. Rerun `mm-arena report <run_dir>` to add the new columns to an existing
report. The committed `core-v1` traces from 0.2.0 are unchanged; the five new replicate traces
are added beside them.

Full list: [CHANGELOG.md](../CHANGELOG.md).
