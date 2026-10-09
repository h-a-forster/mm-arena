# mm-arena

[![CI](https://github.com/h-a-forster/mm-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/h-a-forster/mm-arena/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)

Market-making games as a benchmark for LLM agents, scored exactly against a Bayes-optimal quoter.

"Make me a market on the sum of three dice" is a standard trading-interview game. You quote a bid
and an ask, information arrives, some counterparties know more than you, and you settle at the
true value. Doing it well takes two skills: updating a belief from reveals *and from who trades
with you*, and pricing the risk of trading against someone better informed (adverse selection).

mm-arena puts an LLM in the market maker's seat. The hidden state is small enough to enumerate,
so the simulator knows the exact public posterior at every step. Every quote gets an exact
expected value, and every agent is compared with a Bayes-optimal quoter on the same dice and the
same counterparties.

## Results

`core-v1`: 60 games (5 families, classic and perturbed), one episode each, same episodes for
every agent. Claude 5.5 models via Claude Code headless mode (`claude -p`, no tools), October
2026. 95% intervals from a bootstrap over games. 0 invalid replies and 0 provider errors in
2,150 LLM quotes.

![Leaderboard](docs/figures/leaderboard.png)

| agent | edge captured % [95% CI] | width / Bayes | adverse / episode | β flow | β reveal | classic − perturbed | output tokens / quote |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 100 | 1.00 | 0.40 | 1.00 | 1.00 | 0 | - |
| **opus 5.5 @high** | 87.8 [83.2, 91.7] | 0.91 | 0.54 | 0.88 | 1.05 | +0.1 [-8.0, +8.4] | 1,751 |
| `bayes-noflow` | 87.5 [82.3, 91.8] | 1.03 | 0.44 | 0.00 | 0.88 | -2.4 [-12.4, +7.0] | - |
| **sonnet 5.5 @high** | 67.4 [59.8, 74.9] | 0.81 | 0.65 | 0.66 | 0.87 | +7.7 [-7.1, +21.5] | 1,611 |
| **opus 5.5 @low** | 61.9 [57.0, 66.4] | 0.63 | 0.80 | 0.79 | 0.87 | +5.8 [-3.3, +15.2] | 677 |
| `static` | 48.7 [34.4, 60.8] | 1.08 | 0.53 | 0.00 | 0.00 | +0.5 [-29.1, +27.6] | - |
| **sonnet 5.5 @low** | 12.3 [0.3, 22.4] | 0.42 | 0.91 | 0.21 | 0.79 | +21.9 [-0.1, +42.6] | 750 |
| `glosten-milgrom` | 4.1 [3.5, 4.8] | 0.27 | 1.06 | 0.91 | 0.98 | +1.1 [-0.2, +2.4] | - |
| **haiku 5.5 @low** | -0.8 [-14.7, 11.1] | 0.38 | 0.93 | 0.10 | 0.86 | +15.5 [-11.4, +39.7] | 1,744 |
| `random` | -83.2 [-113.7, -57.9] | 0.56 | 0.76 | -0.23 | 0.09 | +21.0 [-36.4, +78.1] | - |

Edge captured: expected P&L as a share of the Bayes quoter's on the same episodes (100 = Bayes,
0 = never quoting). Width, adverse selection and β are defined under [Metrics](#metrics).
`@low` / `@high` is the reasoning-effort setting.

**What the numbers say**

1. **Reasoning effort matters most.** Opus 5.5 goes from 62% to 88% of the Bayes edge
   between low and high effort, Sonnet 5.5 from 12% to 67%. Both jumps are significant (paired
   test over games, Holm-adjusted p < 0.01). Opus at high effort matches `bayes-noflow`, which
   knows the exact posterior from reveals but ignores order flow.
2. **The shortfall is spread width, not fair value.** Every model's mid is unbiased (mean
   signed error within ±0.03 posterior sd) and about as close to the posterior mean as
   `bayes-noflow`. But quotes are 0.38-0.91 times as wide as the Bayes quote. Haiku and Sonnet at
   low effort sit near the zero-profit Glosten-Milgrom width and lose more than twice as much to
   informed traders as Bayes (0.9 vs 0.4 prior sd per episode). Across agents, edge tracks width.
3. **Two models fall below a static quoter.** Sonnet at low effort (12%) and Haiku (-1%) do
   worse than `static`, which quotes the prior mean ± one sd and never updates (49%).
4. **Order flow is under-used.** After a trade, models move their quotes 10-88% as far as the
   Bayes quoter does (β flow). Public reveals are handled better (β reveal 0.79-1.05).
5. **Thinking more is not sufficient.** Haiku writes as many output tokens per quote as Opus at
   high effort (about 1,750) and captures no edge.
6. **No significant recall advantage.** The classic-minus-perturbed gap includes zero for every
   model. Sonnet at low effort is the borderline case (+21.9 points, CI -0.1 to +42.6).
7. **Realized P&L would not rank these models.** Separating Opus and Sonnet at high effort by
   0.1 prior sd per episode needs about 127 episodes with xPnL and about 1,125 with realized P&L
   (8.9 times as many). A leaderboard built on realized P&L from a few dozen episodes mostly
   measures luck.

Full report: [results/core-v1/REPORT.md](results/core-v1/REPORT.md). Traces for every episode
are in [results/core-v1/](results/core-v1/); `mm-arena report results/core-v1` rescores them.

![Edge vs quote width](docs/figures/spread.png)

![Realized vs expected P&L](docs/figures/variance.png)

One episode, Sonnet 5.5 at low effort on three standard dice. Its quotes (blue) hug the posterior
mean while the Bayes quotes (orange, dashed) stay wide. It made money on this episode by luck;
the expected value of its quotes was negative.

![Example episode](docs/figures/episode-sonnet-low.png)

## How it works

```
hidden state ω (dice, cards, coin bias, urn)      contract settles at V(ω)
stage 1: quote, quote, quote  ->  reveal die 1  ->  stage 2: quote, quote, quote  ->  ...  settle
each quote: one counterparty arrives
   informed (prob α): knows V, buys if V > ask, sells if V < bid
   noise (prob 1-α):  values at fair value + N(0, s), same rule
```

- **Exact posterior.** Outcomes are enumerated (at most 250k, usually a few hundred). Reveals and
  fills (and quiet steps) update the posterior by Bayes' rule under the disclosed trader model.
- **Exact score per quote.** For every quote, the simulator computes its expected one-step profit
  given public information, split into spread *capture* and *adverse* selection.
- **xPnL, not P&L.** The headline score sums those expectations along the path the agent played.
  It has the same expectation as realized P&L but strips out the luck of who arrived and what
  the dice were, the same idea as luck-adjusted scoring in poker (DIVAT, AIVAT).
- **Common random numbers.** The hidden outcome and every counterparty draw depend only on
  `(game, seed)`. All agents face identical episodes; comparisons are paired.
- **Contamination probe.** Each family has a *classic* variant (three standard dice, a 52-card
  deck) and *perturbed* variants generated per seed (odd dice, custom decks, unusual contracts).
  A model that does better on classic than perturbed games is recalling, not reasoning.

Details, formulas and limitations: [docs/methodology.md](docs/methodology.md).

### Reference quoters

| agent | what it does |
| --- | --- |
| `bayes` | exact posterior, quote maximising one-step expected profit. The 100 mark. |
| `bayes-noflow` | same, but ignores what trades reveal. The gap measures learning from order flow. |
| `glosten-milgrom` | exact posterior, zero-profit quote `ask = E[V \| buy]`. A tight market is not a profitable one. |
| `static` | prior mean ± one prior sd, never updated. |
| `random` | random quotes around the prior. |

### Game families

| family | hidden state | contract | classic variant |
| --- | --- | --- | --- |
| `dice` | 2-4 dice, custom faces, some loaded | sum | three d6 |
| `cards` | 2-3 cards from a custom deck | sum | three cards from a 52-card deck |
| `transform` | dice or cards | max, min, range, product, count above a threshold | product of two d6 |
| `coin` | coin picked from a set of biases, n flips | heads (times a multiplier) | fair or double-headed coin |
| `urn` | urn with an unknown number of red balls | red balls in the urn | uniform prior, 10 balls |

## Install

```sh
uv tool install "mm-arena[all] @ git+https://github.com/h-a-forster/mm-arena"
# or
pip install "mm-arena[all] @ git+https://github.com/h-a-forster/mm-arena"
```

Python 3.11+. The only required dependency is numpy. Extras: `anthropic`, `openai`, `plot`
(matplotlib), `all`.

## Quick start

Baselines need no API key and finish in seconds:

```sh
mm-arena run --agent bayes --agent static --agent glosten-milgrom --suite core-v1
mm-arena report runs/core-v1
```

Run a model:

```sh
export ANTHROPIC_API_KEY=...
mm-arena run --agent anthropic:claude-sonnet-5-5@low --suite core-v1 --limit 1

export OPENAI_API_KEY=...
mm-arena run --agent openai:gpt-5.1 --suite core-v1

# any OpenAI-compatible server: vLLM, Ollama, LM Studio, OpenRouter
mm-arena run --agent "openai:qwen3:8b@http://localhost:11434/v1" --suite smoke

# Claude Code headless mode, using the local login
mm-arena run --agent claude-cli:claude-opus-5-5@low --suite core-v1 --limit 1

mm-arena report runs/core-v1
```

Play it yourself, then get a step-by-step comparison with the Bayes quoter:

```sh
mm-arena play --family dice --variant classic
```

Other commands:

```sh
mm-arena prompt --family coin --seed 3     # the exact prompt an LLM sees
mm-arena games --suite core-v1             # list games
mm-arena show runs/core-v1/bayes.jsonl --episode 3 --plot ep.png
mm-arena suites
```

### Agent specs

| spec | meaning |
| --- | --- |
| `bayes`, `bayes-noflow`, `glosten-milgrom`, `static`, `random` | reference quoters |
| `anthropic:MODEL[@EFFORT]` | Anthropic Messages API (`ANTHROPIC_API_KEY`) |
| `openai:MODEL[@BASE_URL][@EFFORT]` | OpenAI or any compatible server (`OPENAI_API_KEY`, `OPENROUTER_API_KEY` for openrouter.ai) |
| `claude-cli:MODEL[@EFFORT]` | `claude -p` with no tools, no MCP, no settings |
| `scripted:TEXT` | fixed reply, for tests |

Runs are resumable: rerunning the same command skips finished episodes. Replies are cached in
`.mmarena-cache/`, keyed by the full request plus game, episode and attempt, so a rerun or a
rescore costs nothing. Provider failures (auth, rate limits, outages) exclude the episode instead
of scoring it.

## Metrics

| metric | meaning | ideal |
| --- | --- | --- |
| edge captured | `100 · Σ xPnL / Σ xPnL(bayes)` on shared episodes | 100 |
| xPnL/sd, PnL/sd | expected and realized P&L per episode, in prior sd of the value | high |
| width / Bayes | quote width relative to the Bayes quote at the same state | ~1 |
| adverse | expected loss to informed traders per episode | low |
| mid abs z | distance of the quote mid from the posterior mean, in posterior sd | ~0 |
| β flow, β reveal | how much the mid moves per unit of Bayes-optimal move, after trades and after reveals | 1 |
| dominated | quotes that lose for sure if hit (bid above the highest possible value) | 0 |
| invalid | unparseable or crossed replies | 0 |

## Suites

| suite | games | episodes | use |
| --- | --- | --- | --- |
| `smoke` | 5 | 5 | CI, quick checks |
| `core-v1` | 60 | 120 (`--limit 1`: 60) | the leaderboard |
| `full-v1` | 160 | 480 | tighter intervals |

Suites are versioned. A generator change that alters any game ships as a new suite version.

## Reproduce

```sh
git clone https://github.com/h-a-forster/mm-arena && cd mm-arena
uv sync --all-extras --dev
uv run pytest
uv run mm-arena run --suite core-v1 --limit 1 --out runs/core-v1   --agent bayes --agent bayes-noflow --agent glosten-milgrom --agent static --agent random
for spec in claude-haiku-5-5@low claude-sonnet-5-5@low claude-opus-5-5@low             claude-sonnet-5-5@high claude-opus-5-5@high; do
  uv run mm-arena run --agent claude-cli:$spec --suite core-v1 --limit 1 --out runs/core-v1
done
uv run mm-arena report runs/core-v1
uv run python scripts/figures.py runs/core-v1 docs/figures
```

## Limitations

- Stylised market: one counterparty per step, unit size, informed traders see the value
  exactly, noise traders value around the exact public mean.
- The reference is myopic. It does not value the information a quote generates, so a score
  above 100 is possible.
- The trader model is disclosed in full. The benchmark measures reasoning under a known model,
  not estimating one.
- LLM scores depend on the prompt and provider settings. Both are recorded in every trace; the
  prompt is fixed for a suite version.
- One run per model and effort. Intervals cover game sampling, not run-to-run variation of the
  model.

## Related work

Builds on Glosten and Milgrom (1985) for the market model and on DIVAT/AIVAT for luck-adjusted
evaluation. Unlike LLM trading benchmarks that score realized P&L on market data (StockBench,
InvestorBench, Alpha Arena), it measures belief updating and adverse-selection pricing where the
optimal answer is known. See [docs/related-work.md](docs/related-work.md).

## Citation

```bibtex
@software{mm_arena,
  title  = {mm-arena: market-making games as a benchmark for LLM agents},
  author = {{h-a-forster}},
  year   = {2026},
  url    = {https://github.com/h-a-forster/mm-arena}
}
```

## License

MIT
