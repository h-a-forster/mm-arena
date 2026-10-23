# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Report variance table: paired realized vs expected P&L for the two highest-ranked LLM setups
  (`summary.json` key `variance.top_llm_pair`). The README's episodes-needed figures for Fable vs
  Opus at high effort (25 with xPnL, 444 with realized P&L) now come from `REPORT.md`; the
  numbers are unchanged.

## [0.2.0] - 2026-10-10

### Added

- `mmarena.pricing`: API list prices. Reports cost runs from recorded token counts instead of the
  provider's own figure (Claude Code priced Haiku 5.5 at Opus rates).
- Cost figure and README section: edge captured against list price and latency per setup, with
  the Pareto frontier.
- Results for Claude 5.5 and Fable 5.1 models on `core-v1` (120 episodes each) in
  `results/core-v1/` (committed on 2026-10-10; previously listed under 0.1.0).
- Reference quoters `bayes-mean` (exact posterior mean ± k posterior sd, k tuned on a separate
  seed set by `scripts/tune_k.py`) and `bayes-lookahead` (one-step lookahead;
  `scripts/headroom.py`), with core-v1 traces.
- Report sections: centring vs width decomposition (`mmarena.decompose`) and run-to-run
  variability for replicate runs (`agent#rN`); bootstrap p-values for the classic − perturbed gap.
- New `core-v1` runs: opus 5.5 @medium, and replicates of opus 5.5 @high and haiku 5.5 @high.
- Effort-curve figure.

### Changed

- CI: `actions/checkout` v7 and `astral-sh/setup-uv` v10.3.0.
- LLM traces now record `cache_write_1h_tokens`, so cache writes are priced by their actual TTL.
- `scripts/figures.py` writes the example episode charts as PNG only.
- Classic − perturbed intervals resample hidden structures (the classic games of a family share
  one) and are Holm-adjusted across LLM setups; several intervals widened.
- REPORT.md drops P(best) (always 1.00 for `bayes`); comparisons anchor on `bayes`.
- Latency is the provider-reported time per call everywhere, not engine wall clock.
- README findings rewritten to match: the shortfall is width at low effort, width and centring
  at high effort; the classic-game advantage is no longer claimed as significant.

### Fixed

- Sonnet 5.5 cache-read price (0.10, not 0.20 USD per million tokens).
- sdist no longer lists a non-existent top-level `suites` directory.
- `claude-cli`: replies are attributed to the requested model. Claude Code 2.1.296 adds an
  auxiliary Haiku call listed first in `modelUsage`, which mislabelled and mispriced replies; its
  tokens are now recorded as `aux_input_tokens` / `aux_output_tokens`.

## [0.1.0] - 2026-10-09

### Added

- Five game families (dice, cards, transform, coin, urn), each with a classic and a perturbed
  variant, built deterministically from a seed.
- Exact public posterior over enumerated outcomes; exact one-step value of any quote, split
  into spread capture and adverse selection.
- Episode engine with common random numbers, tick widening, inventory limits and invalid-quote
  handling.
- Reference quoters: `bayes` (myopic optimal), `bayes-noflow`, `glosten-milgrom`, `static`,
  `random`.
- LLM agents through the Anthropic API, OpenAI-compatible servers and Claude Code headless
  mode, with retries, infra-error exclusion and an on-disk response cache.
- Suites `smoke`, `core-v1`, `full-v1`; resumable JSONL traces.
- Scoring and reports: edge captured, xPnL, belief and updating metrics, game-clustered
  bootstrap, paired permutation tests with Holm correction, variance analysis, figures.
- `mm-arena play`: practice mode with a step-by-step debrief against the Bayes quoter.
