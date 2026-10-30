# mm-arena 0.2.1

Released 2026-10-30. Reporting and provenance changes. Scoring (`market.py`, `metrics.py`,
`stats.py`, `decompose.py`) is unchanged from 0.2.0.

## Added

- Trace version 2. Each trace carries a `provenance` object: the package version and, for LLM
  agents, provider, model, options, the harness version (`claude --version` for `claude-cli`,
  the SDK version for `anthropic` and `openai`) and a SHA-256 of the step-0 prompt. Each LLM
  step's `info` records `prompt_sha256`. Version 1 traces still load and score unchanged.
- Variance table: paired realized vs expected P&L for the two highest-ranked LLM setups
  (`variance.top_llm_pair` in `summary.json`).
- Run-to-run section: the sample SD of each setup's run edges, for any number of replicate
  runs (`replicates.setups[].pooled.run_sd`).

## Changed

- Effort figure: lines that skip an effort level without a run are dashed, and the subtitle
  lists the replicate runs found in the report.

## Upgrading

No action needed. Rerun `mm-arena report <run_dir>` to add the new columns to an existing
report. The committed `core-v1` traces are the same as in 0.2.0.

Full list: [CHANGELOG.md](../CHANGELOG.md).
