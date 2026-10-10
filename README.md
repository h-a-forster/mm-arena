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

`core-v1`: 60 games (5 families, classic and perturbed), 2 episodes each, the same 120 episodes
for every agent. Claude 5.5 and Fable 5.1 models via Claude Code headless mode (`claude -p`, no
tools), October 2026. 95% intervals from a bootstrap over games. 0 invalid replies and 0 provider
errors in 6,880 LLM quotes.

![Leaderboard](docs/figures/leaderboard.png)

| agent | edge captured % [95% CI] | width / Bayes | adverse / episode | β flow | β reveal | classic − perturbed | output tokens / quote |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bayes` | 100 | 1.00 | 0.41 | 1.00 | 1.00 | 0 | - |
| **fable 5.1 @high** | 90.7 [87.5, 93.3] | 0.92 | 0.54 | 1.03 | 0.99 | +1.4 [-3.9, +6.8] | 2,101 |
| `bayes-noflow` | 88.5 [83.9, 92.1] | 1.03 | 0.44 | 0.00 | 0.93 | -0.1 [-8.1, +7.9] | - |
| **opus 5.5 @high** | 87.7 [83.7, 91.2] | 0.90 | 0.55 | 0.98 | 1.03 | +2.3 [-4.7, +9.5] | 1,750 |
| **haiku 5.5 @high** | 79.9 [72.9, 85.2] | 0.94 | 0.53 | 0.30 | 0.91 | +4.8 [-8.6, +16.8] | 6,516 |
| **sonnet 5.5 @high** | 69.2 [63.8, 74.8] | 0.80 | 0.67 | 0.66 | 0.90 | +12.5 [+1.9, +22.5] | 1,620 |
| **opus 5.5 @low** | 60.0 [56.4, 63.7] | 0.61 | 0.83 | 0.84 | 0.94 | +9.6 [+2.8, +16.9] | 664 |
| **fable 5.1 @low** | 59.8 [55.7, 64.0] | 0.61 | 0.81 | 0.98 | 0.94 | -1.3 [-9.4, +6.5] | 752 |
| `static` | 47.4 [36.2, 56.3] | 1.07 | 0.56 | 0.00 | 0.00 | +4.9 [-15.5, +24.9] | - |
| **sonnet 5.5 @low** | 14.8 [5.8, 22.1] | 0.43 | 0.93 | 0.33 | 0.83 | +21.5 [+7.4, +35.6] | 757 |
| `glosten-milgrom` | 4.3 [3.7, 5.0] | 0.27 | 1.09 | 0.96 | 1.00 | +0.8 [-0.5, +2.2] | - |
| **haiku 5.5 @low** | -0.4 [-13.7, 10.7] | 0.38 | 0.93 | 0.17 | 0.87 | +17.0 [-9.4, +39.3] | 1,706 |
| `random` | -80.3 [-107.7, -58.1] | 0.56 | 0.77 | -0.02 | 0.15 | +20.5 [-31.4, +70.6] | - |

Edge captured: expected P&L as a share of the Bayes quoter's on the same episodes (100 = Bayes,
0 = never quoting). Width, adverse selection and β are defined under [Metrics](#metrics).
`@low` / `@high` is the reasoning-effort setting.

**What the numbers say**

1. **Reasoning effort matters most.** From low to high effort, Haiku 5.5 goes from 0% to 80% of
   the Bayes edge, Sonnet 5.5 from 15% to 69%, Opus 5.5 from 60% to 88% and Fable 5.1 from 60%
   to 91%. All four jumps are significant (paired test over games, Holm-adjusted p < 0.01). At
   high effort, Fable and Opus match `bayes-noflow`, which knows the exact posterior from
   reveals but ignores order flow. Fable leads Opus by 3.0 points [1.1, 5.2] (Holm p = 0.02).
2. **The shortfall is spread width, not fair value.** Every model's mid is close to unbiased
   (mean signed error at most +0.09 posterior sd). But quotes are 0.38-0.94 times as wide as the
   Bayes quote. At low effort, Haiku and Sonnet quote at under half the Bayes width, closer to
   the zero-profit Glosten-Milgrom quote (0.27), and lose more than twice as much to informed
   traders as Bayes (0.93 vs 0.41 prior sd per episode). Across agents, edge tracks width.
3. **Two setups fall below a static quoter.** Sonnet (15%) and Haiku (0%) at low effort do
   worse than `static`, which quotes the prior mean ± one sd and never updates (47%).
4. **Order flow separates the top models.** After a trade, Fable and Opus move their quotes
   about as far as the Bayes quoter does (β flow 0.84-1.03). Haiku at high effort reaches 80%
   with β flow 0.30: it quotes wide enough to survive informed traders but barely learns from
   them, like `bayes-noflow`. Every model handles public reveals well (β reveal 0.83-1.03).
5. **Token count does not explain it.** Haiku at low effort writes as many output tokens per
   quote as Opus at high effort (about 1,700) and captures no edge. At high effort Haiku writes
   about 6,500 per quote, 3.7 times as many as Opus, to reach 80%.
6. **Some setups do better on textbook games.** Sonnet at both efforts and Opus at low effort
   score 10-22 points higher on classic games than on perturbed ones (95% intervals exclude
   zero; not corrected for multiple comparisons). Fable at both efforts and Opus at high effort
   show no gap. This fits recall, but textbook setups (standard dice, uniform priors) may also be
   easier to compute. The design does not separate the two.
7. **Realized P&L would not rank these models.** Detecting a difference of 0.1 prior sd per
   episode between Fable and Opus at high effort needs about 25 episodes with xPnL and about 444
   with realized P&L (18 times as many). For single LLM agents the ratio is 4-12. A leaderboard
   built on realized P&L from a few dozen episodes mostly measures luck.

Full report: [results/core-v1/REPORT.md](results/core-v1/REPORT.md). Traces for every episode
are in [results/core-v1/](results/core-v1/); `mm-arena report results/core-v1` rescores them.

![Edge vs quote width](docs/figures/spread.png)

![Realized vs expected P&L](docs/figures/variance.png)

One episode, Sonnet 5.5 at low effort on the classic urn game. After the first draw its quotes
(blue) hug the posterior mean; the Bayes quotes (orange, dashed) are almost three times as wide
overall. Expected profit
of its quotes: 6.5. The Bayes quoter, from the same states: 15.2.

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
  A model that does better on classic than perturbed games may be recalling rather than
  reasoning.

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
| `core-v1` | 60 | 120 | the leaderboard |
| `full-v1` | 160 | 480 | tighter intervals |

Suites are versioned. A generator change that alters any game ships as a new suite version.

## Reproduce

```sh
git clone https://github.com/h-a-forster/mm-arena && cd mm-arena
uv sync --all-extras --dev
uv run pytest
uv run mm-arena run --suite core-v1 --out runs/core-v1   --agent bayes --agent bayes-noflow --agent glosten-milgrom --agent static --agent random
for model in claude-haiku-5-5 claude-sonnet-5-5 claude-opus-5-5 claude-fable-5-1; do
  for effort in low high; do
    uv run mm-arena run --agent claude-cli:$model@$effort --suite core-v1 --out runs/core-v1
  done
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
