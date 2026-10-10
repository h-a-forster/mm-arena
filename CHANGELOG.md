# Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `mmarena.pricing`: API list prices. Reports cost runs from recorded token counts instead of the
  provider's own figure (Claude Code priced Haiku 5.5 at Opus rates).
- Cost figure and README section: edge captured against list price and latency per setup, with
  the Pareto frontier.

### Fixed

- Sonnet 5.5 cache-read price (0.10, not 0.20 USD per million tokens).

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
- Results for Claude 5.5 and Fable 5.1 models on `core-v1` (120 episodes each) in
  `results/core-v1/`.
